from __future__ import annotations

import logging
import os
import time
from typing import Any

from commons.logging import get_logger
from data_service.client import NakshaClient
from data_service.logging_utils import log_read_service_event
from data_service.services.helpers import (
    build_detected_output_columns,
    build_input_filter_columns,
    build_read_query,
    build_standard_read_response,
    execute_read_with_descriptions,
    extract_result_ids,
    filter_rows_by_candidate_keys,
    is_rate_limit_error,
    normalize_metadata_filter_keys,
    normalize_rows,
    render_query,
)

logger = get_logger(__name__)
LOG_SQL_QUERIES = os.getenv("LOG_SQL_QUERIES", "false").strip().lower() in {"1", "true", "yes", "on"}


PRISM_CATALOG = os.getenv("CATALOG", "vgpp")
PRISM_SCHEMA = os.getenv("PRISM_SCHEMA", "seg_std_views")
PRISM_SOT_TABLE = os.getenv("PRISM_SOT_TABLE", "seg_fmea_wo_models_gen_psot")

PRISM_SOT_VIEW = os.getenv("PRISM_SOT_VIEW", f"{PRISM_CATALOG}.{PRISM_SCHEMA}.{PRISM_SOT_TABLE}")


PRISM_SELECT_COLUMNS = "*"
PRISM_SERIAL_QUERY_COLUMN = "TURBINE_NUMBER"
PRISM_SERIAL_RESULT_KEYS: tuple[str, ...] = ("TURBINE_NUMBER", "turbine_number", "serial_number")
PRISM_SERIAL_PARAM_NAME = "serial_number"
PRISM_DESCRIPTION_TABLES: tuple[str, ...] = (PRISM_SOT_VIEW,)
PRISM_ORDER_BY_CLAUSE = "REF_DATE DESC"
PRISM_METADATA_FILTER_CONFIG: dict[str, dict[str, str]] = {
    "model_id": {"query_column": "MODEL_ID", "description_column": "MODEL_ID", "operator": "="},
    "model_desc": {"query_column": "MODEL_DESC", "description_column": "MODEL_DESC", "operator": "ILIKE"},
    "risk_rule": {"query_column": "RISK_RULE", "description_column": "RISK_RULE", "operator": "ILIKE"},
    "modified_by": {"query_column": "MODIFIED_BY", "description_column": "MODIFIED_BY", "operator": "ILIKE"},
    "modified_date": {"query_column": "MODIFIED_DATE", "description_column": "MODIFIED_DATE", "operator": "="},
    "ref_date": {"query_column": "REF_DATE", "description_column": "REF_DATE", "operator": "="},
    "gen_cod": {"query_column": "GEN_COD", "description_column": "GEN_COD", "operator": "="},
    "last_rewind": {"query_column": "LAST_REWIND", "description_column": "LAST_REWIND", "operator": "="},
    "risk_profile": {"query_column": "RISK_PROFILE", "description_column": "RISK_PROFILE", "operator": "ILIKE"},
    "eec": {"query_column": "EEC", "description_column": "EEC", "operator": "="},
    "gen_vintage": {"query_column": "GEN_VINTAGE", "description_column": "GEN_VINTAGE", "operator": "="},
    "stag_code": {"query_column": "STAG_CODE", "description_column": "STAG_CODE", "operator": "="},
    "component": {"query_column": "COMPONENT", "description_column": "COMPONENT", "operator": "="},
}


class PrismServiceError(Exception):
    def __init__(self, error_code: str, message: str, request_id: str | None = None):
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.request_id = request_id


def _is_rate_limit_error(exc: Exception) -> bool:
    return is_rate_limit_error(exc)


