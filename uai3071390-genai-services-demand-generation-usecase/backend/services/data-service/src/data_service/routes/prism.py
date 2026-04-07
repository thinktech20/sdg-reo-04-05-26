"""PRISM FMEA route.

Source table: vgpp.seg_std_views.seg_fmea_wo_models_gen_psot
Route:  POST /api/v1/prism/read   { serial_number, component? }
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from commons.logging import get_logger
from data_service.services.prism_service import PrismServiceError, read_prism_by_serial

logger = get_logger(__name__)
router = APIRouter(prefix="/dataservices/api/v1/prism", tags=["prism"])


class PrismReadRequest(BaseModel):
    serial_number: str
    component: str = ""
    metadata_filters: dict[str, Any] | None = None
    request_id: str | None = None


def _prism_error_response(exc: PrismServiceError) -> HTTPException:
    status_code = 400
    if exc.error_code == "UNAUTHORIZED":
        status_code = 403
    if exc.error_code == "SERIAL_NOT_FOUND":
        status_code = 404
    if exc.error_code == "RATE_LIMITED":
        status_code = 429
    if exc.error_code == "SYSTEM_ERROR":
        status_code = 500
    detail = {
        "status": "error",
        "error_code": exc.error_code,
        "message": exc.message,
    }
    if exc.request_id:
        detail["request_id"] = exc.request_id
    return HTTPException(
        status_code=status_code,
        detail=detail,
    )


async def _read_prism_payload(
    request: Request,
    serial_number: str,
    component: str = "",
    metadata_filters: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    user = request.headers.get("x-user") or request.headers.get("x-caller-service") or "unknown"

    effective_metadata_filters = dict(metadata_filters or {})
    if component:
        effective_metadata_filters.setdefault("component", component)

    return await read_prism_by_serial(
        serial_number=serial_number,
        requesting_user=user,
        metadata_filters=effective_metadata_filters,
        request_id=request_id,
        db_client=request.app.state.naksha_client,
    )


@router.post("/read")
async def read_prism(
    body: PrismReadRequest,
    request: Request,
) -> dict[str, Any]:
    """Return PRISM FMEA records for the given serial number and optional component.

    Known blocker: table `sot_seg_fmea_wo_models_gen_psot` access pending confirmation.
    With USE_MOCK=true returns canned records regardless.
    """
    logger.info("prism: POST - read serial_number=%s component=%s", body.serial_number, body.component)
    logger.info("prism: POST Metadat filter - " + str(body.metadata_filters))
    try:
        return await _read_prism_payload(
            request=request,
            serial_number=body.serial_number,
            component=body.component,
            metadata_filters=body.metadata_filters,
            request_id=body.request_id,
        )
    except PrismServiceError as exc:
        raise _prism_error_response(exc) from exc
    except Exception as exc:
        logger.exception("prism: unexpected error")
        raise HTTPException(status_code=500, detail="An internal error occurred") from exc


@router.get("/health")
async def prism_health() -> dict[str, str]:
    return {"status": "ok", "service": "prism"}
