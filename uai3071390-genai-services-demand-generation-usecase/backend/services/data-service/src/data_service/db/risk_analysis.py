"""
RiskAnalysis DynamoDB table abstraction.

Table schema (AWS-provisioned — aligned with infra)
----------------------------------------------------
PK  esn          (S)  — ESN value
SK  createdAt    (S)  — ISO-8601 UTC

assessmentId (S)  — regular attribute; GSI-1 PK
rawRows      (L)  — flat LLM output rows (ground truth)
findings     (L)  — grouped finding objects consumed by the UI and narrative agent
summary      (S)  — assessment-level summary associated with the findings payload
feedback     (M)  — {findingId → {userId, rating, comments, helpful, submittedAt}}
updatedAt    (S)  — ISO-8601, updated when feedback is written

GSI-1: ra-assessment-index (PK=assessmentId, ALL)
  → LIMIT=1 ScanIndexForward=False gives latest run for an assessmentId
"""

from __future__ import annotations

from datetime import timezone, datetime
from typing import Any

from data_service import config
from data_service.db import sanitize_for_dynamodb
import logging
logger = logging.getLogger(__name__)

# ── In-memory store (default for USE_MOCK / IS_LOCAL) ─────────────────────────
_STORE: dict[str, dict[str, Any]] = {}
_RETRIEVAL_STORE: dict[str, dict[str, Any]] = {}

