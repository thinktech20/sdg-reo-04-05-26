"""
Train service – fetches trains (with nested equipment) from IBAT tables.

Uses the SQL join between ``ibat_train_mst`` and ``ibat_equipment_mst`` limited
to 5 trains, then maps the flat rows into the same shape as ``MOCK_TRAINS``
consumed by the ``/api/v1/units`` route.
"""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from typing import Any

from commons.logging import get_logger
from data_service import config
from data_service.client import NakshaClient
from data_service.logging_utils import log_read_service_event
from data_service.mock_services.equipment import MOCK_TRAINS
from data_service.services.helpers import (
    execute_with_retries,
    is_rate_limit_error,
    render_query,
)
from data_service.services.ibat_service import (
    IBAT_EQUIPMENT_VIEW,
    IBAT_TRAIN_VIEW,
    _map_ibat_to_equipment,
)

logger = get_logger(__name__)
LOG_SQL_QUERIES = os.getenv("LOG_SQL_QUERIES", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

# Columns selected from each table – mirrors the provided SQL query.
_TRAIN_SELECT_COLUMNS: tuple[str, ...] = (
    "train_name",
    "location",
    "train_type",
)
_EQUIPMENT_SELECT_COLUMNS: tuple[str, ...] = (
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
    "cooling_system",
    "equip_serial_number",
)

DEFAULT_PAGE_SIZE = 25
DEFAULT_PAGE = 1


class TrainServiceError(Exception):
    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code
        self.message = message


def _build_trains_query(
    page: int = DEFAULT_PAGE,
    page_size: int = DEFAULT_PAGE_SIZE,
    search: str = "",
) -> tuple[str, dict[str, Any]]:
    """Build the SQL that joins trains → equipment with pagination.

    Returns ``(query_template, params)`` – the template contains ``:name``
    placeholders that :func:`render_query` will safely interpolate.
    """
    train_cols = ", ".join(f"t.{c}" for c in _TRAIN_SELECT_COLUMNS)
    equip_cols = ", ".join(f"e.{c}" for c in _EQUIPMENT_SELECT_COLUMNS)

    params: dict[str, Any] = {}
    search_clause = ""

    if search:
        search_clause = "AND (LOWER(train_name) LIKE :search OR LOWER(location) LIKE :search)"
        params["search"] = f"%{search.lower()}%"

    offset = (max(1, int(page)) - 1) * int(page_size)
    limit = int(page_size)

    query = f"""
        SELECT
            {train_cols},
            {equip_cols}
        FROM {IBAT_TRAIN_VIEW} t
        JOIN {IBAT_EQUIPMENT_VIEW} e
            ON e.train_sys_id_fk = t.train_sys_id
        WHERE
          t.train_name IS NOT NULL
          AND e.equip_serial_number IS NOT NULL
          AND t.train_sys_id IN (
            SELECT DISTINCT train_sys_id
            FROM {IBAT_TRAIN_VIEW}
            WHERE train_name IS NOT NULL
            {search_clause}
            ORDER BY train_sys_id
            LIMIT {limit}
            OFFSET {offset}
        )
        ORDER BY t.train_name, e.equipment_name
    """
    return query, params


def _map_row_to_train(row: dict[str, Any]) -> dict[str, Any]:
    """Map a flat SQL row to the train-level fields matching MOCK_TRAINS shape."""
    return {
        "id": row.get("train_sys_id_fk"),
        "trainName": row.get("train_name"),
        "site": row.get("location"),
        "trainType": row.get("train_type"),
    }


def _group_rows_into_trains(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Group flat joined rows by ``train_sys_id_fk`` and nest equipment under
    each train, producing a list matching the MOCK_TRAINS shape.
    """
    train_map: dict[str, dict[str, Any]] = {}
    equipment_map: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        train_id = str(row.get("train_sys_id_fk") or "")
        if not train_id:
            continue

        # Build train entry once per id.
        if train_id not in train_map:
            train_map[train_id] = _map_row_to_train(row)

        # Map equipment using the shared helper from ibat_service.
        serial_number = str(row.get("equip_serial_number") or "")
        equipment = _map_ibat_to_equipment(row, serial_number=serial_number)
        equipment_map[train_id].append(equipment)

    trains: list[dict[str, Any]] = []
    for train_id, train in train_map.items():
        train["equipment"] = equipment_map.get(train_id, [])
        trains.append(train)

    return trains


async def get_trains(
    page: int = DEFAULT_PAGE,
    page_size: int = DEFAULT_PAGE_SIZE,
    search: str = "",
    filter_type: str | None = None,
    user: str | None = None,
    request_id: str | None = None,
    db_client: NakshaClient | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch trains with nested equipment from IBAT.
    """
    if config.USE_MOCK_UNITS:
        logger.debug("USE_MOCK_UNITS=true – returning mock trains")
        return list(MOCK_TRAINS)

    normalized_user = str(user or "unknown").strip() or "unknown"
    normalized_request_id = str(request_id).strip() if request_id is not None else None

    client = db_client or NakshaClient()
    started = time.perf_counter()
    error: str | None = None
    error_code: str | None = None
    try:
        query, params = _build_trains_query(page=page, page_size=page_size, search=search)
        rendered_query = render_query(query, params)

        if LOG_SQL_QUERIES:
            logger.info(
                "train sql query request_id=%s query=%s",
                normalized_request_id,
                rendered_query,
            )
        elif logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "train sql query request_id=%s query=%s",
                normalized_request_id,
                rendered_query,
            )

        max_attempts = max(1, int(os.getenv("TRAIN_MAX_RETRIES", "3")))
        backoff_seconds = float(os.getenv("TRAIN_RETRY_BACKOFF_SECONDS", "1.5"))

        rows = await execute_with_retries(
            lambda: client.execute_sql(rendered_query),
            max_attempts=max_attempts,
            backoff_seconds=backoff_seconds,
            retry_if=lambda exc: is_rate_limit_error(exc),
        )

        if not rows:
            logger.warning("train query returned no rows")
            return []

        return _group_rows_into_trains(rows)

    except TrainServiceError as exc:
        error = exc.message
        error_code = exc.error_code
        logger.error("TrainServiceError: %s", exc.message)
        raise
    except Exception as exc:
        error = str(exc)
        error_code = "SYSTEM_ERROR"
        logger.exception("get_trains failed")
        raise
    finally:
        duration_ms = int((time.perf_counter() - started) * 1000)
        log_read_service_event(
            event="get_trains",
            user=normalized_user,
            serial_number=None,
            request_id=normalized_request_id,
            metadata_filters={},
            error=error,
            error_code=error_code,
            result_ids=[],
            duration_ms=duration_ms,
            naksha_status="unknown",
            table_status="unknown",
        )
