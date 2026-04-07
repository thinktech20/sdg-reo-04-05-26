# Local Test Runbook — Q&A Agent E2E Testing

**Date:** 2026-03-24  
**Branch:** `feature/589897-adhoc-qna-agent`  
**Pairing session**

---

## Background / Where We Left Off

We spent the evening fighting corporate proxy (Zscaler) issues when running
services inside Docker. The key blocker:

- **Databricks rejects Docker container traffic** — Docker Desktop's built-in
  proxy (`http.docker.internal:3128`) routes outbound traffic through an IP that
  Databricks workspace ACLs don't allow. This means the `data-service` container
  cannot query Databricks for real train data.
- **Zscaler intercepts localhost in the browser** — even `http://127.0.0.1:4000`
  gets blocked with "invalid server IP" by Zscaler when curl/browser goes
  through the proxy.

### What IS working

- **data-service running locally** (`uv run`, port 8001) can reach Databricks
  successfully through Zscaler on the host.
- **Vite proxy rewrite** works: `/api/units` → `/dataservices/api/v1/units` → 200 OK
  with real train data (verified via `curl --noproxy '*'`).
- **Docker images build** successfully (with the uv-bin + proxy workarounds).
- **DynamoDB Local** container works (proxy env cleared in compose).
- **MinIO** container works.
- **AWS S3 bucket** `app-uai3071390-sdg-dev-s3-qna-session` is accessible.

### What needs fixing

- Browser access to `localhost:4000` is blocked by Zscaler. Need to either:
  1. Disable Zscaler temporarily, OR
  2. Add `localhost,127.0.0.1` to the Zscaler bypass/PAC exclusion, OR
  3. Use a fully local approach with `--noproxy` curl testing (no browser)

---

## Recommended Approach: Hybrid (Option C from test instructions)

**data-service** and **qna-agent** run locally via `uv run` (to avoid Docker
proxy issues with Databricks). Everything else in Docker. Frontend via `pnpm dev`.

### Prerequisites

1. Zscaler must be running (for Databricks and LiteLLM access)
2. `backend/.env` is already configured (all values filled in)
3. `backend/certs/ge-ca-bundle.pem` exists (~223KB)
4. Node/pnpm installed (for frontend)
5. `uv` installed (for Python services)

---

## Step-by-Step Commands

### Step 0: Open a fresh terminal, go to the repo

```bash
cd /home/u560060992/uai3071390-genai-services-demand-generation-usecase
git checkout feature/589897-adhoc-qna-agent
git pull
```

### Step 1: AWS Login (for real S3 — skip if testing with MinIO)

```bash
gossamer3 login \
  --role arn:aws:iam::337693406325:role/vn/account-privileged \
  --disable-keychain --force
```

Then export the credentials into your shell:

```bash
eval "$(aws configure export-credentials --profile default --format env)"
```

Verify:

```bash
env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy \
  AWS_CA_BUNDLE=backend/certs/ge-ca-bundle.pem \
  aws s3 ls s3://app-uai3071390-sdg-dev-s3-qna-session/ --no-cli-pager
```

> **Creds expire after ~1 hour.** Re-run gossamer3 + eval when they expire.

### Step 2: Start DynamoDB Local + MinIO (Docker)

```bash
docker compose up -d dynamodb-local dynamodb-init minio minio-init
```

Wait for init containers to finish:

```bash
docker compose logs -f dynamodb-init minio-init
# Wait until you see "DynamoDB tables ready" and "MinIO buckets ready"
# Then Ctrl+C
```

Verify DynamoDB is healthy:

```bash
docker compose ps dynamodb-local
# Should show "healthy"
```

### Step 3: Start data-service (Terminal 1 — "uv" terminal)

```bash
cd /home/u560060992/uai3071390-genai-services-demand-generation-usecase/backend

# Unset cert vars that conflict with Zscaler-managed certs on host
env -u SSL_CERT_FILE -u REQUESTS_CA_BUNDLE -u CURL_CA_BUNDLE \
  DYNAMODB_ENDPOINT_URL=http://localhost:8000 \
  DYNAMODB_REGION=us-east-1 \
  AWS_ACCESS_KEY_ID=local \
  AWS_SECRET_ACCESS_KEY=local \
  uv run --package sdg-data-service \
  uvicorn data_service.main:app --host 0.0.0.0 --port 8001 --reload
```

