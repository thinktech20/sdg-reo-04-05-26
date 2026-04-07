"""Persona-based tool registry.

Filters the tool list returned by the MCP server based on the requesting user's persona (RE =
Reliability Engineer, OE = Outage Engineer).

Tool names are set server-side via ``mcp_names`` in data_service/mcp/server.py, so tools
arrive with their canonical prompt-facing names already applied.

Canonical tool names (source of truth — _CANONICAL_TOOL_NAMES in server.py):
    RE: query_fsr, query_er, read_ibat, read_prism,
        read_risk_matrix, read_re_table, read_re_report
    OE: query_fsr, query_er, read_ibat, read_event_master,
        read_risk_matrix, read_re_table, read_re_report,
        read_oe_event_report, read_oe_table
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Tool names allowed per persona — aligned with the system-prompt tool lists.
# Names here must match the canonical names set by the MCP server.
_PERSONA_TOOLS: dict[str, set[str]] = {
    "RE": {
        "read_ibat",
        "read_prism",
        "query_fsr",
        "query_er",
        "read_risk_matrix",
        "read_re_table",
        "read_re_report",
    },
    "OE": {
        "read_ibat",
        "query_fsr",
        "query_er",
        "read_risk_matrix",
        "read_re_table",
        "read_re_report",
        "read_oe_table",
        "read_event_master",
        "read_oe_event_report",
    },
}


def get_tool_name(tool: Any) -> str:
    """Resolve a stable tool name across MCP AgentTool wrappers and function tools."""
    name = getattr(tool, "tool_name", None)
    if isinstance(name, str) and name:
        return name

    tool_spec = getattr(tool, "tool_spec", None)
    if isinstance(tool_spec, dict):
        spec_name = tool_spec.get("name")
        if isinstance(spec_name, str) and spec_name:
            return spec_name

    name = getattr(tool, "name", None)
    if isinstance(name, str) and name:
        return name

    function_name = getattr(tool, "__name__", "")
    if isinstance(function_name, str):
        return function_name

    return ""


def filter_by_persona(tools: list[Any], persona: str) -> list[Any]:
    """Return only the tools permitted for the given persona.

    Args:
        tools: List of tool objects from MCPClient (have a .name attribute) or @tool decorated
            functions (have a __name__ attribute).
        persona: "RE" or "OE". Raises ValueError for unknown values.

    Returns:
        Filtered list of tool objects.

    Raises:
        ValueError: If persona is not a recognised value.
    """

    persona_upper = persona.upper()
    if persona_upper not in _PERSONA_TOOLS:
        raise ValueError(f"Unknown persona: {persona!r}. Must be one of {list(_PERSONA_TOOLS)}")
    allowed = _PERSONA_TOOLS[persona_upper]

    filtered = []
    for tool in tools:
        name = get_tool_name(tool)
        if name in allowed:
            filtered.append(tool)

    logger.info(
        "registry: persona=%s allowed=%d/%d tools",
        persona,
        len(filtered),
        len(tools),
    )
    return filtered





