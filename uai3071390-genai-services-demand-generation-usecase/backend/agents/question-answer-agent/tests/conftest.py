"""Pytest fixtures for the question-answer-assistant test suite."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def mock_strands_imports() -> None:
    # Force local-dev auth mode so AuthMiddleware doesn't reject test requests.
    # Must be set before importing question_answer.config so config.AUTH_LOCAL_MODE=True.
    os.environ["AUTH_LOCAL_MODE"] = "true"

    # Import config here — after AUTH_LOCAL_MODE is set — so config.AUTH_LOCAL_MODE=True.
    # This also ensures question_answer.config is in sys.modules before the patch.dict
    # context below, so it persists across the context and importlib.reload() works in
    # tests that don't use the client fixture.
    import question_answer.config as _cfg  # noqa: PLC0415
    _cfg.AUTH_LOCAL_MODE = True

    """Mock all Strands SDK imports to avoid needing the actual SDK installed during test discovery."""
    # Mock the Agent class
    mock_agent_class = MagicMock()
    mock_agent_instance = MagicMock()
    mock_agent_instance.invoke_async = AsyncMock(
        return_value=MagicMock(message={"content": [{"text": "Mocked agent response"}]})
    )
    mock_agent_instance.cleanup = MagicMock()
    mock_agent_class.return_value = mock_agent_instance

    # Mock LiteLLMModel
    mock_litellm_model_class = MagicMock()
    mock_litellm_model_instance = MagicMock()
    mock_litellm_model_class.return_value = mock_litellm_model_instance

    # Mock S3SessionManager
    mock_s3_session_manager_class = MagicMock()

    # Mock tool decorator
    def mock_tool_decorator(func: object) -> object:
        return func

    # MCPClient mock — returns a list of named mock tools (our addition for MCP support)
    def _make_tool(name: str) -> MagicMock:
        t = MagicMock()
        t.name = name
        return t

    _all_tools = [
        _make_tool(n) for n in (
            "read_ibat", "read_prism", "query_fsr", "query_er",
            "read_risk_matrix", "retrieve_issue_data",
            "read_re_table", "read_re_report",
            "read_oe_table", "read_event_master", "read_oe_event_report",
        )
    ]
    mock_mcp_instance = MagicMock()
    mock_mcp_instance.list_tools_sync = MagicMock(return_value=_all_tools)
    mock_mcp_instance.__aenter__ = AsyncMock(return_value=mock_mcp_instance)
    mock_mcp_instance.__aexit__ = AsyncMock(return_value=None)
    mock_mcp_class = MagicMock(return_value=mock_mcp_instance)

    # Create the module mocks
    strands_mock = MagicMock()
    strands_mock.Agent = mock_agent_class
    strands_mock.tool = mock_tool_decorator

    strands_models_litellm_mock = MagicMock()
    strands_models_litellm_mock.LiteLLMModel = mock_litellm_model_class

    strands_session_s3_mock = MagicMock()
    strands_session_s3_mock.S3SessionManager = mock_s3_session_manager_class

    with patch.dict(
        "sys.modules",
        {
            "strands": strands_mock,
            "strands.models": MagicMock(),
            "strands.models.litellm": strands_models_litellm_mock,
            "strands.agent": MagicMock(),
            "strands.agent.conversation_manager": MagicMock(
                SlidingWindowConversationManager=MagicMock()
            ),
            "strands.tools": MagicMock(),
            "strands.tools.mcp": MagicMock(MCPClient=mock_mcp_class),
            "strands.types": MagicMock(),
            "strands.types.content": MagicMock(),
            "strands.session": MagicMock(),
            "strands.session.s3_session_manager": strands_session_s3_mock,
            "mcp.client.sse": MagicMock(),
            "mcp.client.streamable_http": MagicMock(),
        },
    ):
        yield


@pytest.fixture
async def client(mock_strands_imports: None) -> AsyncClient:  # type: ignore[override]
    """Test client with mocked Strands SDK dependencies."""
    # Import after mocking to ensure mocks are in place
    from question_answer.main import app  # noqa: PLC0415

    # Seed app.state with mock objects
    app.state.litellm_model = MagicMock()
    app.state.boto_session = MagicMock()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
