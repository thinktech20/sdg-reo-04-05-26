"""Comprehensive tests for databricks_client.py.

Tests cover:
- DatabricksClient initialization
- Configuration validation
- SQL literal conversion
- Query rendering and execution
- Mock mode behavior
- Schema validation
- Async query methods
"""

from __future__ import annotations

import datetime
import decimal
import os
from unittest.mock import MagicMock, patch

import pytest


class TestDatabricksClientInit:
    """Tests for DatabricksClient initialization."""

    @patch.dict(os.environ, {}, clear=True)
    def test_init_default_values(self) -> None:
        """Test initialization with default environment values."""
        from data_service.databricks_client import DatabricksClient

        client = DatabricksClient()

        assert client.sql_mock_mode is False
        assert client.host == ""
        assert client.token == ""
        assert client.http_path == ""
        assert client.socket_timeout == 120
        assert client.last_query_backend == "unknown"

    @patch.dict(
        os.environ,
        {
            "DATABRICKS_SQL_MOCK_MODE": "true",
            "DATABRICKS_HOST": "test-host.databricks.com",
            "DATABRICKS_TOKEN": "test-token-123",
            "DATABRICKS_HTTP_PATH": "/sql/1.0/warehouses/abc",
            "DATABRICKS_SOCKET_TIMEOUT": "60",
        },
    )
    def test_init_with_env_values(self) -> None:
        """Test initialization with environment values."""
        from data_service.databricks_client import DatabricksClient

        client = DatabricksClient()

        assert client.sql_mock_mode is True
        assert client.host == "test-host.databricks.com"
        assert client.token == "test-token-123"
        assert client.http_path == "/sql/1.0/warehouses/abc"
        assert client.socket_timeout == 60


class TestValidation:
    """Tests for _validate method."""

    @patch.dict(os.environ, {"DATABRICKS_SQL_MOCK_MODE": "true"}, clear=True)
    def test_validate_skips_in_mock_mode(self) -> None:
        """Test that validation is skipped in mock mode."""
        from data_service.databricks_client import DatabricksClient

        client = DatabricksClient()
        # Should not raise
        client._validate()

    @patch.dict(os.environ, {"DATABRICKS_SQL_MOCK_MODE": "false"}, clear=True)
    def test_validate_raises_without_host(self) -> None:
        """Test validation fails without host."""
        from data_service.databricks_client import DatabricksClient

        client = DatabricksClient()

        with pytest.raises(ValueError) as exc_info:
            client._validate()

        assert "DATABRICKS_HOST" in str(exc_info.value)

    @patch.dict(
        os.environ,
        {
            "DATABRICKS_SQL_MOCK_MODE": "false",
            "DATABRICKS_HOST": "host",
        },
        clear=True,
    )
    def test_validate_raises_without_token(self) -> None:
        """Test validation fails without token."""
        from data_service.databricks_client import DatabricksClient

        client = DatabricksClient()

        with pytest.raises(ValueError) as exc_info:
            client._validate()

        assert "DATABRICKS_TOKEN" in str(exc_info.value)

    @patch.dict(
        os.environ,
        {
            "DATABRICKS_SQL_MOCK_MODE": "false",
            "DATABRICKS_HOST": "host",
            "DATABRICKS_TOKEN": "token",
        },
        clear=True,
    )
    def test_validate_raises_without_http_path(self) -> None:
        """Test validation fails without http_path."""
        from data_service.databricks_client import DatabricksClient

        client = DatabricksClient()

        with pytest.raises(ValueError) as exc_info:
            client._validate()

        assert "DATABRICKS_HTTP_PATH" in str(exc_info.value)

    @patch.dict(
        os.environ,
        {
            "DATABRICKS_SQL_MOCK_MODE": "false",
            "DATABRICKS_HOST": "host",
            "DATABRICKS_TOKEN": "token",
            "DATABRICKS_HTTP_PATH": "/path",
        },
        clear=True,
    )
    def test_validate_passes_with_all_config(self) -> None:
        """Test validation passes with all required config."""
        from data_service.databricks_client import DatabricksClient

        client = DatabricksClient()
        # Should not raise
        client._validate()


