"""
Unit tests for services/equipment_service.py — mapping functions, SQL builders, data readiness.
"""

from __future__ import annotations

from typing import Any

import pytest

from data_service.services.equipment_service import (
    _build_where,
    _map_er_case,
    _map_fsr_report,
    _map_outage,
    check_ibat_data,
    check_prism_data,
    get_data_readiness,
    get_er_cases,
    get_fsr_reports,
    get_outage_history,
)


class _FakeDbClient:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self._rows = rows or []
        self.last_sql: str = ""

    async def execute_sql(self, sql: str) -> list[dict[str, Any]]:
        self.last_sql = sql
        return self._rows

    def get_last_query_markers(self) -> dict[str, str]:
        return {"naksha_status": "mock", "table_status": "mock"}


# ── _build_where ──────────────────────────────────────────────────────────────


class TestBuildWhere:
    def test_esn_only(self):
        where = _build_where("serial", "GT12345")
        assert where == "serial = 'GT12345'"

    def test_with_from_date(self):
        where = _build_where("serial", "GT12345", "created", "2024-01-01", None)
        assert "created >= '2024-01-01'" in where

    def test_with_to_date(self):
        where = _build_where("serial", "GT12345", "created", None, "2024-12-31")
        assert "created <= '2024-12-31'" in where

    def test_with_both_dates(self):
        where = _build_where("serial", "GT12345", "created", "2024-01-01", "2024-12-31")
        assert "serial = 'GT12345'" in where
        assert "created >= '2024-01-01'" in where
        assert "created <= '2024-12-31'" in where


# ── _map_er_case ──────────────────────────────────────────────────────────────


class TestMapERCase:
    def test_maps_forced_outage_to_high_severity(self):
        row = {"number": "ER-1", "short_description": "Test", "forced_outage": "true", "created_date": "2024-01-01", "state_": "Open"}
        result = _map_er_case(row)
        assert result["severity"] == "High"
        assert result["erNumber"] == "ER-1"

    def test_maps_non_forced_outage_to_medium(self):
        row = {"number": "ER-2", "forced_outage": "false", "state_": "Open"}
        result = _map_er_case(row)
        assert result["severity"] == "Medium"

    def test_closed_state_maps_to_closed(self):
        row = {"number": "ER-3", "state_": "Closed", "forced_outage": ""}
        result = _map_er_case(row)
        assert result["status"] == "Closed"

    def test_resolved_state_maps_to_closed(self):
        row = {"number": "ER-4", "state_": "Resolved", "forced_outage": ""}
        result = _map_er_case(row)
        assert result["status"] == "Closed"

    def test_open_state(self):
        row = {"number": "ER-5", "state_": "In Progress", "forced_outage": ""}
        result = _map_er_case(row)
        assert result["status"] == "Open"

    def test_rewind_related_flag(self):
        row = {"number": "ER-6", "rewind_related": "true", "forced_outage": "", "state_": "Open"}
        result = _map_er_case(row)
        assert result["rewindFlag"] == "true"


# ── _map_fsr_report ───────────────────────────────────────────────────────────


class TestMapFSRReport:
    def test_maps_basic_fields(self):
        row = {"id": "FSR-1", "report_name": "Report", "start_date": "2024-01-15T00:00:00", "outage_type": "Forced", "rewind_flag": "true", "executive_summary": "Summary"}
        result = _map_fsr_report(row)
        assert result["reportId"] == "FSR-1"
        assert result["title"] == "Report"
        assert result["outageDate"] == "2024-01-15"
        assert result["outageType"] == "Forced"
        assert result["rewindOccurrence"] is True
        assert result["findings"] == "Summary"

    def test_non_forced_outage_type_is_none(self):
        row = {"id": "FSR-2", "outage_type": "Planned", "rewind_flag": "false"}
        result = _map_fsr_report(row)
        assert result["outageType"] is None
        assert result["rewindOccurrence"] is None

    def test_missing_start_date(self):
        row = {"id": "FSR-3", "rewind_flag": "false"}
        result = _map_fsr_report(row)
        assert result["outageDate"] == ""


