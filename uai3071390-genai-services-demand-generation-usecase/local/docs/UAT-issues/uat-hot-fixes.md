This change (from commit 0a87fbc — "Fix QnA assessment context and MCP tool aliases") fixes a gap where assessment_id was not being passed to the LLM when serial_number was missing.

Before: If no serial_number was in the context, the function returned the raw message with no assessment context at all — the agent had no idea which assessment the user was asking about.

After: The assessment_id is always included in the prompt. When serial_number is present, the agent is told to use it for equipment queries. 
When it's absent, the agent is told to use assessment_id for assessment-specific data lookups (e.g., read_re_table, read_re_report).

====

The system prompts say nothing about assessment_id. They only mention serial_number (for query_fsr, query_er, read_ibat, read_prism, etc.) and say "Use the serial number from the current session context."

However, the assessment tools (read_re_table / read_re_report / read_risk_analysis) take assessment_id as their path parameter — that's the only way to call them.

So the behavior change is correct and necessary for the assessment chat flow:

The assessment endpoints (/assessments/{assessment_id}/chat/reliability) always have an assessment_id from the URL path
Without passing it in the prompt, the LLM has no way to supply it when calling read_re_table(assessment_id=...) or read_re_report(assessment_id=...)
The tools that need serial_number (query_fsr, query_er, read_ibat, read_prism) still get it when present


What's missing: the system prompts don't mention assessment_id at all. The prompts describe read_re_table and read_re_report without explaining that they require an assessment_id parameter. The LLM has to infer this from the tool schema + the user prompt context. This works in practice (the LLM sees assessment_id in the prompt and the tool's parameter schema), but it would be cleaner to add a line in the system prompts like:

- Use the assessment_id from the session context when calling `read_re_table`, `read_re_report`, or `read_risk_analysis`.

===

The frontend always sends serialNumber: assessment.serialNumber in the context. serial_number would be missing only if:

assessment.serialNumber is undefined/null/"" — the assessment object in the database doesn't have a serial number populated yet (e.g., assessment was created without selecting equipment, or equipment data hasn't been linked).

Direct API calls without context — someone calls the endpoint with "context": {} or "context": "" (e.g., testing via curl, or a client that doesn't pass context).

OE chat panel — let me check:

Both RE and OE chat panels send serialNumber: assessment.serialNumber. So serial_number will be missing only when:

assessment.serialNumber is falsy (undefined/null/empty string) — this can happen if the assessment was created before equipment was selected, or the DynamoDB record doesn't have that field populated.
Direct API/curl calls with "context": {} or "context": "" — manual testing or integrations that skip the frontend.
In the normal frontend flow, serialNumber should always be present since assessments are created from an equipment selection. The fallback to assessment_id is a safety net — without it, the agent would get no context at all in those edge cases, making it unable to call any assessment tools.