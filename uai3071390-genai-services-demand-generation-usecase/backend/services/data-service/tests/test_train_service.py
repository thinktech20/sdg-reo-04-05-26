from __future__ import annotations

from typing import Any

import pytest

from data_service.mock_services.equipment import MOCK_TRAINS
from data_service.services import train_service

# ── Fake DB client (same pattern as test_ibat_service) ──────────────────────


class _FakeDbClient:
    def __init__(
        self,
        rows: list[dict[str, Any]] | None = None,
        exc: Exception | None = None,
    ) -> None:
        self._rows = rows or []
        self._exc = exc
        self.last_sql: str | None = None

    async def execute_sql(self, sql: str) -> list[dict[str, Any]]:
        self.last_sql = sql
        if self._exc is not None:
            raise self._exc
        return self._rows

    def get_last_query_markers(self) -> dict[str, str]:
        return {"naksha_status": "success", "table_status": "available"}


# ── Sample rows (flat join output matching the SQL query) ────────────────────


def _make_row(
    *,
    train_sys_id_fk: str = "T-100",
    train_name: str = "Alpha Train",
    location: str = "Plant-A",
    train_type: str = "Combined Cycle",
    equip_serial_number: str = "GT00001",
    equipment_type: str = "Gas Turbine",
    equipment_name: str = "GT Unit 1",
    equipment_code: str = "7FA.05",
    equipment_class: str = "7FA",
    cooling_system: str = "Air-Cooled",
    **overrides: Any,
) -> dict[str, Any]:
    """Return a single flat row as it would come back from the SQL join."""
    base: dict[str, Any] = {
        "train_sys_id_fk": train_sys_id_fk,
        "train_name": train_name,
        "location": location,
        "train_type": train_type,
        "equip_serial_number": equip_serial_number,
        "equipment_type": equipment_type,
        "equipment_name": equipment_name,
        "equipment_code": equipment_code,
        "equipment_class": equipment_class,
        "cooling_system": cooling_system,
        "sales_channel": None,
        "equipment_sys_id": "EQ-1",
        "contract_type": None,
        "block_sys_id_fk": None,
        "plant_sys_id_fk": "P-1",
        "actualized_flag": None,
        "duty_cycle": None,
        # Fields used by _map_ibat_to_equipment that come from the plant table
        "plant_name": location,
    }
    base.update(overrides)
    return base


SAMPLE_ROWS = [
    _make_row(
        train_sys_id_fk="T-100",
        train_name="Alpha Train",
        location="Plant-A",
        train_type="Combined Cycle",
        equip_serial_number="GT00001",
        equipment_type="Gas Turbine",
        equipment_name="GT Unit 1",
        equipment_code="7FA.05",
        equipment_class="7FA",
        cooling_system="Air-Cooled",
    ),
    _make_row(
        train_sys_id_fk="T-100",
        train_name="Alpha Train",
        location="Plant-A",
        train_type="Combined Cycle",
        equip_serial_number="GEN00002",
        equipment_type="Generator",
        equipment_name="Gen Unit 1",
        equipment_code="W88",
        equipment_class="W88",
        cooling_system="Hydrogen-Cooled",
    ),
    _make_row(
        train_sys_id_fk="T-200",
        train_name="Beta Train",
        location="Plant-B",
        train_type="Simple Cycle",
        equip_serial_number="GT00003",
        equipment_type="Gas Turbine",
        equipment_name="GT Unit 3",
        equipment_code="9FA.03",
        equipment_class="9FA",
        cooling_system="Closed-Loop Water",
    ),
]


# ── Unit tests: _build_trains_query ──────────────────────────────────────────


def test_build_trains_query_returns_tuple() -> None:
    result = train_service._build_trains_query(page=1, page_size=25)
    assert isinstance(result, tuple)
    assert len(result) == 2


def test_build_trains_query_contains_limit_and_offset() -> None:
    query, _params = train_service._build_trains_query(page=1, page_size=25)
    assert "LIMIT 25" in query
    assert "OFFSET 0" in query


def test_build_trains_query_custom_page_size() -> None:
    query, _params = train_service._build_trains_query(page=1, page_size=10)
    assert "LIMIT 10" in query
    assert "OFFSET 0" in query


def test_build_trains_query_page_offset() -> None:
    query, _params = train_service._build_trains_query(page=3, page_size=10)
    assert "LIMIT 10" in query
    assert "OFFSET 20" in query


def test_build_trains_query_references_both_tables() -> None:
    query, _params = train_service._build_trains_query()
    assert train_service.IBAT_TRAIN_VIEW in query
    assert train_service.IBAT_EQUIPMENT_VIEW in query


def test_build_trains_query_selects_train_columns() -> None:
    query, _params = train_service._build_trains_query()
    for col in train_service._TRAIN_SELECT_COLUMNS:
        assert f"t.{col}" in query