class TestNormalizeServerHostname:
    """Tests for _normalize_server_hostname static method."""

    def test_normalize_removes_https(self) -> None:
        """Test HTTPS prefix removal."""
        from data_service.databricks_client import DatabricksClient

        result = DatabricksClient._normalize_server_hostname("https://host.com")
        assert result == "host.com"

    def test_normalize_removes_http(self) -> None:
        """Test HTTP prefix removal."""
        from data_service.databricks_client import DatabricksClient

        result = DatabricksClient._normalize_server_hostname("http://host.com")
        assert result == "host.com"

    def test_normalize_strips_trailing_slash(self) -> None:
        """Test trailing slash removal."""
        from data_service.databricks_client import DatabricksClient

        result = DatabricksClient._normalize_server_hostname("host.com/")
        assert result == "host.com"

    def test_normalize_handles_none(self) -> None:
        """Test handling of None input."""
        from data_service.databricks_client import DatabricksClient

        result = DatabricksClient._normalize_server_hostname(None)
        assert result == ""

    def test_normalize_handles_empty(self) -> None:
        """Test handling of empty string."""
        from data_service.databricks_client import DatabricksClient

        result = DatabricksClient._normalize_server_hostname("")
        assert result == ""

    def test_normalize_preserves_clean_hostname(self) -> None:
        """Test that clean hostname is preserved."""
        from data_service.databricks_client import DatabricksClient

        result = DatabricksClient._normalize_server_hostname("my-host.databricks.com")
        assert result == "my-host.databricks.com"


class TestSqlLiteral:
    """Tests for _sql_literal static method."""

    def test_sql_literal_none(self) -> None:
        """Test NULL conversion."""
        from data_service.databricks_client import DatabricksClient

        assert DatabricksClient._sql_literal(None) == "NULL"

    def test_sql_literal_true(self) -> None:
        """Test boolean True conversion."""
        from data_service.databricks_client import DatabricksClient

        assert DatabricksClient._sql_literal(True) == "TRUE"

    def test_sql_literal_false(self) -> None:
        """Test boolean False conversion."""
        from data_service.databricks_client import DatabricksClient

        assert DatabricksClient._sql_literal(False) == "FALSE"

    def test_sql_literal_int(self) -> None:
        """Test integer conversion."""
        from data_service.databricks_client import DatabricksClient

        assert DatabricksClient._sql_literal(42) == "42"

    def test_sql_literal_float(self) -> None:
        """Test float conversion."""
        from data_service.databricks_client import DatabricksClient

        assert DatabricksClient._sql_literal(3.14) == "3.14"

    def test_sql_literal_decimal(self) -> None:
        """Test Decimal conversion."""
        from data_service.databricks_client import DatabricksClient

        assert DatabricksClient._sql_literal(decimal.Decimal("99.99")) == "99.99"

    def test_sql_literal_datetime(self) -> None:
        """Test datetime conversion."""
        from data_service.databricks_client import DatabricksClient

        dt = datetime.datetime(2026, 3, 12, 10, 30, 0)
        result = DatabricksClient._sql_literal(dt)
        assert result == "'2026-03-12 10:30:00'"

    def test_sql_literal_date(self) -> None:
        """Test date conversion."""
        from data_service.databricks_client import DatabricksClient

        d = datetime.date(2026, 3, 12)
        result = DatabricksClient._sql_literal(d)
        assert result == "'2026-03-12'"

    def test_sql_literal_string(self) -> None:
        """Test string conversion with escaping."""
        from data_service.databricks_client import DatabricksClient

        assert DatabricksClient._sql_literal("test") == "'test'"

    def test_sql_literal_string_with_quotes(self) -> None:
        """Test string with single quotes is escaped."""
        from data_service.databricks_client import DatabricksClient

        assert DatabricksClient._sql_literal("O'Brien") == "'O''Brien'"


