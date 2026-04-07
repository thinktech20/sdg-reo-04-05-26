"""Tests for middleware/auth.py and core/agent_factory.py branches."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_auth_local_mode_injects_anonymous_user(client: AsyncClient) -> None:
    """AUTH_LOCAL_MODE (which our test fixture sets) injects anonymous user context."""
    response = await client.post(
        "/questionansweragent/api/v1/chat",
        json={"prompt": "hello", "persona": "RE"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_bypasses_auth(client: AsyncClient) -> None:
    """/health must pass even without any auth headers."""
    response = await client.get("/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_missing_oidc_header_returns_401_when_not_local_mode() -> None:
    """When AUTH_LOCAL_MODE is off, missing X-Amzn-OIDC-Data → 401."""
    with patch.dict(os.environ, {"AUTH_LOCAL_MODE": "false"}):
        # Re-import config so it picks up the patched env
        import importlib  # noqa: PLC0415

        from question_answer import config as cfg  # noqa: PLC0415

        importlib.reload(cfg)
        # Temporarily flip the flag on the live module for this test
        original = cfg.AUTH_LOCAL_MODE
        cfg.AUTH_LOCAL_MODE = False
        try:
            from question_answer.main import app  # noqa: PLC0415

            app.state.litellm_model = MagicMock()
            app.state.boto_session = MagicMock()

            from httpx import ASGITransport  # noqa: PLC0415

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                response = await ac.post("/questionansweragent/api/v1/chat", json={"prompt": "hi", "persona": "RE"})
                assert response.status_code == 401
        finally:
            cfg.AUTH_LOCAL_MODE = original


@pytest.mark.asyncio
async def test_agent_factory_with_session_id_no_s3_local_mode() -> None:
    """build_agent with session_id wires S3SessionManager."""
    from unittest.mock import MagicMock, patch  # noqa: PLC0415

    mock_s3 = MagicMock()
    with patch(
        "question_answer.core.agent_factory.S3SessionManager",
        mock_s3,
        create=True,
    ):
        # Re-test the import path used inside the factory
        with patch.dict(os.environ, {"S3_LOCAL_MODE": "false"}):
            import importlib  # noqa: PLC0415

            from question_answer.core import agent_factory  # noqa: PLC0415

            importlib.reload(agent_factory)

            mock_model = MagicMock()
            mock_boto = MagicMock()

            with (
                patch("question_answer.core.agent_factory.Agent") as mock_agent_cls,
                patch("question_answer.core.agent_factory.S3SessionManager", mock_s3),
            ):
                mock_agent_cls.return_value = MagicMock()
                agent = agent_factory.build_agent(
                    model=mock_model,
                    boto_session=mock_boto,
                    persona="RE",
                    user_sso_id="test-user",
                    session_id="sess-abc",
                )
                assert agent is not None


@pytest.mark.asyncio
async def test_agent_factory_s3_local_mode_sets_env() -> None:
    """build_agent with S3_LOCAL_MODE=true sets AWS_ENDPOINT_URL_S3.

    The autouse mock_strands_imports fixture already mocks S3SessionManager
    in sys.modules, so no additional patching is required.
    """
    with patch.dict(
        os.environ,
        {"S3_LOCAL_MODE": "true", "S3_ENDPOINT_URL": "http://minio:9000"},
        clear=False,
    ):
        import importlib  # noqa: PLC0415

        from question_answer.core import agent_factory  # noqa: PLC0415

        importlib.reload(agent_factory)

        with patch("question_answer.core.agent_factory.Agent") as mock_agent_cls:
            mock_agent_cls.return_value = MagicMock()
            agent_factory.build_agent(
                model=MagicMock(),
                boto_session=MagicMock(),
                persona="RE",
                user_sso_id="test-user",
                session_id="sess-xyz",
            )
        assert os.environ.get("AWS_ENDPOINT_URL_S3") == "http://minio:9000"


@pytest.mark.asyncio
async def test_build_boto_session_local_mode() -> None:
    """build_boto_session in S3_LOCAL_MODE uses explicit credentials."""
    with patch.dict(
        os.environ,
        {
            "S3_LOCAL_MODE": "true",
            "S3_ACCESS_KEY_ID": "minioadmin",
            "S3_SECRET_ACCESS_KEY": "minioadmin",  # nosec B105
        },
    ):
        import importlib  # noqa: PLC0415

        from question_answer.core import agent_factory  # noqa: PLC0415

        importlib.reload(agent_factory)
        session = agent_factory.build_boto_session()
        assert session is not None


def test_extract_text_content_accepts_blocks_without_type() -> None:
    from question_answer.core.agent_factory import _extract_text_content

    message = {"content": [{"text": "Mocked agent response"}]}
    assert _extract_text_content(message) == "Mocked agent response"


def test_build_mcp_transport_uses_streamable_http_by_default() -> None:
    import importlib  # noqa: PLC0415

    from question_answer.core import agent_factory  # noqa: PLC0415

    importlib.reload(agent_factory)

    with patch("question_answer.core.agent_factory.config.MCP_SERVER_URL", "http://localhost:8001/mcp/"), \
         patch("question_answer.core.agent_factory.streamablehttp_client") as mock_streamable:
        transport = agent_factory._build_mcp_transport()
        transport()

    mock_streamable.assert_called_once_with("http://localhost:8001/mcp/")
