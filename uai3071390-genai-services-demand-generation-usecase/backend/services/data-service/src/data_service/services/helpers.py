from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Awaitable, Callable
from typing import Any

from cachetools import TTLCache  # type: ignore[import-untyped]
from pydantic import BaseModel

from commons.logging import get_logger
from data_service.client import NakshaClient, NakshaRateLimitError

logger = get_logger(__name__)

# Column metadata is static — cache per table for 8 hours (28800 s), up to 50 tables.
_description_cache: TTLCache[str, dict[str, str]] = TTLCache(maxsize=50, ttl=28800)
_DESCRIPTION_LOOKUP_MAX_WAIT_SECONDS = max(
    0.0,
    float(os.getenv("DESCRIPTION_LOOKUP_MAX_WAIT_SECONDS", "5")),
)

type JsonRpcId = str | int | None


class JsonRpcRequest(BaseModel):
    jsonrpc: str
    id: JsonRpcId = None
    method: str
    params: dict[str, Any] | None = None


class JsonRpcRequestError(Exception):
    def __init__(self, code: int, message: str, data: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


def extract_jsonrpc_params(request: JsonRpcRequest, *, expected_method: str) -> dict[str, Any]:
    if request.jsonrpc != "2.0":
        raise JsonRpcRequestError(
            -32600,
            "Invalid Request",
            {"reason": "jsonrpc must be '2.0'"},
        )
    if request.method != expected_method:
        raise JsonRpcRequestError(
            -32601,
            "Method not found",
            {"method": request.method, "expected_method": expected_method},
        )
    return dict(request.params or {})


def build_jsonrpc_result(request_id: JsonRpcId, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result,
    }


def build_jsonrpc_error(
    request_id: JsonRpcId,
    code: int,
    message: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    error: dict[str, Any] = {
        "code": code,
        "message": message,
    }
    if data is not None:
        error["data"] = data

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": error,
    }


def normalize_metadata_filter_keys(
    metadata_filters: dict[str, Any] | None,
    *,
    key_normalizer: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in (metadata_filters or {}).items():
        normalized_key = str(key).strip()
        if key_normalizer is not None:
            normalized_key = key_normalizer(normalized_key)
        normalized[normalized_key] = value
    return normalized


def normalize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def normalize_rows(
    rows: list[dict[str, Any]],
    columns: tuple[str, ...] | None = None,
    *,
    deduplicate: bool = False,
) -> list[dict[str, Any]]:
    normalized_rows: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()

    for row in rows:
        if columns is None:
            normalized_row: dict[str, Any] = {str(key): normalize_value(value) for key, value in row.items()}
            row_key: tuple[Any, ...] = tuple((key, normalized_row[key]) for key in sorted(normalized_row))
        else:
            normalized_row = {column: normalize_value(row.get(column)) for column in columns}
            row_key = tuple(normalized_row.get(column) for column in columns)

        if deduplicate:
            if row_key in seen:
                continue
            seen.add(row_key)

        normalized_rows.append(normalized_row)

    return normalized_rows


def sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int | float):
        return str(value)
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


def render_query(query: str, params: dict[str, Any]) -> str:
    rendered = query
    for key, value in params.items():
        rendered = rendered.replace(f":{key}", sql_literal(value))
    return rendered


def build_select_clause(select_columns: str | dict[str, tuple[str, ...]]) -> str:
    if isinstance(select_columns, str):
        return select_columns

    select_exprs: list[str] = []
    for table_alias, columns in select_columns.items():
        select_exprs.extend(f"{table_alias}.{column}" for column in columns)
    return ",\n            ".join(select_exprs)


def build_read_query(
    *,
    select_columns: str | dict[str, tuple[str, ...]],
    from_clause: str,
    serial_query_column: str,
    serial_param_name: str,
    serial_value: str,
    fixed_filters: tuple[tuple[str, str, Any], ...] = (),
    metadata_filters: dict[str, Any] | None,
    metadata_filter_config: dict[str, dict[str, str]],
    error_factory: Callable[[str, str], Exception],
    join_clauses: tuple[str, ...] = (),
    order_by_clause: str | None = None,
    limit: int = 500,
    distinct: bool = False,
) -> tuple[str, dict[str, Any]]:
    select_clause = build_select_clause(select_columns)
    params: dict[str, Any] = {}
    filters: list[str] = []

    for query_filter, param_name, value in fixed_filters:
        filters.append(query_filter)
        params[param_name] = value

    params[serial_param_name] = serial_value
    filters.append(f"{serial_query_column} = :{serial_param_name}")

    for index, (field_name, value) in enumerate((metadata_filters or {}).items()):
        normalized_name = str(field_name).strip()
        filter_config = metadata_filter_config.get(normalized_name)
        if filter_config is None:
            raise error_factory("INVALID_INPUT", f"Unsupported metadata field: {normalized_name}")
        if value is None or (isinstance(value, str) and value.strip() == ""):
            raise error_factory("INVALID_INPUT", f"metadata_filters.{normalized_name} cannot be empty")

        query_column = filter_config["query_column"]
        operator = filter_config["operator"]
        param_name = f"metadata_{index}"
        filters.append(f"{query_column} {operator} :{param_name}")

        if operator.upper() == "ILIKE":
            params[param_name] = f"%{str(value).strip()}%"
        elif isinstance(value, str):
            params[param_name] = value.strip()
        else:
            params[param_name] = value

    query_lines = [
        "SELECT DISTINCT" if distinct else "SELECT",
        f"    {select_clause}",
        f"FROM {from_clause}",
    ]
    query_lines.extend(join_clauses)
    query_lines.append(f"WHERE {' AND '.join(filters)}")
    if order_by_clause:
        query_lines.append(f"ORDER BY {order_by_clause}")
    query_lines.append(f"LIMIT {limit}")
    return "\n".join(query_lines), params


def description_for(column_name: str, descriptions: dict[str, str]) -> str:
    target = str(column_name or "").strip().lower()
    if not target:
        return ""
    for key, value in descriptions.items():
        if str(key or "").strip().lower() == target:
            return str(value or "")
    return ""


def extract_result_ids(rows: list[dict[str, Any]], candidate_keys: tuple[str, ...]) -> list[str]:
    normalized_candidates = {key.strip().lower() for key in candidate_keys if key and key.strip()}
    result_ids: list[str] = []

    for row in rows:
        if not isinstance(row, dict):
            continue

        matched_value: Any = None
        for key, value in row.items():
            if str(key).strip().lower() in normalized_candidates:
                matched_value = value
                break

        result_ids.append(str(matched_value or ""))

    return result_ids


def row_matches_candidate_keys(row: dict[str, Any], target_value: str, candidate_keys: tuple[str, ...]) -> bool:
    normalized_target = str(target_value or "").strip().lower()
    if not normalized_target:
        return False

    for candidate_key in candidate_keys:
        for row_key, row_value in row.items():
            if str(row_key).strip().lower() == candidate_key.lower():
                return str(row_value or "").strip().lower() == normalized_target
    return False


def filter_rows_by_candidate_keys(
    rows: list[dict[str, Any]],
    target_value: str,
    candidate_keys: tuple[str, ...],
) -> list[dict[str, Any]]:
    return [row for row in rows if row_matches_candidate_keys(row, target_value, candidate_keys)]


def is_rate_limit_error(exc: Exception) -> bool:
    if isinstance(exc, NakshaRateLimitError):
        return True
    text = str(exc)
    lower = text.lower()
    return "429" in text or "too many requests" in lower


async def execute_with_retries(
    operation: Callable[[], Awaitable[list[dict[str, Any]]]],
    *,
    max_attempts: int,
    backoff_seconds: float,
    retry_if: Callable[[Exception], bool],
) -> list[dict[str, Any]]:
    attempts = max(1, int(max_attempts))
    backoff = max(0.0, float(backoff_seconds))

    for attempt in range(1, attempts + 1):
        try:
            return await operation()
        except Exception as exc:
            if attempt < attempts and retry_if(exc):
                await asyncio.sleep(backoff * attempt)
                continue
            raise

    return []


async def merge_table_column_descriptions(
    table_names: tuple[str, ...],
    *,
    db_client: Any,
) -> dict[str, str]:
    from data_service.schema_metadata import get_table_column_descriptions

    async def _fetch_table_descriptions(table_name: str) -> dict[str, str]:
        if table_name in _description_cache:
            logger.info(
                "purpose=description_lookup stage=cache_hit table=%s empty=%s",
                table_name,
                len(_description_cache[table_name]) == 0,
            )
            return dict(_description_cache[table_name])

        started = time.perf_counter()
        logger.info("purpose=description_lookup stage=start table=%s", table_name)
        try:
            descriptions: dict[str, str] = await get_table_column_descriptions(table_name, db_client=db_client)
            _description_cache[table_name] = descriptions
            logger.info(
                "purpose=description_lookup stage=done table=%s column_count=%s duration_ms=%s",
                table_name,
                len(descriptions),
                int((time.perf_counter() - started) * 1000),
            )
            return descriptions
        except Exception as exc:
            logger.warning(
                "purpose=description_lookup stage=failed table=%s error=%s duration_ms=%s",
                table_name,
                exc.__class__.__name__,
                int((time.perf_counter() - started) * 1000),
            )
            raise

    description_sets = await asyncio.gather(
        *(_fetch_table_descriptions(table_name) for table_name in table_names),
        return_exceptions=True,
    )
    merged: dict[str, str] = {}
    for table_name, description_set in zip(table_names, description_sets, strict=False):
        if isinstance(description_set, Exception):
            logger.warning(
                "description lookup failed table=%s error=%s",
                table_name,
                description_set.__class__.__name__,
            )
            continue
        merged.update(description_set)  # type: ignore[arg-type]
    return merged


def clone_naksha_client(db_client: Any) -> NakshaClient:
    bearer_token = getattr(db_client, "_token", "")
    return NakshaClient(bearer_token=bearer_token)


def isolate_query_client(query_client: Any) -> Any:
    if isinstance(query_client, NakshaClient):
        return clone_naksha_client(query_client)
    return query_client


async def execute_read_with_descriptions(
    *,
    sql: str,
    description_tables: tuple[str, ...],
    query_client: NakshaClient,
    max_attempts: int,
    backoff_seconds: float,
    retry_if: Callable[[Exception], bool],
    read_purpose: str = "main_read",
) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, str]]:
    main_client = isolate_query_client(query_client)

    async def _execute_main_read() -> tuple[list[dict[str, Any]], dict[str, str]]:
        started = time.perf_counter()
        logger.info("purpose=%s stage=start", read_purpose)
        try:
            rows = await execute_with_retries(
                lambda: main_client.execute_sql(sql),
                max_attempts=max_attempts,
                backoff_seconds=backoff_seconds,
                retry_if=retry_if,
            )
            logger.info(
                "purpose=%s stage=done row_count=%s duration_ms=%s",
                read_purpose,
                len(rows),
                int((time.perf_counter() - started) * 1000),
            )
            return rows, main_client.get_last_query_markers()
        except Exception as exc:
            logger.warning(
                "purpose=%s stage=failed error=%s duration_ms=%s",
                read_purpose,
                exc.__class__.__name__,
                int((time.perf_counter() - started) * 1000),
            )
            raise

    metadata_client = isolate_query_client(query_client)
    rows_task = asyncio.create_task(_execute_main_read())
    descriptions_task = asyncio.create_task(
        merge_table_column_descriptions(
            description_tables,
            db_client=metadata_client,
        )
    )

    try:
        rows, query_markers = await rows_task
    except Exception:
        descriptions_task.cancel()
        await asyncio.gather(descriptions_task, return_exceptions=True)
        raise

    if not rows:
        logger.info("purpose=description_lookup stage=cancelled reason=empty_main_result")
        descriptions_task.cancel()
        await asyncio.gather(descriptions_task, return_exceptions=True)
        return rows, {}, query_markers

    try:
        if _DESCRIPTION_LOOKUP_MAX_WAIT_SECONDS == 0:
            descriptions_task.cancel()
            await asyncio.gather(descriptions_task, return_exceptions=True)
            descriptions = {}
        else:
            descriptions = await asyncio.wait_for(
                descriptions_task,
                timeout=_DESCRIPTION_LOOKUP_MAX_WAIT_SECONDS,
            )
    except asyncio.TimeoutError:
        logger.warning(
            "description aggregation timed out timeout_seconds=%s",
            _DESCRIPTION_LOOKUP_MAX_WAIT_SECONDS,
        )
        await asyncio.gather(descriptions_task, return_exceptions=True)
        descriptions = {}
    except Exception as exc:
        logger.warning(
            "description aggregation failed error=%s",
            exc.__class__.__name__,
        )
        descriptions = {}

    return rows, descriptions, query_markers


