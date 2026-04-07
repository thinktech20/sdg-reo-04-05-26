#!/usr/bin/env python3
"""Standalone FSR query sample with Confluence-style metadata enrichment.

This script copies the tested retrieval pattern used by the active REChain FSR
runtime and adds the SQL joins described in the Query FSR tool spec.

Flow:
1. Query Databricks Vector Search for top-k FSR chunks filtered by generator_serial.
2. Pull the returned chunk rows from the chunk table.
3. Join only those returned chunks to:
   - vgpd.fsr_std_views.fsr_pdf_ref
   - vgpd.fsr_std_views.fsr_scraped_file_mapping_ref
   - vgpd.fsr_std_views.fsr_field_vision_field_services_report_psot
4. Return a grouped JSON payload with chunk, fsr_report, pdf_ref, and
   scraped_mapping objects.

The script is intentionally standalone and uses only requests plus environment
variables or local token files.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import requests


ROOT_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = ROOT_DIR.parent

DEFAULT_HOST = "https://gevernova-ai-dev-dbr.cloud.databricks.com"
DEFAULT_SQL_HTTP_PATH = "/sql/1.0/warehouses/c383216f6af5c7c0"
DEFAULT_VS_INDEX = "main.gp_services_sdg_poc.vs_field_service_report_gt_litellm"
DEFAULT_CHUNK_TABLE = "main.gp_services_sdg_poc.field_service_report_gt_litellm"
DEFAULT_PDF_REF_VIEW = "vgpd.fsr_std_views.fsr_pdf_ref"
DEFAULT_SCRAPED_MAPPING_VIEW = "vgpd.fsr_std_views.fsr_scraped_file_mapping_ref"
DEFAULT_FSR_REPORT_VIEW = "vgpd.fsr_std_views.fsr_field_vision_field_services_report_psot"
DEFAULT_EMBEDDING_MODEL = "azure-text-embedding-3-large-1"
DEFAULT_EMBEDDING_PATH = "/v1/embeddings"

PDF_REF_FILE_STEM_COLUMN = "s3_filename"
PDF_REF_DISPLAY_NAME_COLUMN = "PDF_name"
PDF_REF_ESN_COLUMN = "esn"
PDF_REF_EVENT_ID_COLUMN = "ev_equipment_event_id"

SCRAPED_MAPPING_FILE_COLUMN = "pdf_name"

FSR_REPORT_EVENT_ID_COLUMN = "event_id"
FSR_REPORT_ESN_COLUMN = "esn"
FSR_REPORT_STATUS_COLUMN = "report_unit_status"
FSR_REPORT_START_DATE_COLUMN = "start_date"
FSR_REPORT_END_DATE_COLUMN = "end_date"
FSR_REPORT_NAME_COLUMN = "report_name"

RETURN_COLUMNS = [
    "chunk_id",
    "pdf_name",
    "page_number",
    "chunk_text",
    "generator_serial",
]

EMBEDDING_EXCLUDE_COLUMNS = {"embedding", "chunk_embedding"}

REQUEST_SESSION = requests.Session()
REQUEST_SESSION.trust_env = False


def _load_dotenv_file(path: Path) -> None:
    if not path.exists():
        return
    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.lower().startswith("export "):
                line = line[7:].lstrip()
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, value)
    except OSError:
        return


for dotenv_path in (
    ROOT_DIR / ".env",
    WORKSPACE_DIR / ".env",
    WORKSPACE_DIR.parent / ".env",
):
    _load_dotenv_file(dotenv_path)


def _first_non_empty(*values: str) -> str:
    for value in values:
        if value and str(value).strip():
            return str(value).strip()
    return ""


def _normalize_host(value: str) -> str:
    host = value.strip()
    if host.startswith("https://"):
        host = host[8:]
    elif host.startswith("http://"):
        host = host[7:]
    return host.rstrip("/")


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def _read_secret_file(*paths: Path) -> str:
    for path in paths:
        try:
            if path.exists():
                value = path.read_text(encoding="utf-8").strip().strip("'\"")
                if value:
                    return value
        except OSError:
            continue
    return ""


def _require_setting(value: str, *, name: str, hints: Sequence[str]) -> str:
    cleaned = (value or "").strip()
    if cleaned:
        return cleaned
    raise RuntimeError(f"Missing {name}. Configure one of: {', '.join(hints)}")


def _derive_warehouse_id(sql_http_path: str) -> str:
    marker = "/warehouses/"
    if marker not in sql_http_path:
        return ""
    return sql_http_path.split(marker, 1)[1].strip("/")


def _sql_quote(value: Any) -> str:
    return str(value).replace("'", "''")


def _sql_string_list(values: Iterable[Any]) -> str:
    cleaned = [f"'{_sql_quote(value)}'" for value in values if value is not None and str(value) != ""]
    if not cleaned:
        return "(NULL)"
    return "(" + ", ".join(cleaned) + ")"


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _json_row(row: Dict[str, Any], *, exclude_columns: Sequence[str] = ()) -> Dict[str, Any]:
    excluded = {column.lower() for column in exclude_columns}
    return {
        key: _json_safe(value)
        for key, value in row.items()
        if key.lower() not in excluded
    }


def _normalize_pdf_key(value: Any) -> str:
    text = str(value or "").strip()
    text = text.replace("\\", "/")
    if "/" in text:
        text = text.rsplit("/", 1)[-1]
    if text.lower().endswith(".pdf"):
        text = text[:-4]
    return text


def _lookup_ci(row: Dict[str, Any], *keys: str) -> Any:
    lowered = {str(key).lower(): value for key, value in row.items()}
    for key in keys:
        if key.lower() in lowered:
            return lowered[key.lower()]
    return None


def _headers(token: str, *, json_content: bool = True) -> Dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if json_content:
        headers["Content-Type"] = "application/json"
    return headers


def _build_embedding_url(base_url: str, request_path: str) -> str:
    base = base_url.rstrip("/")
    path = request_path if request_path.startswith("/") else f"/{request_path}"
    if base.endswith("/v1") and path.startswith("/v1/"):
        path = path[3:]
    return base + path


def _candidate_embedding_urls(base_url: str, request_path: str) -> List[str]:
    urls = [_build_embedding_url(base_url, request_path)]
    for fallback_path in ("/v1/embeddings", "/embeddings"):
        candidate = _build_embedding_url(base_url, fallback_path)
        if candidate not in urls:
            urls.append(candidate)
    return urls


def _get_query_vector(query_text: str, *, base_url: str, api_key: str, model: str, request_path: str, verify_ssl: bool) -> List[float]:
    query = query_text.strip()
    if not query:
        raise ValueError("query text is empty")

    urls = _candidate_embedding_urls(base_url, request_path)
    payload = {"model": model, "input": [query]}
    failures: List[str] = []

    for url in urls:
        try:
            response = REQUEST_SESSION.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=120,
                verify=verify_ssl,
            )
            if response.status_code == 404:
                failures.append(f"{url} -> HTTP 404")
                continue
            response.raise_for_status()
            body = response.json()
            data = body.get("data") or []
            if len(data) != 1:
                raise RuntimeError(f"expected 1 embedding, received {len(data)}")
            embedding = data[0].get("embedding") or []
            if not embedding:
                raise RuntimeError("embedding response did not include values")
            return [float(value) for value in embedding]
        except Exception as exc:
            failures.append(f"{url} -> {exc}")

    raise RuntimeError(
        "LiteLLM embedding request failed for all candidate embedding endpoints: "
        + " | ".join(failures)
    )


def _api_json(method: str, url: str, *, token: str, json_body: Dict[str, Any] | None = None, timeout: int = 120, verify_ssl: bool) -> Dict[str, Any]:
    response = REQUEST_SESSION.request(
        method=method,
        url=url,
        headers=_headers(token),
        json=json_body,
        timeout=timeout,
        verify=verify_ssl,
    )
    response.raise_for_status()
    if not response.text.strip():
        return {}
    return response.json()


def _sql_statement(host: str, token: str, warehouse_id: str, statement: str, *, verify_ssl: bool, wait_timeout: str = "50s") -> Dict[str, Any]:
    body = _api_json(
        "POST",
        f"{host}/api/2.0/sql/statements",
        token=token,
        json_body={
            "warehouse_id": warehouse_id,
            "statement": statement,
            "wait_timeout": wait_timeout,
            "disposition": "INLINE",
        },
        timeout=120,
        verify_ssl=verify_ssl,
    )

    state = body.get("status", {}).get("state", "")
    statement_id = body.get("statement_id", "")
    while state in {"PENDING", "RUNNING"} and statement_id:
        time.sleep(5)
        body = _api_json(
            "GET",
            f"{host}/api/2.0/sql/statements/{statement_id}",
            token=token,
            timeout=120,
            verify_ssl=verify_ssl,
        )
        state = body.get("status", {}).get("state", "")

    if state != "SUCCEEDED":
        error = body.get("status", {}).get("error", {})
        message = error.get("message") or str(body.get("status", {}))
        raise RuntimeError(f"SQL failed: {message}\nStatement: {statement[:500]}")

    return body


def _sql_rows(host: str, token: str, warehouse_id: str, statement: str, *, verify_ssl: bool) -> List[Dict[str, Any]]:
    payload = _sql_statement(host, token, warehouse_id, statement, verify_ssl=verify_ssl)
    manifest = payload.get("manifest", {}) or {}
    schema = manifest.get("schema", {}) or {}
    columns = [column.get("name") for column in schema.get("columns", []) if column.get("name")]
    if not columns:
        columns = [column.get("name") for column in manifest.get("columns", []) if column.get("name")]
    if not columns:
        raise RuntimeError("SQL statement returned no schema metadata")

    rows = list(payload.get("result", {}).get("data_array", []) or [])
    next_chunk_link = payload.get("result", {}).get("next_chunk_internal_link")
    while next_chunk_link:
        chunk_payload = _api_json(
            "GET",
            f"{host}{next_chunk_link}" if next_chunk_link.startswith("/") else next_chunk_link,
            token=token,
            timeout=120,
            verify_ssl=verify_ssl,
        )
        result = chunk_payload.get("result", {}) or {}
        rows.extend(result.get("data_array", []) or chunk_payload.get("data_array", []) or [])
        next_chunk_link = result.get("next_chunk_internal_link") or chunk_payload.get("next_chunk_internal_link")

    return [dict(zip(columns, row)) for row in rows]


def _vector_search_query(host: str, token: str, index_name: str, *, serial_number: str, query_text: str, query_vector: List[float], k: int, query_type: str, verify_ssl: bool) -> List[Dict[str, Any]]:
    payload = {
        "query_text": query_text,
        "query_vector": query_vector,
        "columns": RETURN_COLUMNS,
        "num_results": k,
        "query_type": query_type.upper(),
        "filters_json": json.dumps({"generator_serial": serial_number}),
    }
    response = REQUEST_SESSION.post(
        f"{host}/api/2.0/vector-search/indexes/{index_name}/query",
        headers=_headers(token),
        json=payload,
        timeout=60,
        verify=verify_ssl,
    )
    response.raise_for_status()
    body = response.json()
    columns = [column.get("name") for column in body.get("manifest", {}).get("columns", [])]
    rows = body.get("result", {}).get("data_array", []) or []
    return [dict(zip(columns, row)) for row in rows]


def _choose_pdf_ref(chunk_row: Dict[str, Any], pdf_ref_rows: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    if not pdf_ref_rows:
        return None

    chunk_pdf_name = _normalize_pdf_key(_lookup_ci(chunk_row, "pdf_name") or "")
    chunk_serial = str(_lookup_ci(chunk_row, "generator_serial", "esn") or "").strip()
    exact_file_matches: List[Dict[str, Any]] = []
    exact_file_and_esn_matches: List[Dict[str, Any]] = []

    for row in pdf_ref_rows:
        row_pdf_name = _pdf_ref_file_key(row)
        if row_pdf_name != chunk_pdf_name:
            continue

        exact_file_matches.append(row)
        row_serial = str(_lookup_ci(row, "esn", "generator_serial") or "").strip()
        if chunk_serial and row_serial == chunk_serial:
            exact_file_and_esn_matches.append(row)

    if exact_file_and_esn_matches:
        return exact_file_and_esn_matches[0]
    if exact_file_matches:
        return exact_file_matches[0]
    return pdf_ref_rows[0]


def _pdf_ref_file_key(row: Dict[str, Any]) -> str:
    return _normalize_pdf_key(
        _lookup_ci(row, "s3_filename", "filename", "pdf_name", "PDF_name") or ""
    )


def _scraped_mapping_file_key(row: Dict[str, Any]) -> str:
    return _normalize_pdf_key(
        _lookup_ci(row, "filename", "pdf_name", "PDF_name", "s3_filename") or ""
    )


def _chunk_rows_by_id(host: str, token: str, warehouse_id: str, table_name: str, chunk_ids: Sequence[str], *, verify_ssl: bool) -> Dict[str, Dict[str, Any]]:
    if not chunk_ids:
        return {}
    statement = f"""
