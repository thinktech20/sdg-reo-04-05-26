from __future__ import annotations

import json
from datetime import datetime

from data_service.logging_utils import log_ibat_event, log_query_event


def test_log_query_event_includes_iso_timestamp(caplog) -> None:
    caplog.set_level("INFO")
    log_query_event(logger_name="data-svc-test", event="ibat_query", payload={"user": "may"})

    message = caplog.records[-1].message
    body = json.loads(message)
    assert body["event"] == "ibat_query"
    assert body["user"] == "may"
    datetime.fromisoformat(body["timestamp"])


def test_log_ibat_event_emits_required_payload_fields(caplog) -> None:
    caplog.set_level("INFO")
    log_ibat_event(
        user="may",
        serial_number="342447641",
        assessment_id=None,
        equipment_type=None,
        result_ids=["342447641", "G09298"],
        errors=None,
        duration_ms=17,
    )

    message = caplog.records[-1].message
    body = json.loads(message)

    assert "timestamp" in body
    assert body["user"] == "may"
    assert body["serial_number"] == "342447641"
    assert body["errors"] is None
    assert body["result_count"] == 2
    assert body["duration_ms"] == 17
