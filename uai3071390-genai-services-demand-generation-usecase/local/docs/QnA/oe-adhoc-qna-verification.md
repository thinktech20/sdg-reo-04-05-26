# OE Adhoc QnA Agent — Verification & Testing

**Branch:** `feature/verify-oe-adhoc-qna` (from Develop)  
**Started:** April 6, 2026

---

## Architecture (end-to-end)

```
Frontend OutageChatPanel
  → POST /api/assessments/{id}/chat/outage
    → QnA Agent (persona="OE", label="outage-agent")
      → MCP Client (filtered tools per persona)
        → Data Service REST endpoints
```

OE focuses on **Other Repairs** (bearings, hydrogen/scavenging systems, collector rings, seals, etc.)  
RE focuses on **Rotor & Stator** — separate persona, separate prompt, separate tool set.

---

## Key Files

| Area | File | Notes |
|------|------|-------|
| Chat endpoint | `backend/agents/question-answer-agent/src/question_answer/api/v1/endpoints.py` | `chat_outage()` handler, hardcoded persona="OE" |
| Tool registry | `backend/agents/question-answer-agent/src/question_answer/tools/registry.py` | `_PERSONA_TOOLS["OE"]`, `_TOOL_NAME_ALIASES` |
| Agent factory | `backend/agents/question-answer-agent/src/question_answer/core/agent_factory.py` | `run_agent()` — MCP connect, filter, build, invoke |
| OE prompt | `backend/agents/question-answer-agent/src/question_answer/prompts/oe_system_prompt.txt` | ~400 lines, Other Repairs scope |
| Schemas | `backend/agents/question-answer-agent/src/question_answer/schemas.py` | `AssessmentChatRequest`, `AssessmentChatResponse` |
| Frontend chat | `frontend/src/components/outage/OutageChatPanel.tsx` | Gated on OE_DEFAULT workflow completion |
| Chat state | `frontend/src/store/slices/chatSlice.ts` | `outageChats[assessmentId]` |
| MCP server | `backend/services/data-service/src/data_service/mcp/server.py` | Auto-generates tool names from OpenAPI routes |
| Data routes | `backend/services/data-service/src/data_service/routes/` | assessments.py, equipment.py, etc. |

---

## OE Tool Set

Tools allowed for OE persona (from `_PERSONA_TOOLS["OE"]`):

| Prompt-Friendly Name | Purpose | Alias Mapping Status |
|----------------------|---------|---------------------|
| `read_ibat` | IBAT equipment metadata | mapped |
| `query_fsr` | Search Field Service Reports | mapped |
| `query_er` | Search Engineering Request cases | mapped |
| `read_risk_matrix` | Risk severity criteria (OE-filtered) | mapped |
| `read_re_table` | RE Risk Assessment Table (read-only context) | mapped |
| `read_re_report` | RE Narrative Summary (read-only context) | mapped |
| `read_oe_table` | OE Risk Assessment Table | **MISSING alias** |
| `read_event_master` | Event Master outage history | **MISSING alias** |
| `read_oe_event_report` | OE Event History & Key Findings | **MISSING alias** |

OE-excluded: `read_prism` (RE-only, Rotor/Stator predictive risk)

---

## Merged: feature/mcp-canonical-tool-names

Merged the in-flight PR branch (`feature/mcp-canonical-tool-names`) into our working branch.  
This branch moved tool naming to the **server side** — MCP tools now arrive with canonical names  
via `mcp_names` param in `FastMCP.from_openapi()`. Client-side alias mapping is removed.

Key changes from that branch:
- `data_service/mcp/server.py` — added `_CANONICAL_TOOL_NAMES` dict + `_build_mcp_names()` 
- `question_answer/tools/registry.py` — removed `_TOOL_NAME_ALIASES`, `rename_tools()`, `_resolve_alias()` 
- `question_answer/core/agent_factory.py` — removed `rename_tools()` call
- New test: `test_mcp_server_coverage.py`

---

## Known Issues

### 1. Three OE-specific tools missing from `_CANONICAL_TOOL_NAMES` (server.py)
`read_oe_table`, `read_event_master`, `read_oe_event_report` are in `_PERSONA_TOOLS["OE"]` (registry.py)  
but **missing from `_CANONICAL_TOOL_NAMES`** (server.py). Tools without canonical names keep their  
auto-generated operationId names, so `filter_by_persona("OE")` won't match them.

**Fix:** Add entries to `_CANONICAL_TOOL_NAMES` mapping the operationId prefixes → canonical names.

### 2. Need to identify OE-specific operationIds
Must find the FastAPI route function names for:
- `read_oe_table` → likely the same `get_findings` endpoint (persona-aware) or a separate OE route
- `read_event_master` → likely `outage_history` in equipment.py
- `read_oe_event_report` → may be embedded in `get_assessment_by_id` response, or a separate route

### 3. MCP route pattern coverage
MCP `_build_route_maps()` uses pattern `/api/v1/.*` but actual routes are mounted at `/dataservices/api/v1/…`.  
Need to verify the outage-history endpoint is captured by the route patterns.

### 4. Shared endpoints serving both personas
Same `/assessments/{id}/findings` endpoint serves both RE and OE data. Currently only maps to `read_re_table`.  
OE may need a separate mapping or the same tool name may work if the data is persona-filtered server-side.

---

## Implementation Plan

### Phase 1: MCP tool discovery
- Start data-service locally
- List MCP tools and capture actual operationIds
- Identify which operationId prefixes correspond to OE tools
- Check route pattern matching for OE endpoints

### Phase 2: Add OE canonical tool names
- Add missing entries to `_CANONICAL_TOOL_NAMES` in `data_service/mcp/server.py`
- Update `test_mcp_server_coverage.py` to cover OE tools
- Verify `filter_by_persona("OE")` returns correct count (9 tools)
- Run existing unit tests

### Phase 3: API-level testing
- Start data-service + QnA agent locally
- POST to `/api/assessments/{id}/chat/outage` with OE questions
- Verify agent uses OE tools (read_oe_table, read_event_master, etc.)
- Check response quality and source citations

### Phase 4: UI testing
- Run frontend
- Verify OutageChatPanel renders and locks until OE_DEFAULT completes
- Send messages and verify response display
- Test quick actions

---

## Progress Log

### April 6, 2026 — Initial review
- Created branch `feature/verify-oe-adhoc-qna` from Develop
- Reviewed all key source files end-to-end
- Merged `feature/mcp-canonical-tool-names` (fast-forward) — tool naming now server-side
- Documented architecture, tool mappings, and known issues
- **Next:** Phase 1 — spin up data-service and list actual MCP tool names / operationIds
