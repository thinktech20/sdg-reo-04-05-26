from __future__ import annotations

import logging
import os
import time
from typing import Any

from commons.logging import get_logger
from data_service.client import NakshaClient
from data_service.logging_utils import log_query_event
from data_service.services.helpers import (
    build_input_filter_columns,
    build_output_columns,
    build_read_query,
    build_standard_read_response,
    execute_read_with_descriptions,
    is_rate_limit_error,
    normalize_metadata_filter_keys,
    normalize_rows,
    render_query,
)

logger = get_logger(__name__)
LOG_SQL_QUERIES = os.getenv("LOG_SQL_QUERIES", "false").strip().lower() in {"1", "true", "yes", "on"}


HEATMAP_CATALOG = os.getenv("CATALOG", "vgpp")
HEATMAP_SCHEMA = os.getenv("HEATMAP_SCHEMA", "fsr_std_views")
HEATMAP_TABLE = os.getenv("HEATMAP_TABLE", "fsr_unit_risk_matrix_view")

HEATMAP_VIEW = os.getenv("HEATMAP_VIEW", f"{HEATMAP_CATALOG}.{HEATMAP_SCHEMA}.{HEATMAP_TABLE}")


HEATMAP_SELECT_COLUMNS = """
equipment_type,
technology_group,
technology,
component,
persona,
issue_grouping,
issue_name,
issue_prompt,
severity_criteria_0_no_data AS severity_criteria_0,
severity_criteria_1_light AS severity_criteria_1,
severity_criteria_2_medium AS severity_criteria_2,
severity_criteria_3_heavy AS severity_criteria_3,
severity_criteria_4_immediate AS severity_criteria_4,
applicable_data_objects
""".strip()
HEATMAP_FILTER_QUERY_COLUMN = "UPPER(equipment_type)"
HEATMAP_FILTER_PARAM_NAME = "equipment_type"
HEATMAP_DESCRIPTION_TABLES: tuple[str, ...] = (HEATMAP_VIEW,)
HEATMAP_ORDER_BY_CLAUSE = "issue_name"
HEATMAP_OUTPUT_COLUMNS: tuple[str, ...] = (
    "equipment_type",
    "technology_group",
    "technology",
    "component",
    "persona",
    "issue_grouping",
    "issue_name",
    "issue_prompt",
    "severity_criteria_0",
    "severity_criteria_1",
    "severity_criteria_2",
    "severity_criteria_3",
    "severity_criteria_4",
    "applicable_data_objects",
)
HEATMAP_METADATA_FILTER_CONFIG: dict[str, dict[str, str]] = {
    "component": {"query_column": "component", "description_column": "component", "operator": "ILIKE"},
}


class HeatmapServiceError(Exception):
    def __init__(self, error_code: str, message: str, request_id: str | None = None):
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.request_id = request_id


def _validate_equipment_type(value: str) -> str:
    normalized = str(value or "").strip().upper()
    if normalized not in {"GEN", "GT"}:
        raise HeatmapServiceError("INVALID_INPUT", "equipment_type must be GEN or GT")
    return normalized


def _validate_persona(value: str) -> str:
    normalized = str(value or "").strip().upper()
    if normalized not in {"REL", "OE"}:
        raise HeatmapServiceError("INVALID_INPUT", "persona must be REL or OE")
    return normalized


def _is_rate_limit_error(exc: Exception) -> bool:
    return is_rate_limit_error(exc)


