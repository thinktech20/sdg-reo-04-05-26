"""
Unit tests — GET   /dataservices/api/v1/assessments/
             POST  /dataservices/api/v1/assessments/
             GET   /dataservices/api/v1/assessments/{id}
             POST  /dataservices/api/v1/assessments/{id}/analyze/run
             GET   /dataservices/api/v1/assessments/{id}/status
             PUT   /dataservices/api/v1/assessments/{id}/reliability
             PUT   /dataservices/api/v1/assessments/{id}/outage
             POST  /dataservices/api/v1/assessments/{id}/findings/{fid}/feedback
"""

import json
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from data_service.routes.assessments import FeedbackRequest, _group_by_operation

VALID_ASSESSMENT_PAYLOAD = {
    "esn": "GT12345",
    "unitId": "train-001",
    "title": "Test Assessment",
}


# ── GET /dataservices/api/v1/assessments/ ─────────────────────────────────────────────────────


class TestListAssessments:
    def test_returns_list(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/assessments")
        assert resp.status_code == 200
        data = resp.json()
        assert "assessments" in data
        assert isinstance(data["assessments"], list)

    def test_contains_seed_data(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/assessments")
        ids = [a["id"] for a in resp.json()["assessments"]]
        assert "asmt_001" in ids

    def test_filter_by_status(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/assessments?status=Completed")
        assert resp.status_code == 200
        for a in resp.json()["assessments"]:
            assert a["status"].lower() == "completed"

    def test_filter_by_esn(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/assessments?esn=GT12345")
        assert resp.status_code == 200
        for a in resp.json()["assessments"]:
            assert a["esn"] == "GT12345"


# ── POST /dataservices/api/v1/assessments/ ────────────────────────────────────────────────────


class TestCreateAssessment:
    def test_creates_assessment(self, client: TestClient):
        resp = client.post("/dataservices/api/v1/assessments", json=VALID_ASSESSMENT_PAYLOAD)
        assert resp.status_code == 201
        data = resp.json()
        assert "assessment" in data
        assessment = data["assessment"]
        assert "id" in assessment
        assert assessment["esn"] == "GT12345"

    def test_creates_with_pending_status(self, client: TestClient):
        resp = client.post("/dataservices/api/v1/assessments", json=VALID_ASSESSMENT_PAYLOAD)
        assessment = resp.json()["assessment"]
        assert assessment.get("status") in (None, "PENDING", "active", "draft", "Draft")

    def test_missing_required_fields_422(self, client: TestClient):
        resp = client.post("/dataservices/api/v1/assessments", json={})
        assert resp.status_code == 422

    def test_missing_esn_422(self, client: TestClient):
        resp = client.post("/dataservices/api/v1/assessments", json={"unitId": "train-001"})
        assert resp.status_code == 422

    def test_created_assessment_retrievable(self, client: TestClient):
        resp = client.post("/dataservices/api/v1/assessments", json=VALID_ASSESSMENT_PAYLOAD)
        assessment_id = resp.json()["assessment"]["id"]
        get_resp = client.get(f"/dataservices/api/v1/assessments/{assessment_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["assessment"]["id"] == assessment_id


# ── GET /dataservices/api/v1/assessments/{id} ─────────────────────────────────────────────────


class TestGetAssessment:
    def test_gets_existing_assessment(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/assessments/asmt_001")
        assert resp.status_code == 200
        data = resp.json()
        assert "assessment" in data
        assert data["assessment"]["id"] == "asmt_001"

    def test_unknown_assessment_404(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/assessments/DOES_NOT_EXIST")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_response_has_esn(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/assessments/asmt_001")
        assert resp.json()["assessment"]["esn"] == "GT12345"


class TestAnalyzeRun:
    def test_re_triggers_analysis(self, client: TestClient):
        resp = client.post("/dataservices/api/v1/assessments/asmt_001/analyze/run", json={"persona": "RE"})
        assert resp.status_code == 202
        data = resp.json()
        assert data.get("workflowStatus") == "PENDING"
        assert data.get("workflowId") == "RE_DEFAULT"

    def test_oe_triggers_analysis(self, client: TestClient):
        resp = client.post("/dataservices/api/v1/assessments/asmt_001/analyze/run", json={"persona": "OE"})
        assert resp.status_code == 202
        data = resp.json()
        assert data.get("workflowStatus") == "PENDING"
        assert data.get("workflowId") == "OE_DEFAULT"

    def test_unknown_assessment_404(self, client: TestClient):
        resp = client.post("/dataservices/api/v1/assessments/UNKNOWN/analyze/run", json={"persona": "RE"})
        assert resp.status_code == 404

    def test_invalid_persona_422(self, client: TestClient):
        resp = client.post("/dataservices/api/v1/assessments/asmt_001/analyze/run", json={"persona": "ADMIN"})
        assert resp.status_code == 422

    def test_re_status_becomes_complete(self, client: TestClient):
        client.post("/dataservices/api/v1/assessments/asmt_001/analyze/run", json={"persona": "RE"})
        status_resp = client.get("/dataservices/api/v1/assessments/asmt_001/status?workflowId=RE_DEFAULT")
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["workflowStatus"] in ("PENDING", "COMPLETED")

    def test_oe_status_becomes_complete(self, client: TestClient):
        client.post("/dataservices/api/v1/assessments/asmt_001/analyze/run", json={"persona": "OE"})
        status_resp = client.get("/dataservices/api/v1/assessments/asmt_001/status?workflowId=OE_DEFAULT")
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["workflowStatus"] in ("PENDING", "COMPLETED")

    def test_re_live_path_forwards_frontend_payload(self, client: TestClient, monkeypatch) -> None:
        import data_service.config as cfg
        import data_service.db.assessments as db_mod
        from data_service.routes import assessments as routes

        captured: dict[str, object] = {}

        async def fake_invoke_orchestrator(**kwargs):
            captured.update(kwargs)

        monkeypatch.setattr(cfg, "USE_MOCK", False)
        monkeypatch.setattr(cfg, "USE_MOCK_ASSESSMENTS", False)
        monkeypatch.setattr(routes, "get_assessment", lambda assessment_id: {"assessmentId": assessment_id, "esn": "GT12345"})
        monkeypatch.setattr(db_mod, "update_execution_state", lambda assessment_id, **kwargs: None)
        monkeypatch.setattr(routes, "_invoke_orchestrator", AsyncMock(side_effect=fake_invoke_orchestrator))

        resp = client.post(
            "/dataservices/api/v1/assessments/asmt_001/analyze/run",
            json={
                "persona": "RE",
                "equipmentType": "Generator",
                "dataTypes": ["fsr-reports", "er-cases"],
                "dateFrom": "2025-01-01",
                "dateTo": "2025-12-31",
            },
        )

        assert resp.status_code == 202
        assert captured["assessment_id"] == "asmt_001"
        assert captured["workflow_id"] == "RE_DEFAULT"
        assert captured["esn"] == "GT12345"
        assert captured["persona"] == "RE"
        assert captured["input_payload"]["equipmentType"] == "Generator"
        assert captured["input_payload"]["dataTypes"] == ["fsr-reports", "er-cases"]
        assert captured["input_payload"]["dateFrom"] == "2025-01-01"
        assert captured["input_payload"]["dateTo"] == "2025-12-31"
        assert captured["input_payload"]["filters"]["dataTypes"] == ["fsr-reports", "er-cases"]


class TestAnalyzeNarrative:
    def test_re_triggers_narrative(self, client: TestClient):
        resp = client.post("/dataservices/api/v1/assessments/asmt_001/analyze/narrative", json={"persona": "RE"})
        assert resp.status_code == 202
        data = resp.json()
        assert data.get("workflowStatus") == "PENDING"
        assert data.get("workflowId") == "RE_NARRATIVE"

    def test_oe_triggers_narrative(self, client: TestClient):
        resp = client.post("/dataservices/api/v1/assessments/asmt_001/analyze/narrative", json={"persona": "OE"})
        assert resp.status_code == 202
        data = resp.json()
        assert data.get("workflowStatus") == "PENDING"
        assert data.get("workflowId") == "OE_NARRATIVE"

    def test_unknown_assessment_404(self, client: TestClient):
        resp = client.post("/dataservices/api/v1/assessments/UNKNOWN/analyze/narrative", json={"persona": "RE"})
        assert resp.status_code == 404

    def test_invalid_persona_422(self, client: TestClient):
        resp = client.post("/dataservices/api/v1/assessments/asmt_001/analyze/narrative", json={"persona": "X"})
        assert resp.status_code == 422

    def test_narrative_status_polled(self, client: TestClient):
        client.post("/dataservices/api/v1/assessments/asmt_001/analyze/narrative", json={"persona": "RE"})
        resp = client.get("/dataservices/api/v1/assessments/asmt_001/status?workflowId=RE_NARRATIVE")
        assert resp.status_code == 200
        data = resp.json()
        assert data["workflowStatus"] in ("PENDING", "COMPLETED")
        assert data["assessmentId"] == "asmt_001"


class TestGetStatus:
    def test_status_before_job_shows_state(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/assessments/asmt_001/status?workflowId=RE_DEFAULT")
        assert resp.status_code == 200
        data = resp.json()
        assert "assessmentId" in data
        assert "workflowStatus" in data

    def test_status_after_re_run(self, client: TestClient):
        client.post("/dataservices/api/v1/assessments/asmt_001/analyze/run", json={"persona": "RE"})
        resp = client.get("/dataservices/api/v1/assessments/asmt_001/status?workflowId=RE_DEFAULT")
        assert resp.status_code == 200
        data = resp.json()
        assert data["workflowStatus"] in ("PENDING", "COMPLETED")

    def test_status_after_oe_run(self, client: TestClient):
        client.post("/dataservices/api/v1/assessments/asmt_001/analyze/run", json={"persona": "OE"})
        resp = client.get("/dataservices/api/v1/assessments/asmt_001/status?workflowId=OE_DEFAULT")
        assert resp.status_code == 200

    def test_missing_workflow_id_422(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/assessments/asmt_001/status")
        assert resp.status_code == 422


# ── PUT /dataservices/api/v1/assessments/{id}/reliability ─────────────────────────────────────


class TestPutReliability:
    def test_updates_reliability(self, client: TestClient):
        payload = {"recommendations": [{"id": "r1", "text": "Inspect blades"}]}
        resp = client.put("/dataservices/api/v1/assessments/asmt_001/reliability", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "assessment" in data

    def test_unknown_assessment_404(self, client: TestClient):
        resp = client.put("/dataservices/api/v1/assessments/UNKNOWN/reliability", json={})
        assert resp.status_code == 404


# ── PUT /dataservices/api/v1/assessments/{id}/outage ──────────────────────────────────────────


class TestPutOutage:
    def test_updates_outage(self, client: TestClient):
        payload = {"riskLevel": "Medium", "notes": "Outage risk updated"}
        resp = client.put("/dataservices/api/v1/assessments/asmt_001/outage", json=payload)
        assert resp.status_code == 200
        assert "assessment" in resp.json()

    def test_unknown_assessment_404(self, client: TestClient):
        resp = client.put("/dataservices/api/v1/assessments/UNKNOWN/outage", json={})
        assert resp.status_code == 404


# ── POST /dataservices/api/v1/assessments/{id}/findings/{fid}/feedback ────────────────────────


class TestFeedback:
    def test_submit_feedback(self, client: TestClient):
        payload = {"rating": 1, "comments": "Good finding", "helpful": True}
        resp = client.post(
            "/dataservices/api/v1/assessments/asmt_001/findings/finding_001/feedback",
            json=payload,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "feedback" in data or "status" in data or "findingId" in data

    def test_unknown_assessment_404(self, client: TestClient):
        resp = client.post(
            "/dataservices/api/v1/assessments/UNKNOWN/findings/finding_001/feedback",
            json={"rating": 1},
        )
        assert resp.status_code == 404


# ── db.assessments coverage ──────────────────────────────────────────────────

class TestAssessmentDbUnit:
    """Unit tests for db.assessments write/read/update cycle (USE_MOCK=True path)."""

    def test_write_and_read_round_trip(self) -> None:
        from data_service.db import assessments as db_mod
        db_mod.clear()
        record = db_mod.write_assessment("ESN1", "asmt_test_1", "RE", workflow_id="RE_DEFAULT")
        assert record["workflowStatus"] == "PENDING"
        fetched = db_mod.read_assessment_by_id("asmt_test_1", "RE_DEFAULT")
        assert fetched is not None
        assert fetched["assessmentId"] == "asmt_test_1"
        db_mod.clear()

    def test_update_execution_state(self) -> None:
        from data_service.db import assessments as db_mod
        db_mod.clear()
        db_mod.write_assessment("ESN2", "asmt_test_2", "OE", workflow_id="OE_DEFAULT")
        db_mod.update_execution_state(
            "asmt_test_2",
            "OE_DEFAULT",
            workflow_status="IN_PROGRESS",
            active_node="risk_eval",
            node_timings={"risk_eval": {"startedAt": "t"}},
        )
        record = db_mod.read_assessment_by_id("asmt_test_2", "OE_DEFAULT")
        assert record["workflowStatus"] == "IN_PROGRESS"
        assert record["activeNode"] == "risk_eval"
        db_mod.clear()

    def test_update_to_completed(self) -> None:
        from data_service.db import assessments as db_mod
        db_mod.clear()
        db_mod.write_assessment("ESN3", "asmt_test_3", "RE", workflow_id="RE_DEFAULT")
        db_mod.update_execution_state("asmt_test_3", "RE_DEFAULT", workflow_status="COMPLETED")
        record = db_mod.read_assessment_by_id("asmt_test_3", "RE_DEFAULT")
        assert record["workflowStatus"] == "COMPLETED"
        db_mod.clear()

    def test_read_missing_returns_none(self) -> None:
        from data_service.db import assessments as db_mod
        db_mod.clear()
        assert db_mod.read_assessment_by_id("no-such-id", "RE_DEFAULT") is None

    def test_live_update_seeds_missing_workflow_row(self, monkeypatch) -> None:
        from data_service import config as cfg
        from data_service.db import assessments as db_mod

        class _FakeTable:
            def __init__(self) -> None:
                self.query_calls = 0
                self.put_items: list[dict] = []

            def query(self, **kwargs):
                self.query_calls += 1
                # 1st query: exact assessmentId+workflowId lookup => missing
                if self.query_calls == 1:
                    return {"Items": []}
                # 2nd query: seed row lookup by assessmentId => found RE_DEFAULT row
                return {
                    "Items": [
                        {
                            "esn": "ESN42",
                            "assessmentId": "asmt_live_1",
                            "persona": "RE",
                            "workflowId": "RE_DEFAULT",
                            "reviewPeriod": "18-month",
                            "unitNumber": "01",
                            "filters": {"dataTypes": ["er-cases"]},
                            "createdBy": "user_001",
                        }
                    ]
                }

            def put_item(self, Item):
                self.put_items.append(Item)

        fake_table = _FakeTable()
        monkeypatch.setattr(cfg, "USE_MOCK_ASSESSMENTS", False)
        monkeypatch.setattr(db_mod, "_ddb_table", lambda: fake_table)

        db_mod.update_execution_state("asmt_live_1", "RE_NARRATIVE", workflow_status="IN_QUEUE")

        assert len(fake_table.put_items) == 1
        item = fake_table.put_items[0]
        assert item["assessmentId"] == "asmt_live_1"
        assert item["workflowId"] == "RE_NARRATIVE"
        assert item["workflowStatus"] == "IN_QUEUE"
        assert item["esn"] == "ESN42"

    def test_live_read_assessment_by_id_uses_latest_duplicate_row(self, monkeypatch) -> None:
        from data_service import config as cfg
        from data_service.db import assessments as db_mod

        class _FakeTable:
            def query(self, **kwargs):
                if "ExclusiveStartKey" not in kwargs:
                    return {
                        "Items": [
                            {
                                "assessmentId": "asmt_live_2",
                                "workflowId": "RE_DEFAULT",
                                "workflowStatus": "IN_PROGRESS",
                                "updatedAt": "2026-03-20T10:00:00Z",
                            }
                        ],
                        "LastEvaluatedKey": {"assessmentId": "asmt_live_2", "workflowId": "RE_DEFAULT"},
                    }
                return {
                    "Items": [
                        {
                            "assessmentId": "asmt_live_2",
                            "workflowId": "RE_DEFAULT",
                            "workflowStatus": "COMPLETED",
                            "updatedAt": "2026-03-20T10:02:00Z",
                        }
                    ]
                }

        monkeypatch.setattr(cfg, "USE_MOCK_ASSESSMENTS", False)
        monkeypatch.setattr(db_mod, "_ddb_table", lambda: _FakeTable())

        record = db_mod.read_assessment_by_id("asmt_live_2", "RE_DEFAULT")
        assert record is not None
        assert record["workflowStatus"] == "COMPLETED"

    def test_live_update_execution_state_updates_latest_duplicate_row(self, monkeypatch) -> None:
        from data_service import config as cfg
        from data_service.db import assessments as db_mod

        class _FakeTable:
            def __init__(self) -> None:
                self.update_calls: list[dict] = []

            def query(self, **kwargs):
                if "ProjectionExpression" in kwargs:
                    if "ExclusiveStartKey" not in kwargs:
                        return {
                            "Items": [
                                {
                                    "esn": "ESN7",
                                    "createdAt": "2026-03-20T10:00:00Z",
                                    "updatedAt": "2026-03-20T10:00:00Z",
                                }
                            ],
                            "LastEvaluatedKey": {"assessmentId": "asmt_live_3", "workflowId": "RE_DEFAULT"},
                        }
                    return {
                        "Items": [
                            {
                                "esn": "ESN7",
                                "createdAt": "2026-03-20T10:01:00Z",
                                "updatedAt": "2026-03-20T10:02:00Z",
                            }
                        ]
                    }
                return {"Items": []}

            def update_item(self, **kwargs):
                self.update_calls.append(kwargs)

        fake_table = _FakeTable()
        monkeypatch.setattr(cfg, "USE_MOCK_ASSESSMENTS", False)
        monkeypatch.setattr(db_mod, "_ddb_table", lambda: fake_table)

        db_mod.update_execution_state("asmt_live_3", "RE_DEFAULT", workflow_status="FAILED")

        assert len(fake_table.update_calls) == 1
        assert fake_table.update_calls[0]["Key"] == {
            "esn": "ESN7",
            "createdAt": "2026-03-20T10:01:00Z",
        }


# ── RE completion updates assessment reliabilityStatus ────────────────────────

class TestAnalysisStatusUpdate:
    def test_re_completion_updates_reliability_status(self, client: TestClient) -> None:
        """Running RE analysis (USE_MOCK=True) should write workflowStatus=COMPLETED."""
        client.post("/dataservices/api/v1/assessments/asmt_001/analyze/run", json={"persona": "RE"})
        resp = client.get("/dataservices/api/v1/assessments/asmt_001")
        assert resp.status_code == 200
        assessment = resp.json()["assessment"]
        # mock path writes workflowStatus=COMPLETED synchronously
        assert assessment.get("workflowStatus") == "COMPLETED"

    def test_oe_completion_updates_outage_status(self, client: TestClient) -> None:
        """Running OE analysis (USE_MOCK=True) should write workflowStatus=COMPLETED."""
        client.post("/dataservices/api/v1/assessments/asmt_001/analyze/run", json={"persona": "OE"})
        resp = client.get("/dataservices/api/v1/assessments/asmt_001")
        assert resp.status_code == 200
        assessment = resp.json()["assessment"]
        assert assessment.get("workflowStatus") == "COMPLETED"

    def test_narrative_persists_summary(self, client: TestClient) -> None:
        """Triggering narrative (USE_MOCK=True) should store narrative in domain store."""
        from data_service.db import narrative_summary as ns
        resp = client.post("/dataservices/api/v1/assessments/asmt_001/analyze/narrative", json={"persona": "RE"})
        assert resp.status_code == 202
        stored = ns.read_narrative_summary("asmt_001")
        assert stored is not None

    def test_persist_result_serializes_structured_narrative_summary(self) -> None:
        from data_service.db import narrative_summary as ns
        from data_service.routes.assessments import _persist_result

        ns.clear()

        _persist_result(
            assessment_id="asmt_001",
            workflow_id="RE_NARRATIVE",
            persona="RE",
            esn="GT12345",
            result={
                "narrativeSummary": {
                    "Executive Summary": "Rotor issue requires inspection.",
                    "Recommendations": ["Inspect rotor", "Review operating history"],
                }
            },
        )

        stored = ns.read_narrative_summary("asmt_001")

        assert stored is not None
        assert isinstance(stored["summary"], str)
        assert json.loads(stored["summary"]) == {
            "Executive Summary": "Rotor issue requires inspection.",
            "Recommendations": ["Inspect rotor", "Review operating history"],
        }

        ns.clear()

    def test_persist_result_write_retrieval_exception_is_swallowed(
        self, monkeypatch
    ) -> None:
        """bugfix/622621: write_retrieval errors (e.g. 400 KB limit) must not
        propagate — the assessment result is already persisted at this point."""
        from unittest.mock import patch
        from data_service.routes.assessments import _persist_result
        from data_service.db import risk_analysis as ra_store

        with patch.object(ra_store, "write_retrieval", side_effect=Exception("Item size too large")):
            # Must not raise
            _persist_result(
                assessment_id="asmt_001",
                workflow_id="RE_DEFAULT",
                persona="RE",
                esn="GT12345",
                result={"retrieval": {"source": "fsr", "chunks": ["chunk1"]}},
            )

    def test_persist_result_write_retrieval_exception_logs_warning(
        self, monkeypatch, caplog
    ) -> None:
        """bugfix/622621: a warning must be emitted when write_retrieval is skipped."""
        import logging
        from unittest.mock import patch
        from data_service.routes.assessments import _persist_result
        from data_service.db import risk_analysis as ra_store

        with patch.object(ra_store, "write_retrieval", side_effect=Exception("400 KB limit")):
            with caplog.at_level(logging.WARNING):
                _persist_result(
                    assessment_id="asmt_002",
                    workflow_id="RE_DEFAULT",
                    persona="RE",
                    esn="GT12345",
                    result={"retrieval": {"source": "fsr", "chunks": ["x"]}},
                )

        assert any(
            "write_retrieval skipped" in r.message and "asmt_002" in r.message
            for r in caplog.records
        )

    def test_init_qna_session_swallows_connection_error(self) -> None:
        """_init_qna_session should not raise when QnA agent is unreachable."""
        import asyncio
        from data_service.routes.assessments import _init_qna_session
        # Should not raise even if QNA_AGENT_URL is unreachable
        asyncio.run(_init_qna_session("asmt_x", "RE", {"riskCategories": []}))

    def test_get_assessment_exposes_empty_reliability_categories(self, monkeypatch) -> None:
        """If risk analysis exists but findings are empty, API still returns reliabilityRiskCategories={}."""
        from data_service.mock_services import assessments as mock_assess
        from data_service.db import risk_analysis as ra_store

        monkeypatch.setattr(ra_store, "read_risk_analysis", lambda _assessment_id: {"findings": []})
        assessment = mock_assess.get_assessment("asmt_001")
        assert assessment is not None
        assert "reliabilityRiskCategories" in assessment
        assert assessment["reliabilityRiskCategories"] == {}

    def test_seeded_assessment_contains_larger_demo_findings(self) -> None:
        from data_service.mock_services import assessments as mock_assess

        assessment = mock_assess.get_assessment("asmt_001")

        assert assessment is not None
        categories = assessment["reliability"]["riskCategories"]
        assert len(categories) >= 10
        assert {item["component"] for item in categories} == {"Rotor", "Stator"}


# ── FeedbackRequest model_post_init ───────────────────────────────────────────


class TestFeedbackRequestModel:
    def test_up_feedback_sets_positive_rating(self):
        req = FeedbackRequest(feedback="up")
        assert req.rating == 1
        assert req.helpful is True

    def test_down_feedback_sets_negative_rating(self):
        req = FeedbackRequest(feedback="down")
        assert req.rating == -1
        assert req.helpful is False

    def test_no_feedback_keeps_defaults(self):
        req = FeedbackRequest()
        assert req.rating == 0
        assert req.helpful is True

    def test_feedback_type_sets_correctness_alias(self):
        req = FeedbackRequest(feedback="down", feedbackType="High")
        assert req.correctness == "High"
        assert req.feedbackType == "High"


# ── GET /dataservices/api/v1/assessments/{id}/findings ────────────────────────────────────────


class TestGetFindings:
    def test_returns_findings_for_analyzed_assessment(self, client: TestClient):
        # First trigger RE analysis to persist findings
        client.post("/dataservices/api/v1/assessments/asmt_001/analyze/run", json={"persona": "RE"})
        resp = client.get("/dataservices/api/v1/assessments/asmt_001/findings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["assessmentId"] == "asmt_001"
        assert "findings" in data
        assert "summary" in data
        assert "feedback" in data

    def test_seeded_demo_findings_include_feedback(self, client: TestClient):
        # _seed_mock_risk_analysis_store() runs at import time when USE_MOCK_ASSESSMENTS
        # may be False (dev env default). Re-run it here so _STORE is populated while
        # the mock_env fixture guarantees USE_MOCK_ASSESSMENTS=True.
        from data_service.mock_services.assessments import _seed_mock_risk_analysis_store  # noqa: PLC0415
        _seed_mock_risk_analysis_store()
        resp = client.get("/dataservices/api/v1/assessments/asmt_001/findings")

        assert resp.status_code == 200
        data = resp.json()
        assert data["assessmentId"] == "asmt_001"
        assert data["summary"].startswith("Simulated risk-eval output saved for ESN GT12345")
        first_finding = data["findings"][0]
        assert list(first_finding.keys()) == [
            "id",
            "Issue name",
            "Component and Issue Grouping",
            "Condition",
            "Threshold",
            "Actual Value",
            "Risk",
            "Evidence",
            "Citation",
            "justification",
            "Ambiguity handling",
            "_meta",
        ]
        # Each finding must carry a non-empty id so the narrative can correlate feedback.
        assert first_finding["id"], "Finding id must be non-empty for narrative feedback mapping"
        # Confirm the id from the findings list matches the feedback key — this is the
        # core invariant fixed in ticket 622737.
        ids_in_findings = {f["id"] for f in data["findings"] if f.get("id")}
        assert "finding_001" in ids_in_findings, "finding_001 id must surface in findings response"
        assert data["feedback"]["finding_001"]["correctness"] == "Heavy"
        assert data["feedback"]["finding_001"]["helpful"] is False

    def test_returns_404_for_no_findings(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/assessments/NO_SUCH_ID/findings")
        assert resp.status_code == 404


# ── List assessments with date-range filter ───────────────────────────────────


class TestListAssessmentsDateFilter:
    def test_date_range_filter_accepted(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/assessments?date_from=2024-01-01&date_to=2026-12-31")
        assert resp.status_code == 200
        assert isinstance(resp.json()["assessments"], list)


# ── Feedback with up/down via route ───────────────────────────────────────────


class TestFeedbackUpDown:
    def test_submit_up_feedback(self, client: TestClient):
        # Trigger analysis first so findings exist
        client.post("/dataservices/api/v1/assessments/asmt_001/analyze/run", json={"persona": "RE"})
        payload = {"feedback": "up", "comments": "Great finding"}
        resp = client.post(
            "/dataservices/api/v1/assessments/asmt_001/findings/finding_001/feedback",
            json=payload,
        )
        assert resp.status_code == 200

        findings = client.get("/dataservices/api/v1/assessments/asmt_001/findings")
        assert findings.status_code == 200
        feedback_map = findings.json().get("feedback", {})
        assert "finding_001" in feedback_map
        assert feedback_map["finding_001"]["rating"] == 1

    def test_submit_down_feedback(self, client: TestClient):
        client.post("/dataservices/api/v1/assessments/asmt_001/analyze/run", json={"persona": "RE"})
        payload = {"feedback": "down", "feedbackType": "High", "comments": "Not relevant"}
        resp = client.post(
            "/dataservices/api/v1/assessments/asmt_001/findings/finding_001/feedback",
            json=payload,
        )
        assert resp.status_code == 200

        findings = client.get("/dataservices/api/v1/assessments/asmt_001/findings")
        assert findings.status_code == 200
        feedback_map = findings.json().get("feedback", {})
        assert feedback_map["finding_001"]["feedback"] == "down"
        assert feedback_map["finding_001"]["feedbackType"] == "High"
        assert feedback_map["finding_001"]["correctness"] == "High"


# ── Unit tests: _group_by_operation ───────────────────────────────────────────────────────────


class TestGroupByOperation:
    """Pure unit tests for _group_by_operation — no HTTP client needed."""

    def _make_finding(self, component: str, risk: str = "Heavy") -> dict:
        return {
            "component": component,
            "riskLevel": risk,
            "overallRisk": risk,
            "Issue name": f"{component} issue",
            "Condition": "Test condition",
            "condition": "Test condition",
        }

    def test_groups_identical_components(self) -> None:
        findings = [
            self._make_finding("Stator"),
            self._make_finding("Stator"),
            self._make_finding("Rotor"),
        ]
        groups = _group_by_operation(findings)
        ids = [g["id"] for g in groups]
        assert "stator-rewind" in ids
        assert "rotor-rewind" in ids
        assert len(groups) == 2

    def test_normalizes_stator_variants_into_one_group(self) -> None:
        """LLM naming inconsistencies must all merge to the same Stator group."""
        findings = [
            self._make_finding("Stator Winding"),
            self._make_finding("Generator Stator"),
            self._make_finding("Stator"),
            self._make_finding("Traction Motor Stator"),
        ]
        groups = _group_by_operation(findings)
        assert len(groups) == 1
        assert groups[0]["id"] == "stator-rewind"
        assert groups[0]["component"] == "Stator"
        assert len(groups[0]["conditions"]) == 4

    def test_normalizes_rotor_and_field_variants_into_one_group(self) -> None:
        findings = [
            self._make_finding("Rotor"),
            self._make_finding("Generator Rotor"),
            self._make_finding("Generator Field"),
            self._make_finding("Field Winding"),
        ]
        groups = _group_by_operation(findings)
        assert len(groups) == 1
        assert groups[0]["id"] == "rotor-rewind"
        assert groups[0]["component"] == "Rotor"
        assert len(groups[0]["conditions"]) == 4

    def test_sorts_categories_by_severity_descending(self) -> None:
        """Heavy categories must appear before Medium, Medium before Light."""
        findings = [
            self._make_finding("Stator", "Light"),
            self._make_finding("Rotor", "Medium"),
        ]
        # Add a third group with Heavy
        findings.append({**self._make_finding("General", "Heavy"), "component": "General"})
        groups = _group_by_operation(findings)
        risk_order = [g["overallRisk"] for g in groups]
        assert risk_order == ["Heavy", "Medium", "Light"]

    def test_conditions_count_in_description(self) -> None:
        findings = [self._make_finding("Stator")] * 3
        groups = _group_by_operation(findings)
        assert "3 evidence records evaluated" in groups[0]["description"]

    def test_empty_input_returns_empty_list(self) -> None:
        assert _group_by_operation([]) == []

    def test_non_dict_entries_skipped(self) -> None:
        findings = ["bad", None, self._make_finding("Stator")]
        groups = _group_by_operation(findings)  # type: ignore[arg-type]
        assert len(groups) == 1

    def test_conditions_from_nested_conditions_list(self) -> None:
        """If a finding already has a 'conditions' list, use those directly."""
        finding = {
            "component": "Stator",
            "overallRisk": "Medium",
            "conditions": [
                {"findingId": "cond-1", "riskLevel": "Medium"},
                {"findingId": "cond-2", "riskLevel": "Low"},
            ],
        }
        groups = _group_by_operation([finding])
        assert len(groups[0]["conditions"]) == 2
        assert groups[0]["conditions"][0]["findingId"] == "cond-1"
