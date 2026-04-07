"""API v1 route handler for the Risk Evaluation Assistant."""

from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, status

router = APIRouter()

from risk_evaluation import config
from risk_evaluation.core.config.logger_config import get_logger
from risk_evaluation.core.services.risk_assessment_creation import RiskAssessmentCreationService
from risk_evaluation.core.utils.utils import format_assistant_response
from risk_evaluation.schemas import RunRequest, RunResponse
from risk_evaluation.core.services.llm_assistant import LLMAssistant
from risk_evaluation.core.services.risk_analysis_persistence import RiskAnalysisPersistence

# Initialize logger
logger = get_logger(__name__)


def _build_query(input_params: RunRequest, esn: str) -> str | None:
    if input_params.query is not None:
        query = input_params.query.strip()
        return query or None

    if input_params.assessment_id and esn:
        assessment_id = (input_params.assessment_id or "").strip() or "unknown-assessment"
        persona = (input_params.persona or "RE").strip().upper() or "RE"
        return (
            f"Generate a {persona} risk assessment for assessment {assessment_id} "
            f"and equipment ESN {esn}."
        )

    return None


def _slugify(value: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or fallback


def _overall_risk_from_severity(severity: str) -> str:
    severity_lower = severity.lower()
    if "immediate" in severity_lower or "heavy" in severity_lower:
        return "Heavy"
    if "medium" in severity_lower:
        return "Medium"
    return "Light"


def _condition_risk_level(overall_risk: str) -> str:
    return {
        "Heavy": "High",
        "Medium": "Medium",
        "Light": "Low",
    }.get(overall_risk, "Low")


def _derive_datasource(source_ref: str) -> str:
    """Derive a short datasource label from a Source Reference string.

    Examples:
      "Field_Service_Report_...pdf - Page 618.0" → "FSR"
      "ER-20241129-1045"                          → "ER"
      ""                                          → "Unknown"
    """
    if not source_ref:
        return "Unknown"
    upper = source_ref.upper()
    if upper.startswith("ER-") or upper.startswith("ER "):
        return "ER"
    if "FSR" in upper or "FIELD_SERVICE" in upper or "FIELD SERVICE" in upper:
        return "FSR"
    if "IBAT" in upper or "INSTALL-BASE" in upper:
        return "IBAT"
    if "OUTAGE" in upper:
        return "OUTAGE_HISTORY"
    if "RELIABILITY" in upper or "RELMODEL" in upper:
        return "RELIABILITY_MODELS"
    return source_ref.split()[0] if source_ref else "Unknown"


def _build_findings(parsed_data: dict[str, object], component_type: str | None) -> list[dict[str, object]]:
    existing_findings = parsed_data.get("findings")
    if isinstance(existing_findings, list):
        return [item for item in existing_findings if isinstance(item, dict)]

    data_rows = parsed_data.get("data")
    if not isinstance(data_rows, list):
        return []

    findings: list[dict[str, object]] = []
    for index, row in enumerate(data_rows, start=1):
        if not isinstance(row, dict):
            continue
        evidence = str(row.get("Evidence") or row.get("evidence") or row.get("result") or "").strip()
        severity = str(row.get("Severity Category") or row.get("severity") or "1 - Light").strip()
        # "Source Reference" is the canonical citation field in the schema (verbatim)
        source_ref = str(row.get("Source Reference") or row.get("Datasource") or row.get("dataSource") or "").strip()
        # Derive a short dataSource label from the Source Reference prefix
        datasource = _derive_datasource(source_ref)
        # "Severity Rationale" is the canonical justification field
        rationale = str(row.get("Severity Rationale") or row.get("Rationale") or row.get("justification") or evidence).strip()
        # "Identified Component" is the canonical component field
        component = str(row.get("Identified Component") or row.get("component") or component_type or "General").strip() or "General"
        category_id = _slugify(f"{component}-{index}", f"finding-{index}")
        overall_risk = _overall_risk_from_severity(severity)
        primary_citation = source_ref or f"Generated risk finding {index}"
        condition_id = f"{category_id}-condition-1"

        findings.append(
            {
                "id": category_id,
                "name": f"{component} Risk {index}",
                "component": component,
                "overallRisk": overall_risk,
                "processDocument": source_ref or "Generated from assistant evidence",
                "reliabilityModelRef": datasource,
                "description": evidence or f"Generated risk finding {index}",
                "conditions": [
                    {
                        "findingId": condition_id,
                        "id": condition_id,
                        "category": component,
                        "condition": evidence or f"Generated risk finding {index}",
                        "threshold": severity,
                        "actualValue": severity,
                        "riskLevel": _condition_risk_level(overall_risk),
                        "dataSource": datasource,
                        "justification": rationale or evidence or f"Generated risk finding {index}",
                        "primaryCitation": primary_citation,
                        "additionalCitations": [],
                        "status": "complete",
                    }
                ],
            }
        )

    return findings


def _build_risk_categories(findings: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    risk_categories: dict[str, dict[str, object]] = {}
    for index, finding in enumerate(findings, start=1):
        category_id = str(finding.get("id") or f"finding-{index}")
        risk_categories[category_id] = finding
    return risk_categories

_COMPONENT_CANONICAL: dict[str, str] = {
    "stator": "Stator",
    "rotor": "Rotor",
    "field": "Rotor",  # Generator Field = Rotor
}


def _canonical_component(raw: str) -> str:
    """Map a raw LLM component string to a canonical name (Stator / Rotor / General)."""
    lower = raw.lower()
    for token, canonical in _COMPONENT_CANONICAL.items():
        if token in lower:
            return canonical
    return "General"


def _infer_component(row: dict[str, Any], component_type: str | None) -> str:
    explicit = str(
        row.get("Identified Component")
        or row.get("component")
        or row.get("Component")
        or ""
    ).strip()
    if explicit:
        return _canonical_component(explicit)

    grouping = str(row.get("Component and Issue Grouping") or "").strip()
    if grouping:
        prefix = grouping.split("-", 1)[0].strip() if "-" in grouping else grouping
        return _canonical_component(prefix or component_type or "General")
    return _canonical_component(component_type or "General")


def _normalize_llm_results(
    parsed_results: list[dict[str, Any]],
    component_type: str | None,
) -> tuple[list[dict[str, Any]], str]:
    """Flatten parsed per-issue LLM results into row-level findings + summary."""
    rows: list[dict[str, Any]] = []
    summaries: list[str] = []

    for result in parsed_results:
        if not isinstance(result, dict):
            continue

        issue_id = str(result.get("issue_id") or "").strip()
        issue_summary = str(result.get("summary") or "").strip()
        if issue_summary:
            summaries.append(f"[{issue_id}] {issue_summary}" if issue_id else issue_summary)

        raw_findings = result.get("findings")
        if not isinstance(raw_findings, list):
            continue

        for idx, finding in enumerate(raw_findings, start=1):
            if not isinstance(finding, dict):
                continue

            normalized = dict(finding)
            component = _infer_component(normalized, component_type)
            risk_text = str(normalized.get("Risk") or normalized.get("riskLevel") or "Not Mentioned").strip()
            fallback_id = _slugify(f"{component}-{issue_id or 'finding'}-{idx}", f"finding-{len(rows) + 1}")

            normalized.setdefault("id", fallback_id)
            normalized.setdefault("component", component)
            normalized.setdefault("Severity Category", risk_text)
            normalized.setdefault("riskLevel", risk_text)
            normalized.setdefault("overallRisk", _overall_risk_from_severity(risk_text))
            normalized.setdefault("Severity Rationale", str(normalized.get("justification") or "").strip())
            normalized.setdefault(
                "Source Reference",
                str(normalized.get("Citation") or normalized.get("primaryCitation") or "").strip(),
            )

            rows.append(normalized)

    summary_text = "\n\n".join(summaries)
    return rows, summary_text

def _resolve_filters(input_params: RunRequest) -> dict[str, Any]:
    payload_filters = input_params.filters if isinstance(input_params.filters, dict) else {}
    data_types = input_params.data_types
    if not isinstance(data_types, list):
        candidate = payload_filters.get("data_types")
        if not isinstance(candidate, list):
            candidate = payload_filters.get("dataTypes")
        data_types = candidate if isinstance(candidate, list) else []
    date_from = input_params.date_from
    if date_from is None:
        date_from = payload_filters.get("date_from")
    if date_from is None:
        date_from = payload_filters.get("dateFrom")

    date_to = input_params.date_to
    if date_to is None:
        date_to = payload_filters.get("date_to")
    if date_to is None:
        date_to = payload_filters.get("dateTo")

    return {
        "data_types": data_types or [],
        "date_from": date_from,
        "date_to": date_to,
    }

def derive_datasources_from_list(data_types: list[str] | None) -> list[str]:
    """Derive datasource labels from a list of data type strings.

    Loops over each item in data_types, applies _derive_datasource to each,
    and returns a deduplicated list of datasource labels.

    Args:
        data_types: List of data type strings (e.g., ["Field_Service_Report", "ER-123"])

    Returns:
        List of unique datasource labels (e.g., ["FSR", "ER"])
    """
    if not data_types:
        return []

    datasources = []
    for data_type in data_types:
        derived = _derive_datasource(data_type)
        logger.info(f"Derived datasource '{derived}' from data type '{data_type}'")
        if derived not in datasources:
            datasources.append(derived)

    return datasources

@router.post("/run", response_model=RunResponse)
async def risk_assessment_creation(input_params: RunRequest) -> RunResponse:
    """
    Risk assessment creation API endpoint.
    Initiates RiskAssessmentCreationService, calls analyze_fsr_with_context,
    formats output, and invokes create_risk_assessment method.
    
    Args:
        input_params: RunRequest with query, esn, and component_type
        
    Returns:
        200 OK: Successfully created risk assessment with data
        400 Bad Request: Invalid input parameters
        404 Not Found: No data found for given ESN/query
        503 Service Unavailable: External service failure (Databricks, LLM)
    """
    logger.info(input_params)
    # Validate required inputs
    if not input_params.assessment_id or not input_params.assessment_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assessment ID is required and cannot be empty"
        )
    # Validate required inputs
    if not input_params.esn or not input_params.esn.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ESN is required and cannot be empty"
        )
    # Validate required inputs
    if not input_params.persona or not input_params.persona.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Persona is required and cannot be empty"
        )

    esn = input_params.esn.strip()
    assessment_id = (input_params.assessment_id or "").strip() or f"legacy-{esn}"
    persona = (input_params.persona or "RE").strip() or "RE"
    component_type = (input_params.component_type or "").strip() or None
    filters = _resolve_filters(input_params)        

    try:
        logger.info("DEBUG: Initiating risk assessment creation")
        logger.info(f"Input: assessment_id='{assessment_id}'")

        # Step 1: Instantiate the RiskAssessmentCreationService class
        service = RiskAssessmentCreationService()

        # Step 2: Retrieve heatmap issues from Databricks to build ESN-issue matrix
        success = await service.retrieve_heatmap_issues_from_databricks(
            esn=esn,
            persona=persona,
            component_type=input_params.component_type
        )
        if not success:
            logger.error("Failed to retrieve heatmap issues from Databricks for ESN=%s", esn)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No risk issue mappings found for ESN {esn}"
            )

        # Step 2.6: Derive datasources from input data_types
        datasources = derive_datasources_from_list(input_params.filters.get("data_types"))
        logger.info(f"Derived datasources: {datasources}")

        # Normalize datasource names to uppercase for consistent matching
        datasources_upper = [ds.upper() for ds in datasources]

        # Step 2.7: Retrieve IBAT equipment metadata if IBAT is in datasources
        if "IBAT" in datasources_upper:
            logger.info("IBAT datasource requested, retrieving IBAT data")
            ibat_success = await service.retrieve_ibat_from_databricks()
            if not ibat_success:
                logger.error("Failed to retrieve IBAT data from Databricks for ESN=%s", esn)
                raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No IBAT data found for ESN {esn}"
            )
        else:
            #TODO return response as empty response include this assumption in comment
            logger.error("IBAT should mandatorily be present in the datasources for ESN=%s", esn)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"IBAT should mandatorily be present in the datasources for ESN {esn}"
            )
        
        # Step 3: Retrieve evidence from Databricks using the populated ESN-issue matrix
        success = await service.retrieve_evidence_from_databricks(datasources=datasources)
        if not success:
            logger.error("Failed to retrieve evidence from Databricks for ESN=%s", esn)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to retrieve risk evidence for ESN {esn}",
            )

        # Run all LLM calls across parallel channels,
        # reading user_prompt_*.txt files from run_outputs/<esn>/
        llm_assistant = LLMAssistant()
        llm_results = await llm_assistant.run_parallel_llm_calls(esn=esn)
        logger.info("LLM processing complete: %d results", len(llm_results))

        # Parse each LLM response string into structured findings
        parsed_findings = RiskAnalysisPersistence.parse_llm_results(llm_results)
        logger.info("Parsed %d issue-level finding bundles from LLM results", len(parsed_findings))

        data_rows, summary = _normalize_llm_results(parsed_findings, component_type)
        findings = _build_findings({"data": data_rows}, component_type)
        risk_categories = _build_risk_categories(findings)
        retrieval: dict[str, Any] = {}

        # Persist findings + retrieval evidence to DynamoDB, then clean up artifacts
        persistence = RiskAnalysisPersistence(esn=esn)
        try:
            retrieval = persistence.build_retrieval()
            # Change in design to persist the data using Orchestrator service and not risk-eval
            #await persistence.persist(assessment_id=input_params.assessment_id, findings=parsed_findings)
        except Exception as e:
            logger.error(f"Failed to load the retrieval for risk analysis for assessment_id={assessment_id}: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to load the retrieval for risk analysis: {str(e)}"
            )
        finally:
            persistence.cleanup()

        return RunResponse(
            result=summary or None,
            data=data_rows,
            columns=list(data_rows[0].keys()) if data_rows else [],
            assessment_id=assessment_id,
            findings=findings,
            riskCategories=risk_categories,
            retrieval=retrieval,
            status="completed",
            message=summary or None,
        )


    except HTTPException as e:
        # Re-raise HTTPExceptions (400, 404, etc.)
        logger.error(f"HTTP error occurred: status_code={e.status_code}, detail={e.detail}")
        raise HTTPException(
            status_code=e.status_code,
            detail=e.detail
        )
    except ConnectionError as e:
        # Database/service connection issues
        logger.error(f"Connection error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to connect to data service: {str(e)}"
        )
    except TimeoutError as e:
        logger.error(f"Timeout error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Request timed out: {str(e)}"
        )
    except ValueError as e:
        # Invalid data/parsing errors
        logger.error(f"Value error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Data processing error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to create risk assessment: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to create risk assessment: {str(e)}"
        )