from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from data_service.services import helpers as service_helpers


@pytest.mark.asyncio
async def test_merge_table_column_descriptions_caches_empty_results(monkeypatch: pytest.MonkeyPatch) -> None:
    service_helpers._description_cache.clear()
    get_descriptions = AsyncMock(return_value={})

    monkeypatch.setattr(
        "data_service.schema_metadata.get_table_column_descriptions",
        get_descriptions,
    )

    first = await service_helpers.merge_table_column_descriptions(("cat.sch.tbl",), db_client=object())
    second = await service_helpers.merge_table_column_descriptions(("cat.sch.tbl",), db_client=object())

    assert first == {}
    assert second == {}
    assert get_descriptions.await_count == 1


@pytest.mark.asyncio
async def test_merge_table_column_descriptions_returns_cached_empty_for_mixed_tables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service_helpers._description_cache.clear()

    async def _fake(table_name: str, db_client: object | None = None) -> dict[str, str]:
        del db_client
        if table_name == "cat.sch.empty":
            return {}
        return {"serial_number": "Equipment serial"}

    get_descriptions = AsyncMock(side_effect=_fake)
    monkeypatch.setattr(
        "data_service.schema_metadata.get_table_column_descriptions",
        get_descriptions,
    )

    first = await service_helpers.merge_table_column_descriptions(
        ("cat.sch.empty", "cat.sch.full"),
        db_client=object(),
    )
    second = await service_helpers.merge_table_column_descriptions(
        ("cat.sch.empty", "cat.sch.full"),
        db_client=object(),
    )

    assert first == {"serial_number": "Equipment serial"}
    assert second == {"serial_number": "Equipment serial"}
    assert get_descriptions.await_count == 2


@pytest.mark.asyncio
async def test_execute_read_with_descriptions_preserves_main_query_markers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _SharedClient:
        def __init__(self) -> None:
            self._markers = {"naksha_status": "unknown", "table_status": "unknown"}
            self._main_read_done = asyncio.Event()

        async def execute_sql(self, sql: str) -> list[dict[str, object]]:
            del sql
            self._markers = {
                "naksha_status": "fallback_databricks",
                "table_status": "available",
            }
            self._main_read_done.set()
            return [{"issue_name": "Rotor issue"}]

        def get_last_query_markers(self) -> dict[str, str]:
            return dict(self._markers)

    async def _fake_merge(table_names: tuple[str, ...], db_client: _SharedClient | None = None) -> dict[str, str]:
        del table_names
        assert db_client is not None
        await db_client._main_read_done.wait()
        db_client._markers = {
            "naksha_status": "success",
            "table_status": "available",
        }
        return {"issue_name": "Issue description"}

    client = _SharedClient()
    monkeypatch.setattr(service_helpers, "merge_table_column_descriptions", _fake_merge)

    rows, descriptions, query_markers = await service_helpers.execute_read_with_descriptions(
        sql="SELECT issue_name FROM some_table",
        description_tables=("cat.sch.tbl",),
        query_client=client,
        max_attempts=1,
        backoff_seconds=0,
        retry_if=lambda exc: False,
    )

    assert rows == [{"issue_name": "Rotor issue"}]
    assert descriptions == {"issue_name": "Issue description"}
    assert query_markers == {
        "naksha_status": "fallback_databricks",
        "table_status": "available",
    }
