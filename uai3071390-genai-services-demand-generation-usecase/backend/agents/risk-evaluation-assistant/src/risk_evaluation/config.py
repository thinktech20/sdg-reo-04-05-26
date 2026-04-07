"""Configuration — Risk Evaluation Assistant.

All settings read from environment variables with safe local defaults.
Auth bypass (AUTH_LOCAL_MODE=true) must be set explicitly in production as false.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def _to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

# Load .env from backend folder explicitly (works regardless of cwd)
_backend_dir = Path(__file__).resolve().parents[4]  # config.py -> risk_evaluation -> src -> risk-evaluation-assistant -> agents -> backend
_env_path = _backend_dir / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
else:
    load_dotenv()  # Fallback to cwd

# LiteLLM proxy base URL (injected by ECS task definition)
LITELLM_API_BASE: str = os.getenv(
    "LITELLM_API_BASE",
    os.getenv("LITELLM_PROXY_URL", "https://dev-gateway.apps.gevernova.net"),
)
LITELLM_API_KEY: str = os.getenv("LITELLM_API_KEY", os.getenv("LITELLM_PROXY_API_KEY", ""))

# LiteLLM model ID routed through LiteLLM proxy
LITELLM_MODEL_ID: str = os.getenv("LITELLM_MODEL_ID", os.getenv("LITELLM_MODEL", "azure-gpt-5-2"),
)

# Model identifier routed through LiteLLM proxy
LITELLM_MODEL: str = os.getenv(
    "LITELLM_MODEL",
    os.getenv("LITELLM_MODEL_ID", LITELLM_MODEL_ID),
)

# Keep main-side naming available without breaking the branch's existing env contract.
LITELLM_MODEL_ID: str = os.getenv("LITELLM_MODEL_ID", LITELLM_MODEL)
LITELLM_PROXY_API_KEY: str = os.getenv("LITELLM_PROXY_API_KEY", LITELLM_API_KEY)

# AWS region for boto3 session
AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")

# Data Service base URL (for future real tool calls)
DATA_SERVICE_URL: str = os.getenv("DATA_SERVICE_URL", "http://dataservices.sdg.dev:8086")

# Auth — set true locally to bypass ALB OIDC JWT validation
AUTH_LOCAL_MODE: bool = os.getenv("AUTH_LOCAL_MODE", "true").lower() == "true"

# MCP server URL for HTTP tool calls
MCP_SERVER_PARAMS: str = os.getenv("MCP_SERVER_PARAMS", f"{DATA_SERVICE_URL}/dataservices/mcp/")

# Simulate mode — skip full generation and persist a sample payload in data-service.
AGENT_SIMULATE_MODE: bool = _to_bool(os.getenv("AGENT_SIMULATE_MODE"), False)
AGENT_SIM_DELAY_SECS: float = float(os.getenv("AGENT_SIM_DELAY_SECS", "10"))
AGENT_SIM_SAVE_TIMEOUT_SECS: float = float(os.getenv("AGENT_SIM_SAVE_TIMEOUT_SECS", "15"))
