"""Configuration for the Orchestrator service."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

# ── SSL certificate bundle ────────────────────────────────────────────────────
# SSL_CERT_FILE / REQUESTS_CA_BUNDLE are set inside the Docker image to
# /app/ca-bundle.crt.  Outside Docker (local uv run) the paths don't
# exist → httpx raises [Errno 2].  Unset them so the system CA bundle
# is used instead.
for _cert_var in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
    _cert_path = os.getenv(_cert_var, "")
    if _cert_path and not os.path.isfile(_cert_path):
        os.environ.pop(_cert_var, None)

# Downstream agent ALB URLs (set via ECS task env or .env in local dev)
RISK_EVAL_URL: str = os.getenv("RISK_EVAL_URL", "http://localhost:8082")
NARRATIVE_SUMMARY_URL: str = os.getenv("NARRATIVE_SUMMARY_URL", "http://localhost:8083")
EVENT_HISTORY_URL: str = os.getenv("EVENT_HISTORY_URL", "http://localhost:8084")

# Foundation Services — all state writes go through here, never direct boto3
FOUNDATION_SERVICE_URL: str = os.getenv("FOUNDATION_SERVICE_URL", "http://localhost:9999")

# AWS
AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")

# DynamoDB — endpoint URL is set for local (dynamodb-local); unset in AWS to use real DynamoDB
DYNAMODB_ENDPOINT_URL: str = os.getenv("DYNAMODB_ENDPOINT_URL", "")

# DynamoDB -- used by LangGraph checkpointer (integrated via Foundation Services REST,
# not boto3 directly -- checkpointer wired in production, MemorySaver used locally)
LANGGRAPH_CHECKPOINTER_TABLE: str = os.getenv("LANGGRAPH_CHECKPOINTER_TABLE", "app-uai3071390-sdg-ddtable-orchestrator-checkpointer-dev")

# Data service — orchestrator pushes node progress via PATCH /internal/.../execution-state
DATA_SERVICE_URL: str = os.getenv("DATA_SERVICE_URL", "http://localhost:8086")

# Orchestrator job state store
# ORCHESTRATOR_USE_DYNAMODB=true: writes status metadata to execution-state rows
# via assessment-workflow-index; required for multi-replica ECS.
# ORCHESTRATOR_USE_DYNAMODB=false (default): in-memory; requires desiredCount=1 on ECS.
ORCHESTRATOR_USE_DYNAMODB: bool = os.getenv("ORCHESTRATOR_USE_DYNAMODB", "false").lower() == "true"
EXECUTION_STATE_TABLE: str = os.getenv("EXECUTION_STATE_TABLE", "app-uai3071390-sdg-ddtable-execution-state-store-dev")

# LangGraph checkpointer backend: "memory" (default, local dev) or "dynamodb" (production)
ORCHESTRATOR_CHECKPOINTER_TYPE: str = os.getenv("ORCHESTRATOR_CHECKPOINTER_TYPE", "memory")

# Local dev flag -- when true, skips real downstream agent calls
ORCHESTRATOR_LOCAL_MODE: bool = os.getenv("ORCHESTRATOR_LOCAL_MODE", "false").lower() == "true"

# ── Agent call timeouts & retry ───────────────────────────────────────────────
# AGENT_CALL_TIMEOUT_SECS <= 0 means no timeout for downstream agent calls.
AGENT_CALL_TIMEOUT_SECS: float = float(os.getenv("AGENT_CALL_TIMEOUT_SECS", "0"))
# Retried on transient errors (timeout / network / 5xx).  Not retried on 4xx.
AGENT_CALL_MAX_RETRIES: int = int(os.getenv("AGENT_CALL_MAX_RETRIES", "3"))
# Backoff multiplier: attempt N waits N * BACKOFF seconds (5 s, 10 s, 15 s …)
AGENT_CALL_RETRY_BACKOFF_SECS: float = float(os.getenv("AGENT_CALL_RETRY_BACKOFF_SECS", "5.0"))

APP_PREFIX: str = os.getenv("APP_PREFIX", "uai3071390-dev-sdg") + '-'