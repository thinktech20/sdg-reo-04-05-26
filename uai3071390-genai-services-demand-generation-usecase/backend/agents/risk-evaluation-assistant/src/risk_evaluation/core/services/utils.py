"""Compatibility utility module for risk-evaluation service tests.

This module preserves the historical import path:
    risk_evaluation.core.services.utils

Canonical implementations originally moved under core.utils.utils. The wrappers
below keep behavior compatible for existing tests and callers.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from risk_evaluation import config
from risk_evaluation.core.config.logger_config import get_logger
from risk_evaluation.core.utils.utils import call_rest_api

logger = get_logger(__name__)

MCP_HTTP_TIMEOUT = httpx.Timeout(300.0, connect=30.0)


async def run_http_with_tool(tool_name: str, tool_args: dict[str, Any]) -> Any:
    """Execute an MCP tool call via HTTP transport."""
    server_params = config.MCP_SERVER_PARAMS

    async with httpx.AsyncClient(timeout=MCP_HTTP_TIMEOUT, follow_redirects=True, trust_env=False) as http_client:
        try:
            async with streamable_http_client(server_params, http_client=http_client) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, tool_args)
                    logger.debug("TOOL CALL RESULT: %s", result)

                    extracted_result: Any = None
                    if result.content and isinstance(result.content, list) and len(result.content) > 0:
                        first_content = result.content[0]
                        if hasattr(first_content, "type"):
                            if first_content.type == "text":
                                extracted_result = first_content.text
                                try:
                                    extracted_result = json.loads(extracted_result)
                                except (json.JSONDecodeError, TypeError):
                                    pass
                            else:
                                extracted_result = first_content
                        else:
                            extracted_result = first_content
                    return extracted_result
        except ConnectionError as exc:
            logger.error("Connection error while calling MCP tool '%s': %s", tool_name, exc)
            raise ConnectionError(f"Failed to connect to MCP server: {exc}") from exc
        except TimeoutError as exc:
            logger.error("Timeout error while calling MCP tool '%s': %s", tool_name, exc)
            raise TimeoutError(f"MCP tool call timed out: {exc}") from exc


def _repair_json_string(json_str: str) -> str:
    """Attempt to repair common JSON formatting issues."""
    import re

    json_str = json_str.strip()

    if json_str.startswith("```"):
        first_newline = json_str.find("\n")
        if first_newline != -1:
            json_str = json_str[first_newline + 1 :]
        if json_str.endswith("```"):
            json_str = json_str[:-3].rstrip()

    if "{" in json_str and "}" in json_str:
        start_idx = json_str.find("{")
        end_idx = json_str.rfind("}") + 1
        json_str = json_str[start_idx:end_idx]

    json_str = re.sub(r'"Sl No\.\s*(\d+)"', r'"Sl No.": \1', json_str)
    json_str = re.sub(r'"Sl No\.":\s*(\d+):\s*\d+', r'"Sl No.": \1', json_str)

    return json_str


def format_assistant_response(analyze_result: Any) -> tuple[bool, Any]:
    """Parse and validate JSON-like assistant output."""
    if isinstance(analyze_result, dict):
        if "data" in analyze_result and isinstance(analyze_result["data"], list):
            _ = [item for item in analyze_result["data"] if isinstance(item, dict)]
        return True, analyze_result

    if isinstance(analyze_result, str):
        try:
            repaired = _repair_json_string(analyze_result)
            try:
                return True, json.loads(repaired)
            except json.JSONDecodeError:
                return True, json.loads(repaired, strict=False)
        except Exception:
            return False, None

    return False, None


__all__ = [
    "run_http_with_tool",
    "call_rest_api",
    "_repair_json_string",
    "format_assistant_response",
]