Wait for `Application startup complete`, then verify in another terminal:

```bash
curl --noproxy '*' -sS http://localhost:8001/dataservices/api/v1/units | head -c 200
```

You should see JSON with train data. If this hangs for >2 min, Databricks may be
cold-starting — wait up to 10 min on first query.

### Step 4: Start Q&A Agent (Terminal 2)

For **MinIO (local S3)**:

```bash
cd /home/u560060992/uai3071390-genai-services-demand-generation-usecase/backend

env -u SSL_CERT_FILE -u REQUESTS_CA_BUNDLE -u CURL_CA_BUNDLE \
  DATA_SERVICE_URL=http://localhost:8001 \
  MCP_SERVER_URL=http://localhost:8001/mcp/ \
  AUTH_LOCAL_MODE=true \
  S3_LOCAL_MODE=true \
  S3_ENDPOINT_URL=http://localhost:9000 \
  SESSION_S3_BUCKET_NAME=app-uai3071390-sdg-dev-s3-qna-session \
  S3_ACCESS_KEY_ID=minioadmin \
  S3_SECRET_ACCESS_KEY=minioadmin \
  uv run --package sdg-question-answer-agent \
  uvicorn question_answer.main:app --host 0.0.0.0 --port 8087 --reload
```

For **real AWS S3** (requires Step 1 creds in your env):

```bash
cd /home/u560060992/uai3071390-genai-services-demand-generation-usecase/backend

env -u SSL_CERT_FILE -u REQUESTS_CA_BUNDLE -u CURL_CA_BUNDLE \
  DATA_SERVICE_URL=http://localhost:8001 \
  MCP_SERVER_URL=http://localhost:8001/mcp/ \
  AUTH_LOCAL_MODE=true \
  S3_LOCAL_MODE=false \
  SESSION_S3_BUCKET_NAME=app-uai3071390-sdg-dev-s3-qna-session \
  AWS_DEFAULT_REGION=us-east-1 \
  uv run --package sdg-question-answer-agent \
  uvicorn question_answer.main:app --host 0.0.0.0 --port 8087 --reload
```

> Note: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` must
> already be exported in the shell from Step 1.

Verify:

```bash
curl --noproxy '*' -sS http://localhost:8087/health
# Should return: {"status":"ok"}
```

### Step 5: Start Frontend (Terminal 3)

```bash
cd /home/u560060992/uai3071390-genai-services-demand-generation-usecase/frontend

VITE_DATA_SERVICE_URL=http://localhost:8001 pnpm dev
```

Frontend will be at `http://localhost:4000`.

### Step 6: Access the UI

**Known issue:** Zscaler blocks `localhost` / `127.0.0.1` in the browser.

Try these workarounds (in order):
1. **Temporarily disconnect from VPN/Zscaler** if allowed
2. **Use Firefox** with proxy set to "No proxy" for localhost
3. **Bypass via PAC file** — ask IT to add `localhost` to Zscaler bypass
4. **Test via curl only** (no browser needed for Q&A chat):

```bash
# Fetch trains (test data-service through vite proxy)
curl --noproxy '*' -sS http://localhost:4000/api/units | python3 -m json.tool | head -30

# Or hit data-service directly
curl --noproxy '*' -sS http://localhost:8001/dataservices/api/v1/units | python3 -m json.tool | head -30
```

---

## Testing Q&A Chat (curl — no browser needed)

### Create an Assessment first

```bash
# Pick an ESN from the units list above (e.g. "810548")
curl --noproxy '*' -sS -X POST http://localhost:8001/dataservices/api/v1/assessments \
  -H "Content-Type: application/json" \
  -d '{
    "esn": "810548",
    "persona": "RE",
    "workflowId": "RE_DEFAULT"
  }' | python3 -m json.tool
```

Note the `id` from the response (e.g. `"id": "abc-123-..."`). Use it below.

### Send a Q&A Chat Message

```bash
ASSESSMENT_ID="<paste-assessment-id-here>"

curl --noproxy '*' -sS -X POST http://localhost:8087/api/assessments/${ASSESSMENT_ID}/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is the rotor rewind history for this unit?",
    "context": {"serialNumber": "810548"}
  }' | python3 -m json.tool
```

### Verify Session Persistence

Send a follow-up:

