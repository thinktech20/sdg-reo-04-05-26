# QnA Prompt Fix: Tool Retry Loop Prevention

## Problem (observed 2026-04-03 in dev)

The QnA agent gets stuck in an infinite tool-call loop when a tool keeps returning errors.
In CloudWatch logs, the LLM called `read_prism` **20+ times** with the same serial numbers
(`290T484`, `92307`) that kept returning `SERIAL_NOT_FOUND`. The chat UI just spins forever.

### Root cause

1. **No iteration limit** — Strands SDK (v1.33.0) Agent has no `max_turns` or tool-call cap.
   The event loop recurses without a depth limit.
2. **Weak error handling prompt** — The existing prompt says "suggest alternative keywords,
   a broader query, or a different tool" which the LLM interprets as "try different serial
   number formats" on the same tool.

### CloudWatch log excerpt

```
strands tool_call: name=read_prism
strands tool_error: ... 'SERIAL_NOT_FOUND', 'message': 'No records found for serial 290T484'
strands tool_call: name=read_prism   ← same tool, same serial, immediate retry
strands tool_error: ... 'SERIAL_NOT_FOUND', 'message': 'No records found for serial 290T484'
strands tool_call: name=read_prism   ← again
... (20+ times over ~3 minutes)
```

Also observed: `query_er` hit a Databricks permission error (`Catalog 'vgpp' is not accessible`)
which is a data platform issue, not our code.

## Fix: Update error handling in system prompts

### Files to change

- `backend/agents/question-answer-agent/src/question_answer/prompts/re_system_prompt.txt`
- `backend/agents/question-answer-agent/src/question_answer/prompts/oe_system_prompt.txt`

### Change (both files)

Replace the **Error handling** section:

**BEFORE (re_system_prompt.txt, section 5):**
```
5. **Error handling:**
   - If a tool returns empty or no results, inform the user and suggest alternative keywords, a broader query, or a different tool.
   - If conflicting findings exist across sources, present both and note the discrepancy with citations.
```

**AFTER:**
```
5. **Error handling:**
   - If a tool returns an error or empty results, do NOT retry the same tool with the same or similar parameters. Move on to a different tool or approach.
   - Never call the same tool more than 3 times total in a single response. After 2 consecutive failures from the same tool, stop calling it and work with whatever data you have from other sources.
   - If no tool returns useful results, inform the user clearly and suggest alternative keywords or a broader query.
   - If conflicting findings exist across sources, present both and note the discrepancy with citations.
```

**BEFORE (oe_system_prompt.txt, section 7):**
```
7. **Error handling:**
    - If a tool returns empty or no results, inform the user and suggest alternative keywords, a broader query, or a different tool.
    - If conflicting findings exist across sources, present both and note the discrepancy with citations.
```

**AFTER:**
```
7. **Error handling:**
    - If a tool returns an error or empty results, do NOT retry the same tool with the same or similar parameters. Move on to a different tool or approach.
    - Never call the same tool more than 3 times total in a single response. After 2 consecutive failures from the same tool, stop calling it and work with whatever data you have from other sources.
    - If no tool returns useful results, inform the user clearly and suggest alternative keywords or a broader query.
    - If conflicting findings exist across sources, present both and note the discrepancy with citations.
```

## Notes

- Strands SDK has no `max_turns` parameter on Agent or `invoke_async`. The only control is
  the system prompt.
- This is a prompt-only change — no code changes needed.
- The fix was tested locally but reverted to keep prompt files clean while other priorities
  are addressed. Re-apply this change when ready to deploy.
