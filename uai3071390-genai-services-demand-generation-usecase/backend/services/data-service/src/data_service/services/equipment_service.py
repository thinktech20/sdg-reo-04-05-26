"""
Equipment data service — ER Cases, FSR Reports, Outage History, and Data Readiness.

Each query function accepts an optional NakshaClient. SQL queries select explicit
columns; mapping functions translate DB column names → API response field names.
When the real DB column names are known, update the column constants and the
left-hand side of each mapping function.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from commons.logging import get_logger
from data_service.client import NakshaClient
from data_service.services.helpers import sql_literal

logger = get_logger(__name__)
LOG_SQL_QUERIES = os.getenv("LOG_SQL_QUERIES", "false").strip().lower() in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------------------
# SQL helpers
# ---------------------------------------------------------------------------


def _build_where(
    esn_column: str,
    esn: str,
    date_column: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
) -> str:
    clauses = [f"{esn_column} = {sql_literal(esn)}"]
    if date_column and from_date:
        clauses.append(f"{date_column} >= {sql_literal(from_date)}")
    if date_column and to_date:
        clauses.append(f"{date_column} <= {sql_literal(to_date)}")
    return " AND ".join(clauses)


# ---------------------------------------------------------------------------
# ER Cases  (vgpp.qlt_std_views.u_pac)
# ---------------------------------------------------------------------------

ER_CATALOG = os.getenv("ER_CATALOG", "vgpp")
ER_SCHEMA = os.getenv("ER_SCHEMA", "qlt_std_views")
ER_TABLE = os.getenv("ER_TABLE", "u_pac")
ER_VIEW = os.getenv("ER_VIEW", f"{ER_CATALOG}.{ER_SCHEMA}.{ER_TABLE}")
ER_CASES_ESN_COLUMN = "u_serial_number"
ER_CASES_DATE_COLUMN = "created_date"
ER_CASES_SELECT_COLUMNS = (
    "number",
    "short_description",
    "created_date",
    "forced_outage",
    "u_component",
    "u_sub_component",
    "state_",
    "description_",
)


def _map_er_case(row: dict[str, Any]) -> dict[str, Any]:
    """Map DB row → API response shape matching frontend ERCase interface."""
    forced = row.get("forced_outage", "")
    return {
        "erNumber": row.get("number"),
        "title": row.get("short_description"),
        "severity": "High" if str(forced).lower() == "true" else "Medium",
        "component": row.get("u_component", ""),
        "dateReported": row.get("created_date"),
        "status": "Closed" if str(row.get("state_", "")).lower() in {"closed", "resolved"} else "Open",
        "summary": row.get("description_", ""),
        "forcedOutage": forced,
        "subComponent": row.get("u_sub_component", ""),
        "rewindFlag": row.get("rewind_related", "false"),
    }


async def get_er_cases(
    esn: str,
    *,
    from_date: str | None = None,
    to_date: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db_client: NakshaClient | None = None,
) -> list[dict[str, Any]]:
    """Return ER cases for *esn*, optionally filtered by date range."""
    client = db_client or NakshaClient()
    columns = ", ".join(ER_CASES_SELECT_COLUMNS)
    rewind_expr = (
        "CASE WHEN LOWER(u_sub_component) LIKE '%rewind%'"
        " OR LOWER(u_sub_component) LIKE '%winding%'"
        " THEN 'true' ELSE 'false' END AS rewind_related"
    )
    where = _build_where(ER_CASES_ESN_COLUMN, esn, ER_CASES_DATE_COLUMN, from_date, to_date)

    offset = (max(1, int(page)) - 1) * int(page_size)
    limit = int(page_size)
    sql = f"SELECT {columns}, {rewind_expr} FROM {ER_VIEW} WHERE {where} LIMIT {limit} OFFSET {offset}"
    logger.info("equipment_service er_cases sql=%s", sql)

    rows = await client.execute_sql(sql)
    if LOG_SQL_QUERIES:
        print(rows)
    logger.info("equipment_service er_cases rows_returned=%d", len(rows))
    return [_map_er_case(r) for r in rows]


# ---------------------------------------------------------------------------
# FSR Reports  (vgpp.fsr_std_views.fsr_field_vision_field_services_report_psot)
# ---------------------------------------------------------------------------

FSR_CATALOG = os.getenv("FSR_CATALOG", "vgpp")
FSR_SCHEMA = os.getenv("FSR_SCHEMA", "fsr_std_views")
FSR_TABLE = os.getenv("FSR_TABLE", "fsr_field_vision_field_services_report_psot")
FSR_VIEW = os.getenv("FSR_VIEW", f"{FSR_CATALOG}.{FSR_SCHEMA}.{FSR_TABLE}")
FSR_REPORTS_ESN_COLUMN = "esn"
FSR_REPORTS_DATE_COLUMN = "start_date"
FSR_REPORTS_SELECT_COLUMNS = (
    "id",
    "report_name",
    "start_date",
    "outage_id",
    "outage_type",
    "report_focus",
    "executive_summary",
)


def _map_fsr_report(row: dict[str, Any]) -> dict[str, Any]:
    """Map DB row → API response shape matching frontend FSRReport interface."""
    rewind = row.get("rewind_flag", "false")
    return {
        "reportId": row.get("id"),
        "title": row.get("report_name"),
        "component": row.get("report_focus", ""),
        "testType": "",
        "outageDate": str(row["start_date"])[:10] if row.get("start_date") else "",
        "outageType": "Forced" if str(row.get("outage_type", "")).lower() == "forced" else None,
        "rewindOccurrence": True if rewind == "true" else None,
        "findings": row.get("executive_summary", ""),
        "recommendation": "",
        "rewindFlag": rewind,
        "outageSummary": row.get("executive_summary", ""),
    }


async def get_fsr_reports(
    esn: str,
    *,
    from_date: str | None = None,
    to_date: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db_client: NakshaClient | None = None,
) -> list[dict[str, Any]]:
    """Return FSR reports for *esn*, optionally filtered by date range."""
    client = db_client or NakshaClient()
    columns = ", ".join(FSR_REPORTS_SELECT_COLUMNS)
    rewind_expr = (
        "CASE WHEN LOWER(report_name) LIKE '%rewind%'"
        " OR LOWER(work_scope) LIKE '%rewind%'"
        " OR LOWER(report_focus) LIKE '%rewind%'"
        " THEN 'true' ELSE 'false' END AS rewind_flag"
    )
    where = _build_where(FSR_REPORTS_ESN_COLUMN, esn, FSR_REPORTS_DATE_COLUMN, from_date, to_date)

    offset = (max(1, int(page)) - 1) * int(page_size)
    limit = int(page_size)
    sql = f"SELECT {columns}, {rewind_expr} FROM {FSR_VIEW} WHERE {where} LIMIT {limit} OFFSET {offset}"
    logger.info("equipment_service fsr_reports sql=%s", sql)

    rows = await client.execute_sql(sql)
    logger.info("equipment_service fsr_reports rows_returned=%d", len(rows))
    return [_map_fsr_report(r) for r in rows]


# ---------------------------------------------------------------------------
# Outage History / Event Master  (vgpp.fsr_std_views.ev_fsp_consolidated_event_sot)
# ---------------------------------------------------------------------------

EVENT_MASTER_CATALOG = os.getenv("EVENT_MASTER_CATALOG", "vgpp")
EVENT_MASTER_SCHEMA = os.getenv("EVENT_MASTER_SCHEMA", "fsr_std_views")

OUTAGE_EVENTMGMT_TABLE = os.getenv("OUTAGE_EVENTMGMT_TABLE", "eventmgmt_event_vision_sot")
OUTAGE_EVENTMGMT_VIEW = os.getenv(
    "OUTAGE_EVENTMGMT_VIEW",
    f"{EVENT_MASTER_CATALOG}.{EVENT_MASTER_SCHEMA}.{OUTAGE_EVENTMGMT_TABLE}",
)
OUTAGE_EQUIP_DTLS_TABLE = os.getenv("OUTAGE_EQUIP_DTLS_TABLE", "event_equipment_dtls_event_vision_sot")
OUTAGE_EQUIP_DTLS_VIEW = os.getenv(
    "OUTAGE_EQUIP_DTLS_VIEW",
    f"{EVENT_MASTER_CATALOG}.{EVENT_MASTER_SCHEMA}.{OUTAGE_EQUIP_DTLS_TABLE}",
)
OUTAGE_SCOPE_TABLE = os.getenv("OUTAGE_SCOPE_TABLE", "scope_schedule_summary_event_vision_sot")
OUTAGE_SCOPE_VIEW = os.getenv(
    "OUTAGE_SCOPE_VIEW",
    f"{EVENT_MASTER_CATALOG}.{EVENT_MASTER_SCHEMA}.{OUTAGE_SCOPE_TABLE}",
)
OUTAGE_HISTORY_ESN_COLUMN = "ev_serial_number"
OUTAGE_HISTORY_DATE_COLUMN = "ev_actual_start_date"


def _map_outage(row: dict[str, Any]) -> dict[str, Any]:
    """Map DB row → API response shape matching frontend OutageEvent interface."""
    event_type_raw = row.get("event_type", "")
    outage_type = "Major" if "major" in str(event_type_raw).lower() else "Minor"
    return {
        "outageId": row.get("id", ""),
        "outageType": outage_type,
        "startDate": row.get("start_date", ""),
        "endDate": row.get("end_date", ""),
        "duration": 0,
        "workPerformed": [],
        "title": row.get("title", ""),
        "rewindFlag": row.get("rewind_flag", "false"),
        "outageSummary": row.get("outage_summary", ""),
    }


async def get_outage_history(
    esn: str,
    *,
    from_date: str | None = None,
    to_date: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db_client: NakshaClient | None = None,
) -> list[dict[str, Any]]:
    """Return outage history for *esn*, optionally filtered by date range."""
    client = db_client or NakshaClient()

    where_clauses = [f"ed.{OUTAGE_HISTORY_ESN_COLUMN} = {sql_literal(esn)}"]
    if from_date:
        where_clauses.append(f"em.{OUTAGE_HISTORY_DATE_COLUMN} >= {sql_literal(from_date)}")
    if to_date:
        where_clauses.append(f"em.{OUTAGE_HISTORY_DATE_COLUMN} <= {sql_literal(to_date)}")
    where = " AND ".join(where_clauses)

    offset = (max(1, int(page)) - 1) * int(page_size)
    limit = int(page_size)
    sql = (
        f"SELECT DISTINCT em.ev_equipment_event_id AS id, "
        f"COALESCE(em.ev_actual_start_date, em.ev_plan_event_start_date) AS start_date, "
        f"COALESCE(em.ev_actual_end_date, em.ev_plan_event_end_date) AS end_date, "
        f"em.ev_event_description AS title, "
        f"em.ev_event_type AS event_type, "
        f"CASE WHEN LOWER(em.ev_event_type) LIKE '%rewind%' "
        f"THEN 'true' ELSE 'false' END AS rewind_flag, "
        f"em.ev_event_description AS outage_summary "
        f"FROM {OUTAGE_EVENTMGMT_VIEW} em "
        f"INNER JOIN {OUTAGE_EQUIP_DTLS_VIEW} ed "
        f"ON em.ev_equipment_event_id = ed.ev_equipment_event_id "
        f"WHERE {where} "
        f"ORDER BY id "
        f"LIMIT {limit} OFFSET {offset}"
    )
    logger.info("equipment_service outage_history sql=%s", sql)

    rows = await client.execute_sql(sql)
    logger.info("equipment_service outage_history rows_returned=%d", len(rows))
    return [_map_outage(r) for r in rows]


# ---------------------------------------------------------------------------
# IBAT availability check (configuration / reference data — no date filter)
# ---------------------------------------------------------------------------

IBAT_CATALOG = os.getenv("CATALOG", "vgpp")
IBAT_SCHEMA = os.getenv("IBAT_SCHEMA", "prm_std_views")
IBAT_EQUIPMENT_TABLE = os.getenv("IBAT_EQUIPMENT_TABLE", "IBAT_EQUIPMENT_MST")
IBAT_EQUIPMENT_VIEW = os.getenv("IBAT_EQUIPMENT_VIEW", f"{IBAT_CATALOG}.{IBAT_SCHEMA}.{IBAT_EQUIPMENT_TABLE}")
IBAT_ESN_COLUMN = "equip_serial_number"


async def check_ibat_data(
    esn: str,
    *,
    db_client: NakshaClient | None = None,
) -> bool:
    """Return True if IBAT install-base data exists for *esn*."""
    client = db_client or NakshaClient()

    sql = f"SELECT 1 FROM {IBAT_EQUIPMENT_VIEW} WHERE {IBAT_ESN_COLUMN} = {sql_literal(esn)} LIMIT 1"
    logger.info("equipment_service check_ibat sql=%s", sql)

    rows = await client.execute_sql(sql)
    return len(rows) > 0


# ---------------------------------------------------------------------------
# PRISM availability check (reference / model data — no date filter)
# ---------------------------------------------------------------------------

PRISM_CATALOG = os.getenv("CATALOG", "vgpp")
PRISM_SCHEMA = os.getenv("PRISM_SCHEMA", "seg_std_views")
PRISM_SOT_TABLE = os.getenv("PRISM_SOT_TABLE", "seg_fmea_wo_models_gen_psot")
PRISM_SOT_VIEW = os.getenv("PRISM_SOT_VIEW", f"{PRISM_CATALOG}.{PRISM_SCHEMA}.{PRISM_SOT_TABLE}")
PRISM_ESN_COLUMN = "TURBINE_NUMBER"


async def check_prism_data(
    esn: str,
    *,
    db_client: NakshaClient | None = None,
) -> bool:
    """Return True if PRISM reliability-model data exists for *esn*."""
    client = db_client or NakshaClient()

    sql = f"SELECT 1 FROM {PRISM_SOT_VIEW} WHERE {PRISM_ESN_COLUMN} = {sql_literal(esn)} LIMIT 1"
    logger.info("equipment_service check_prism sql=%s", sql)

    rows = await client.execute_sql(sql)
    return len(rows) > 0


# ---------------------------------------------------------------------------
# Count helpers (used by data-readiness — date-filtered SQL)
# ---------------------------------------------------------------------------


async def _count_er_cases(
    esn: str,
    *,
    from_date: str | None = None,
    to_date: str | None = None,
    db_client: NakshaClient | None = None,
) -> int:
    client = db_client or NakshaClient()
    where = _build_where(ER_CASES_ESN_COLUMN, esn, ER_CASES_DATE_COLUMN, from_date, to_date)
    sql = f"SELECT COUNT(*) AS cnt FROM {ER_VIEW} WHERE {where}"
    logger.info("equipment_service count_er_cases sql=%s", sql)

    rows = await client.execute_sql(sql)
    logger.info("equipment_service count_er_cases result=%s", rows)
    return int(rows[0].get("cnt", 0)) if rows else 0


async def _count_fsr_reports(
    esn: str,
    *,
    from_date: str | None = None,
    to_date: str | None = None,
    db_client: NakshaClient | None = None,
) -> int:
    client = db_client or NakshaClient()
    where = _build_where(FSR_REPORTS_ESN_COLUMN, esn, FSR_REPORTS_DATE_COLUMN, from_date, to_date)
    sql = f"SELECT COUNT(*) AS cnt FROM {FSR_VIEW} WHERE {where}"
    logger.info("equipment_service count_fsr_reports sql=%s", sql)

    rows = await client.execute_sql(sql)
    logger.info("equipment_service count_fsr_reports result=%s", rows)
    return int(rows[0].get("cnt", 0)) if rows else 0


async def _count_outage_history(
    esn: str,
    *,
    from_date: str | None = None,
    to_date: str | None = None,
    db_client: NakshaClient | None = None,
) -> int:
    client = db_client or NakshaClient()

    where_clauses = [f"ed.{OUTAGE_HISTORY_ESN_COLUMN} = {sql_literal(esn)}"]
    if from_date:
        where_clauses.append(f"em.{OUTAGE_HISTORY_DATE_COLUMN} >= {sql_literal(from_date)}")
    if to_date:
        where_clauses.append(f"em.{OUTAGE_HISTORY_DATE_COLUMN} <= {sql_literal(to_date)}")
    where = " AND ".join(where_clauses)

    sql = (
        f"SELECT COUNT(*) AS cnt "
        f"FROM {OUTAGE_EVENTMGMT_VIEW} em "
        f"INNER JOIN {OUTAGE_EQUIP_DTLS_VIEW} ed "
        f"ON em.ev_equipment_event_id = ed.ev_equipment_event_id "
        f"WHERE {where}"
    )
    logger.info("equipment_service count_outage_history sql=%s", sql)

    rows = await client.execute_sql(sql)
    logger.info("equipment_service count_outage_history result=%s", rows)
    return int(rows[0].get("cnt", 0)) if rows else 0


# ---------------------------------------------------------------------------
# Data Readiness  (parallel fetch via asyncio.gather)
# ---------------------------------------------------------------------------


async def get_data_readiness(
    esn: str,
    *,
    from_date: str | None = None,
    to_date: str | None = None,
    db_client: NakshaClient | None = None,
) -> dict[str, Any]:
    """
    Return consolidated data-source availability for *esn*.

    Date filtering applies to ER Cases, FSR Reports, and Outage History counts.
    IBAT and PRISM are configuration/reference data and are not date-filtered.
    """
    (
        ibat_available,
        er_count,
        fsr_count,
        outage_count,
        prism_available,
    ) = await asyncio.gather(
        check_ibat_data(esn, db_client=db_client),
        _count_er_cases(esn, from_date=from_date, to_date=to_date, db_client=db_client),
        _count_fsr_reports(esn, from_date=from_date, to_date=to_date, db_client=db_client),
        _count_outage_history(esn, from_date=from_date, to_date=to_date, db_client=db_client),
        check_prism_data(esn, db_client=db_client),
    )

    data_sources: dict[str, Any] = {
        "ibatData": {"available": ibat_available},
        "erCases": {"available": er_count > 0, "count": er_count},
        "fsrReports": {"available": fsr_count > 0, "count": fsr_count},
        "outageHistory": {"available": outage_count > 0, "count": outage_count},
        "prismData": {"available": prism_available},
    }

    total_available = sum(
        1
        for src in data_sources.values()
        if src.get("available")
    )

    return {
        "esn": esn,
        "fromDate": from_date,
        "toDate": to_date,
        "dataSources": data_sources,
        "totalAvailable": total_available,
        "totalSources": len(data_sources),
    }



