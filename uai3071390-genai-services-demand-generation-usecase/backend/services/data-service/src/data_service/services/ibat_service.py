from __future__ import annotations

import logging
import os
import time
from typing import Any

from commons.logging import get_logger
from data_service.client import NakshaClient
from data_service.logging_utils import log_read_service_event
from data_service.mock_services.equipment import MOCK_INSTALL_BASE
from data_service.services.helpers import (
    build_input_filter_columns,
    build_output_columns,
    build_read_query,
    build_standard_read_response,
    execute_read_with_descriptions,
    extract_result_ids,
    is_rate_limit_error,
    normalize_metadata_filter_keys,
    normalize_rows,
    render_query,
)

logger = get_logger(__name__)
LOG_SQL_QUERIES = os.getenv("LOG_SQL_QUERIES", "false").strip().lower() in {"1", "true", "yes", "on"}

IBAT_CATALOG = os.getenv("CATALOG", "vgpp")
IBAT_SCHEMA = os.getenv("IBAT_SCHEMA", "prm_std_views")

IBAT_EQUIPMENT_TABLE = os.getenv("IBAT_EQUIPMENT_TABLE", "IBAT_EQUIPMENT_MST")
IBAT_PLANT_TABLE = os.getenv("IBAT_PLANT_TABLE", "IBAT_PLANT_MST")
IBAT_TRAIN_TABLE = os.getenv("IBAT_TRAIN_TABLE", "ibat_train_mst")

IBAT_EQUIPMENT_VIEW = os.getenv("IBAT_EQUIPMENT_VIEW", f"{IBAT_CATALOG}.{IBAT_SCHEMA}.{IBAT_EQUIPMENT_TABLE}")
IBAT_PLANT_VIEW = os.getenv("IBAT_PLANT_VIEW", f"{IBAT_CATALOG}.{IBAT_SCHEMA}.{IBAT_PLANT_TABLE}")
IBAT_TRAIN_VIEW = os.getenv("IBAT_TRAIN_VIEW", f"{IBAT_CATALOG}.{IBAT_SCHEMA}.{IBAT_TRAIN_TABLE}")

IBAT_EQUIPMENT_COLUMNS: tuple[str, ...] = (
    "equipment_type",
    "equipment_name",
    "sales_channel",
    "equipment_sys_id",
    "contract_type",
    "equipment_code",
    "equipment_class",
    "block_sys_id_fk",
    "plant_sys_id_fk",
    "train_sys_id_fk",
    "actualized_flag",
    "duty_cycle",
    "equip_serial_number",
    "rotor_rewind",
    "stator_rewind",
    "cooling_system",
    "equipment_model",
    "excitation_system",
    "equipment_status",
    "present_apparent_pwr_mva",
    "present_voltage_v",
    "speed_rpm",
    "equipment_comm_date",
    "csa_contract_number",
    "er_support_level",
)
IBAT_PLANT_COLUMNS: tuple[str, ...] = (
    "site_customer_name",
    "plant_name",
    "site_country",
    "site_state",
    "hyp_sub_region",
    "ps_pole",
    "cust_gegul_name",
    "industry",
)
IBAT_TRAIN_COLUMNS: tuple[str, ...] = ("fuel_type",)
IBAT_SELECT_COLUMNS: dict[str, tuple[str, ...]] = {
    "e": IBAT_EQUIPMENT_COLUMNS,
    "p": IBAT_PLANT_COLUMNS,
    "t": IBAT_TRAIN_COLUMNS,
}
IBAT_OUTPUT_COLUMNS: tuple[str, ...] = (*IBAT_EQUIPMENT_COLUMNS, *IBAT_PLANT_COLUMNS, *IBAT_TRAIN_COLUMNS)
IBAT_SERIAL_QUERY_COLUMN = "e.equip_serial_number"
IBAT_SERIAL_RESULT_KEYS: tuple[str, ...] = ("equip_serial_number", "serial_number")
IBAT_SERIAL_PARAM_NAME = "equip_serial_number"
IBAT_DESCRIPTION_TABLES: tuple[str, ...] = (IBAT_EQUIPMENT_VIEW, IBAT_PLANT_VIEW, IBAT_TRAIN_VIEW)
IBAT_JOIN_CLAUSES: tuple[str, ...] = (
    f"LEFT JOIN {IBAT_PLANT_VIEW} p ON e.plant_sys_id_fk = p.plant_sys_id",
    f"LEFT JOIN {IBAT_TRAIN_VIEW} t ON e.train_sys_id_fk = t.train_sys_id",
)
IBAT_METADATA_FILTER_CONFIG: dict[str, dict[str, str]] = {
    "equipment_sys_id": {
        "query_column": "e.equipment_sys_id",
        "description_column": "equipment_sys_id",
        "operator": "=",
    },
    "site_customer_name": {
        "query_column": "p.site_customer_name",
        "description_column": "site_customer_name",
        "operator": "ILIKE",
    },
    "plant_name": {
        "query_column": "p.plant_name",
        "description_column": "plant_name",
        "operator": "ILIKE",
    },
}


