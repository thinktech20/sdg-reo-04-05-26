"""Tests for POST /dataservices/api/v1/prism/read."""

from fastapi.testclient import TestClient

from data_service.routes import prism as prism_route


def _mock_prism_success(serial_number: str, metadata_filters: dict[str, str] | None = None) -> dict:
    return {
        "status": "success",
        "record_count": 1,
        "data": [{"TURBINE_NUMBER": serial_number, "RISK_PROFILE": "BEARING"}],
        "metadata": {
            "serial_number": serial_number,
            "user": "unknown",
            "request_id": None,
            "metadata_filters": metadata_filters or {},
            "input_filter_columns": {},
            "output_columns": {},
            "naksha_status": "mock",
            "table_status": "mock",
            "execution_time_ms": 1,
        },
    }


def test_prism_read_returns_records(client: TestClient, monkeypatch) -> None:
    async def _fake_read_prism_by_serial(**kwargs):
        serial_number = kwargs["serial_number"]
        metadata_filters = kwargs.get("metadata_filters") or {}
        return _mock_prism_success(serial_number=serial_number, metadata_filters=metadata_filters)

    monkeypatch.setattr(prism_route, "read_prism_by_serial", _fake_read_prism_by_serial)

    resp = client.post(
        "/dataservices/api/v1/prism/read",
        json={"serial_number": "ESN001"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert "data" in body
    assert "record_count" in body
    assert body["record_count"] == len(body["data"])


def test_prism_read_with_component(client: TestClient, monkeypatch) -> None:
    async def _fake_read_prism_by_serial(**kwargs):
        serial_number = kwargs["serial_number"]
        metadata_filters = kwargs.get("metadata_filters") or {}
        return _mock_prism_success(serial_number=serial_number, metadata_filters=metadata_filters)

    monkeypatch.setattr(prism_route, "read_prism_by_serial", _fake_read_prism_by_serial)

    resp = client.post(
        "/dataservices/api/v1/prism/read",
        json={"serial_number": "ESN001", "component": "BEARING"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["metadata"]["metadata_filters"]["component"] == "BEARING"


def test_prism_read_missing_serial_number(client: TestClient) -> None:
    resp = client.post("/dataservices/api/v1/prism/read", json={})
    assert resp.status_code == 422


def test_prism_read_response_metadata(client: TestClient, monkeypatch) -> None:
    async def _fake_read_prism_by_serial(**kwargs):
        serial_number = kwargs["serial_number"]
        metadata_filters = kwargs.get("metadata_filters") or {}
        return _mock_prism_success(serial_number=serial_number, metadata_filters=metadata_filters)

    monkeypatch.setattr(prism_route, "read_prism_by_serial", _fake_read_prism_by_serial)

    resp = client.post("/dataservices/api/v1/prism/read", json={"serial_number": "ESN001"})
    body = resp.json()
    assert "metadata" in body
    assert "naksha_status" in body["metadata"]
    assert "table_status" in body["metadata"]


def test_prism_system_error_is_generic_and_includes_request_id(client: TestClient, monkeypatch) -> None:
    async def _fake_read_prism_by_serial(**kwargs):
        raise prism_route.PrismServiceError(
            "SYSTEM_ERROR",
            "An internal error occurred",
            request_id="req-prism-500",
        )

    monkeypatch.setattr(prism_route, "read_prism_by_serial", _fake_read_prism_by_serial)

    resp = client.post(
        "/dataservices/api/v1/prism/read",
        json={"serial_number": "ESN001", "request_id": "req-prism-500"},
    )
    assert resp.status_code == 500
    detail = resp.json()["detail"]
    assert detail["message"] == "An internal error occurred"
    assert detail["request_id"] == "req-prism-500"
