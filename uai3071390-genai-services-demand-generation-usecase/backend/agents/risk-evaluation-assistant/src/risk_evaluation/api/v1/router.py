"""API v1 route handlers for the Risk Evaluation Assistant."""
from fastapi import APIRouter

from risk_evaluation.api.v1.endpoints import health_check, risk_assessment_creation_api

api_router = APIRouter()
api_router.include_router(health_check.router, tags=["Healthcheck"])
api_router.include_router(risk_assessment_creation_api.router, tags=["Risk Assessment Creation"])