class TestRenderQuery:
    """Tests for _render_query method."""

    @patch.dict(os.environ, {"DATABRICKS_SQL_MOCK_MODE": "true"}, clear=True)
    def test_render_query_no_params(self) -> None:
        """Test query rendering without parameters."""
        from data_service.databricks_client import DatabricksClient

        client = DatabricksClient()
        query = "SELECT * FROM table"
        result = client._render_query(query, {})

        assert result == query

    @patch.dict(os.environ, {"DATABRICKS_SQL_MOCK_MODE": "true"}, clear=True)
    def test_render_query_with_string_param(self) -> None:
        """Test query rendering with string parameter."""
        from data_service.databricks_client import DatabricksClient

        client = DatabricksClient()
        query = "SELECT * FROM table WHERE name = :name"
        result = client._render_query(query, {"name": "test"})

        assert result == "SELECT * FROM table WHERE name = 'test'"

    @patch.dict(os.environ, {"DATABRICKS_SQL_MOCK_MODE": "true"}, clear=True)
    def test_render_query_with_multiple_params(self) -> None:
        """Test query rendering with multiple parameters."""
        from data_service.databricks_client import DatabricksClient

        client = DatabricksClient()
        query = "SELECT * FROM t WHERE id = :id AND status = :status"
        result = client._render_query(query, {"id": 123, "status": "active"})

        assert result == "SELECT * FROM t WHERE id = 123 AND status = 'active'"

    @patch.dict(os.environ, {"DATABRICKS_SQL_MOCK_MODE": "true"}, clear=True)
    def test_render_query_missing_param_raises(self) -> None:
        """Test that missing parameter raises ValueError."""
        from data_service.databricks_client import DatabricksClient

        client = DatabricksClient()
        query = "SELECT * FROM table WHERE id = :id AND name = :missing_param"

        with pytest.raises(ValueError) as exc_info:
            client._render_query(query, {"id": 1})  # missing_param not provided

        assert "Missing SQL parameter" in str(exc_info.value)


class TestExpectedSelectColumns:
    """Tests for _expected_select_columns static method."""

    def test_select_star_returns_empty(self) -> None:
        """Test SELECT * returns empty list."""
        from data_service.databricks_client import DatabricksClient

        result = DatabricksClient._expected_select_columns("SELECT * FROM table")
        assert result == []

    def test_extracts_column_names(self) -> None:
        """Test extraction of column names."""
        from data_service.databricks_client import DatabricksClient

        result = DatabricksClient._expected_select_columns("SELECT id, name FROM table")
        assert "id" in result
        assert "name" in result

    def test_extracts_aliased_columns(self) -> None:
        """Test extraction of aliased column names."""
        from data_service.databricks_client import DatabricksClient

        result = DatabricksClient._expected_select_columns(
            "SELECT user_id AS id, full_name AS name FROM users"
        )
        assert "id" in result
        assert "name" in result

    def test_handles_qualified_columns(self) -> None:
        """Test handling of table-qualified column names."""
        from data_service.databricks_client import DatabricksClient

        result = DatabricksClient._expected_select_columns(
            "SELECT t.column_name FROM table t"
        )
        assert "column_name" in result

    def test_no_select_returns_empty(self) -> None:
        """Test non-SELECT query returns empty list."""
        from data_service.databricks_client import DatabricksClient

        result = DatabricksClient._expected_select_columns("INSERT INTO table VALUES (1)")
        assert result == []


class TestValidateResultShape:
    """Tests for _validate_result_shape static method."""

    def test_empty_rows_passes(self) -> None:
        """Test that empty rows pass validation."""
        from data_service.databricks_client import DatabricksClient

        # Should not raise
        DatabricksClient._validate_result_shape("SELECT id FROM table", [])

    def test_matching_columns_passes(self) -> None:
        """Test that matching columns pass validation."""
        from data_service.databricks_client import DatabricksClient

        rows = [{"id": 1, "name": "test"}]
        # Should not raise
        DatabricksClient._validate_result_shape("SELECT id, name FROM table", rows)

    def test_mismatching_columns_raises(self) -> None:
        """Test that mismatching columns raise RuntimeError."""
        from data_service.databricks_client import DatabricksClient

        rows = [{"other_col": 1}]

        with pytest.raises(RuntimeError) as exc_info:
            DatabricksClient._validate_result_shape("SELECT id, name, status FROM table", rows)

        assert "unexpected schema" in str(exc_info.value)

    def test_rows_without_columns_raises(self) -> None:
        """Test that rows without columns raise RuntimeError."""
        from data_service.databricks_client import DatabricksClient

        rows = [{}]

        with pytest.raises(RuntimeError) as exc_info:
            DatabricksClient._validate_result_shape("SELECT id FROM table", rows)

        assert "without columns" in str(exc_info.value)


