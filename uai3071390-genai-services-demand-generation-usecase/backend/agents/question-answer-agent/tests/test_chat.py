"""Tests for all chat endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

VALID_PAYLOAD = {
    "prompt": "What is the serial number history for SN-12345?",
    "persona": "RE",
}

ASSESSMENT_ID = "assess-001"


# ── POST /questionansweragent/api/v1/chat ─────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_returns_200(client: AsyncClient) -> None:
    response = await client.post("/questionansweragent/api/v1/chat", json=VALID_PAYLOAD)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_chat_response_shape(client: AsyncClient) -> None:
    response = await client.post("/questionansweragent/api/v1/chat", json=VALID_PAYLOAD)
    body = response.json()
    assert "reply" in body
    assert isinstance(body["reply"], str)


@pytest.mark.asyncio
async def test_chat_reply_not_empty(client: AsyncClient) -> None:
    response = await client.post("/questionansweragent/api/v1/chat", json=VALID_PAYLOAD)
    body = response.json()
    assert len(body["reply"]) > 0


@pytest.mark.asyncio
async def test_chat_with_session_id(client: AsyncClient) -> None:
    payload = {**VALID_PAYLOAD, "session_id": "test-session-123"}
    response = await client.post("/questionansweragent/api/v1/chat", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body.get("session_id") == "test-session-123"


@pytest.mark.asyncio
async def test_chat_oe_persona(client: AsyncClient) -> None:
    payload = {**VALID_PAYLOAD, "persona": "OE"}
    response = await client.post("/questionansweragent/api/v1/chat", json=payload)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_chat_missing_prompt_returns_422(client: AsyncClient) -> None:
    payload = {"persona": "RE"}
    response = await client.post("/questionansweragent/api/v1/chat", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_chat_invalid_persona_returns_422(client: AsyncClient) -> None:
    payload = {"prompt": "hello", "persona": "INVALID"}
    response = await client.post("/questionansweragent/api/v1/chat", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_chat_empty_prompt_accepted(client: AsyncClient) -> None:
    """Empty prompt is technically valid — agent uses conversation history."""
    payload = {"prompt": "", "persona": "RE"}
    response = await client.post("/questionansweragent/api/v1/chat", json=payload)
    assert response.status_code == 200


# ── POST /questionansweragent/api/v1/assessments/{id}/chat/reliability ────────

@pytest.mark.asyncio
async def test_assessment_chat_reliability_returns_200(client: AsyncClient) -> None:
    payload = {"message": "What is the stator risk?", "context": ASSESSMENT_ID}
    response = await client.post(f"/questionansweragent/api/v1/assessments/{ASSESSMENT_ID}/chat/reliability", json=payload)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_assessment_chat_reliability_response_shape(client: AsyncClient) -> None:
    payload = {"message": "What is the stator risk?", "context": ASSESSMENT_ID}
    response = await client.post(f"/questionansweragent/api/v1/assessments/{ASSESSMENT_ID}/chat/reliability", json=payload)
    body = response.json()
    assert "response" in body
    assert "chatHistory" in body
    assert body["response"]["agent"] == "reliability-agent"
    assert isinstance(body["chatHistory"], list)
    assert len(body["chatHistory"]) == 2
    assert body["chatHistory"][0]["role"] == "user"
    assert body["chatHistory"][1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_assessment_chat_reliability_reply_not_empty(client: AsyncClient) -> None:
    payload = {"message": "What is the stator risk?", "context": ASSESSMENT_ID}
    response = await client.post(f"/questionansweragent/api/v1/assessments/{ASSESSMENT_ID}/chat/reliability", json=payload)
    body = response.json()
    assert len(body["response"]["message"]) > 0


@pytest.mark.asyncio
async def test_assessment_chat_reliability_passes_serial_number_context_to_agent(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from question_answer.core import agent_factory  # noqa: PLC0415

    run_agent_mock = AsyncMock(return_value="Mocked agent response")
    monkeypatch.setattr(agent_factory, "run_agent", run_agent_mock)

    payload = {
        "message": "What is the stator risk?",
        "context": {
            "assessmentId": ASSESSMENT_ID,
            "serialNumber": "GEN98765",
        },
    }
    response = await client.post(f"/questionansweragent/api/v1/assessments/{ASSESSMENT_ID}/chat/reliability", json=payload)

    assert response.status_code == 200
    prompt = run_agent_mock.await_args.kwargs["prompt"]
    assert f"assessment_id: {ASSESSMENT_ID}" in prompt
    assert "serial_number: GEN98765" in prompt
    assert "User question: What is the stator risk?" in prompt


@pytest.mark.asyncio
async def test_assessment_chat_reliability_passes_assessment_id_without_serial_number(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from question_answer.core import agent_factory  # noqa: PLC0415

    run_agent_mock = AsyncMock(return_value="Mocked agent response")
    monkeypatch.setattr(agent_factory, "run_agent", run_agent_mock)

    payload = {
        "message": "Summarize the RE table feedback",
        "context": ASSESSMENT_ID,
    }
    response = await client.post(f"/questionansweragent/api/v1/assessments/{ASSESSMENT_ID}/chat/reliability", json=payload)

    assert response.status_code == 200
    prompt = run_agent_mock.await_args.kwargs["prompt"]
    assert prompt == "Summarize the RE table feedback"


# ── POST /questionansweragent/api/v1/assessments/{id}/chat/outage ─────────────

@pytest.mark.asyncio
async def test_assessment_chat_outage_returns_200(client: AsyncClient) -> None:
    payload = {"message": "What outage events occurred?", "context": ASSESSMENT_ID}
    response = await client.post(f"/questionansweragent/api/v1/assessments/{ASSESSMENT_ID}/chat/outage", json=payload)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_assessment_chat_outage_response_shape(client: AsyncClient) -> None:
    payload = {"message": "What outage events occurred?", "context": ASSESSMENT_ID}
    response = await client.post(f"/questionansweragent/api/v1/assessments/{ASSESSMENT_ID}/chat/outage", json=payload)
    body = response.json()
    assert "response" in body
    assert body["response"]["agent"] == "outage-agent"


@pytest.mark.asyncio
async def test_assessment_chat_invalid_id_returns_422(client: AsyncClient) -> None:
    payload = {"message": "hello", "context": ""}
    response = await client.post("/questionansweragent/api/v1/assessments/../admin/chat/reliability", json=payload)
    assert response.status_code in {404, 422}


@pytest.mark.asyncio
async def test_assessment_chat_missing_message_returns_422(client: AsyncClient) -> None:
    payload = {"context": ASSESSMENT_ID}
    response = await client.post(f"/questionansweragent/api/v1/assessments/{ASSESSMENT_ID}/chat/reliability", json=payload)
    assert response.status_code == 422