SELECT *
FROM {table_name}
WHERE chunk_id IN {_sql_string_list(chunk_ids)}
ORDER BY chunk_id
"""
    rows = _sql_rows(host, token, warehouse_id, statement, verify_ssl=verify_ssl)
    return {str(row.get("chunk_id")): row for row in rows}


def _total_chunks_for_esn(host: str, token: str, warehouse_id: str, table_name: str, serial_number: str, *, verify_ssl: bool) -> int:
    statement = f"""
SELECT COUNT(*) AS total_chunks_for_esn
FROM {table_name}
WHERE generator_serial = '{_sql_quote(serial_number)}'
"""
    rows = _sql_rows(host, token, warehouse_id, statement, verify_ssl=verify_ssl)
    if not rows:
        return 0
    return int(rows[0].get("total_chunks_for_esn") or 0)


def _pdf_ref_rows(host: str, token: str, warehouse_id: str, table_name: str, pdf_names: Sequence[str], *, verify_ssl: bool) -> Dict[str, List[Dict[str, Any]]]:
    if not pdf_names:
        return {}
    normalized_pdf_names = list(dict.fromkeys(_normalize_pdf_key(name) for name in pdf_names if name))
    pdf_name_variants: List[str] = []
    for name in normalized_pdf_names:
        pdf_name_variants.append(name)
        pdf_name_variants.append(f"{name}.pdf")
    statement = f"""
