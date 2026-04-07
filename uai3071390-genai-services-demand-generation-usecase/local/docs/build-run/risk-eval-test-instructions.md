# Risk Evaluation Assistant — Local Test Instructions

## Overview

The risk-evaluation-assistant produces structured risk findings and categories
for a given equipment serial number. It calls data-service MCP tools
(`read_risk_matrix`, `query_fsr`, `query_er`) to retrieve evidence, then uses
an LLM to evaluate risk.

## Prerequisites

Same as Q&A agent — see `agent-test-instructions-2.md` for shared prereqs
(Docker, certs, `.env`, AWS creds).

## Dependencies

| Service | Port | Required |
|---------|------|----------|
| DynamoDB Local | 8000 | Always (stores risk analysis results) |
| data-service | 8001 (local) / 8086 (Docker) | Always (MCP tools for heatmap, FSR, ER) |
| LiteLLM proxy | external | For real LLM calls (skip with `AGENT_SIMULATE_MODE=true`) |
| Databricks (Naksha) | external | When `USE_MOCK=false` |

**Not required:** MinIO, QnA agent, orchestrator, narrative/event-history agents.

---

## Quick Start (Option C — fully local with `uv run`)

### 0. Kill leftover processes

```bash
pkill -f "uvicorn risk_evaluation.main:app" 2>/dev/null || true
pkill -f "uvicorn data_service.main:app" 2>/dev/null || true
lsof -i :8001 -i :8002 2>/dev/null
```

> If ports are still occupied after `pkill`, use `pkill -9 -f ...` and wait 3 seconds.

### 1. Start dependencies

```bash
cd /home/u560060992/uai3071390-genai-services-demand-generation-usecase
docker compose up -d dynamodb-local dynamodb-init minio minio-init
```

### 2. Start data-service (if not already running)

The data-service needs the GE CA bundle for Databricks SSL connections (Zscaler intercepts),
and `DATA_SERVICE_URL` pointing at itself so MCP tool calls stay local:

```bash
cd /home/u560060992/uai3071390-genai-services-demand-generation-usecase/backend
SSL_CERT_FILE=certs/ge-ca-bundle.pem \
  REQUESTS_CA_BUNDLE=certs/ge-ca-bundle.pem \
  DATA_SERVICE_URL=http://localhost:8001 \
  uv run uvicorn data_service.main:app --port 8001 --reload 2>&1 | tee data-service.log
```

### 3. Start risk-eval agent

```bash
cd /home/u560060992/uai3071390-genai-services-demand-generation-usecase/backend
DATA_SERVICE_URL=http://localhost:8001 \
  uv run uvicorn risk_evaluation.main:app --port 8002 --reload 2>&1 | tee risk-eval.log
```

> **Simulate mode** (skip LLM, use mock responses):
> Add `AGENT_SIMULATE_MODE=true` before `uv run`.

---

## Health Checks

Must bypass Zscaler proxy for localhost:

```bash
env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy -u ALL_PROXY -u all_proxy \
  curl --noproxy '*' -sS http://localhost:8002/riskevaluationassistant/api/v1/risk-eval/healthcheck
```

Expected: `{"status":"healthy","message":"Service is up and running","registered_users":1}`

Other health endpoints:
- `GET /health`
- `GET /riskevaluationassistant/health`

---

## Trigger Risk Evaluation

### Endpoint

```
POST /riskevaluationassistant/api/v1/risk-eval/run
```

### Minimal Request

> **Important:** The `filters` field is required. Without it, the service crashes with
> `'NoneType' object has no attribute 'get'` on `input_params.filters`.

```bash
env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy -u ALL_PROXY -u all_proxy \
  curl --noproxy '*' -sS -X POST http://localhost:8002/riskevaluationassistant/api/v1/risk-eval/run \
  -H "Content-Type: application/json" \
  -d '{
    "esn": "342447641",
    "assessment_id": "test-risk-eval-01",
    "persona": "RE",
    "filters": {
      "data_types": ["IBAT", "FSR", "ER"],
      "dateFrom": "2024-01-01",
      "dateTo": "2025-12-31"
    }
  }' 2>&1 | python -m json.tool
```

### Full Request (with filters)