class IbatServiceError(Exception):
    def __init__(self, error_code: str, message: str, request_id: str | None = None):
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.request_id = request_id


def _is_rate_limit_error(exc: Exception) -> bool:
    return is_rate_limit_error(exc)


async def read_ibat_by_serial(
    equip_serial_number: str,
    metadata_filters: dict[str, Any] | None = None,
    user: str | None = None,
    request_id: str | None = None,
    db_client: NakshaClient | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    del kwargs
    normalized_serial_number = str(equip_serial_number or "").strip()
    if not normalized_serial_number:
        raise IbatServiceError("INVALID_INPUT", "equip_serial_number is required")
    if metadata_filters is not None and not isinstance(metadata_filters, dict):
        raise IbatServiceError("INVALID_INPUT", "metadata_filters must be a dictionary")

    normalized_user = str(user or "unknown").strip() or "unknown"
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
            select_columns=IBAT_SELECT_COLUMNS,
            from_clause=f"{IBAT_EQUIPMENT_VIEW} e",
            serial_query_column=IBAT_SERIAL_QUERY_COLUMN,
            serial_param_name=IBAT_SERIAL_PARAM_NAME,
            serial_value=normalized_serial_number,
            metadata_filters=normalized_metadata_filters,
            metadata_filter_config=IBAT_METADATA_FILTER_CONFIG,
            error_factory=IbatServiceError,
            join_clauses=IBAT_JOIN_CLAUSES,
            distinct=True,
        )
        rendered_query = render_query(query, params)
        if LOG_SQL_QUERIES:
            logger.info(
                "ibat sql query request_id=%s serial_number=%s query=%s",
                normalized_request_id,
                normalized_serial_number,
                rendered_query,
            )
        elif logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "ibat sql query request_id=%s serial_number=%s query=%s",
                normalized_request_id,
                normalized_serial_number,
                rendered_query,
            )

        max_attempts = max(1, int(os.getenv("IBAT_MAX_RETRIES", "3")))
        backoff_seconds = float(os.getenv("IBAT_RETRY_BACKOFF_SECONDS", "1.5"))

        rows, all_descriptions, query_markers = await execute_read_with_descriptions(
            sql=rendered_query,
            description_tables=IBAT_DESCRIPTION_TABLES,
            query_client=client,
            max_attempts=max_attempts,
            backoff_seconds=backoff_seconds,
            retry_if=_is_rate_limit_error,
        )

        result_ids = extract_result_ids(rows, IBAT_SERIAL_RESULT_KEYS)

        normalized_rows = normalize_rows(rows, IBAT_OUTPUT_COLUMNS, deduplicate=True)
        if not normalized_rows:
            raise IbatServiceError("SERIAL_NOT_FOUND", f"No records found for serial {normalized_serial_number}")

        input_filter_columns = build_input_filter_columns(
            serial_input_key=IBAT_SERIAL_PARAM_NAME,
            serial_description_column="equip_serial_number",
            metadata_filters=normalized_metadata_filters,
            metadata_filter_config=IBAT_METADATA_FILTER_CONFIG,
            descriptions=all_descriptions,
        )

        output_columns = build_output_columns(IBAT_OUTPUT_COLUMNS, all_descriptions)

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
    except IbatServiceError as exc:
        error = exc.message
        error_code = exc.error_code
        raise
    except Exception as exc:
        if _is_rate_limit_error(exc):
            error = "IBAT upstream rate limited (429)"
            error_code = "RATE_LIMITED"
            raise IbatServiceError("RATE_LIMITED", error, request_id=normalized_request_id) from exc
        lower_error = str(exc).lower()
        if "permission" in lower_error or "unauthorized" in lower_error or "insufficient" in lower_error:
            error_code = "UNAUTHORIZED"
            raise IbatServiceError(
                "UNAUTHORIZED",
                "Access denied by Unity Catalog permissions",
                request_id=normalized_request_id,
            ) from exc
        logger.exception(
            "ibat service unexpected error request_id=%s serial_number=%s",
            normalized_request_id,
            normalized_serial_number,
        )
        error = "An internal error occurred"
        error_code = "SYSTEM_ERROR"
        raise IbatServiceError("SYSTEM_ERROR", error, request_id=normalized_request_id) from exc
    finally:
        duration_ms = int((time.perf_counter() - started) * 1000)
        log_read_service_event(
            event="read_ibat_by_serial",
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


async def search_equipment_by_esn(
    esn: str,
    request_id: str | None = None,
    user: str | None = None,
    db_client: NakshaClient | None = None,
) -> dict[str, Any] | None:
    """Lookup equipment by ESN, preferring IBAT data and falling back to mock install base."""
    normalized_esn = str(esn or "").strip()
    if not normalized_esn:
        return None

    fallback_equipment = MOCK_INSTALL_BASE.get(normalized_esn) or MOCK_INSTALL_BASE.get(normalized_esn.upper()) or None
    serial_number = str((fallback_equipment or {}).get("serialNumber") or normalized_esn)

    try:
        ibat_response = await read_ibat_by_serial(
            equip_serial_number=serial_number,
            request_id=request_id,
            user=user,
            db_client=db_client,
        )
    except IbatServiceError:
        return fallback_equipment
    except Exception:
        logger.exception("search_equipment_by_esn failed for serial=%s", serial_number)
        return fallback_equipment

    rows = ibat_response.get("data", []) if isinstance(ibat_response, dict) else []
    if not isinstance(rows, list) or not rows:
        return fallback_equipment

    first_row = rows[0]
    if not isinstance(first_row, dict):
        return fallback_equipment

    mapped_equipment = _map_ibat_to_equipment(first_row, serial_number=serial_number)
    if fallback_equipment:
        return {**fallback_equipment, **{k: v for k, v in mapped_equipment.items() if v is not None}}
    return mapped_equipment


def _map_ibat_to_equipment(ibat_record: dict[str, Any], serial_number: str) -> dict[str, Any]:
    return {
        "serialNumber": ibat_record.get("equip_serial_number") or serial_number,
        "equipmentType": ibat_record.get("equipment_type"),
        "equipmentCode": ibat_record.get("equipment_code"),
        "model": ibat_record.get("equipment_class"),
        "site": ibat_record.get("plant_name"),
        "commercialOpDate": ibat_record.get("equipment_comm_date"),
        "totalEOH": None,
        "totalStarts": None,
        "coolingType": ibat_record.get("cooling_system"),
    }


def _map_ibat_record_to_equipment(ibat_record: dict[str, Any], serial_number: str) -> dict[str, Any]:
    return _map_ibat_to_equipment(ibat_record, serial_number)
