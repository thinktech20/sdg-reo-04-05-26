"""Pytest fixtures for the risk-evaluation-assistant test suite."""

from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# Mock pandas and numpy before any test imports happen (avoids numpy reload issue)
sys.modules["pandas"] = MagicMock()
sys.modules["numpy"] = MagicMock()


@pytest.fixture(autouse=True)
def mock_strands_imports() -> None:  # type: ignore[return]
    """Mock Strands SDK to avoid needing the actual SDK at test discovery time."""
    os.environ["AUTH_LOCAL_MODE"] = "true"
    os.environ["AGENT_SIMULATE_MODE"] = "false"

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

    # Mock MCP-related modules
    mcp_mock = MagicMock()
    mcp_client_mock = MagicMock()

    with patch.dict(
        "sys.modules",
        {
            "strands": strands_mock,
            "strands.models": MagicMock(),
            "strands.models.litellm": strands_models_litellm_mock,
            "mcp": mcp_mock,
            "mcp.client": mcp_client_mock,
            "mcp.client.streamable_http": MagicMock(),
        },
    ):
        yield


@pytest.fixture
async def client(mock_strands_imports: None) -> AsyncClient:  # type: ignore[override]
    """Test client with mocked Strands SDK dependencies."""
    from risk_evaluation.main import app  # noqa: PLC0415

    app.state.litellm_model = MagicMock()
    app.state.boto_session = MagicMock()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