class TestQueryMockMode:
    """Tests for query method in mock mode."""

    @patch.dict(os.environ, {"DATABRICKS_SQL_MOCK_MODE": "true"}, clear=True)
    def test_query_mock_mode_returns_empty(self) -> None:
        """Test query returns empty list in mock mode."""
        from data_service.databricks_client import DatabricksClient

        client = DatabricksClient()
        result = client.query("SELECT * FROM table")

        assert result == []
        assert client.last_query_backend == "mock_sql"

    @patch.dict(os.environ, {"DATABRICKS_SQL_MOCK_MODE": "true"}, clear=True)
    def test_query_direct_sql_mock_mode(self) -> None:
        """Test query_direct_sql returns empty in mock mode."""
        from data_service.databricks_client import DatabricksClient

        client = DatabricksClient()
        result = client.query_direct_sql("SELECT * FROM table")

        assert result == []
        assert client.last_query_backend == "mock_sql"


class TestQueryRealMode:
    """Tests for query method in real mode (mocked connection)."""

    @patch("data_service.databricks_client.sql")
    @patch.dict(
        os.environ,
        {
            "DATABRICKS_SQL_MOCK_MODE": "false",
            "DATABRICKS_HOST": "host.com",
            "DATABRICKS_TOKEN": "token",
            "DATABRICKS_HTTP_PATH": "/path",
        },
        clear=True,
    )
    def test_query_success(self, mock_sql: MagicMock) -> None:
        """Test successful query execution."""
        from data_service.databricks_client import DatabricksClient

        # Setup mocks
        mock_cursor = MagicMock()
        mock_cursor.description = [("id",), ("name",)]
        mock_cursor.fetchall.return_value = [(1, "Alice"), (2, "Bob")]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_sql.connect.return_value = mock_conn

        client = DatabricksClient()
        result = client.query("SELECT id, name FROM users")

        assert len(result) == 2
        assert result[0] == {"id": 1, "name": "Alice"}
        assert result[1] == {"id": 2, "name": "Bob"}
        assert client.last_query_backend == "direct_sql"

    @patch("data_service.databricks_client.sql")
    @patch.dict(
        os.environ,
        {
            "DATABRICKS_SQL_MOCK_MODE": "false",
            "DATABRICKS_HOST": "host.com",
            "DATABRICKS_TOKEN": "token",
            "DATABRICKS_HTTP_PATH": "/path",
        },
        clear=True,
    )
    def test_query_error_logs_and_raises(self, mock_sql: MagicMock) -> None:
        """Test query error handling."""
        from data_service.databricks_client import DatabricksClient

        mock_sql.connect.side_effect = Exception("Connection failed")

        client = DatabricksClient()

        with pytest.raises(Exception) as exc_info:
            client.query("SELECT * FROM table")

        assert "Connection failed" in str(exc_info.value)

    @patch("data_service.databricks_client.sql")
    @patch.dict(
        os.environ,
        {
            "DATABRICKS_SQL_MOCK_MODE": "false",
            "DATABRICKS_HOST": "host.com",
            "DATABRICKS_TOKEN": "token",
            "DATABRICKS_HTTP_PATH": "/path",
        },
        clear=True,
    )
    def test_query_closes_cursor_and_connection(self, mock_sql: MagicMock) -> None:
        """Test that cursor and connection are closed in finally block."""
        from data_service.databricks_client import DatabricksClient

        mock_cursor = MagicMock()
        mock_cursor.description = [("id",)]
        mock_cursor.fetchall.return_value = [(1,)]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_sql.connect.return_value = mock_conn

        client = DatabricksClient()
        client.query("SELECT id FROM table")

        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch("data_service.databricks_client.sql")
    @patch.dict(
        os.environ,
        {
            "DATABRICKS_SQL_MOCK_MODE": "false",
            "DATABRICKS_HOST": "host.com",
            "DATABRICKS_TOKEN": "token",
            "DATABRICKS_HTTP_PATH": "/path",
        },
        clear=True,
    )
    def test_query_handles_close_exception(self, mock_sql: MagicMock) -> None:
        """Test that close exceptions don't propagate."""
        from data_service.databricks_client import DatabricksClient

        mock_cursor = MagicMock()
        mock_cursor.description = [("id",)]
        mock_cursor.fetchall.return_value = [(1,)]
        mock_cursor.close.side_effect = Exception("Close failed")

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.close.side_effect = Exception("Close failed")

        mock_sql.connect.return_value = mock_conn

        client = DatabricksClient()
        # Should not raise despite close exceptions
        result = client.query("SELECT id FROM table")

        assert len(result) == 1


