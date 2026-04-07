"""Orchestrator job state store.

Two backends selected by ORCHESTRATOR_USE_DYNAMODB:

    false (default) - InMemoryJobStore: dict-based, process-local.
                                        Use for local dev, unit tests, and single-replica deploys.

    true            - DynamoDB-backed status rows written into EXECUTION_STATE_TABLE
                                        using the same assessmentId+workflowId index as data-service.
                                        Use in production ECS to support multi-replica orchestrator
                                        deployments.

NOTE: The orchestrator should run with desiredCount=1 when
ORCHESTRATOR_USE_DYNAMODB=false. With DynamoDB enabled, multiple replicas can
coexist because all replicas read/write shared status records.
"""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

import orchestrator.config as config

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _workflow_id(persona: str, job_type: str) -> str:
    persona_up = (persona or "RE").upper()
    suffix = "DEFAULT" if job_type == "run" else "NARRATIVE"
    return f"{persona_up}_{suffix}"


def _pick_latest(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not items:
        return None
    return max(items, key=lambda x: str(x.get("updatedAt") or x.get("createdAt") or ""))

# ---------------------------------------------------------------------------
# In-memory backend
# ---------------------------------------------------------------------------

_store: dict[tuple[str, str], dict[str, Any]] = {}


def _write_memory(data: dict[str, Any]) -> None:
    _store[(data["assessmentId"], data["jobType"])] = data


def _read_memory(assessment_id: str, job_type: str) -> dict[str, Any] | None:
    return _store.get((assessment_id, job_type))


def _sanitize_for_dynamodb(obj: Any) -> Any:
    """Recursively convert float → Decimal for DynamoDB boto3 compatibility.

    Orchestrator is a separate deployable from data-service so this is a local
    duplicate of data_service.db.sanitize_for_dynamodb.
    """
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return str(obj)
        try:
            return Decimal(str(obj))
        except InvalidOperation:
            return str(obj)
    if isinstance(obj, dict):
        return {k: _sanitize_for_dynamodb(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_for_dynamodb(v) for v in obj]
    return obj


# ---------------------------------------------------------------------------
# DynamoDB backend
# ---------------------------------------------------------------------------

def _get_table() -> Any:
    import boto3  # noqa: PLC0415

    kwargs: dict[str, Any] = {"region_name": config.AWS_REGION}
    if config.DYNAMODB_ENDPOINT_URL:
        kwargs["endpoint_url"] = config.DYNAMODB_ENDPOINT_URL
    return boto3.resource("dynamodb", **kwargs).Table(config.EXECUTION_STATE_TABLE)


def _resolve_row_key(table: Any, assessment_id: str, workflow_id: str) -> dict[str, Any] | None:
    from boto3.dynamodb.conditions import Key  # noqa: PLC0415

    query_kwargs: dict[str, Any] = {
        "IndexName": config.APP_PREFIX + "assessment-workflow-index",
        "KeyConditionExpression": Key("assessmentId").eq(assessment_id) & Key("workflowId").eq(workflow_id),
        "ProjectionExpression": "esn, createdAt, updatedAt",
    }
    items: list[dict[str, Any]] = []
    while True:
        resp = table.query(**query_kwargs)
        items.extend(resp.get("Items", []))
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break
        query_kwargs["ExclusiveStartKey"] = last_key
    latest = _pick_latest(items)
    if not latest:
        return None
    return {"esn": latest["esn"], "createdAt": latest["createdAt"]}


def _resolve_latest_status_item(table: Any, assessment_id: str, job_type: str) -> dict[str, Any] | None:
    from boto3.dynamodb.conditions import Key  # noqa: PLC0415

    candidates: list[dict[str, Any]] = []
    for persona in ("RE", "OE"):
        workflow_id = _workflow_id(persona, job_type)
        query_kwargs: dict[str, Any] = {
            "IndexName": config.APP_PREFIX + "assessment-workflow-index",
            "KeyConditionExpression": Key("assessmentId").eq(assessment_id) & Key("workflowId").eq(workflow_id),
        }
        while True:
            resp = table.query(**query_kwargs)
            candidates.extend(resp.get("Items", []))
            last_key = resp.get("LastEvaluatedKey")
            if not last_key:
                break
            query_kwargs["ExclusiveStartKey"] = last_key
    return _pick_latest(candidates)


def _to_job_status(item: dict[str, Any], assessment_id: str, job_type: str) -> dict[str, Any]:
    return {
        "assessmentId": assessment_id,
        "jobType": job_type,
        "status": item.get("status") or "PENDING",
        "result": item.get("result"),
        "errorMessage": item.get("errorMessage"),
        "activeNode": item.get("activeNode"),
        "nodeTimings": item.get("nodeTimings"),
    }


def _write_dynamodb(data: dict[str, Any]) -> None:
    assessment_id = data.get("assessmentId", "<unknown>")
    _write_memory(data)  # always mirror full data (including result) to in-memory store
    try:
        table = _get_table()
        job_type = str(data.get("jobType") or "run")
        persona = str(data.get("persona") or "RE").upper()
        workflow_id = _workflow_id(persona, job_type)
        # Exclude 'result' — the full LLM output can exceed DynamoDB's 400KB item limit.
        # result is stored in-memory only (see _write_memory above) and merged back on reads.
        updates = _sanitize_for_dynamodb({
            "jobType": job_type,
            "status": data.get("status", "PENDING"),
            "errorMessage": data.get("errorMessage"),
            "activeNode": data.get("activeNode"),
            "nodeTimings": data.get("nodeTimings"),
            "updatedAt": _now(),
        })

        key = _resolve_row_key(table, assessment_id, workflow_id)
        if key is None:
            esn = str(data.get("esn") or "")
            if not esn:
                raise ValueError(
                    f"Cannot create orchestrator status row for {assessment_id}/{workflow_id} without esn"
                )
            now = _now()
            item: dict[str, Any] = {
                "esn": esn,
                "createdAt": now,
                "assessmentId": assessment_id,
                "workflowId": workflow_id,
                "persona": persona,
                "workflowStatus": "IN_PROGRESS",
                "updatedAt": now,
                **{k: v for k, v in updates.items() if v is not None},
            }
            table.put_item(Item=item)
            return

        expr_parts: list[str] = []
        expr_names: dict[str, str] = {}
        expr_values: dict[str, Any] = {}
        for field, value in updates.items():
            if value is None:
                continue
            expr_parts.append(f"#{field} = :{field}")
            expr_names[f"#{field}"] = field
            expr_values[f":{field}"] = value
        if expr_parts:
            table.update_item(
                Key=key,
                UpdateExpression="SET " + ", ".join(expr_parts),
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values,
            )
    except Exception:
        logger.exception(
            "orchestrator: DynamoDB job-store write failed assessment_id=%s "
            "(in-memory result already saved)",
            assessment_id,
        )


def _read_dynamodb(assessment_id: str, job_type: str) -> dict[str, Any] | None:
    try:
        table = _get_table()
        item = _resolve_latest_status_item(table, assessment_id, job_type)
        if not item:
            return _read_memory(assessment_id, job_type)
        status_row = _to_job_status(item, assessment_id, job_type)
        # result is excluded from DynamoDB writes — merge it back from in-memory store
        mem = _read_memory(assessment_id, job_type)
        if mem and mem.get("result") is not None:
            status_row["result"] = mem["result"]
        return status_row
    except Exception:
        logger.exception(
            "orchestrator: DynamoDB job-store read failed assessment_id=%s - "
            "falling back to in-memory read",
            assessment_id,
        )
        return _read_memory(assessment_id, job_type)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def write_job(assessment_id: str, job_type: str, status: str, **kwargs: Any) -> None:
    data: dict[str, Any] = {
        "assessmentId": assessment_id,
        "jobType": job_type,
        "status": status,
        **kwargs,
    }
    if config.ORCHESTRATOR_USE_DYNAMODB:
        _write_dynamodb(data)
    else:
        _write_memory(data)


def read_job(assessment_id: str, job_type: str) -> dict[str, Any] | None:
    if config.ORCHESTRATOR_USE_DYNAMODB:
        return _read_dynamodb(assessment_id, job_type)
    return _read_memory(assessment_id, job_type)
