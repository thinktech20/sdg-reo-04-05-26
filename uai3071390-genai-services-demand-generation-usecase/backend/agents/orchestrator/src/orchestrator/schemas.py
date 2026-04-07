"""Pydantic schemas for the Orchestrator API boundary."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class NodeTiming(BaseModel):
    """Start / end timestamps for a single pipeline node."""

    startedAt: str
    completedAt: str | None = None


class RunRequest(BaseModel):
    """Payload sent by the data-service to trigger a pipeline run."""

    assessment_id: str = Field(..., description="Assessment UUID")
    job_type: str = Field(default="run", description="Pipeline to run: 'run' (A1/A3) | 'narrative' (A2, post-feedback)")
    esn: str = Field(..., description="Equipment serial number")
    persona: str = Field(default="RE", description="User persona: RE | OE")
    input_payload: dict[str, Any] = Field(default_factory=dict)


class RunAcceptedResponse(BaseModel):
    """202 Accepted — job queued, poll /status for progress."""

    assessmentId: str
    status: str = Field(default="PENDING")


class StatusResponse(BaseModel):
    """Job status response — matches the frontend JobStatus interface exactly."""

    assessmentId: str
    jobType: str
    status: str = Field(..., description="PENDING | RUNNING | COMPLETE | FAILED")
    result: dict[str, Any] | None = None
    errorMessage: str | None = None
    activeNode: str | None = None
    nodeTimings: dict[str, NodeTiming] | None = None
