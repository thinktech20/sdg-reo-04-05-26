# AWS ECS Fargate Deployment Guide

This document covers all environment variables, DynamoDB tables, S3 buckets, and
networking configuration needed to run the SDG Risk Analyser services on AWS ECS Fargate.

---

## Architecture Overview

```text
ALB (PingID OIDC)
  └── frontend (nginx)
        ├── /qna/         → qna-agent     (8087)  [HTTP + WebSocket]
        ├── /api/         → data-service  (8086)
        └── /             → React SPA (nginx serves index.html)

data-service calls:
  orchestrator      (8081)  POST /orchestrator/api/v1/assessments/{id}/run
                            GET  /orchestrator/api/v1/assessments/{id}/status

orchestrator (LangGraph pipeline) calls:
  risk-eval         (8082)  POST /riskevaluationassistant/api/v1/risk-eval/run
  narrative         (8083)  POST /summarizationassistant/api/v1/narrative/run
  event-history     (8084)  POST /eventhistoryassistant/api/v1/event-history/run
  (RE persona: risk_eval → finalize)
  (OE persona: risk_eval → event_history → finalize)

All LLM agents (risk-eval, narrative, event-history, qna-agent) call:
  LiteLLM proxy (external, dev-gateway.apps.gevernova.net)

data-service calls:
  Naksha SQL proxy (Databricks via API Gateway)

qna-agent calls:
  data-service      (8086)  REST assessment context lookup

DynamoDB tables (see below) used by:
  data-service: execution-state-store, risk-analysis-output,
                navigation-summary, event-history-report
  orchestrator: execution-state-store (job state, when ORCHESTRATOR_USE_DYNAMODB=true),
                orchestrator-checkpointer (LangGraph checkpoints)

S3 / MinIO:
  qna-agent: session history bucket
```

---

## DynamoDB Tables

Provision these tables before deploying. All tables use **PAY_PER_REQUEST** billing.

All 5 tables are provisioned in AWS under the `app-uai3071390-sdg-ddtable-*-dev` naming scheme. Use the exact names below in ECS task definition environment variables.

The current application code is aligned to the AWS key schema already in use:

- Domain tables use `esn` as the partition key and `createdAt` as the sort key.
- `assessmentId` lookups rely on GSIs, not on the base table primary key.
- `EXECUTION_STATE_TABLE` uses `assessment-workflow-index`.
- `LANGGRAPH_CHECKPOINTER_TABLE` is library-managed by LangGraph and should be treated as immutable.

| Env var | Provisioned table name | PK (HASH) | SK (RANGE) | Required GSI(s) | Owner | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `RISK_ANALYSIS_TABLE` | `app-uai3071390-sdg-ddtable-risk-analysys-output-table-dev` | `esn` (S) | `createdAt` (S) | `ra-assessment-index` | data-service | Versioned risk-analysis findings; feedback updates resolve the latest row via the GSI. |
| `NARRATIVE_SUMMARY_TABLE` | `app-uai3071390-sdg-ddtable-navigation-summary-dev` | `esn` (S) | `createdAt` (S) | `ns-assessment-index` | data-service | Versioned narrative-summary rows keyed by ESN + creation timestamp. |
| `EVENT_HISTORY_TABLE` | `app-uai3071390-sdg-ddtable-event-history-report-dev` | `esn` (S) | `createdAt` (S) | `eh-assessment-index` | data-service | Event-history payloads, latest row resolved by `assessmentId`. |
| `EXECUTION_STATE_TABLE` | `app-uai3071390-sdg-ddtable-execution-state-store-dev` | `esn` (S) | `createdAt` (S) | `assessment-workflow-index` | data-service + orchestrator | Shared assessment metadata and workflow state store. Current code is already aligned to this schema. |
| `LANGGRAPH_CHECKPOINTER_TABLE` | `app-uai3071390-sdg-ddtable-orchestrator-checkpointer-dev` | `thread_id` (S) | `checkpoint_ns` (S) | library-managed | orchestrator | LangGraph checkpoint persistence only. Do not add app-specific attributes or GSIs. |

### CloudFormation snippet (DynamoDB)

> These tables are already provisioned in AWS dev. The snippets below are for reference / reprovisioning in other environments.