def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _pick_latest(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not items:
        return None
    return max(items, key=lambda x: str(x.get("updatedAt") or x.get("createdAt") or ""))

def _ddb_table() -> Any:  # pragma: no cover
    import boto3  # noqa: PLC0415

    return boto3.resource(
        "dynamodb",
        region_name=config.DYNAMODB_REGION,
        endpoint_url=config.DYNAMODB_ENDPOINT_URL,
    ).Table(config.RISK_ANALYSIS_TABLE)


def _query_items_by_assessment_id(assessment_id: str) -> list[dict[str, Any]]:  # pragma: no cover
    from boto3.dynamodb.conditions import Key  # noqa: PLC0415

    table = _ddb_table()
    query_kwargs: dict[str, Any] = {
        "IndexName": config.APP_PREFIX + "ra-assessment-index",
        "KeyConditionExpression": Key("assessmentId").eq(assessment_id),
    }
    items: list[dict[str, Any]] = []
    while True:
        response = table.query(**query_kwargs)
        items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        query_kwargs["ExclusiveStartKey"] = last_key
    return items

# ── Public API ─────────────────────────────────────────────────────────────────


def write_risk_analysis(
    esn: str,
    assessment_id: str,
    raw_rows: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    summary: str | None = None,
) -> None:
    """Persist reliability findings for an assessment.

    Each call writes a new item (versioned writes — no idempotency read-before-write).
    The mock store overwrites the latest entry per assessmentId for simplicity.
    """
    from boto3.dynamodb.conditions import Key
    if config.USE_MOCK_ASSESSMENTS:
        existing = _STORE.get(assessment_id, {})
        _STORE[assessment_id] = {
            "esn": esn,
            "assessmentId": assessment_id,
            "createdAt": _now(),
            "rawRows": raw_rows,
            "findings": findings,
            "summary": summary if summary is not None else existing.get("summary", ""),
            "feedback": existing.get("feedback", {}),
            "updatedAt": _now(),
        }
    else:  # pragma: no cover — boto3 path exercised in integration tests only
        import boto3  # noqa: PLC0415

        table = boto3.resource(
            "dynamodb",
            region_name=config.DYNAMODB_REGION,
            endpoint_url=config.DYNAMODB_ENDPOINT_URL,
        ).Table(config.RISK_ANALYSIS_TABLE)
        created_at = _now()
        table.put_item(
            Item=sanitize_for_dynamodb({
                "esn": esn,               # table PK
                "createdAt": created_at,  # table SK
                "assessmentId": assessment_id,
                "rawRows": raw_rows,
                "findings": findings,
                "summary": summary or "",
                "feedback": {},
                "updatedAt": created_at,
            })
        )
        try:
            resp = table.query(
                IndexName=config.APP_PREFIX + "ra-assessment-index",
                KeyConditionExpression=Key("assessmentId").eq(assessment_id),
                ScanIndexForward=False,
            )
            items = resp.get("Items", [])
            total = len(items)
            logger.info("[write_risk_analysis] DynamoDB write validated for assessment_id=%s: %d record(s) found", assessment_id, total)
            # Display top 5 records for verification
            for i, item in enumerate(items):
                logger.info("  [%d] esn=%s, createdAt=%s, findings_count=%s", i+1, item.get("esn"), item.get("createdAt"), item.get("findings", []))
        except Exception as exc:
            logger.error(f"[write_risk_analysis] Post-write validation failed for assessment_id={assessment_id}: {exc}")


def read_risk_analysis(assessment_id: str) -> dict[str, Any] | None:
    """Return the risk analysis item or None if not found."""
    if config.USE_MOCK_ASSESSMENTS:
        return _STORE.get(assessment_id)
    else:  # pragma: no cover
        from botocore.exceptions import ClientError  # noqa: PLC0415

        try:
            items = _query_items_by_assessment_id(assessment_id)
            finding_items = [
                item for item in items if isinstance(item.get("findings"), list)
            ]
            return _pick_latest(finding_items)
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ResourceNotFoundException":
                return None
            raise


def write_feedback(
    assessment_id: str,
    finding_id: str,
    feedback: dict[str, Any],
) -> None:
    """Upsert feedback for a single finding within the latest risk-analysis item."""
    if config.USE_MOCK_ASSESSMENTS:
        item = _STORE.setdefault(
            assessment_id,
            {
                "esn": "",
                "assessmentId": assessment_id,
                "createdAt": _now(),
                "rawRows": [],
                "findings": [],
                "summary": "",
                "feedback": {},
                "updatedAt": _now(),
            },
        )
        item["feedback"][finding_id] = {**feedback, "submittedAt": _now()}
        item["updatedAt"] = _now()
    else:  # pragma: no cover
        import boto3  # noqa: PLC0415
        from boto3.dynamodb.conditions import Key  # noqa: PLC0415

        ddb = boto3.resource(
            "dynamodb",
            region_name=config.DYNAMODB_REGION,
            endpoint_url=config.DYNAMODB_ENDPOINT_URL,
        )
        table = ddb.Table(config.RISK_ANALYSIS_TABLE)
        # Resolve (esn, createdAt) via GSI-1 LIMIT=1 for the UpdateItem key
        resp = table.query(
            IndexName=config.APP_PREFIX + "ra-assessment-index",
            KeyConditionExpression=Key("assessmentId").eq(assessment_id),
            ProjectionExpression="esn, createdAt",
        )
        items = list(resp.get("Items", []))
        while "LastEvaluatedKey" in resp:
            resp = table.query(
                IndexName=config.APP_PREFIX + "ra-assessment-index",
                KeyConditionExpression=Key("assessmentId").eq(assessment_id),
                ExclusiveStartKey=resp["LastEvaluatedKey"],
                ProjectionExpression="esn, createdAt",
            )
            items.extend(resp.get("Items", []))
        latest = _pick_latest(items)
        if not latest:
            return
        esn = latest["esn"]
        created_at = latest["createdAt"]
        # DynamoDB rejects `SET feedback.#fid = :fb` when the parent `feedback` map
        # does not exist on the item (ValidationException: "document path invalid for
        # update").  Items written before the feedback schema was introduced — such as
        # assessments for ESNs that had no ER/FSR data like 337X134 — have no
        # `feedback` attribute at all, which causes a 500.
        #
        # Fix: attempt to initialise the empty map first with a conditional write
        # that only fires when the attribute is truly absent, then write the
        # finding-level entry.  Two separate UpdateItem calls are required because
        # DynamoDB does not allow overlapping paths in a single SET expression
        # (e.g. `SET feedback = :m, feedback.#fid = :fb` is rejected).
        try:
            table.update_item(
                Key={"esn": esn, "createdAt": created_at},
                UpdateExpression="SET feedback = :empty_map",
                ConditionExpression="attribute_not_exists(feedback)",
                ExpressionAttributeValues={":empty_map": {}},
            )
        except Exception as exc:  # noqa: BLE001
            # ConditionalCheckFailedException means feedback already exists — fine.
            if "ConditionalCheckFailedException" not in str(type(exc)):
                raise
        table.update_item(
            Key={"esn": esn, "createdAt": created_at},
            UpdateExpression="SET feedback.#fid = :fb, updatedAt = :ts",
            ExpressionAttributeNames={"#fid": finding_id},
            ExpressionAttributeValues=sanitize_for_dynamodb({
                ":fb": {**feedback, "submittedAt": _now()},
                ":ts": _now(),
            }),
        )


def write_retrieval(assessment_id: str, retrieval: dict[str, Any]) -> None:
    """Persist per-issue retrieval evidence (top-K FSR + ER chunks) for an assessment."""
    if config.USE_MOCK_ASSESSMENTS:
        _RETRIEVAL_STORE[assessment_id] = {
            "assessmentId": assessment_id,
            "retrieval": retrieval,
            "updatedAt": _now(),
        }
    else:  # pragma: no cover
        items = _query_items_by_assessment_id(assessment_id)
        findings_items = [item for item in items if isinstance(item.get("findings"), list)]
        latest_findings = _pick_latest(findings_items)
        if not latest_findings:
            return

        esn = str(latest_findings.get("esn") or "")
        if not esn:
            return

        # Update the existing FINDINGS item in place rather than putting a new item.
        # A separate put_item would create a second DynamoDB row for the same
        # assessmentId. Because write_feedback resolves the target via _pick_latest
        # (latest updatedAt/createdAt), a newer RETRIEVAL row would be selected
        # instead of the FINDINGS row, causing feedback to be written to an item that
        # read_risk_analysis never returns (it filters for items with a `findings`
        # list). Updating in-place keeps findings, feedback, and retrieval on one item.
        _ddb_table().update_item(
            Key={"esn": esn, "createdAt": latest_findings["createdAt"]},
            UpdateExpression="SET retrieval = :retrieval, updatedAt = :ts",
            ExpressionAttributeValues=sanitize_for_dynamodb({
                ":retrieval": retrieval,
                ":ts": _now(),
            }),
        )


def read_retrieval(assessment_id: str) -> dict[str, Any] | None:
    """Return the retrieval evidence item or None if not found."""
    if config.USE_MOCK_ASSESSMENTS:
        return _RETRIEVAL_STORE.get(assessment_id)
    else:  # pragma: no cover
        from botocore.exceptions import ClientError  # noqa: PLC0415

        try:
            items = _query_items_by_assessment_id(assessment_id)
            retrieval_items = [item for item in items if isinstance(item.get("retrieval"), dict)]
            return _pick_latest(retrieval_items)
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ResourceNotFoundException":
                return None
            raise


def clear() -> None:
    """Remove all records — used between tests."""
    _STORE.clear()
    _RETRIEVAL_STORE.clear()
