"""FastAPI application factory for the Narrative Summary Assistant.

Routes:
  GET  /health                  — liveness probe
  POST /api/v1/narrative/run    — generate narrative summary for an assessment

Environment variables (all optional locally — defaults shown):
  LITELLM_API_BASE   http://localhost:4000   LiteLLM proxy base URL
  DATA_SERVICE_URL   http://localhost:8001   sdg-data-service base URL
  AUTH_LOCAL_MODE    true                    Skip ALB OIDC in local dev

Architecture notes:
  - Strands SDK: LiteLLMModel + per-request Agent() (no S3SessionManager — A2 is stateless)
  - LiteLLMModel initialised ONCE at lifespan startup
  - Agent created per-request (threading.Lock — not concurrency-safe)
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from narrative_summary.api.v1 import endpoints

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Startup / shutdown hook (no shared resources needed — LiteLLM called directly)."""
    logger.info("Narrative Summary Assistant starting")
    yield
    logger.info("Shutdown")


app = FastAPI(
    title="sdg-narrative-assistant",
    version="0.1.0",
    description="Narrative Summary Assistant — Strands SDK + LiteLLM",
    lifespan=lifespan,
)


@app.get("/health")
@app.get("/summarizationassistant/")
@app.get("/summarizationassistant/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "narrative-summary-assistant"}


app.include_router(
    endpoints.router,
  prefix="/api/v1/narrative",
  tags=["narrative"],
)

app.include_router(
  endpoints.router,
    prefix="/summarizationassistant/api/v1/narrative",
    tags=["narrative"],
)