```yaml
RiskAnalysisTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: app-uai3071390-sdg-ddtable-risk-analysys-output-table-dev
    BillingMode: PAY_PER_REQUEST
    AttributeDefinitions:
      - { AttributeName: esn,          AttributeType: S }
      - { AttributeName: createdAt,    AttributeType: S }
      - { AttributeName: assessmentId, AttributeType: S }
    KeySchema:
      - { AttributeName: esn,          KeyType: HASH }
      - { AttributeName: createdAt,    KeyType: RANGE }
    GlobalSecondaryIndexes:
      - IndexName: ra-assessment-index
        KeySchema:
          - { AttributeName: assessmentId, KeyType: HASH }
        Projection: { ProjectionType: ALL }

NarrativeSummaryTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: app-uai3071390-sdg-ddtable-navigation-summary-dev
    BillingMode: PAY_PER_REQUEST
    AttributeDefinitions:
      - { AttributeName: esn,          AttributeType: S }
      - { AttributeName: createdAt,    AttributeType: S }
      - { AttributeName: assessmentId, AttributeType: S }
    KeySchema:
      - { AttributeName: esn,          KeyType: HASH }
      - { AttributeName: createdAt,    KeyType: RANGE }
    GlobalSecondaryIndexes:
      - IndexName: ns-assessment-index
        KeySchema:
          - { AttributeName: assessmentId, KeyType: HASH }
        Projection: { ProjectionType: ALL }

EventHistoryTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: app-uai3071390-sdg-ddtable-event-history-report-dev
    BillingMode: PAY_PER_REQUEST
    AttributeDefinitions:
      - { AttributeName: esn,          AttributeType: S }
      - { AttributeName: createdAt,    AttributeType: S }
      - { AttributeName: assessmentId, AttributeType: S }
    KeySchema:
      - { AttributeName: esn,          KeyType: HASH }
      - { AttributeName: createdAt,    KeyType: RANGE }
    GlobalSecondaryIndexes:
      - IndexName: eh-assessment-index
        KeySchema:
          - { AttributeName: assessmentId, KeyType: HASH }
        Projection: { ProjectionType: ALL }

ExecutionStateStoreTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: app-uai3071390-sdg-ddtable-execution-state-store-dev
    BillingMode: PAY_PER_REQUEST
    AttributeDefinitions:
      - { AttributeName: esn,          AttributeType: S }
      - { AttributeName: createdAt,    AttributeType: S }
      - { AttributeName: assessmentId, AttributeType: S }
      - { AttributeName: workflowId,   AttributeType: S }
    KeySchema:
      - { AttributeName: esn,          KeyType: HASH }
      - { AttributeName: createdAt,    KeyType: RANGE }
    GlobalSecondaryIndexes:
      - IndexName: assessment-workflow-index
        KeySchema:
          - { AttributeName: assessmentId, KeyType: HASH }
          - { AttributeName: workflowId,   KeyType: RANGE }
        Projection: { ProjectionType: ALL }

LanggraphCheckpointerTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: app-uai3071390-sdg-ddtable-orchestrator-checkpointer-dev
    BillingMode: PAY_PER_REQUEST
    AttributeDefinitions:
      - { AttributeName: thread_id,      AttributeType: S }
      - { AttributeName: checkpoint_ns,  AttributeType: S }
    KeySchema:
      - { AttributeName: thread_id,     KeyType: HASH }
      - { AttributeName: checkpoint_ns, KeyType: RANGE }
```

---

## S3 Buckets

Only one S3 bucket is referenced by current first-party runtime code:

| Bucket | Required in current runtime? | Purpose | Service |
| --- | --- | --- | --- |
| `qna-session-memory` | yes | Q&A agent conversation session history | qna-agent |
| `sdg-checkpointer-offload` | no | Created by local compose bootstrap only; not referenced by current orchestrator application code or task env vars | — |

---

## ECS Service Connect / Cloud Map

Use AWS Cloud Map with a namespace (e.g. `sdg.local`) and register each service:

| Service Name | Port | Cloud Map entry |
| --- | --- | --- |
| `data-service` | 8086 | `data-service.sdg.local` |
| `orchestrator` | 8081 | `orchestrator.sdg.local` |
| `risk-eval` | 8082 | `risk-eval.sdg.local` |
| `narrative` | 8083 | `narrative.sdg.local` |
| `event-history` | 8084 | `event-history.sdg.local` |
| `qna-agent` | 8087 | `qna-agent.sdg.local` |

Frontend nginx env vars for ECS:

```text
NGINX_RESOLVER=169.254.169.253  # VPC resolver
SERVICE_NAMESPACE=.sdg.local    # Cloud Map namespace suffix
```

---

## Environment Variables per Service

`backend/.env.example` is a shared local-development file, but ECS task definitions should set only the variables each service actually consumes.

Reading guide:

- `Local committed value` means the checked-in non-secret value currently present in `.env.example`, `compose.yml`, or a code default.
- Secret-bearing variables intentionally show `—` even when `.env.example` contains a placeholder.
- `VITE_*` values are build-time only; `NGINX_*` values are runtime.
- `DYNAMODB_ENDPOINT_URL`, `S3_ENDPOINT_URL`, and `S3_LOCAL_MODE` are local-only.
- Assistant LiteLLM env handling is mixed by service: risk-eval primarily uses `LITELLM_API_BASE`; qna-agent accepts both `LITELLM_PROXY_URL` and `LITELLM_API_BASE`; narrative and event-history read `LITELLM_PROXY_URL` and map it into `config.LITELLM_API_BASE` internally.

### data-service

Core runtime variables:

| Variable | Local committed value | ECS guidance | Notes |
| --- | --- | --- | --- |
| `DYNAMODB_REGION` | `us-east-1` | set to deployed AWS region | `.env.example` and compose agree. |
| `DYNAMODB_ENDPOINT_URL` | `http://dynamodb-local:8000` | leave unset in AWS | Compose runtime value inside the container; `.env.example` uses `http://localhost:8000` for host-local runs. |
| `RISK_ANALYSIS_TABLE` | `app-uai3071390-sdg-ddtable-risk-analysys-output-table-dev` | set to provisioned table name | Risk analysis output store. |
| `NARRATIVE_SUMMARY_TABLE` | `app-uai3071390-sdg-ddtable-navigation-summary-dev` | set to provisioned table name | Narrative summary store. |
| `EVENT_HISTORY_TABLE` | `app-uai3071390-sdg-ddtable-event-history-report-dev` | set to provisioned table name | Event history store. |
| `EXECUTION_STATE_TABLE` | `app-uai3071390-sdg-ddtable-execution-state-store-dev` | set to provisioned table name | Shared with orchestrator workflow state. |
| `ORCHESTRATOR_URL` | `http://orchestrator:8081` | `http://orchestrator.<namespace>:8081` | Compose override for container-to-container traffic. |
| `QNA_AGENT_URL` | `http://qna-agent:8087` | `http://qna-agent.<namespace>:8087` | Compose override for container-to-container traffic. |
| `CORS_ORIGINS` | `http://localhost:3000` | set to frontend origin(s) | Compose-local frontend origin. |
| `AUTH_LOCAL_MODE` | `true` | `false` in AWS | Local-only auth bypass. |
| `USE_MOCK` | `false` | `false` in AWS | Global mock switch. If unset, code auto-detects from `NAKSHA_API_URL`. |
| `USE_MOCK_UNITS` | `false` | `false` in AWS | Not set in repo files; current local behavior inherits `USE_MOCK=false`. |
| `USE_MOCK_ASSESSMENTS` | `false` | `false` in AWS | Not set in repo files; current local behavior inherits `USE_MOCK=false`. |
| `SERVICE_NAME` | `data-svc` | optional | Code default only. |
| `AWS_ACCESS_KEY_ID` | `local` | not needed when using a task role | Compose-only local DynamoDB credential. |
| `AWS_SECRET_ACCESS_KEY` | `local` | not needed when using a task role | Compose-only local DynamoDB credential. |

Naksha proxy variables:

| Variable | Local committed value | ECS guidance | Notes |
| --- | --- | --- | --- |
| `NAKSHA_API_URL` | `https://lp3c4ukmlh.execute-api.us-east-1.amazonaws.com/Dev/databricks-orchestrator-proxy-dev` | required for live mode | Databricks SQL proxy endpoint. |
| `NAKSHA_BUSINESS` | `gas_power` | set per tenant | Current checked-in local example. |
| `NAKSHA_DOMAIN` | `global_services` | set per tenant | Current checked-in local example. |
| `NAKSHA_SUBDOMAIN` | `fsr` | set per tenant | Current checked-in local example. |
| `NAKSHA_USER_EMAIL` | `test@ge.com` | set to service-account identity | Forwarded as part of Naksha request context. |
| `NAKSHA_USER_DOMAINS` | `fsr` | set as comma-separated list | Current checked-in local example. |
| `NAKSHA_USER_GROUP_IDS` | `""` | optional | Empty in `.env.example`. |
| `NAKSHA_TIMEOUT` | `120` | optional tuning | Code default only. |
| `NAKSHA_MAX_RETRIES` | `3` | optional tuning | Code default only. |
| `NAKSHA_VERIFY_SSL` | `true` | usually `true` | Code default only. |
| `NAKSHA_POLL_INTERVAL_SECONDS` | `2` | optional tuning | Code default only. |
| `NAKSHA_MAX_POLLS` | `60` | optional tuning | Code default only. |