# ── _map_outage ───────────────────────────────────────────────────────────────


class TestMapOutage:
    def test_major_outage_type(self):
        row = {"id": "OUT-1", "event_type": "Major Inspection", "start_date": "2024-01-01", "end_date": "2024-02-01", "rewind_flag": "false", "outage_summary": "Summary"}
        result = _map_outage(row)
        assert result["outageType"] == "Major"
        assert result["outageId"] == "OUT-1"

    def test_minor_outage_type(self):
        row = {"event_type": "Combustion Inspection"}
        result = _map_outage(row)
        assert result["outageType"] == "Minor"

    def test_empty_event_type(self):
        row = {"event_type": ""}
        result = _map_outage(row)
        assert result["outageType"] == "Minor"


# ── Async query functions ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_er_cases_returns_mapped_rows():
    fake_rows = [
        {"number": "ER-1", "short_description": "Test", "forced_outage": "true", "created_date": "2024-01-01", "state_": "Open", "u_component": "Turbine", "u_sub_component": "rewind", "description_": "Details", "rewind_related": "true"},
    ]
    client = _FakeDbClient(rows=fake_rows)
    result = await get_er_cases("GT12345", db_client=client)
    assert len(result) == 1
    assert result[0]["erNumber"] == "ER-1"
    assert result[0]["rewindFlag"] == "true"


@pytest.mark.asyncio
async def test_get_er_cases_with_date_filters():
    client = _FakeDbClient(rows=[])
    await get_er_cases("GT12345", from_date="2024-01-01", to_date="2024-12-31", db_client=client)
    assert "2024-01-01" in client.last_sql
    assert "2024-12-31" in client.last_sql


@pytest.mark.asyncio
async def test_get_er_cases_pagination_default():
    client = _FakeDbClient(rows=[])
    await get_er_cases("GT12345", db_client=client)
    assert "LIMIT 20" in client.last_sql
    assert "OFFSET 0" in client.last_sql


@pytest.mark.asyncio
async def test_get_er_cases_pagination_page_2():
    client = _FakeDbClient(rows=[])
    await get_er_cases("GT12345", page=2, page_size=20, db_client=client)
    assert "LIMIT 20" in client.last_sql
    assert "OFFSET 20" in client.last_sql


@pytest.mark.asyncio
async def test_get_er_cases_pagination_custom_page_size():
    client = _FakeDbClient(rows=[])
    await get_er_cases("GT12345", page=3, page_size=10, db_client=client)
    assert "LIMIT 10" in client.last_sql
    assert "OFFSET 20" in client.last_sql


@pytest.mark.asyncio
async def test_get_fsr_reports_returns_mapped_rows():
    fake_rows = [
        {"id": "FSR-1", "report_name": "Report", "start_date": "2024-03-15", "outage_type": "Forced", "report_focus": "Turbine", "executive_summary": "Summary", "outage_id": "O-1", "rewind_flag": "false"},
    ]
    client = _FakeDbClient(rows=fake_rows)
    result = await get_fsr_reports("GT12345", db_client=client)
    assert len(result) == 1
    assert result[0]["reportId"] == "FSR-1"


@pytest.mark.asyncio
async def test_get_fsr_reports_pagination_default():
    client = _FakeDbClient(rows=[])
    await get_fsr_reports("GT12345", db_client=client)
    assert "LIMIT 20" in client.last_sql
    assert "OFFSET 0" in client.last_sql


@pytest.mark.asyncio
async def test_get_fsr_reports_pagination_page_2():
    client = _FakeDbClient(rows=[])
    await get_fsr_reports("GT12345", page=2, page_size=20, db_client=client)
    assert "LIMIT 20" in client.last_sql
    assert "OFFSET 20" in client.last_sql


