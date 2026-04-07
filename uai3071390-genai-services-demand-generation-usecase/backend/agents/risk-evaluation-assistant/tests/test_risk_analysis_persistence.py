"""Unit tests for risk analysis persistence helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from risk_evaluation.core.services.risk_analysis_persistence import RiskAnalysisPersistence


def test_parse_llm_results_mixed_inputs() -> None:
    llm_results = [
        {"issue_id": "ok-1", "response": '```json {"findings": [], "summary": "done"} ```', "error": None},
        {"issue_id": "err-1", "response": None, "error": "tool failed"},
        {"issue_id": "bad-1", "response": "not-json", "error": None},
    ]

    parsed = RiskAnalysisPersistence.parse_llm_results(llm_results)
    assert len(parsed) == 3
    assert parsed[0]["issue_id"] == "ok-1"
    assert parsed[1]["summary"].startswith("Error:")
    assert parsed[2]["summary"] == "Failed to parse LLM response"


def test_build_retrieval_merges_issue_keys(monkeypatch: Any, tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    run_dir = run_root / "ESN-1"
    run_dir.mkdir(parents=True)

    (run_dir / "fsr_result.json").write_text(
        json.dumps({"data": {"i1": [{"chunk_id": "f1"}], "i2": [{"chunk_id": "f2"}]}}),
        encoding="utf-8",
    )
    (run_dir / "er_result.json").write_text(
        json.dumps({"data": {"i2": [{"er": "e2"}], "i3": [{"er": "e3"}]}}),
        encoding="utf-8",
    )

    monkeypatch.setenv("RUN_ARTIFACTS_DIR", str(run_root))
    persistence = RiskAnalysisPersistence(esn="ESN-1")

    retrieval = persistence.build_retrieval()
    assert set(retrieval.keys()) == {"i1", "i2", "i3"}
    assert retrieval["i1"]["er_chunks"] == []
    assert retrieval["i3"]["fsr_chunks"] == []


@pytest.mark.asyncio
async def test_persist_posts_findings_and_retrieval(monkeypatch: Any, tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    run_dir = run_root / "ESN-1"
    run_dir.mkdir(parents=True)
    monkeypatch.setenv("RUN_ARTIFACTS_DIR", str(run_root))

    persistence = RiskAnalysisPersistence(esn="ESN-1")

    with patch(
        "risk_evaluation.core.services.risk_analysis_persistence.call_rest_api",
        new=AsyncMock(return_value={"ok": True}),
    ) as mock_call, patch.object(
        persistence,
        "build_retrieval",
        return_value={"i1": {"fsr_chunks": [], "er_chunks": []}},
    ):
        await persistence.persist("assessment-1", [{"id": "f-1"}])

    assert mock_call.await_count == 1
    call_args = mock_call.await_args.kwargs
    assert call_args["method"] == "POST"
    assert call_args["body"]["findings"] == [{"id": "f-1"}]


def test_cleanup_removes_run_directory(monkeypatch: Any, tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    run_dir = run_root / "ESN-1"
    run_dir.mkdir(parents=True)
    (run_dir / "x.txt").write_text("x", encoding="utf-8")
    monkeypatch.setenv("RUN_ARTIFACTS_DIR", str(run_root))

    persistence = RiskAnalysisPersistence(esn="ESN-1")
    persistence.cleanup()

    assert not run_dir.exists()