Databricks / retrieval / query tuning variables:

| Variable | Local committed value | ECS guidance | Notes |
| --- | --- | --- | --- |
| `EMBEDDING_TABLE_NAME` | Low | `main.gp_services_sdg_poc.heatmap_issue_prompt_embeddings` | Embedding table for heatmap issue prompts |
| `VECTOR_DATABRICKS_WORKSPACE_URL` | Low | `https://gevernova-ai-dev-dbr.cloud.databricks.com` | Vector search Databricks workspace URL |
| `VECTOR_DATABRICKS_TOKEN` | `HIGH` | `redacted` | Vector search Databricks token |
| `ER_VECTOR_SEARCH_INDEX` | Low | `main.gp_services_sdg_poc.vs_engineering_report_chunk_litellm` | ER vector search index (engineering reports) |
| `DATABRICKS_SQL_MOCK_MODE` | `false` | `false` in AWS | Code default only. |
| `DATABRICKS_HOST` | `https://gevernova-nrc-workspace.cloud.databricks.com` | required for live SQL access | Checked-in local example value. |
| `DATABRICKS_TOKEN` | `—` | required for live SQL/vector access | Secret; do not commit. |
| `DATABRICKS_HTTP_PATH` | `/sql/1.0/warehouses/daff57b69fee5745` | required for live SQL access | Checked-in local example value. |
| `DATABRICKS_SOCKET_TIMEOUT` | `120` | optional tuning | Code default only. |
| `DATABRICKS_WORKSPACE_URL` | ``https://gevernova-nrc-workspace.cloud.databricks.com`` | optional unless vector search used | No checked-in value. |
| `VECTOR_SEARCH_ENDPOINT` | `—` | optional unless vector search used | No checked-in value. |
| `VECTOR_SEARCH_INDEX` | ``main.gp_services_sdg_poc.vs_field_service_report_gt_litellm`` | optional unless vector search used | No checked-in value. |
| `VECTOR_SEARCH_PROXY_URL` | Low | `http://host.docker.internal:9999` (default) | Proxy URL for vector search (bypasses direct workspace URL) |
| `SIMILARITY_SCORE_DELTA` | `0.025` | optional tuning | Code default only. |
| `LOG_SQL_QUERIES` | `true` | optional | Checked-in local example value. |
| `TRAIN_QUERY_LIMIT` | `5` | optional tuning | Code default only. |
| `TRAIN_MAX_RETRIES` | `3` | optional tuning | Code default only. |
| `TRAIN_RETRY_BACKOFF_SECONDS` | `1.5` | optional tuning | Code default only. |
| `IBAT_MAX_RETRIES` | `3` | optional tuning | Code default only. |
| `IBAT_RETRY_BACKOFF_SECONDS` | `1.5` | optional tuning | Code default only. |
| `PRISM_MAX_RETRIES` | `3` | optional tuning | Code default only. |
| `PRISM_RETRY_BACKOFF_SECONDS` | `1.5` | optional tuning | Code default only. |
| `HEATMAP_MAX_RETRIES` | `3` | optional tuning | Code default only. |
| `HEATMAP_RETRY_BACKOFF_SECONDS` | `1.5` | optional tuning | Code default only. |

Data-source catalog / table override variables:

