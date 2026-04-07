"""Tests for POST /summarizationassistant/api/v1/narrative/run."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import AsyncClient

VALID_PAYLOAD = {
    "assessment_id": "assessment-002",
    "esn": "SN-12345",
    "persona": "RE",
}


@pytest.mark.asyncio
async def test_run_returns_200(client: AsyncClient) -> None:
    response = await client.post("/summarizationassistant/api/v1/narrative/run", json=VALID_PAYLOAD)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_run_response_shape(client: AsyncClient) -> None:
    response = await client.post("/summarizationassistant/api/v1/narrative/run", json=VALID_PAYLOAD)
    body = response.json()
    assert "status" in body
    assert "assessment_id" in body
    assert "message" in body
    assert "narrative_summary" in body


@pytest.mark.asyncio
async def test_run_echoes_assessment_id(client: AsyncClient) -> None:
    response = await client.post("/summarizationassistant/api/v1/narrative/run", json=VALID_PAYLOAD)
    assert response.json()["assessment_id"] == "assessment-002"


@pytest.mark.asyncio
async def test_run_status_accepted(client: AsyncClient) -> None:
    response = await client.post("/summarizationassistant/api/v1/narrative/run", json=VALID_PAYLOAD)
    assert response.json()["status"] == "accepted"


@pytest.mark.asyncio
async def test_run_oe_persona(client: AsyncClient) -> None:
    payload = {**VALID_PAYLOAD, "persona": "OE"}
    response = await client.post("/summarizationassistant/api/v1/narrative/run", json=payload)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_run_missing_assessment_id_returns_422(client: AsyncClient) -> None:
    payload = {
        "esn": "SN-12345",
        "persona": "RE",
    }
    response = await client.post("/summarizationassistant/api/v1/narrative/run", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_run_narrative_summary_field_present(client: AsyncClient) -> None:
    """Simulate mode should return a populated narrative_summary field."""
    response = await client.post("/summarizationassistant/api/v1/narrative/run", json=VALID_PAYLOAD)
    body = response.json()
    assert "narrative_summary" in body
    assert body["narrative_summary"]


@pytest.mark.asyncio
async def test_run_root_alias_returns_200(client: AsyncClient) -> None:
    response = await client.post("/api/v1/narrative/run", json=VALID_PAYLOAD)
    assert response.status_code == 200


def test_normalize_prism_row_applies_start_date_rule() -> None:
    from narrative_summary.api.v1.endpoints import _normalize_prism_row

    rotor_result = _normalize_prism_row(
        {
            "TURBINE_NUMBER": "290T484",
            "ADJ_RISK": 0.5662,
            "MODEL_DESC": "7FH2 Generator Rotor Rewind",
            "GEN_COD": "2002-06-20",
            "RISK_PROFILE": "Rotor High Risk",
            "LAST_REWIND": None,
        },
        "290T484",
    )
    stator_result = _normalize_prism_row(
        {
            "TURBINE_NUMBER": "290T484",
            "ADJ_RISK": 0.4123,
            "MODEL_DESC": "7FH2 Generator Stator Rewind",
            "GEN_COD": "2002-06-20",
            "RISK_PROFILE": "Stator Medium Risk",
            "LAST_REWIND": "2015-03-11",
        },
        "290T484",
    )

    assert rotor_result["ADJ_RISK"] == 0.5662
    assert stator_result["ADJ_RISK"] == 0.4123
    assert rotor_result["GEN_COD"] == "2002-06-20"
    assert stator_result["GEN_COD"] == "2002-06-20"
    assert rotor_result["RISK_MODEL_START_DATE"] == "2002-06-20"
    assert rotor_result["RISK_MODEL_START_REASON"] == "GEN_COD no rewind on record"
    assert stator_result["RISK_MODEL_START_DATE"] == "2015-03-11"
    assert stator_result["RISK_MODEL_START_REASON"] == "LAST_REWIND used as risk model start date"


def test_build_risk_assessment_table_includes_finding_id() -> None:
    from narrative_summary.api.v1.endpoints import _build_risk_assessment_table

    result = _build_risk_assessment_table(
        [
            {
                "id": "finding_123",
                "Issue name": "Rotor Vibration Trend",
                "Component and Issue Grouping": "Rotor - Vibration",
                "Condition": "trend up",
                "Threshold": "fleet median",
                "Actual Value": "+14%",
                "Risk": "Medium",
                "Evidence": "evidence",
                "Citation": "citation",
                "justification": "because",
            }
        ],
        "summary",
    )

    assert result["findings"][0]["Finding ID"] == "finding_123"


def test_build_user_feedback_includes_finding_id_and_corrected_level() -> None:
    from narrative_summary.api.v1.endpoints import _build_user_feedback

    result = _build_user_feedback(
        [
            {
                "id": "finding_123",
                "Issue name": "Rotor Vibration Trend",
                "Risk": "Medium",
            }
        ],
        {
            "finding_123": {
                "feedback": "down",
                "rating": 4,
                "comments": "Reviewer says this should be heavy.",
            }
        },
    )

    assert result[0]["Finding ID"] == "finding_123"
    assert result[0]["Agreement"] == "Disagree"
    assert result[0]["Correctness"] == "Heavy"
    assert "Reviewer says this should be heavy." in result[0]["Comment"]


def test_build_user_feedback_uses_feedback_type_correction() -> None:
    from narrative_summary.api.v1.endpoints import _build_user_feedback

    result = _build_user_feedback(
        [
            {
                "id": "finding_456",
                "Issue name": "Stator winding insulation",
                "Risk": "Med",
            }
        ],
        {
            "finding_456": {
                "feedback": "down",
                "feedbackType": "High",
                "comments": "Should be escalated.",
            }
        },
    )

    assert result[0]["Finding ID"] == "finding_456"
    assert result[0]["Agreement"] == "Disagree"
    assert result[0]["Correctness"] == "Heavy"
    assert "Should be escalated." in result[0]["Comment"]


def test_build_risk_counts_applies_feedback_corrections() -> None:
    from narrative_summary.api.v1.endpoints import _build_risk_counts

    findings = [
        {
            "id": "finding_rotor_1",
            "Component and Issue Grouping": "Rotor - Vibration",
            "Risk": "Med",
        },
        {
            "id": "finding_stator_1",
            "Component and Issue Grouping": "Stator - Electrical Tests",
            "Risk": "Light",
        },
        {
            "id": "finding_stator_2",
            "Component and Issue Grouping": "Stator - Core",
            "Risk": "Heavy",
        },
    ]
    feedback_map = {
        "finding_rotor_1": {
            "feedback": "down",
            "feedbackType": "High",
        },
        "finding_stator_1": {
            "feedback": "up",
        },
    }

    counts = _build_risk_counts(findings, feedback_map)

    assert {"Component": "Rotor", "Risk": "Heavy", "Count": 1} in counts
    assert {"Component": "Stator", "Risk": "Heavy", "Count": 1} in counts
    assert {"Component": "Stator", "Risk": "Light", "Count": 1} in counts


def test_build_risk_counts_defaults_to_not_mentioned() -> None:
    from narrative_summary.api.v1.endpoints import _build_risk_counts

    findings = [
        {
            "id": "finding_rotor_2",
            "Component and Issue Grouping": "Rotor - Other",
            "Risk": "",
        }
    ]

    counts = _build_risk_counts(findings, {})

    assert counts == [{"Component": "Rotor", "Risk": "Not Mentioned", "Count": 1}]


@pytest.mark.asyncio
async def test_fetch_prism_handles_client_init_failure() -> None:
    from narrative_summary.api.v1.endpoints import _fetch_prism_component

    with patch(
        "narrative_summary.api.v1.endpoints.httpx.AsyncClient",
        side_effect=RuntimeError("client init failed"),
    ):
        result = await _fetch_prism_component("290T484", "ROTOR")

    assert result is None


@pytest.mark.asyncio
async def test_fetch_prism_calls_dataservices_route() -> None:
    from narrative_summary.api.v1.endpoints import _fetch_prism_component

    response = SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {
            "data": [
                {
                    "TURBINE_NUMBER": "290T484",
                    "ADJ_RISK": 0.5662,
                    "MODEL_DESC": "7FH2 Generator Rotor Rewind",
                    "GEN_COD": "2002-06-20",
                    "RISK_PROFILE": "Rotor High Risk",
                    "LAST_REWIND": None,
                }
            ]
        },
    )
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=response)
    mock_async_client = AsyncMock()
    mock_async_client.__aenter__.return_value = mock_client
    mock_async_client.__aexit__.return_value = None

    with patch(
        "narrative_summary.api.v1.endpoints.httpx.AsyncClient",
        return_value=mock_async_client,
    ):
        result = await _fetch_prism_component("290T484", "ROTOR")

    assert result is not None
    assert mock_client.post.await_args.args[0].endswith("/dataservices/api/v1/prism/read")


def _mock_litellm_response(content: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content),
            )
        ]
    )


@pytest.mark.asyncio
async def test_call_litellm_retries_once_on_invalid_json() -> None:
    from narrative_summary.api.v1.endpoints import _call_litellm_with_json_retries

    litellm_mock = SimpleNamespace(
        acompletion=AsyncMock(
            side_effect=[
                _mock_litellm_response("not-json"),
                _mock_litellm_response('{"Unit Summary":"ok"}'),
            ]
        )
    )

    with patch.dict("sys.modules", {"litellm": litellm_mock}):
        response = await _call_litellm_with_json_retries(
            [{"role": "user", "content": "test"}]
        )

    assert response.choices[0].message.content == '{"Unit Summary":"ok"}'
    assert litellm_mock.acompletion.await_count == 2


@pytest.mark.asyncio
async def test_call_litellm_enforces_max_tokens_and_timeout() -> None:
    from narrative_summary.api.v1.endpoints import _call_litellm_with_json_retries

    litellm_mock = SimpleNamespace(
        acompletion=AsyncMock(return_value=_mock_litellm_response('{"Unit Summary":"ok"}'))
    )

    with patch.dict("sys.modules", {"litellm": litellm_mock}):
        await _call_litellm_with_json_retries([{"role": "user", "content": "test"}])

    kwargs = litellm_mock.acompletion.await_args.kwargs
    assert kwargs["max_tokens"] == 12000
    assert isinstance(kwargs["timeout"], httpx.Timeout)
    assert kwargs["timeout"].connect == 30.0
    assert kwargs["timeout"].read == 180.0
