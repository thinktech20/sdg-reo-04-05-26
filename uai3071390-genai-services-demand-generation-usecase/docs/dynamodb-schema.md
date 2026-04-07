# DynamoDB Schema Reference

This document describes the DynamoDB tables used by the SDG platform based on
the current application code in `backend/services/data-service` and
`backend/agents/orchestrator`.

All tables use **PAY_PER_REQUEST** billing and are created either by IaC in AWS
or by `dynamodb-init` in local Docker Compose.

---

## Current Canonical Model

The current codebase is aligned to the following storage model:

- Application-owned domain tables use `esn` as the partition key and
  `createdAt` as the sort key.
- `assessmentId` is a regular attribute and is resolved through GSIs.
- Risk analysis, narrative summary, and event history tables use versioned
  writes: each run writes a fresh row.
- `EXECUTION_STATE_TABLE` is the shared assessment metadata and workflow-state
  store used by both data-service and orchestrator.
- `LANGGRAPH_CHECKPOINTER_TABLE` is library-managed and is not read or written
  directly by first-party application code.

---

## Table Summary

| Env var | Table purpose | PK | SK | GSI(s) used by code |
| --- | --- | --- | --- | --- |
| `EXECUTION_STATE_TABLE` | Assessment metadata + workflow state | `esn` | `createdAt` | `assessment-workflow-index` |
| `RISK_ANALYSIS_TABLE` | Reliability findings + feedback | `esn` | `createdAt` | `ra-assessment-index` |
| `NARRATIVE_SUMMARY_TABLE` | Narrative summary versions | `esn` | `createdAt` | `ns-assessment-index` |
| `EVENT_HISTORY_TABLE` | Event history versions | `esn` | `createdAt` | `eh-assessment-index` |
| `LANGGRAPH_CHECKPOINTER_TABLE` | LangGraph checkpoint persistence | `thread_id` | `checkpoint_ns` | library-managed |

---

## 1. `EXECUTION_STATE_TABLE`

Purpose: stores assessment metadata and orchestrator execution state. Results are
not stored here; they live in the domain output tables.

### Execution state primary key

```text
PK  esn        (S)  - ESN value
SK  createdAt  (S)  - ISO-8601 UTC timestamp
```

### Execution state GSI

| Index name | PK | SK | Used for |
| --- | --- | --- | --- |
| `assessment-workflow-index` | `assessmentId` | `workflowId` | point lookups by assessment + workflow |

### Execution state item shape

| Attribute | Type | Description |
| --- | --- | --- |
| `esn` | S | ESN / equipment identifier |
| `createdAt` | S | Storage sort key; timestamp of initial row creation |
| `assessmentId` | S | Assessment UUID |
| `persona` | S | `RE` or `OE` |
| `workflowId` | S | `RE_DEFAULT`, `OE_DEFAULT`, `RE_NARRATIVE`, or `OE_NARRATIVE` |
| `reviewPeriod` | S | Review window label |
| `unitNumber` | S | Optional unit identifier |
| `workflowStatus` | S | `PENDING`, `IN_QUEUE`, `IN_PROGRESS`, `COMPLETED`, or `FAILED` |
| `errorMessage` | S | Optional terminal error message |
| `activeNode` | S | Current orchestrator node |
| `nodeTimings` | M | Per-node timing map |
| `filters` | M | `{dataTypes, fromDate, toDate}` request context |
| `createdBy` | S | Optional creator identifier |
| `updatedAt` | S | Last mutation timestamp |

### Execution state access patterns

| Pattern | Query path |
| --- | --- |
| Write initial assessment row | `PutItem(PK=esn, SK=createdAt)` |
| Read a specific workflow row | `Query(IndexName="assessment-workflow-index")` |
| Read latest row across workflows for an assessment | `Query(IndexName="assessment-workflow-index")` + max by `updatedAt` / `createdAt` |
| List assessments for an ESN | `Query(PK=esn)` |
| Update workflow state | resolve `(esn, createdAt)` via GSI, then `UpdateItem` |

### Execution state notes

- Current code no longer uses `assessmentId + jobType` as a storage key.
- In mock mode, rows are stored in memory keyed by `assessmentId::workflowId` for
  convenience, but the live DynamoDB path uses the schema above.

---

## 2. `RISK_ANALYSIS_TABLE`

Purpose: stores reliability findings produced by the Risk Evaluation Assistant,
plus user feedback attached to individual findings.

### Risk analysis primary key

```text
PK  esn        (S)  - ESN value
SK  createdAt  (S)  - ISO-8601 UTC timestamp, new per run
```

### Risk analysis GSI

| Index name | PK | SK | Used for |
| --- | --- | --- | --- |
| `ra-assessment-index` | `assessmentId` | — | lookup by assessment ID |

### Risk analysis item shape

| Attribute | Type | Description |
| --- | --- | --- |
| `esn` | S | ESN / equipment identifier |
| `createdAt` | S | Storage sort key; run timestamp |
| `assessmentId` | S | Assessment UUID |
| `rawRows` | L | Raw evidence rows returned by the risk-eval pipeline |
| `findings` | L | Grouped findings consumed by the UI and narrative generation |
| `feedback` | M | Map keyed by `findingId` |
| `updatedAt` | S | Last mutation timestamp |

### Feedback map shape