SELECT *
FROM {table_name}
WHERE {PDF_REF_FILE_STEM_COLUMN} IN {_sql_string_list(normalized_pdf_names)}
   OR {PDF_REF_DISPLAY_NAME_COLUMN} IN {_sql_string_list(pdf_name_variants)}
ORDER BY {PDF_REF_FILE_STEM_COLUMN}, {PDF_REF_DISPLAY_NAME_COLUMN}, {PDF_REF_ESN_COLUMN}, {PDF_REF_EVENT_ID_COLUMN}
"""
    rows = _sql_rows(host, token, warehouse_id, statement, verify_ssl=verify_ssl)
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        filename = _pdf_ref_file_key(row)
        grouped.setdefault(filename, []).append(row)
    return grouped


def _scraped_mapping_rows(host: str, token: str, warehouse_id: str, table_name: str, pdf_names: Sequence[str], *, verify_ssl: bool) -> Dict[str, List[Dict[str, Any]]]:
    if not pdf_names:
        return {}
    normalized_pdf_names = list(dict.fromkeys(_normalize_pdf_key(name) for name in pdf_names if name))
    like_clauses = [
        f"LOWER({SCRAPED_MAPPING_FILE_COLUMN}) LIKE '%/{_sql_quote(name.lower())}.pdf'"
        for name in normalized_pdf_names
    ]
    where_clause = " OR ".join(like_clauses) if like_clauses else "1 = 0"
    statement = f"""