| Variable | Local committed value | ECS guidance | Notes |
| --- | --- | --- | --- |
| `CATALOG` | `vgpd` | optional global catalog override | Shared default for IBAT / Prism / heatmap services. |
| `IBAT_SCHEMA` | `prm_std_views` | optional | Checked-in local value matches code default. |
| `IBAT_EQUIPMENT_TABLE` | `IBAT_EQUIPMENT_MST` | optional | Checked-in local value matches code default. |
| `IBAT_PLANT_TABLE` | `IBAT_PLANT_MST` | optional | Checked-in local value matches code default. |
| `IBAT_TRAIN_TABLE` | `IBAT_TRAIN_MST` | optional | Checked-in value differs in case from the code default `ibat_train_mst`. |
| `IBAT_EQUIPMENT_VIEW` | `—` | optional explicit fully-qualified override | If unset, composed from catalog/schema/table. |
| `IBAT_PLANT_VIEW` | `—` | optional explicit fully-qualified override | If unset, composed from catalog/schema/table. |
| `IBAT_TRAIN_VIEW` | `—` | optional explicit fully-qualified override | If unset, composed from catalog/schema/table. |
| `PRISM_SCHEMA` | `seg_std_views` | optional | Code default only. |
| `PRISM_SOT_TABLE` | `seg_fmea_wo_models_gen_psot` | optional | Code default only. |
| `PRISM_SOT_VIEW` | `—` | optional explicit fully-qualified override | If unset, composed from catalog/schema/table. |
| `ER_CATALOG` | `vgpp` | optional | Code default only. |
| `ER_SCHEMA` | `qlt_std_views` | optional | Code default only. |
| `ER_TABLE` | `u_pac` | optional | Code default only. |
| `ER_VIEW` | `—` | optional explicit fully-qualified override | Used by equipment service. |
| `FSR_CATALOG` | `vgpd` | optional | Code default only. |
| `FSR_SCHEMA` | `fsr_std_views` | optional | Code default only. |
| `FSR_TABLE` | `fsr_field_vision_field_services_report_psot` | optional | Code default only. |
| `FSR_VIEW` | `—` | optional explicit fully-qualified override | Used by equipment service. |
| `EVENT_MASTER_CATALOG` | `vgpd` | optional | Code default only. |
| `EVENT_MASTER_SCHEMA` | `fsr_std_views` | optional | Code default only. |
| `OUTAGE_EVENTMGMT_TABLE` | `eventmgmt_event_vision_sot` | optional | Code default only. |
| `OUTAGE_EVENTMGMT_VIEW` | `—` | optional explicit fully-qualified override | Used by outage history service. |
| `OUTAGE_EQUIP_DTLS_TABLE` | `event_equipment_dtls_event_vision_sot` | optional | Code default only. |
| `OUTAGE_EQUIP_DTLS_VIEW` | `—` | optional explicit fully-qualified override | Used by outage history service. |
| `OUTAGE_SCOPE_TABLE` | `scope_schedule_summary_event_vision_sot` | optional | Code default only. |
| `OUTAGE_SCOPE_VIEW` | `—` | optional explicit fully-qualified override | Used by outage history service. |
| `HEATMAP_SCHEMA` | `fsr_std_views` | optional | Code default only. |
| `HEATMAP_TABLE` | `fsr_unit_risk_matrix_view` | optional | Code default only. |
| `HEATMAP_VIEW` | `—` | optional explicit fully-qualified override | Used by heatmap service. |
| `IBAT_EQUIPMENT_DATA_URL` | `—` | optional local/mock override | No checked-in value. |
| `ER_CASES_DATA_URL` | `—` | optional local/mock override | No checked-in value. |

TLS / proxy variables sometimes needed in enterprise environments:

| Variable | Local committed value | ECS guidance | Notes |
| --- | --- | --- | --- |
| `GE_ENTERPRISE_CA_CERT` | `/app/certs/GE_Enterprise_Root_CA_2_1.pem` | optional | Shared `.env.example` path for Dockerized cert bundle. |
| `GE_EXTERNAL_CA_CERT` | `/app/certs/GE_External_Root_CA_2_1.crt` | optional | Shared `.env.example` path for Dockerized cert bundle. |
| `SSL_CERT_FILE` | `/app/certs/ge-ca-bundle.pem` | optional | Code unsets it automatically if the file path does not exist. |
| `REQUESTS_CA_BUNDLE` | `/app/certs/ge-ca-bundle.pem` | optional | Code unsets it automatically if the file path does not exist. |
| `CURL_CA_BUNDLE` | `—` | optional | Code may use it, but there is no checked-in explicit value. |
| `HTTP_PROXY` | `http://PITC-Zscaler-Global-3PRZ.proxy.corporate.ge.com:80` | optional | Used in checked-in local examples and image builds. |
| `HTTPS_PROXY` | `http://PITC-Zscaler-Global-3PRZ.proxy.corporate.ge.com:80` | optional | Used in checked-in local examples and image builds. |
| `NO_PROXY` | `localhost,127.0.0.1,.corp,https://dev-gateway.apps.gevernova.net` | optional | Used in checked-in local examples and image builds. |

