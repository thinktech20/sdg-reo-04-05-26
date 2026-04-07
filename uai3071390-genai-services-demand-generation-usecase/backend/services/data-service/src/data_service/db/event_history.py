"""
EventHistory DynamoDB table abstraction.

Table schema (AWS-provisioned — aligned with infra)
----------------------------------------------------
PK  esn          (S)  — ESN value
SK  createdAt    (S)  — ISO-8601 UTC timestamp (fresh per run)

  assessmentId (S)  — regular attribute; GSI-1 PK for lookup without ESN

events       (L)  — event history records from the orchestrator
generatedAt  (S)  — ISO-8601 timestamp

GSI-1: eh-assessment-index (PK=assessmentId, ALL)
  → standard single-item lookup without knowing esn
"""

from __future__ import annotations

from datetime import timezone, datetime
from typing import Any

from data_service import config
from data_service.db import sanitize_for_dynamodb

# ── In-memory store ────────────────────────────────────────────────────────────
_STORE: dict[str, dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


# ── Public API ─────────────────────────────────────────────────────────────────


def write_event_history(esn: str, assessment_id: str, events: list[dict[str, Any]]) -> None:
    """Persist event history for an assessment (one item per assessment, overwrite on re-run)."""
    if config.USE_MOCK_ASSESSMENTS:
        _STORE[assessment_id] = {
            "esn": esn,
            "createdAt": _now(),
            "assessmentId": assessment_id,
            "events": events,
            "generatedAt": _now(),
        }
    else:  # pragma: no cover
        import boto3  # noqa: PLC0415

        table = boto3.resource(
            "dynamodb",
            region_name=config.DYNAMODB_REGION,
            endpoint_url=config.DYNAMODB_ENDPOINT_URL,
        ).Table(config.EVENT_HISTORY_TABLE)
        now = _now()
        table.put_item(
            Item=sanitize_for_dynamodb({
                "esn": esn,               # table PK
                "createdAt": now,         # table SK (timestamp, fresh per run)
                "assessmentId": assessment_id,
                "events": events,
                "generatedAt": now,
            })
        )


def read_event_history(assessment_id: str) -> dict[str, Any] | None:
    """Return the event history item for an assessment, or None if not found.

    Mock: direct lookup by assessmentId.
    Live: GSI-1 Query(assessmentId=X, Limit=1).
    """
    if config.USE_MOCK_ASSESSMENTS:
        return _STORE.get(assessment_id)
    else:  # pragma: no cover
        import boto3  # noqa: PLC0415
        from boto3.dynamodb.conditions import Key  # noqa: PLC0415
        from botocore.exceptions import ClientError  # noqa: PLC0415

        table = boto3.resource(
            "dynamodb",
            region_name=config.DYNAMODB_REGION,
            endpoint_url=config.DYNAMODB_ENDPOINT_URL,
        ).Table(config.EVENT_HISTORY_TABLE)
        try:
            resp = table.query(
                IndexName=config.APP_PREFIX + "eh-assessment-index",
                KeyConditionExpression=Key("assessmentId").eq(assessment_id),
            )
            items = resp.get("Items", [])
            if not items:
                return None
            items.sort(key=lambda x: str(x.get("createdAt") or x.get("generatedAt") or ""), reverse=True)
            return items[0]
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ResourceNotFoundException":
                return None
            raise


def clear() -> None:
    """Remove all records — used between tests."""
    _STORE.clear()