async def read_heatmap(
    equipment_type: str,
    persona: str,
    requesting_user: str,
    serial_number: str | None = None,
    metadata_filters: dict[str, Any] | None = None,
    request_id: str | None = None,
    db_client: NakshaClient | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    del kwargs
    normalized_equipment_type = _validate_equipment_type(equipment_type)
    normalized_persona = _validate_persona(persona)
    if metadata_filters is not None and not isinstance(metadata_filters, dict):
        raise HeatmapServiceError("INVALID_INPUT", "metadata_filters must be a dictionary")

    normalized_user = str(requesting_user or "unknown").strip() or "unknown"
    normalized_request_id = str(request_id).strip() if request_id is not None else None
    normalized_serial_number = str(serial_number).strip() if serial_number is not None else None
    normalized_metadata_filters = normalize_metadata_filter_keys(
        metadata_filters,
        key_normalizer=str.lower,
    )

    if "persona" in normalized_metadata_filters:
        raise HeatmapServiceError("INVALID_INPUT", "persona must be provided as a top-level argument")

    client = db_client or NakshaClient()
    started = time.perf_counter()
    error: str | None = None
    error_code: str | None = None
    query_markers: dict[str, str] = {
        "naksha_status": "unknown",
        "table_status": "unknown",
    }

    try:
        query, params = build_read_query(
            select_columns=HEATMAP_SELECT_COLUMNS,
            from_clause=HEATMAP_VIEW,
            serial_query_column=HEATMAP_FILTER_QUERY_COLUMN,
            serial_param_name=HEATMAP_FILTER_PARAM_NAME,
            serial_value=normalized_equipment_type,
            fixed_filters=(("UPPER(persona) = :persona", "persona", normalized_persona),),
            metadata_filters=normalized_metadata_filters,
            metadata_filter_config=HEATMAP_METADATA_FILTER_CONFIG,
            error_factory=HeatmapServiceError,
            order_by_clause=HEATMAP_ORDER_BY_CLAUSE,
        )
        rendered_query = render_query(query, params)
        if LOG_SQL_QUERIES:
            logger.info(
                "heatmap sql query request_id=%s serial_number=%s equipment_type=%s persona=%s metadata_filters=%s query=%s",
                normalized_request_id,
                normalized_serial_number,
                normalized_equipment_type,
                normalized_persona,
                normalized_metadata_filters,
                rendered_query,
            )
        elif logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "heatmap sql query request_id=%s serial_number=%s equipment_type=%s persona=%s query=%s",
                normalized_request_id,
                normalized_serial_number,
                normalized_equipment_type,
                normalized_persona,
                rendered_query,
            )

        max_attempts = max(1, int(os.getenv("HEATMAP_MAX_RETRIES", "3")))
        backoff_seconds = float(os.getenv("HEATMAP_RETRY_BACKOFF_SECONDS", "1.5"))

        rows, all_descriptions, query_markers = await execute_read_with_descriptions(
            sql=rendered_query,
            description_tables=HEATMAP_DESCRIPTION_TABLES,
            query_client=client,
            max_attempts=max_attempts,
            backoff_seconds=backoff_seconds,
            retry_if=_is_rate_limit_error,
        )

        normalized_rows = normalize_rows(rows, HEATMAP_OUTPUT_COLUMNS)

        if not normalized_rows:
            raise HeatmapServiceError(
                "NO_DATA",
                f"No records found for equipment_type={normalized_equipment_type} and persona={normalized_persona}",
                request_id=normalized_request_id,
            )

        input_filter_columns = build_input_filter_columns(
            serial_input_key=HEATMAP_FILTER_PARAM_NAME,
            serial_description_column="equipment_type",
            metadata_filters=normalized_metadata_filters,
            metadata_filter_config=HEATMAP_METADATA_FILTER_CONFIG,
            descriptions=all_descriptions,
        )
        input_filter_columns["persona"] = all_descriptions.get("persona", "")

        output_columns = build_output_columns(HEATMAP_OUTPUT_COLUMNS, all_descriptions)

        return build_standard_read_response(
            serial_number=normalized_serial_number,
            identifier_fields={
                "equipment_type": normalized_equipment_type,
                "persona": normalized_persona,
            },
            user=normalized_user,
            request_id=normalized_request_id,
            metadata_filters=normalized_metadata_filters,
            data=normalized_rows,
            input_filter_columns=input_filter_columns,
            output_columns=output_columns,
            query_markers=query_markers,
            execution_time_ms=int((time.perf_counter() - started) * 1000),
        )
    except HeatmapServiceError as exc:
        error = exc.message
        error_code = exc.error_code
        raise
    except Exception as exc:
        lower_error = str(exc).lower()
        if _is_rate_limit_error(exc):
            error = "HEATMAP upstream rate limited (429)"
            error_code = "RATE_LIMITED"
            raise HeatmapServiceError("RATE_LIMITED", error, request_id=normalized_request_id) from exc
        if "permission" in lower_error or "unauthorized" in lower_error:
            error = "Access denied by Unity Catalog permissions"
            error_code = "UNAUTHORIZED"
            raise HeatmapServiceError("UNAUTHORIZED", error, request_id=normalized_request_id) from exc
        logger.exception(
            "heatmap service unexpected error request_id=%s equipment_type=%s persona=%s",
            normalized_request_id,
            normalized_equipment_type,
            normalized_persona,
        )
        error = "An internal error occurred"
        error_code = "SYSTEM_ERROR"
        raise HeatmapServiceError("SYSTEM_ERROR", error, request_id=normalized_request_id) from exc
    finally:
        duration_ms = int((time.perf_counter() - started) * 1000)
        log_query_event(
            logger_name="data-svc",
            event="read_heatmap",
            payload={
                "user": normalized_user,
                "serial_number": normalized_serial_number,
                "equipment_type": normalized_equipment_type,
                "persona": normalized_persona,
                "request_id": normalized_request_id,
                "metadata_filters": normalized_metadata_filters,
                "errors": error,
                "error_code": error_code,
                "record_count": len(normalized_rows) if "normalized_rows" in locals() else 0,
                "naksha_status": query_markers.get("naksha_status", "unknown"),
                "table_status": query_markers.get("table_status", "unknown"),
                "duration_ms": duration_ms,
            },
        )
