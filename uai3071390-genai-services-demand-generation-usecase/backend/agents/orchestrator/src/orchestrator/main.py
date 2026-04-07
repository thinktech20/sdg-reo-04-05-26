"""FastAPI application entry point for the Orchestrator service.

Startup:
  - Compiles the LangGraph serial pipeline once and stores it in app.state.graph.
  - Pipeline is shared across all requests (stateless compilation; per-run state
    lives in MemorySaver checkpointer keyed by assessment_id / thread_id).

Port: 8006
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from orchestrator.api.v1.endpoints import router
from orchestrator.graph.pipeline import build_pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Build shared resources once at startup; release on shutdown."""
    logger.info("orchestrator: building LangGraph pipeline")
    app.state.graph = build_pipeline()
    logger.info("orchestrator: pipeline ready")
    yield
    logger.info("orchestrator: shutdown")


app = FastAPI(
    title="SDG Orchestrator",
    description="LangGraph serial pipeline dispatcher.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
@app.get("/orchestrator")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "orchestrator"}


app.include_router(router, prefix="/orchestrator")