def test_build_trains_query_selects_equipment_columns() -> None:
    query, _params = train_service._build_trains_query()
    for col in train_service._EQUIPMENT_SELECT_COLUMNS:
        assert f"e.{col}" in query


def test_build_trains_query_no_search_no_search_clause() -> None:
    query, params = train_service._build_trains_query()
    assert ":search" not in query
    assert "search" not in params


def test_build_trains_query_with_search_adds_like_clause() -> None:
    query, params = train_service._build_trains_query(search="alpha")
    assert "LOWER(train_name) LIKE :search" in query
    assert "LOWER(location) LIKE :search" in query
    assert params["search"] == "%alpha%"


def test_build_trains_query_search_is_lowercased() -> None:
    _query, params = train_service._build_trains_query(search="PLANT")
    assert params["search"] == "%plant%"


def test_build_trains_query_has_not_null_filters() -> None:
    query, _params = train_service._build_trains_query()
    assert "t.train_name IS NOT NULL" in query
    assert "e.equip_serial_number IS NOT NULL" in query


def test_build_trains_query_uses_distinct_in_subquery() -> None:
    query, _params = train_service._build_trains_query()
    assert "SELECT DISTINCT train_sys_id" in query


# ── Unit tests: _map_row_to_train ────────────────────────────────────────────


def test_map_row_to_train_basic() -> None:
    row = _make_row()
    result = train_service._map_row_to_train(row)

    assert result["id"] == "T-100"
    assert result["trainName"] == "Alpha Train"
    assert result["site"] == "Plant-A"
    assert result["trainType"] == "Combined Cycle"


def test_map_row_to_train_missing_fields() -> None:
    row: dict[str, Any] = {"train_sys_id_fk": None, "train_name": None, "location": None, "train_type": None}
    result = train_service._map_row_to_train(row)

    assert result["id"] is None
    assert result["trainName"] is None
    assert result["site"] is None
    assert result["trainType"] is None


# ── Unit tests: _group_rows_into_trains ──────────────────────────────────────


def test_group_rows_into_trains_groups_by_train_id() -> None:
    trains = train_service._group_rows_into_trains(SAMPLE_ROWS)

    assert len(trains) == 2

    alpha = next(t for t in trains if t["id"] == "T-100")
    beta = next(t for t in trains if t["id"] == "T-200")

    assert alpha["trainName"] == "Alpha Train"
    assert len(alpha["equipment"]) == 2

    assert beta["trainName"] == "Beta Train"
    assert len(beta["equipment"]) == 1


def test_group_rows_into_trains_equipment_has_correct_serial_numbers() -> None:
    trains = train_service._group_rows_into_trains(SAMPLE_ROWS)

    alpha = next(t for t in trains if t["id"] == "T-100")
    serial_numbers = {e["serialNumber"] for e in alpha["equipment"]}
    assert serial_numbers == {"GT00001", "GEN00002"}


def test_group_rows_into_trains_equipment_mapped_fields() -> None:
    trains = train_service._group_rows_into_trains(SAMPLE_ROWS)

    beta = next(t for t in trains if t["id"] == "T-200")
    equip = beta["equipment"][0]

    assert equip["serialNumber"] == "GT00003"
    assert equip["equipmentType"] == "Gas Turbine"
    assert equip["equipmentCode"] == "9FA.03"
    assert equip["model"] == "9FA"
    assert equip["coolingType"] == "Closed-Loop Water"


def test_group_rows_into_trains_skips_rows_without_train_id() -> None:
    rows = [_make_row(train_sys_id_fk=""), _make_row(train_sys_id_fk=None)]  # type: ignore[arg-type]
    trains = train_service._group_rows_into_trains(rows)
    assert trains == []


def test_group_rows_into_trains_empty_input() -> None:
    trains = train_service._group_rows_into_trains([])
    assert trains == []


# ── Async tests: get_trains ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_trains_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(train_service.config, "USE_MOCK_UNITS", False)
    logged: dict[str, Any] = {}

    def _fake_log_event(**kwargs: Any) -> None:
        logged.update(kwargs)

    monkeypatch.setattr(train_service, "log_read_service_event", _fake_log_event)

    trains = await train_service.get_trains(
        page=1,
        page_size=5,
        user="test-user",
        request_id="req-001",
        db_client=_FakeDbClient(rows=SAMPLE_ROWS),
    )

    assert len(trains) == 2
    alpha = next(t for t in trains if t["id"] == "T-100")
    assert alpha["trainName"] == "Alpha Train"
    assert alpha["site"] == "Plant-A"
    assert len(alpha["equipment"]) == 2

    # Verify logging
    assert logged["event"] == "get_trains"
    assert logged["user"] == "test-user"
    assert logged["request_id"] == "req-001"
    assert logged["error"] is None
    assert isinstance(logged["duration_ms"], int)


