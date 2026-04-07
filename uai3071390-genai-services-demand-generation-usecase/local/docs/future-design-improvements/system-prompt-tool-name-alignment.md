# System Prompt — Tool Name Alignment

## Status: Deferred

## Context

With server-side `mcp_names` stabilizing canonical tool names, the system prompts
(`re_system_prompt.txt`, `oe_system_prompt.txt`) should be reviewed to make sure
the tool names mentioned in prose match the canonical names emitted by `_CANONICAL_TOOL_NAMES`.

## Items to check

- `read_risk_analysis` is defined server-side in `_CANONICAL_TOOL_NAMES` but not yet
  in `_PERSONA_TOOLS` or system prompts. Pending DS team confirmation.
- Verify all tool names in RE/OE system prompts match `_CANONICAL_TOOL_NAMES` values exactly.
- Confirm Confluence tool tables match (see Recommended Confluence Wording in `mcp-tool-metadata.md`).

## Files

- `backend/agents/question-answer-agent/src/question_answer/prompts/re_system_prompt.txt`
- `backend/agents/question-answer-agent/src/question_answer/prompts/oe_system_prompt.txt`
- `backend/agents/question-answer-agent/src/question_answer/tools/registry.py` (`_PERSONA_TOOLS`)
- `backend/services/data-service/src/data_service/mcp/server.py` (`_CANONICAL_TOOL_NAMES`)
