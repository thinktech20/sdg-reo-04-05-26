"""Environment configuration for the Q&A Agent.

All settings read from environment variables with safe local defaults.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from backend folder explicitly (works regardless of cwd)
# config.py -> question_answer -> src -> question-answer-agent -> agents -> backend
_backend_dir = Path(__file__).resolve().parents[4]
_env_path = _backend_dir / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
else:
    load_dotenv()  # Fallback to cwd

# ── LiteLLM proxy ────────────────────────────────────────────────────────────
LITELLM_API_BASE: str = os.getenv("LITELLM_PROXY_URL", os.getenv("LITELLM_API_BASE", "https://dev-gateway.apps.gevernova.net"))
LITELLM_API_KEY: str = os.getenv("LITELLM_API_KEY", "")
LITELLM_MODEL: str = os.getenv("LITELLM_MODEL", "litellm_proxy/azure-gpt-5-2")
# ── Model generation params ───────────────────────────────────────────────────
TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.1"))
MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "4000"))
LITELLM_STREAM: bool = os.getenv("LITELLM_STREAM", "false").lower() == "true"
STRANDS_DEBUG: bool = os.getenv("STRANDS_DEBUG", "false").lower() == "true"

# ── Session / S3 ─────────────────────────────────────────────────────────────
SESSION_S3_BUCKET_NAME: str = os.getenv("SESSION_S3_BUCKET_NAME", "app-uai3071390-sdg-dev-s3-qna-session")
SESSION_S3_REGION: str = os.getenv("SESSION_S3_REGION", "us-east-1")

# MinIO / local S3 fallback
S3_LOCAL_MODE: bool = os.getenv("S3_LOCAL_MODE", "false").lower() == "true"
S3_ENDPOINT_URL: str = os.getenv("S3_ENDPOINT_URL", "http://localhost:9000")
S3_ACCESS_KEY_ID: str = os.getenv("S3_ACCESS_KEY_ID", "minioadmin")
S3_SECRET_ACCESS_KEY: str = os.getenv("S3_SECRET_ACCESS_KEY", "minioadmin")

# ── Data Service / MCP ────────────────────────────────────────────────────────
DATA_SERVICE_URL: str = os.getenv("DATA_SERVICE_URL", "http://localhost:8086")
MCP_SERVER_URL: str = os.getenv("MCP_SERVER_URL", f"{DATA_SERVICE_URL}/dataservices/mcp/")

# ── Auth ──────────────────────────────────────────────────────────────────────
# AUTH_LOCAL_MODE=true → skip ALB OIDC JWT validation (local dev only)
AUTH_LOCAL_MODE: bool = os.getenv("AUTH_LOCAL_MODE", "true").lower() == "true"
ALB_REGION: str = os.getenv("ALB_REGION", "us-east-1")
EXPECTED_ALB_ARN: str = os.getenv("EXPECTED_ALB_ARN", "")

# ── Server ────────────────────────────────────────────────────────────────────
PORT: int = int(os.getenv("PORT", os.getenv("SERVER_PORT", "8087")))
SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")  # noqa: S104

# Session ID header forwarded by ALB (or set manually in local dev)
SESSION_ID_HEADER: str = "X-Session-Id"
REQUIRE_SESSION_ID: bool = os.getenv("REQUIRE_SESSION_ID", "false").lower() == "true"