"""Additional helper and branch tests for risk_assessment_creation_api."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from risk_evaluation.api.v1.endpoints import risk_assessment_creation_api as api
from risk_evaluation.schemas import RunRequest


def test_build_query_and_slug_helpers() -> None:
    req = RunRequest(query="  direct query ", esn="E1")
    assert api._build_query(req, "E1") == "direct query"

    fallback_req = RunRequest(query=None, assessment_id="a-1", persona="re")
    built = api._build_query(fallback_req, "E1")
    assert built is not None
    assert "assessment a-1" in built
    assert "RE" in built

    assert api._build_query(RunRequest(query=None), "") is None
    assert api._slugify("Rotor Section 1", "fallback") == "rotor-section-1"
    assert api._slugify("***", "fallback") == "fallback"


def test_risk_mapping_and_datasource_derivation() -> None:
    assert api._overall_risk_from_severity("immediate") == "Heavy"
    assert api._overall_risk_from_severity("heavy") == "Heavy"
    assert api._overall_risk_from_severity("medium") == "Medium"
    assert api._overall_risk_from_severity("other") == "Light"

    assert api._condition_risk_level("Heavy") == "High"
    assert api._condition_risk_level("Medium") == "Medium"
    assert api._condition_risk_level("Light") == "Low"
    assert api._condition_risk_level("Other") == "Low"

    assert api._derive_datasource("") == "Unknown"
    assert api._derive_datasource("ER-123") == "ER"
    assert api._derive_datasource("Field_Service_Report_x") == "FSR"
    assert api._derive_datasource("IBAT snapshot") == "IBAT"
    assert api._derive_datasource("Outage history") == "OUTAGE_HISTORY"
    assert api._derive_datasource("Reliability model ref") == "RELIABILITY_MODELS"
    assert api._derive_datasource("Custom Source") == "Custom"


def test_build_findings_and_categories() -> None:
    rows = {
        "data": [
            {
                "Evidence": "Leakage trace",
                "Severity Category": "3 - Heavy",
                "Source Reference": "ER-777",
                "Severity Rationale": "High risk",
                "Identified Component": "Stator",
            },
            {
                "result": "Fallback row",
                "severity": "2 - Medium",
                "Datasource": "Field_Service_Report_1",
            },
        ]
    }
    findings = api._build_findings(rows, component_type="Rotor")
    assert len(findings) == 2
    assert findings[0]["overallRisk"] == "Heavy"
    assert findings[0]["conditions"][0]["riskLevel"] == "High"
    assert findings[1]["component"] == "Rotor"

    categories = api._build_risk_categories(findings)
    assert len(categories) == 2
    assert list(categories.values())[0]["id"] == findings[0]["id"]

    passthrough = api._build_findings({"findings": [{"id": "x"}]}, None)
    assert passthrough == [{"id": "x"}]


def test_canonical_component_normalization() -> None:
    """_canonical_component maps LLM component variants to canonical names."""
    # Exact matches
    assert api._canonical_component("Stator") == "Stator"
    assert api._canonical_component("Rotor") == "Rotor"
    # Substring / variant matches
    assert api._canonical_component("Stator Winding") == "Stator"
    assert api._canonical_component("Generator Stator") == "Stator"
    assert api._canonical_component("Traction Motor Stator") == "Stator"
    assert api._canonical_component("Generator Rotor") == "Rotor"
    assert api._canonical_component("Generator Field") == "Rotor"   # Field → Rotor
    assert api._canonical_component("field winding") == "Rotor"
    # Case-insensitive
    assert api._canonical_component("STATOR INSULATION") == "Stator"
    assert api._canonical_component("rotor bar") == "Rotor"
    # Unknown → General
    assert api._canonical_component("General") == "General"
    assert api._canonical_component("Bearing") == "General"
    assert api._canonical_component("") == "General"


def test_infer_normalize_and_filter_resolution() -> None:
    # Explicit component fields — all normalised
    assert api._infer_component({"Identified Component": "Rotor"}, None) == "Rotor"
    assert api._infer_component({"Identified Component": "Stator Winding"}, None) == "Stator"
    assert api._infer_component({"Identified Component": "Generator Field"}, None) == "Rotor"
    # Component and Issue Grouping — prefix split then normalised
    assert api._infer_component({"Component and Issue Grouping": "Stator - Leakage"}, None) == "Stator"
    assert api._infer_component({"Component and Issue Grouping": "Stator Winding - Electrical Tests"}, None) == "Stator"
    assert api._infer_component({"Component and Issue Grouping": "Rotor"}, None) == "Rotor"  # no dash
    # Fallback to component_type (normalised)
    assert api._infer_component({}, "Stator") == "Stator"
    # Unknown component_type → General
    assert api._infer_component({}, "Generator") == "General"
    assert api._infer_component({}, None) == "General"

    parsed_results = [
        {
            "issue_id": "i-1",
            "summary": "Issue summary",
            "findings": [
                {
                    "Risk": "Immediate",
                    "Citation": "ER-1",
                    "justification": "because",
                    "Component and Issue Grouping": "Stator-Leak",
                }
            ],
        }
    ]
    rows, summary = api._normalize_llm_results(parsed_results, component_type="Rotor")
    assert len(rows) == 1
    assert summary.startswith("[i-1]")
    assert rows[0]["overallRisk"] == "Heavy"

    req = RunRequest(
        query="x",
        esn="E1",
        filters={"dataTypes": ["fsr"], "dateFrom": "2024-01-01", "dateTo": "2024-02-01"},
    )
    resolved = api._resolve_filters(req)
    assert resolved["data_types"] == ["fsr"]
    assert resolved["date_from"] == "2024-01-01"
    assert resolved["date_to"] == "2024-02-01"


@pytest.mark.asyncio
@patch("risk_evaluation.api.v1.endpoints.risk_assessment_creation_api.RiskAnalysisPersistence")
@patch("risk_evaluation.api.v1.endpoints.risk_assessment_creation_api.LLMAssistant")
@patch("risk_evaluation.api.v1.endpoints.risk_assessment_creation_api.RiskAssessmentCreationService")
async def test_orchestrated_workflow_path_success(
    mock_service_class: MagicMock,
    mock_llm_class: MagicMock,
    mock_persistence_class: MagicMock,
    client: Any,
) -> None:
    service = mock_service_class.return_value
    service.retrieve_heatmap_issues_from_databricks = AsyncMock(return_value=True)
    service.retrieve_ibat_from_databricks = AsyncMock(return_value=True)
    service.retrieve_evidence_from_databricks = AsyncMock(return_value=True)

    llm = mock_llm_class.return_value
    llm.run_parallel_llm_calls = AsyncMock(return_value=[{"issue_id": "i-1", "response": "{}", "error": None}])

    mock_persistence_class.parse_llm_results.return_value = [
        {
            "issue_id": "i-1",
            "summary": "ok",
            "findings": [
                {
                    "Risk": "3 - Heavy",
                    "Identified Component": "Stator",
                    "Source Reference": "ER-1",
                    "Severity Rationale": "critical",
                }
            ],
        }
    ]

    persistence = mock_persistence_class.return_value
    persistence.build_retrieval.return_value = {"i-1": {"fsr_chunks": [], "er_chunks": []}}
    persistence.cleanup.return_value = None

    response = await client.post(
        "/riskevaluationassistant/api/v1/risk-eval/run",
        json={"esn": "E1", "query": "q", "workflow_id": "wf-1", "assessment_id": "a-1", "persona": "RE"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["assessment_id"] == "a-1"
    assert body["retrieval"] == {"i-1": {"fsr_chunks": [], "er_chunks": []}}
    assert len(body["findings"]) == 1


@pytest.mark.asyncio
@patch("risk_evaluation.api.v1.endpoints.risk_assessment_creation_api.RiskAssessmentCreationService")
async def test_orchestrated_path_heatmap_missing_returns_404(
    mock_service_class: MagicMock,
    client: Any,
) -> None:
    service = mock_service_class.return_value
    service.retrieve_heatmap_issues_from_databricks = AsyncMock(return_value=False)

    response = await client.post(
        "/riskevaluationassistant/api/v1/risk-eval/run",
        json={"esn": "E1", "query": "q", "workflow_id": "wf-1", "assessment_id": "a-1"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
@patch("risk_evaluation.api.v1.endpoints.risk_assessment_creation_api.RiskAssessmentCreationService")
async def test_orchestrated_path_evidence_failure_returns_503(
    mock_service_class: MagicMock,
    client: Any,
) -> None:
    service = mock_service_class.return_value
    service.retrieve_heatmap_issues_from_databricks = AsyncMock(return_value=True)
    service.retrieve_ibat_from_databricks = AsyncMock(return_value=True)
    service.retrieve_evidence_from_databricks = AsyncMock(return_value=False)

    response = await client.post(
        "/riskevaluationassistant/api/v1/risk-eval/run",
        json={"esn": "E1", "query": "q", "workflow_id": "wf-1", "assessment_id": "a-1"},
    )

    assert response.status_code == 503