### orchestrator

| Variable | Local committed value | ECS guidance | Notes |
| --- | --- | --- | --- |
| `RISK_EVAL_URL` | `http://risk-eval:8082` | `http://risk-eval.<namespace>:8082` | Compose override for container-to-container traffic. |
| `NARRATIVE_SUMMARY_URL` | `http://narrative:8083` | `http://narrative.<namespace>:8083` | Compose override for container-to-container traffic. |
| `EVENT_HISTORY_URL` | `http://event-history:8084` | `http://event-history.<namespace>:8084` | Compose override for container-to-container traffic. |
| `DATA_SERVICE_URL` | `http://localhost:8086` | `http://data-service.<namespace>:8086` | Comes from `.env.example`; compose does not currently override it for orchestrator. |
| `FOUNDATION_SERVICE_URL` | `http://localhost:9999` | set only if foundation-service integration is enabled | Code default only. |
| `AWS_REGION` | `us-east-1` | set to deployed AWS region | Code default only. |
| `DYNAMODB_ENDPOINT_URL` | `http://dynamodb-local:8000` | leave unset in AWS | Compose runtime value inside the container. |
| `LANGGRAPH_CHECKPOINTER_TABLE` | `app-uai3071390-sdg-ddtable-orchestrator-checkpointer-dev` | set to provisioned checkpointer table name | `.env.example` value; compose fallback is `orchestrator-checkpointer`. |
| `EXECUTION_STATE_TABLE` | `app-uai3071390-sdg-ddtable-execution-state-store-dev` | set to provisioned execution-state table name | Shared with data-service. |
| `ORCHESTRATOR_USE_DYNAMODB` | `true` | `true` in ECS | `.env.example` and compose both set this to `true`. |
| `ORCHESTRATOR_CHECKPOINTER_TYPE` | `dynamodb` | `dynamodb` in ECS | `.env.example` and compose both set this to `dynamodb`. |
| `ORCHESTRATOR_LOCAL_MODE` | `false` | `false` in ECS | Compose override for local containers. |
| `SSL_CERT_FILE` | `/app/certs/ge-ca-bundle.pem` | optional | Inherited from `.env.example`; code unsets if file is absent. |
| `REQUESTS_CA_BUNDLE` | `/app/certs/ge-ca-bundle.pem` | optional | Inherited from `.env.example`; code unsets if file is absent. |
| `CURL_CA_BUNDLE` | `—` | optional | Code may use it, but there is no checked-in explicit value. |

### risk-eval (A1)

| Variable | Local committed value | ECS guidance | Notes |
| --- | --- | --- | --- |
| `LITELLM_LOCAL_MODEL_COST_MAP` | Low | Set to `"True"` in code | Disables internet fetch of LiteLLM model cost map; prevents startup hang |
| `LITELLM_API_BASE` | Low | `https://dev-gateway.apps.gevernova.net/` | Base URL for the LiteLLM proxy gateway |
| `LITELLM_MODEL_ID` | Low | `azure-gpt-5-2` | LLM model identifier routed through LiteLLM proxy |
| `BEDROCK_MODEL_ID` | Low | `bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0` | Bedrock model ID (alternative to Azure) |
| `LITELLM_PROXY_API_KEY` | **High** | `<Your_LiteLLM_Proxy_API_Key>` | API key for authenticating with LiteLLM proxy |
| `AWS_REGION` | Low | `us-east-1` | AWS region for Bedrock / boto3 session |
| `DATA_SERVICE_URL` | Low | `http://data-service:8000` (compose) / `http://localhost:8086` (.env) | Base URL of the data-service API |
| `MCP_SERVER_PARAMS` | Low | `http://data-service:8000/mcp` (compose) / `http://localhost:8000/mcp` (.env) | MCP server endpoint for HTTP tool calls |
| `AUTH_LOCAL_MODE` | Medium | `true` | Bypass ALB OIDC JWT validation (local dev only; must be `false` in prod) |
| `RUN_ARTIFACTS_DIR` | Low | `/app/run_outputs` (compose) / `/tmp/run` (code default) | Writable directory for run artifacts (heatmap, prompts, results) |
| `SSL_VERIFY` | Medium | Set to `"False"` in code | Disables SSL verification for proxy connections |

