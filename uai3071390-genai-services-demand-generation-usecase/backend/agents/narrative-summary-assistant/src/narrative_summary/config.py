"""Configuration — Narrative Summary Assistant.

All settings read from environment variables with safe local defaults.
"""

from __future__ import annotations

import os


def _to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


LITELLM_API_BASE: str = os.getenv("LITELLM_PROXY_URL", "https://dev-gateway.apps.gevernova.net")
LITELLM_MODEL: str = os.getenv("LITELLM_MODEL", "litellm_proxy/gemini-3-flash")
LITELLM_API_KEY: str = os.getenv("LITELLM_API_KEY", "")
LITELLM_SSL_VERIFY: bool = _to_bool(os.getenv("LITELLM_SSL_VERIFY"), True)
# LITELLM_DEBUG: bool = _to_bool(os.getenv("LITELLM_DEBUG"), False)
LITELLM_DEBUG: bool = True  # Enable debug logging by default for better observability
DATA_SERVICE_URL: str = os.getenv("DATA_SERVICE_URL", "http://localhost:8086")
AUTH_LOCAL_MODE: bool = os.getenv("AUTH_LOCAL_MODE", "true").lower() == "true"

# Simulate mode — skip LLM and return a realistic pre-baked fixture
AGENT_SIMULATE_MODE: bool = os.getenv("AGENT_SIMULATE_MODE", "false").lower() == "true"

# Delay in seconds to sleep before returning the simulate fixture
AGENT_SIM_DELAY_SECS: float = float(os.getenv("AGENT_SIM_DELAY_SECS", "10"))
