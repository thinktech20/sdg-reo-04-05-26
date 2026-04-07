# Q&A Agent — End-to-End Test Instructions (v2)

## Prerequisites

1. **Docker Desktop** — must be running before any `docker compose` commands.
   Check with `docker info`. If you get `command not found` or a connection error,
   start Docker Desktop from Windows first and wait for it to be ready.

2. **GE Enterprise certs** in `backend/certs/`:
   - `GE_Enterprise_Root_CA_2_1.pem`
   - `GE_External_Root_CA_2_1.crt`

3. **`backend/.env`** — copy from `.env.example` and fill in:
   - `LITELLM_API_KEY` (required — your LiteLLM proxy key)
   - `LITELLM_PROXY_URL` (default: `https://dev-gateway.apps.gevernova.net`)
  - `LITELLM_MODEL` (recommended: `litellm_proxy/bedrock-claude-sonnet-4.5`)
   - `USE_MOCK=false` (set `true` for quick smoke test without Databricks)
   - Databricks / Naksha vars (required when `USE_MOCK=false`)

4. **AWS credentials** (for real S3 session storage):
   ```bash
   gossamer3 login \
     --role arn:aws:iam::337693406325:role/vn/account-privileged \
     --disable-keychain --force
   ```
   Credentials expire after ~1 hour. Re-login as needed.

---

## Option A: Docker Compose (recommended)

This spins up the entire stack in containers. No `uv run` needed.

### A.1 — With MinIO (local S3)

Default — no AWS credentials required.

```bash
cd /home/u560060992/uai3071390-genai-services-demand-generation-usecase

# Build and start everything
docker compose up --build -d

# Watch logs (optional — Ctrl+C to stop tailing, containers keep running)
docker compose logs -f qna-agent data-service frontend
```

**What starts:**
| Service         | Internal Port | Host Port | URL                          |
|-----------------|---------------|-----------|------------------------------|
| dynamodb-local  | 8000          | 8000      | —                            |
| minio           | 9000 / 9001   | 9000/9001 | http://localhost:9001 (console) |
| data-service    | 8086          | 8086      | http://localhost:8086/health  |
| risk-eval       | 8082          | 8082      | http://localhost:8082/health  |
| narrative       | 8083          | 8083      | http://localhost:8083/health  |
| event-history   | 8084          | 8084      | http://localhost:8084/health  |
| orchestrator    | 8081          | —         | (internal only)              |
| qna-agent       | 8087          | 8087      | http://localhost:8087/health  |
| frontend        | 3000          | 3000      | http://localhost:3000         |

> **Note:** Q&A agent listens on port 8087 both inside and outside Docker.

### A.2 — With Real S3 (AWS)

Use a compose override so the Q&A agent uses real AWS S3 instead of MinIO.

1. Login to AWS first:

```bash
gossamer3 login \
  --role arn:aws:iam::337693406325:role/vn/account-privileged \
  --disable-keychain --force
```

2. Export short-lived AWS credentials into your shell:

```bash
eval "$(aws configure export-credentials --profile default --format env)"
```

3. Create a temporary compose override file from the repo root:

```yaml
# compose.real-s3.yml
services:
  qna-agent:
    environment:
      S3_LOCAL_MODE: "false"
      SESSION_S3_BUCKET_NAME: ${SESSION_S3_BUCKET_NAME:-sdg-qna-agent-sessions}
      SESSION_S3_REGION: ${SESSION_S3_REGION:-us-east-1}
      AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID}
      AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY}
      AWS_SESSION_TOKEN: ${AWS_SESSION_TOKEN}
    depends_on:
      data-service:
        condition: service_healthy
```

4. Start the full stack without MinIO services:

```bash
cd /home/u560060992/uai3071390-genai-services-demand-generation-usecase

export SESSION_S3_BUCKET_NAME=sdg-qna-agent-sessions
export SESSION_S3_REGION=us-east-1

docker compose -f compose.yml -f compose.real-s3.yml up --build -d \
  dynamodb-local dynamodb-init \
  data-service risk-eval narrative event-history orchestrator qna-agent frontend
```

5. Watch logs if needed:

```bash
docker compose -f compose.yml -f compose.real-s3.yml logs -f qna-agent data-service frontend
```

