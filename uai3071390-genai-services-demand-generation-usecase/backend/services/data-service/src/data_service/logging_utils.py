from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any

from commons.logging import get_logger

SERVICE_NAME = os.getenv("SERVICE_NAME", "data-svc")


def log_query_event(*, logger_name: str, event: str, payload: dict[str, Any]) -> None:
    logger = get_logger(logger_name)
    body = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event": event,
        **payload,
    }
    logger.info(json.dumps(body, ensure_ascii=False))


def log_read_service_event(
    *,
    event: str,
    user: str,
    serial_number: str | None,
    request_id: str | None,
    metadata_filters: dict[str, Any],
    error: str | None,
    error_code: str | None,
    result_ids: list[str],
    duration_ms: int,
    naksha_status: str = "unknown",
    table_status: str = "unknown",
) -> None:
    log_query_event(
        logger_name=SERVICE_NAME,
        event=event,
        payload={
            "user": user,
            "serial_number": serial_number,
            "request_id": request_id,
            "metadata_filters": metadata_filters,
            "errors": error,
            "error_code": error_code,
            "record_count": len(result_ids),
            "result_ids": result_ids,
            "naksha_status": naksha_status,
            "table_status": table_status,
            "execution_time_ms": duration_ms,
            "duration_ms": duration_ms,
        },
    )


def log_ibat_event(
    *,
    user: str,
    serial_number: str,
    assessment_id: str | None,
    equipment_type: str | None,
    result_ids: list[str],
    errors: str | None,
    duration_ms: int,
) -> None:
    log_query_event(
        logger_name=SERVICE_NAME,
        event="ibat_query",
        payload={
            "user": user,
            "assessment_id": assessment_id,
            "serial_number": serial_number,
            "equipment_type": equipment_type,
            "result_count": len(result_ids),
            "result_ids": result_ids,
            "errors": errors,
            "duration_ms": duration_ms,
        },
    )


def log_prism_event(
    *,
    user: str,
    serial_number: str,
    component: str | None,
    model_id: str | None,
    date_from: str | None,
    date_to: str | None,
    result_count: int,
    result_ids: list[str],
    errors: str | None,
    duration_ms: int,
) -> None:
    log_query_event(
        logger_name=SERVICE_NAME,
        event="prism_query",
        payload={
            "user": user,
            "serial_number": serial_number,
            "component": component,
            "model_id": model_id,
            "date_from": date_from,
            "date_to": date_to,
            "result_count": result_count,
            "result_ids": result_ids,
            "errors": errors,
            "duration_ms": duration_ms,
        },
    )


def log_risk_matrix_event(
    *,
    user: str,
    serial_number: str | None,
    equipment_type: str,
    persona: str,
    component: str | None,
    result_count: int,
    risk_matrix_version: str | None,
    errors: str | None,
    duration_ms: int,
) -> None:
    log_query_event(
        logger_name=SERVICE_NAME,
        event="risk_matrix_query",
        payload={
            "user": user,
            "serial_number": serial_number,
            "equipment_type": equipment_type,
            "persona": persona,
            "component": component,
            "result_count": result_count,
            "risk_matrix_version": risk_matrix_version,
            "errors": errors,
            "duration_ms": duration_ms,
        },
    )
