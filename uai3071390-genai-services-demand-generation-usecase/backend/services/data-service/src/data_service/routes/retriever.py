"""Retriever route for FSR (Field Service Reports) semantic search.

Route:  GET  /api/v1/retriever/health
Route:  POST /api/v1/retriever/retrieve
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from commons.logging import get_logger
from data_service.services.retriever_service import retrieve_issue_data

logger = get_logger(__name__)
router = APIRouter(prefix="/dataservices/api/v1/retriever", tags=["retriever"])


class IssuePromptItem(BaseModel):
    """A single issue prompt with its associated UUID."""

    issue_id: str = Field(..., min_length=1, description="UUID identifying this issue")
    issue_prompt: str = Field(..., min_length=1, description="Natural language query for FSR search")


class RetrieverRequest(BaseModel):
    """Request model for POST /retrieve endpoint."""

    issue_prompts: list[IssuePromptItem] = Field(..., min_length=1, description="List of issue prompts to search")
    esn: str = Field(..., min_length=1, description="Equipment serial number")


@router.get("/health")
def retriever_health() -> dict[str, str]:
    """Health check for retriever service."""
    return {"status": "ok", "service": "retriever"}


@router.post("/retrieve")
async def retrieve_endpoint(payload: RetrieverRequest) -> dict[str, Any]:
    """Search Field Service Reports using semantic search.

    This endpoint retrieves relevant technical documents from Databricks vector database
    and returns formatted evidence data.

    Use this for:
    - DC leakage test analysis and results
    - Field service report queries
    - Technical document analysis
    - Equipment inspection reports
    - Component failure analysis
    - Test methodology and acceptance criteria
    - Generator serial number lookups
    """
    logger.info(
        "retriever: POST /retrieve issue_prompts=%d items, esn=%s",
        len(payload.issue_prompts),
        payload.esn,
    )
    try:
        # Convert Pydantic models to plain dicts for the service layer
        result_str = await retrieve_issue_data(
            issue_prompts=[item.model_dump() for item in payload.issue_prompts],
            esn=payload.esn,
        )
        result: dict[str, Any] = json.loads(result_str)
        return result
    except Exception as exc:
        logger.exception("retriever: unexpected error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
