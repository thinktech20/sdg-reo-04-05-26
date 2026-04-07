"""Tests for GET /riskevaluationassistant/api/v1/risk-eval/healthcheck."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_status_200(client: AsyncClient) -> None:
    response = await client.get("/riskevaluationassistant/api/v1/risk-eval/healthcheck")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_response_body(client: AsyncClient) -> None:
    response = await client.get("/riskevaluationassistant/api/v1/risk-eval/healthcheck")
    body = response.json()
    assert body["status"] == "healthy"
    assert body["message"] == "Service is up and running"
