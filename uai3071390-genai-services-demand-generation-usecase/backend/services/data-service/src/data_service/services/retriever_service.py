"""Retriever service for FSR (Field Service Reports) semantic search.

Uses Databricks vector search to retrieve relevant technical documents.
"""

from __future__ import annotations

import json
import os
from typing import Any

import requests

from commons.logging import get_logger

# Import config to ensure .env is loaded before reading env vars
from data_service import config  # noqa: F401
from data_service.databricks_client import DatabricksClient
from data_service.services.fsr_metadata_service import resolve_pdf_names

logger = get_logger(__name__)


class RetrieverServiceError(Exception):
    """Raised when retriever service encounters an error."""

    def __init__(self, message: str, error_code: str = "RETRIEVER_ERROR") -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code


async def retrieve_issue_data(
    issue_prompts: list[dict[str, str]] | None = None,
    esn: str | None = None,
    top_k: int = 10,
    *,
    query: str | None = None,
    component_type: str | None = None,
) -> str:
    """Retrieve FSR evidence in either legacy single-query or batch issue-prompt mode.

    Legacy mode is selected when `issue_prompts` is not provided.
    Batch mode is selected when `issue_prompts` is provided.
    """
    if issue_prompts is not None:
        return await _retrieve_issue_data_batch(issue_prompts=issue_prompts, esn=esn, top_k=top_k)

    return await _retrieve_issue_data_legacy(
        query=query,
        esn=esn,
        top_k=top_k,
        component_type=component_type,
    )


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


async def _retrieve_issue_data_legacy(
    query: str | None,
    esn: str | None,
    top_k: int,
    component_type: str | None,
) -> str:
    """Compatibility path for existing unit tests and legacy callers."""
    sanitized_query = (query.strip() if isinstance(query, str) else "")
    if not sanitized_query:
        return json.dumps({"error": "Query is required for FSR analysis", "data": []})

    if not (1 <= top_k <= 20):
        return json.dumps({"error": "top_k must be between 1 and 20", "data": []})

    cfg = {
        "workspace_url": os.getenv("DATABRICKS_WORKSPACE_URL", "https://gevernova-ai-dev-dbr.cloud.databricks.com"),
        "token": os.getenv("DATABRICKS_TOKEN", ""),
        # "endpoint": os.getenv("VECTOR_SEARCH_ENDPOINT", ""),
        "index": os.getenv("VECTOR_SEARCH_INDEX", "main.gp_services_sdg_poc.vs_field_service_report_gt_litellm"),
    }
    missing = [k for k, v in cfg.items() if not v]
    if missing:
        return json.dumps({"error": f"Missing required Databricks config: {', '.join(missing)}", "data": []})

    query_prefix = (component_type.strip() if isinstance(component_type, str) else "")
    query_text = f"{query_prefix}: {sanitized_query}" if query_prefix else sanitized_query

    sanitized_esn = (esn.strip() if isinstance(esn, str) else "")
    filters = {"generator_serial": sanitized_esn} if sanitized_esn else None

    try:
        from databricks.vector_search.client import VectorSearchClient
    except Exception as exc:
        return json.dumps({"error": f"Databricks retrieval failed: {exc}", "data": []})

    try:
        client = VectorSearchClient(
            workspace_url=cfg["workspace_url"],
            personal_access_token=cfg["token"],
        )
    except Exception as exc:
        return json.dumps({"error": f"Databricks retrieval failed: {exc}", "data": []})

    try:
        index = client.get_index(
            endpoint_name=cfg["endpoint"],
            index_name=cfg["index"],
        )
    except Exception as exc:
        return json.dumps({"error": f"Failed to connect to Databricks index: {exc}", "data": []})

    try:
        results = index.similarity_search(
            query_text=query_text,
            columns=["chunk_text", "pdf_name", "page_number", "report_date", "score"],
            num_results=top_k,
            filters=filters,
        )
    except Exception as exc:
        return json.dumps({"error": f"Vector search failed: {exc}", "data": []})

    try:
        rows = results.get("result", {}).get("data_array", [])
        if not isinstance(rows, list):
            rows = []

        delta = float(os.getenv("SIMILARITY_SCORE_DELTA", "0.025"))
        formatted: list[dict[str, Any]] = []
        prev_score: float | None = None

        for row in rows[:10]:
            if not isinstance(row, list):
                continue

            score = _safe_float(row[4] if len(row) > 4 else None)
            if prev_score is not None and score is not None and prev_score - score > delta:
                break

            formatted.append(
                {
                    "#": len(formatted) + 1,
                    "Evidence": row[0] if len(row) > 0 else "",
                    "Document Name": row[1] if len(row) > 1 else "",
                    "Page Number": row[2] if len(row) > 2 else "",
                    "Report Date": row[3] if len(row) > 3 else "",
                    "Similarity Score": score if score is not None else 0,
                }
            )
            if score is not None:
                prev_score = score

        return json.dumps({"data": formatted})
    except Exception as exc:
        return json.dumps({"error": f"Databricks retrieval failed: {exc}", "data": []})


