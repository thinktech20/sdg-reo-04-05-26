"""NakshaClient -- async HTTP wrapper for the Naksha SQL proxy.

Naksha is the platform's internal SQL proxy. Agents query it via structured
SQL statements; responses use an OpenAI-style envelope:
  choices[0].message.content  →  JSON string  →  parse  →  data[] list

Retry policy: exponential backoff, 3 attempts, 2s/4s/8s (tenacity).
All calls time out after NAKSHA_TIMEOUT seconds (default 120s).
USE_MOCK=true bypasses all HTTP calls and returns the provided mock fixture.
"""

from __future__ import annotations

import asyncio
import datetime
import decimal
import json
import os
import re
import socket
import time
import uuid
from typing import Any

import httpx
import requests
import urllib3
from tenacity import retry, stop_after_attempt, wait_exponential

from commons.logging import get_logger
from data_service import config

logger = get_logger(__name__)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Naksha request envelope shape
_NAKSHA_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
}

_PARAM_PATTERN = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")
_SELECT_PATTERN = re.compile(r"\bselect\b(.*?)\bfrom\b", re.IGNORECASE | re.DOTALL)


class NakshaError(RuntimeError):
    """Raised when Naksha returns a non-200 response or unparseable content."""


class NakshaRateLimitError(NakshaError):
    """Raised when Naksha returns a rate limit response."""


