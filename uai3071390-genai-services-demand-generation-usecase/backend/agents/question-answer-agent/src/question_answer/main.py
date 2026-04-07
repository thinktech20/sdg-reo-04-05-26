"""FastAPI application factory for the Q&A Agent.

Routes:
  GET  /health                                          — liveness probe
  GET  /ready                                           — readiness probe (checks data-service)
  POST /api/v1/chat                                     — ad-hoc Q&A (internal contract)
  POST /api/assessments/{id}/chat/reliability            — RE persona (frontend contract)
  POST /api/assessments/{id}/chat/outage                 — OE persona (frontend contract)

  ALB path-based routing (same handlers, /questionansweragent prefix):
  GET  /questionansweragent/health
  GET  /questionansweragent/ready
  POST /questionansweragent/api/v1/chat
  POST /questionansweragent/api/assessments/{id}/chat/reliability
  POST /questionansweragent/api/assessments/{id}/chat/outage

Environment variables (all optional locally — defaults shown):
  LITELLM_API_BASE        http://localhost:4000              LiteLLM proxy
  LITELLM_MODEL           litellm_proxy/claude...            Model ID for proxy
  MCP_SERVER_URL          http://localhost:8001/mcp          MCP server endpoint
  SESSION_S3_BUCKET_NAME  app-uai3071390-sdg-dev-s3-qna-session  S3 bucket for session history
  AUTH_LOCAL_MODE         true                               Skip ALB OIDC in local dev
  SERVER_PORT             8087                               Listening port
  EXPECTED_ALB_ARN        (required in production)           ALB ARN for JWT signer validation

Architecture notes:
  - Full Strands SDK adoption: Agent() loop + LiteLLMModel + S3SessionManager
  - Per-request Agent construction (Strands Agent is NOT concurrency-safe)
  - LiteLLMModel + boto3.Session initialised ONCE at lifespan startup
  - Tools: MCP tools filtered by persona via MCPClient
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from question_answer import config
from question_answer.api.v1 import endpoints
from question_answer.core.agent_factory import build_boto_session, build_model
from question_answer.middleware.auth import AuthMiddleware

logging.basicConfig(level=logging.DEBUG if config.STRANDS_DEBUG else logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Initialise expensive shared resources on startup; release on shutdown.

    Shared resources (not per-request):
      - LiteLLMModel       — expensive to construct, safe to share
      - boto3.Session      — thread-safe, safe to share

    Per-request (NOT shared):
      - Agent              — uses threading.Lock, raises ConcurrencyException
                             when called concurrently → build fresh per request
      - S3SessionManager   — session-specific, bound to Agent instance
    """
    logger.info("Initialising Q&A Agent (port %d, strands_debug=%s)", config.PORT, config.STRANDS_DEBUG)

    if not config.AUTH_LOCAL_MODE and not config.EXPECTED_ALB_ARN:
        raise RuntimeError(
            "EXPECTED_ALB_ARN must be set in production (AUTH_LOCAL_MODE is false). "
            "Set this to the ARN of the ALB that fronts this service."
        )

    app.state.litellm_model = build_model()
    app.state.boto_session = build_boto_session()
    logger.info("Startup complete — LiteLLMModel + boto3.Session ready")
    yield
    logger.info("Shutdown — releasing resources")


app = FastAPI(
    title="sdg-qna-agent",
    version="0.1.0",
    description="Q&A Agent — Strands SDK + LiteLLM + MCP tools",
    lifespan=lifespan,
)

# CORS middleware (permissive for local dev — tighten in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth middleware — validates ALB OIDC JWT (or skips in AUTH_LOCAL_MODE)
app.add_middleware(AuthMiddleware)

@app.get("/health")
@app.get("/questionansweragent/")
@app.get("/questionansweragent/health")
async def health() -> dict[str, str]:
    """Liveness probe — always returns ok if the process is running."""
    return {"status": "ok", "service": "question-answer-agent"}


@app.get("/ready")
@app.get("/questionansweragent/ready")
async def ready() -> dict[str, str]:
    """Readiness probe — verifies data-service is reachable before accepting traffic."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(config.DATA_SERVICE_URL + "/dataservices/health")
            resp.raise_for_status()
    except Exception as exc:
        logger.warning("Readiness check failed — data-service unreachable: %s", exc)
        from fastapi import HTTPException  # noqa: PLC0415
        raise HTTPException(status_code=503, detail="data-service unreachable") from exc
    return {"status": "ready", "service": "question-answer-agent"}

# ALB path-based routing — requests arrive with /questionansweragent prefix
app.include_router(
    endpoints.router,
    prefix="/questionansweragent/api/v1",
    tags=["chat"],
)
