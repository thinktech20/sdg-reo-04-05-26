"""Risk heatmap / risk-matrix route.

Source view: vgpp.fsr_std_views.fsr_unit_risk_matrix_view
Routes:
    GET  /api/v1/heatmap/load?equipment_type={GEN|GT}&persona={REL|OE}&component={}
    GET  /api/v1/heatmap/health
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from commons.logging import get_logger
from data_service.services.heatmap_service import HeatmapServiceError, read_heatmap

logger = get_logger(__name__)
router = APIRouter(prefix="/dataservices/api/v1/heatmap", tags=["heatmap"])


def _heatmap_error_response(exc: HeatmapServiceError) -> HTTPException:
    status_code = 400
    if exc.error_code == "NO_DATA":
        status_code = 404
    if exc.error_code == "UNAUTHORIZED":
        status_code = 403
    if exc.error_code == "RATE_LIMITED":
        status_code = 429
    if exc.error_code == "SYSTEM_ERROR":
        status_code = 500
    detail: dict[str, Any] = {
        "status": "error",
        "error_code": exc.error_code,
        "message": exc.message,
    }
    if exc.request_id:
        detail["request_id"] = exc.request_id
    return HTTPException(status_code=status_code, detail=detail)


@router.get("/load")
async def load_heatmap(
    request: Request,
    equipment_type: str | None = Query(None, description="GEN or GT"),
    persona: str | None = Query(None, description="REL or OE"),
    component: str = Query("", description="Optional component filter"),
    serial_number: str | None = Query(None, min_length=1, description="Optional ESN context for audit logging"),
    request_id: str | None = Query(None, min_length=1),
) -> dict[str, Any]:
    """Return risk-matrix rows for the given equipment type and persona."""
    if equipment_type is None or not str(equipment_type).strip():
        raise _heatmap_error_response(HeatmapServiceError("INVALID_INPUT", "equipment_type is required"))

    if persona is None or not str(persona).strip():
        raise _heatmap_error_response(HeatmapServiceError("INVALID_INPUT", "persona is required"))

    logger.info(
        "heatmap: GET /load equipment_type=%s persona=%s component=%s serial_number=%s",
        equipment_type,
        persona,
        component,
        serial_number,
    )
    user = request.headers.get("x-user") or request.headers.get("x-caller-service") or "unknown"

    effective_metadata_filters: dict[str, Any] = {}
    if component:
        effective_metadata_filters["component"] = component

    try:
        return await read_heatmap(
            equipment_type=equipment_type,
            persona=persona,
            serial_number=serial_number,
            requesting_user=user,
            metadata_filters=effective_metadata_filters,
            request_id=request_id,
            db_client=request.app.state.naksha_client,
        )
    except HeatmapServiceError as exc:
        raise _heatmap_error_response(exc) from exc
    except Exception as exc:
        logger.exception("heatmap: unexpected error")
        raise HTTPException(status_code=500, detail="An internal error occurred") from exc


@router.get("/health")
async def heatmap_health() -> dict[str, str]:
    return {"status": "ok", "service": "heatmap"}
