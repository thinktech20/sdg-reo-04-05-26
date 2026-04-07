"""Tests for heatmap_service."""

from __future__ import annotations

from typing import Any

import pytest

from data_service.services import heatmap_service
from data_service.services import helpers as service_helpers


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


def _sample_row(**overrides: Any) -> dict[str, Any]:
    base = {col: f"val-{col}" for col in heatmap_service.HEATMAP_OUTPUT_COLUMNS}
    base["equipment_type"] = "GEN"
    base["persona"] = "REL"
    base["component"] = "STATOR"
    base["issue_prompt"] = "Check for winding degradation"
    base.update(overrides)
    return base


# ── Validation ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invalid_equipment_type_raises() -> None:
    with pytest.raises(heatmap_service.HeatmapServiceError) as exc:
        await heatmap_service.read_heatmap(
            equipment_type="INVALID",
            persona="REL",
            requesting_user="may",
            db_client=_FakeDbClient(),
        )
    assert exc.value.error_code == "INVALID_INPUT"


@pytest.mark.asyncio
async def test_invalid_persona_raises() -> None:
    with pytest.raises(heatmap_service.HeatmapServiceError) as exc:
        await heatmap_service.read_heatmap(
            equipment_type="GEN",
            persona="UNKNOWN",
            requesting_user="may",
            db_client=_FakeDbClient(),
        )
    assert exc.value.error_code == "INVALID_INPUT"


# ── Happy path ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_success_returns_data_and_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    row = _sample_row()

    async def _fake_merge(table_names: tuple[str, ...], db_client: Any = None) -> dict[str, str]:
        del table_names, db_client
        return {col: f"desc-{col}" for col in heatmap_service.HEATMAP_OUTPUT_COLUMNS}

    monkeypatch.setattr(service_helpers, "merge_table_column_descriptions", _fake_merge)

    response = await heatmap_service.read_heatmap(
        equipment_type="GEN",
        persona="REL",
        requesting_user="may",
        db_client=_FakeDbClient(rows=[row]),
    )

    assert response["status"] == "success"
    assert response["record_count"] == 1
    assert set(response["data"][0].keys()) == set(heatmap_service.HEATMAP_OUTPUT_COLUMNS)
    assert response["metadata"]["equipment_type"] == "GEN"
    assert response["metadata"]["persona"] == "REL"
    assert response["metadata"]["user"] == "may"
    assert "output_columns" in response["metadata"]


@pytest.mark.asyncio
async def test_serial_number_context_is_added_to_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    row = _sample_row()

    async def _fake_merge(table_names: tuple[str, ...], db_client: Any = None) -> dict[str, str]:
        del table_names, db_client
        return {}

    monkeypatch.setattr(service_helpers, "merge_table_column_descriptions", _fake_merge)

    response = await heatmap_service.read_heatmap(
        equipment_type="GEN",
        persona="REL",
        serial_number="270T484",
        requesting_user="may",
        db_client=_FakeDbClient(rows=[row]),
    )

    assert response["metadata"]["serial_number"] == "270T484"


@pytest.mark.asyncio
async def test_component_filter_appears_in_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    row = _sample_row()

    async def _fake_merge(table_names: tuple[str, ...], db_client: Any = None) -> dict[str, str]:
        del table_names, db_client
        return {}

    monkeypatch.setattr(service_helpers, "merge_table_column_descriptions", _fake_merge)

    response = await heatmap_service.read_heatmap(
        equipment_type="GT",
        persona="OE",
        requesting_user="may",
        metadata_filters={"component": "STATOR"},
        db_client=_FakeDbClient(rows=[row]),
    )

    assert response["metadata"]["metadata_filters"]["component"] == "STATOR"
    assert "metadata_filters.component" in response["metadata"]["input_filter_columns"]


# ── Empty result ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_empty_rows_raise_no_data(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_merge(table_names: tuple[str, ...], db_client: Any = None) -> dict[str, str]:
        del table_names, db_client
        return {}

    monkeypatch.setattr(service_helpers, "merge_table_column_descriptions", _fake_merge)

    with pytest.raises(heatmap_service.HeatmapServiceError) as exc:
        await heatmap_service.read_heatmap(
            equipment_type="GEN",
            persona="REL",
            requesting_user="may",
            db_client=_FakeDbClient(rows=[]),
        )
    assert exc.value.error_code == "NO_DATA"


# ── Error mapping ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_permission_error_maps_to_unauthorized(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_merge(table_names: tuple[str, ...], db_client: Any = None) -> dict[str, str]:
        del table_names, db_client
        return {}

    monkeypatch.setattr(service_helpers, "merge_table_column_descriptions", _fake_merge)

    with pytest.raises(heatmap_service.HeatmapServiceError) as exc:
        await heatmap_service.read_heatmap(
            equipment_type="GEN",
            persona="REL",
            requesting_user="may",
            db_client=_FakeDbClient(exc=RuntimeError("Insufficient permission")),
        )
    assert exc.value.error_code == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_generic_error_maps_to_system_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_merge(table_names: tuple[str, ...], db_client: Any = None) -> dict[str, str]:
        del table_names, db_client
        return {}

    monkeypatch.setattr(service_helpers, "merge_table_column_descriptions", _fake_merge)

    with pytest.raises(heatmap_service.HeatmapServiceError) as exc:
        await heatmap_service.read_heatmap(
            equipment_type="GEN",
            persona="OE",
            requesting_user="may",
            db_client=_FakeDbClient(exc=RuntimeError("database timeout")),
        )
    assert exc.value.error_code == "SYSTEM_ERROR"


# ── SQL generation ─────────────────────────────────────────────────────────────


def test_build_query_without_component() -> None:
    sql = heatmap_service.render_query(
        *heatmap_service.build_read_query(
            select_columns=heatmap_service.HEATMAP_SELECT_COLUMNS,
            from_clause=heatmap_service.HEATMAP_VIEW,
            serial_query_column=heatmap_service.HEATMAP_FILTER_QUERY_COLUMN,
            serial_param_name=heatmap_service.HEATMAP_FILTER_PARAM_NAME,
            serial_value="GEN",
            fixed_filters=(("UPPER(persona) = :persona", "persona", "REL"),),
            metadata_filters={},
            metadata_filter_config=heatmap_service.HEATMAP_METADATA_FILTER_CONFIG,
            error_factory=heatmap_service.HeatmapServiceError,
            order_by_clause=heatmap_service.HEATMAP_ORDER_BY_CLAUSE,
        )
    )
    assert "equipment_type" in sql
    assert "'GEN'" in sql
    assert "'REL'" in sql
    assert "component" not in sql.lower().split("where")[1].split("order")[0] or "LIKE" not in sql


def test_build_query_with_component() -> None:
    sql = heatmap_service.render_query(
        *heatmap_service.build_read_query(
            select_columns=heatmap_service.HEATMAP_SELECT_COLUMNS,
            from_clause=heatmap_service.HEATMAP_VIEW,
            serial_query_column=heatmap_service.HEATMAP_FILTER_QUERY_COLUMN,
            serial_param_name=heatmap_service.HEATMAP_FILTER_PARAM_NAME,
            serial_value="GT",
            fixed_filters=(("UPPER(persona) = :persona", "persona", "OE"),),
            metadata_filters={"component": "STATOR"},
            metadata_filter_config=heatmap_service.HEATMAP_METADATA_FILTER_CONFIG,
            error_factory=heatmap_service.HeatmapServiceError,
            order_by_clause=heatmap_service.HEATMAP_ORDER_BY_CLAUSE,
        )
    )
    assert "LIKE" in sql
    assert "%STATOR%" in sql
