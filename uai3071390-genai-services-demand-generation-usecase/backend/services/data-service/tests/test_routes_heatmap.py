"""Tests for GET /dataservices/api/v1/heatmap/load."""

from fastapi.testclient import TestClient

from data_service.routes import heatmap as heatmap_route


def _mock_heatmap_success(
    equipment_type: str = "GEN",
    persona: str = "REL",
    component: str | None = None,
) -> dict:
    return {
        "status": "success",
        "record_count": 1,
        "data": [
            {
                "equipment_type": equipment_type,
                "persona": persona,
                "component": component or "STATOR",
                "issue_prompt": "Check winding",
            }
        ],
        "metadata": {
            "equipment_type": equipment_type,
            "persona": persona,
            "component": component,
            "user": "unknown",
            "request_id": None,
            "input_filter_columns": {},
            "output_columns": {},
            "naksha_status": "mock",
            "table_status": "mock",
            "execution_time_ms": 1,
        },
    }


def test_heatmap_returns_data(client: TestClient, monkeypatch) -> None:
    async def _fake(**kwargs):
        return _mock_heatmap_success(
            equipment_type=kwargs["equipment_type"],
            persona=kwargs["persona"],
        )

    monkeypatch.setattr(heatmap_route, "read_heatmap", _fake)

    resp = client.get("/dataservices/api/v1/heatmap/load?equipment_type=GEN&persona=REL")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["record_count"] == 1
    assert isinstance(body["data"], list)


def test_heatmap_requires_equipment_type(client: TestClient) -> None:
    resp = client.get("/dataservices/api/v1/heatmap/load?persona=REL")

    assert resp.status_code == 400
    assert resp.json()["detail"]["message"] == "equipment_type is required"


def test_heatmap_requires_persona(client: TestClient) -> None:
    resp = client.get("/dataservices/api/v1/heatmap/load?equipment_type=GEN")

    assert resp.status_code == 400
    assert resp.json()["detail"]["message"] == "persona is required"


def test_heatmap_passes_component(client: TestClient, monkeypatch) -> None:
    captured: dict = {}

    async def _fake(**kwargs):
        captured.update(kwargs)
        return _mock_heatmap_success(component=kwargs.get("metadata_filters", {}).get("component"))

    monkeypatch.setattr(heatmap_route, "read_heatmap", _fake)

    resp = client.get("/dataservices/api/v1/heatmap/load?equipment_type=GT&persona=OE&component=STATOR")
    assert resp.status_code == 200
    assert captured["persona"] == "OE"
    assert captured["metadata_filters"]["component"] == "STATOR"


def test_heatmap_passes_serial_number_context(client: TestClient, monkeypatch) -> None:
    captured: dict = {}

    async def _fake(**kwargs):
        captured.update(kwargs)
        return _mock_heatmap_success()

    monkeypatch.setattr(heatmap_route, "read_heatmap", _fake)

    resp = client.get("/dataservices/api/v1/heatmap/load?equipment_type=GEN&persona=REL&serial_number=270T484")
    assert resp.status_code == 200
    assert captured["serial_number"] == "270T484"


def test_heatmap_invalid_equipment_type_returns_400(client: TestClient, monkeypatch) -> None:
    async def _fake(**kwargs):
        raise heatmap_route.HeatmapServiceError("INVALID_INPUT", "equipment_type must be GEN or GT")

    monkeypatch.setattr(heatmap_route, "read_heatmap", _fake)

    resp = client.get("/dataservices/api/v1/heatmap/load?equipment_type=INVALID&persona=REL")
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert detail["error_code"] == "INVALID_INPUT"


def test_heatmap_no_data_returns_404(client: TestClient, monkeypatch) -> None:
    async def _fake(**kwargs):
        raise heatmap_route.HeatmapServiceError("NO_DATA", "No risk-matrix rows")

    monkeypatch.setattr(heatmap_route, "read_heatmap", _fake)

    resp = client.get("/dataservices/api/v1/heatmap/load?equipment_type=GEN&persona=REL")
    assert resp.status_code == 404


def test_heatmap_rate_limited_returns_429(client: TestClient, monkeypatch) -> None:
    async def _fake(**kwargs):
        raise heatmap_route.HeatmapServiceError("RATE_LIMITED", "upstream rate limited")

    monkeypatch.setattr(heatmap_route, "read_heatmap", _fake)

    resp = client.get("/dataservices/api/v1/heatmap/load?equipment_type=GEN&persona=REL")
    assert resp.status_code == 429


def test_heatmap_system_error_returns_500(client: TestClient, monkeypatch) -> None:
    async def _fake(**kwargs):
        raise heatmap_route.HeatmapServiceError("SYSTEM_ERROR", "An internal error occurred")

    monkeypatch.setattr(heatmap_route, "read_heatmap", _fake)

    resp = client.get("/dataservices/api/v1/heatmap/load?equipment_type=GEN&persona=REL")
    assert resp.status_code == 500


def test_heatmap_health_endpoint(client: TestClient) -> None:
    resp = client.get("/dataservices/api/v1/heatmap/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "heatmap"}
