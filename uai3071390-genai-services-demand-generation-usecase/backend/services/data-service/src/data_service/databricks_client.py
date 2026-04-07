"""Databricks SQL client for direct database queries.

Provides synchronous and async methods for executing SQL queries
against Databricks using the databricks-sql-connector.
"""

from __future__ import annotations

import asyncio
import datetime
import decimal
import os
import re
import socket
from typing import Any

from databricks import sql

from commons.logging import get_logger
from data_service.config import _to_bool

logger = get_logger(__name__)

_PARAM_PATTERN = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")
_SELECT_PATTERN = re.compile(r"\bselect\b(.*?)\bfrom\b", re.IGNORECASE | re.DOTALL)


class DatabricksClient:
    """Client for executing SQL queries against Databricks."""

    def __init__(self) -> None:
        self.sql_mock_mode = _to_bool(os.getenv("DATABRICKS_SQL_MOCK_MODE"), False)
        self.host = str(os.getenv("DATABRICKS_HOST", "https://gevernova-nrc-workspace.cloud.databricks.com")).strip()
        self.token = str(os.getenv("DATABRICKS_TOKEN", "")).strip()
        self.http_path = str(os.getenv("DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/daff57b69fee5745")).strip()
        self.socket_timeout = int(os.getenv("DATABRICKS_SOCKET_TIMEOUT", "120"))
        self.last_query_backend = "unknown"

    def _validate(self) -> None:
        """Validate required Databricks configuration."""
        if self.sql_mock_mode:
            return
        missing = []
        if not self.host:
            missing.append("DATABRICKS_HOST")
        if not self.token:
            missing.append("DATABRICKS_TOKEN")
        if not self.http_path:
            missing.append("DATABRICKS_HTTP_PATH")
        if missing:
            raise ValueError(f"Missing required Databricks settings: {', '.join(missing)}")

    @staticmethod
    def _normalize_server_hostname(host: str) -> str:
        """Normalize Databricks server hostname."""
        normalized = str(host or "").strip()
        normalized = re.sub(r"^https?://", "", normalized)
        return normalized.rstrip("/")

    @staticmethod
    def _sql_literal(value: Any) -> str:
        """Convert a Python value to a SQL literal string."""
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, int | float | decimal.Decimal):
            return str(value)
        if isinstance(value, datetime.datetime | datetime.date):
            escaped = str(value).replace("'", "''")
            return f"'{escaped}'"

        escaped = str(value).replace("'", "''")
        return f"'{escaped}'"

    def _render_query(self, query: str, params: dict[str, Any]) -> str:
        """Render a parameterized query by substituting :param placeholders."""
        if not params:
            return query

        def replace(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in params:
                raise ValueError(f"Missing SQL parameter: {key}")
            return self._sql_literal(params[key])

        return _PARAM_PATTERN.sub(replace, query)

    @staticmethod
    def _expected_select_columns(query: str) -> list[str]:
        """Extract expected column names from a SELECT query."""
        match = _SELECT_PATTERN.search(query)
        if not match:
            return []

        select_clause = match.group(1).strip()
        if not select_clause or "*" in select_clause:
            return []

        expected: list[str] = []
        for raw_expr in select_clause.split(","):
            expression = raw_expr.strip()
            if not expression:
                continue

            alias_match = re.search(r"\bas\s+([A-Za-z_][A-Za-z0-9_]*)\s*$", expression, re.IGNORECASE)
            if alias_match:
                expected.append(alias_match.group(1).lower())
                continue

            token = expression.split()[-1]
            expected.append(token.split(".")[-1].strip('"').lower())

        return expected

    @staticmethod
    def _validate_result_shape(query: str, rows: list[dict[str, Any]]) -> None:
        """Validate that query results match expected schema."""
        if not rows:
            return

        expected = DatabricksClient._expected_select_columns(query)
        if not expected:
            return

        actual_keys = {str(key).strip().lower() for key in rows[0].keys()}
        if not actual_keys:
            raise RuntimeError("Databricks returned rows without columns")

        matched = [column for column in expected if column in actual_keys]
        required_matches = max(1, min(3, len(expected)))
        if len(matched) < required_matches:
            raise RuntimeError("Databricks returned unexpected schema for SQL query")

    def query(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        debug: bool = True,
        validate_shape: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Execute query using direct Databricks SQL connection.

        Args:
            query: SQL query string with optional :param placeholders
            params: Dictionary of parameter values
            debug: Whether to log debug information
            validate_shape: Whether to validate result schema

        Returns:
            List of result rows as dictionaries
        """
        if self.sql_mock_mode:
            self.last_query_backend = "mock_sql"
            if debug:
                logger.debug("DATABRICKS_SQL_MOCK_MODE=true returning empty result set")
            return []

        self._validate()
        rendered_query = self._render_query(query, params or {})

        if debug:
            logger.debug("Connecting to Databricks host=%s", self._normalize_server_hostname(self.host))
            logger.debug("Executing query: %s...", rendered_query[:200])

        conn = None
        cursor = None
        try:
            socket.setdefaulttimeout(30)
            conn = sql.connect(
                server_hostname=self._normalize_server_hostname(self.host),
                http_path=self.http_path,
                access_token=self.token,
                _socket_timeout=self.socket_timeout,
                _tls_no_verify=True,
            )
            cursor = conn.cursor()
            cursor.execute(rendered_query)
            columns = [col[0] for col in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            result_rows = [dict(zip(columns, row, strict=False)) for row in rows]

            self.last_query_backend = "direct_sql"
            if debug:
                logger.debug("Query returned %d rows", len(result_rows))
            if validate_shape:
                self._validate_result_shape(rendered_query, result_rows)
            return result_rows
        except Exception as exc:
            logger.error("Databricks query failed: %s", exc)
            raise
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def query_direct_sql(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        validate_shape: bool = True,
    ) -> list[dict[str, Any]]:
        """Execute query with detailed debug logging."""
        if self.sql_mock_mode:
            self.last_query_backend = "mock_sql"
            logger.debug("DATABRICKS_SQL_MOCK_MODE=true returning empty result set")
            return []

        self._validate()
        params = params or {}

        logger.debug(
            "Connecting to Databricks host=%s http_path=%s",
            self._normalize_server_hostname(self.host),
            self.http_path,
        )
        logger.debug("HTTP_PROXY=%s", os.environ.get("HTTP_PROXY"))
        logger.debug("HTTPS_PROXY=%s", os.environ.get("HTTPS_PROXY"))
        logger.debug("NO_PROXY=%s", os.environ.get("NO_PROXY"))

        conn = None
        cursor = None
        try:
            socket.setdefaulttimeout(30)
            conn = sql.connect(
                server_hostname=self._normalize_server_hostname(self.host),
                http_path=self.http_path,
                access_token=self.token,
                _socket_timeout=self.socket_timeout,
                _tls_no_verify=True,
            )
            cursor = conn.cursor()
            logger.debug("Running warmup query: SELECT 1")
            cursor.execute("SELECT 1")
            cursor.fetchone()
            logger.debug("Warmup query completed")
            logger.debug("Executing query: %s with params: %s", query, params)

            cursor.execute(query, params)
            columns = [col[0] for col in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            result_rows = [dict(zip(columns, row, strict=False)) for row in rows]

            self.last_query_backend = "direct_sql"
            logger.debug("Query returned %d rows", len(result_rows))
            if validate_shape:
                self._validate_result_shape(query, result_rows)
            return result_rows
        except Exception as exc:
            logger.error("Databricks query failed: %s", exc)
            raise
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def get_last_query_markers(self) -> dict[str, str]:
        """Return query execution metadata markers."""
        return {
            "naksha_status": "disabled",
            "table_status": self.last_query_backend,
        }

    async def query_async(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        debug: bool = True,
        validate_shape: bool = True,
    ) -> list[dict[str, Any]]:
        """Async wrapper for query method."""
        return await asyncio.to_thread(self.query, query, params, debug, validate_shape)

    async def query_direct_sql_async(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        validate_shape: bool = True,
    ) -> list[dict[str, Any]]:
        """Async wrapper for query_direct_sql method."""
        return await asyncio.to_thread(self.query_direct_sql, query, params, validate_shape)
