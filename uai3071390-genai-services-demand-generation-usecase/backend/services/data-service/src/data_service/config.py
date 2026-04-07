"""Data Service configuration -- all settings from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from backend folder explicitly (works regardless of cwd)
_backend_dir = Path(__file__).resolve().parents[4]  # config.py -> data_service -> src -> data-service -> services -> backend
_env_path = _backend_dir / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
else:
    load_dotenv()  # Fallback to cwd

# ── SSL certificate bundle ────────────────────────────────────────────────────
# SSL_CERT_FILE / REQUESTS_CA_BUNDLE are set inside the Docker image to
# /app/ca-bundle.crt.  The .env file mirrors those values so they work
# inside Docker Compose.  Outside Docker (local uv run) the paths don't
# exist → httpx / botocore raise [Errno 2].  Unset them so the system
# default CA bundle is used instead.
for _cert_var in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
    _cert_path = os.getenv(_cert_var, "")
    if _cert_path and not os.path.isfile(_cert_path):
        os.environ.pop(_cert_var, None)


def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


# ── Mock mode (local dev / CI) ────────────────────────────────────────────────
# Auto-detected: if NAKSHA_API_URL is configured the live endpoint is used.
# Override explicitly with USE_MOCK=true/false when needed.
_use_mock_env: str = os.getenv("USE_MOCK", "").strip()
if _use_mock_env:
    USE_MOCK: bool = _use_mock_env.lower() in {"1", "true", "yes", "y", "on"}
else:
    # No explicit override -- use mock only when Naksha endpoint is absent
    USE_MOCK: bool = not bool(os.getenv("NAKSHA_API_URL", "").strip())

# Domain-level mock controls (default to global USE_MOCK for backward compatibility).
# - USE_MOCK_UNITS: controls /api/units train source behavior
# - USE_MOCK_ASSESSMENTS: controls assessment/orchestrator/DDB workflow behavior

USE_MOCK_UNITS: bool = _to_bool(os.getenv("USE_MOCK_UNITS"), USE_MOCK)
USE_MOCK_ASSESSMENTS: bool = _to_bool(os.getenv("USE_MOCK_ASSESSMENTS"), USE_MOCK)

# ── Naksha SQL proxy ────────────────────────────────────────────────────────────────
APP_PREFIX: str = os.getenv("APP_PREFIX", "uai3071390-dev-sdg") + '-'

NAKSHA_API_URL: str = os.getenv("NAKSHA_API_URL","https://lp3c4ukmlh.execute-api.us-east-1.amazonaws.com/Dev/databricks-orchestrator-proxy-dev")
NAKSHA_BUSINESS: str = os.getenv("NAKSHA_BUSINESS", "")
NAKSHA_DOMAIN: str = os.getenv("NAKSHA_DOMAIN", "")
NAKSHA_SUBDOMAIN: str = os.getenv("NAKSHA_SUBDOMAIN", "")
NAKSHA_TIMEOUT: float = float(os.getenv("NAKSHA_TIMEOUT", "120"))
NAKSHA_MAX_RETRIES: int = int(os.getenv("NAKSHA_MAX_RETRIES", "3"))
NAKSHA_VERIFY_SSL: bool = _to_bool(os.getenv("NAKSHA_VERIFY_SSL", "true"), True)
NAKSHA_USER_EMAIL: str = os.getenv("NAKSHA_USER_EMAIL", "")
NAKSHA_USER_DOMAINS: list[str] = [
    item.strip() for item in os.getenv("NAKSHA_USER_DOMAINS", "fsr").split(",") if item.strip()
]
NAKSHA_USER_GROUP_IDS: list[str] = [
    item.strip() for item in os.getenv("NAKSHA_USER_GROUP_IDS", "").split(",") if item.strip()
]
NAKSHA_POLL_INTERVAL_SECONDS: float = float(os.getenv("NAKSHA_POLL_INTERVAL_SECONDS", "2"))
NAKSHA_MAX_POLLS: int = int(os.getenv("NAKSHA_MAX_POLLS", "60"))

# ── Orchestrator ──────────────────────────────────────────────────────────────
# Internal URL for the orchestrator service (not exposed to the browser).
ORCHESTRATOR_URL: str = os.getenv("ORCHESTRATOR_URL", "http://localhost:8081")

# Polling settings for the background task that waits for orchestrator completion.
# ORCHESTRATOR_POLL_MAX_ATTEMPTS <= 0 means no timeout (poll until COMPLETE/FAILED).
ORCHESTRATOR_POLL_INTERVAL_SECONDS: float = float(os.getenv("ORCHESTRATOR_POLL_INTERVAL_SECONDS", "3"))
ORCHESTRATOR_POLL_MAX_ATTEMPTS: int = int(os.getenv("ORCHESTRATOR_POLL_MAX_ATTEMPTS", "0"))

# ── Q&A Agent ─────────────────────────────────────────────────────────────────
# Internal URL for the Q&A agent — used to initialise an assessment session
# after analysis completes so the agent has context without a user prompt.
QNA_AGENT_URL: str = os.getenv("QNA_AGENT_URL", "http://localhost:8085")

# ── DynamoDB ──────────────────────────────────────────────────────────────────
DYNAMODB_REGION: str = os.getenv("DYNAMODB_REGION", "us-east-1")
# Set to http://dynamodb-local:8000 when running DynamoDB Local (Docker Compose).
# Leave unset (None) in AWS to use the real service.
DYNAMODB_ENDPOINT_URL: str | None = os.getenv("DYNAMODB_ENDPOINT_URL") or None

EXECUTION_STATE_TABLE: str = os.getenv("EXECUTION_STATE_TABLE", "app-uai3071390-sdg-ddtable-execution-state-store-dev")
RISK_ANALYSIS_TABLE: str = os.getenv("RISK_ANALYSIS_TABLE", "app-uai3071390-sdg-ddtable-risk-analysys-output-table-dev")
NARRATIVE_SUMMARY_TABLE: str = os.getenv("NARRATIVE_SUMMARY_TABLE", "app-uai3071390-sdg-ddtable-navigation-summary-dev")
EVENT_HISTORY_TABLE: str = os.getenv("EVENT_HISTORY_TABLE", "app-uai3071390-sdg-ddtable-event-history-report-dev")

# ── Auth ──────────────────────────────────────────────────────────────────────
# Bearer token forwarded from the calling agent (injected by ALB in production)
AUTH_LOCAL_MODE: bool = os.getenv("AUTH_LOCAL_MODE", "true").lower() == "true"
# ── CORS ──────────────────────────────────────────────────────────────────
# Comma-separated list of allowed origins. Default "*" is fine for local dev.
# Set to the actual frontend origin (e.g. http://localhost:4000) in staging/prod.
CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")

# ── IBAT (Install Base) ──────────────────────────────────────────────────
IBAT_MAX_RETRIES: int = int(os.getenv("IBAT_MAX_RETRIES", "3"))
IBAT_RETRY_BACKOFF_SECONDS: float = float(os.getenv("IBAT_RETRY_BACKOFF_SECONDS", "1.5"))

# ── ER Cases (Engineering Reviews) ───────────────────────────────────────
ER_CATALOG: str = os.getenv("ER_CATALOG", "vgpp")
ER_SCHEMA: str = os.getenv("ER_SCHEMA", "qlt_std_views")
ER_TABLE: str = os.getenv("ER_TABLE", "u_pac")

# ── FSR Reports (Field Service Reports) ──────────────────────────────────
FSR_CATALOG: str = os.getenv("FSR_CATALOG", "vgpp")
FSR_SCHEMA: str = os.getenv("FSR_SCHEMA", "fsr_std_views")
FSR_TABLE: str = os.getenv("FSR_TABLE", "fsr_field_vision_field_services_report_psot")

# ── Outage History / Event Master ─────────────────────────────────────────
EVENT_MASTER_CATALOG: str = os.getenv("EVENT_MASTER_CATALOG", "vgpp")
EVENT_MASTER_SCHEMA: str = os.getenv("EVENT_MASTER_SCHEMA", "fsr_std_views")
OUTAGE_EVENTMGMT_TABLE: str = os.getenv("OUTAGE_EVENTMGMT_TABLE", "eventmgmt_event_vision_sot")
OUTAGE_EQUIP_DTLS_TABLE: str = os.getenv("OUTAGE_EQUIP_DTLS_TABLE", "event_equipment_dtls_event_vision_sot")
OUTAGE_SCOPE_TABLE: str = os.getenv("OUTAGE_SCOPE_TABLE", "scope_schedule_summary_event_vision_sot")

# ── PRISM (Reliability Models) ───────────────────────────────────────────
PRISM_SCHEMA: str = os.getenv("PRISM_SCHEMA", "seg_std_views")
PRISM_SOT_TABLE: str = os.getenv("PRISM_SOT_TABLE", "seg_fmea_wo_models_gen_psot")
PRISM_MAX_RETRIES: int = int(os.getenv("PRISM_MAX_RETRIES", "3"))
PRISM_RETRY_BACKOFF_SECONDS: float = float(os.getenv("PRISM_RETRY_BACKOFF_SECONDS", "1.5"))

# ── Heatmap ──────────────────────────────────────────────────────────────
HEATMAP_SCHEMA: str = os.getenv("HEATMAP_SCHEMA", "fsr_std_views")
HEATMAP_TABLE: str = os.getenv("HEATMAP_TABLE", "fsr_unit_risk_matrix_view")
HEATMAP_MAX_RETRIES: int = int(os.getenv("HEATMAP_MAX_RETRIES", "3"))
HEATMAP_RETRY_BACKOFF_SECONDS: float = float(os.getenv("HEATMAP_RETRY_BACKOFF_SECONDS", "1.5"))

# ── Train Service ────────────────────────────────────────────────────────
TRAIN_QUERY_LIMIT: int = int(os.getenv("TRAIN_QUERY_LIMIT", "5"))
TRAIN_MAX_RETRIES: int = int(os.getenv("TRAIN_MAX_RETRIES", "3"))
TRAIN_RETRY_BACKOFF_SECONDS: float = float(os.getenv("TRAIN_RETRY_BACKOFF_SECONDS", "1.5"))