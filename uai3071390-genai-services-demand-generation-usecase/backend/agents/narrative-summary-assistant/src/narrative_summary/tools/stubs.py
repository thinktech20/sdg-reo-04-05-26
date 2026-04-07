"""Tool stubs for the Narrative Summary Assistant (A2).

Docstrings serve as tool descriptions sent to the LLM by Strands.
Replace stub returns with real Data Service calls in a later step.
"""

from __future__ import annotations

from strands import tool


@tool
def get_risk_findings(assessment_id: str) -> str:
    """Retrieve scored risk findings (with user feedback) for a given assessment.

    Returns a list of risk findings including component, severity, risk level,
    inspector notes, and any user feedback submitted after the risk evaluation.
    This is the primary data source for generating the narrative summary.

    Args:
        assessment_id: Unique identifier for the unit risk assessment.
    """
    import json  # noqa: PLC0415
    import os  # noqa: PLC0415

    import httpx  # noqa: PLC0415

    data_service_url = os.getenv("DATA_SERVICE_URL", "http://localhost:8086")
    try:
        resp = httpx.get(
            f"{data_service_url}/api/assessments/{assessment_id}/findings",
            timeout=10.0,
        )
        resp.raise_for_status()
        return json.dumps(resp.json())
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc), "findings": [], "feedback": {}})


@tool
def get_assessment_metadata(assessment_id: str) -> str:
    """Retrieve metadata for a given assessment record.

    Returns assessment details: unit ID, asset serial number, assessment date,
    originating persona, and current status.

    Args:
        assessment_id: Unique identifier for the unit risk assessment.
    """
    return f"[STUB] Assessment metadata for {assessment_id}: {{unit_id: null, date: null, status: 'draft'}}"


@tool
def lookup_historical_incidents(serial_number: str) -> str:
    """Look up historical incident records for an asset.

    Returns a summary of past failures, near-misses, and maintenance events
    that provide context for the current assessment narrative.

    Args:
        serial_number: Asset serial number (ESN) to retrieve history for.
    """
    return f"[STUB] Historical incidents for {serial_number}: {{incidents: [], total: 0}}"


@tool
def get_narrative_template(persona: str) -> str:
    """Retrieve the narrative report template for a given persona.

    Returns the structured template format specifying sections, required fields,
    and tone guidelines appropriate for the RE or OE persona.

    Args:
        persona: Target audience — 'RE' (Reliability Engineering) or 'OE' (Operations Engineering).
    """
    if persona.upper() == "RE":
        return "[STUB] RE template: {sections: ['Technical Summary', 'Failure Mode Analysis', 'Compliance Status', 'Recommendations']}"
    return "[STUB] OE template: {sections: ['Operational Impact', 'Risk Priority List', 'Action Items', 'Next Inspection Date']}"


@tool
def format_executive_summary(key_findings: str) -> str:
    """Format a concise executive summary from key risk findings.

    Takes a free-text description of key findings and returns a structured
    executive summary paragraph suitable for the report header.

    Args:
        key_findings: Free-text description of the most significant findings.
    """
    return f"[STUB] Executive summary generated from: {key_findings[:80]}..."


# Exported list for the agent
NARRATIVE_TOOLS = [
    get_risk_findings,
    get_assessment_metadata,
    lookup_historical_incidents,
    get_narrative_template,
    format_executive_summary,
]
