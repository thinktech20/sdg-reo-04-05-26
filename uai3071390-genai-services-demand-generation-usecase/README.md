# SDG Use Case - Risk Analysis Platform

AI-powered risk assessment platform for gas turbine reliability and outage workflows.

## Current Status

- Architecture setup for T1001 is complete across frontend, data-service, orchestrator, and assistants.
- Risk-evaluation compatibility paths are hardened for both legacy and orchestrated workflows.
- Local stack is fully containerized through Docker Compose, with optional per-service local uv runs.

## Repository Structure

```text
sdg-usecase/
├── frontend/                         # React + Vite UI
├── backend/
│   ├── libs/
│   │   └── commons/                 # Shared backend library
│   ├── services/
│   │   └── data-service/            # API and MCP data backend
│   └── agents/
│       ├── risk-evaluation-assistant/
│       ├── narrative-summary-assistant/
│       ├── event-history-assistant/
│       ├── question-answer-agent/
│       └── orchestrator/
└── compose.yml                       # Local full stack
```

## Runtime Topology

```text
Frontend (3000)
  -> /api/* -> Data Service (8086 in compose)
  -> /qna/* -> QnA Agent (8087 in compose)

Data Service
  -> Orchestrator (internal)
  -> writes/reads DynamoDB local (compose)

Orchestrator
  -> Risk Eval (8082 internal)
  -> Narrative (8083 internal)
  -> Event History (8084 internal)
```

## Quickstart (Docker Compose)

```bash
cd sdg-usecase
cp backend/.env.example backend/.env
docker compose up --build
```

## Service Ports (Docker Compose host)

| Service | Port |
|---|---|
| frontend | 3000 |
| data-service | 8086 |
| risk-evaluation-assistant | 8082 |
| narrative-summary-assistant | 8083 |
| event-history-assistant | 8084 |
| question-answer-agent | 8087 |
| dynamodb-local | 8000 |
| minio api | 9000 |
| minio console | 9001 |
| orchestrator | internal only |

## Quality Gate Commands

```bash
# Backend
cd backend
USE_MOCK=true USE_MOCK_ASSESSMENTS=true ORCHESTRATOR_USE_DYNAMODB=false ORCHESTRATOR_CHECKPOINTER_TYPE=memory uv run pytest

# Frontend
cd ../frontend
pnpm test:run
pnpm test:e2e

# Full container build
cd ..
docker compose build
```

## ADO Tickets

- [587882 — Risk Analysis Agent: Service Layer Base](https://dev.azure.com/vernova/PWRDT-DataScience%20AI/_workitems/edit/587882)
- [606418 — T1001 SDG Risk Analysis Agent - Software Architecture Setup](https://dev.azure.com/vernova/PWRDT-DataScience%20AI/_workitems/edit/606418)
