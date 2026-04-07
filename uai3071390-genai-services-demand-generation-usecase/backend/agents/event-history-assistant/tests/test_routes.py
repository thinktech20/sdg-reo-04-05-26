"""Tests for POST /eventhistoryassistant/api/v1/event-history/run."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

VALID_PAYLOAD = {
    "assessment_id": "assessment-003",
    "esn": "SN-12345",
    "persona": "RE",
    "event_data": [
        {"event_id": "EVT-001", "event_type": "forced_outage", "duration_hours": 48},
        {"event_id": "EVT-002", "event_type": "planned_maintenance", "duration_hours": 12},
    ],
}


@pytest.mark.asyncio
async def test_run_returns_200(client: AsyncClient) -> None:
    response = await client.post("/eventhistoryassistant/api/v1/event-history/run", json=VALID_PAYLOAD)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_run_response_shape(client: AsyncClient) -> None:
    response = await client.post("/eventhistoryassistant/api/v1/event-history/run", json=VALID_PAYLOAD)
    body = response.json()
    assert "status" in body
    assert "assessment_id" in body
    assert "message" in body


@pytest.mark.asyncio
async def test_run_echoes_assessment_id(client: AsyncClient) -> None:
    response = await client.post("/eventhistoryassistant/api/v1/event-history/run", json=VALID_PAYLOAD)
    assert response.json()["assessment_id"] == "assessment-003"


@pytest.mark.asyncio
async def test_run_status_accepted(client: AsyncClient) -> None:
    response = await client.post("/eventhistoryassistant/api/v1/event-history/run", json=VALID_PAYLOAD)
    assert response.json()["status"] == "accepted"


@pytest.mark.asyncio
async def test_run_oe_persona(client: AsyncClient) -> None:
    payload = {**VALID_PAYLOAD, "persona": "OE"}
    response = await client.post("/eventhistoryassistant/api/v1/event-history/run", json=payload)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_run_empty_events_accepted(client: AsyncClient) -> None:
    payload = {**VALID_PAYLOAD, "event_data": []}
    response = await client.post("/eventhistoryassistant/api/v1/event-history/run", json=payload)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_run_missing_assessment_id_returns_422(client: AsyncClient) -> None:
    payload = {
        "esn": "SN-12345",
        "persona": "RE",
        "event_data": [],
    }
    response = await client.post("/eventhistoryassistant/api/v1/event-history/run", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_run_missing_event_data_returns_422(client: AsyncClient) -> None:
    payload = {
        "assessment_id": "assessment-003",
        "esn": "SN-12345",
        "persona": "RE",
    }
    response = await client.post("/eventhistoryassistant/api/v1/event-history/run", json=payload)
    assert response.status_code == 422
