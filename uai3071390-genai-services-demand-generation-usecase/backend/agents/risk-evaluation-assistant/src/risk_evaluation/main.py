"""FastAPI application factory for the Risk Evaluation Assistant.

Routes:
  GET  /health                   — liveness probe
  POST /api/v1/risk-eval/run     — trigger risk evaluation for an assessment

Environment variables (all optional locally — defaults shown):
  LITELLM_API_BASE   http://localhost:4000   LiteLLM proxy base URL
  DATA_SERVICE_URL   http://localhost:8001   sdg-data-service base URL
  AUTH_LOCAL_MODE    true                    Skip ALB OIDC in local dev

Architecture notes:
  - Strands SDK: LiteLLMModel + per-request Agent() (no S3SessionManager — A1 is stateless)
  - LiteLLMModel + boto3.Session initialised ONCE at lifespan startup
  - Agent created per-request (threading.Lock — not concurrency-safe)
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from risk_evaluation.core.config.logger_config import get_logger

logger = get_logger(__name__)

#from app.api.router import api_router
from risk_evaluation.api.v1.router import api_router

ROUTE_PREFIX = "/api"

app = FastAPI(
    title="sdg-risk-eval-assistant",
    version="0.1.0",
    description="Risk Evaluation Assistant — Strands SDK + LiteLLM",
    docs_url=f"{ROUTE_PREFIX}/docs"
)

@app.get("/health")
@app.get("/riskevaluationassistant/")
@app.get("/riskevaluationassistant/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "riskevaluation-assistant"}

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # Allow local origins (change in production)
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
  api_router,
  prefix=f"/riskevaluationassistant{ROUTE_PREFIX}/v1/risk-eval",
  tags=["risk-eval"]
)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Liveness probe — consistent with all other SDG services."""
    return {"status": "ok", "service": "risk-evaluation-assistant"}