"""API v1 route handler for the Health Check."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

from risk_evaluation.core.config.logger_config import get_logger

# Initialize logger
logger = get_logger(__name__)


@router.get("/healthcheck")
def healthcheck() -> JSONResponse:
    try:
        logger.info("Checking overall health")
        return JSONResponse(
            content={
                "status": "healthy",
                "message": "Service is up and running",
                "registered_users": 1,
            },
            status_code=200,
        )

    except Exception as e:
        logger.error(f"Healthcheck failed: {str(e)}")
        return JSONResponse(
            content={"status": "unhealthy", "message": "Service health check failed"},
            status_code=503,
        )
