"""Tests for IBAT routes."""

from fastapi.testclient import TestClient

from data_service.routes import ibat as ibat_route


def _mock_ibat_success(serial_number: str, request_id: str | None = None, metadata_filters: dict | None = None) -> dict:
    return {
        "status": "success",
        "record_count": 1,
        "data": [{"equip_serial_number": serial_number, "equipment_sys_id": "EQ123"}],
        "metadata": {
            "serial_number": serial_number,
            "user": "unknown",
            "request_id": request_id,
            "metadata_filters": metadata_filters or {},
            "input_filter_columns": {"equip_serial_number": ""},
            "output_columns": {"equip_serial_number": ""},
            "naksha_status": "mock",
            "table_status": "mock",
            "execution_time_ms": 1,
        },
    }


def test_ibat_returns_equipment(client: TestClient, monkeypatch) -> None:
    async def _fake_read_ibat_by_serial(**kwargs):
        return _mock_ibat_success(serial_number=kwargs["equip_serial_number"])

    monkeypatch.setattr(ibat_route, "read_ibat_by_serial", _fake_read_ibat_by_serial)

    resp = client.get("/dataservices/api/v1/ibat/equipment?serial_number=ESN001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["metadata"]["serial_number"] == "ESN001"
    assert "record_count" in body
    assert isinstance(body["data"], list)


def test_ibat_missing_serial_number(client: TestClient) -> None:
    resp = client.get("/dataservices/api/v1/ibat/equipment")
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert detail["error_code"] == "INVALID_INPUT"


def test_ibat_different_serial_number(client: TestClient) -> None:
    resp = client.get("/dataservices/api/v1/ibat/equipment?serial_number=ESN999")
    assert resp.status_code == 404
    detail = resp.json()["detail"]
    assert detail["error_code"] == "SERIAL_NOT_FOUND"
    assert "No records found for serial ESN999" in detail["message"]


def test_ibat_metadata_filters_are_accepted(client: TestClient, monkeypatch) -> None:
    async def _fake_read_ibat_by_serial(**kwargs):
        return _mock_ibat_success(
            serial_number=kwargs["equip_serial_number"],
            metadata_filters=kwargs.get("metadata_filters") or {},
        )

    monkeypatch.setattr(ibat_route, "read_ibat_by_serial", _fake_read_ibat_by_serial)

    resp = client.get(
        "/dataservices/api/v1/ibat/equipment?serial_number=ESN001&equipment_sys_id=EQ123&site_customer_name=acme&plant_name=alpha"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["metadata"]["metadata_filters"]["equipment_sys_id"] == "EQ123"
    assert body["metadata"]["metadata_filters"]["site_customer_name"] == "acme"
    assert body["metadata"]["metadata_filters"]["plant_name"] == "alpha"


def test_ibat_request_id_is_passed_through(client: TestClient, monkeypatch) -> None:
    async def _fake_read_ibat_by_serial(**kwargs):
        return _mock_ibat_success(
            serial_number=kwargs["equip_serial_number"],
            request_id=kwargs.get("request_id"),
        )

    monkeypatch.setattr(ibat_route, "read_ibat_by_serial", _fake_read_ibat_by_serial)

    resp = client.get("/dataservices/api/v1/ibat/equipment?serial_number=ESN001&request_id=req-ibat-001")
    assert resp.status_code == 200
    assert resp.json()["metadata"]["request_id"] == "req-ibat-001"


def test_ibat_health_endpoint(client: TestClient) -> None:
    resp = client.get("/dataservices/api/v1/ibat/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "ibat"}


def test_ibat_rate_limited_maps_to_429(client: TestClient, monkeypatch) -> None:
    async def _fake_read_ibat_by_serial(**kwargs):
        raise ibat_route.IbatServiceError("RATE_LIMITED", "IBAT upstream rate limited (429)")

    monkeypatch.setattr(ibat_route, "read_ibat_by_serial", _fake_read_ibat_by_serial)

    resp = client.get("/dataservices/api/v1/ibat/equipment?serial_number=ESN001")
    assert resp.status_code == 429
    detail = resp.json()["detail"]
    assert detail["error_code"] == "RATE_LIMITED"


def test_ibat_system_error_is_generic_and_includes_request_id(client: TestClient, monkeypatch) -> None:
    async def _fake_read_ibat_by_serial(**kwargs):
        raise ibat_route.IbatServiceError(
            "SYSTEM_ERROR",
            "An internal error occurred",
            request_id="req-ibat-500",
        )

    monkeypatch.setattr(ibat_route, "read_ibat_by_serial", _fake_read_ibat_by_serial)

    resp = client.get("/dataservices/api/v1/ibat/equipment?serial_number=ESN001&request_id=req-ibat-500")
    assert resp.status_code == 500
    detail = resp.json()["detail"]
    assert detail["message"] == "An internal error occurred"
    assert detail["request_id"] == "req-ibat-500"
