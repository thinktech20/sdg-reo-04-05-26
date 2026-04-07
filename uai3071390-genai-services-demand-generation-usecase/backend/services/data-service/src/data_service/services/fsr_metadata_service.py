"""FSR metadata service for resolving document IDs to PDF names.

Uses Databricks SQL to look up PDF display names from the fsr_pdf_ref table.
"""

from __future__ import annotations

from commons.logging import get_logger
from data_service.databricks_client import DatabricksClient
import os

logger = get_logger(__name__)

FSR_CATALOG = os.getenv("FSR_CATALOG", "vgpp")
FSR_SCHEMA = os.getenv("FSR_SCHEMA", "fsr_std_views")
FSR_TABLE = os.getenv("FSR_TABLE", "fsr_field_vision_field_services_report_psot")
FSR_VIEW = os.getenv("FSR_VIEW", f"{FSR_CATALOG}.{FSR_SCHEMA}.{FSR_TABLE}")


async def resolve_pdf_names(
    db_client: DatabricksClient,
    document_ids: list[str],
) -> dict[str, str]:
    """Resolve a batch of document IDs to their PDF display names.

    Issues a single SQL query with an IN clause to resolve all unique
    document IDs at once, keeping the overhead to one Databricks roundtrip.

    Args:
        db_client: An initialised DatabricksClient instance.
        document_ids: List of document identifier strings (pdf_name column
            values returned by the vector search index).

    Returns:
        Dict mapping document_id -> resolved PDF_name.
    """
    unique_ids = list({did.strip() for did in document_ids if did and did.strip()})
    if not unique_ids:
        return {}

    # Build a safe IN-clause using parameterised literals
    in_values = ", ".join(f"'{did.replace(chr(39), chr(39)*2)}'" for did in unique_ids)

    query = (
        f"SELECT s3_filename, PDF_name "
        f"FROM {FSR_VIEW} "
        f"WHERE s3_filename IN ({in_values}) "
        f"   OR PDF_name IN ({in_values})"
    )

    try:
        rows = await db_client.query_async(query)
    except Exception:
        logger.warning("Batch PDF name resolution query failed, keeping original IDs", exc_info=True)
        return {}

    # Build lookup: match on s3_filename first, then PDF_name
    resolved: dict[str, str] = {}
    s3_to_pdf: dict[str, str] = {}
    pdfname_set: dict[str, str] = {}

    for row in rows:
        s3 = row.get("s3_filename") or row.get("S3_FILENAME") or ""
        pdf = row.get("PDF_name") or row.get("pdf_name") or ""
        if s3:
            s3_to_pdf[s3.strip()] = pdf
        if pdf:
            pdfname_set[pdf.strip()] = pdf

    for doc_id in unique_ids:
        if doc_id in s3_to_pdf:
            resolved[doc_id] = s3_to_pdf[doc_id]
        elif doc_id in pdfname_set:
            resolved[doc_id] = pdfname_set[doc_id]

    logger.info("Resolved %d / %d document IDs to PDF names", len(resolved), len(unique_ids))
    return resolved