@pytest.mark.asyncio
async def test_get_trains_with_search(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that search param is passed through to the SQL query."""
    monkeypatch.setattr(train_service.config, "USE_MOCK_UNITS", False)
    captured_sql: list[str] = []

    class _CapturingClient:
        async def execute_sql(self, sql: str) -> list[dict[str, Any]]:
            captured_sql.append(sql)
            return SAMPLE_ROWS

        def get_last_query_markers(self) -> dict[str, str]:
            return {"naksha_status": "success", "table_status": "available"}

    def _fake_log_event(**kwargs: Any) -> None:
        pass

    monkeypatch.setattr(train_service, "log_read_service_event", _fake_log_event)

    trains = await train_service.get_trains(
        search="alpha",
        db_client=_CapturingClient(),
    )

    assert len(trains) == 2
    assert len(captured_sql) == 1
    assert "'%alpha%'" in captured_sql[0]


@pytest.mark.asyncio
async def test_get_trains_empty_rows_returns_empty_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty SQL result should return [] rather than falling back to mock data."""
    monkeypatch.setattr(train_service.config, "USE_MOCK_UNITS", False)
    logged: dict[str, Any] = {}

    def _fake_log_event(**kwargs: Any) -> None:
        logged.update(kwargs)

    monkeypatch.setattr(train_service, "log_read_service_event", _fake_log_event)

    trains = await train_service.get_trains(
        db_client=_FakeDbClient(rows=[]),
    )

    assert trains == []


@pytest.mark.asyncio
async def test_get_trains_db_error_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """DB errors must propagate rather than silently returning mock data."""
    monkeypatch.setattr(train_service.config, "USE_MOCK_UNITS", False)
    logged: dict[str, Any] = {}

    def _fake_log_event(**kwargs: Any) -> None:
        logged.update(kwargs)

    monkeypatch.setattr(train_service, "log_read_service_event", _fake_log_event)

    with pytest.raises(RuntimeError, match="connection refused"):
        await train_service.get_trains(
            user="svc-a",
            db_client=_FakeDbClient(exc=RuntimeError("connection refused")),
        )

    assert logged["error"] == "connection refused"
    assert logged["error_code"] == "SYSTEM_ERROR"


@pytest.mark.asyncio
async def test_get_trains_train_service_error_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(train_service.config, "USE_MOCK_UNITS", False)
    logged: dict[str, Any] = {}

    def _fake_log_event(**kwargs: Any) -> None:
        logged.update(kwargs)

    monkeypatch.setattr(train_service, "log_read_service_event", _fake_log_event)

    with pytest.raises(train_service.TrainServiceError):
        await train_service.get_trains(
            db_client=_FakeDbClient(exc=train_service.TrainServiceError("BAD_QUERY", "bad sql")),
        )

    assert logged["error"] == "bad sql"
    assert logged["error_code"] == "BAD_QUERY"


@pytest.mark.asyncio
async def test_get_trains_defaults_user_to_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(train_service.config, "USE_MOCK_UNITS", False)
    logged: dict[str, Any] = {}

    def _fake_log_event(**kwargs: Any) -> None:
        logged.update(kwargs)

    monkeypatch.setattr(train_service, "log_read_service_event", _fake_log_event)

    await train_service.get_trains(
        db_client=_FakeDbClient(rows=SAMPLE_ROWS),
    )

    assert logged["user"] == "unknown"


@pytest.mark.asyncio
async def test_get_trains_use_mock_returns_mock_trains() -> None:
    """When USE_MOCK_UNITS=true, get_trains should return MOCK_TRAINS without hitting the DB."""
    # conftest defaults domain mock flags from USE_MOCK=true for test runs
    trains = await train_service.get_trains()
    assert trains == list(MOCK_TRAINS)


@pytest.mark.asyncio
async def test_get_trains_rate_limit_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify the service retries on 429 and eventually returns data."""
    monkeypatch.setattr(train_service.config, "USE_MOCK_UNITS", False)

    call_count = 0

    class _RateLimitThenSucceed:
        async def execute_sql(self, sql: str) -> list[dict[str, Any]]:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("429 Too Many Requests")
            return SAMPLE_ROWS

        def get_last_query_markers(self) -> dict[str, str]:
            return {"naksha_status": "success", "table_status": "available"}

    logged: dict[str, Any] = {}

    def _fake_log_event(**kwargs: Any) -> None:
        logged.update(kwargs)

    monkeypatch.setattr(train_service, "log_read_service_event", _fake_log_event)
    monkeypatch.setenv("TRAIN_RETRY_BACKOFF_SECONDS", "0")

    trains = await train_service.get_trains(
        db_client=_RateLimitThenSucceed(),
    )

    assert len(trains) == 2
    assert call_count == 2
