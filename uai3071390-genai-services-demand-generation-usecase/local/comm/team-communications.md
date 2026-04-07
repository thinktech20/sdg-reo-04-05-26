# Team Communications Log


## Apr 6 

StandUp:
Worked with Vaishnavi on the MCP tool name changes - that PR is ready for review. Also verified the OE flow for the adhoc QnA agent end-to-end locally - all 9 tools are wired up and working. That branch depends on the MCP tool names PR, so it merges after. Also looked into a recurring 404 in CloudWatch for /sessions/init - it's a dead code path we can clean up in a separate PR.

1. OE chat flow
tested the OE QnA agent flow end-to-end locally - agent picks up all 9 OE tools and responds correctly. branch is feature/oe-adhoc-qna.

this depends on the MCP canonical tool names PR (with Abhinanaya), so needs to merge after that one.

some of the data-service route changes in my PR might overlap with another branch - we can compare when verifying OE flow together. the key piece from my PR is the tool name mappings.



2. Errors in Cloudwatch Log - 

Naresh pointed me to a recurring 404 in CloudWatch for /sessions/init - the data-service tries to push context to the QnA agent after analysis completes, this should be removed.  The agent already has MCP tools to fetch any data it needs on-demand. The push duplicates what the pull model does. Let me know if anyone sess any issue with it, this is low priority but should eb addressed. I will create a PR for the same unless anyone has objections to it.

# assessments.py line ~341
if orchestrator_status == "COMPLETE":
    _persist_result(...)
    if not workflow_id.endswith("_NARRATIVE"):
        await _init_qna_session(assessment_id, persona, result)  # ← 404
```











## Mar 31 2026 — Prompt Updates + LITELLM_DEBUG

**To**: Naresh (offshore team)
**Channel**: Slack

### Message 1: Prompt redeployment request



Based on the SME validations and Xujin's updates, there are prompt changes needed for:

1. Narrative Summary — updated system prompt - backend/agents/narrative-summary-assistant/src/narrative_summary/prompts.py (system_prompt_RE_Narrative_Short.txt)
2. Risk Evaluation — updated heatmap/risk matrix prompt - backend/agents/risk-evaluation-assistant/src/risk_evaluation/prompt_lib/system_prompt.txt (system_prompt_RE_Risk_Table.txt)

These will require a redeployment. Updated prompts are attached. I've also updated the ticket with the same request.

PR: https://github.apps.gevernova.net/arc-genai/uai3071390-genai-services-demand-generation-usecase/pull/77

Additionally, we need to enable `LITELLM_DEBUG=true` in the deployed environment? Xujin needs the full user prompts visible in the logs while SME validations are ongoing. This can be turned off once validation is complete.

### Message 2: Future improvement — decouple prompts from deployments

One thing to flag for future improvement: right now every prompt change requires a full redeployment. As we iterate more frequently with SME validations, this becomes a bottleneck. We should look at decoupling prompts from the container image — for example, loading system prompts from S3 at runtime with a short TTL cache. That way prompt updates would just be an S3 upload, no redeploy needed. I've documented a design proposal in `docs/hot-reload-prompts-design.md` — we can discuss when priorities allow.
====================================================================

## MCP Tools Mapping - 04/03 - TBD


Notable findings reflected in the update:

3 OE tools (read_event_master, read_oe_table, read_oe_event_report) are in the QnA allowlist and system prompt but have no data-service route yet — they can't actually work
query_risk_er and read_risk_analysis are on the MCP server but not in QnA persona allowlists
Risk-eval agent uses 3 tools (query_fsr, read_risk_matrix, query_risk_er) via raw operationIds, bypassing canonical naming
Removed the old "Retrieve Issue Data" row — that's just query_fsr with a stale alias name