Notes:
- Do not start `minio` or `minio-init` in this mode.
- Do not rely on `backend/.env` values like `S3_LOCAL_MODE=true` or `S3_ENDPOINT_URL=http://localhost:9000`; the override file above supersedes them for the `qna-agent` container.
- Keep DynamoDB Local enabled unless you intentionally want to test against real AWS DynamoDB too.
- The S3 bucket must already exist and the exported AWS credentials must have read/write access.



### A.3 — Tear down

```bash
docker compose down          # stop and remove containers
docker compose down -v       # also remove volumes (MinIO data, etc.)
```

---

## Option B: Hybrid (frontend via pnpm dev, backend via Docker)

Useful when you want to iterate on the frontend without rebuilding the container.

```bash
# 1. Start all backend services in containers
docker compose up --build -d dynamodb-local dynamodb-init minio minio-init \
  data-service risk-eval narrative event-history orchestrator qna-agent

# 2. Run frontend locally with vite dev server
cd frontend
pnpm dev
```

Vite dev server on http://localhost:4000 proxies:
- `/qna/*` → `http://localhost:8087` (qna-agent container, host port)
- `/api/*` → `http://localhost:8086` (data-service container, host port)

> **Important:** Vite defaults `QNA_TARGET` to `http://localhost:8087` which matches the Docker compose port mapping.

---

## Option C: Fully Local (uv run, no containers for agents)

Useful for debugging with breakpoints. Still needs MinIO (or S3) from Docker.

### C.0 — Kill leftover processes

Before starting, make sure no previous instances are running:

```bash
# Check for existing processes on the ports we need
lsof -i :8001 -i :8087 2>/dev/null

# Kill leftover agent/data-service if needed
pkill -f "uvicorn question_answer.main:app" 2>/dev/null || true
pkill -f "uvicorn data_service.main:app" 2>/dev/null || true
```

### C.1 — Start MinIO and DynamoDB

```bash
cd /home/u560060992/uai3071390-genai-services-demand-generation-usecase
docker compose up -d minio minio-init dynamodb-local dynamodb-init
```

Optional health check (must bypass Zscaler proxy for localhost):
```bash
env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy -u ALL_PROXY -u all_proxy \
  curl --noproxy '*' -sS -i http://localhost:9000/minio/health/live
```

### C.2 — Terminal 1: data-service

```bash
cd /home/u560060992/uai3071390-genai-services-demand-generation-usecase/backend
uv run uvicorn data_service.main:app --port 8001 --reload 2>&1 | tee data-service.log
```

If your shell already exports proxy-managed cert variables that conflict with
`backend/.env`, start the data-service with a clean cert env instead of changing
application code:

```bash
cd /home/u560060992/uai3071390-genai-services-demand-generation-usecase/backend
env -u SSL_CERT_FILE -u REQUESTS_CA_BUNDLE -u CURL_CA_BUNDLE \
  uv run uvicorn data_service.main:app --port 8001 --reload 2>&1 | tee data-service.log
```

### C.3 — Terminal 2: Q&A agent

`backend/.env` may have `S3_LOCAL_MODE=false` and `DATA_SERVICE_URL` pointing at the
remote dev environment. Override them on the command line for local testing:

```bash
cd /home/u560060992/uai3071390-genai-services-demand-generation-usecase/backend
DATA_SERVICE_URL=http://localhost:8001 \
  S3_LOCAL_MODE=true \
  S3_ENDPOINT_URL=http://localhost:9000 \
  uv run uvicorn question_answer.main:app --port 8087 --reload 2>&1 | tee agent.log
```

> **Tip:** Add `STRANDS_DEBUG=true` before `uv run` for verbose agent/tool logging.
>
> **If port 8087 is already in use:** Run `pkill -f "uvicorn question_answer.main:app"`
> and wait 2 seconds before retrying.

### C.4 — Terminal 3: frontend

```bash
cd /home/u560060992/uai3071390-genai-services-demand-generation-usecase/frontend
VITE_DATA_SERVICE_URL=http://localhost:8001 pnpm dev
```

> The env var tells the vite proxy to forward `/api/*` to your local data-service
> on port 8001 instead of the Docker default (8086). `QNA_TARGET` already
> defaults to `http://localhost:8087` so no override is needed.

### What to expect

| Service        | Port  | URL                             |
|----------------|-------|---------------------------------|
| MinIO S3 API   | 9000  | http://localhost:9000           |
| MinIO console  | 9001  | http://localhost:9001           |
| data-service   | 8001  | http://localhost:8001/health    |
| Q&A agent      | 8087  | http://localhost:8087/health    |
| frontend       | 4000  | http://localhost:4000           |

