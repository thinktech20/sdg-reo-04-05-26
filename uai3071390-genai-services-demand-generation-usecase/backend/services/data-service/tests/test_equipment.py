"""
Unit tests:
  Units router     (routes/units.py)     — GET /dataservices/api/v1/units
  Equipment router (routes/equipment.py) — GET /dataservices/api/v1/equipment/search
                                           GET /dataservices/api/v1/equipment/{esn}/er-cases
                                           GET /dataservices/api/v1/equipment/{esn}/fsr-reports
                                           GET /dataservices/api/v1/equipment/{esn}/outage-history

  Direct tests for mock_services/equipment.py helper functions.

Domain model:
  Train     = outage grouping (trainName, site, outageType, equipment[]).
  Equipment = serialised component identified by serialNumber (ESN).
"""

from fastapi.testclient import TestClient

from data_service.mock_services.equipment import (
    _filter_by_date,
    get_all_trains,
    get_er_cases_by_esn,
    get_fsr_reports_by_esn,
    get_outage_history_by_esn,
    search_equipment_by_esn,
)
from data_service.routes.equipment import _equipment_error_response
from data_service.services.ibat_service import IbatServiceError

# ── GET /dataservices/api/v1/units ─────────────────────────────────────────────────────────────


class TestGetUnits:
    def test_returns_all_units(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/units")
        assert resp.status_code == 200
        data = resp.json()
        assert "units" in data
        assert len(data["units"]) == 4

    def test_response_schema(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/units")
        train = resp.json()["units"][0]
        assert "id" in train
        assert "trainName" in train
        assert "site" in train
        assert "outageType" in train
        assert "outageId" in train
        assert "equipment" in train
        assert isinstance(train["equipment"], list)

    def test_equipment_schema(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/units")
        eq = resp.json()["units"][0]["equipment"][0]
        assert "serialNumber" in eq
        assert "equipmentType" in eq
        assert "equipmentCode" in eq
        assert "totalEOH" in eq

    def test_filter_type_param_accepted(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/units?filter_type=Major")
        assert resp.status_code == 200
        assert "units" in resp.json()

    def test_filter_all_returns_everything(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/units?filter_type=all")
        assert len(resp.json()["units"]) == 4

    def test_search_param_accepted(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/units?search=train")
        assert resp.status_code == 200
        assert "units" in resp.json()

    def test_search_by_site(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/units?search=moss+landing")
        units = resp.json()["units"]
        assert len(units) >= 1
        assert any("Moss Landing" in u["site"] for u in units)

    def test_search_case_insensitive(self, client: TestClient):
        resp_upper = client.get("/dataservices/api/v1/units?search=MOSS+LANDING")
        resp_lower = client.get("/dataservices/api/v1/units?search=moss+landing")
        assert len(resp_upper.json()["units"]) == len(resp_lower.json()["units"])


# ── GET /dataservices/api/v1/equipment/search ──────────────────────────────────────────────────


class TestSearchEquipment:
    def test_finds_gas_turbine(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/equipment/search?esn=GT12345")
        assert resp.status_code == 200
        data = resp.json()
        assert "equipment" in data
        assert data["equipment"]["serialNumber"] == "GT12345"
        assert data["equipment"]["equipmentType"] == "Gas Turbine"

    def test_finds_generator(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/equipment/search?esn=92307")
        assert resp.status_code == 200
        eq = resp.json()["equipment"]
        assert eq["serialNumber"] == "92307"
        assert eq["equipmentType"] == "Generator"

    def test_equipment_schema(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/equipment/search?esn=GT12345")
        eq = resp.json()["equipment"]
        for field in (
            "serialNumber",
            "equipmentType",
            "equipmentCode",
            "model",
            "site",
            "commercialOpDate",
            "totalEOH",
            "totalStarts",
        ):
            assert field in eq, f"Missing field: {field}"

    def test_missing_esn_param_422(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/equipment/search")
        assert resp.status_code == 422

    def test_unknown_esn_404(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/equipment/search?esn=UNKNOWN_SERIAL")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


# ── _equipment_error_response helper ──────────────────────────────────────────


class TestEquipmentErrorResponse:
    def test_serial_not_found_maps_to_404(self):
        exc = IbatServiceError("SERIAL_NOT_FOUND", "Not found")
        http_exc = _equipment_error_response(exc)
        assert http_exc.status_code == 404

    def test_unauthorized_maps_to_403(self):
        exc = IbatServiceError("UNAUTHORIZED", "No access")
        http_exc = _equipment_error_response(exc)
        assert http_exc.status_code == 403

    def test_rate_limited_maps_to_429(self):
        exc = IbatServiceError("RATE_LIMITED", "Too many requests")
        http_exc = _equipment_error_response(exc)
        assert http_exc.status_code == 429

    def test_system_error_maps_to_500(self):
        exc = IbatServiceError("SYSTEM_ERROR", "Internal error")
        http_exc = _equipment_error_response(exc)
        assert http_exc.status_code == 500

    def test_unknown_code_defaults_to_400(self):
        exc = IbatServiceError("INVALID_INPUT", "Bad input")
        http_exc = _equipment_error_response(exc)
        assert http_exc.status_code == 400

    def test_includes_request_id_when_present(self):
        exc = IbatServiceError("SYSTEM_ERROR", "Error", request_id="req-123")
        http_exc = _equipment_error_response(exc)
        assert http_exc.detail["request_id"] == "req-123"

    def test_omits_request_id_when_none(self):
        exc = IbatServiceError("INVALID_INPUT", "Bad")
        http_exc = _equipment_error_response(exc)
        assert "request_id" not in http_exc.detail


# ── GET /dataservices/api/v1/equipment/{esn}/data-readiness ───────────────────────────────────


class TestDataReadiness:
    def test_returns_data_readiness(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/equipment/GT12345/data-readiness")
        assert resp.status_code == 200
        data = resp.json()
        assert data["esn"] == "GT12345"
        assert "dataSources" in data
        assert "totalAvailable" in data
        assert "totalSources" in data

    def test_data_readiness_with_date_range(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/equipment/GT12345/data-readiness?from_date=2024-01-01&to_date=2025-12-31")
        assert resp.status_code == 200
        data = resp.json()
        assert data["fromDate"] == "2024-01-01"
        assert data["toDate"] == "2025-12-31"


# ── GET /dataservices/api/v1/equipment/{esn}/er-cases ─────────────────────────────────────────


class TestERCases:
    def test_returns_er_cases_for_gt(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/equipment/GT12345/er-cases")
        assert resp.status_code == 200
        data = resp.json()
        assert "erCases" in data
        assert isinstance(data["erCases"], list)

    def test_returns_pagination_metadata(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/equipment/GT12345/er-cases")
        data = resp.json()
        assert data["page"] == 1
        assert data["pageSize"] == 20

    def test_custom_page_and_page_size(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/equipment/GT12345/er-cases?page=2&pageSize=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 2
        assert data["pageSize"] == 5

    def test_invalid_page_returns_422(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/equipment/GT12345/er-cases?page=0")
        assert resp.status_code == 422

    def test_page_size_exceeds_max_returns_422(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/equipment/GT12345/er-cases?pageSize=101")
        assert resp.status_code == 422

    def test_returns_er_cases_for_generator(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/equipment/92307/er-cases")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["erCases"], list)

    def test_response_schema(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/equipment/GT12345/er-cases")
        cases = resp.json()["erCases"]
        if cases:
            case = cases[0]
            assert "erNumber" in case

    def test_unknown_esn_returns_empty_list(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/equipment/UNKNOWN/er-cases")
        assert resp.status_code == 200
        assert resp.json()["erCases"] == []


# ── GET /dataservices/api/v1/equipment/{esn}/fsr-reports ──────────────────────────────────────


class TestFSRReports:
    def test_returns_fsr_reports(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/equipment/GT12345/fsr-reports")
        assert resp.status_code == 200
        data = resp.json()
        assert "fsrReports" in data
        assert isinstance(data["fsrReports"], list)

    def test_returns_pagination_metadata(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/equipment/GT12345/fsr-reports")
        data = resp.json()
        assert data["page"] == 1
        assert data["pageSize"] == 20

    def test_custom_page_and_page_size(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/equipment/GT12345/fsr-reports?page=3&pageSize=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 3
        assert data["pageSize"] == 10

    def test_invalid_page_returns_422(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/equipment/GT12345/fsr-reports?page=-1")
        assert resp.status_code == 422

    def test_response_schema(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/equipment/92307/fsr-reports")
        reports = resp.json()["fsrReports"]
        if reports:
            report = reports[0]
            for field in ("reportId", "title", "outageDate", "findings", "outageSummary"):
                assert field in report, f"Missing field: {field}"

    def test_unknown_esn_returns_empty_list(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/equipment/UNKNOWN/fsr-reports")
        assert resp.status_code == 200
        assert resp.json()["fsrReports"] == []


# ── GET /dataservices/api/v1/equipment/{esn}/outage-history ───────────────────────────────────


class TestOutageHistory:
    def test_returns_outage_history(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/equipment/GT12345/outage-history")
        assert resp.status_code == 200
        data = resp.json()
        assert "outageHistory" in data
        assert isinstance(data["outageHistory"], list)

    def test_returns_pagination_metadata(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/equipment/GT12345/outage-history")
        data = resp.json()
        assert data["page"] == 1
        assert data["pageSize"] == 20

    def test_custom_page_and_page_size(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/equipment/GT12345/outage-history?page=2&pageSize=15")
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 2
        assert data["pageSize"] == 15

    def test_invalid_page_returns_422(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/equipment/GT12345/outage-history?page=0")
        assert resp.status_code == 422

    def test_page_size_exceeds_max_returns_422(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/equipment/GT12345/outage-history?pageSize=200")
        assert resp.status_code == 422

    def test_response_schema(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/equipment/GT12345/outage-history")
        events = resp.json()["outageHistory"]
        if events:
            event = events[0]
            for field in ("outageId", "outageType", "startDate"):
                assert field in event, f"Missing field: {field}"

    def test_unknown_esn_returns_empty_list(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/equipment/UNKNOWN/outage-history")
        assert resp.status_code == 200
        assert resp.json()["outageHistory"] == []


# ── Direct tests for mock_services/equipment.py helper functions ──────────────


class TestMockGetAllTrains:
    def test_returns_all_trains(self):
        trains = get_all_trains()
        assert isinstance(trains, list)
        assert len(trains) == 4

    def test_train_has_equipment(self):
        trains = get_all_trains()
        for train in trains:
            assert "equipment" in train
            assert isinstance(train["equipment"], list)
            assert len(train["equipment"]) >= 1


class TestMockSearchEquipmentByEsn:
    def test_finds_known_esn(self):
        eq = search_equipment_by_esn("GT12345")
        assert eq is not None
        assert eq["serialNumber"] == "GT12345"

    def test_finds_esn_case_insensitive(self):
        eq = search_equipment_by_esn("gt12345")
        assert eq is not None
        assert eq["serialNumber"] == "GT12345"

    def test_returns_none_for_unknown(self):
        assert search_equipment_by_esn("DOES_NOT_EXIST") is None


# ── Direct tests for _filter_by_date and keyed mock helpers ───────────────────


class TestFilterByDate:
    def test_no_dates_returns_all(self):
        items = [{"d": "2024-01-01"}, {"d": "2024-06-01"}]
        assert _filter_by_date(items, "d", None, None) is items

    def test_start_date_filters(self):
        items = [{"d": "2024-01-01"}, {"d": "2024-06-01"}, {"d": "2024-12-01"}]
        result = _filter_by_date(items, "d", "2024-05-01", None)
        assert len(result) == 2

    def test_end_date_filters(self):
        items = [{"d": "2024-01-01"}, {"d": "2024-06-01"}, {"d": "2024-12-01"}]
        result = _filter_by_date(items, "d", None, "2024-07-01")
        assert len(result) == 2

    def test_both_dates_filter(self):
        items = [{"d": "2024-01-01"}, {"d": "2024-06-01"}, {"d": "2024-12-01"}]
        result = _filter_by_date(items, "d", "2024-02-01", "2024-07-01")
        assert len(result) == 1

    def test_missing_field_treated_as_empty_string(self):
        items = [{"other": "x"}]
        result = _filter_by_date(items, "d", "2024-01-01", None)
        assert result == []


class TestGetERCasesByEsn:
    def test_returns_cases_for_known_esn(self):
        cases = get_er_cases_by_esn("GT12345")
        assert len(cases) >= 1

    def test_case_insensitive_lookup(self):
        cases = get_er_cases_by_esn("gt12345")
        assert len(cases) >= 1

    def test_unknown_esn_returns_empty(self):
        assert get_er_cases_by_esn("NOPE") == []

    def test_date_filtering(self):
        cases = get_er_cases_by_esn("GT12345", start_date="2024-10-01")
        assert all(c["dateOpened"] >= "2024-10-01" for c in cases)


class TestGetFSRReportsByEsn:
    def test_returns_reports_for_known_esn(self):
        reports = get_fsr_reports_by_esn("GT12345")
        assert len(reports) >= 1

    def test_unknown_esn_returns_empty(self):
        assert get_fsr_reports_by_esn("NOPE") == []

    def test_date_filtering(self):
        reports = get_fsr_reports_by_esn("GT12345", end_date="2022-01-01")
        assert reports == []


class TestGetOutageHistoryByEsn:
    def test_returns_history_for_known_esn(self):
        history = get_outage_history_by_esn("GT12345")
        assert len(history) >= 1

    def test_unknown_esn_returns_empty(self):
        assert get_outage_history_by_esn("NOPE") == []

    def test_date_filtering(self):
        history = get_outage_history_by_esn("GT12345", start_date="2022-01-01")
        # startDate field is present in outage history mock data
        assert isinstance(history, list)
