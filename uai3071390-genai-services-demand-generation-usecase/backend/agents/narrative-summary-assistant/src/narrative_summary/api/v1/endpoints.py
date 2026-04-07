"""API v1 route handlers for the Narrative Summary Assistant.

Pull-based, tool-free approach:
  1. Fetch risk findings + user feedback from the data-service directly.
  2. Build a prompt containing all findings data (including pre-computed risk counts).
  3. Call LiteLLM directly (no Strands agent, no tools).
  4. Return narrative_summary in the response.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os

import httpx
from fastapi import APIRouter

from narrative_summary import config
from narrative_summary.prompts import SYSTEM_PROMPT
from narrative_summary.schemas import NarrativeSummarySections, RunRequest, RunResponse
from narrative_summary.simulate import simulate_run

logger = logging.getLogger(__name__)

router = APIRouter()

_LITELLM_MAX_TOKENS = 12000
_LITELLM_TIMEOUT = httpx.Timeout(180.0, connect=30.0)
_INVALID_JSON_MAX_RETRIES = 2

_REQUIRED_NARRATIVE_SECTIONS: tuple[tuple[str, str], ...] = (
    ("Unit Summary", "unit_summary"),
    ("OPERATIONAL HISTORY", "operational_history"),
    ("MISC Details", "misc_details"),
    ("Overall Equipment Health Assessment", "overall_equipment_health_assessment"),
    ("Recommendations", "recommendations"),
)


async def _fetch_findings(assessment_id: str) -> tuple[list, dict]:
    """Fetch risk findings and user feedback from the data-service."""
    try:
        async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
            resp = await client.get(
                f"{config.DATA_SERVICE_URL}/dataservices/api/v1/assessments/{assessment_id}/findings"
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("findings", []), data.get("summary", ""), data.get("feedback", {})
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "narrative: could not fetch findings for %s: %s", assessment_id, exc
        )
        return [], "", {}


def _first_present_value(row: dict[str, object], *keys: str) -> object | None:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _normalize_date_value(value: object) -> str | None:
    if value in (None, ""):
        return None

    text = str(value).strip()
    if not text:
        return None
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    return text


def _normalize_float_value(value: object) -> float | None:
    if value in (None, ""):
        return None

    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _normalize_prism_row(row: dict[str, object], serial_number: str) -> dict[str, object]:
    gen_cod = _normalize_date_value(_first_present_value(row, "GEN_COD", "gen_cod"))
    last_rewind = _normalize_date_value(_first_present_value(row, "LAST_REWIND", "last_rewind"))
    risk_model_start_date = last_rewind or gen_cod
    risk_model_start_reason = (
        "LAST_REWIND used as risk model start date"
        if last_rewind
        else "GEN_COD no rewind on record"
    )

    return {
        "TURBINE_NUMBER": str(
            _first_present_value(row, "TURBINE_NUMBER", "turbine_number", "serial_number")
            or serial_number
        ),
        "ADJ_RISK": _normalize_float_value(_first_present_value(row, "ADJ_RISK", "adj_risk")),
        "MODEL_DESC": str(_first_present_value(row, "MODEL_DESC", "model_desc") or ""),
        "GEN_COD": gen_cod,
        "RISK_PROFILE": str(_first_present_value(row, "RISK_PROFILE", "risk_profile") or ""),
        "LAST_REWIND": last_rewind,
        "RISK_MODEL_START_DATE": risk_model_start_date,
        "RISK_MODEL_START_REASON": risk_model_start_reason,
    }


async def _fetch_prism_component(serial_number: str, component: str) -> dict[str, object] | None:
    """Fetch one PRISM record for a specific component."""
    try:
        async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
            resp = await client.post(
                f"{config.DATA_SERVICE_URL}/dataservices/api/v1/prism/read",
                json={
                    "serial_number": serial_number,
                    "metadata_filters": {"component": component},
                    "request_id": f"narrative-prism-{serial_number}-{component.lower()}",
                },
                headers={"x-caller-service": "narrative-summary-assistant"},
            )
            resp.raise_for_status()
            data = resp.json()
            rows = data.get("data", []) if isinstance(data, dict) else []
            if not isinstance(rows, list):
                return None
            for row in rows:
                if isinstance(row, dict):
                    return _normalize_prism_row(row, serial_number)
            return None
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "narrative: could not fetch prism data for %s component=%s: %s",
            serial_number,
            component,
            exc,
        )
        return None


def _build_risk_assessment_table(findings: list[dict], summary: str) -> dict[str, object]:
    transformed_findings: list[dict[str, object]] = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        transformed_findings.append(
            {
                "Finding ID": str(finding.get("id") or ""),
                "Issue Name": finding.get("Issue name", ""),
                "Component and Issue Grouping": finding.get("Component and Issue Grouping", ""),
                "Condition": finding.get("Condition", ""),
                "Threshold": finding.get("Threshold", ""),
                "Actual Value": finding.get("Actual Value", ""),
                "Risk": finding.get("Risk", ""),
                "Evidence": finding.get("Evidence", ""),
                "Citation": finding.get("Citation", ""),
                "Justification": finding.get("justification", ""),
            }
        )

    return {"findings": transformed_findings, "summary": summary}


def _derive_agreement(feedback: dict[str, object]) -> str:
    explicit = str(feedback.get("Agreement") or feedback.get("agreement") or "").strip().lower()
    if explicit in {"agree", "disagree"}:
        return "Agree" if explicit == "agree" else "Disagree"

    signal = str(feedback.get("feedback") or "").strip().lower()
    if signal == "up":
        return "Agree"
    if signal == "down":
        return "Disagree"

    helpful = feedback.get("helpful")
    if isinstance(helpful, bool):
        return "Agree" if helpful else "Disagree"

    try:
        rating = int(str(feedback.get("rating") or "").strip())
        if rating < 0:
            return "Disagree"
        if rating > 0:
            return "Agree"
    except (TypeError, ValueError):
        pass

    return "Agree"


def _normalize_risk_level(value: str | None) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return "Not Mentioned"

    lowered = normalized.lower()
    if lowered in {"med", "medium"}:
        return "Med"
    if lowered in {"light", "l or n/a", "l or n/a ", "l or n/a."}:
        return "Light"
    if lowered in {"heavy"}:
        return "Heavy"
    if lowered in {"immediate action", "immediate"}:
        return "IMMEDIATE ACTION"
    if lowered in {"no data", "not mentioned", "no data or medium", "n/a"}:
        return "Not Mentioned"
    return normalized


def _rating_to_corrected_level(rating: object) -> str | None:
    try:
        normalized_rating = int(str(rating).strip())
    except (TypeError, ValueError):
        return None

    if normalized_rating <= 0:
        return None
    if normalized_rating <= 2:
        return "Light"
    if normalized_rating == 3:
        return "Med"
    if normalized_rating == 4:
        return "Heavy"
    return "IMMEDIATE ACTION"


def _feedback_level_to_correctness(value: object) -> str | None:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None

    if normalized in {"not mentioned", "not_mentioned", "none", "n/a", "na"}:
        return "Not Mentioned"
    if normalized in {"low", "light"}:
        return "Light"
    if normalized in {"med", "medium"}:
        return "Med"
    if normalized in {"high", "heavy"}:
        return "Heavy"
    if normalized in {"immediate", "immediate action", "immediate_action"}:
        return "IMMEDIATE ACTION"
    return None


def _build_user_feedback(
    findings: list[dict],
    feedback_map: dict[str, dict],
) -> list[dict[str, object]]:
    transformed_feedback: list[dict[str, object]] = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        finding_id = str(finding.get("id") or "").strip()
        if not finding_id:
            continue
        feedback = feedback_map.get(finding_id)
        if not isinstance(feedback, dict):
            continue

        agreement = _derive_agreement(feedback)
        correctness: str | None = None
        if agreement == "Disagree":
            correctness = (
                _feedback_level_to_correctness(feedback.get("correctness"))
                or _feedback_level_to_correctness(feedback.get("feedbackType"))
                or _rating_to_corrected_level(feedback.get("rating"))
            )

        ai_risk = _normalize_risk_level(str(finding.get("Risk") or ""))
        comment_parts: list[str] = []
        if agreement == "Disagree" and correctness:
            comment_parts.append(
                f"AI returned {ai_risk}; reviewer rating maps to corrected level {correctness}"
            )

        reviewer_comment = str(feedback.get("comments") or "").strip()
        if reviewer_comment:
            comment_parts.append(reviewer_comment)

        transformed_feedback.append(
            {
                "Finding ID": finding_id,
                "Issue Name": str(finding.get("Issue name") or finding_id),
                "Agreement": agreement,
                "Correctness": correctness,
                "Comment": " ".join(comment_parts),
            }
        )

    return transformed_feedback


def _extract_json_object(raw_text: str) -> dict[str, object] | None:
    stripped = raw_text.strip()
    if not stripped:
        return None

    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].lstrip()

    try:
        parsed = json.loads(stripped)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    try:
        parsed = json.loads(stripped[start : end + 1])
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def _build_narrative_sections(raw_narrative: str) -> tuple[NarrativeSummarySections, bool]:
    parsed = _extract_json_object(raw_narrative) or {}
    section_values: dict[str, str] = {}
    narrative_valid = True

    for source_key, target_key in _REQUIRED_NARRATIVE_SECTIONS:
        value = parsed.get(source_key, "") if isinstance(parsed, dict) else ""
        normalized_value = str(value or "").strip()
        if not normalized_value:
            narrative_valid = False
        section_values[target_key] = normalized_value

    return NarrativeSummarySections(**section_values), narrative_valid


def _count_disagreements(user_feedback: list[dict[str, object]]) -> int:
    return sum(1 for item in user_feedback if str(item.get("Agreement") or "") == "Disagree")


def _count_high_risk_findings(findings: list[dict[str, object]]) -> int:
    high_risk_levels = {"Heavy", "IMMEDIATE ACTION"}
    return sum(
        1
        for finding in findings
        if _normalize_risk_level(str(finding.get("Risk") or "")) in high_risk_levels
    )


_RISK_LEVELS_ORDERED = ("IMMEDIATE ACTION", "Heavy", "Med", "Light", "Not Mentioned")


def _extract_component(component_and_grouping: str) -> str:
    """Return 'Rotor' or 'Stator' from a 'Component - Grouping' string, defaulting to 'Rotor'."""
    text = str(component_and_grouping or "").strip()
    lowered = text.lower()
    if "stator" in lowered:
        return "Stator"
    return "Rotor"


def _build_risk_counts(
    findings: list[dict],
    feedback_map: dict[str, dict],
) -> list[dict[str, object]]:
    """Compute per-(Component, Risk) counts AFTER applying user feedback corrections.

    For each finding:
    - If the reviewer disagreed and supplied a corrected level, use that level.
    - Otherwise use the AI-assigned Risk from the finding.
    Counts are grouped by component (Rotor | Stator) and risk level.
    """
    counts: dict[tuple[str, str], int] = {}

    for finding in findings:
        if not isinstance(finding, dict):
            continue

        component = _extract_component(
            str(finding.get("Component and Issue Grouping") or "")
        )
        ai_risk = _normalize_risk_level(str(finding.get("Risk") or ""))

        # Apply feedback correction if present
        finding_id = str(finding.get("id") or "").strip()
        effective_risk = ai_risk
        if finding_id:
            feedback = feedback_map.get(finding_id)
            if isinstance(feedback, dict) and _derive_agreement(feedback) == "Disagree":
                corrected = (
                    _feedback_level_to_correctness(feedback.get("correctness"))
                    or _feedback_level_to_correctness(feedback.get("feedbackType"))
                    or _rating_to_corrected_level(feedback.get("rating"))
                )
                if corrected:
                    effective_risk = corrected

        key = (component, effective_risk)
        counts[key] = counts.get(key, 0) + 1

    # Emit one entry per component per risk level (only levels with count > 0)
    result: list[dict[str, object]] = []
    for component in ("Rotor", "Stator"):
        for risk in _RISK_LEVELS_ORDERED:
            count = counts.get((component, risk), 0)
            if count > 0:
                result.append({"Component": component, "Risk": risk, "Count": count})
    return result


def _serialize_litellm_response_for_debug(response: object) -> str:
    if hasattr(response, "model_dump_json"):
        return str(response.model_dump_json(indent=2))
    if hasattr(response, "json"):
        return str(response.json())
    return str(response)


async def _call_litellm_with_json_retries(messages: list[dict[str, str]]) -> object:
    import litellm  # noqa: PLC0415

    total_attempts = _INVALID_JSON_MAX_RETRIES + 1
    last_response: object | None = None

    for attempt in range(1, total_attempts + 1):
        response = await litellm.acompletion(
            model=config.LITELLM_MODEL,
            api_base=config.LITELLM_API_BASE,
            api_key=config.LITELLM_API_KEY,
            messages=messages,
            max_tokens=_LITELLM_MAX_TOKENS,
            timeout=_LITELLM_TIMEOUT,
        )
        last_response = response

        if config.LITELLM_DEBUG:
            logger.info(
                "narrative: LiteLLM raw response (attempt %s/%s)\n%s",
                attempt,
                total_attempts,
                _serialize_litellm_response_for_debug(response),
            )

        narrative_text = response.choices[0].message.content or ""
        if _extract_json_object(narrative_text) is not None:
            return response

        if attempt < total_attempts:
            logger.warning(
                "narrative: invalid JSON response from LiteLLM on attempt %s/%s; retrying",
                attempt,
                total_attempts,
            )

    return last_response


@router.post("/run", response_model=RunResponse)
async def run(request_body: RunRequest) -> RunResponse:
    """Generate a narrative summary for an assessment.

    Fetches risk findings and feedback from the data-service, then calls
    LiteLLM directly to produce a structured narrative report.
    """
    serial_number = request_body.serial_number or request_body.esn

    logger.info(
        "narrative run requested",
        extra={
            "assessment_id": request_body.assessment_id,
            "esn": request_body.esn,
            "serial_number": serial_number,
            "persona": request_body.persona,
        },
    )

    if config.AGENT_SIMULATE_MODE:
        return await simulate_run(request_body)

    findings_result, rotor_prism_record, stator_prism_record = await asyncio.gather(
        _fetch_findings(request_body.assessment_id),
        _fetch_prism_component(serial_number, "ROTOR"),
        _fetch_prism_component(serial_number, "STATOR"),
    )
    findings, summary, feedback = findings_result
    prism_data = [record for record in (rotor_prism_record, stator_prism_record) if record is not None]

    risk_assessment_table = _build_risk_assessment_table(findings, summary)
    user_feedback = _build_user_feedback(findings, feedback)
    risk_counts = _build_risk_counts(findings, feedback)
    payload_json = json.dumps(
        {
            "Risk Assessment Table": risk_assessment_table,
            "User Feedback": user_feedback,
            "Risk Counts": risk_counts,
            "PRISM Data": prism_data,
        },
        default=str,
    )

    prompt = (
        f"Generate a narrative risk assessment report for assessment "
        f"'{request_body.assessment_id}', asset ESN '{request_body.esn}'. "
        f"Requesting persona: {request_body.persona}. "
        f"{len(risk_assessment_table['findings'])} risk finding(s) total, {len(user_feedback)} with reviewer feedback, "
        f"{len(risk_counts)} risk count entries (post-feedback corrections), "
        f"and {len(prism_data)} PRISM record(s). "
        f"Risk Assessment Table, User Feedback, Risk Counts, and PRISM Data: {payload_json}. "
        "Where reviewer feedback is present on a finding, incorporate it to calibrate "
        "confidence and acknowledge the reviewer's input in the narrative. "
        "For the Unit Summary risk count paragraph, use ONLY the numbers in the Risk Counts "
        "input — do NOT recount from the Risk Assessment Table. "
        "Use the PRISM data as an additional equipment-level predictive maintenance signal. "
        "Return only valid JSON with exactly these five top-level sections: "
        '"Unit Summary", "OPERATIONAL HISTORY", "MISC Details", '
        '"Overall Equipment Health Assessment", and "Recommendations". '
        "Do not return markdown fences or explanatory text outside the JSON object."
    )

    if not config.LITELLM_SSL_VERIFY:
        # LiteLLM/httpx can read SSL and CA bundle settings from process env.
        os.environ.pop("SSL_CERT_FILE", None)
        os.environ.pop("REQUESTS_CA_BUNDLE", None)
        os.environ.pop("CURL_CA_BUNDLE", None)
        os.environ["SSL_VERIFY"] = "False"

    import litellm  # noqa: PLC0415

    litellm.suppress_debug_info = not config.LITELLM_DEBUG
    if config.LITELLM_DEBUG:
        litellm.set_verbose = True
        logger.info("narrative: LiteLLM system prompt\n%s", SYSTEM_PROMPT)
        logger.info("narrative: LiteLLM user prompt\n%s", prompt)

    response = await _call_litellm_with_json_retries(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
    )

    narrative_text: str = response.choices[0].message.content or ""
    narrative_sections, narrative_valid = _build_narrative_sections(narrative_text)

    return RunResponse(
        serial_number=serial_number,
        narrative_valid=narrative_valid,
        findings_count=len(risk_assessment_table["findings"]),
        disagree_count=_count_disagreements(user_feedback),
        high_risk_count=_count_high_risk_findings(risk_assessment_table["findings"]),
        narrative_summary=narrative_sections,
    )