Vite proxies:
- `/api/*` → `http://localhost:8001/dataservices/api/v1/*`
- `/qna/*` → `http://localhost:8087/*`

---

## Health Checks

After starting, verify all services are healthy.

> **Important:** Zscaler proxy intercepts localhost requests. Always bypass it with
> `--noproxy '*'` and unset proxy env vars, or you'll get `307 Moved Temporarily`
> responses from Zscaler instead of the actual service.

```bash
# Quick checks (Option C ports) — must bypass Zscaler
env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy -u ALL_PROXY -u all_proxy \
  curl --noproxy '*' -sS http://localhost:8001/health          # data-service

env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy -u ALL_PROXY -u all_proxy \
  curl --noproxy '*' -sS http://localhost:8087/health          # qna-agent

# Docker compose health (Option A/B only)
docker compose ps                              # all services should show "healthy"
```

---

## E2E Test Flow

### 1. Create an Assessment

Open http://localhost:3000 (or :4000 in Option B/C).

1. Enter a **real equipment serial number** (e.g., from the team's test dataset)
2. Select data sources and date range
3. Click **Create Assessment**

### 2. Run RE Analysis (Steps 3–5)

1. The UI triggers RE analysis automatically
2. Wait for the risk assessment table to populate (poll status)
3. Review findings — optionally add feedback (Agreement, Correctness, Comment)

### 3. Generate RE Narrative (Step 6)

1. Click to generate the narrative summary
2. Wait for completion
3. Review the narrative output

### 4. Test Q&A Chat — RE Persona (Step 8)

1. Navigate to the **Reliability Chat** panel
2. Ask questions like:
   - "What is the rotor rewind history for this unit?"
   - "What are the IMMEDIATE ACTION findings?"
   - "Show me the evidence for the DC leakage test finding"
   - "What does the PRISM risk profile say about the stator?"
3. **Verify:**
   - Response arrives as a single complete message (no streaming, per ADR-001)
   - Response includes **Answer**, **Explanation**, and **Sources** sections
   - Citations reference tool outputs (`[FSR: ...]`, `[RE Table]`, `[IBAT Data]`, etc.)
   - No fabricated data — answer is grounded in tool outputs only
   - Serial number context is preserved across turns

### 5. Test Q&A Chat — OE Persona

The OE outage chat endpoint is live at `/questionansweragent/api/v1/assessments/{id}/chat/outage`.

**OE tool set (9 tools):** `read_ibat`, `query_fsr`, `query_er`, `read_risk_matrix`,
`read_re_table`, `read_re_report`, `read_oe_table`, `read_event_master`, `read_oe_event_report`.

OE excludes `read_prism` (RE-only).

#### Via curl (local — must bypass Zscaler):

```bash
env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy -u ALL_PROXY -u all_proxy \
  curl --noproxy '*' -sS -X POST \
  http://localhost:8087/questionansweragent/api/v1/assessments/YOUR_ASSESSMENT_ID/chat/outage \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are the bearing findings for this unit?",
    "context": {"serialNumber": "YOUR_ESN"}
  }' | python3 -m json.tool
```

Example questions:
- "What are the bearing findings for this unit?"
- "Summarize the outage event history"
- "What does the OE risk assessment table show?"
- "Are there any collector ring or seal issues in the FSR reports?"
- "What did the RE analysis find? Any overlap with OE scope?"

**Verify:**
- Response includes `"agent": "outage-agent"`
- Agent uses OE tools (check server logs for `filtered tools persona=OE count=9`)
- Agent does NOT have access to `read_prism`
- Agent CAN read RE outputs (`read_re_table`, `read_re_report`) for cross-persona context
- Serial number context is used when querying equipment-specific tools

#### Via curl (deployed environment):

```bash
curl -sk -X POST \
  https://dev-unitrisk.apps.gevernova.net/questionansweragent/api/v1/assessments/YOUR_ASSESSMENT_ID/chat/outage \
  -H "Content-Type: application/json" \
  -d '{"message":"What are the bearing findings?","context":{"serialNumber":"YOUR_ESN"}}'
```

### 6. Verify Session Persistence (S3)

1. Send a message in the chat
2. Send a follow-up that references the first message (e.g., "Tell me more about that")
3. **With MinIO:** Open http://localhost:9001, navigate to the `qna-session-memory` bucket, verify session files exist
4. **With real S3:** Check the bucket in AWS console or via CLI:
   ```bash
   aws s3 ls s3://sdg-qna-agent-sessions/qna-agent/ --recursive
   ```

---

## Troubleshooting

### Port conflicts
```bash
# Check what's using a port
lsof -i :8087 -i :8001 -i :8086 -i :3000 -i :4000
# Kill leftover uv run processes
pkill -f "uvicorn question_answer.main:app" 2>/dev/null || true
pkill -f "uvicorn data_service.main:app" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
# Or tear down containers
docker compose down
```

### Zscaler proxy blocking localhost
If `curl http://localhost:...` returns `307 Moved Temporarily` or a Zscaler captcha URL,
the corporate proxy is intercepting localhost traffic. Always use:
```bash
env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy -u ALL_PROXY -u all_proxy \
  curl --noproxy '*' -sS http://localhost:8001/health
```

### MCP connection errors
The Q&A agent connects to data-service MCP at `{DATA_SERVICE_URL}/dataservices/mcp/`.
- In Docker: `http://data-service:8086/dataservices/mcp/` (internal DNS)
- Local: `http://localhost:8001/dataservices/mcp/` (or `:8086` depending on how you started data-service)

Check the MCP endpoint is alive:
```bash
env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy -u ALL_PROXY -u all_proxy \
  curl --noproxy '*' -sS http://localhost:8001/dataservices/mcp/  # should return MCP protocol response, not 404
```

### Q&A agent returns 503
Agent invocation failed — check logs:
```bash
# Option C (local uv run) — check terminal output or agent.log
tail -50 agent.log

# Option A/B (Docker)
docker compose logs qna-agent --tail=50
docker compose logs qna-agent 2>&1 | grep -i "error\|exception\|traceback"
```

Common causes:
- **S3_LOCAL_MODE not set** — `.env` has `S3_LOCAL_MODE=false` but MinIO is running.
  Override with `S3_LOCAL_MODE=true S3_ENDPOINT_URL=http://localhost:9000` on the command line.
- **Expired AWS token** — If using real S3, `ExpiredToken` errors appear in logs.
  Re-login with gossamer3 or switch to MinIO.
- LiteLLM proxy unreachable (check `LITELLM_PROXY_URL` and certs)
- MCP server not ready (data-service hasn't finished starting)
- S3 bucket doesn't exist (MinIO init failed or wrong bucket name)

### AWS credential expiry
Gossamer3 tokens expire after ~1 hour. If S3 calls fail with `ExpiredTokenException`:
```bash
gossamer3 login --role arn:aws:iam::337693406325:role/vn/account-privileged --disable-keychain --force
# Then restart the qna-agent container to pick up new creds
docker compose restart qna-agent
```

### SSL/TLS errors (Databricks, LiteLLM)
Ensure certs are bundled. Inside containers, the Dockerfile copies certs and sets:
```
SSL_CERT_FILE=/app/certs/ge-ca-bundle.pem
REQUESTS_CA_BUNDLE=/app/certs/ge-ca-bundle.pem
```
For local `uv run`, set these env vars manually or use `LITELLM_SSL_VERIFY=false`.

### Databricks "Unauthorized network access to workspace"
When running in Docker, containers may route Databricks traffic through Docker
Desktop's built-in proxy (`http.docker.internal:3128`) instead of the corporate
Zscaler proxy. Databricks workspace ACLs reject connections from unknown IPs.

**Fix:** Ensure the corporate proxy and `NO_PROXY` are set in the compose
`environment:` block for `data-service` (and any other service that calls
Databricks). The `compose.yml` already includes these, but if they are missing:

```yaml
services:
  data-service:
    environment:
      HTTP_PROXY: ${HTTP_PROXY:-}
      HTTPS_PROXY: ${HTTPS_PROXY:-}
      http_proxy: ${HTTP_PROXY:-}
      https_proxy: ${HTTPS_PROXY:-}
      NO_PROXY: dynamodb-local,data-service,qna-agent,orchestrator,risk-eval,narrative,event-history,minio,localhost,127.0.0.1
      no_proxy: dynamodb-local,data-service,qna-agent,orchestrator,risk-eval,narrative,event-history,minio,localhost,127.0.0.1
```

Similarly, `dynamodb-init` must **clear** proxy vars so the AWS CLI reaches
`dynamodb-local` over the Docker network and not via the corporate proxy:

```yaml
  dynamodb-init:
    environment:
      HTTP_PROXY: ""
      HTTPS_PROXY: ""
      http_proxy: ""
      https_proxy: ""
```

When launching compose, export the proxy in your shell **before** running
`docker compose up`:

```bash
export HTTP_PROXY=http://PITC-Zscaler-Global-3PRZ.proxy.corporate.ge.com:80
export HTTPS_PROXY=http://PITC-Zscaler-Global-3PRZ.proxy.corporate.ge.com:80
```

---

## Chat Endpoint Reference

| Endpoint | Method | Persona | Description |
|----------|--------|---------|-------------|
| `/questionansweragent/api/v1/chat` | POST | RE/OE (body param) | Internal contract |
| `/questionansweragent/api/v1/assessments/{id}/chat/reliability` | POST | RE | Frontend — reliability chat |
| `/questionansweragent/api/v1/assessments/{id}/chat/outage` | POST | OE | Frontend — outage chat |

### Deployed Environment URLs

| Environment | Base URL | Health Check |
|-------------|----------|--------------|
| Dev | `https://dev-unitrisk.apps.gevernova.net` | `https://dev-unitrisk.apps.gevernova.net/questionansweragent/health` |
| QA | `https://qa-unitrisk.apps.gevernova.net` | `https://qa-unitrisk.apps.gevernova.net/questionansweragent/health` |
| Local | `http://localhost:8087` | `http://localhost:8087/questionansweragent/health` |

### Deployed Environment Test Commands

**Health check (QA):**
```bash
curl -sk https://qa-unitrisk.apps.gevernova.net/questionansweragent/health
```

**RE chat (QA):**
```bash
curl -sk -X POST https://qa-unitrisk.apps.gevernova.net/questionansweragent/api/v1/assessments/YOUR_ASSESSMENT_ID/chat/reliability \
  -H "Content-Type: application/json" \
  -d '{"message":"What are the key findings?","context":{"serialNumber":"YOUR_ESN"}}'
```

**OE chat (QA):**
```bash
curl -sk -X POST https://qa-unitrisk.apps.gevernova.net/questionansweragent/api/v1/assessments/YOUR_ASSESSMENT_ID/chat/outage \
  -H "Content-Type: application/json" \
  -d '{"message":"What are the bearing findings?","context":{"serialNumber":"YOUR_ESN"}}'
```

### Local Test Commands

**Request body** (assessment endpoints):
```json
{
  "message": "What are the key findings?",
  "context": {
    "serialNumber": "ABC123"
  }
}
```

**Response:**
```json
{
  "assessmentId": "...",
  "message": {
    "role": "assistant",
    "content": "**Answer**: ...\n\n**Explanation**: ...\n\n**Sources**: ..."
  },
  "agentResponse": {
    "text": "...",
    "toolsUsed": ["read_re_table", "query_fsr"],
    "tokensUsed": 1234,
    "latencyMs": 5678
  }
}
```
==========================

## Quick Local Test Commands

```bash
# Build and start services
docker compose up data-service --build
docker compose up qna-agent --build

# RE chat — local docker
env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy -u NO_PROXY -u no_proxy \
  curl -sS -X POST http://localhost:8087/questionansweragent/api/v1/assessments/assess-001/chat/reliability \
  -H 'Content-Type: application/json' \
  -d '{"message":"What can you tell me about serial 342447641? Use IBAT and PRISM if relevant.","context":{"serialNumber":"342447641"}}'

# Run qna-agent locally with uv (outside docker)
cd ~/uai3071390-genai-services-demand-generation-usecase/backend && \
  DATA_SERVICE_URL=http://localhost:8086 \
  uv run --package sdg-qna-agent uvicorn question_answer.main:app --host 0.0.0.0 --port 8087

# RE chat — local uv
env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy -u NO_PROXY -u no_proxy \
  curl -sS -X POST http://localhost:8087/questionansweragent/api/v1/assessments/madhurima-test-01/chat/reliability \
  -H 'Content-Type: application/json' \
  -d '{"message":"What can you tell me about serial 342447641?","context":{"serialNumber":"342447641"}}'

# OE chat — local uv
env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy -u NO_PROXY -u no_proxy \
  curl -sS -X POST http://localhost:8087/questionansweragent/api/v1/assessments/madhurima-test-01/chat/outage \
  -H 'Content-Type: application/json' \
  -d '{"message":"What are the bearing findings for this unit?","context":{"serialNumber":"342447641"}}'
```