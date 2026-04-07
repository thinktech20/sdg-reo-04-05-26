"""Unit tests for NakshaClient."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import data_service.config as cfg
from data_service.client import DatabricksClient, NakshaClient, NakshaError

# ── Mock-mode behaviour ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_execute_sql_mock_returns_fixture() -> None:
    """With USE_MOCK=true, execute_sql returns mock_data without any HTTP call."""
    client = NakshaClient()
    fixture = [{"id": 1, "value": "test"}]
    result = await client.execute_sql("SELECT 1", mock_data=fixture)
    assert result == fixture


@pytest.mark.asyncio
async def test_execute_sql_mock_empty_when_no_fixture() -> None:
    client = NakshaClient()
    result = await client.execute_sql("SELECT 1")
    assert result == []


# ── Live-mode: missing NAKSHA_API_URL ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_execute_sql_live_no_url_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cfg, "USE_MOCK", False)
    monkeypatch.setattr(cfg, "NAKSHA_API_URL", "")
    client = NakshaClient()
    with pytest.raises(NakshaError, match="NAKSHA_API_URL"):
        await client.execute_sql("SELECT 1")


# ── Response parsing ───────────────────────────────────────────────────────────


def test_parse_valid_response() -> None:
    data = [{"col": "val"}]
    body = {"choices": [{"message": {"content": json.dumps({"data": data})}}]}
    assert NakshaClient._parse(body) == data


def test_parse_empty_data_list() -> None:
    body = {"choices": [{"message": {"content": json.dumps({"data": []})}}]}
    assert NakshaClient._parse(body) == []


def test_parse_missing_data_key() -> None:
    body = {"choices": [{"message": {"content": json.dumps({})}}]}
    assert NakshaClient._parse(body) == []


def test_parse_invalid_json_raises() -> None:
    body = {"choices": [{"message": {"content": "not-json"}}]}
    with pytest.raises(NakshaError, match="Unparseable"):
        NakshaClient._parse(body)


def test_parse_missing_choices_raises() -> None:
    with pytest.raises(NakshaError, match="Unparseable"):
        NakshaClient._parse({})


def test_infer_table_status_success_without_rows_is_empty_or_filtered() -> None:
    parsed = {"status": "success", "message": "cannot run this query"}
    table_status = NakshaClient._infer_table_status(parsed, rows=[], naksha_status="success")
    assert table_status == "empty_or_filtered"


def test_infer_table_status_error_without_rows_is_unavailable() -> None:
    parsed = {"status": "error", "message": "table not available"}
    table_status = NakshaClient._infer_table_status(parsed, rows=[], naksha_status="error")
    assert table_status == "unavailable"


# ── Live-mode: HTTP error ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_execute_sql_falls_back_to_databricks_on_naksha_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx  # noqa: PLC0415

    monkeypatch.setattr(cfg, "USE_MOCK", False)
    monkeypatch.setattr(cfg, "NAKSHA_API_URL", "http://naksha.internal")
    monkeypatch.setattr(cfg, "NAKSHA_MAX_RETRIES", 1)

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.HTTPStatusError("500", request=MagicMock(), response=mock_response)
        with patch.object(DatabricksClient, "query_direct_sql_async", new_callable=AsyncMock) as mock_fallback:
            mock_fallback.return_value = [{"serial_number": "SN-001"}]
            client = NakshaClient()
            rows = await client.execute_sql("SELECT 1")

    assert rows == [{"serial_number": "SN-001"}]
    assert client.get_last_query_markers()["naksha_status"] == "fallback_databricks"


@pytest.mark.asyncio
async def test_execute_sql_falls_back_to_databricks_on_naksha_429(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx  # noqa: PLC0415

    monkeypatch.setattr(cfg, "USE_MOCK", False)
    monkeypatch.setattr(cfg, "NAKSHA_API_URL", "http://naksha.internal")
    monkeypatch.setattr(cfg, "NAKSHA_MAX_RETRIES", 1)

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 429
    mock_response.text = "Too Many Requests"

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.HTTPStatusError("429", request=MagicMock(), response=mock_response)
        with patch.object(DatabricksClient, "query_direct_sql_async", new_callable=AsyncMock) as mock_fallback:
            mock_fallback.return_value = [{"serial_number": "SN-429"}]
            client = NakshaClient()
            rows = await client.execute_sql("SELECT 1")

    assert rows == [{"serial_number": "SN-429"}]
    assert client.get_last_query_markers()["naksha_status"] == "fallback_databricks"


@pytest.mark.asyncio
async def test_execute_sql_falls_back_on_request_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx  # noqa: PLC0415

    monkeypatch.setattr(cfg, "USE_MOCK", False)
    monkeypatch.setattr(cfg, "NAKSHA_API_URL", "http://naksha.internal")
    monkeypatch.setattr(cfg, "NAKSHA_MAX_RETRIES", 1)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.RequestError("connection refused")
        with patch.object(DatabricksClient, "query_direct_sql_async", new_callable=AsyncMock) as mock_fallback:
            mock_fallback.return_value = [{"col": "val"}]
            client = NakshaClient()
            rows = await client.execute_sql("SELECT 1")

    assert rows == [{"col": "val"}]


@pytest.mark.asyncio
async def test_execute_sql_successful_response(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx  # noqa: PLC0415

    monkeypatch.setattr(cfg, "USE_MOCK", False)
    monkeypatch.setattr(cfg, "NAKSHA_API_URL", "http://naksha.internal")
    monkeypatch.setattr(cfg, "NAKSHA_MAX_RETRIES", 1)

    body = {
        "type": "answer",
        "answer": "ok",
        "sql": "SELECT 1",
        "result_preview": {
            "columns": ["serial_number"],
            "rows": [["SN-001"]],
            "row_count": 1,
        },
    }

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = body
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        client = NakshaClient()
        rows = await client.execute_sql("SELECT 1")

    assert rows == [{"serial_number": "SN-001"}]
    assert client.get_last_query_markers()["naksha_status"] == "success"
    assert client.get_last_query_markers()["table_status"] == "available"


@pytest.mark.asyncio
async def test_execute_sql_falls_back_when_parsed_status_is_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx  # noqa: PLC0415

    monkeypatch.setattr(cfg, "USE_MOCK", False)
    monkeypatch.setattr(cfg, "NAKSHA_API_URL", "http://naksha.internal")
    monkeypatch.setattr(cfg, "NAKSHA_MAX_RETRIES", 1)

    body = {"type": "error", "error": "table not found"}

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = body
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with patch.object(DatabricksClient, "query_direct_sql_async", new_callable=AsyncMock) as mock_fallback:
            mock_fallback.return_value = []
            client = NakshaClient()
            rows = await client.execute_sql("SELECT 1")

    assert rows == []


@pytest.mark.asyncio
async def test_execute_sql_polls_running_response(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx  # noqa: PLC0415

    monkeypatch.setattr(cfg, "USE_MOCK", False)
    monkeypatch.setattr(cfg, "NAKSHA_API_URL", "http://naksha.internal")
    monkeypatch.setattr(cfg, "NAKSHA_MAX_RETRIES", 1)
    monkeypatch.setattr(cfg, "NAKSHA_MAX_POLLS", 2)
    monkeypatch.setattr(cfg, "NAKSHA_POLL_INTERVAL_SECONDS", 0)

    running_resp = MagicMock(spec=httpx.Response)
    running_resp.status_code = 200
    running_resp.json.return_value = {
        "type": "running",
        "space": {"id": "space-1"},
        "genie": {"conversation_id": "conv-1", "message_id": "msg-1"},
        "chosen_tag": "sql",
        "tables_selected": ["event"],
    }
    running_resp.raise_for_status = MagicMock()

    answer_resp = MagicMock(spec=httpx.Response)
    answer_resp.status_code = 200
    answer_resp.json.return_value = {
        "type": "answer",
        "answer": "ok",
        "result_preview": {"columns": ["serial_number"], "rows": [["SN-002"]]},
    }
    answer_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [running_resp, answer_resp]
        client = NakshaClient()
        rows = await client.execute_sql("SELECT 1")

    assert rows == [{"serial_number": "SN-002"}]


@pytest.mark.asyncio
async def test_execute_sql_falls_back_on_payload_429(monkeypatch: pytest.MonkeyPatch) -> None:
    """Naksha sometimes returns 429 in the JSON body with HTTP 200."""
    import httpx  # noqa: PLC0415

    monkeypatch.setattr(cfg, "USE_MOCK", False)
    monkeypatch.setattr(cfg, "NAKSHA_API_URL", "http://naksha.internal")
    monkeypatch.setattr(cfg, "NAKSHA_MAX_RETRIES", 1)

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"statusCode": 429, "body": "rate limited"}
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with patch.object(DatabricksClient, "query_direct_sql_async", new_callable=AsyncMock) as mock_fallback:
            mock_fallback.return_value = [{"row": 1}]
            client = NakshaClient()
            rows = await client.execute_sql("SELECT 1")

    assert rows == [{"row": 1}]


# ── NakshaClient helpers ───────────────────────────────────────────────────────


def test_headers_without_token() -> None:
    client = NakshaClient()
    headers = client._headers()
    assert "Authorization" not in headers
    assert headers["Content-Type"] == "application/json"


def test_headers_with_token() -> None:
    client = NakshaClient(bearer_token="tok123")
    headers = client._headers()
    assert headers["Authorization"] == "Bearer tok123"


def test_system_content_basic() -> None:
    client = NakshaClient()
    content = client._system_content()
    assert "BUSINESS" in content
    assert "DOMAIN" in content


def test_system_content_with_conversation_and_space() -> None:
    client = NakshaClient()
    content = client._system_content(conversation_id="conv-1", space_id="space-1")
    assert "CONVERSATION_ID: conv-1" in content
    assert "SPACE_ID: space-1" in content


def test_parse_lambda_proxy_body_dict_body() -> None:
    payload = {"body": {"key": "value"}}
    assert NakshaClient._parse_lambda_proxy_body(payload) == {"key": "value"}


def test_parse_lambda_proxy_body_string_body() -> None:
    payload = {"body": json.dumps({"key": "value"})}
    assert NakshaClient._parse_lambda_proxy_body(payload) == {"key": "value"}


def test_parse_lambda_proxy_body_no_body_key() -> None:
    payload = {"key": "direct"}
    assert NakshaClient._parse_lambda_proxy_body(payload) == {"key": "direct"}


def test_parse_choice_content_non_dict_parsed() -> None:
    body = {"choices": [{"message": {"content": json.dumps([1, 2, 3])}}]}
    result = NakshaClient._parse_choice_content(body)
    assert result == {"data": [1, 2, 3]}


def test_parse_choice_content_invalid_json_returns_raw() -> None:
    body = {"choices": [{"message": {"content": "not-json"}}]}
    result = NakshaClient._parse_choice_content(body)
    assert result == {"raw_text": "not-json"}


def test_parse_choice_content_empty_choices_returns_body() -> None:
    body = {"choices": [], "status": "ok"}
    result = NakshaClient._parse_choice_content(body)
    assert result == body


def test_parse_choice_content_empty_content_returns_body() -> None:
    body = {"choices": [{"message": {"content": ""}}], "status": "ok"}
    result = NakshaClient._parse_choice_content(body)
    assert result == body


def test_extract_rows_filters_non_dicts() -> None:
    parsed = {"data": [{"a": 1}, "not-a-dict", None, {"b": 2}]}
    assert NakshaClient._extract_rows(parsed) == [{"a": 1}, {"b": 2}]


def test_extract_rows_missing_data_key() -> None:
    assert NakshaClient._extract_rows({}) == []


def test_infer_table_status_rows_present() -> None:
    status = NakshaClient._infer_table_status({}, rows=[{"x": 1}], naksha_status="success")
    assert status == "available"


def test_infer_table_status_cannot_run_query() -> None:
    parsed = {"raw_text": "cannot run this query for you"}
    status = NakshaClient._infer_table_status(parsed, rows=[], naksha_status="unknown")
    assert status == "unavailable"


def test_infer_table_status_table_not_found_text() -> None:
    parsed = {"message": "table not found"}
    status = NakshaClient._infer_table_status(parsed, rows=[], naksha_status="unknown")
    assert status == "unavailable"


def test_get_last_query_markers_returns_copy() -> None:
    client = NakshaClient()
    markers = client.get_last_query_markers()
    markers["naksha_status"] = "mutated"
    assert client.get_last_query_markers()["naksha_status"] == "unknown"


# ── NakshaClient.query() sync ─────────────────────────────────────────────────


def test_query_mock_mode_returns_empty() -> None:
    client = NakshaClient()
    result = client.query("SELECT 1")
    assert result == []
    assert client.get_last_query_markers()["naksha_status"] == "mock"


def test_query_live_naksha_error_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cfg, "USE_MOCK", False)
    monkeypatch.setattr(cfg, "NAKSHA_API_URL", "http://naksha.internal")
    client = NakshaClient()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"type": "error", "error": "table unavailable"}
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.post", return_value=mock_resp):
        with pytest.raises(NakshaError, match="table unavailable"):
            client.query("SELECT 1")


def test_build_run_inline_payload_uses_new_shape() -> None:
    client = NakshaClient()
    payload = client._build_run_inline_payload("SELECT 1")
    assert payload["action"] == "run_inline"
    assert payload["payload"]["messages"] == [{"role": "user", "content": "SELECT 1"}]
    assert payload["payload"]["naksha_session_id"]


def test_convert_preview_rows_builds_dicts() -> None:
    result = {
        "result_preview": {
            "columns": ["serial_number", "event_type"],
            "rows": [["890078", "MI"]],
        }
    }
    assert NakshaClient._convert_preview_rows(result) == [{"serial_number": "890078", "event_type": "MI"}]


# ── DatabricksClient helpers ──────────────────────────────────────────────────


def test_normalize_server_hostname_strips_scheme_and_slash() -> None:
    assert DatabricksClient._normalize_server_hostname("https://host.example.com/") == "host.example.com"
    assert DatabricksClient._normalize_server_hostname("http://host.example.com") == "host.example.com"
    assert DatabricksClient._normalize_server_hostname("host.example.com") == "host.example.com"


def test_sql_literal_none() -> None:
    assert DatabricksClient._sql_literal(None) == "NULL"


def test_sql_literal_bool() -> None:
    assert DatabricksClient._sql_literal(True) == "TRUE"
    assert DatabricksClient._sql_literal(False) == "FALSE"


def test_sql_literal_int() -> None:
    assert DatabricksClient._sql_literal(42) == "42"


def test_sql_literal_string_escapes_quotes() -> None:
    assert DatabricksClient._sql_literal("O'Brien") == "'O''Brien'"


def test_render_query_substitutes_params() -> None:
    client = DatabricksClient(enable_naksha=False)
    result = client._render_query("SELECT * FROM t WHERE id = :id AND name = :name", {"id": 1, "name": "O'Brien"})
    assert result == "SELECT * FROM t WHERE id = 1 AND name = 'O''Brien'"


def test_render_query_missing_param_raises() -> None:
    client = DatabricksClient(enable_naksha=False)
    with pytest.raises(ValueError, match="Missing SQL parameter"):
        client._render_query("SELECT :missing", {})


def test_expected_select_columns_star_returns_empty() -> None:
    assert DatabricksClient._expected_select_columns("SELECT * FROM t") == []


def test_expected_select_columns_extracts_aliases() -> None:
    cols = DatabricksClient._expected_select_columns("SELECT a.foo AS bar, b.baz FROM t")
    assert "bar" in cols
    assert "baz" in cols


def test_expected_select_columns_no_select_returns_empty() -> None:
    assert DatabricksClient._expected_select_columns("SHOW TABLES") == []


def test_validate_result_shape_passes_when_no_rows() -> None:
    DatabricksClient._validate_result_shape("SELECT col FROM t", [])  # no error


def test_validate_result_shape_passes_matching_column() -> None:
    DatabricksClient._validate_result_shape("SELECT col FROM t", [{"col": 1}])


def test_validate_result_shape_raises_on_mismatch() -> None:
    with pytest.raises(RuntimeError, match="unexpected schema"):
        DatabricksClient._validate_result_shape("SELECT col_a, col_b, col_c FROM t", [{"x": 1}])


def test_databricks_validate_raises_when_missing_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABRICKS_SQL_MOCK_MODE", "false")
    monkeypatch.setenv("DATABRICKS_HOST", "")
    monkeypatch.setenv("DATABRICKS_TOKEN", "")
    monkeypatch.setenv("DATABRICKS_HTTP_PATH", "")
    client = DatabricksClient(enable_naksha=False)
    with pytest.raises(ValueError, match="Missing required Databricks settings"):
        client._validate()


def test_databricks_mock_sql_mode_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABRICKS_SQL_MOCK_MODE", "true")
    client = DatabricksClient(enable_naksha=False)
    result = client.query_direct_sql("SELECT 1")
    assert result == []
    assert client.last_query_backend == "mock_sql"


def test_databricks_query_raises_when_naksha_disabled() -> None:
    client = DatabricksClient(enable_naksha=False)
    with pytest.raises(RuntimeError, match="Naksha client is disabled"):
        client.query("SELECT 1", params={})


def test_databricks_get_last_query_markers_no_naksha() -> None:
    client = DatabricksClient(enable_naksha=False)
    markers = client.get_last_query_markers()
    assert markers["naksha_status"] == "fallback_databricks"
