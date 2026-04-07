# Hot-Reload Prompts — Design Proposal

## Problem

System prompts are currently bundled inside the container image (`.txt` or `.py` files). Any prompt change requires a new image build and ECS redeployment, which adds latency and risk to prompt iteration.

## Goal

Allow prompt updates to take effect without redeploying container images.

## Options Considered

### Option 1: S3-backed prompts with TTL cache (Recommended)

- Store prompts in an S3 bucket (already have boto3 + S3 for session management).
- Agent loads prompt on first request, caches in-memory with a TTL (e.g., 5 minutes).
- Falls back to bundled `.txt` file if S3 read fails.
- To update: upload new prompt to S3 → takes effect within TTL, no redeploy.

**Pros**: Simple, no new infra, S3 versioning gives rollback for free, works for all agents.
**Cons**: Up to TTL seconds delay before new prompt is active; S3 read latency on cache miss (~50ms).

### Option 2: DynamoDB-backed prompts

- Same pattern as Option 1 but store prompt text in DynamoDB (already have tables).
- Slightly faster reads than S3.

**Pros**: Low latency, consistent reads, already in the stack.
**Cons**: DynamoDB is not ideal for large text blobs (400KB item limit); prompts may grow.

### Option 3: Admin reload endpoint

- Keep prompts bundled on disk in the container.
- Add `POST /admin/reload-prompts` endpoint that re-reads files from disk.
- Requires a new container image for the file change, but no ECS service restart — just hit the endpoint.

**Pros**: No external dependency.
**Cons**: Still requires image rebuild; less useful than S3.

## Recommended: Option 1 (S3)

### S3 Key Structure

```
s3://<session-bucket>/prompts/
  qna/
    re_system_prompt.txt
    oe_system_prompt.txt
  narrative-summary/
    system_prompt.txt
  event-history/
    system_prompt.txt
  risk-evaluation/
    system_prompt.txt
    risk_analysis_user_prompt_gen.yaml
```

Reuses the existing S3 session bucket (`SESSION_S3_BUCKET_NAME`).

### Implementation Sketch (QnA Agent)

```python
# prompts/__init__.py
import time
import logging
from pathlib import Path

import boto3

logger = logging.getLogger(__name__)

_DIR = Path(__file__).resolve().parent
_CACHE: dict[str, tuple[str, float]] = {}
_TTL = 300  # seconds (5 minutes)

# Bundled prompts (fallback)
_BUNDLED: dict[str, str] = {
    "RE": (_DIR / "re_system_prompt.txt").read_text(encoding="utf-8"),
    "OE": (_DIR / "oe_system_prompt.txt").read_text(encoding="utf-8"),
}

_S3_PREFIX = "prompts/qna/"


def get_system_prompt(
    persona: str,
    s3_bucket: str | None = None,
    s3_client=None,
) -> str:
    key = persona.upper()
    now = time.time()

    # Return cached if still fresh
    if key in _CACHE and (now - _CACHE[key][1]) < _TTL:
        return _CACHE[key][0]

    # Try S3
    if s3_bucket:
        s3_key = f"{_S3_PREFIX}{key.lower()}_system_prompt.txt"
        try:
            client = s3_client or boto3.client("s3")
            obj = client.get_object(Bucket=s3_bucket, Key=s3_key)
            text = obj["Body"].read().decode("utf-8")
            _CACHE[key] = (text, now)
            logger.info("Loaded prompt from s3://%s/%s", s3_bucket, s3_key)
            return text
        except Exception:
            logger.warning(
                "S3 prompt load failed (s3://%s/%s), using bundled",
                s3_bucket, s3_key,
            )

    # Fallback to bundled
    text = _BUNDLED.get(key)
    if text is None:
        raise ValueError(f"Unknown persona: {persona!r}")
    _CACHE[key] = (text, now)
    return text
```

### Config Changes

Add to `config.py`:
```python
PROMPT_S3_ENABLED: bool = os.getenv("PROMPT_S3_ENABLED", "false").lower() == "true"
```

When `PROMPT_S3_ENABLED=false` (default), the agent behaves exactly as today — bundled files only.

### Applying to Other Agents

Same pattern applies to narrative-summary, event-history, and risk-evaluation agents:
1. Add S3 prompt loader to each agent's prompt module.
2. Change `SYSTEM_PROMPT` from a module-level constant to a function call.
3. Add fallback to bundled file.

### Updating a Prompt (no redeploy)

```bash
# Upload new prompt
aws s3 cp re_system_prompt.txt s3://<bucket>/prompts/qna/re_system_prompt.txt

# Verify (optional)
aws s3 cp s3://<bucket>/prompts/qna/re_system_prompt.txt -

# Takes effect within 5 minutes (TTL)
```

### Rollback

```bash
# S3 versioning — restore previous version
aws s3api list-object-versions --bucket <bucket> --prefix prompts/qna/re_system_prompt.txt
aws s3api copy-object --bucket <bucket> --key prompts/qna/re_system_prompt.txt \
  --copy-source "<bucket>/prompts/qna/re_system_prompt.txt?versionId=<prev-version-id>"
```

## Current Prompt Locations (for reference)

| Agent | Prompt File | Format |
|---|---|---|
| QnA (RE) | `backend/agents/question-answer-agent/src/question_answer/prompts/re_system_prompt.txt` | .txt |
| QnA (OE) | `backend/agents/question-answer-agent/src/question_answer/prompts/oe_system_prompt.txt` | .txt |
| Narrative Summary | `backend/agents/narrative-summary-assistant/src/narrative_summary/prompts.py` | Python string |
| Event History | `backend/agents/event-history-assistant/src/event_history/prompts.py` | Python string |
| Risk Evaluation (system) | `backend/agents/risk-evaluation-assistant/src/risk_evaluation/prompt_lib/system_prompt.txt` | .txt |
| Risk Evaluation (user template) | `backend/agents/risk-evaluation-assistant/src/risk_evaluation/prompt_lib/risk_analysis_user_prompt_gen.yaml` | YAML |

## Effort Estimate

- Small: QnA agent only (already uses .txt files, minimal change).
- Medium: All agents (narrative-summary and event-history need refactor from module constants to function calls).
