"""Pytest fixtures for the narrative-summary-assistant test suite."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def mock_strands_imports() -> None:  # type: ignore[return]
    """Mock Strands SDK to avoid needing the actual SDK at test discovery time."""
    os.environ["AUTH_LOCAL_MODE"] = "true"
    os.environ["AGENT_SIMULATE_MODE"] = "true"

    mock_agent_instance = MagicMock()
    mock_agent_instance.invoke_async = AsyncMock(
        return_value=MagicMock(message={"content": [{"text": "Mocked agent response"}]})
    )
    mock_agent_instance.cleanup = MagicMock()
    mock_agent_class = MagicMock(return_value=mock_agent_instance)

    mock_litellm_model_class = MagicMock(return_value=MagicMock())

    def mock_tool_decorator(func: object) -> object:
        return func

    strands_mock = MagicMock()
    strands_mock.Agent = mock_agent_class
    strands_mock.tool = mock_tool_decorator

    strands_models_litellm_mock = MagicMock()
    strands_models_litellm_mock.LiteLLMModel = mock_litellm_model_class

    with patch.dict(
        "sys.modules",
        {
            "strands": strands_mock,
            "strands.models": MagicMock(),
            "strands.models.litellm": strands_models_litellm_mock,
        },
    ):
        yield


@pytest.fixture
async def client(mock_strands_imports: None) -> AsyncClient:  # type: ignore[override]
    """Test client with mocked Strands SDK dependencies."""
    from narrative_summary.main import app  # noqa: PLC0415

    app.state.litellm_model = MagicMock()
    app.state.boto_session = MagicMock()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
