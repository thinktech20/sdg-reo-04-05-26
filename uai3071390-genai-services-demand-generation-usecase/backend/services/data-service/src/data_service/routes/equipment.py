"""
Equipment routes.

**Equipment** is a serialised gas turbine component identified by ESN (Equipment Serial Number).
It belongs to a Unit installation (unitId / unitNumber).
Use GET /dataservices/api/v1/units to browse the fleet; use these routes for ESN-level detail.

Routes (all served under canonical /dataservices/api/v1/ prefix):
  GET /dataservices/api/v1/equipment/search?esn=
  GET /dataservices/api/v1/equipment/{esn}/data-readiness
  GET /dataservices/api/v1/equipment/{esn}/er-cases
  GET /dataservices/api/v1/equipment/{esn}/fsr-reports
  GET /dataservices/api/v1/equipment/{esn}/outage-history
  GET /dataservices/api/v1/equipment/{esn}/documents  (see documents.py)
  POST /dataservices/api/v1/equipment/{esn}/documents (see documents.py)

The frontend always calls /api/* — nginx/vite rewrites /api/* → /dataservices/api/v1/*
before the request reaches this service, so callers never need to know the internal prefix.
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from commons.logging import get_logger
from data_service import config
from data_service.mock_services.equipment import search_equipment_by_esn as mock_search_equipment_by_esn
from data_service.services.equipment_service import (
    get_data_readiness,
    get_er_cases,
    get_fsr_reports,
    get_outage_history,
)
from data_service.services.ibat_service import IbatServiceError, search_equipment_by_esn as ibat_search_equipment_by_esn

logger = get_logger(__name__)
router = APIRouter(prefix="/dataservices/api/v1", tags=["equipment"])


def _equipment_error_response(exc: IbatServiceError) -> HTTPException:
    status_code = 400
    if exc.error_code == "SERIAL_NOT_FOUND":
        status_code = 404
    if exc.error_code == "UNAUTHORIZED":
        status_code = 403
    if exc.error_code == "RATE_LIMITED":
        status_code = 429
    if exc.error_code == "SYSTEM_ERROR":
        status_code = 500
    detail: dict[str, str] = {"status": "error", "error_code": exc.error_code, "message": exc.message}
    if exc.request_id:
        detail["request_id"] = exc.request_id
    return HTTPException(status_code=status_code, detail=detail)


@router.get("/equipment/search")
async def search_equipment(
    request: Request, esn: str = Query(...), request_id: str | None = Query(None, min_length=1)
) -> dict[str, Any]:
    """Lookup a single piece of equipment by ESN."""
    try:
        if not esn:
            raise IbatServiceError("INVALID_INPUT", "equip_serial_number or serial_number is required")
        if config.USE_MOCK:
            equipment = mock_search_equipment_by_esn(esn)
        else:
            user = request.headers.get("x-user") or request.headers.get("x-caller-service") or "unknown"
            equipment = await ibat_search_equipment_by_esn(esn=esn, request_id=request_id, user=user)
        if not equipment:
            raise HTTPException(status_code=404, detail=f"Equipment '{esn}' not found")
        return {"equipment": equipment}
    except IbatServiceError as exc:
        raise _equipment_error_response(exc) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("equipment: unexpected error")
        raise HTTPException(status_code=500, detail="An internal error occurred") from exc


@router.get("/equipment/{esn}/data-readiness")
async def data_readiness(
    request: Request,
    esn: str,
    from_date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    to_date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
) -> dict[str, Any]:
    """Consolidated data-source availability counts for an ESN."""
    db_client = request.app.state.naksha_client
    return await get_data_readiness(esn, from_date=from_date, to_date=to_date, db_client=db_client)


@router.get("/equipment/{esn}/er-cases")
async def er_cases(
    request: Request,
    esn: str,
    start_date: str | None = Query(None, alias="startDate", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end_date: str | None = Query(None, alias="endDate", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
) -> dict[str, Any]:
    db_client = request.app.state.naksha_client
    return {
        "erCases": await get_er_cases(esn, from_date=start_date, to_date=end_date, page=page, page_size=page_size, db_client=db_client),
        "page": page,
        "pageSize": page_size,
    }


@router.get("/equipment/{esn}/fsr-reports")
async def fsr_reports(
    request: Request,
    esn: str,
    start_date: str | None = Query(None, alias="startDate", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end_date: str | None = Query(None, alias="endDate", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
) -> dict[str, Any]:
    db_client = request.app.state.naksha_client
    return {
        "fsrReports": await get_fsr_reports(esn, from_date=start_date, to_date=end_date, page=page, page_size=page_size, db_client=db_client),
        "page": page,
        "pageSize": page_size,
    }


@router.get("/equipment/{esn}/outage-history")
async def outage_history(
    request: Request,
    esn: str,
    start_date: str | None = Query(None, alias="startDate", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end_date: str | None = Query(None, alias="endDate", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
) -> dict[str, Any]:
    db_client = request.app.state.naksha_client
    return {
        "outageHistory": await get_outage_history(esn, from_date=start_date, to_date=end_date, page=page, page_size=page_size, db_client=db_client),
        "page": page,
        "pageSize": page_size,
    }
