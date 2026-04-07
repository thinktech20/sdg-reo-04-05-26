"""
ExecutionState DynamoDB table abstraction.

Table: EXECUTION_STATE_TABLE  (env var → "execution-state-store")

Schema (AWS-provisioned — aligned with infra):
    PK  esn            (S)  — ESN value
    SK  createdAt      (S)  — ISO-8601 UTC timestamp

Item fields
-----------
  assessmentId   (S)  — UUID, GSI-1 PK
  persona        (S)  — RE | OE
  workflowId     (S)  — RE_DEFAULT | OE_DEFAULT
  reviewPeriod   (S)  — 18-months | 12-months | 6-months
  unitNumber     (S)  — optional
  workflowStatus (S)  — PENDING | IN_QUEUE | IN_PROGRESS | COMPLETED | FAILED
  errorMessage   (S)  — set on FAILED
  activeNode     (S)  — set during execution
  nodeTimings    (M)  — per-node timings
  filters        (M)  — {dataTypes, fromDate, toDate}
  createdBy      (S)  — optional
  updatedAt      (S)  — ISO-8601

GSI-1: assessment-workflow-index  (PK=assessmentId, SK=workflowId, projection ALL)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from data_service import config
from data_service.db import sanitize_for_dynamodb

# In-memory mock store — keyed by "assessmentId::workflowId" for O(1) lookup
_STORE: dict[str, dict[str, Any]] = {}


def _store_key(assessment_id: str, workflow_id: str) -> str:
    return f"{assessment_id}::{workflow_id}"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _normalized_item(item: dict[str, Any]) -> dict[str, Any]:
    """Return an app-level assessment row shape regardless of storage backend."""
    return dict(item)


def _pick_latest(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not items:
        return None
    return max(items, key=lambda x: str(x.get("updatedAt") or x.get("createdAt") or ""))


def _ddb_table():  # type: ignore[return]  # pragma: no cover
    """Return a boto3 DynamoDB Table resource (lazy — avoids import at module load)."""
    import boto3  # noqa: PLC0415

    return boto3.resource(
        "dynamodb",
        region_name=config.DYNAMODB_REGION,
        endpoint_url=config.DYNAMODB_ENDPOINT_URL,
    ).Table(config.EXECUTION_STATE_TABLE)


# ── Public API ─────────────────────────────────────────────────────────────────


def write_assessment(
    esn: str,
    assessment_id: str,
    persona: str,
    workflow_id: str,
    review_period: str = "",
    unit_number: str | None = None,
    filters: dict[str, Any] | None = None,
    created_by: str | None = None,
) -> dict[str, Any]:
    """Create a new execution-state record for an assessment (PutItem)."""
    now = _now()
    record: dict[str, Any] = {
        "esn": esn,
        "createdAt": now,
        "assessmentId": assessment_id,
        "persona": persona,
        "workflowId": workflow_id,
        "reviewPeriod": review_period,
        "unitNumber": unit_number or "",
        "workflowStatus": "PENDING",
        "filters": filters or {},
        "createdBy": created_by or "",
        "updatedAt": now,
    }
    if config.USE_MOCK_ASSESSMENTS:
        _STORE[_store_key(assessment_id, workflow_id)] = record
    else:  # pragma: no cover
        _ddb_table().put_item(Item=sanitize_for_dynamodb(record))
    return record


def read_assessment_by_id(assessment_id: str, workflow_id: str) -> dict[str, Any] | None:
    """Return the execution-state record for (assessmentId, workflowId), or None if absent."""
    if config.USE_MOCK_ASSESSMENTS:
        item = _STORE.get(_store_key(assessment_id, workflow_id))
        return _normalized_item(item) if item else None
    else:  # pragma: no cover
        from boto3.dynamodb.conditions import Key  # noqa: PLC0415

        query_kwargs: dict[str, Any] = {
            "IndexName": config.APP_PREFIX + "assessment-workflow-index",
            "KeyConditionExpression": Key("assessmentId").eq(assessment_id) & Key("workflowId").eq(workflow_id),
        }
        items: list[dict[str, Any]] = []
        while True:
            response = _ddb_table().query(**query_kwargs)
            items.extend(response.get("Items", []))
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            query_kwargs["ExclusiveStartKey"] = last_key
        latest = _pick_latest(items)
        return _normalized_item(latest) if latest else None


def read_latest_assessment(assessment_id: str) -> dict[str, Any] | None:
    """Return the latest execution-state row for an assessment across workflows."""
    if config.USE_MOCK_ASSESSMENTS:
        candidates = [v for v in _STORE.values() if v.get("assessmentId") == assessment_id]
        if not candidates:
            return None
        latest = max(candidates, key=lambda x: str(x.get("updatedAt") or x.get("createdAt") or ""))
        return _normalized_item(latest)
    else:  # pragma: no cover
        from boto3.dynamodb.conditions import Key  # noqa: PLC0415

        response = _ddb_table().query(
            IndexName=config.APP_PREFIX + "assessment-workflow-index",
            KeyConditionExpression=Key("assessmentId").eq(assessment_id),
        )
        items = response.get("Items", [])
        if not items:
            return None
        latest = max(items, key=lambda x: str(x.get("updatedAt") or x.get("createdAt") or ""))
        return _normalized_item(latest)


def list_assessments_by_esn(esn: str, status: str | None = None) -> list[dict[str, Any]]:
    """Return execution-state records for an ESN, optionally filtered by workflowStatus."""
    if config.USE_MOCK_ASSESSMENTS:
        results = [v for v in _STORE.values() if v.get("esn") == esn]
        if status:
            results = [r for r in results if r.get("workflowStatus", "").lower() == status.lower()]
        return [_normalized_item(r) for r in results]
    else:  # pragma: no cover
        # esn is the table PK — direct table query by ESN, no GSI or scan needed.
        from boto3.dynamodb.conditions import Key  # noqa: PLC0415

        response = _ddb_table().query(
            KeyConditionExpression=Key("esn").eq(esn),
        )
        items = response.get("Items", [])
        if status:
            items = [i for i in items if i.get("workflowStatus", "").lower() == status.lower()]
        return [_normalized_item(i) for i in items]


def list_assessments(
    status: str | None = None,
    esn: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    """List execution-state rows with optional status/ESN/date filters."""
    status_lc = (status or "").lower()
    esn_lc = (esn or "").lower()

    def _matches(item: dict[str, Any]) -> bool:
        created_at = str(item.get("createdAt") or "")
        workflow_status = str(item.get("workflowStatus") or item.get("status") or "").lower()
        item_esn = str(item.get("esn") or "").lower()
        if status_lc and workflow_status != status_lc:
            return False
        if esn_lc and item_esn != esn_lc:
            return False
        if date_from and created_at < date_from:
            return False
        if date_to and created_at > f"{date_to}T23:59:59Z":
            return False
        return True

    if config.USE_MOCK_ASSESSMENTS:
        rows = [_normalized_item(v) for v in _STORE.values()]
    else:  # pragma: no cover
        table = _ddb_table()
        rows: list[dict[str, Any]] = []
        if esn:
            from boto3.dynamodb.conditions import Key  # noqa: PLC0415

            query_kwargs: dict[str, Any] = {
                "KeyConditionExpression": Key("esn").eq(esn),
            }
            while True:
                resp = table.query(**query_kwargs)
                rows.extend(resp.get("Items", []))
                last_key = resp.get("LastEvaluatedKey")
                if not last_key:
                    break
                query_kwargs["ExclusiveStartKey"] = last_key
        else:
            scan_kwargs: dict[str, Any] = {}
            while True:
                resp = table.scan(**scan_kwargs)
                rows.extend(resp.get("Items", []))
                last_key = resp.get("LastEvaluatedKey")
                if not last_key:
                    break
                scan_kwargs["ExclusiveStartKey"] = last_key
        rows = [_normalized_item(r) for r in rows]

    filtered = [r for r in rows if _matches(r)]
    filtered.sort(key=lambda x: str(x.get("updatedAt") or x.get("createdAt") or ""), reverse=True)
    return filtered


def update_execution_state(
    assessment_id: str,
    workflow_id: str,
    workflow_status: str | None = None,
    error_message: str | None = None,
    active_node: str | None = None,
    node_timings: dict[str, Any] | None = None,
) -> None:
    """Patch execution-state fields for a (assessmentId, workflowId) row.

    If no record exists in the mock store (e.g. seed assessments that were never
    written via write_assessment), a minimal placeholder is created so that status
    updates are never silently dropped.
    """
    if config.USE_MOCK_ASSESSMENTS:
        key = _store_key(assessment_id, workflow_id)
        record = _STORE.get(key)
        if record is None:
            record = {
                "assessmentId": assessment_id,
                "workflowId": workflow_id,
                "workflowStatus": "PENDING",
                "updatedAt": _now(),
            }
            _STORE[key] = record
        if workflow_status is not None:
            record["workflowStatus"] = workflow_status
        if error_message is not None:
            record["errorMessage"] = error_message
        if active_node is not None:
            record["activeNode"] = active_node
        if node_timings is not None:
            record["nodeTimings"] = node_timings
        record["updatedAt"] = _now()
    else:  # pragma: no cover
        from boto3.dynamodb.conditions import Key  # noqa: PLC0415

        # Resolve table keys (esn, createdAt) via GSI-1 first.
        query_kwargs: dict[str, Any] = {
            "IndexName": config.APP_PREFIX + "assessment-workflow-index",
            "KeyConditionExpression": Key("assessmentId").eq(assessment_id) & Key("workflowId").eq(workflow_id),
            "ProjectionExpression": "esn, createdAt, updatedAt",
        }
        key_items: list[dict[str, Any]] = []
        while True:
            resp = _ddb_table().query(**query_kwargs)
            key_items.extend(resp.get("Items", []))
            last_key = resp.get("LastEvaluatedKey")
            if not last_key:
                break
            query_kwargs["ExclusiveStartKey"] = last_key
        if not key_items:
            # No existing row for this workflow yet (common for narrative regen).
            # Seed a new row by cloning metadata from the latest assessment row.
            seed_resp = _ddb_table().query(
                IndexName=config.APP_PREFIX + "assessment-workflow-index",
                KeyConditionExpression=Key("assessmentId").eq(assessment_id),
                ScanIndexForward=False,
                Limit=1,
            )
            seed_items = seed_resp.get("Items", [])
            if not seed_items:
                return
            seed = seed_items[0]
            now = _now()
            new_item: dict[str, Any] = {
                "esn": seed.get("esn", ""),
                "createdAt": now,
                "assessmentId": assessment_id,
                "persona": seed.get("persona", ""),
                "workflowId": workflow_id,
                "reviewPeriod": seed.get("reviewPeriod", ""),
                "unitNumber": seed.get("unitNumber", ""),
                "workflowStatus": workflow_status or "PENDING",
                "filters": seed.get("filters", {}),
                "createdBy": seed.get("createdBy", ""),
                "updatedAt": now,
            }
            if error_message is not None:
                new_item["errorMessage"] = error_message
            if active_node is not None:
                new_item["activeNode"] = active_node
            if node_timings is not None:
                new_item["nodeTimings"] = node_timings
            _ddb_table().put_item(Item=sanitize_for_dynamodb(new_item))
            return
        latest_key_item = _pick_latest(key_items)
        if not latest_key_item:
            return
        item_key = {"esn": latest_key_item["esn"], "createdAt": latest_key_item["createdAt"]}
        updates: dict[str, Any] = {"updatedAt": _now()}
        if workflow_status is not None:
            updates["workflowStatus"] = workflow_status
        if error_message is not None:
            updates["errorMessage"] = error_message
        if active_node is not None:
            updates["activeNode"] = active_node
        if node_timings is not None:
            updates["nodeTimings"] = node_timings
        expr_parts = [f"#{k} = :{k}" for k in updates]
        _ddb_table().update_item(
            Key=item_key,
            UpdateExpression="SET " + ", ".join(expr_parts),
            ExpressionAttributeNames={f"#{k}": k for k in updates},
            ExpressionAttributeValues=sanitize_for_dynamodb({f":{k}": v for k, v in updates.items()}),
        )


def clear() -> None:
    """Remove all records — test helper."""
    _STORE.clear()
