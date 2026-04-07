"""Tests for the /dataservices/api/v1/units route."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from data_service.routes import units as units_route

SAMPLE_TRAINS = [
    {
        "id": "T-100",
        "trainName": "Alpha Train",
        "site": "Plant-A",
        "trainType": "Combined Cycle",
        "outageId": None,
        "outageType": None,
        "startDate": None,
        "endDate": None,
        "equipment": [
            {
                "serialNumber": "GT00001",
                "equipmentType": "Gas Turbine",
                "equipmentCode": "7FA.05",
                "model": "7FA",
                "site": None,
                "commercialOpDate": None,
                "totalEOH": None,
                "totalStarts": None,
                "coolingType": "Air-Cooled",
            },
        ],
    },
    {
        "id": "T-200",
        "trainName": "Beta Train",
        "site": "Plant-B",
        "trainType": "Simple Cycle",
        "outageId": None,
        "outageType": None,
        "startDate": None,
        "endDate": None,
        "equipment": [],
    },
]


def test_get_units_returns_all_trains(client: TestClient, monkeypatch) -> None:
    async def _fake_get_trains(**kwargs: Any) -> list[dict[str, Any]]:
        return list(SAMPLE_TRAINS)

    monkeypatch.setattr(units_route, "get_trains", _fake_get_trains)

    resp = client.get("/dataservices/api/v1/units")
    assert resp.status_code == 200
    body = resp.json()
    assert "units" in body
    assert len(body["units"]) == 2


def test_get_units_passes_search_to_service(client: TestClient, monkeypatch) -> None:
    captured_kwargs: dict[str, Any] = {}

    async def _fake_get_trains(**kwargs: Any) -> list[dict[str, Any]]:
        captured_kwargs.update(kwargs)
        return list(SAMPLE_TRAINS)

    monkeypatch.setattr(units_route, "get_trains", _fake_get_trains)

    resp = client.get("/dataservices/api/v1/units?search=alpha")
    assert resp.status_code == 200
    assert captured_kwargs["search"] == "alpha"


def test_get_units_passes_filter_type_to_service(client: TestClient, monkeypatch) -> None:
    captured_kwargs: dict[str, Any] = {}

    async def _fake_get_trains(**kwargs: Any) -> list[dict[str, Any]]:
        captured_kwargs.update(kwargs)
        return list(SAMPLE_TRAINS)

    monkeypatch.setattr(units_route, "get_trains", _fake_get_trains)

    resp = client.get("/dataservices/api/v1/units?filter_type=Major")
    assert resp.status_code == 200
    assert captured_kwargs["filter_type"] == "Major"


def test_get_units_default_params(client: TestClient, monkeypatch) -> None:
    captured_kwargs: dict[str, Any] = {}

    async def _fake_get_trains(**kwargs: Any) -> list[dict[str, Any]]:
        captured_kwargs.update(kwargs)
        return []

    monkeypatch.setattr(units_route, "get_trains", _fake_get_trains)

    resp = client.get("/dataservices/api/v1/units")
    assert resp.status_code == 200
    assert captured_kwargs["search"] == ""
    assert captured_kwargs["filter_type"] == "all"
    assert resp.json() == {"units": [], "page": 1, "page_size": 25}


def test_get_units_empty_result(client: TestClient, monkeypatch) -> None:
    async def _fake_get_trains(**kwargs: Any) -> list[dict[str, Any]]:
        return []

    monkeypatch.setattr(units_route, "get_trains", _fake_get_trains)

    resp = client.get("/dataservices/api/v1/units")
    assert resp.status_code == 200
    assert resp.json() == {"units": [], "page": 1, "page_size": 25}
