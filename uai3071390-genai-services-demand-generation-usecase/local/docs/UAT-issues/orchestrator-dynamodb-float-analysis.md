# Orchestrator DynamoDB Float Serialization Analysis

Date: 2026-03-27

## Problem Summary

Orchestrator status persistence to DynamoDB intermittently failed during finalize/write operations with:

`TypeError: Float types are not supported. Use Decimal types instead.`

Observed log pattern:

- `orchestrator: DynamoDB job-store write failed ... falling back to in-memory write`
- stack trace through boto3 dynamodb serializer internals (`_serialize_m`, `_serialize_l`, `_is_number`)

## Root Cause

This is an application-side boto3 serialization issue, not an AWS service outage.

- boto3 DynamoDB serializer does not accept Python `float`.
- At least one float exists in nested payload written by orchestrator `job_store`.
- The write fails before request reaches DynamoDB API.

Likely source field:

- `result` (from pipeline `final_result`) is most likely to carry nested numeric metrics/scores as floats.
- `nodeTimings` is usually string timestamps and less likely the source.

## Why Recursive Sanitization Is Required

Payload shape is nested (`dict`/`list` combinations). If only top-level fields are converted, deep floats remain and still fail serialization.

Evidence from traceback:

- repeated nested serializer calls (`_serialize_m`, `_serialize_l`) before failure
- error thrown only after traversing deep structure

Therefore conversion must recurse through nested containers.

## Fix Applied (Code-Level)

File changed:

- `backend/agents/orchestrator/src/orchestrator/job_store.py`

What was added:

- Recursive sanitizer `_sanitize_for_dynamodb(value)` converting `float -> Decimal(str(value))`
- Applied to the `updates` payload before both:
  - `table.put_item(Item=item)`
  - `table.update_item(... ExpressionAttributeValues=expr_values)`

## Performance Considerations

Overhead exists but is typically acceptable:

- Complexity is linear in payload size: `O(n)` across nested elements.
- This runs only on orchestrator status writes, not on all request paths.
- DynamoDB network latency generally dominates compared to in-process traversal cost.

Optimization options (if needed later):

1. Fast-path skip when no float is present.
2. Sanitize only high-risk fields (for example `result`) instead of all update fields.
3. In-place mutation for dict/list containers to reduce allocations.

## Should We Also Investigate Why Floats Are Produced?

Yes. The boundary fix is required for reliability, but upstream investigation is still important.

Why investigate upstream:

1. Clarifies whether float usage is intentional (for example scores/confidence values) or accidental.
2. Prevents similar failures in other persistence sinks or integrations that may also reject floats.
3. Helps establish a stable data contract for orchestrator `final_result` payloads.

Likely upstream source:

- `result` persisted by orchestrator (derived from pipeline `final_result`) is the highest-probability source of nested floats.

Suggested follow-up checks:

1. Trace node outputs in orchestrator graph for float-emitting fields (scores, confidence, percentages, durations).
2. Check JSON parsing paths that materialize numbers as Python float.
3. Define schema expectations for numeric fields (Decimal vs int vs float) in result payloads.

Conclusion:

- Keep boundary sanitization as a safety net.
- Also perform root-cause analysis upstream for long-term data quality and consistency.

## Operational Impact

Before fix:

- DynamoDB write failure triggered fallback to in-memory state (non-durable across restarts/replicas).

After fix:

- Nested float values are converted for DynamoDB compatibility.
- Expected reduction/elimination of fallback writes caused by float serialization errors.

## Quick Classification

- Type of failure: Data type serialization mismatch
- Layer: Application runtime (boto3 serializer)
- Not a root cause: AWS DynamoDB service availability
