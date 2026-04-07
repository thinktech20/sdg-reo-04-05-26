# sdg-data-service

Canonical backend API and MCP data backend for SDG.

- Serves frontend data APIs.
- Serves internal APIs consumed by orchestrator and assistants.
- Exposes MCP tools at /mcp for tool-based agent calls.

## Ports

- Local uv run: 8001
- Docker Compose host: 8086

## Key Responsibilities

| Area | Description |
|---|---|
| Frontend API | Assessment, units, findings, documents, and related reads/writes |
| Agent Data API | Heatmap, IBAT, PRISM, ER, retriever endpoints |
| MCP Tools | FastMCP-backed tool discovery/call path at /mcp |
| Internal State | Execution-state patch endpoints used by orchestrator |

## Endpoint Groups

| Group | Prefix |
|---|---|
| Health | /health, /dataservices/health |
| Core APIs | /api/v1/* (router-specific) |
| Assessments canonical | /dataservices/api/v1/assessments/* |
| Assessments legacy alias | /api/assessments/* |
| Internal orchestrator state | /internal/assessments/* |
| MCP | /mcp |

## Local Run

```bash
cd backend
uv run uvicorn data_service.main:app --port 8001 --reload
```

## Tests

```bash
cd backend
uv run pytest services/data-service/
```

## Docker Compose

```bash
cd sdg-usecase
docker compose up --build data-service
```
