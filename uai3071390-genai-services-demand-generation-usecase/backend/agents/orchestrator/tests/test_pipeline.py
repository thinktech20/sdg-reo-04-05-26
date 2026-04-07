"""Unit tests for the orchestrator routed pipeline.

Two separate invocations:
    1. job_type="run"       — RE: A1→A2; OE: A1→A3
  2. job_type="narrative" — A2 (narrative) ONLY, triggered after user feedback gate

All tests use ORCHESTRATOR_LOCAL_MODE=true (set in conftest) so no
real downstream HTTP calls are made.
"""

from __future__ import annotations

import pytest

from orchestrator.graph.state import PipelineState

_TERMINAL = ("PENDING", "RUNNING", "COMPLETE", "FAILED")


# ── Health ────────────────────────────────────────────────────────────────────


class TestHealth:
    def test_health_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ── Run endpoint (job_type="run") ─────────────────────────────────────────────


class TestRunEndpoint:
    def test_re_run_job_type_run_returns_202(self, client):
        resp = client.post(
            "/orchestrator/api/v1/assessments/asmt_001/run",
            json={"assessment_id": "asmt_001", "esn": "GT12345", "persona": "RE", "job_type": "run"},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["assessmentId"] == "asmt_001"
        assert data["status"] == "PENDING"

    def test_oe_run_job_type_run_returns_202(self, client):
        resp = client.post(
            "/orchestrator/api/v1/assessments/asmt_002/run",
            json={"assessment_id": "asmt_002", "esn": "GT99999", "persona": "OE", "job_type": "run"},
        )
        assert resp.status_code == 202
        assert resp.json()["status"] == "PENDING"

    def test_job_type_defaults_to_run(self, client):
        """job_type defaults to 'run' when omitted — backwards compatible."""
        resp = client.post(
            "/orchestrator/api/v1/assessments/asmt_003/run",
            json={"assessment_id": "asmt_003", "esn": "GT12345", "persona": "RE"},
        )
        assert resp.status_code == 202

    def test_missing_assessment_id_422(self, client):
        resp = client.post(
            "/orchestrator/api/v1/assessments/asmt_001/run",
            json={"esn": "GT12345"},
        )
        assert resp.status_code == 422


# ── Narrative endpoint (job_type="narrative", post-feedback gate) ─────────────


class TestNarrativeInvocation:
    def test_narrative_job_type_returns_202(self, client):
        """Narrative is a separate invocation triggered AFTER user submits feedback."""
        resp = client.post(
            "/orchestrator/api/v1/assessments/asmt_n1/run",
            json={"assessment_id": "asmt_n1", "esn": "GT12345", "persona": "RE", "job_type": "narrative"},
        )
        assert resp.status_code == 202
        assert resp.json()["status"] == "PENDING"

    def test_narrative_tracked_separately_from_run(self, client):
        """run and narrative jobs for the same assessment are independent job store entries."""
        client.post(
            "/orchestrator/api/v1/assessments/asmt_n2/run",
            json={"assessment_id": "asmt_n2", "esn": "GT12345", "persona": "RE", "job_type": "run"},
        )
        client.post(
            "/orchestrator/api/v1/assessments/asmt_n2/run",
            json={"assessment_id": "asmt_n2", "esn": "GT12345", "persona": "RE", "job_type": "narrative"},
        )
        run_status = client.get("/orchestrator/api/v1/assessments/asmt_n2/status?jobType=run").json()
        narrative_status = client.get("/orchestrator/api/v1/assessments/asmt_n2/status?jobType=narrative").json()
        assert run_status["jobType"] == "run"
        assert narrative_status["jobType"] == "narrative"
        assert run_status["status"] in _TERMINAL
        assert narrative_status["status"] in _TERMINAL


# ── Status endpoint ───────────────────────────────────────────────────────────


class TestStatusEndpoint:
    def test_status_before_run_returns_pending(self, client):
        resp = client.get("/orchestrator/api/v1/assessments/no_job_yet/status?jobType=run")
        assert resp.status_code == 200
        data = resp.json()
        assert data["assessmentId"] == "no_job_yet"
        assert data["status"] == "PENDING"

    def test_status_after_run_submitted(self, client):
        client.post(
            "/orchestrator/api/v1/assessments/asmt_s1/run",
            json={"assessment_id": "asmt_s1", "esn": "GT12345", "persona": "RE", "job_type": "run"},
        )
        resp = client.get("/orchestrator/api/v1/assessments/asmt_s1/status?jobType=run")
        assert resp.status_code == 200
        assert resp.json()["status"] in _TERMINAL

    def test_narrative_status_before_narrative_invocation_is_pending(self, client):
        """Status for narrative job is PENDING until /analyze/narrative is called."""
        resp = client.get("/orchestrator/api/v1/assessments/asmt_s2/status?jobType=narrative")
        assert resp.status_code == 200
        assert resp.json()["status"] == "PENDING"

    def test_oe_run_status_tracked_correctly(self, client):
        client.post(
            "/orchestrator/api/v1/assessments/asmt_s3/run",
            json={"assessment_id": "asmt_s3", "esn": "GT12345", "persona": "OE", "job_type": "run"},
        )
        resp = client.get("/orchestrator/api/v1/assessments/asmt_s3/status?jobType=run")
        assert resp.status_code == 200
        assert resp.json()["status"] in _TERMINAL


class TestRiskEvalContract:
    @pytest.mark.asyncio
    async def test_risk_eval_node_maps_equipment_type_to_component_type(self, monkeypatch):
        from orchestrator.graph import nodes

        captured: dict[str, object] = {}

        class DummyResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, object]:
                return {"riskCategories": {}}

        class DummyClient:
            def __init__(self, *args, **kwargs) -> None:
                return None

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb) -> None:
                return None

            async def post(self, url: str, json: dict[str, object]) -> DummyResponse:
                captured["url"] = url
                captured["json"] = json
                return DummyResponse()

        monkeypatch.setattr(nodes.config, "ORCHESTRATOR_LOCAL_MODE", False)
        monkeypatch.setattr(nodes.config, "RISK_EVAL_URL", "http://risk-eval")
        monkeypatch.setattr(nodes.httpx, "AsyncClient", DummyClient)

        state: PipelineState = {
            "assessment_id": "asmt-re-1",
            "job_type": "run",
            "esn": "92307",
            "persona": "RE",
            "input_payload": {"equipmentType": "Generator"},
            "current_stage": "starting",
            "error": None,
        }

        result = await nodes.risk_eval_node(state)

        assert "risk_eval_result" in result
        assert captured["url"] == "http://risk-eval/riskevaluationassistant/api/v1/risk-eval/run"
        assert captured["json"]["component_type"] == "Generator"
        assert captured["json"]["esn"] == "92307"

    @pytest.mark.asyncio
    async def test_finalize_node_returns_keyed_risk_categories(self):
        from orchestrator.graph.nodes import finalize_node

        result = await finalize_node(
            {
                "assessment_id": "asmt-re-2",
                "job_type": "run",
                "persona": "RE",
                "risk_eval_result": {
                    "findings": [
                        {"id": "stator-rewind", "name": "Stator Rewind Risk"},
                        {"id": "rotor-rewind", "name": "Rotor Rewind Risk"},
                    ]
                },
            }
        )

        assert result["final_result"]["riskCategories"] == {
            "stator-rewind": {"id": "stator-rewind", "name": "Stator Rewind Risk"},
            "rotor-rewind": {"id": "rotor-rewind", "name": "Rotor Rewind Risk"},
        }
        # data and findings are promoted to top level for _persist_result
        assert result["final_result"]["findings"] == [
            {"id": "stator-rewind", "name": "Stator Rewind Risk"},
            {"id": "rotor-rewind", "name": "Rotor Rewind Risk"},
        ]
        assert result["final_result"]["data"] == []

    @pytest.mark.asyncio
    async def test_finalize_node_prefers_explicit_risk_categories(self):
        from orchestrator.graph.nodes import finalize_node

        result = await finalize_node(
            {
                "assessment_id": "asmt-re-3",
                "job_type": "run",
                "persona": "RE",
                "risk_eval_result": {
                    "findings": [{"id": "legacy", "name": "Legacy Finding"}],
                    "riskCategories": {"stator": {"id": "stator", "name": "Stator Rewind Risk"}},
                },
            }
        )

        assert result["final_result"]["riskCategories"] == {
            "stator": {"id": "stator", "name": "Stator Rewind Risk"}
        }
        assert result["final_result"]["findings"] == [{"id": "legacy", "name": "Legacy Finding"}]

    @pytest.mark.asyncio
    async def test_finalize_node_passes_through_retrieval_payload(self):
        from orchestrator.graph.nodes import finalize_node

        result = await finalize_node(
            {
                "assessment_id": "asmt-re-3b",
                "job_type": "run",
                "persona": "RE",
                "risk_eval_result": {
                    "findings": [],
                    "retrieval": {
                        "issue-1": {
                            "fsr_chunks": [{"chunk_id": "fsr-1"}],
                            "er_chunks": [{"chunk_id": "er-1"}],
                        }
                    },
                },
            }
        )

        assert result["final_result"]["retrieval"]["issue-1"]["fsr_chunks"][0]["chunk_id"] == "fsr-1"

    @pytest.mark.asyncio
    async def test_finalize_node_includes_re_narrative_summary(self):
        from orchestrator.graph.nodes import finalize_node

        result = await finalize_node(
            {
                "assessment_id": "asmt-re-4",
                "job_type": "run",
                "persona": "RE",
                "risk_eval_result": {"findings": []},
                "narrative_result": {"narrative_summary": "Narrative from A2"},
            }
        )

        assert result["final_result"]["narrativeSummary"] == "Narrative from A2"