| Field | Type | Description |
| --- | --- | --- |
| `userId` | S | User ID of the submitting engineer |
| `rating` | N | `1`, `-1`, or `0` |
| `comments` | S | Optional free text |
| `helpful` | BOOL | Derived from rating |
| `submittedAt` | S | Submission timestamp |

### Risk analysis access patterns

| Pattern | Query path |
| --- | --- |
| Write findings for a new run | `PutItem(PK=esn, SK=createdAt)` |
| Get latest findings for an assessment | `Query(IndexName="ra-assessment-index")` |
| Get all historical runs for an assessment | `Query(IndexName="ra-assessment-index")` |
| Update feedback on latest run | resolve `(esn, createdAt)` via GSI, then `UpdateItem` |

### Risk analysis notes

- The live table uses versioned writes, not overwrite-in-place semantics.
- The GSI is the canonical path for assessment-based reads.

---

## 3. `NARRATIVE_SUMMARY_TABLE`

Purpose: stores narrative summary text generated from findings and feedback.

### Narrative summary primary key

```text
PK  esn        (S)  - ESN value
SK  createdAt  (S)  - ISO-8601 UTC timestamp, new per generation
```

### Narrative summary GSI

| Index name | PK | SK | Used for |
| --- | --- | --- | --- |
| `ns-assessment-index` | `assessmentId` | — | lookup by assessment ID |

### Narrative summary item shape

| Attribute | Type | Description |
| --- | --- | --- |
| `esn` | S | ESN / equipment identifier |
| `createdAt` | S | Storage sort key; generation timestamp |
| `assessmentId` | S | Assessment UUID |
| `persona` | S | `RE` or `OE` |
| `summary` | S | Narrative text |
| `updatedAt` | S | Last mutation timestamp |

### Narrative summary access patterns

| Pattern | Query path |
| --- | --- |
| Write a new narrative | `PutItem(PK=esn, SK=createdAt)` |
| Get latest narrative for an assessment | `Query(IndexName="ns-assessment-index")` |
| Get all narrative generations for an assessment | `Query(IndexName="ns-assessment-index")` |

### Narrative summary notes

- Like risk analysis, this table uses versioned writes.

---

## 4. `EVENT_HISTORY_TABLE`

Purpose: stores the event history output for OE workflows.

### Event history primary key

```text
PK  esn        (S)  - ESN value
SK  createdAt  (S)  - ISO-8601 UTC timestamp, new per run
```

### Event history GSI

| Index name | PK | SK | Used for |
| --- | --- | --- | --- |
| `eh-assessment-index` | `assessmentId` | — | lookup by assessment when ESN is not known |

### Event history item shape

| Attribute | Type | Description |
| --- | --- | --- |
| `esn` | S | ESN / equipment identifier |
| `createdAt` | S | Storage sort key; run timestamp |
| `assessmentId` | S | Assessment UUID |
| `events` | L | Event-history records |
| `generatedAt` | S | Generation timestamp |

### Event history access patterns

| Pattern | Query path |
| --- | --- |
| Write event history for a new run | `PutItem(PK=esn, SK=createdAt)` |
| Get latest event history for an assessment | `Query(IndexName="eh-assessment-index")` then choose latest by `createdAt` / `generatedAt` |
| Get event-history rows for an ESN | `Query(PK=esn)` |

---

## 5. `LANGGRAPH_CHECKPOINTER_TABLE`

Purpose: stores LangGraph checkpoint state for the orchestrator.

### Checkpointer primary key

```text
PK  thread_id      (S)
SK  checkpoint_ns  (S)
```

### Checkpointer notes

- This schema is dictated by the LangGraph library.
- First-party application code does not directly read or write this table.
- Do not add app-specific GSIs or mutate the schema unless a LangGraph upgrade
  explicitly requires it.

---

## Shared Patterns And Conventions

### Versioned writes

The current code treats risk analysis, narrative summary, and event history as
append-only per-run outputs:

- each new run writes a fresh row with a fresh `createdAt`
- latest-run reads resolve through the appropriate GSI
- historical rows remain available for diagnostics and auditing

### GSIs by table

| Table | Active GSI strategy |
| --- | --- |
| `EXECUTION_STATE_TABLE` | exact workflow lookup via `assessment-workflow-index` |
| `RISK_ANALYSIS_TABLE` | lookup via `ra-assessment-index` |
| `NARRATIVE_SUMMARY_TABLE` | lookup via `ns-assessment-index` |
| `EVENT_HISTORY_TABLE` | lookup via `eh-assessment-index` |

---

## Local Provisioning Notes

Current checked-in local configuration points these env vars at the provisioned
AWS dev table names in `backend/.env.example`:

| Env var | Checked-in local value |
| --- | --- |
| `EXECUTION_STATE_TABLE` | `app-uai3071390-sdg-ddtable-execution-state-store-dev` |
| `RISK_ANALYSIS_TABLE` | `app-uai3071390-sdg-ddtable-risk-analysys-output-table-dev` |
| `NARRATIVE_SUMMARY_TABLE` | `app-uai3071390-sdg-ddtable-navigation-summary-dev` |
| `EVENT_HISTORY_TABLE` | `app-uai3071390-sdg-ddtable-event-history-report-dev` |
| `LANGGRAPH_CHECKPOINTER_TABLE` | `app-uai3071390-sdg-ddtable-orchestrator-checkpointer-dev` |

In local Docker Compose, `dynamodb-init` creates equivalent local tables using
these env vars plus the GSIs documented above.