```bash
env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy -u ALL_PROXY -u all_proxy \
  curl --noproxy '*' -sS -X POST http://localhost:8002/riskevaluationassistant/api/v1/risk-eval/run \
  -H "Content-Type: application/json" \
  -d '{
    "esn": "342447641",
    "assessment_id": "test-risk-eval-02",
    "persona": "RE",
    "component_type": "Stator",
    "data_types": ["IBAT", "FSR", "ER"],
    "date_from": "2024-01-01",
    "date_to": "2025-12-31",
    "filters": {
      "data_types": ["IBAT", "FSR", "ER"],
      "dateFrom": "2024-01-01",
      "dateTo": "2025-12-31"
    }
  }' 2>&1 | python -m json.tool
```

### Expected Response Shape

```json
{
  "result": "<per-issue text summaries>",
  "data": [
    {
      "Issue name": "High Stator Bar Temps",
      "Component and Issue Grouping": "Stator - Stator Bar Temperature",
      "Risk": "Not Mentioned",
      "Evidence": "[IBAT Data] ...",
      "Citation": "IBAT",
      "id": "stator-...",
      "component": "Stator"
    }
  ],
  "findings": [...],
  "riskCategories": {...},
  "status": "complete",
  "assessment_id": "test-risk-eval-01"
}
```

> A successful run with ESN `342447641` returns 42 issue entries. Most will be
> `"Risk": "Not Mentioned"` if no FSR/ER data is loaded for that ESN.
> Response time: expect **2-8 minutes** for a full run (Databricks + LLM calls).

### Expected Log Output

In the risk-eval terminal, you should see:
```
INFO - Calling MCP tool 'read_risk_matrix' for persona=REL (from RE)
INFO - MCP_SERVER_PARAMS: http://localhost:8001/dataservices/mcp/
INFO - Heatmap result received
INFO - Formed ESN-issue matrix with 42 entries for ESN=342447641
INFO - TOOL CALL RESULT: ... query_fsr ...
INFO - TOOL CALL RESULT: ... query_er ...
```

### What to verify for MCP canonical names

Check the risk-eval logs for MCP tool calls. They should use canonical names:
- `read_risk_matrix` (not `load_heatmap_dataservices_api_v1_heatmap_load_get`)
- `query_fsr` (not `retrieve_endpoint_dataservices_api_v1_retriever_retrieve`)
- `query_er` (not `get_risk_er_cases_endpoint_dataservices_api_v1_er_risk_e`)

---

## Troubleshooting

### Port 8002 already in use
```bash
pkill -f "uvicorn risk_evaluation.main:app" 2>/dev/null
sleep 2
# If still occupied:
pkill -9 -f "uvicorn risk_evaluation.main:app" 2>/dev/null
sleep 3
```

### Stale heatmap cache
The risk-eval agent caches heatmap data at `/tmp/run/<esn>/heatmap.xlsx`. If a
previous run failed (e.g., SSL error), the cached file may be empty and cause
`No issue rows available` or `object has no attribute 'all_issues'` errors.
Clear it before retrying:
```bash
rm -rf /tmp/run/342447641
```

### Databricks SSL errors in data-service logs
If data-service logs show `SSL: CERTIFICATE_VERIFY_FAILED` retrying against
Databricks, the GE CA bundle is not loaded. Restart data-service with:
```bash
SSL_CERT_FILE=certs/ge-ca-bundle.pem \
  REQUESTS_CA_BUNDLE=certs/ge-ca-bundle.pem \
  DATA_SERVICE_URL=http://localhost:8001 \
  uv run uvicorn data_service.main:app --port 8001 --reload
```

### `'NoneType' object has no attribute 'get'` on filters
The `filters` field in the request body is required. Add it:
```json
"filters": { "data_types": ["IBAT", "FSR", "ER"], "dateFrom": "2024-01-01", "dateTo": "2025-12-31" }
```

### DynamoDB table not found
DynamoDB init container creates the tables. If it failed:
```bash
docker compose up dynamodb-init
```

### 404 on MCP tool call
data-service must be running and healthy. Verify:
```bash
env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy -u ALL_PROXY -u all_proxy \
  curl --noproxy '*' -sS http://localhost:8001/health
```

### Slow response
Risk evaluation makes multiple MCP + LLM calls. Expect **2-8 minutes** for a full run.
Use `AGENT_SIMULATE_MODE=true` for quick functional testing.
