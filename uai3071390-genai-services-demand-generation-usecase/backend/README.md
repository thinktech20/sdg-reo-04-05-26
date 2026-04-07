# SDG Backend Workspace

Python 3.13 uv workspace containing all SDG backend services, agents, and shared libraries.

## ADO Tickets

- [587882 — Risk Analysis Agent: Service Layer Base](https://dev.azure.com/vernova/PWRDT-DataScience%20AI/_workitems/edit/587882)
- [606418 — T1001 SDG Risk Analysis Agent - Software Architecture Setup](https://dev.azure.com/vernova/PWRDT-DataScience%20AI/_workitems/edit/606418)

## Workspace Members

| Package | Path | Local uv port | Docker Compose host port |
|---|---|---:|---:|
| sdg-commons | libs/commons | n/a | n/a |
| sdg-data-service | services/data-service | 8001 | 8086 |
| sdg-risk-eval-assistant | agents/risk-evaluation-assistant | 8002 | 8082 |
| sdg-narrative-assistant | agents/narrative-summary-assistant | 8003 | 8083 |
| sdg-event-history-assistant | agents/event-history-assistant | 8004 | 8084 |
| sdg-qna-agent | agents/question-answer-agent | 8005 | 8087 |
| sdg-orchestrator | agents/orchestrator | 8006 | internal only |

## Architecture Setup (T1001)

1. Data-service provides canonical retrieval endpoints and MCP tools.
2. Risk-evaluation assistant computes findings and risk categories.
3. Narrative and event-history assistants generate downstream analysis.
4. Orchestrator coordinates pipeline execution and status transitions.

Compatibility hardening includes mock-safe fallbacks, backward-compatible request handling, and expanded coverage in risk-eval internals.

## Setup

```bash
cd backend
uv sync
```

## Test Commands

```bash
cd backend

# Full backend suite
USE_MOCK=true USE_MOCK_ASSESSMENTS=true ORCHESTRATOR_USE_DYNAMODB=false ORCHESTRATOR_CHECKPOINTER_TYPE=memory uv run pytest

# Focused package run (example)
uv run pytest agents/risk-evaluation-assistant/
```

## Lint and Type Checks

```bash
cd backend
uv run ruff check .
uv run ruff format --check .
uv run mypy .
```

## Workspace Layout

```text
backend/
├── pyproject.toml
├── uv.lock
├── uv.toml
├── .python-version
├── .env.example
├── libs/
│   └── commons/
├── services/
│   └── data-service/
└── agents/
    ├── risk-evaluation-assistant/
    ├── narrative-summary-assistant/
    ├── event-history-assistant/
    ├── question-answer-agent/
    └── orchestrator/
```
