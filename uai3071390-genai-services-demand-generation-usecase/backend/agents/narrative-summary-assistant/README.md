# sdg-narrative-assistant

Generates structured narrative summaries from assessment findings and feedback.

## ADO Ticket

- [587976 — Narrative Summary Assistant Base Setup](https://dev.azure.com/vernova/PWRDT-DataScience%20AI/_workitems/edit/587976)

## Ports

- Local uv run: 8003
- Docker Compose host: 8083

## Endpoints

| Method | Path |
|---|---|
| GET | /health |
| GET | /summarizationassistant/health |
| POST | /api/v1/narrative/run |
| POST | /summarizationassistant/api/v1/narrative/run |

## Request Model (summary)

```json
{
  "assessment_id": "ASS-001",
  "esn": "ESN-12345",
  "persona": "RE"
}
```

The service fetches findings and feedback from data-service and returns structured narrative sections.

## Local Run

```bash
cd backend
uv run uvicorn narrative_summary.main:app --port 8003 --reload
```

## Tests

```bash
cd backend
uv run pytest agents/narrative-summary-assistant/
```
