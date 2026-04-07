"""Tests for health and ready probe endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


# ── /health ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_status_200(client: AsyncClient) -> None:
   response = await client.get("/health")
   assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_response_body(client: AsyncClient) -> None:
   response = await client.get("/health")
   body = response.json()
   assert body["status"] == "ok"
   assert body["service"] == "question-answer-agent"


# ── /questionansweragent/ and /questionansweragent/health ─────────────────────

@pytest.mark.asyncio
async def test_questionansweragent_root_returns_200(client: AsyncClient) -> None:
   response = await client.get("/questionansweragent/")
   assert response.status_code == 200
   body = response.json()
   assert body["status"] == "ok"


@pytest.mark.asyncio
async def test_questionansweragent_health_returns_200(client: AsyncClient) -> None:
   response = await client.get("/questionansweragent/health")
   assert response.status_code == 200
   body = response.json()
   assert body["status"] == "ok"
   assert body["service"] == "question-answer-agent"


# ── /ready ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ready_returns_200_when_data_service_healthy(client: AsyncClient) -> None:
   mock_response = AsyncMock()
   mock_response.raise_for_status = lambda: None
   with patch("question_answer.main.httpx.AsyncClient") as mock_httpx:
       mock_ctx = AsyncMock()
       mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
       mock_ctx.__aexit__ = AsyncMock(return_value=None)
       mock_ctx.get = AsyncMock(return_value=mock_response)
       mock_httpx.return_value = mock_ctx
       response = await client.get("/ready")
   assert response.status_code == 200
   body = response.json()
   assert body["status"] == "ready"
   assert body["service"] == "question-answer-agent"


@pytest.mark.asyncio
async def test_ready_returns_503_when_data_service_down(client: AsyncClient) -> None:
   with patch("question_answer.main.httpx.AsyncClient") as mock_httpx:
       mock_ctx = AsyncMock()
       mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
       mock_ctx.__aexit__ = AsyncMock(return_value=None)
       mock_ctx.get = AsyncMock(side_effect=ConnectionError("refused"))
       mock_httpx.return_value = mock_ctx
       response = await client.get("/ready")
   assert response.status_code == 503


# ── /questionansweragent/ready ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_questionansweragent_ready_returns_200(client: AsyncClient) -> None:
   mock_response = AsyncMock()
   mock_response.raise_for_status = lambda: None
   with patch("question_answer.main.httpx.AsyncClient") as mock_httpx:
       mock_ctx = AsyncMock()
       mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
       mock_ctx.__aexit__ = AsyncMock(return_value=None)
       mock_ctx.get = AsyncMock(return_value=mock_response)
       mock_httpx.return_value = mock_ctx
       response = await client.get("/questionansweragent/ready")
   assert response.status_code == 200
   body = response.json()
   assert body["status"] == "ready"
