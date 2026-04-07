"""Coverage tests for risk_evaluation.core.utils.utils legacy helpers."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


def test_legacy_repair_and_format_helpers() -> None:
    from risk_evaluation.core.utils.utils import _repair_json_string, format_assistant_response

    repaired = _repair_json_string('```json\n{"data": [{"Sl No. 1": "x"}]}\n```')
    assert '"Sl No.": 1' in repaired

    ok, parsed = format_assistant_response('{"data": [{"a": 1}]}')
    assert ok is True
    assert parsed["data"][0]["a"] == 1

    ok2, parsed2 = format_assistant_response("not-json")
    assert ok2 is False
    assert parsed2 is None

    ok3, parsed3 = format_assistant_response({"data": [{"a": 1}, "bad", 2]})
    assert ok3 is True
    assert isinstance(parsed3, dict)

    ok4, parsed4 = format_assistant_response({"result": "x"})
    assert ok4 is True
    assert parsed4["result"] == "x"

    ok5, parsed5 = format_assistant_response(42)
    assert ok5 is False
    assert parsed5 is None


@pytest.mark.asyncio
@patch("risk_evaluation.core.utils.utils.streamable_http_client")
@patch("risk_evaluation.core.utils.utils.ClientSession")
async def test_legacy_run_http_with_tool_success(
    mock_session_class: MagicMock,
    mock_http_client: MagicMock,
) -> None:
    mock_content = MagicMock()
    mock_content.type = "text"
    mock_content.text = '{"value": 1}'

    mock_result = MagicMock()
    mock_result.content = [mock_content]

    mock_session = AsyncMock()
    mock_session.initialize = AsyncMock()
    mock_session.call_tool = AsyncMock(return_value=mock_result)

    mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_class.return_value.__aexit__ = AsyncMock()

    mock_http_client.return_value.__aenter__ = AsyncMock(return_value=(AsyncMock(), AsyncMock(), None))
    mock_http_client.return_value.__aexit__ = AsyncMock()

    from risk_evaluation.core.utils.utils import run_http_with_tool

    result = await run_http_with_tool("tool", {"x": 1})
    assert result == {"value": 1}


@pytest.mark.asyncio
@patch("risk_evaluation.core.utils.utils.streamable_http_client")
@patch("risk_evaluation.core.utils.utils.ClientSession")
async def test_legacy_run_http_with_tool_non_text_and_empty(
    mock_session_class: MagicMock,
    mock_http_client: MagicMock,
) -> None:
    content_non_text = MagicMock()
    content_non_text.type = "image"

    mock_result_non_text = MagicMock()
    mock_result_non_text.content = [content_non_text]

    mock_result_empty = MagicMock()
    mock_result_empty.content = None

    mock_session = AsyncMock()
    mock_session.initialize = AsyncMock()
    mock_session.call_tool = AsyncMock(side_effect=[mock_result_non_text, mock_result_empty])

    mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_class.return_value.__aexit__ = AsyncMock()

    mock_http_client.return_value.__aenter__ = AsyncMock(return_value=(AsyncMock(), AsyncMock(), None))
    mock_http_client.return_value.__aexit__ = AsyncMock()

    from risk_evaluation.core.utils.utils import run_http_with_tool

    out1 = await run_http_with_tool("tool", {})
    out2 = await run_http_with_tool("tool", {})

    assert out1 == content_non_text
    assert out2 is None


@pytest.mark.asyncio
@patch("risk_evaluation.core.utils.utils.streamable_http_client")
@patch("risk_evaluation.core.utils.utils.ClientSession")
async def test_legacy_run_http_with_tool_content_without_type(
    mock_session_class: MagicMock,
    mock_http_client: MagicMock,
) -> None:
    content_without_type = MagicMock(spec=[])

    mock_result = MagicMock()
    mock_result.content = [content_without_type]

    mock_session = AsyncMock()
    mock_session.initialize = AsyncMock()
    mock_session.call_tool = AsyncMock(return_value=mock_result)

    mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_class.return_value.__aexit__ = AsyncMock()

    mock_http_client.return_value.__aenter__ = AsyncMock(return_value=(AsyncMock(), AsyncMock(), None))
    mock_http_client.return_value.__aexit__ = AsyncMock()

    from risk_evaluation.core.utils.utils import run_http_with_tool

    output = await run_http_with_tool("tool", {})
    assert output == content_without_type


@pytest.mark.asyncio
@patch("risk_evaluation.core.utils.utils.streamable_http_client")
async def test_legacy_run_http_with_tool_connection_error(mock_http_client: MagicMock) -> None:
    mock_http_client.return_value.__aenter__ = AsyncMock(side_effect=ConnectionError("down"))

    from risk_evaluation.core.utils.utils import run_http_with_tool

    with pytest.raises(ConnectionError):
        await run_http_with_tool("tool", {})


@pytest.mark.asyncio
async def test_legacy_run_http_with_tool_timeout_error(monkeypatch: Any) -> None:
    from risk_evaluation.core.utils import utils

    class _TimeoutClient:
        async def __aenter__(self) -> "_TimeoutClient":
            raise TimeoutError("slow")

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

    monkeypatch.setattr(utils.httpx, "AsyncClient", lambda **kwargs: _TimeoutClient())

    with pytest.raises(TimeoutError):
        await utils.run_http_with_tool("tool", {})


@pytest.mark.asyncio
async def test_legacy_run_http_with_tool_timeout_inside_streamable(monkeypatch: Any) -> None:
    from risk_evaluation.core.utils import utils

    class _StreamCtx:
        async def __aenter__(self) -> tuple[object, object, object]:
            raise TimeoutError("stream timeout")

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

    monkeypatch.setattr(utils, "streamable_http_client", lambda *args, **kwargs: _StreamCtx())

    with pytest.raises(TimeoutError):
        await utils.run_http_with_tool("tool", {})


@pytest.mark.asyncio
@patch("risk_evaluation.core.utils.utils.httpx.AsyncClient")
async def test_legacy_call_rest_api_success(mock_http_client_class: MagicMock) -> None:
    from risk_evaluation.core.utils import utils

    utils.config.DATA_SERVICE_URL = "http://svc"

    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {"ok": True}

    http_client = AsyncMock()
    http_client.request = AsyncMock(return_value=response)

    mock_http_client_class.return_value.__aenter__ = AsyncMock(return_value=http_client)
    mock_http_client_class.return_value.__aexit__ = AsyncMock()

    result = await utils.call_rest_api("/api/test", method="POST", body={"x": 1})
    assert result == {"ok": True}
    http_client.request.assert_awaited_once()


@pytest.mark.asyncio
async def test_legacy_call_rest_api_http_error(monkeypatch: Any) -> None:
    from risk_evaluation.core.utils import utils

    utils.config.DATA_SERVICE_URL = "http://svc"

    request = httpx.Request("GET", "http://svc/api/test")
    response = httpx.Response(500, request=request, text="boom")

    class _FailingClient:
        async def __aenter__(self) -> "_FailingClient":
            return self

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        async def request(self, method: str, url: str, params: object = None, json: object = None) -> object:
            raise httpx.HTTPStatusError("error", request=request, response=response)

    monkeypatch.setattr(utils.httpx, "AsyncClient", lambda **kwargs: _FailingClient())

    with pytest.raises(httpx.HTTPStatusError):
        await utils.call_rest_api("/api/test")


@pytest.mark.asyncio
async def test_legacy_call_rest_api_http_error_from_raise_for_status(monkeypatch: Any) -> None:
    from risk_evaluation.core.utils import utils

    utils.config.DATA_SERVICE_URL = "http://svc"
    request = httpx.Request("GET", "http://svc/api/test")
    response = httpx.Response(503, request=request, text="bad")

    class _Resp:
        def raise_for_status(self) -> None:
            raise httpx.HTTPStatusError("bad", request=request, response=response)

        def json(self) -> dict[str, str]:
            return {"never": "reached"}

    class _Client:
        async def __aenter__(self) -> "_Client":
            return self

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        async def request(self, method: str, url: str, params: object = None, json: object = None) -> object:
            return _Resp()

    monkeypatch.setattr(utils.httpx, "AsyncClient", lambda **kwargs: _Client())

    with pytest.raises(httpx.HTTPStatusError):
        await utils.call_rest_api("/api/test")


@pytest.mark.asyncio
async def test_legacy_call_rest_api_unexpected_error(monkeypatch: Any) -> None:
    from risk_evaluation.core.utils import utils

    utils.config.DATA_SERVICE_URL = "http://svc"

    class _Client:
        async def __aenter__(self) -> "_Client":
            return self

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        async def request(self, method: str, url: str, params: object = None, json: object = None) -> object:
            raise RuntimeError("unexpected")

    monkeypatch.setattr(utils.httpx, "AsyncClient", lambda **kwargs: _Client())

    with pytest.raises(RuntimeError):
        await utils.call_rest_api("/api/test")


def test_legacy_format_assistant_response_strict_false_and_outer_excepts(monkeypatch: Any) -> None:
    from risk_evaluation.core.utils import utils

    # json.loads(strict=True) fails due raw newline in string; strict=False succeeds.
    ok, parsed = utils.format_assistant_response('{"text": "line1\nline2"}')
    assert ok is True
    assert parsed["text"] == "line1\nline2"

    def _raise_json_error(_: str) -> str:
        raise json.JSONDecodeError("boom", "x", 0)

    def _raise_runtime(_: str) -> str:
        raise RuntimeError("boom")

    import json

    monkeypatch.setattr(utils, "_repair_json_string", _raise_json_error)
    ok2, parsed2 = utils.format_assistant_response("x")
    assert ok2 is False
    assert parsed2 is None

    monkeypatch.setattr(utils, "_repair_json_string", _raise_runtime)
    ok3, parsed3 = utils.format_assistant_response("x")
    assert ok3 is False
    assert parsed3 is None
