# sdg-orchestrator

LangGraph-based orchestration service for SDG analysis flow.

## ADO Ticket

- [587972 — LangChain Orchestrator Setup](https://dev.azure.com/vernova/PWRDT-DataScience%20AI/_workitems/edit/587972)

## Ports

- Local uv run: 8006
- Docker Compose: internal service only (container listens on 8081)

## Pipeline Role

The orchestrator manages assessment job execution and status transitions for downstream assistants.

## API Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | /health | Health check |
| GET | /orchestrator/health | Prefixed health |
| POST | /orchestrator/api/v1/assessments/{assessment_id}/run | Start pipeline job |
| GET | /orchestrator/api/v1/assessments/{assessment_id}/status | Poll job status |

## Local Modes

| Variable | Effect |
|---|---|
| ORCHESTRATOR_LOCAL_MODE=true | Skip real downstream calls (stub mode) |
| ORCHESTRATOR_USE_DYNAMODB=false | Keep job store in-memory for local tests |
| ORCHESTRATOR_CHECKPOINTER_TYPE=memory | Use memory checkpointer |

## Local Run

```bash
cd backend
uv run uvicorn orchestrator.main:app --port 8006 --reload
```

## Tests

```bash
cd backend
uv run pytest agents/orchestrator/
```
