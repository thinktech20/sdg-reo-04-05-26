"""IBAT equipment data route.

Routes:
    GET /api/v1/ibat/health
    GET /api/v1/ibat/equipment?equip_serial_number={esn}
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from commons.logging import get_logger
from data_service.services.ibat_service import IbatServiceError, read_ibat_by_serial

logger = get_logger(__name__)

router = APIRouter(prefix="/dataservices/api/v1/ibat", tags=["ibat"])


def _ibat_error_response(exc: IbatServiceError) -> HTTPException:
    status_code = 400
    if exc.error_code == "SERIAL_NOT_FOUND":
        status_code = 404
    if exc.error_code == "UNAUTHORIZED":
        status_code = 403
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


async def _read_ibat_equipment(
    request: Request,
    equip_serial_number: str | None = None,
    serial_number: str | None = None,
    request_id: str | None = None,
    equipment_sys_id: str | None = None,
    site_customer_name: str | None = None,
    plant_name: str | None = None,
    metadata_filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    effective_serial = str(equip_serial_number or serial_number or "").strip()
    if not effective_serial:
        raise IbatServiceError("INVALID_INPUT", "equip_serial_number or serial_number is required")

    user = request.headers.get("x-user") or request.headers.get("x-caller-service") or "unknown"
    effective_metadata_filters = dict(metadata_filters or {})
    if equipment_sys_id:
        effective_metadata_filters["equipment_sys_id"] = equipment_sys_id
    if site_customer_name:
        effective_metadata_filters["site_customer_name"] = site_customer_name
    if plant_name:
        effective_metadata_filters["plant_name"] = plant_name

    return await read_ibat_by_serial(
        equip_serial_number=effective_serial,
        metadata_filters=effective_metadata_filters,
        user=user,
        request_id=request_id,
    )


@router.get("/equipment")
async def get_ibat_equipment_endpoint(
    request: Request,
    equip_serial_number: str | None = Query(None, min_length=1),
    serial_number: str | None = Query(None, min_length=1),
    request_id: str | None = Query(None, min_length=1),
    equipment_sys_id: str | None = Query(None, min_length=1),
    site_customer_name: str | None = Query(None, min_length=1),
    plant_name: str | None = Query(None, min_length=1),
) -> dict[str, Any]:
    try:
        return await _read_ibat_equipment(
            request=request,
            equip_serial_number=equip_serial_number,
            serial_number=serial_number,
            request_id=request_id,
            equipment_sys_id=equipment_sys_id,
            site_customer_name=site_customer_name,
            plant_name=plant_name,
        )
    except IbatServiceError as exc:
        raise _ibat_error_response(exc) from exc
    except Exception as exc:
        logger.exception("ibat: unexpected error")
        raise HTTPException(status_code=500, detail="An internal error occurred") from exc


@router.get("/health")
async def ibat_health() -> dict[str, str]:
    return {"status": "ok", "service": "ibat"}
