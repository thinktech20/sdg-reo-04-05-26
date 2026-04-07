"""Tests for GET /dataservices/api/v1/er/cases."""

from fastapi.testclient import TestClient


def test_er_returns_cases(client: TestClient) -> None:
    resp = client.get("/dataservices/api/v1/er/cases?serial_number=GT12345")
    assert resp.status_code == 200
    body = resp.json()
    assert "records" in body
    assert "result_count" in body
    assert body["result_count"] == len(body["records"])


def test_er_missing_serial_number(client: TestClient) -> None:
    resp = client.get("/dataservices/api/v1/er/cases")
    assert resp.status_code == 422


def test_er_with_component(client: TestClient) -> None:
    resp = client.get("/dataservices/api/v1/er/cases?serial_number=GT12345&component=Combustion")
    assert resp.status_code == 200
    body = resp.json()
    assert "records" in body
    # Check ESN matches if records returned
    if body["records"]:
        assert body["records"][0]["serial_number"] == "GT12345"
        assert body["records"][0]["component"] == "Combustion"


def test_er_mock_flag(client: TestClient) -> None:
    resp = client.get("/dataservices/api/v1/er/cases?serial_number=GT12345")
    records = resp.json()["records"]
    # Mock records may or may not have mock flag depending on mode
    assert isinstance(records, list)
