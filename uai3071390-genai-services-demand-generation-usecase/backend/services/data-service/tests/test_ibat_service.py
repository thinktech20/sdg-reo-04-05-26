from __future__ import annotations

from typing import Any

import pytest

from data_service.services import helpers as service_helpers
from data_service.services import ibat_service


class _FakeDbClient:
    def __init__(
        self,
        rows: list[dict[str, Any]] | None = None,
        exc: Exception | None = None,
        markers: dict[str, str] | None = None,
    ) -> None:
        self._rows = rows or []
        self._exc = exc
        self._markers = markers or {"naksha_status": "success", "table_status": "available"}

    async def execute_sql(self, sql: str) -> list[dict[str, Any]]:
        del sql
        if self._exc is not None:
            raise self._exc
        return self._rows

    def get_last_query_markers(self) -> dict[str, str]:
        return dict(self._markers)


@pytest.mark.asyncio
async def test_read_ibat_success_includes_all_ax_columns_and_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    row = {column: f"value-{column}" for column in ibat_service.IBAT_OUTPUT_COLUMNS}
    row["duty_cycle"] = ""
    row["actualized_flag"] = None
    row["equipment_code"] = "n/a"

    async def _fake_merge_descriptions(table_names: tuple[str, ...], db_client: Any = None) -> dict[str, str]:
        del table_names, db_client
        return {column: f"desc-{column}" for column in ibat_service.IBAT_OUTPUT_COLUMNS}

    logged: dict[str, Any] = {}

    def _fake_log_event(**kwargs: Any) -> None:
        logged.update(kwargs)

    monkeypatch.setattr(service_helpers, "merge_table_column_descriptions", _fake_merge_descriptions)
    monkeypatch.setattr(ibat_service, "log_read_service_event", _fake_log_event)

    response = await ibat_service.read_ibat_by_serial(
        equip_serial_number="342447641",
        user="may",
        db_client=_FakeDbClient(rows=[row]),
    )

    assert response["status"] == "success"
    assert response["record_count"] == 1
    assert set(response["data"][0].keys()) == set(ibat_service.IBAT_OUTPUT_COLUMNS)

    assert response["data"][0]["duty_cycle"] is None
    assert response["data"][0]["actualized_flag"] is None
    assert response["data"][0]["equipment_code"] == "n/a"

    assert response["metadata"]["serial_number"] == "342447641"
    assert response["metadata"]["user"] == "may"
    assert response["metadata"]["request_id"] is None
    assert set(response["metadata"]["output_columns"].keys()) == set(ibat_service.IBAT_OUTPUT_COLUMNS)

    assert logged["event"] == "read_ibat_by_serial"
    assert logged["user"] == "may"
    assert logged["serial_number"] == "342447641"
    assert logged["request_id"] is None
    assert logged["error"] is None
    assert logged["result_ids"] == ["value-equip_serial_number"]
    assert isinstance(logged["duration_ms"], int)


