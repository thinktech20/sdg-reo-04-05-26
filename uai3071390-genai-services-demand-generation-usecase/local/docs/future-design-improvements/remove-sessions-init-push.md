# Remove `/sessions/init` push from data-service

**Date:** April 6, 2026  
**Status:** Analysis complete — ready for cleanup

---

## Problem

CloudWatch logs for the QnA agent (`questionansweragent`) show recurring `404 Not Found` entries:

```
INFO  10.244.254.116:48284 - "POST /questionansweragent/api/v1/sessions/init HTTP/1.1" 404 Not Found
INFO  10.244.254.116:54036 - "POST /questionansweragent/api/v1/sessions/init HTTP/1.1" 404 Not Found
```

These appear every time an analysis (RE or OE) completes in the dev environment, mixed in with health check 200s. The 404s are harmless (the caller swallows errors) but create noise in production logs and could mask real issues.

---

## Root Cause

The data-service fires a POST to the QnA agent after every completed analysis:

**Caller:** `data_service/routes/assessments.py` → `_init_qna_session()`  
**Trigger:** After orchestrator reports `COMPLETE` for any `*_DEFAULT` workflow  
**Target:** `POST {QNA_AGENT_URL}/questionansweragent/api/v1/sessions/init`

```python
# assessments.py line ~341
if orchestrator_status == "COMPLETE":
    _persist_result(...)
    if not workflow_id.endswith("_NARRATIVE"):
        await _init_qna_session(assessment_id, persona, result)  # ← 404
```

The QnA agent **never implemented** this endpoint. It was added on March 12, 2026 (commit `d3de080`) as part of the initial E2E wiring, with the intent to pre-seed the Q&A session with analysis results so the first chat would be faster.

---

## Design Analysis

### Current architecture (pull model)

The QnA agent already has a well-established pull model:

1. Every chat request includes `assessment_id` + `serialNumber`
2. The agent connects to the data-service via MCP
3. The agent uses tools (`read_re_table`, `read_oe_table`, `read_re_report`, etc.) to pull exactly the data it needs based on the user's question
4. Tool selection is driven by the LLM — it only fetches what's relevant

### What `/sessions/init` tries to do (push model)

After analysis completes, data-service pushes the full result payload to the QnA agent to "warm up" the session. This is a push model where:

- Data-service sends the complete analysis result (could be large)
- QnA agent would cache it for the first chat turn
- Subsequent tool calls would still go through MCP anyway

### Why the push model is unnecessary

1. **Redundant** — The agent already has MCP tools to fetch any data it needs on-demand. The push duplicates what the pull model does.

2. **Stateless architecture conflict** — The QnA agent builds a fresh `Agent` instance per request (due to Strands threading constraints). There's no persistent in-memory session to pre-seed.

3. **Coupling** — Data-service shouldn't need to know about the QnA agent's URL or API contract. The current architecture has clean responsibility separation: data-service serves data via MCP, agent consumes it.

4. **No performance benefit** — The first chat turn calls MCP tools regardless. Pre-seeding would only help if the agent could skip tool calls, but the system prompt instructs it to always ground answers in tool outputs.

5. **Config burden** — Requires `QNA_AGENT_URL` in data-service config, adding another service discovery dependency. In ECS, this means cross-service networking for a call that provides no value.

---

## Recommendation

**Remove `_init_qna_session` and the call site entirely.** No stub endpoint needed in the QnA agent.

### Files to change

| File | Change |
|------|--------|
| `data_service/routes/assessments.py` | Remove `_init_qna_session()` function and its call site (~line 341) |
| `data_service/config.py` | Remove `QNA_AGENT_URL` if no other callers use it |
| `question_answer/api/v1/endpoints.py` | Remove the stub `/sessions/init` endpoint (if added) |

### What NOT to do

- Don't move this to the orchestrator — same coupling problem, different service
- Don't implement the endpoint for real — the pull model via MCP tools is the right pattern
- If future latency optimization is needed, consider MCP tool response caching in the agent rather than reintroducing a push model