async def _retrieve_issue_data_batch(
    issue_prompts: list[dict[str, str]],
    esn: str | None = None,
    top_k: int = 10,
) -> str:
    """
    Search Field Service Reports (FSR) using semantic search from Databricks
    for a list of issue prompts.

    Each item in issue_prompts must be a dict with:
        - "issue_id":     A UUID string identifying the issue
        - "issue_prompt": Natural language query describing the issue

    The method processes each issue prompt serially and returns all results
    grouped by issue_id.

    Use this for:
    - DC leakage test analysis and results
    - Field service report queries
    - Technical document analysis
    - Equipment inspection reports
    - Component failure analysis
    - Test methodology and acceptance criteria
    - Generator serial number lookups

    Args:
        issue_prompts: List of dicts, each with "issue_id" (UUID) and "issue_prompt" (query text)
        esn: Equipment serial number (generator_serial) to filter results
        top_k: Number of documents to retrieve per issue. Default: 10

    Returns:
        JSON string with:
        {
            "data": {
                "<issue_id>": [
                    {"#", "chunk_id", "Document Name", "Page Number", "Evidence", "ESN"},
                    ...
                ],
                ...
            }
        }
        On top-level validation/config error:
        {"error": "...", "data": {}}
    """
    # ==================== Top-level validation (shared across all issues) ====================

    sanitized_esn: str | None = (esn.strip() or None) if isinstance(esn, str) else None
    if not sanitized_esn:
        return json.dumps({"error": "ESN (Equipment Serial Number) is required for FSR analysis", "data": {}})

    if not (1 <= top_k <= 10):
        return json.dumps({"error": "top_k must be between 1 and 10", "data": {}})

    if not issue_prompts:
        return json.dumps({"error": "issue_prompts list is empty", "data": {}})

    # Load embedding table name once — same for all issue prompts
    embedding_table = os.getenv("EMBEDDING_TABLE_NAME", "main.gp_services_sdg_poc.heatmap_issue_prompt_embeddings").strip()
    if not embedding_table:
        return json.dumps({"error": "Missing required env var: EMBEDDING_TABLE_NAME", "data": {}})

    # Load Databricks vector search config once — same for all issue prompts
    # Use local proxy (host machine) to bypass Databricks IP restrictions in Docker
    #_VECTOR_PROXY_URL = os.getenv("VECTOR_SEARCH_PROXY_URL", "http://host.docker.internal:9999")
    cfg = {
        "workspace_url": os.getenv("VECTOR_DATABRICKS_WORKSPACE_URL", "https://gevernova-ai-dev-dbr.cloud.databricks.com"), #When container IP has access to Databricks workspace, use this direct URL
        #"workspace_url": _VECTOR_PROXY_URL,  # Use proxy URL to bypass IP restrictions when running in Docker
        "token": os.getenv("VECTOR_DATABRICKS_TOKEN", ""),
        "index": os.getenv("VECTOR_SEARCH_INDEX", "main.gp_services_sdg_poc.vs_field_service_report_gt_litellm"),
    }
    missing = [k for k, v in cfg.items() if not v]
    if missing:
        error_msg = f"Missing required Databricks config env vars: {', '.join(missing)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg, "data": {}})
    else:
        logger.info("Databricks config loaded for index '%s'", cfg["index"])

    db_client = DatabricksClient()

    # Accumulate results keyed by issue_id
    result_data: dict[str, list[dict[str, Any]]] = {}

    # ==================== Process each issue prompt serially ====================
    for item in issue_prompts:
        issue_id: str = item.get("issue_id", "")
        issue_prompt: str = item.get("issue_prompt", "")

        # Validate per-item fields
        if not issue_id:
            logger.warning("Skipping item with missing issue_id: %s", item)
            continue

        sanitized_query: str | None = (issue_prompt.strip() or None) if isinstance(issue_prompt, str) else None
        if not sanitized_query:
            logger.warning("Skipping issue_id='%s': issue_prompt is empty", issue_id)
            result_data[issue_id] = []
            continue

        logger.info(
            "FSR analysis: issue_id='%s', query='%s', esn=%s, top_k=%d",
            issue_id, sanitized_query[:50], sanitized_esn, top_k,
        )

        # ========== STEP 1: Retrieve issue prompt embedding ==========
        try:
            rows = await db_client.query_async(
                f"SELECT issue_prompt_embedding "
                f"FROM {embedding_table} "
                f"WHERE LOWER(TRIM(issue_prompt)) = LOWER(TRIM(:sanitized_query))",
                {"sanitized_query": sanitized_query},
            )
        except Exception as e:
            logger.error(
                "Embedding query failed for issue_id='%s': %s: %s",
                issue_id, type(e).__name__, e, exc_info=True,
            )
            result_data[issue_id] = []
            continue

        if not rows:
            logger.warning(
                "No embedding found for issue_id='%s', issue_prompt=%r",
                issue_id, sanitized_query,
            )
            result_data[issue_id] = []
            continue

        try:
            raw_embedding = rows[0]["issue_prompt_embedding"]
            if isinstance(raw_embedding, str):
                raw_embedding = json.loads(raw_embedding)
            issue_prompt_embedding = [float(v) for v in raw_embedding]
        except (KeyError, json.JSONDecodeError, TypeError, ValueError) as e:
            logger.error(
                "Failed to parse embedding for issue_id='%s': %s: %s",
                issue_id, type(e).__name__, e, exc_info=True,
            )
            result_data[issue_id] = []
            continue

        logger.info("Embedding retrieved successfully for issue_id='%s'", issue_id)

        # ========== STEP 2: Retrieve chunks through Hybrid Search ==========
        try:
            response = requests.post(
                f"{cfg['workspace_url']}/api/2.0/vector-search/indexes/{cfg['index']}/query",
                headers={
                    "Authorization": f"Bearer {cfg['token']}",
                    "Content-Type": "application/json",
                },
                json={
                    "query_text": sanitized_query,
                    "query_vector": issue_prompt_embedding,
                    "filters_json": json.dumps({"generator_serial": sanitized_esn}),
                    "num_results": top_k,
                    "query_type": "HYBRID",
                    "columns": ["chunk_id", "pdf_name", "page_number", "chunk_text", "generator_serial"],
                },
                timeout=300,
                verify=False,
            )
            response.raise_for_status()
            search_results = response.json()
        except requests.exceptions.Timeout:
            logger.error("Vector search timed out for issue_id='%s'", issue_id)
            result_data[issue_id] = []
            continue
        except requests.exceptions.HTTPError as e:
            logger.error(
                "Vector search HTTP error for issue_id='%s': %d: %s",
                issue_id, e.response.status_code, e.response.text[:200], exc_info=True,
            )
            result_data[issue_id] = []
            continue
        except (requests.exceptions.RequestException, Exception) as e:
            logger.error(
                "Vector search request failed for issue_id='%s': %s: %s",
                issue_id, type(e).__name__, e, exc_info=True,
            )
            result_data[issue_id] = []
            continue

        data = search_results.get("result", {}).get("data_array", [])
        logger.info("Vector search returned %d results for issue_id='%s'", len(data), issue_id)

        if not data:
            result_data[issue_id] = []
            continue

        # ========== STEP 3: Deduplicate + format ==========
        formatted_data: list[dict[str, Any]] = []
        seen_chunk_ids: set[str] = set()
        rank = 0

        for row in data[:10]:  # Process at most top 10
            chunk_id = row[0] if len(row) > 0 else ""
            if chunk_id in seen_chunk_ids:
                logger.info(
                    "issue_id='%s': discarded duplicate chunk_id='%s'",
                    issue_id, chunk_id,
                )
                continue
            seen_chunk_ids.add(chunk_id)
            rank += 1
            formatted_data.append({
                "#": rank,
                "chunk_id": chunk_id,
                "Document Name": row[1] if len(row) > 1 else "",
                "Page Number": row[2] if len(row) > 2 else "",
                "Evidence": row[3] if len(row) > 3 else "",
                "ESN": row[4] if len(row) > 4 else "",
                "Similarity Score": row[5] if len(row) > 5 and row[5] is not None else 0,
            })

        logger.info(
            "issue_id='%s': %d of %d results formatted",
            issue_id, len(formatted_data), len(data),
        )
        result_data[issue_id] = formatted_data

    # ==================== Resolve document IDs to PDF names (single batch) ====================
    all_doc_ids = [
        row["Document Name"]
        for chunks in result_data.values()
        for row in chunks
        if row.get("Document Name")
    ]
    if all_doc_ids:
        try:
            pdf_name_map = await resolve_pdf_names(db_client, all_doc_ids)
            if pdf_name_map:
                for chunks in result_data.values():
                    for row in chunks:
                        original_id = row.get("Document Name", "")
                        if original_id in pdf_name_map:
                            row["Document Name"] = pdf_name_map[original_id]
                logger.info("Resolved %d unique document IDs to PDF names", len(pdf_name_map))
        except Exception:
            logger.warning("PDF name resolution failed, keeping original IDs", exc_info=True)

    return json.dumps({"data": result_data})