@pytest.mark.asyncio
async def test_read_ibat_maps_permission_errors_to_unauthorized(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_merge_descriptions(table_names: tuple[str, ...], db_client: Any = None) -> dict[str, str]:
        del table_names, db_client
        return {}

    monkeypatch.setattr(service_helpers, "merge_table_column_descriptions", _fake_merge_descriptions)

    with pytest.raises(ibat_service.IbatServiceError) as exc:
        await ibat_service.read_ibat_by_serial(
            equip_serial_number="ESN001",
            user="svc-a",
            db_client=_FakeDbClient(exc=RuntimeError("Insufficient permission to read table")),
        )

    assert exc.value.error_code == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_read_ibat_maps_other_errors_to_system_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_merge_descriptions(table_names: tuple[str, ...], db_client: Any = None) -> dict[str, str]:
        del table_names, db_client
        return {}

    monkeypatch.setattr(service_helpers, "merge_table_column_descriptions", _fake_merge_descriptions)

    with pytest.raises(ibat_service.IbatServiceError) as exc:
        await ibat_service.read_ibat_by_serial(
            equip_serial_number="ESN001",
            user="svc-a",
            db_client=_FakeDbClient(exc=RuntimeError("database timeout")),
        )

    assert exc.value.error_code == "SYSTEM_ERROR"
    assert exc.value.message == "An internal error occurred"


@pytest.mark.asyncio
async def test_read_ibat_rejects_unsupported_metadata_filter() -> None:
    with pytest.raises(ibat_service.IbatServiceError) as exc:
        await ibat_service.read_ibat_by_serial(
            equip_serial_number="ESN001",
            user="svc-a",
            metadata_filters={"bad_field": "x"},
            db_client=_FakeDbClient(rows=[]),
        )

    assert exc.value.error_code == "INVALID_INPUT"


@pytest.mark.asyncio
async def test_read_ibat_empty_rows_raise_serial_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_merge_descriptions(table_names: tuple[str, ...], db_client: Any = None) -> dict[str, str]:
        del table_names, db_client
        return {column: f"desc-{column}" for column in ibat_service.IBAT_OUTPUT_COLUMNS}

    monkeypatch.setattr(service_helpers, "merge_table_column_descriptions", _fake_merge_descriptions)

    with pytest.raises(ibat_service.IbatServiceError) as exc:
        await ibat_service.read_ibat_by_serial(
            equip_serial_number="ESN404",
            user="svc-a",
            db_client=_FakeDbClient(rows=[]),
        )

    assert exc.value.error_code == "SERIAL_NOT_FOUND"
    assert "No records found for serial ESN404" in exc.value.message


@pytest.mark.asyncio
async def test_read_ibat_rejects_empty_serial():
    with pytest.raises(ibat_service.IbatServiceError) as exc:
        await ibat_service.read_ibat_by_serial(
            equip_serial_number="",
            db_client=_FakeDbClient(),
        )
    assert exc.value.error_code == "INVALID_INPUT"


@pytest.mark.asyncio
async def test_read_ibat_rejects_non_dict_metadata_filters():
    with pytest.raises(ibat_service.IbatServiceError) as exc:
        await ibat_service.read_ibat_by_serial(
            equip_serial_number="ESN001",
            metadata_filters="bad",  # type: ignore[arg-type]
            db_client=_FakeDbClient(),
        )
    assert exc.value.error_code == "INVALID_INPUT"


@pytest.mark.asyncio
async def test_read_ibat_rate_limit_error_maps_correctly(monkeypatch: pytest.MonkeyPatch) -> None:
    from data_service.client import NakshaRateLimitError

    async def _fake_merge_descriptions(table_names: tuple[str, ...], db_client: Any = None) -> dict[str, str]:
        del table_names, db_client
        return {}

    monkeypatch.setattr(service_helpers, "merge_table_column_descriptions", _fake_merge_descriptions)

    with pytest.raises(ibat_service.IbatServiceError) as exc:
        await ibat_service.read_ibat_by_serial(
            equip_serial_number="ESN001",
            user="svc-a",
            db_client=_FakeDbClient(exc=NakshaRateLimitError("429 Too Many Requests")),
        )
    assert exc.value.error_code == "RATE_LIMITED"


# ── search_equipment_by_esn ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_equipment_empty_esn_returns_none():
    result = await ibat_service.search_equipment_by_esn(esn="", db_client=_FakeDbClient())
    assert result is None


@pytest.mark.asyncio
async def test_search_equipment_ibat_error_returns_mock_fallback(monkeypatch: pytest.MonkeyPatch):
    async def _fake_merge_descriptions(table_names: tuple[str, ...], db_client: Any = None) -> dict[str, str]:
        del table_names, db_client
        return {}

    monkeypatch.setattr(service_helpers, "merge_table_column_descriptions", _fake_merge_descriptions)

    result = await ibat_service.search_equipment_by_esn(
        esn="GT12345",
        db_client=_FakeDbClient(exc=RuntimeError("db error")),
    )
    # Falls back to MOCK_INSTALL_BASE entry
    assert result is not None
    assert result["serialNumber"] == "GT12345"


@pytest.mark.asyncio
async def test_search_equipment_ibat_success_returns_mapped(monkeypatch: pytest.MonkeyPatch):
    ibat_row = {
        "equip_serial_number": "GT12345",
        "equipment_type": "Gas Turbine",
        "equipment_code": "7FA.05",
        "equipment_class": "F-class",
        "plant_name": "Test Plant",
        "cooling_system": "Air",
    }

    async def _fake_merge_descriptions(table_names: tuple[str, ...], db_client: Any = None) -> dict[str, str]:
        del table_names, db_client
        return {column: f"desc-{column}" for column in ibat_service.IBAT_OUTPUT_COLUMNS}

    monkeypatch.setattr(service_helpers, "merge_table_column_descriptions", _fake_merge_descriptions)

    # Build a complete row with all columns
    full_row = {col: f"value-{col}" for col in ibat_service.IBAT_OUTPUT_COLUMNS}
    full_row.update(ibat_row)

    result = await ibat_service.search_equipment_by_esn(
        esn="GT12345",
        db_client=_FakeDbClient(rows=[full_row]),
    )
    assert result is not None
    assert result["serialNumber"] == "GT12345"
    assert result["equipmentType"] == "Gas Turbine"


# ── _map_ibat_to_equipment / _map_ibat_record_to_equipment ────────────────────


def test_map_ibat_to_equipment():
    record = {
        "equip_serial_number": "GT12345",
        "equipment_type": "Gas Turbine",
        "equipment_code": "7FA.05",
        "equipment_class": "F-class",
        "plant_name": "Test Plant",
        "cooling_system": "Air",
    }
    result = ibat_service._map_ibat_to_equipment(record, serial_number="GT12345")
    assert result["serialNumber"] == "GT12345"
    assert result["equipmentType"] == "Gas Turbine"
    assert result["model"] == "F-class"
    assert result["site"] == "Test Plant"
    assert result["coolingType"] == "Air"


def test_map_ibat_record_to_equipment_delegates():
    record = {"equip_serial_number": "X123", "equipment_type": "Generator"}
    result = ibat_service._map_ibat_record_to_equipment(record, serial_number="X123")
    assert result["serialNumber"] == "X123"
