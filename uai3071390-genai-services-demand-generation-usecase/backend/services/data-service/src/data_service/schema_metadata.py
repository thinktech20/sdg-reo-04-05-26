from __future__ import annotations

from commons.logging import get_logger
from data_service.client import NakshaClient
from data_service.services.helpers import sql_literal

logger = get_logger(__name__)


def _split_table_name(table_name: str) -> tuple[str, str, str]:
    parts = [p for p in table_name.split(".") if p]
    if len(parts) != 3:
        raise ValueError(f"Expected fully-qualified table name catalog.schema.table, got: {table_name}")
    return parts[0], parts[1], parts[2]


def _row_value(row: dict[str, object], *candidate_keys: str) -> str:
    normalized = {str(key).strip().lower(): value for key, value in row.items()}
    for candidate in candidate_keys:
        if candidate.strip().lower() in normalized:
            return str(normalized[candidate.strip().lower()] or "")
    return ""


def _descriptions_from_information_schema(rows: list[dict[str, object]]) -> dict[str, str]:
    descriptions: dict[str, str] = {}
    for row in rows:
        key = _row_value(row, "column_name", "COLUMN_NAME").strip()
        if not key:
            continue
        descriptions[key] = _row_value(row, "column_comment", "COLUMN_COMMENT", "comment", "COMMENT")
    return descriptions


def _descriptions_from_describe_rows(rows: list[dict[str, object]]) -> dict[str, str]:
    descriptions: dict[str, str] = {}
    for row in rows:
        key = _row_value(row, "col_name", "column_name").strip()
        if not key or key.startswith("#"):
            continue
        descriptions[key] = _row_value(row, "comment", "column_comment")
    return descriptions


async def get_table_column_descriptions(
    table_name: str,
    db_client: NakshaClient | None = None,
) -> dict[str, str]:
    client = db_client or NakshaClient()
    catalog, schema, table = _split_table_name(table_name)

    query = f"""
        SELECT
            column_name,
            COALESCE(comment, '') AS column_comment
        FROM {catalog}.information_schema.columns
        WHERE LOWER(table_schema) = LOWER({sql_literal(schema)})
          AND LOWER(table_name) = LOWER({sql_literal(table)})
        ORDER BY ordinal_position
    """  # nosec B608

    logger.info("schema_metadata path=information_schema stage=start table=%s", table_name)
    rows = await client.execute_sql(query)
    descriptions = _descriptions_from_information_schema(rows)
    logger.info(
        "schema_metadata path=information_schema stage=done table=%s row_count=%s column_count=%s",
        table_name,
        len(rows),
        len(descriptions),
    )
    if descriptions:
        return descriptions

    describe_query = f"DESCRIBE TABLE {table_name}"  # nosec B608
    logger.info("schema_metadata path=describe_table stage=start table=%s", table_name)
    describe_rows = await client.execute_sql(describe_query)
    describe_descriptions = _descriptions_from_describe_rows(describe_rows)
    logger.info(
        "schema_metadata path=describe_table stage=done table=%s row_count=%s column_count=%s",
        table_name,
        len(describe_rows),
        len(describe_descriptions),
    )
    return describe_descriptions
