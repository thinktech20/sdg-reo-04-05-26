"""MCP server — exposes data-service tools over MCP/SSE.

Mounted in main.py:
    from data_service.mcp.server import mcp
    app.mount("/mcp", mcp.sse_app())

Tools:
    read_ibat        — calls read_ibat_by_serial service directly
    read_prism       — calls read_prism_by_serial service directly
    load_risk_matrix — calls read_heatmap service directly
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import httpx
from fastmcp import FastMCP
from fastmcp.server.openapi import MCPType, RouteMap

from commons.logging import get_logger
from data_service.services.heatmap_service import HeatmapServiceError
from data_service.services.heatmap_service import read_heatmap as _read_heatmap
from data_service.services.ibat_service import IbatServiceError, read_ibat_by_serial
from data_service.services.prism_service import PrismServiceError, read_prism_by_serial

# Initialize logger
logger = get_logger(__name__)

# Base URL of the running FastAPI data-service
DATA_SERVICE_URL = os.getenv("DATA_SERVICE_URL", "http://localhost:8086")

# Canonical prompt-facing names for persona-relevant MCP tools.
# Keys are Python function name prefixes (stable identifiers we control).
# Values are the names the LLM sees in system prompts.
_CANONICAL_TOOL_NAMES: dict[str, str] = {
    "get_ibat_equipment_endpoint": "read_ibat",
    "read_prism":                  "read_prism",
    "load_heatmap":                "read_risk_matrix",
    "get_risk_er_cases_endpoint":  "query_er",
    "retrieve_endpoint":           "query_fsr",
    "get_findings":                "read_re_table",
    "get_assessment_by_id":        "read_re_report",
    "get_risk_analysis":           "read_risk_analysis",
}


def _build_mcp_names(openapi_spec: dict[str, Any]) -> dict[str, str]:
    """Map auto-generated operationIds to canonical prompt-facing names.

    Matches by function-name prefix so that path changes, double prefixes,
    and slug suffixes don't affect the mapping.
    """
    mcp_names: dict[str, str] = {}
    for path_methods in openapi_spec.get("paths", {}).values():
        for method_detail in path_methods.values():
            if not isinstance(method_detail, dict):
                continue
            op_id = method_detail.get("operationId")
            if not op_id:
                continue
            for prefix, canonical in _CANONICAL_TOOL_NAMES.items():
                if op_id.startswith(prefix):
                    mcp_names[op_id] = canonical
                    break
    return mcp_names


def _build_route_maps() -> list[RouteMap]:
    """Define how OpenAPI routes map to MCP component types.

    - Data-fetching GET endpoints → MCP tools
    - Mutation POST endpoints    → MCP tools
    - Health-check endpoints     → excluded
    - The old /mcp JSON-RPC shim → excluded
    """
    return [
        # Exclude health-check endpoints -- not useful as MCP tools
        RouteMap(methods=["GET"], pattern=r".*/health$", mcp_type=MCPType.EXCLUDE),
        # All remaining GET endpoints → MCP tools (data retrieval)
        RouteMap(methods=["GET"], pattern=r"/api/v1/.*", mcp_type=MCPType.TOOL),
        # POST endpoints for retriever and ER → MCP tools
        RouteMap(methods=["POST"], pattern=r".*/retrieve$", mcp_type=MCPType.TOOL),
        RouteMap(methods=["POST"], pattern=r".*/risk-er-cases$", mcp_type=MCPType.TOOL),
        # Assessment POST endpoints → MCP tools
        RouteMap(methods=["POST"], pattern=r".*/assessment.*", mcp_type=MCPType.TOOL),
    ]

def create_mcp_server(openapi_spec: dict[str, Any]) -> FastMCP:
    """Create a FastMCP server from the given OpenAPI spec."""
    # Increased timeout to 300s for slow Databricks queries
    client = httpx.AsyncClient(base_url=DATA_SERVICE_URL, timeout=600.0)

    mcp = FastMCP.from_openapi(
        openapi_spec=openapi_spec,
        client=client,
        route_maps=_build_route_maps(),
        mcp_names=_build_mcp_names(openapi_spec),
        name="data-tool-mcp",
    )
    return mcp


def _fetch_openapi_spec() -> dict[str, Any]:
    """Fetch OpenAPI spec from the running FastAPI service."""
    url = f"{DATA_SERVICE_URL}/openapi.json"
    resp = httpx.get(url, timeout=30.0)
    resp.raise_for_status()
    result: dict[str, Any] = resp.json()
    return result


def _generate_openapi_spec_offline() -> dict[str, Any]:
    """Generate the OpenAPI spec directly from the FastAPI app object
    (no running server required). Useful for stdio transport."""
    # Adjust path so app module resolves
    src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    from data_service.main import app
    result: dict[str, Any] = app.openapi()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="MCP server for data-service")
    parser.add_argument(
        "--transport",
        choices=["streamable-http", "sse", "stdio"],
        default="streamable-http",
        help="MCP transport type (default: streamable-http)",
    )
    parser.add_argument("--port", type=int, default=8002, help="Port for HTTP/SSE transport")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    parser.add_argument(
        "--spec-file",
        default=None,
        help="Path to a local openapi.json file instead of fetching from the running service",
    )
    args = parser.parse_args()

    # --- Obtain the OpenAPI spec ---
    if args.spec_file:
        with open(args.spec_file, encoding="utf-8") as f:
            spec = json.load(f)
        print(f"[MCP] Loaded OpenAPI spec from file: {args.spec_file}")
    elif args.transport == "stdio":
        # For stdio we may not have a running server, generate offline
        try:
            spec = _fetch_openapi_spec()
            logger.info(f"[MCP] Fetched OpenAPI spec from {DATA_SERVICE_URL}")
        except (httpx.ConnectError, httpx.HTTPStatusError):
            logger.error("[MCP] FastAPI not running, generating spec offline...")
            spec = _generate_openapi_spec_offline()
    else:
        spec = _fetch_openapi_spec()
        logger.info(f"[MCP] Fetched OpenAPI spec from {DATA_SERVICE_URL}")

    mcp = create_mcp_server(spec)

    logger.info(f"[MCP] Starting MCP server  transport={args.transport}")

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    elif args.transport == "sse":
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        mcp.run(transport="streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
