from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from commons.logging import get_logger
from data_service import config
from data_service.mock_services.equipment import get_er_cases_by_esn
from data_service.services.er_service import get_er_cases, get_risk_assessment_er_cases

logger = get_logger(__name__)

router = APIRouter(prefix="/dataservices/api/v1/er", tags=["er"])


def _build_mock_er_response(serial_number: str, component: str | None = None) -> dict[str, Any]:
    rows = get_er_cases_by_esn(serial_number)
    if component:
        component_lc = component.lower()
        rows = [
            row
            for row in rows
            if component_lc in str(row.get("category", "")).lower()
        ]

    records = [
        {
            "case_id": str(row.get("caseId") or row.get("id") or ""),
            "serial_number": str(row.get("serialNumber") or serial_number),
            "short_description": str(row.get("shortDesc") or ""),
            "full_description": str(row.get("longDesc") or ""),
            "close_notes": str(row.get("closeNotes") or ""),
            "resolution_notes": str(row.get("closeNotes") or ""),
            "field_action": "",
            "status": str(row.get("status") or ""),
            "priority": str(row.get("severity") or ""),
            "component": str(row.get("category") or ""),
            "sub_component": "",
            "equipment_code": "",
            "date_opened": str(row.get("dateOpened") or ""),
            "date_closed": "",
            "issue_type": str(row.get("category") or ""),
            "work_notes": str(row.get("closeNotes") or ""),
        }
        for row in rows
    ]

    return {
        "serial_number": serial_number,
        "result_count": len(records),
        "records": records,
        "metadata": {
            "naksha_status": "mock",
            "table_status": "mock",
        },
    }

class IssuePromptItem(BaseModel):
    """A single issue prompt with its associated UUID."""

    issue_id: str = Field(..., min_length=1, description="UUID identifying this issue")
    issue_prompt: str = Field(..., min_length=1, description="Natural-language search query")


class ERRequest(BaseModel):
    serial_number: str = Field(..., min_length=1, description="Equipment serial number")
    query: str = Field(..., min_length=1, description="Natural-language search query")
    k: int = Field(..., ge=1, le=50, description="Number of top results to return")
    query_type: str = Field("HYBRID", description="Retrieval mode: HYBRID or ANN")

class ER_risk_Request(BaseModel):
    issue_prompts: list[IssuePromptItem] = Field(..., min_length=1, description="List of issue prompts to search")
    esn: str = Field(..., min_length=1, description="Equipment serial number")
    k: int = Field(10, ge=1, le=50, description="Number of top results to return")
    query_type: str = Field("HYBRID", description="Retrieval mode: HYBRID or ANN")


@router.get("/health")
def er_health() -> dict[str, str]:
    return {"status": "ok", "service": "er"}


@router.get("/cases")
async def get_er_cases_endpoint(
    request: Request,
    serial_number: str = Query(..., min_length=1),
    component: str | None = Query(None),
) -> dict[str, Any]:
    if config.USE_MOCK:
        return _build_mock_er_response(serial_number, component)

    try:
        user = request.headers.get("x-user") or request.headers.get("x-caller-service") or "unknown"
        return await get_er_cases(
            esn=serial_number,
            component=component,
            user=user,
        )
    except Exception as exc:
        if config.USE_MOCK:
            logger.warning("ER route fallback in mock mode due to error: %s", exc)
            return _build_mock_er_response(serial_number, component)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/risk-er-cases")
async def get_risk_er_cases_endpoint(payload: ER_risk_Request) -> dict[str, Any]:

    logger.info(
        "Received ER cases request with esn=%s, issue_prompts=%d items",
        payload.esn,
        len(payload.issue_prompts),
    )
    try:
        # Convert Pydantic models to plain dicts for the service layer
        result_str = await get_risk_assessment_er_cases(
            esn=payload.esn,
            issue_prompts=[item.model_dump() for item in payload.issue_prompts],
            k=payload.k,
            query_type=payload.query_type,
        )
        result: dict[str, Any] = json.loads(result_str)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
