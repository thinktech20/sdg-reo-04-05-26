"""ER (Engineering Review) cases service.

Retrieves ER cases from Databricks Gold Layer (vgpp.qlt_std_views.u_pac).
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Any

import requests

from commons.logging import get_logger
from data_service.databricks_client import DatabricksClient
from data_service.logging_utils import log_query_event

logger = get_logger(__name__)

ER_CATALOG = os.getenv("ER_CATALOG", "vgpp")
ER_SCHEMA = os.getenv("ER_SCHEMA", "qlt_std_views")
ER_TABLE = os.getenv("ER_TABLE", "u_pac")
ER_VIEW = os.getenv("ER_VIEW", f"{ER_CATALOG}.{ER_SCHEMA}.{ER_TABLE}")


async def get_er_cases(
    esn: str,
    component: str | None = None,
    user: str | None = None,
    db_client: DatabricksClient | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Retrieve ER cases for a given serial number."""
    client = db_client or DatabricksClient()
    started = time.perf_counter()
    error: str | None = None
    result_ids: list[str] = []
    query_markers: dict[str, str] = {
        "naksha_status": "unknown",
        "table_status": "unknown",
    }
    params: dict[str, Any] = {"esn": esn}
    component_filter = ""
    if component:
        component_filter = """
            AND (
                LOWER(u_component) LIKE :comp
                OR LOWER(u_sub_component) LIKE :comp
            )
        """
        params["comp"] = f"%{component.lower()}%"
    query = f"""
        SELECT 
            number as case_id,
            u_serial_number as serial_number,
            short_description,
            description_ as full_description,
            close_notes,
            u_resolve_notes as resolution_notes,
            u_field_action_taken as field_action,
            u_status as status,
            priority,
            u_component as component,
            u_sub_component as sub_component,
            equipment_code,
            opened_at as date_opened,
            closed_at as date_closed,
            u_type as issue_type,
            work_notes
        FROM {ER_VIEW}
        WHERE u_serial_number = :esn
        {component_filter}
        ORDER BY opened_at DESC
        LIMIT 50
    """
    try:
        rows = await client.query_async(query, params)
        query_markers = client.get_last_query_markers()

        result_ids = [str(row.get("case_id", "")) for row in rows]
        return {
            "serial_number": esn,
            "result_count": len(rows),
            "records": rows,
            "metadata": {
                "naksha_status": query_markers.get("naksha_status", "unknown"),
                "table_status": query_markers.get("table_status", "unknown"),
            },
        }
    except Exception as exc:
        error = str(exc)
        raise
    finally:
        duration_ms = int((time.perf_counter() - started) * 1000)
        log_query_event(
            logger_name="data-svc",
            event="er_query",
            payload={
                "user": user or "unknown",
                "serial_number": esn,
                "component": component,
                "result_count": len(result_ids),
                "result_ids": result_ids,
                "errors": error,
                "duration_ms": duration_ms,
            },
        )