SELECT *
FROM {table_name}
WHERE {where_clause}
ORDER BY {SCRAPED_MAPPING_FILE_COLUMN}
"""
    rows = _sql_rows(host, token, warehouse_id, statement, verify_ssl=verify_ssl)
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        filename = _scraped_mapping_file_key(row)
        grouped.setdefault(filename, []).append(row)
    return grouped


def _fsr_report_rows(host: str, token: str, warehouse_id: str, table_name: str, pdf_ref_rows: Sequence[Dict[str, Any]], *, verify_ssl: bool) -> Dict[Tuple[str, str], Dict[str, Any]]:
    pairs: List[Tuple[str, str]] = []
    for row in pdf_ref_rows:
        esn = str(_lookup_ci(row, "esn") or "").strip()
        event_id = str(_lookup_ci(row, "event_id", "ev_ofs_event_id") or "").strip()
        if esn and event_id:
            pairs.append((esn, event_id))
    if not pairs:
        return {}

    pair_clauses = [
        f"({FSR_REPORT_ESN_COLUMN} = '{_sql_quote(esn)}' AND {FSR_REPORT_EVENT_ID_COLUMN} = '{_sql_quote(event_id)}')"
        for esn, event_id in dict.fromkeys(pairs)
    ]
    where_clause = " OR ".join(pair_clauses)
    statement = f"""
