"""Tests for /health endpoint."""

from fastapi.testclient import TestClient


def test_health_ok(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "data-service"


def test_health_mode_is_mock(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.json()["mode"] == "mock"


def test_health_compat_dataservices_root(client: TestClient) -> None:
    resp = client.get("/dataservices/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_health_compat_dataservices_health(client: TestClient) -> None:
    resp = client.get("/dataservices/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
