"""Pydantic I/O schemas for the Risk Evaluation Assistant."""

from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class RunRequest(BaseModel):
    """Request body for POST /api/v1/risk-eval/run."""

    model_config = ConfigDict(populate_by_name=True)

    query: str | None = None
    esn: str | None = None
    component_type: str | None = None
    equipment_type: str | None = Field(
        default=None,
        validation_alias=AliasChoices("equipment_type", "equipmentType"),
    )
    review_period: str | None = Field(
        default=None,
        validation_alias=AliasChoices("review_period", "reviewPeriod"),
    )
    unit_number: str | None = Field(
        default=None,
        validation_alias=AliasChoices("unit_number", "unitNumber"),
    )
    workflow_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("workflow_id", "workflowId"),
    )
    assessment_id: str | None = None
    persona: str | None = None
    filters: dict[str, Any] | None = None
    data_types: list[str] | None = Field(
        default=None,
        validation_alias=AliasChoices("data_types", "dataTypes"),
    )
    date_from: str | None = Field(
        default=None,
        validation_alias=AliasChoices("date_from", "dateFrom"),
    )
    date_to: str | None = Field(
        default=None,
        validation_alias=AliasChoices("date_to", "dateTo"),
    )


class RunResponse(BaseModel):
    """Response body for POST /api/v1/risk-eval/run."""

    result: str | None = None
    data: list[dict[str, Any]] | None = None
    columns: list[str] | None = None
    findings: list[dict[str, Any]] | None = None
    riskCategories: dict[str, dict[str, Any]] | list[dict[str, Any]] | None = None
    retrieval: dict[str, Any] | None = None
    status: str | None = None
    assessment_id: str | None = None
    message: str | None = None