def build_input_filter_columns(
    *,
    serial_input_key: str,
    serial_description_column: str,
    metadata_filters: dict[str, Any],
    metadata_filter_config: dict[str, dict[str, str]],
    descriptions: dict[str, str],
) -> dict[str, str]:
    input_filter_columns = {
        serial_input_key: description_for(serial_description_column, descriptions),
    }
    for metadata_key in metadata_filters:
        mapped_column = metadata_filter_config[metadata_key]["description_column"]
        input_filter_columns[f"metadata_filters.{metadata_key}"] = description_for(mapped_column, descriptions)
    return input_filter_columns


def build_output_columns(columns: tuple[str, ...], descriptions: dict[str, str]) -> dict[str, str]:
    return {column: description_for(column, descriptions) for column in columns}


def build_detected_output_columns(rows: list[dict[str, Any]], descriptions: dict[str, str]) -> dict[str, str]:
    if not rows:
        return {}
    return {str(column): description_for(str(column), descriptions) for column in rows[0].keys()}


def build_standard_read_response(
    *,
    serial_number: str | None = None,
    identifier_fields: dict[str, Any] | None = None,
    user: str,
    request_id: str | None,
    metadata_filters: dict[str, Any],
    data: list[dict[str, Any]],
    input_filter_columns: dict[str, str],
    output_columns: dict[str, str],
    query_markers: dict[str, str],
    execution_time_ms: int,
) -> dict[str, Any]:
    metadata: dict[str, Any] = dict(identifier_fields or {})
    if serial_number is not None:
        metadata.setdefault("serial_number", serial_number)
    metadata.update(
        {
            "user": user,
            "request_id": request_id,
            "metadata_filters": metadata_filters,
            "input_filter_columns": input_filter_columns,
            "output_columns": output_columns,
            "naksha_status": query_markers.get("naksha_status", "unknown"),
            "table_status": query_markers.get("table_status", "unknown"),
            "execution_time_ms": execution_time_ms,
        }
    )
    return {
        "status": "success",
        "record_count": len(data),
        "data": data,
        "metadata": metadata,
    }