def _format_date(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            return value
    return str(value)


def _normalize_case(row: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "#": index,
        "er_number": str(row.get("er_number") or row.get("case_id") or ""),
        "serial_number": str(row.get("serial_number") or ""),
        "short_description": str(row.get("short_description") or ""),
        "description": str(row.get("description") or row.get("full_description") or ""),
        "close_notes": str(row.get("close_notes") or row.get("resolution_notes") or ""),
        "u_component": str(row.get("u_component") or row.get("component") or ""),
        "u_sub_component": str(row.get("u_sub_component") or row.get("sub_component") or ""),
        "opened_at": _format_date(row.get("opened_at") or row.get("date_opened")),
        "closed_at": _format_date(row.get("closed_at") or row.get("date_closed")),
    }


async def _get_risk_assessment_er_cases_legacy(esn: str | None, max_cases: int = 50) -> str:
    sanitized_esn = (esn.strip() if isinstance(esn, str) else "")
    if not sanitized_esn:
        return json.dumps({"error": "ESN is required for ER case retrieval", "data": []})

    if not (1 <= max_cases <= 100):
        return json.dumps({"error": "max_cases must be between 1 and 100", "data": []})

    try:
        client = DatabricksClient()
        query = f"""
            SELECT
                number as case_id,
                u_serial_number as serial_number,
                short_description,
                description_ as full_description,
                close_notes,
                u_resolve_notes as resolution_notes,
                u_component,
                u_sub_component,
                opened_at,
                closed_at
            FROM {ER_VIEW}
            WHERE u_serial_number = :esn
            ORDER BY opened_at DESC
            LIMIT :limit
        """
        rows = await client.query_async(query, {"esn": sanitized_esn, "limit": max_cases})
    except Exception as exc:
        message = str(exc)
        if "connection" in message.lower() or "fetch" in message.lower() or "database" in message.lower():
            return json.dumps({"error": f"Failed to fetch ER cases: {message}", "data": []})
        return json.dumps({"error": f"ER retrieval failed: {message}", "data": []})

    normalized = [_normalize_case(row, idx + 1) for idx, row in enumerate(rows[:max_cases])]
    return json.dumps({"data": normalized})


async def get_risk_assessment_er_cases(
    issue_prompts: list[dict[str, str]] | None = None,
    esn: str | None = None,
    k: int = 10,
    query_type: str = "HYBRID",
    max_cases: int | None = None,
) -> str:
    if issue_prompts is None:
        return await _get_risk_assessment_er_cases_legacy(esn=esn, max_cases=max_cases if max_cases is not None else 50)

    return await _get_risk_assessment_er_cases_vector(issue_prompts=issue_prompts, esn=esn, k=k, query_type=query_type)


async def _get_risk_assessment_er_cases_vector(
    issue_prompts: list[dict[str, str]],
    esn: str | None = None,
    k: int = 10,
    query_type: str = "HYBRID",
) -> str:
    """
    Retrieve Engineering Review (ER) cases via vector search from Databricks
    for a list of issue prompts.

    Each item in issue_prompts must be a dict with:
        - "issue_id":     A UUID string identifying the issue
        - "issue_prompt": Natural language query describing the issue

    The method processes each issue prompt serially and returns all results
    grouped by issue_id.

    Use this tool for:
    - Engineering review case lookups
    - Equipment issue history
    - Case resolution details and close notes
    - Component failure investigations

    Args:
        issue_prompts: List of dicts, each with "issue_id" (UUID) and "issue_prompt" (query text)
        esn: Equipment Serial Number to search for (e.g., "290T658")
        k: Number of results to return per issue. Default: 10
        query_type: Vector search query type. Default: "HYBRID"

    Returns:
        JSON string with:
        {
            "data": {
                "<issue_id>": [
                    {"chunk_id", "er_case_number", "chunk_text", "serial_number",
                     "opened_at", "status", "u_component", "u_field_action_taken", "equipment_id"},
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
        return json.dumps({"error": "ESN is required for ER case retrieval", "data": {}})

    if not (1 <= k <= 50):
        return json.dumps({"error": "k must be between 1 and 50", "data": {}})

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
        "index": os.getenv("ER_VECTOR_SEARCH_INDEX", "main.gp_services_sdg_poc.vs_engineering_report_chunk_litellm"),
    }
    missing = [k_name for k_name, v in cfg.items() if not v]
    if missing:
        error_msg = f"Missing required Databricks config env vars: {', '.join(missing)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg, "data": {}})

    logger.info("Databricks config loaded for ER index '%s'", cfg["index"])

    db_client = DatabricksClient()

    er_columns = [
        "chunk_id",
        "er_case_number",
        "chunk_text",
        "serial_number",
        "opened_at",
        "status",
        "u_component",
        "u_field_action_taken",
        "equipment_id",
    ]

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
            "ER vector search: issue_id='%s', query='%s', esn=%s, k=%d",
            issue_id, sanitized_query[:50], sanitized_esn, k,
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

        # ========== STEP 2: Vector search for ER chunks ==========
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
                    "filters_json": json.dumps({"serial_number": sanitized_esn}),
                    "num_results": k,
                    "query_type": query_type,
                    "columns": er_columns,
                },
                timeout=300,
                verify=False,
            )
            response.raise_for_status()
            search_results = response.json()
        except requests.exceptions.Timeout:
            logger.error("ER vector search timed out for issue_id='%s'", issue_id)
            result_data[issue_id] = []
            continue
        except requests.exceptions.HTTPError as e:
            logger.error(
                "ER vector search HTTP error for issue_id='%s': %d: %s",
                issue_id, e.response.status_code, e.response.text[:200], exc_info=True,
            )
            result_data[issue_id] = []
            continue
        except (requests.exceptions.RequestException, Exception) as e:
            logger.error(
                "ER vector search request failed for issue_id='%s': %s: %s",
                issue_id, type(e).__name__, e, exc_info=True,
            )
            result_data[issue_id] = []
            continue

        # ========== STEP 3: Format results ==========
        data = search_results.get("result", {}).get("data_array", [])
        logger.info("ER vector search returned %d results for issue_id='%s'", len(data), issue_id)

        er_results = []
        for row in data:
            er_results.append({
                "chunk_id": row[0] if len(row) > 0 else "",
                "er_case_number": row[1] if len(row) > 1 else "",
                "chunk_text": row[2] if len(row) > 2 else "",
                "serial_number": row[3] if len(row) > 3 else "",
                "opened_at": row[4] if len(row) > 4 else "",
                "status": row[5] if len(row) > 5 else "",
                "u_component": row[6] if len(row) > 6 else "",
                "u_field_action_taken": row[7] if len(row) > 7 else "",
                "equipment_id": row[8] if len(row) > 8 else "",
            })

        result_data[issue_id] = er_results

    return json.dumps({"data": result_data})
