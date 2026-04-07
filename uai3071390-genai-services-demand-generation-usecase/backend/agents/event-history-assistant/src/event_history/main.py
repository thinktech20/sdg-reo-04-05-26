"""FastAPI application factory for the Event History Assistant.

Routes:
  GET  /health                       — liveness probe
  POST /api/v1/event-history/run     — compile event history & key findings

Environment variables (all optional locally — defaults shown):
  LITELLM_API_BASE   http://localhost:4000   LiteLLM proxy base URL
  DATA_SERVICE_URL   http://localhost:8001   sdg-data-service base URL
  AUTH_LOCAL_MODE    true                    Skip ALB OIDC in local dev

Architecture notes:
  - Strands SDK: LiteLLMModel + per-request Agent() (no S3SessionManager — A3 is stateless)
  - LiteLLMModel initialised ONCE at lifespan startup
  - Agent created per-request (threading.Lock — not concurrency-safe)
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from event_history.api.v1 import endpoints
from event_history.core.agent_factory import build_model

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Initialise shared resources on startup; release on shutdown."""
    logger.info("Initialising Event History Assistant")
    app.state.litellm_model = build_model()
    logger.info("Startup complete — LiteLLMModel ready")
    yield
    logger.info("Shutdown")


app = FastAPI(
    title="sdg-event-history-assistant",
    version="0.1.0",
    description="Event History Assistant — Strands SDK + LiteLLM",
    lifespan=lifespan,
)


@app.get("/health")
@app.get("/eventhistoryassistant/")
@app.get("/eventhistoryassistant/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "event-history-assistant"}


app.include_router(
    endpoints.router,
    prefix="/eventhistoryassistant/api/v1/event-history",
    tags=["event-history"],
)