WITH ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY {FSR_REPORT_ESN_COLUMN}, {FSR_REPORT_EVENT_ID_COLUMN}
            ORDER BY CASE UPPER(COALESCE({FSR_REPORT_STATUS_COLUMN}, ''))
                WHEN 'COMPLETED' THEN 1
                WHEN 'STARTED' THEN 2
                WHEN 'NOT STARTED' THEN 3
                WHEN 'HOLD' THEN 4
                ELSE 99
            END,
            COALESCE({FSR_REPORT_END_DATE_COLUMN}, {FSR_REPORT_START_DATE_COLUMN}) DESC,
            COALESCE({FSR_REPORT_NAME_COLUMN}, '') ASC
        ) AS row_num
    FROM {table_name}
    WHERE {where_clause}
)
SELECT * EXCEPT (row_num)
FROM ranked
WHERE row_num = 1
"""
    rows = _sql_rows(host, token, warehouse_id, statement, verify_ssl=verify_ssl)
    return {
        (str(_lookup_ci(row, FSR_REPORT_ESN_COLUMN) or ""), str(_lookup_ci(row, FSR_REPORT_EVENT_ID_COLUMN) or "")): row
        for row in rows
    }


def _build_results(vs_rows: Sequence[Dict[str, Any]], chunk_rows: Dict[str, Dict[str, Any]], pdf_ref_rows: Dict[str, List[Dict[str, Any]]], scraped_rows: Dict[str, List[Dict[str, Any]]], fsr_report_rows: Dict[Tuple[str, str], Dict[str, Any]]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []

    for index, vs_row in enumerate(vs_rows, start=1):
        chunk_id = str(vs_row.get("chunk_id") or "")
        pdf_name = _normalize_pdf_key(vs_row.get("pdf_name") or "")

        full_chunk_row = dict(chunk_rows.get(chunk_id) or {})
        if not full_chunk_row:
            full_chunk_row = {
                "chunk_id": chunk_id,
                "pdf_name": pdf_name,
                "page_number": vs_row.get("page_number"),
                "chunk_text": vs_row.get("chunk_text"),
                "generator_serial": vs_row.get("generator_serial"),
            }

        selected_pdf_ref = _choose_pdf_ref(full_chunk_row, pdf_ref_rows.get(pdf_name, []))
        selected_scraped = (scraped_rows.get(pdf_name) or [None])[0]
        selected_fsr_report = None
        if selected_pdf_ref is not None:
            report_key = (
                str(_lookup_ci(selected_pdf_ref, "esn") or ""),
                str(_lookup_ci(selected_pdf_ref, "event_id", "ev_ofs_event_id") or ""),
            )
            selected_fsr_report = fsr_report_rows.get(report_key)

        results.append(
            {
                "rank": index,
                "rerank_score": float(vs_row.get("score") or 0.0),
                "chunk": _json_row(full_chunk_row, exclude_columns=EMBEDDING_EXCLUDE_COLUMNS),
                "fsr_report": _json_row(selected_fsr_report or {}),
                "pdf_ref": _json_row(selected_pdf_ref or {}),
                "scraped_mapping": _json_row(selected_scraped or {}),
            }
        )

    return results


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Query FSR chunks and enrich them to the Confluence response shape."
    )
    parser.add_argument("--serial", required=True, help="Equipment serial number / generator_serial filter")
    parser.add_argument("--query", required=True, help="Natural language FSR query")
    parser.add_argument("--k", type=int, default=10, help="Number of chunks to return")
    parser.add_argument("--query-type", default="HYBRID", choices=("HYBRID", "ANN"), help="Databricks Vector Search query type")
    parser.add_argument("--host", default=_first_non_empty(os.getenv("DATABRICKS_HOST"), DEFAULT_HOST), help="Databricks workspace URL")
    parser.add_argument("--sql-http-path", default=os.getenv("DATABRICKS_SQL_HTTP_PATH", DEFAULT_SQL_HTTP_PATH), help="Databricks SQL warehouse HTTP path")
    parser.add_argument("--warehouse-id", default=os.getenv("DATABRICKS_SQL_WAREHOUSE_ID", ""), help="Databricks SQL warehouse id; derived from --sql-http-path when omitted")
    parser.add_argument("--vs-index", default=os.getenv("VS_INDEX_NAME", DEFAULT_VS_INDEX), help="Vector Search index name")
    parser.add_argument("--chunk-table", default=os.getenv("FSR_CHUNK_TABLE", DEFAULT_CHUNK_TABLE), help="Chunk table to query for full chunk rows")
    parser.add_argument("--pdf-ref-view", default=os.getenv("FSR_PDF_REF_VIEW", DEFAULT_PDF_REF_VIEW), help="PDF reference view")
    parser.add_argument("--scraped-mapping-view", default=os.getenv("FSR_SCRAPED_MAPPING_VIEW", DEFAULT_SCRAPED_MAPPING_VIEW), help="Scraped mapping view")
    parser.add_argument("--fsr-report-view", default=os.getenv("FSR_REPORT_VIEW", DEFAULT_FSR_REPORT_VIEW), help="FieldVision FSR report view")
    parser.add_argument("--embedding-base-url", default=os.getenv("LITELLM_BASE_URL", "https://dev-gateway.apps.gevernova.net"), help="LiteLLM base URL")
    parser.add_argument("--embedding-model", default=os.getenv("VECTOR_SEARCH_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL), help="LiteLLM embedding model")
    parser.add_argument("--embedding-request-path", default=os.getenv("VECTOR_SEARCH_EMBEDDING_REQUEST_PATH", DEFAULT_EMBEDDING_PATH), help="LiteLLM embedding request path")
    parser.add_argument("--token-file", default=str(ROOT_DIR / "dbr_token.txt"), help="Databricks PAT token file")
    parser.add_argument("--litellm-token-file", default=str(ROOT_DIR / "litellm_token.txt"), help="LiteLLM token file")
    parser.add_argument("--verify-ssl", action="store_true", help="Enable TLS verification for Databricks and LiteLLM requests")
    parser.add_argument("--output", default="", help="Optional output JSON path")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    started_at = time.time()

    host = _first_non_empty(args.host, DEFAULT_HOST).rstrip("/")
    warehouse_id = _first_non_empty(args.warehouse_id, _derive_warehouse_id(args.sql_http_path))
    databricks_token = _require_setting(
        _first_non_empty(
            os.getenv("DATABRICKS_TOKEN"),
            os.getenv("DB_TOKEN"),
            _read_secret_file(Path(args.token_file), WORKSPACE_DIR / "dbr_token.txt"),
        ),
        name="Databricks token",
        hints=["DATABRICKS_TOKEN", "DB_TOKEN", args.token_file, str(WORKSPACE_DIR / "dbr_token.txt")],
    )
    litellm_token = _require_setting(
        _first_non_empty(
            os.getenv("LITELLM_API_KEY"),
            _read_secret_file(Path(args.litellm_token_file), WORKSPACE_DIR / "litellm_token.txt"),
        ),
        name="LiteLLM API key",
        hints=["LITELLM_API_KEY", args.litellm_token_file, str(WORKSPACE_DIR / "litellm_token.txt")],
    )
    _require_setting(
        warehouse_id,
        name="Databricks SQL warehouse id",
        hints=["--warehouse-id", "DATABRICKS_SQL_WAREHOUSE_ID", "--sql-http-path", "DATABRICKS_SQL_HTTP_PATH"],
    )

    verify_ssl = args.verify_ssl or _parse_bool(os.getenv("FSR_QUERY_SAMPLE_VERIFY_SSL"), False)
    query_vector = _get_query_vector(
        args.query,
        base_url=args.embedding_base_url,
        api_key=litellm_token,
        model=args.embedding_model,
        request_path=args.embedding_request_path,
        verify_ssl=verify_ssl,
    )

    vs_rows = _vector_search_query(
        host=host,
        token=databricks_token,
        index_name=args.vs_index,
        serial_number=args.serial,
        query_text=args.query,
        query_vector=query_vector,
        k=args.k,
        query_type=args.query_type,
        verify_ssl=verify_ssl,
    )

    if not vs_rows:
        total_chunks_for_esn = _total_chunks_for_esn(
            host,
            databricks_token,
            warehouse_id,
            args.chunk_table,
            args.serial,
            verify_ssl=verify_ssl,
        )
        payload = {
            "results": [],
            "metadata": {
                "equipment_serial_number": args.serial,
                "query": args.query,
                "k": args.k,
                "query_type": args.query_type,
                "vs_index": args.vs_index,
                "chunk_table": args.chunk_table,
                "total_chunks_for_esn": total_chunks_for_esn,
                "result_count": 0,
                "duration_ms": int((time.time() - started_at) * 1000),
            },
        }
        output = json.dumps(payload, indent=2)
        if args.output:
            output_path = Path(args.output).expanduser().resolve()
            output_path.write_text(output, encoding="utf-8")
            print(f"Wrote output to {output_path}")
        else:
            print(output)
        return 0

    chunk_ids = [str(row.get("chunk_id") or "") for row in vs_rows if row.get("chunk_id")]
    pdf_names = list(dict.fromkeys(str(row.get("pdf_name") or "") for row in vs_rows if row.get("pdf_name")))

    with ThreadPoolExecutor(max_workers=4) as executor:
        chunk_rows_future = executor.submit(
            _chunk_rows_by_id,
            host,
            databricks_token,
            warehouse_id,
            args.chunk_table,
            chunk_ids,
            verify_ssl=verify_ssl,
        )
        pdf_ref_future = executor.submit(
            _pdf_ref_rows,
            host,
            databricks_token,
            warehouse_id,
            args.pdf_ref_view,
            pdf_names,
            verify_ssl=verify_ssl,
        )
        scraped_future = executor.submit(
            _scraped_mapping_rows,
            host,
            databricks_token,
            warehouse_id,
            args.scraped_mapping_view,
            pdf_names,
            verify_ssl=verify_ssl,
        )
        total_chunks_future = executor.submit(
            _total_chunks_for_esn,
            host,
            databricks_token,
            warehouse_id,
            args.chunk_table,
            args.serial,
            verify_ssl=verify_ssl,
        )

        chunk_rows = chunk_rows_future.result()
        pdf_ref_by_filename = pdf_ref_future.result()
        scraped_by_filename = scraped_future.result()
        total_chunks_for_esn = total_chunks_future.result()

    all_pdf_ref_rows = [row for rows in pdf_ref_by_filename.values() for row in rows]
    fsr_report_by_pair = _fsr_report_rows(
        host,
        databricks_token,
        warehouse_id,
        args.fsr_report_view,
        all_pdf_ref_rows,
        verify_ssl=verify_ssl,
    )

    results = _build_results(
        vs_rows,
        chunk_rows,
        pdf_ref_by_filename,
        scraped_by_filename,
        fsr_report_by_pair,
    )
    payload = {
        "results": results,
        "metadata": {
            "equipment_serial_number": args.serial,
            "query": args.query,
            "k": args.k,
            "query_type": args.query_type,
            "vs_index": args.vs_index,
            "chunk_table": args.chunk_table,
            "total_chunks_for_esn": total_chunks_for_esn,
            "result_count": len(results),
            "duration_ms": int((time.time() - started_at) * 1000),
        },
    }

    output = json.dumps(payload, indent=2)
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.write_text(output, encoding="utf-8")
        print(f"Wrote output to {output_path}")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())