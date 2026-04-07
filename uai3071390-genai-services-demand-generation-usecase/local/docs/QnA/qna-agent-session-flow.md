# Question-Answer Agent — Session Flow

## Session Lifecycle

### 1. Creation

Sessions are created **implicitly** on first use. There is no explicit "create session" call.

- For assessment chat endpoints (`/api/assessments/{id}/chat/reliability` or `/chat/outage`), the **assessment_id is used as the session_id**, but chat history is still stored under a user-scoped S3 prefix. In practice, sessions are assessment-scoped within a user namespace, not globally shared across all users for the same assessment.
- For the generic `/api/v1/chat` endpoint, an optional `session_id` can be passed in the request body.

### 2. Storage

Conversation history is persisted in **S3** (or MinIO locally) via Strands SDK's `S3SessionManager`. The S3 key path is:

```
qna-agent/{user_sso_id}/{session_id}
```

### 3. Per-Request Flow

On each chat request:

1. `S3SessionManager` **loads** the prior conversation from S3.
2. A **fresh `Agent` instance** is built (Strands Agent isn't thread-safe, so no reuse).
3. `SlidingWindowConversationManager(window_size=40)` keeps the last **40 turns** in the LLM context window.
4. The agent processes the prompt with full conversation context + MCP tools.
5. After the response, `S3SessionManager` **saves** the updated conversation back to S3.
6. The session_id is echoed back in the response.

## Assessment Context Binding

When using assessment chat endpoints, the **assessment_id doubles as the session_id**, and assessment metadata (serial number, assessment ID) is injected into the prompt:

```python
"Assessment context:\n"
f"- assessment_id: {assessment_id}\n"
f"- serial_number: {serial_number}\n\n"
"Use the serial number above when querying equipment-specific data.\n\n"
f"User question: {message}"
```

## Middleware Role

The `AuthMiddleware` extracts:

- JWT identity from the ALB `X-Amzn-OIDC-Data` header → `UserContext` (SSO ID used for S3 namespace).
- `X-Session-Id` header → `request.state.session_id`.

In local dev mode (`AUTH_LOCAL_MODE=true`), it injects a synthetic anonymous context.

## Orchestrator Integration

After the orchestrator completes an analysis, the **data-service** fires a `POST /api/v1/sessions/init` to pre-seed the Q&A session with assessment results. **However**, this endpoint is **not yet implemented** in the Q&A agent — so currently context is passed inline with each chat request instead.

## Schemas & Endpoints

### Endpoints

| Endpoint | Persona | Session ID Source |
|---|---|---|
| `POST /api/v1/chat` | `RE` or `OE` (via `persona` field) | Optional `session_id` in body |
| `POST /api/assessments/{id}/chat/reliability` | RE | `assessment_id` from path |
| `POST /api/assessments/{id}/chat/outage` | OE | `assessment_id` from path |

### Request / Response Schemas

**Generic chat:**

```json
// Request: ChatRequest
{ "prompt": "...", "persona": "RE", "session_id": "optional-id" }

// Response: ChatResponse
{ "reply": "...", "session_id": "optional-id" }
```

**Assessment chat:**

```json
// Request: AssessmentChatRequest
{ "message": "...", "context": "..." }

// Response: AssessmentChatResponse
{ "response": { ... }, "chatHistory": [ ... ] }
```

## Session Flow Diagram

```
┌─────────────┐
│   Frontend   │
└──────┬──────┘
       │ POST /assessments/{id}/chat/reliability
       ▼
┌──────────────────────┐
│   ALB (OIDC Auth)    │ ◄─ X-Session-Id header
└──────┬───────────────┘
       │ Forwards X-Amzn-OIDC-Data
       ▼
┌──────────────────────┐
│  AuthMiddleware       │
│  - Validate JWT       │
│  - Extract session_id │
│  - Create UserContext  │
└──────┬───────────────┘
       │ request.state.user_context
       │ request.state.session_id
       ▼
┌──────────────────────────────────────┐
│  chat_reliability endpoint           │
│  - Extract assessment_id → session_id│
│  - Build prompt with context         │
└──────┬───────────────────────────────┘
       │ session_id, persona, prompt
       ▼
┌─────────────────────────────────┐
│  agent_factory.run_agent()      │
│  1. Open MCPClient              │
│  2. Filter tools by persona     │
│  3. build_agent():              │
│     - S3SessionManager(session) │◄──────────┐
│     - SlidingWindow(40 turns)   │           │
│  4. agent.invoke_async(prompt)  │           │
│  5. Close MCPClient             │           │
└──────┬──────────────────────────┘           │
       │                                      │
       ▼                                      │
┌──────────────────────┐                      │
│  S3SessionManager    │                      │
│  Load conversation ──────────────────────►  │
│      from S3         │                      │
└──────┬───────────────┘                      │
       ▼                                      │
┌──────────────────────┐                      │
│  Strands Agent       │                      │
│  + LiteLLM Model     │                      │
│  + MCP Tools         │                      │
│  Process with full   │                      │
│  conversation context│  (40-turn window)    │
└────┬─────────────────┘                      │
     │ Generate reply                         │
     ▼                                        │
┌──────────────────────┐                      │
│  S3SessionManager    │                      │
│  Save updated history───────────────────►   │
│        to S3         │                      │
└────┬─────────────────┘                      │
     │ Return reply                           │
     ▼                                        │
  { response, chatHistory }            S3 Bucket
                                   (Conversation History)
```

## Summary

| Aspect | Detail |
|---|---|
| Session identity | `assessment_id` = `session_id` for assessment chats |
| Persistence | S3 / MinIO, auto-managed by Strands SDK |
| Context window | Last 40 conversation turns |
| Agent lifecycle | Fresh instance per request (thread safety) |
| User isolation | S3 prefix namespaced by SSO ID |
| Warm-up endpoint | Called by data-service but **not yet implemented** |