@pytest.mark.asyncio
async def test_get_outage_history_returns_mapped_rows():
    fake_rows = [
        {"id": "OUT-1", "start_date": "2024-01-01", "end_date": "2024-02-01", "title": "Outage 1", "event_type": "Major Inspection", "rewind_flag": "false", "outage_summary": "Summary"},
    ]
    client = _FakeDbClient(rows=fake_rows)
    result = await get_outage_history("GT12345", db_client=client)
    assert len(result) == 1
    assert result[0]["outageType"] == "Major"


@pytest.mark.asyncio
async def test_get_outage_history_with_dates():
    client = _FakeDbClient(rows=[])
    await get_outage_history("GT12345", from_date="2024-01-01", to_date="2024-12-31", db_client=client)
    assert "2024-01-01" in client.last_sql
    assert "2024-12-31" in client.last_sql


@pytest.mark.asyncio
async def test_get_outage_history_pagination_default():
    client = _FakeDbClient(rows=[])
    await get_outage_history("GT12345", db_client=client)
    assert "LIMIT 20" in client.last_sql
    assert "OFFSET 0" in client.last_sql


@pytest.mark.asyncio
async def test_get_outage_history_pagination_page_2():
    client = _FakeDbClient(rows=[])
    await get_outage_history("GT12345", page=2, page_size=20, db_client=client)
    assert "LIMIT 20" in client.last_sql
    assert "OFFSET 20" in client.last_sql


@pytest.mark.asyncio
async def test_get_outage_history_pagination_custom_page_size():
    client = _FakeDbClient(rows=[])
    await get_outage_history("GT12345", page=3, page_size=5, db_client=client)
    assert "LIMIT 5" in client.last_sql
    assert "OFFSET 10" in client.last_sql


@pytest.mark.asyncio
async def test_get_outage_history_uses_select_distinct():
    client = _FakeDbClient(rows=[])
    await get_outage_history("GT12345", db_client=client)
    assert "SELECT DISTINCT" in client.last_sql


@pytest.mark.asyncio
async def test_get_outage_history_has_order_by():
    client = _FakeDbClient(rows=[])
    await get_outage_history("GT12345", db_client=client)
    assert "ORDER BY id" in client.last_sql


@pytest.mark.asyncio
async def test_check_ibat_data_returns_true_when_rows():
    client = _FakeDbClient(rows=[{"1": 1}])
    assert await check_ibat_data("GT12345", db_client=client) is True


@pytest.mark.asyncio
async def test_check_ibat_data_returns_false_when_empty():
    client = _FakeDbClient(rows=[])
    assert await check_ibat_data("GT12345", db_client=client) is False


@pytest.mark.asyncio
async def test_check_prism_data_returns_true_when_rows():
    client = _FakeDbClient(rows=[{"1": 1}])
    assert await check_prism_data("GT12345", db_client=client) is True


@pytest.mark.asyncio
async def test_check_prism_data_returns_false_when_empty():
    client = _FakeDbClient(rows=[])
    assert await check_prism_data("GT12345", db_client=client) is False


@pytest.mark.asyncio
async def test_get_data_readiness_aggregates_sources():
    async def _exec(sql: str) -> list[dict[str, Any]]:
        if "COUNT" in sql:
            return [{"cnt": 5}]
        return [{"1": 1}]

    client = _FakeDbClient()
    client.execute_sql = _exec  # type: ignore[assignment]
    result = await get_data_readiness("GT12345", db_client=client)
    assert result["esn"] == "GT12345"
    assert result["dataSources"]["ibatData"]["available"] is True
    assert result["dataSources"]["erCases"]["count"] == 5
    assert result["totalAvailable"] == 5
    assert result["totalSources"] == 5


@pytest.mark.asyncio
async def test_get_data_readiness_with_no_data():
    client = _FakeDbClient(rows=[])
    result = await get_data_readiness("UNKNOWN", db_client=client)
    assert result["totalAvailable"] == 0
