# sdg-event-history-assistant

Builds event-history analysis output for assessments.

## ADO Ticket

- [587980 — Event History Assistant Base Setup](https://dev.azure.com/vernova/PWRDT-DataScience%20AI/_workitems/edit/587980)

## Ports

- Local uv run: 8004
- Docker Compose host: 8084

## Endpoints

| Method | Path |
|---|---|
| GET | /health |
| GET | /eventhistoryassistant/health |
| POST | /eventhistoryassistant/api/v1/event-history/run |

## Request Model (summary)

```json
{
  "assessment_id": "ASS-001",
  "esn": "ESN-12345",
  "persona": "RE",
  "event_data": []
}
```

## Local Run

```bash
cd backend
uv run uvicorn event_history.main:app --port 8004 --reload
```

## Tests

```bash
cd backend
uv run pytest agents/event-history-assistant/
```