> Compose currently passes `AGENT_SIMULATE_MODE` and `AGENT_SIM_DELAY_SECS` to `risk-eval`, but the current A1 runtime code does not read either variable.

### narrative (A2)

| Variable | Local committed value | ECS guidance | Notes |
| --- | --- | --- | --- |
| `LITELLM_PROXY_URL` | `https://dev-gateway.apps.gevernova.net` | required | A2 reads this env var and exposes it as `config.LITELLM_API_BASE`. |
| `LITELLM_API_KEY` | `—` | required secret | Secret; do not commit. |
| `LITELLM_MODEL` | `litellm_proxy/gemini-3-flash` | required | Shared checked-in value. |
| `DATA_SERVICE_URL` | `http://data-service:8086` | `http://data-service.<namespace>:8086` | Compose override for container-to-container traffic. |
| `AUTH_LOCAL_MODE` | `true` | `false` in AWS | Compose override for local containers. |
| `AGENT_SIMULATE_MODE` | `false` | optional | Compose default. |
| `AGENT_SIM_DELAY_SECS` | `10` | optional | Compose default. |

### event-history (A3)

| Variable | Local committed value | ECS guidance | Notes |
| --- | --- | --- | --- |
| `LITELLM_PROXY_URL` | `https://dev-gateway.apps.gevernova.net` | required | A3 reads this env var and exposes it as `config.LITELLM_API_BASE`. |
| `LITELLM_API_KEY` | `—` | required secret | Secret; do not commit. |
| `LITELLM_MODEL` | `litellm_proxy/gemini-3-flash` | required | Shared checked-in value. |
| `DATA_SERVICE_URL` | `http://data-service:8086` | `http://data-service.<namespace>:8086` | Compose override for container-to-container traffic. |
| `AUTH_LOCAL_MODE` | `true` | `false` in AWS | Compose override for local containers. |
| `AGENT_SIMULATE_MODE` | `false` | optional | Compose default. |
| `AGENT_SIM_DELAY_SECS` | `10` | optional | Compose default. |

### qna-agent (A4)

| Variable | Local committed value | ECS guidance | Notes |
| --- | --- | --- | --- |
| `LITELLM_PROXY_URL` or `LITELLM_API_BASE` | `https://dev-gateway.apps.gevernova.net` | required | Q&A agent accepts either variable and prefers `LITELLM_PROXY_URL` when both are present. |
| `LITELLM_API_KEY` | `—` | required secret | Secret; do not commit. |
| `LITELLM_MODEL` | `litellm_proxy/gemini-3-flash` | required | Shared checked-in value. |
| `TEMPERATURE` | `0.1` | optional tuning | Code default only. |
| `MAX_TOKENS` | `4000` | optional tuning | Code default only. |
| `DATA_SERVICE_URL` | `http://data-service:8086` | `http://data-service.<namespace>:8086` | Compose override for container-to-container traffic. |
| `AUTH_LOCAL_MODE` | `true` | `false` in AWS | Compose override for local containers. |
| `ALB_REGION` | `—` | set to ALB region | Only commented in `.env.example`. |
| `EXPECTED_ALB_ARN` | `—` | required when ALB validation is enabled | Only commented in `.env.example`. |
| `SESSION_S3_BUCKET_NAME` | `qna-session-memory` | required | Shared checked-in value. |
| `SESSION_S3_REGION` | `us-east-1` | set to deployed AWS region | Code default only. |
| `S3_LOCAL_MODE` | `true` | `false` in AWS | Compose override for local containers. |
| `S3_ENDPOINT_URL` | `http://minio:9000` | leave unset in AWS | Compose runtime value inside the container; `.env.example` uses `http://localhost:9000` for host-local runs. |
| `S3_ACCESS_KEY_ID` | `—` | leave unset in AWS unless explicitly using static credentials | Compose resolves this from `MINIO_ROOT_USER`; treat as credential. |
| `S3_SECRET_ACCESS_KEY` | `—` | leave unset in AWS unless explicitly using static credentials | Compose resolves this from `MINIO_ROOT_PASSWORD`; treat as credential. |
| `REQUIRE_SESSION_ID` | `false` | optional | Code default only. |
| `SERVER_PORT` | `8005` | optional, but container entrypoint currently binds `8087` explicitly | Useful for non-container launches only. |
| `SERVER_HOST` | `0.0.0.0` | optional | Code default only. |