class TestQueryDirectSql:
    """Tests for query_direct_sql method."""

    @patch("data_service.databricks_client.sql")
    @patch.dict(
        os.environ,
        {
            "DATABRICKS_SQL_MOCK_MODE": "false",
            "DATABRICKS_HOST": "host.com",
            "DATABRICKS_TOKEN": "token",
            "DATABRICKS_HTTP_PATH": "/path",
        },
        clear=True,
    )
    def test_query_direct_sql_runs_warmup(self, mock_sql: MagicMock) -> None:
        """Test that warmup query is executed."""
        from data_service.databricks_client import DatabricksClient

        mock_cursor = MagicMock()
        mock_cursor.description = [("id",)]
        mock_cursor.fetchall.return_value = [(1,)]
        mock_cursor.fetchone.return_value = (1,)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_sql.connect.return_value = mock_conn

        client = DatabricksClient()
        client.query_direct_sql("SELECT id FROM table")

        # Should have executed warmup SELECT 1 plus the actual query
        assert mock_cursor.execute.call_count == 2


class TestGetLastQueryMarkers:
    """Tests for get_last_query_markers method."""

    @patch.dict(os.environ, {"DATABRICKS_SQL_MOCK_MODE": "true"}, clear=True)
    def test_returns_markers(self) -> None:
        """Test markers are returned."""
        from data_service.databricks_client import DatabricksClient

        client = DatabricksClient()
        client.query("SELECT 1")

        markers = client.get_last_query_markers()

        assert "naksha_status" in markers
        assert "table_status" in markers
        assert markers["naksha_status"] == "disabled"
        assert markers["table_status"] == "mock_sql"


class TestAsyncMethods:
    """Tests for async query methods."""

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"DATABRICKS_SQL_MOCK_MODE": "true"}, clear=True)
    async def test_query_async(self) -> None:
        """Test async query method."""
        from data_service.databricks_client import DatabricksClient

        client = DatabricksClient()
        result = await client.query_async("SELECT * FROM table")

        assert result == []

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"DATABRICKS_SQL_MOCK_MODE": "true"}, clear=True)
    async def test_query_direct_sql_async(self) -> None:
        """Test async direct SQL query method."""
        from data_service.databricks_client import DatabricksClient

        client = DatabricksClient()
        result = await client.query_direct_sql_async("SELECT * FROM table")

        assert result == []


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    @patch("data_service.databricks_client.sql")
    @patch.dict(
        os.environ,
        {
            "DATABRICKS_SQL_MOCK_MODE": "false",
            "DATABRICKS_HOST": "host.com",
            "DATABRICKS_TOKEN": "token",
            "DATABRICKS_HTTP_PATH": "/path",
        },
        clear=True,
    )
    def test_query_no_description(self, mock_sql: MagicMock) -> None:
        """Test handling of query with no description."""
        from data_service.databricks_client import DatabricksClient

        mock_cursor = MagicMock()
        mock_cursor.description = None
        mock_cursor.fetchall.return_value = []

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_sql.connect.return_value = mock_conn

        client = DatabricksClient()
        result = client.query("SELECT * FROM empty_table", validate_shape=False)

        assert result == []

    @patch.dict(os.environ, {"DATABRICKS_SQL_MOCK_MODE": "true"}, clear=True)
    def test_query_with_debug_false(self) -> None:
        """Test query with debug logging disabled."""
        from data_service.databricks_client import DatabricksClient

        client = DatabricksClient()
        result = client.query("SELECT 1", debug=False)

        assert result == []

    @patch.dict(os.environ, {"DATABRICKS_SQL_MOCK_MODE": "true"}, clear=True)
    def test_query_with_validate_shape_false(self) -> None:
        """Test query with shape validation disabled."""
        from data_service.databricks_client import DatabricksClient

        client = DatabricksClient()
        result = client.query("SELECT 1", validate_shape=False)

        assert result == []