```bash
curl --noproxy '*' -sS -X POST http://localhost:8087/api/assessments/${ASSESSMENT_ID}/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Tell me more about that",
    "context": {"serialNumber": "810548"}
  }' | python3 -m json.tool
```

Check S3 sessions exist:

```bash
# MinIO
curl --noproxy '*' -sS http://localhost:9001  # open in browser for MinIO console

# Real S3
env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy \
  AWS_CA_BUNDLE=backend/certs/ge-ca-bundle.pem \
  aws s3 ls s3://app-uai3071390-sdg-dev-s3-qna-session/qna-agent/ --recursive --no-cli-pager
```

---

## Quick Reference: Service Ports

| Service        | Port | How to start                        |
|----------------|------|-------------------------------------|
| DynamoDB Local | 8000 | `docker compose up -d dynamodb-local dynamodb-init` |
| MinIO S3 API   | 9000 | `docker compose up -d minio minio-init`             |
| MinIO Console  | 9001 | (same as above)                     |
| data-service   | 8001 | `uv run` (see Step 3)              |
| Q&A agent      | 8087 | `uv run` (see Step 4)              |
| Frontend       | 4000 | `pnpm dev` (see Step 5)            |

---

## Stopping Everything

```bash
# Stop Docker containers
cd /home/u560060992/uai3071390-genai-services-demand-generation-usecase
docker compose down

# Kill local processes
pkill -f "uvicorn data_service" || true
pkill -f "uvicorn question_answer" || true
pkill -f "vite" || true
```

---

## Unstaged Local Changes (DO NOT lose these)

These files have been modified locally but not committed. They contain proxy and
uv-bin workarounds needed for Docker builds:

```
 M backend/agents/event-history-assistant/Dockerfile       # uv-bin + proxy ARGs
 M backend/agents/narrative-summary-assistant/Dockerfile   # uv-bin + proxy ARGs
 M backend/agents/orchestrator/Dockerfile                  # uv-bin + proxy ARGs
 M backend/agents/question-answer-agent/Dockerfile         # uv-bin + proxy ARGs
 M backend/agents/risk-evaluation-assistant/Dockerfile     # uv-bin + proxy ARGs
 M backend/services/data-service/Dockerfile                # uv-bin + proxy ARGs
 M compose.yml                                             # proxy env for services
?? backend/uv-bin                                          # static uv binary (~59MB)
?? compose.real-s3.yml                                     # S3 override for Docker
```

**What the Dockerfile changes do:** Replace `COPY --from=ghcr.io/astral-sh/uv:latest`
(which fails due to Zscaler TLS intercept) with `COPY uv-bin /bin/uv` (pre-downloaded
binary). Also add `ARG HTTP_PROXY/HTTPS_PROXY/NO_PROXY` + `ENV` so `uv sync` can
reach PyPI through the corporate proxy during Docker build.

---

## Alternative: Full Docker Approach (if proxy issues are resolved)

If the other machine doesn't have Zscaler issues, or you find a way to bypass:

```bash
cd /home/u560060992/uai3071390-genai-services-demand-generation-usecase

# With MinIO (simplest)
docker compose up --build -d

# With real S3 (need AWS creds exported)
docker compose -f compose.yml -f compose.real-s3.yml up --build -d \
  dynamodb-local dynamodb-init \
  data-service risk-eval narrative event-history orchestrator qna-agent frontend

# Watch logs
docker compose logs -f qna-agent data-service frontend

# Frontend at http://localhost:3000
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `gossamer3` creds expired | Re-run Step 1 (gossamer3 login + eval) |
| Databricks hangs on first query | Cold start — wait up to 10 min |
| `curl` returns GE block page | Add `--noproxy '*'` to curl command |
| Browser blocked by Zscaler | See Step 6 workarounds |
| data-service 404 on `/api/units` | Route is `/dataservices/api/v1/units` — use vite proxy or full path |
| Docker build fails (ghcr.io TLS) | Already fixed — Dockerfiles use local `uv-bin` |
| Docker build fails (PyPI DNS) | Already fixed — Dockerfiles have proxy ARGs |
| `dynamodb-init` stuck in loop | Already fixed — proxy vars cleared in compose.yml |
| MCP 404 | Endpoint is `/mcp/` (trailing slash required) |
| Q&A agent can't reach data-service | Check `DATA_SERVICE_URL=http://localhost:8001` is set |
