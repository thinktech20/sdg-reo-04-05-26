# sdg-risk-eval-assistant

Risk analysis assistant that produces structured findings and risk categories.

## ADO Tickets

- [587982 — Risk Evaluation Assistant Base Setup](https://dev.azure.com/vernova/PWRDT-DataScience%20AI/_workitems/edit/587982)
- [606418 — T1001 SDG Risk Analysis Agent - Software Architecture Setup](https://dev.azure.com/vernova/PWRDT-DataScience%20AI/_workitems/edit/606418)

## Ports

- Local uv run: 8002
- Docker Compose host: 8082

## API Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | /health | Service liveness |
| GET | /riskevaluationassistant/health | Prefixed liveness |
| GET | /riskevaluationassistant/api/v1/risk-eval/healthcheck | API healthcheck route |
| POST | /riskevaluationassistant/api/v1/risk-eval/run | Run risk evaluation |

## Request Model (summary)

```json
{
  "esn": "ESN-12345",
  "query": "Analyze stator risk",
  "assessment_id": "ASS-001",
  "persona": "RE",
  "workflow_id": "RE_RISK",
  "component_type": "Stator",
  "filters": {
    "dataTypes": ["er", "fsr"],
    "dateFrom": "2025-01-01",
    "dateTo": "2025-12-31"
  }
}
```

## Architecture Notes

- Supports backward-compatible mode when workflow_id is absent.
- Supports orchestrated flow when workflow_id is present.
- Integrates with data-service for heatmap/IBAT/FSR/ER retrieval.
- Persists normalized findings and retrieval metadata for downstream consumers.

## Local Run

```bash
cd backend
uv run uvicorn risk_evaluation.main:app --port 8002 --reload
```

## Tests

```bash
cd backend
uv run pytest agents/risk-evaluation-assistant/
```