async def read_prism_by_serial(
    serial_number: str,
    requesting_user: str,
    metadata_filters: dict[str, Any] | None = None,
    request_id: str | None = None,
    db_client: NakshaClient | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    del kwargs
    normalized_serial_number = str(serial_number or "").strip()
    if not normalized_serial_number:
        raise PrismServiceError("INVALID_INPUT", "serial_number is required")
    if metadata_filters is not None and not isinstance(metadata_filters, dict):
        raise PrismServiceError("INVALID_INPUT", "metadata_filters must be a dictionary")

    normalized_user = str(requesting_user or "unknown").strip() or "unknown"
    normalized_request_id = str(request_id).strip() if request_id is not None else None
    normalized_metadata_filters = normalize_metadata_filter_keys(
        metadata_filters,
        key_normalizer=str.lower,
    )

    client = db_client or NakshaClient()
    started = time.perf_counter()
    error: str | None = None
    error_code: str | None = None
    result_ids: list[str] = []
    query_markers: dict[str, str] = {
        "naksha_status": "unknown",
        "table_status": "unknown",
    }

    try:
        query, params = build_read_query(
            select_columns=PRISM_SELECT_COLUMNS,
            from_clause=PRISM_SOT_VIEW,
            serial_query_column=PRISM_SERIAL_QUERY_COLUMN,
            serial_param_name=PRISM_SERIAL_PARAM_NAME,
            serial_value=normalized_serial_number,
            metadata_filters=normalized_metadata_filters,
            metadata_filter_config=PRISM_METADATA_FILTER_CONFIG,
            error_factory=PrismServiceError,
            order_by_clause=PRISM_ORDER_BY_CLAUSE,
        )
        rendered_query = render_query(query, params)
        if LOG_SQL_QUERIES:
            logger.info(
                "prism sql query request_id=%s serial_number=%s query=%s",
                normalized_request_id,
                normalized_serial_number,
                rendered_query,
            )
        elif logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "prism sql query request_id=%s serial_number=%s query=%s",
                normalized_request_id,
                normalized_serial_number,
                rendered_query,
            )

        max_attempts = max(1, int(os.getenv("PRISM_MAX_RETRIES", "3")))
        backoff_seconds = float(os.getenv("PRISM_RETRY_BACKOFF_SECONDS", "1.5"))

        rows, all_descriptions, query_markers = await execute_read_with_descriptions(
            sql=rendered_query,
            description_tables=PRISM_DESCRIPTION_TABLES,
            query_client=client,
            max_attempts=max_attempts,
            backoff_seconds=backoff_seconds,
            retry_if=_is_rate_limit_error,
        )

        # Defensive guard: keep only rows matching requested serial.
        rows = filter_rows_by_candidate_keys(rows, normalized_serial_number, PRISM_SERIAL_RESULT_KEYS)

        if not rows:
            raise PrismServiceError("SERIAL_NOT_FOUND", f"No records found for serial {serial_number}")

        result_ids = extract_result_ids(rows, PRISM_SERIAL_RESULT_KEYS)

        normalized_rows = normalize_rows(rows)

        input_filter_columns = build_input_filter_columns(
            serial_input_key=PRISM_SERIAL_PARAM_NAME,
            serial_description_column=PRISM_SERIAL_QUERY_COLUMN,
            metadata_filters=normalized_metadata_filters,
            metadata_filter_config=PRISM_METADATA_FILTER_CONFIG,
            descriptions=all_descriptions,
        )

        output_columns = build_detected_output_columns(normalized_rows, all_descriptions)

        return build_standard_read_response(
            serial_number=normalized_serial_number,
            user=normalized_user,
            request_id=normalized_request_id,
            metadata_filters=normalized_metadata_filters,
            data=normalized_rows,
            input_filter_columns=input_filter_columns,
            output_columns=output_columns,
            query_markers=query_markers,
            execution_time_ms=int((time.perf_counter() - started) * 1000),
        )
    except PrismServiceError as exc:
        error = exc.message
        error_code = exc.error_code
        raise
    except Exception as exc:
        lower_error = str(exc).lower()
        if _is_rate_limit_error(exc):
            error = "PRISM upstream rate limited (429)"
            error_code = "RATE_LIMITED"
            raise PrismServiceError("RATE_LIMITED", error, request_id=normalized_request_id) from exc
        if "permission" in lower_error or "unauthorized" in lower_error:
            error = "Access denied by Unity Catalog permissions"
            error_code = "UNAUTHORIZED"
            raise PrismServiceError("UNAUTHORIZED", error, request_id=normalized_request_id) from exc
        logger.exception(
            "prism service unexpected error request_id=%s serial_number=%s",
            normalized_request_id,
            normalized_serial_number,
        )
        error = "An internal error occurred"
        error_code = "SYSTEM_ERROR"
        raise PrismServiceError("SYSTEM_ERROR", error, request_id=normalized_request_id) from exc
    finally:
        duration_ms = int((time.perf_counter() - started) * 1000)
        log_read_service_event(
            event="read_prism_by_serial",
            user=normalized_user,
            serial_number=normalized_serial_number or None,
            request_id=normalized_request_id,
            metadata_filters=normalized_metadata_filters,
            error=error,
            error_code=error_code,
            result_ids=result_ids,
            duration_ms=duration_ms,
            naksha_status=query_markers.get("naksha_status", "unknown"),
            table_status=query_markers.get("table_status", "unknown"),
        )
