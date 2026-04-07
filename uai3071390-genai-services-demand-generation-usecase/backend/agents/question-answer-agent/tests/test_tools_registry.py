"""Tests for persona-based tool filtering.

With server-side canonical naming (mcp_names), tools arrive with their
prompt-facing names already set.  These tests verify filtering by persona
using canonical names.
"""

from __future__ import annotations

import pytest

from question_answer.tools.registry import filter_by_persona, get_tool_name


class _PlainTool:
   def __init__(self, name: str) -> None:
      self.name = name


class _MCPToolStub:
   def __init__(self, name: str) -> None:
      self._agent_tool_name = name

   @property
   def tool_name(self) -> str:
      return self._agent_tool_name

   @property
   def tool_spec(self) -> dict[str, str]:
      return {"name": self._agent_tool_name}


def _make_tool(name: str) -> _PlainTool:
   return _PlainTool(name)


def _make_mcp_tool(name: str) -> _MCPToolStub:
   return _MCPToolStub(name)


# Tools using canonical names (as set by server-side mcp_names)
ALL_TOOLS = [
   _make_tool("read_ibat"),
   _make_tool("read_prism"),
   _make_tool("read_risk_matrix"),
   _make_tool("query_fsr"),
   _make_tool("read_event_master"),
]


# ── RE persona filtering ─────────────────────────────────────────────────────


def test_re_gets_enabled_tools() -> None:
   tools = filter_by_persona(ALL_TOOLS, "RE")
   names = {t.name for t in tools}
   assert "read_ibat" in names
   assert "read_prism" in names
   assert "read_risk_matrix" in names


def test_re_filters_out_non_enabled_tools() -> None:
   tools = filter_by_persona(ALL_TOOLS, "RE")
   names = {t.name for t in tools}
   assert "read_event_master" not in names


# ── OE persona filtering ─────────────────────────────────────────────────────


def test_oe_gets_same_enabled_tools() -> None:
   tools = filter_by_persona(ALL_TOOLS, "OE")
   names = {t.name for t in tools}
   assert "read_ibat" in names
   assert "read_risk_matrix" in names
   assert "query_fsr" in names
   assert "read_event_master" in names


def test_oe_filters_out_non_enabled_tools() -> None:
   tools = filter_by_persona(ALL_TOOLS, "OE")
   names = {t.name for t in tools}
   assert "read_re_table" not in names


def test_oe_does_not_include_prism() -> None:
   """OE prompt does not list read_prism."""
   tools = filter_by_persona([_make_tool("read_prism")], "OE")
   assert tools == []


def test_oe_includes_re_report_and_re_table() -> None:
   """OE persona can read RE outputs for cross-persona context."""
   tools = filter_by_persona(
      [_make_tool("read_re_table"), _make_tool("read_re_report")], "OE"
   )
   assert len(tools) == 2


# ── Error handling ────────────────────────────────────────────────────────────


def test_unknown_persona_raises() -> None:
   with pytest.raises(ValueError, match="Unknown persona"):
       filter_by_persona(ALL_TOOLS, "UNKNOWN")


def test_empty_tool_list() -> None:
   assert filter_by_persona([], "RE") == []


# ── get_tool_name ─────────────────────────────────────────────────────────────


def test_mcp_tool_name_is_resolved_from_tool_name_property() -> None:
   tool = _make_mcp_tool("read_ibat")
   assert get_tool_name(tool) == "read_ibat"


# ── Canonical names (server-side mcp_names) ───────────────────────────────────


def test_canonical_names_filtered_for_re() -> None:
   """All canonical RE tools pass through filtering."""
   tools = filter_by_persona([
      _make_mcp_tool("read_ibat"),
      _make_mcp_tool("read_prism"),
      _make_mcp_tool("read_risk_matrix"),
      _make_mcp_tool("query_fsr"),
      _make_mcp_tool("query_er"),
      _make_mcp_tool("read_re_table"),
      _make_mcp_tool("read_re_report"),
   ], "RE")
   assert {t.tool_name for t in tools} == {
      "read_ibat", "read_prism", "read_risk_matrix",
      "query_fsr", "query_er",
      "read_re_table", "read_re_report",
   }


def test_canonical_names_filtered_for_oe() -> None:
   """All canonical OE tools pass through filtering."""
   tools = filter_by_persona([
      _make_mcp_tool("read_ibat"),
      _make_mcp_tool("read_risk_matrix"),
      _make_mcp_tool("query_fsr"),
      _make_mcp_tool("query_er"),
      _make_mcp_tool("read_re_table"),
      _make_mcp_tool("read_re_report"),
      _make_mcp_tool("read_oe_table"),
      _make_mcp_tool("read_event_master"),
      _make_mcp_tool("read_oe_event_report"),
   ], "OE")
   assert {t.tool_name for t in tools} == {
      "read_ibat", "read_risk_matrix",
      "query_fsr", "query_er",
      "read_re_table", "read_re_report",
      "read_oe_table", "read_event_master", "read_oe_event_report",
   }


def test_unknown_tool_name_is_filtered_out() -> None:
   """Tools not in any persona allowlist get filtered."""
   tools = filter_by_persona([
      _make_mcp_tool("get_outage_history_api_equipment"),
   ], "OE")
   assert tools == []


def test_read_risk_analysis_filtered_out() -> None:
   """read_risk_analysis is not yet in persona allowlists (pending DS team confirmation)."""
   tools = filter_by_persona([_make_tool("read_risk_analysis")], "RE")
   assert tools == []
   tools = filter_by_persona([_make_tool("read_risk_analysis")], "OE")
   assert tools == []







