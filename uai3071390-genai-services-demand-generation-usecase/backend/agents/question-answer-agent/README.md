# sdg-qna-agent

User-facing chat agent for reliability and outage personas.

## Ports

- Local uv run: 8005
- Docker Compose host: 8087

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | /health | Liveness |
| GET | /ready | Dependency readiness |
| POST | /api/v1/chat | Internal chat contract |
| POST | /api/assessments/{assessment_id}/chat/reliability | Frontend RE chat |
| POST | /api/assessments/{assessment_id}/chat/outage | Frontend OE chat |
| GET | /questionansweragent/health | ALB-prefixed liveness |
| GET | /questionansweragent/ready | ALB-prefixed readiness |

## Runtime Dependencies

1. LiteLLM proxy
2. Data-service MCP endpoint
3. S3 or MinIO session storage
4. Auth mode (local skip or ALB JWT validation)

## Important Config

| Variable | Default |
|---|---|
| DATA_SERVICE_URL | http://localhost:8001 |
| MCP_SERVER_URL | {DATA_SERVICE_URL}/mcp/ |
| PORT / SERVER_PORT | 8005 |
| AUTH_LOCAL_MODE | true |
| S3_LOCAL_MODE | false |

For Docker Compose, these are overridden to container-network values.

## Local Run

```bash
cd backend
uv run uvicorn question_answer.main:app --port 8005 --reload
```

## Tests

```bash
cd backend
uv run pytest agents/question-answer-agent/
```