### frontend / nginx

Build-time variables for the frontend image:

| Variable | Local committed value | ECS guidance | Notes |
| --- | --- | --- | --- |
| `VITE_ENABLE_MOCKS` | `false` | usually `false` in AWS | Build-time only. Compose default is empty/false. |
| `VITE_DATA_SERVICE_URL` | `""` | optional; set only if you want the browser to bypass nginx and call data-service directly | Build-time only. Compose default is unset, so the app uses relative `/api` paths. |
| `VITE_QNA_AGENT_URL` | `""` | optional; set only if you want the browser to bypass nginx and call qna-agent directly | Build-time only. Compose default is unset, so the app uses relative `/qna` paths. |

Runtime variables for nginx service discovery:

| Variable | Local committed value | ECS guidance | Notes |
| --- | --- | --- | --- |
| `NGINX_RESOLVER` | `127.0.0.11` | `169.254.169.253` in ECS Fargate | Docker Compose DNS resolver. |
| `SERVICE_NAMESPACE` | `""` | `.<cloud-map-namespace>` such as `.sdg.local` | Empty in Docker Compose, non-empty in ECS. |

Build-network variables sometimes needed in enterprise environments:

| Variable | Local committed value | ECS guidance | Notes |
| --- | --- | --- | --- |
| `HTTP_PROXY` | `http://PITC-Zscaler-Global-3PRZ.proxy.corporate.ge.com:80` | optional build arg | Used during image build only. |
| `HTTPS_PROXY` | `http://PITC-Zscaler-Global-3PRZ.proxy.corporate.ge.com:80` | optional build arg | Used during image build only. |
| `NO_PROXY` | `localhost,127.0.0.1,.corp,https://dev-gateway.apps.gevernova.net` | optional build arg | Used during image build only. |

The frontend build stage also sets `NODE_EXTRA_CA_CERTS` inside the image, but that value is baked into the Dockerfile and is not sourced from an external task-definition environment variable.

---

## IAM Task Role Permissions

The ECS task role (shared or per-service) needs:

```json
{
  "Effect": "Allow",
  "Action": [
    "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem",
    "dynamodb:DeleteItem", "dynamodb:Query", "dynamodb:Scan"
  ],
  "Resource": [
    "arn:aws:dynamodb:REGION:ACCOUNT:table/app-uai3071390-sdg-ddtable-risk-analysys-output-table-dev",
    "arn:aws:dynamodb:REGION:ACCOUNT:table/app-uai3071390-sdg-ddtable-navigation-summary-dev",
    "arn:aws:dynamodb:REGION:ACCOUNT:table/app-uai3071390-sdg-ddtable-event-history-report-dev",
    "arn:aws:dynamodb:REGION:ACCOUNT:table/app-uai3071390-sdg-ddtable-execution-state-store-dev",
    "arn:aws:dynamodb:REGION:ACCOUNT:table/app-uai3071390-sdg-ddtable-orchestrator-checkpointer-dev"
  ]
},
{
  "Effect": "Allow",
  "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"],
  "Resource": [
    "arn:aws:s3:::qna-session-memory",
    "arn:aws:s3:::qna-session-memory/*"
  ]
}
```

---

## Local Dev Quick Start

```bash
# Copy and review; defaults are already correct for docker compose
cp backend/.env.example backend/.env

# Build and start all services
docker compose up --build

# Verify
curl http://localhost:8086/health   # data-service
docker compose exec orchestrator python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8081/health').read().decode())"  # orchestrator (internal-only)
curl http://localhost:3000          # frontend
```

Key ports (local Docker Compose):

| Service | Host port | Container port |
| --- | --- | --- |
| frontend | 3000 | 3000 |
| data-service | 8086 | 8086 |
| orchestrator | _(no host port — internal-only, reached by data-service via service DNS)_ | 8081 |
| risk-eval | 8082 | 8082 |
| narrative | 8083 | 8083 |
| event-history | 8084 | 8084 |
| qna-agent | 8087 | 8087 |
| DynamoDB Local | 8000 | 8000 |
| MinIO S3 API | 9000 | 9000 |
| MinIO Console | 9001 | 9001 |