class NakshaClient:
    """Async Naksha SQL proxy client.

    Usage (per-request, no shared state):
        client = NakshaClient()
        rows = await client.execute_sql("SELECT * FROM vgpp.prm_std_views LIMIT 10")

    In production the caller passes a bearer_token forwarded from the ALB-injected
    OIDC header.  In local dev (AUTH_LOCAL_MODE=true) no token is required.
    """

    def __init__(self, bearer_token: str = "") -> None:  # nosec B107
        self._token = bearer_token
        self.api_url = config.NAKSHA_API_URL.rstrip("/")
        self.mock_mode = config.USE_MOCK
        self.verify_ssl = config.NAKSHA_VERIFY_SSL
        self.timeout_seconds = config.NAKSHA_TIMEOUT
        self.business = config.NAKSHA_BUSINESS
        self.domain = config.NAKSHA_DOMAIN
        self.subdomain = config.NAKSHA_SUBDOMAIN
        self.user_email = config.NAKSHA_USER_EMAIL
        self.user_domains = list(config.NAKSHA_USER_DOMAINS) or ([self.subdomain] if self.subdomain else [])
        self.user_group_ids = list(config.NAKSHA_USER_GROUP_IDS)
        self.poll_interval_seconds = config.NAKSHA_POLL_INTERVAL_SECONDS
        self.max_polls = config.NAKSHA_MAX_POLLS
        self.session_id = f"data-service-{uuid.uuid4().hex}"
        self.default_headers = dict(_NAKSHA_HEADERS)
        self.last_query_markers: dict[str, str] = {
            "naksha_status": "unknown",
            "table_status": "unknown",
        }

    def _headers(self) -> dict[str, str]:
        headers = dict(self.default_headers)
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def _validate(self) -> None:
        if self.mock_mode:
            return
        if not self.api_url:
            raise NakshaError("NAKSHA_API_URL is not configured")

    async def _execute_via_databricks_fallback(self, sql: str) -> list[dict[str, Any]]:
        started = time.perf_counter()
        logger.info("backend=databricks_fallback stage=start transport=direct_sql")
        fallback_client = DatabricksClient(enable_naksha=False)
        rows = await fallback_client.query_direct_sql_async(sql, validate_shape=False)
        self.last_query_markers = {
            "naksha_status": "fallback_databricks",
            "table_status": "available" if rows else "empty_or_filtered",
        }
        logger.info(
            "backend=databricks_fallback stage=done transport=direct_sql row_count=%s duration_ms=%s",
            len(rows),
            int((time.perf_counter() - started) * 1000),
        )
        return rows

    def _system_content(self, conversation_id: str | None = None, space_id: str | None = None) -> str:
        content = (
            f"BUSINESS: {self.business}\n"
            f"DOMAIN: {self.domain}\n"
            f"SUBDOMAIN: {self.subdomain}\n"
            f"USER_EMAIL: {self.user_email}"
        )
        if conversation_id and space_id:
            content += f"\nCONVERSATION_ID: {conversation_id}\nSPACE_ID: {space_id}"
        return content

    def _build_run_inline_payload(self, sql: str) -> dict[str, Any]:
        return {
            "action": "run_inline",
            "payload": {
                "messages": [{"role": "user", "content": sql}],
                "naksha_session_id": self.session_id,
                "user_email": self.user_email,
                "user_domains": self.user_domains,
                "user_group_ids": self.user_group_ids,
            },
        }

    def _build_run_inline_status_payload(self, sql: str, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "action": "run_inline_status",
            "payload": {
                "space": {"id": state["space_id"]},
                "genie": {
                    "conversation_id": state["conversation_id"],
                    "message_id": state["message_id"],
                },
                "chosen_tag": state.get("chosen_tag", ""),
                "question": sql,
                "tables_selected": state.get("tables_selected", []),
                "naksha_session_id": self.session_id,
                "user_email": self.user_email,
                "user_domains": self.user_domains,
                "user_group_ids": self.user_group_ids,
            },
        }

    @staticmethod
    def _extract_running_state(result: dict[str, Any]) -> dict[str, Any]:
        space = result.get("space") or {}
        genie = result.get("genie") or {}
        return {
            "space_id": str(space.get("id") or "").strip(),
            "conversation_id": str(genie.get("conversation_id") or "").strip(),
            "message_id": str(genie.get("message_id") or "").strip(),
            "chosen_tag": result.get("chosen_tag") or "",
            "tables_selected": result.get("tables_selected") or [],
        }

    @staticmethod
    def _convert_preview_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
        preview = result.get("result_preview") or {}
        columns = preview.get("columns") or []
        raw_rows = preview.get("rows") or []

        rows: list[dict[str, Any]] = []
        for raw_row in raw_rows:
            if isinstance(raw_row, dict):
                rows.append(raw_row)
                continue
            if isinstance(raw_row, list) and columns:
                rows.append({str(columns[index]): raw_row[index] for index in range(min(len(columns), len(raw_row)))})
        return rows

    @staticmethod
    def _normalize_new_api_result(result: dict[str, Any]) -> dict[str, Any]:
        response_type = str(result.get("type") or "").lower()
        if response_type == "answer":
            return {
                "status": "success",
                "answer": result.get("answer") or result.get("executive_summary") or "",
                "sql": result.get("sql") or "",
                "data": NakshaClient._convert_preview_rows(result),
            }
        if response_type == "error":
            genie_message = result.get("genie_message") or {}
            return {
                "status": "error",
                "message": result.get("error")
                or result.get("details")
                or genie_message.get("content")
                or "Naksha query error",
                "data": [],
            }
        if response_type == "clarify":
            return {
                "status": "error",
                "message": result.get("clarifying_question") or "Naksha clarification required",
                "data": [],
            }
        return result

    async def _post_new_api(self, http: httpx.AsyncClient, payload: dict[str, Any]) -> dict[str, Any]:
        resp = await http.post(self.api_url, json=payload, headers=self._headers())
        resp.raise_for_status()
        return self._parse_lambda_proxy_body(resp.json())

    async def _resolve_new_api_async(self, http: httpx.AsyncClient, sql: str) -> dict[str, Any]:
        result = await self._post_new_api(http, self._build_run_inline_payload(sql))
        if result.get("statusCode") == 429:
            return result

        response_type = str(result.get("type") or "").lower()
        if response_type != "running":
            return self._normalize_new_api_result(result)

        state = self._extract_running_state(result)
        if not state["space_id"] or not state["conversation_id"] or not state["message_id"]:
            return {
                "status": "error",
                "message": "Naksha returned an incomplete running state",
                "data": [],
            }

        for _ in range(self.max_polls):
            await asyncio.sleep(self.poll_interval_seconds)
            poll_result = await self._post_new_api(http, self._build_run_inline_status_payload(sql, state))
            if poll_result.get("statusCode") == 429:
                return poll_result
            poll_type = str(poll_result.get("type") or "").lower()
            if poll_type == "running":
                continue
            return self._normalize_new_api_result(poll_result)

        return {
            "status": "error",
            "message": "Naksha polling timed out",
            "data": [],
        }

    def _post_new_api_sync(self, payload: dict[str, Any]) -> dict[str, Any]:
        resp = requests.post(
            self.api_url,
            headers=self._headers(),
            json=payload,
            verify=self.verify_ssl,
            timeout=self.timeout_seconds,
        )
        resp.raise_for_status()
        return self._parse_lambda_proxy_body(resp.json())

    def _resolve_new_api_sync(self, sql: str) -> dict[str, Any]:
        result = self._post_new_api_sync(self._build_run_inline_payload(sql))
        if result.get("statusCode") == 429:
            return result

        response_type = str(result.get("type") or "").lower()
        if response_type != "running":
            return self._normalize_new_api_result(result)

        state = self._extract_running_state(result)
        if not state["space_id"] or not state["conversation_id"] or not state["message_id"]:
            return {
                "status": "error",
                "message": "Naksha returned an incomplete running state",
                "data": [],
            }

        for _ in range(self.max_polls):
            time.sleep(self.poll_interval_seconds)
            poll_result = self._post_new_api_sync(self._build_run_inline_status_payload(sql, state))
            if poll_result.get("statusCode") == 429:
                return poll_result
            poll_type = str(poll_result.get("type") or "").lower()
            if poll_type == "running":
                continue
            return self._normalize_new_api_result(poll_result)

        return {
            "status": "error",
            "message": "Naksha polling timed out",
            "data": [],
        }

    @staticmethod
    def _parse_lambda_proxy_body(payload: dict[str, Any]) -> dict[str, Any]:
        body = payload.get("body", payload)
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except json.JSONDecodeError:
                return payload
        if not isinstance(body, dict):
            return {}
        return body

    @staticmethod
    def _parse_choice_content(body: dict[str, Any]) -> dict[str, Any]:
        choices = body.get("choices", [])
        if not isinstance(choices, list) or not choices:
            return body

        content_str = choices[0].get("message", {}).get("content", "")
        if not content_str:
            return body

        try:
            parsed = json.loads(content_str)
            if isinstance(parsed, dict):
                return parsed
            return {"data": parsed}
        except (TypeError, json.JSONDecodeError):
            return {"raw_text": content_str}

    @staticmethod
    def _extract_rows(parsed: dict[str, Any]) -> list[dict[str, Any]]:
        rows = parsed.get("data", [])
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
        return []

    @staticmethod
    def _infer_table_status(parsed: dict[str, Any], rows: list[dict[str, Any]], naksha_status: str) -> str:
        if rows:
            return "available"

        if naksha_status == "error":
            return "unavailable"

        if naksha_status == "success":
            return "empty_or_filtered"

        text = " ".join(
            [
                str(parsed.get("answer") or ""),
                str(parsed.get("message") or ""),
                str(parsed.get("raw_text") or ""),
            ]
        ).lower()

        if re.search(r"(table|view).*(not available|not found|does not exist|unavailable)", text):
            return "unavailable"
        if "cannot run this query" in text:
            return "unavailable"

        return "unknown"

    def get_last_query_markers(self) -> dict[str, str]:
        return dict(self.last_query_markers)

    def query(
        self,
        sql_query: str,
        conversation_id: str | None = None,
        space_id: str | None = None,
        debug: bool = True,
    ) -> list[dict[str, Any]]:
        self._validate()
        if self.mock_mode:
            self.last_query_markers = {
                "naksha_status": "mock",
                "table_status": "mock",
            }
            if debug:
                logger.debug("[NAKSHA_DEBUG] mock_mode=true returning empty result set")
            return []

        self.last_query_markers = {
            "naksha_status": "unknown",
            "table_status": "unknown",
        }

        del conversation_id
        del space_id

        body = self._resolve_new_api_sync(sql_query)
        if body.get("statusCode") == 429:
            raise NakshaRateLimitError("Naksha rate limited")
        parsed = self._parse_choice_content(body)

        status = str(parsed.get("status", "unknown")).lower()
        naksha_status = status if status in {"success", "error"} else "unknown"
        rows = self._extract_rows(parsed)
        table_status = self._infer_table_status(parsed, rows, naksha_status)
        self.last_query_markers = {
            "naksha_status": naksha_status,
            "table_status": table_status,
        }

        if debug:
            debug_text = str(parsed.get("answer") or parsed.get("message") or parsed.get("raw_text") or "").replace(
                "\n", " "
            )
            logger.debug(
                "[NAKSHA_DEBUG] status=%s table=%s snippet=%s",
                naksha_status,
                table_status,
                debug_text[:30],
            )

        if naksha_status == "error":
            message = parsed.get("answer") or parsed.get("message") or "Naksha query error"
            raise NakshaError(str(message))

        return rows

    @retry(
        stop=stop_after_attempt(config.NAKSHA_MAX_RETRIES),
        wait=wait_exponential(multiplier=2, min=2, max=16),
        reraise=True,
    )
    async def execute_sql(
        self,
        sql: str,
        *,
        mock_data: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a SQL statement via the Naksha proxy.

        Args:
            sql: The SQL query string.
            mock_data: Returned as-is when USE_MOCK=true (caller provides fixture).

        Returns:
            Parsed list of row dicts from ``choices[0].message.content -> data[]``.

        Raises:
            NakshaError: On HTTP errors or unparseable responses.
        """
        if self.mock_mode:
            logger.debug("NakshaClient: USE_MOCK=true, returning mock fixture")
            self.last_query_markers = {
                "naksha_status": "mock",
                "table_status": "mock",
            }
            return mock_data or []

        if not self.api_url:
            raise NakshaError("NAKSHA_API_URL is not configured")

        logger.debug("backend=naksha transport=api url=%s", self.api_url)

        async with httpx.AsyncClient(timeout=self.timeout_seconds, verify=self.verify_ssl) as http:
            try:
                body = await self._resolve_new_api_async(http, sql)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    logger.warning(
                        "backend=naksha status=429 issue=%s action=fallback_databricks",
                        exc.response.text[:300],
                    )
                    return await self._execute_via_databricks_fallback(sql)
                logger.warning(
                    "backend=naksha status=%s issue=%s action=fallback_databricks",
                    exc.response.status_code,
                    exc.response.text[:300],
                )
                return await self._execute_via_databricks_fallback(sql)
            except httpx.RequestError as exc:
                logger.warning(
                    "backend=naksha request_error=%s action=fallback_databricks",
                    exc.__class__.__name__,
                )
                return await self._execute_via_databricks_fallback(sql)

        if body.get("statusCode") == 429:
            logger.warning("backend=naksha payload_status=429 action=fallback_databricks")
            return await self._execute_via_databricks_fallback(sql)

        parsed = self._parse_choice_content(body)
        status = str(parsed.get("status", "unknown")).lower()
        naksha_status = status if status in {"success", "error"} else "unknown"
        rows = self._extract_rows(parsed)
        table_status = self._infer_table_status(parsed, rows, naksha_status)

        if naksha_status == "error":
            issue = parsed.get("answer") or parsed.get("message") or parsed.get("raw_text") or "Naksha parsed error"
            logger.warning(
                "backend=naksha parsed_status=error issue=%s action=fallback_databricks",
                str(issue)[:500],
            )
            return await self._execute_via_databricks_fallback(sql)

        self.last_query_markers = {
            "naksha_status": naksha_status,
            "table_status": table_status,
        }
        return rows

    @staticmethod
    def _parse(body: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract data rows from the Naksha OpenAI-style response envelope.

        Expected shape:
            { "choices": [ { "message": { "content": "<JSON string>" } } ] }
        Where the JSON string parses to: { "data": [ {...}, ... ] }
        """
        try:
            content_str: str = body["choices"][0]["message"]["content"]
            content: dict[str, Any] = json.loads(content_str)
            rows: list[dict[str, Any]] = content.get("data", [])
            return rows
        except (KeyError, IndexError, json.JSONDecodeError, TypeError) as exc:
            raise NakshaError(f"Unparseable Naksha response: {exc}  body={str(body)[:200]}") from exc


class DatabricksClient:
    def __init__(self, *, enable_naksha: bool = True) -> None:
        self.naksha_client = NakshaClient() if enable_naksha else None
        self.sql_mock_mode = config._to_bool(os.getenv("DATABRICKS_SQL_MOCK_MODE"), False)
        self.host = str(os.getenv("DATABRICKS_HOST", "https://gevernova-nrc-workspace.cloud.databricks.com")).strip()
        self.token = str(os.getenv("DATABRICKS_TOKEN", "")).strip()
        self.http_path = str(os.getenv("DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/daff57b69fee5745")).strip()
        self.socket_timeout = int(os.getenv("DATABRICKS_SOCKET_TIMEOUT", "120"))
        self.last_query_backend = "unknown"

    def _validate(self) -> None:
        if self.sql_mock_mode:
            return
        missing: list[str] = []
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
        normalized = str(host or "").strip()
        normalized = re.sub(r"^https?://", "", normalized)
        return normalized.rstrip("/")

    @staticmethod
    def _sql_literal(value: Any) -> str:
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
        def replace(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in params:
                raise ValueError(f"Missing SQL parameter: {key}")
            return self._sql_literal(params[key])

        return _PARAM_PATTERN.sub(replace, query)

    @staticmethod
    def _expected_select_columns(query: str) -> list[str]:
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
        if not rows:
            return

        expected = DatabricksClient._expected_select_columns(query)
        if not expected:
            return

        actual_keys = {str(key).strip().lower() for key in rows[0].keys()}
        if not actual_keys:
            raise RuntimeError("Naksha returned rows without columns")

        matched = [column for column in expected if column in actual_keys]
        required_matches = max(1, min(3, len(expected)))
        if len(matched) < required_matches:
            raise RuntimeError("Naksha returned unexpected schema for SQL query")

    def query(
        self,
        query: str,
        params: dict[str, Any],
        debug: bool = True,
        validate_shape: bool = True,
    ) -> list[dict[str, Any]]:
        if self.naksha_client is None:
            raise RuntimeError("Naksha client is disabled for this DatabricksClient instance")
        rendered_query = self._render_query(query, params or {})
        rows = self.naksha_client.query(rendered_query, debug=debug)
        self.last_query_backend = "naksha"
        if validate_shape:
            self._validate_result_shape(rendered_query, rows)
        return rows

    def query_direct_sql(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        validate_shape: bool = True,
    ) -> list[dict[str, Any]]:
        if self.sql_mock_mode:
            self.last_query_backend = "mock_sql"
            logger.debug("[DEBUG] DATABRICKS_SQL_MOCK_MODE=true returning empty result set")
            return []

        self._validate()
        params = params or {}

        logger.debug(
            "[DEBUG] Connecting to Databricks host=%s http_path=%s",
            self._normalize_server_hostname(self.host),
            self.http_path,
        )

        conn: Any = None
        cursor: Any = None
        try:
            from databricks import sql  # noqa: PLC0415

            socket.setdefaulttimeout(30)
            conn = sql.connect(
                server_hostname=self._normalize_server_hostname(self.host),
                http_path=self.http_path,
                access_token=self.token,
                _socket_timeout=self.socket_timeout,
            )
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()

            cursor.execute(query, params)
            columns = [col[0] for col in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            result_rows = [dict(zip(columns, row, strict=False)) for row in rows]

            self.last_query_backend = "direct_sql"
            if validate_shape:
                self._validate_result_shape(query, result_rows)
            return result_rows
        except ImportError as exc:
            raise RuntimeError("databricks-sql-connector is required for direct SQL queries") from exc
        except Exception as exc:
            logger.exception("Databricks query failed")
            raise RuntimeError(f"Databricks query failed: {exc}") from exc
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:  # nosec B110
                    pass
            if conn is not None:
                try:
                    conn.close()
                except Exception:  # nosec B110
                    pass

    def get_last_query_markers(self) -> dict[str, str]:
        if self.naksha_client is None:
            return {
                "naksha_status": "fallback_databricks",
                "table_status": "unknown",
            }
        return self.naksha_client.get_last_query_markers()

    async def query_async(
        self,
        query: str,
        params: dict[str, Any],
        debug: bool = True,
        validate_shape: bool = True,
    ) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self.query, query, params, debug, validate_shape)

    async def query_direct_sql_async(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        validate_shape: bool = True,
    ) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self.query_direct_sql, query, params, validate_shape)
