"""Pydantic I/O schemas for the Narrative Summary Assistant."""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class RunRequest(BaseModel):
    """Request body for POST /api/v1/narrative/run.

    The agent fetches findings and feedback directly from the data-service
    using assessment_id — no payload passing required.
    """

    model_config = ConfigDict(populate_by_name=True)

    assessment_id: str
    esn: str = Field(validation_alias=AliasChoices("esn", "serial_number"))
    persona: str  # "RE" | "OE"

    @property
    def serial_number(self) -> str:
        return self.esn


class NarrativeSummarySections(BaseModel):
    """Validated narrative summary sections returned by the endpoint."""

    unit_summary: str = Field(alias="Unit Summary")
    operational_history: str = Field(alias="OPERATIONAL HISTORY")
    misc_details: str = Field(alias="MISC Details")
    overall_equipment_health_assessment: str = Field(alias="Overall Equipment Health Assessment")
    recommendations: str = Field(alias="Recommendations")

    model_config = {
        "populate_by_name": True,
        "serialize_by_alias": True,
    }


class RunResponse(BaseModel):
    """Response body for POST /api/v1/narrative/run.

    Supports both the legacy simulate payload and the new structured runtime payload.
    """

    status: str | None = None
    assessment_id: str | None = None
    message: str | None = None
    serial_number: str | None = None
    narrative_valid: bool | None = None
    findings_count: int | None = None
    disagree_count: int | None = None
    high_risk_count: int | None = None
    narrative_summary: NarrativeSummarySections | str | None = None
