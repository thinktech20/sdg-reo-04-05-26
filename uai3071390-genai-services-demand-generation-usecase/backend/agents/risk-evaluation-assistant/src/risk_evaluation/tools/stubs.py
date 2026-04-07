"""Tool stubs for the Risk Evaluation Assistant (A1).

These are @tool-decorated stubs. The function docstrings are used by the
Strands Agent as tool descriptions sent to the LLM — docstring quality matters.

Replace stub return values with real Data Service calls in a later step.
"""

from __future__ import annotations

from strands import tool


@tool
def get_risk_heatmap(assessment_id: str) -> str:
    """Retrieve the risk heatmap for a given assessment.

    Returns a JSON-formatted risk heatmap showing components flagged as
    high / medium / low risk based on inspection findings.

    Args:
        assessment_id: Unique identifier for the unit risk assessment.
    """
    return f"[STUB] Risk heatmap for assessment {assessment_id}: {{components: [], risk_levels: []}}"


@tool
def lookup_ibat_entry(serial_number: str) -> str:
    """Look up IBAT (Inspection-Based Asset Tracking) data for a given asset.

    Returns structured inspection records including findings, dates, and
    inspector notes from the IBAT system.

    Args:
        serial_number: Asset serial number (ESN) to retrieve IBAT records for.
    """
    return f"[STUB] IBAT data for {serial_number}: {{findings: [], last_inspection: null}}"


@tool
def lookup_prism_entry(serial_number: str) -> str:
    """Look up PRISM predictive maintenance data for a given asset.

    Returns predictive risk indicators, historical failure patterns, and
    maintenance recommendations from the PRISM analytics system.

    Args:
        serial_number: Asset serial number (ESN) to retrieve PRISM data for.
    """
    return f"[STUB] PRISM data for {serial_number}: {{risk_indicators: [], failure_modes: []}}"


@tool
def lookup_compliance_criteria(standard_id: str) -> str:
    """Retrieve compliance criteria for a specific inspection standard.

    Returns the acceptance criteria, threshold values, and regulatory
    references applicable to the given inspection standard.

    Args:
        standard_id: Standard identifier (e.g. 'API-580', 'ASME-B31.3').
    """
    return f"[STUB] Compliance criteria for {standard_id}: {{thresholds: [], references: []}}"


@tool
def calculate_risk_score(severity: str, likelihood: str) -> str:
    """Calculate a composite risk score using the DS risk scoring methodology.

    Applies the severity × likelihood risk matrix to produce a risk level
    (High / Medium / Low / Acceptable) consistent with the DS scoring formula.

    Args:
        severity: Finding severity — 'High', 'Medium', or 'Low'.
        likelihood: Occurrence likelihood — 'High', 'Medium', or 'Low'.
    """
    matrix: dict[tuple[str, str], str] = {
        ("High", "High"): "Critical",
        ("High", "Medium"): "High",
        ("High", "Low"): "Medium",
        ("Medium", "High"): "High",
        ("Medium", "Medium"): "Medium",
        ("Medium", "Low"): "Low",
        ("Low", "High"): "Medium",
        ("Low", "Medium"): "Low",
        ("Low", "Low"): "Acceptable",
    }
    score = matrix.get((severity, likelihood), "Unknown")
    return f"Risk score [{severity} × {likelihood}] = {score}"


# Exported list for the agent
RISK_EVAL_TOOLS = [
    get_risk_heatmap,
    lookup_ibat_entry,
    lookup_prism_entry,
    lookup_compliance_criteria,
    calculate_risk_score,
]
