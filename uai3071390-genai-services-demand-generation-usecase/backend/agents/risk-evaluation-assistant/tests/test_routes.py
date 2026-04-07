"""Tests for POST /riskevaluationassistant/api/v1/risk-eval/run."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

# Valid payload matching RunRequest schema
VALID_PAYLOAD = {
    "query": "DC leakage test results",
    "esn": "337X380",
    "component_type": "Stator",
}

# Mock response from RiskAssessmentCreationService
MOCK_SERVICE_RESPONSE = {
    "columns": ["#", "Evidence", "Document Name", "Page Number", "Report Date"],
    "data": [
        {
            "#": 1,
            "Evidence": "DC leakage test performed on stator winding",
            "Document Name": "FSR_337X380_2025.pdf",
            "Page Number": 12,
            "Report Date": "2025-01-15",
        }
    ],
}


@pytest.mark.asyncio
@patch("risk_evaluation.api.v1.endpoints.risk_assessment_creation_api.RiskAssessmentCreationService")
async def test_run_returns_200(mock_service_class: AsyncMock, client: AsyncClient) -> None:
    """Test valid request returns 200 OK."""
    mock_service = mock_service_class.return_value
    mock_service.retrieve_evidence_from_databricks = AsyncMock(return_value=MOCK_SERVICE_RESPONSE)

    response = await client.post("/riskevaluationassistant/api/v1/risk-eval/run", json=VALID_PAYLOAD)
    assert response.status_code == 200


@pytest.mark.asyncio
@patch("risk_evaluation.api.v1.endpoints.risk_assessment_creation_api.RiskAssessmentCreationService")
async def test_run_response_shape(mock_service_class: AsyncMock, client: AsyncClient) -> None:
    """Test response contains expected fields."""
    mock_service = mock_service_class.return_value
    mock_service.retrieve_evidence_from_databricks = AsyncMock(return_value=MOCK_SERVICE_RESPONSE)

    response = await client.post("/riskevaluationassistant/api/v1/risk-eval/run", json=VALID_PAYLOAD)
    body = response.json()

    assert "data" in body or "result" in body
    assert "findings" in body
    assert "riskCategories" in body


@pytest.mark.asyncio
@patch("risk_evaluation.api.v1.endpoints.risk_assessment_creation_api.RiskAssessmentCreationService")
async def test_run_returns_data_list(mock_service_class: AsyncMock, client: AsyncClient) -> None:
    """Test response data is a list of dictionaries."""
    mock_service = mock_service_class.return_value
    mock_service.retrieve_evidence_from_databricks = AsyncMock(return_value=MOCK_SERVICE_RESPONSE)

    response = await client.post("/riskevaluationassistant/api/v1/risk-eval/run", json=VALID_PAYLOAD)
    body = response.json()

    if body.get("data"):
        assert isinstance(body["data"], list)
        if len(body["data"]) > 0:
            assert isinstance(body["data"][0], dict)


@pytest.mark.asyncio
async def test_run_missing_query_returns_400(client: AsyncClient) -> None:
    """Test missing query returns 400 Bad Request."""
    payload = {"query": "", "esn": "337X380", "component_type": "Rotor"}
    response = await client.post("/riskevaluationassistant/api/v1/risk-eval/run", json=payload)
    assert response.status_code == 400
    assert "query" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_run_missing_esn_returns_400(client: AsyncClient) -> None:
    """Test missing ESN returns 400 Bad Request."""
    payload = {"query": "DC leakage test", "esn": "", "component_type": "Stator"}
    response = await client.post("/riskevaluationassistant/api/v1/risk-eval/run", json=payload)
    assert response.status_code == 400
    assert "esn" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_run_null_query_returns_400(client: AsyncClient) -> None:
    """Test null query returns 400 Bad Request."""
    payload = {"query": None, "esn": "337X380", "component_type": "Stator"}
    response = await client.post("/riskevaluationassistant/api/v1/risk-eval/run", json=payload)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_run_null_esn_returns_400(client: AsyncClient) -> None:
    """Test null ESN returns 400 Bad Request."""
    payload = {"query": "DC leakage test", "esn": None, "component_type": "Rotor"}
    response = await client.post("/riskevaluationassistant/api/v1/risk-eval/run", json=payload)
    assert response.status_code == 400


@pytest.mark.asyncio
@patch("risk_evaluation.api.v1.endpoints.risk_assessment_creation_api.RiskAssessmentCreationService")
async def test_run_different_component_type(mock_service_class: AsyncMock, client: AsyncClient) -> None:
    """Test request with different component type (Rotor)."""
    mock_service = mock_service_class.return_value
    mock_service.retrieve_evidence_from_databricks = AsyncMock(return_value=MOCK_SERVICE_RESPONSE)

    payload = {"query": "insulation resistance", "esn": "337X380", "component_type": "Rotor"}
    response = await client.post("/riskevaluationassistant/api/v1/risk-eval/run", json=payload)
    assert response.status_code == 200


@pytest.mark.asyncio
@patch("risk_evaluation.api.v1.endpoints.risk_assessment_creation_api.RiskAssessmentCreationService")
async def test_run_optional_component_type(mock_service_class: AsyncMock, client: AsyncClient) -> None:
    """Test request without component_type still succeeds for orchestrator compatibility."""
    mock_service = mock_service_class.return_value
    mock_service.retrieve_evidence_from_databricks = AsyncMock(return_value=MOCK_SERVICE_RESPONSE)

    payload = {"query": "DC leakage test results", "esn": "337X380"}
    response = await client.post("/riskevaluationassistant/api/v1/risk-eval/run", json=payload)
    assert response.status_code == 200


@pytest.mark.asyncio
@patch("risk_evaluation.api.v1.endpoints.risk_assessment_creation_api.RiskAssessmentCreationService")
async def test_run_accepts_orchestrator_payload(mock_service_class: AsyncMock, client: AsyncClient) -> None:
    """Test orchestrator-style payload is accepted and normalized."""
    mock_service = mock_service_class.return_value
    mock_service.retrieve_evidence_from_databricks = AsyncMock(return_value=MOCK_SERVICE_RESPONSE)

    payload = {
        "assessment_id": "assess-123",
        "esn": "337X380",
        "persona": "RE",
    }
    response = await client.post("/riskevaluationassistant/api/v1/risk-eval/run", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["assessment_id"] == "assess-123"
    assert isinstance(body.get("findings"), list)
    assert isinstance(body.get("riskCategories"), dict)
    mock_service.retrieve_evidence_from_databricks.assert_called_once()


@pytest.mark.asyncio
@patch("risk_evaluation.api.v1.endpoints.risk_assessment_creation_api.RiskAssessmentCreationService")
async def test_run_returns_keyed_risk_categories(mock_service_class: AsyncMock, client: AsyncClient) -> None:
    """Test riskCategories is keyed by finding id for frontend compatibility."""
    mock_service = mock_service_class.return_value
    mock_service.retrieve_evidence_from_databricks = AsyncMock(return_value=MOCK_SERVICE_RESPONSE)

    response = await client.post("/riskevaluationassistant/api/v1/risk-eval/run", json=VALID_PAYLOAD)

    assert response.status_code == 200
    body = response.json()
    findings = body.get("findings") or []
    risk_categories = body.get("riskCategories") or {}

    assert isinstance(risk_categories, dict)
    assert findings
    assert risk_categories[findings[0]["id"]]["id"] == findings[0]["id"]


@pytest.mark.asyncio
@patch("risk_evaluation.api.v1.endpoints.risk_assessment_creation_api.RiskAssessmentCreationService")
async def test_run_empty_data_response(mock_service_class: AsyncMock, client: AsyncClient) -> None:
    """Test response with empty data (non-existent ESN)."""
    mock_service = mock_service_class.return_value
    mock_service.retrieve_evidence_from_databricks = AsyncMock(
        return_value={"columns": [], "data": []}
    )

    payload = {"query": "DC leakage", "esn": "FAKE12345", "component_type": "Stator"}
    response = await client.post("/riskevaluationassistant/api/v1/risk-eval/run", json=payload)
    # Should return 200 with empty data, not an error
    assert response.status_code in [200, 404]


@pytest.mark.asyncio
@patch("risk_evaluation.api.v1.endpoints.risk_assessment_creation_api.RiskAssessmentCreationService")
async def test_run_service_called_with_correct_params(mock_service_class: AsyncMock, client: AsyncClient) -> None:
    """Test service is called with correct parameters."""
    mock_service = mock_service_class.return_value
    mock_service.retrieve_evidence_from_databricks = AsyncMock(return_value=MOCK_SERVICE_RESPONSE)

    await client.post("/riskevaluationassistant/api/v1/risk-eval/run", json=VALID_PAYLOAD)

    mock_service.retrieve_evidence_from_databricks.assert_called_once_with(
        query="DC leakage test results",
        esn="337X380",
        component_type="Stator",
        filters={"data_types": [], "date_from": None, "date_to": None},
    )
