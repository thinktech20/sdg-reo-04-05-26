"""Extended unit tests for risk assessment creation service internals."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from risk_evaluation.core.services.risk_assessment_creation import (
    RiskAssessmentCreationService,
    _normalize_heatmap_persona,
)


class _FakeExcelRow:
    def __init__(self, row: dict[str, Any]) -> None:
        self._row = row

    def to_dict(self) -> dict[str, Any]:
        return dict(self._row)


class _FakeExcelFrame:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def iterrows(self) -> Any:
        for idx, row in enumerate(self._rows):
            yield idx, _FakeExcelRow(row)


@patch("risk_evaluation.core.services.risk_assessment_creation.RiskAnalysisAssistant")
def test_normalize_persona_and_save_artifact(
    _mock_assistant: MagicMock,
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    assert _normalize_heatmap_persona("RE") == "REL"
    assert _normalize_heatmap_persona("OE") == "OE"
    assert _normalize_heatmap_persona(None) == "REL"

    monkeypatch.setenv("RUN_ARTIFACTS_DIR", str(tmp_path / "run"))
    service = RiskAssessmentCreationService()
    service._save_run_artifact("ESN-1", "a.json", {"k": 1})

    saved = tmp_path / "run" / "ESN-1" / "a.json"
    assert saved.exists()
    assert json.loads(saved.read_text(encoding="utf-8")) == {"k": 1}


@patch("risk_evaluation.core.services.risk_assessment_creation.RiskAnalysisAssistant")
def test_form_esn_issue_matrix_deduplicates(
    _mock_assistant: MagicMock,
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("RUN_ARTIFACTS_DIR", str(tmp_path / "run"))
    service = RiskAssessmentCreationService()
    service.all_issues = [
        {
            "component": "Stator",
            "issue_name": "Leakage",
            "issue_grouping": "Stator-Issue",
            "issue_prompt": "Q1",
            "severity_criteria_0_no_data": "N",
            "severity_criteria_1_light": "L",
            "severity_criteria_2_medium": "M",
            "severity_criteria_3_heavy": "H",
            "severity_criteria_4_immediate": "I",
        },
        {
            "component": "stator",
            "issue_name": "LEAKAGE",
            "issue_grouping": "Stator-Issue",
            "issue_prompt": "Q2",
            "severity_criteria_0_no_data": "N",
            "severity_criteria_1_light": "L",
            "severity_criteria_2_medium": "M",
            "severity_criteria_3_heavy": "H",
            "severity_criteria_4_immediate": "I",
        },
    ]

    matrix = service._form_esn_issue_matrix("ESN-2")
    assert len(matrix) == 1
    assert matrix[0]["serial_number"] == "ESN-2"


@pytest.mark.asyncio
@patch("risk_evaluation.core.services.risk_assessment_creation.RiskAnalysisAssistant")
async def test_retrieve_heatmap_uses_cached_excel(
    _mock_assistant: MagicMock,
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run" / "ESN-3"
    run_dir.mkdir(parents=True)
    (run_dir / "heatmap.xlsx").write_text("x", encoding="utf-8")

    monkeypatch.setenv("RUN_ARTIFACTS_DIR", str(tmp_path / "run"))
    service = RiskAssessmentCreationService()

    rows = [
        {
            "serial_number": "ESN-3",
            "issue_id": "i-1",
            "component": "Stator",
            "issue_name": "Leakage",
            "severity_criteria": "{'light': 'L'}",
        }
    ]
    monkeypatch.setattr(
        "risk_evaluation.core.services.risk_assessment_creation.pd.read_excel",
        lambda *_args, **_kwargs: _FakeExcelFrame(rows),
    )

    ok = await service.retrieve_heatmap_issues_from_databricks("ESN-3", persona="RE")
    assert ok is True
    assert len(service.esn_issue_matrix) == 1
    assert service.esn_issue_matrix[0]["severity_criteria"]["light"] == "L"


@pytest.mark.asyncio
@patch("risk_evaluation.core.services.risk_assessment_creation.RiskAnalysisAssistant")
@patch("risk_evaluation.core.services.risk_assessment_creation.call_rest_api")
async def test_retrieve_heatmap_calls_rest_and_forms_matrix(
    mock_call_rest_api: AsyncMock,
    _mock_assistant: MagicMock,
) -> None:
    service = RiskAssessmentCreationService()
    mock_call_rest_api.return_value = {
        "heatmap": [
            {
                "component": "Rotor",
                "issue_name": "Crack",
                "issue_grouping": "Rotor-Issue",
                "issue_prompt": "Q",
                "severity_criteria_0_no_data": "N",
                "severity_criteria_1_light": "L",
                "severity_criteria_2_medium": "M",
                "severity_criteria_3_heavy": "H",
                "severity_criteria_4_immediate": "I",
            }
        ]
    }

    with patch.object(service, "_form_esn_issue_matrix", return_value=[{"issue_id": "x"}]):
        ok = await service.retrieve_heatmap_issues_from_databricks("ESN-4", persona="RE", component_type="Generator")

    assert ok is True
    assert service.esn_issue_matrix == [{"issue_id": "x"}]
    assert mock_call_rest_api.await_count >= 1


@pytest.mark.asyncio
@patch("risk_evaluation.core.services.risk_assessment_creation.RiskAnalysisAssistant")
@patch("risk_evaluation.core.services.risk_assessment_creation.call_rest_api")
async def test_retrieve_heatmap_returns_false_when_no_rows(
    mock_call_rest_api: AsyncMock,
    _mock_assistant: MagicMock,
) -> None:
    service = RiskAssessmentCreationService()
    mock_call_rest_api.return_value = {"heatmap": []}
    ok = await service.retrieve_heatmap_issues_from_databricks("ESN-5", persona="RE")
    assert ok is False


@pytest.mark.asyncio
@patch("risk_evaluation.core.services.risk_assessment_creation.RiskAnalysisAssistant")
async def test_retrieve_ibat_paths(
    _mock_assistant: MagicMock,
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run"
    run_dir = run_root / "ESN-6"
    run_dir.mkdir(parents=True)
    monkeypatch.setenv("RUN_ARTIFACTS_DIR", str(run_root))

    service = RiskAssessmentCreationService()
    assert await service.retrieve_ibat_from_databricks("a1") is False

    service.esn_issue_matrix = [{"serial_number": "ESN-6"}]
    (run_dir / "ibat_result.json").write_text(json.dumps([{"equip_serial_number": "ESN-6"}]), encoding="utf-8")
    assert await service.retrieve_ibat_from_databricks("a1") is True
    assert service.ibat_data["equip_serial_number"] == "ESN-6"


@pytest.mark.asyncio
@patch("risk_evaluation.core.services.risk_assessment_creation.RiskAnalysisAssistant")
@patch("risk_evaluation.core.services.risk_assessment_creation.call_rest_api")
async def test_retrieve_ibat_rest_success_and_error(
    mock_call_rest_api: AsyncMock,
    _mock_assistant: MagicMock,
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run"
    run_dir = run_root / "ESN-7"
    run_dir.mkdir(parents=True)
    monkeypatch.setenv("RUN_ARTIFACTS_DIR", str(run_root))

    service = RiskAssessmentCreationService()
    service.esn_issue_matrix = [{"serial_number": "ESN-7"}]

    mock_call_rest_api.return_value = {"data": [{"equip_serial_number": "ESN-7"}]}
    assert await service.retrieve_ibat_from_databricks("a1") is True
    assert service.ibat_data["equip_serial_number"] == "ESN-7"

    (run_dir / "ibat_result.json").unlink(missing_ok=True)
    mock_call_rest_api.side_effect = RuntimeError("down")
    assert await service.retrieve_ibat_from_databricks("a1") is False


@pytest.mark.asyncio
@patch("risk_evaluation.core.services.risk_assessment_creation.RiskAnalysisAssistant")
@patch("risk_evaluation.core.services.risk_assessment_creation.generate_user_prompt_for_LLM")
@patch("risk_evaluation.core.services.risk_assessment_creation.run_http_with_tool")
async def test_orchestrated_evidence_paths(
    mock_run_tool: AsyncMock,
    mock_generate_prompt: MagicMock,
    _mock_assistant: MagicMock,
) -> None:
    service = RiskAssessmentCreationService()

    # No matrix -> False
    assert await service._retrieve_evidence_from_databricks_orchestrated() is False

    service.esn_issue_matrix = [
        {"serial_number": "ESN-8", "issue_id": "i1", "issue_question": "q1"},
        {"serial_number": "ESN-8", "issue_id": "i2", "issue_question": "q2"},
    ]
    mock_run_tool.side_effect = [{"data": {}}, {"data": {}}]

    with patch.object(service, "_save_run_artifact") as mock_save:
        ok = await service._retrieve_evidence_from_databricks_orchestrated()

    assert ok is True
    assert mock_run_tool.await_count == 2
    assert mock_generate_prompt.call_count == 2
    assert mock_save.call_count == 2


@pytest.mark.asyncio
@patch("risk_evaluation.core.services.risk_assessment_creation.RiskAnalysisAssistant")
async def test_retrieve_evidence_dispatches_modes(_mock_assistant: MagicMock) -> None:
    service = RiskAssessmentCreationService()

    with patch.object(service, "_retrieve_evidence_from_databricks_legacy", new=AsyncMock(return_value={"ok": True})) as mock_legacy, patch.object(
        service,
        "_retrieve_evidence_from_databricks_orchestrated",
        new=AsyncMock(return_value=True),
    ) as mock_orchestrated:
        legacy = await service.retrieve_evidence_from_databricks(query="q", esn="E1")
        orchestrated = await service.retrieve_evidence_from_databricks()

    assert legacy == {"ok": True}
    assert orchestrated is True
    assert mock_legacy.await_count == 1
    assert mock_orchestrated.await_count == 1
