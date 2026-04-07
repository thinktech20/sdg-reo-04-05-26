"""Tests for data_service.schema_metadata."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from data_service.schema_metadata import _split_table_name, get_table_column_descriptions

# ---------------------------------------------------------------------------
# _split_table_name
# ---------------------------------------------------------------------------


def test_split_table_name_valid() -> None:
    assert _split_table_name("main.sales.equipment") == ("main", "sales", "equipment")


def test_split_table_name_extra_dots_skipped() -> None:
    # Leading/trailing dots produce empty parts that are filtered out
    assert _split_table_name(".main.sales.equipment.") == ("main", "sales", "equipment")


def test_split_table_name_too_few_parts() -> None:
    with pytest.raises(ValueError, match="Expected fully-qualified"):
        _split_table_name("sales.equipment")


def test_split_table_name_too_many_parts() -> None:
    with pytest.raises(ValueError, match="Expected fully-qualified"):
        _split_table_name("a.b.c.d")


def test_split_table_name_empty() -> None:
    with pytest.raises(ValueError, match="Expected fully-qualified"):
        _split_table_name("")


# ---------------------------------------------------------------------------
# get_table_column_descriptions — happy paths
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_returns_descriptions_lowercase_keys() -> None:
    mock_client = MagicMock()
    mock_client.execute_sql = AsyncMock(
        return_value=[
            {"column_name": "serial_number", "column_comment": "Equipment serial"},
            {"column_name": "status", "column_comment": "Current status"},
        ]
    )

    result = await get_table_column_descriptions("cat.sch.tbl", db_client=mock_client)

    assert result == {
        "serial_number": "Equipment serial",
        "status": "Current status",
    }


@pytest.mark.anyio
async def test_accepts_uppercase_column_keys() -> None:
    """Rows with UPPER-CASE keys from some JDBC drivers are normalised."""
    mock_client = MagicMock()
    mock_client.execute_sql = AsyncMock(
        return_value=[
            {"COLUMN_NAME": "esn", "COLUMN_COMMENT": "Engine serial number"},
        ]
    )

    result = await get_table_column_descriptions("cat.sch.tbl", db_client=mock_client)

    assert result == {"esn": "Engine serial number"}


@pytest.mark.anyio
async def test_accepts_comment_key_fallback() -> None:
    """Falls back to 'comment' when 'column_comment' is absent."""
    mock_client = MagicMock()
    mock_client.execute_sql = AsyncMock(
        return_value=[
            {"column_name": "foo", "comment": "A foo column"},
        ]
    )

    result = await get_table_column_descriptions("cat.sch.tbl", db_client=mock_client)

    assert result == {"foo": "A foo column"}


@pytest.mark.anyio
async def test_empty_rows_returns_empty_dict() -> None:
    mock_client = MagicMock()
    mock_client.execute_sql = AsyncMock(side_effect=[[], []])

    result = await get_table_column_descriptions("cat.sch.tbl", db_client=mock_client)

    assert result == {}


@pytest.mark.anyio
async def test_falls_back_to_describe_when_information_schema_is_empty() -> None:
    mock_client = MagicMock()
    mock_client.execute_sql = AsyncMock(
        side_effect=[
            [],
            [
                {"col_name": "fsp_event_id", "comment": "FSP event identifier"},
                {"col_name": "equip_serial_number", "comment": "Equipment serial number"},
                {"col_name": "# Partition Information", "comment": ""},
            ],
        ]
    )

    result = await get_table_column_descriptions("cat.sch.tbl", db_client=mock_client)

    assert result == {
        "fsp_event_id": "FSP event identifier",
        "equip_serial_number": "Equipment serial number",
    }
    assert mock_client.execute_sql.await_count == 2


@pytest.mark.anyio
async def test_rows_with_missing_column_name_are_skipped() -> None:
    mock_client = MagicMock()
    mock_client.execute_sql = AsyncMock(
        return_value=[
            {"column_comment": "no name here"},
            {"column_name": "good_col", "column_comment": "kept"},
        ]
    )

    result = await get_table_column_descriptions("cat.sch.tbl", db_client=mock_client)

    assert result == {"good_col": "kept"}


@pytest.mark.anyio
async def test_rows_with_empty_column_name_are_skipped() -> None:
    mock_client = MagicMock()
    mock_client.execute_sql = AsyncMock(
        return_value=[
            {"column_name": "   ", "column_comment": "blank name"},
            {"column_name": "real_col", "column_comment": "ok"},
        ]
    )

    result = await get_table_column_descriptions("cat.sch.tbl", db_client=mock_client)

    assert result == {"real_col": "ok"}


@pytest.mark.anyio
async def test_null_comment_becomes_empty_string() -> None:
    mock_client = MagicMock()
    mock_client.execute_sql = AsyncMock(
        return_value=[
            {"column_name": "col_a", "column_comment": None},
        ]
    )

    result = await get_table_column_descriptions("cat.sch.tbl", db_client=mock_client)

    assert result == {"col_a": ""}


# ---------------------------------------------------------------------------
# get_table_column_descriptions — SQL query construction
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_sql_contains_schema_and_table_literals() -> None:
    """Schema and table names must appear as quoted SQL literals in the query."""
    captured: list[str] = []
    mock_client = MagicMock()

    async def _capture_sql(sql: str) -> list[dict[str, object]]:
        captured.append(sql)
        return []

    mock_client.execute_sql = _capture_sql

    await get_table_column_descriptions("mycat.myschema.mytable", db_client=mock_client)

    assert captured, "execute_sql was never called"
    sql = captured[0]
    assert "'myschema'" in sql
    assert "'mytable'" in sql
    assert "mycat.information_schema.columns" in sql


# ---------------------------------------------------------------------------
# get_table_column_descriptions — default client creation
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_creates_default_client_when_none_given(monkeypatch: pytest.MonkeyPatch) -> None:
    """When db_client is None, a NakshaClient is instantiated automatically."""
    created: list[object] = []

    mock_instance = MagicMock()
    mock_instance.execute_sql = AsyncMock(return_value=[])

    def _fake_client(**_kwargs: object) -> MagicMock:
        created.append(mock_instance)
        return mock_instance

    monkeypatch.setattr("data_service.schema_metadata.NakshaClient", _fake_client)

    await get_table_column_descriptions("c.s.t")

    assert len(created) == 1
