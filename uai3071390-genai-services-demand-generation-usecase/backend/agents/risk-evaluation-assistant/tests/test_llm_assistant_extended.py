"""Extended tests for LLMAssistant channel orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from risk_evaluation.core.services.llm_assistant import LLMAssistant


@patch("risk_evaluation.core.services.llm_assistant.RiskAnalysisAssistant")
def test_init_loads_system_prompt(mock_assistant_class: MagicMock) -> None:
    assistant_impl = mock_assistant_class.return_value
    assistant_impl.load_system_prompt.return_value = "system prompt"

    assistant = LLMAssistant(model_name="gpt-x", num_channels=2)

    assert assistant.system_prompt == "system prompt"
    assert assistant.num_channels == 2
    mock_assistant_class.assert_called_once_with(model_name="gpt-x")


@pytest.mark.asyncio
@patch("risk_evaluation.core.services.llm_assistant.RiskAnalysisAssistant")
async def test_process_channel_success_and_failure(mock_assistant_class: MagicMock) -> None:
    assistant_impl = mock_assistant_class.return_value
    assistant_impl.load_system_prompt.return_value = "sys"
    assistant_impl.invoke_with_prompt = AsyncMock(side_effect=["ok", RuntimeError("boom")])

    assistant = LLMAssistant(num_channels=2)
    results = await assistant._process_channel(
        channel_id=1,
        system_prompt="sys",
        user_prompts=[
            {"issue_id": "i1", "user_prompt": "u1"},
            {"issue_id": "i2", "user_prompt": "u2"},
        ],
    )

    assert len(results) == 2
    assert results[0]["response"] == "ok"
    assert results[0]["error"] is None
    assert "boom" in str(results[1]["error"])


def test_load_user_prompts_from_disk(monkeypatch: Any, tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    run_dir = run_root / "ESN-1"
    run_dir.mkdir(parents=True)
    (run_dir / "user_prompt_b.txt").write_text("prompt B", encoding="utf-8")
    (run_dir / "user_prompt_a.txt").write_text("prompt A", encoding="utf-8")

    monkeypatch.setenv("RUN_ARTIFACTS_DIR", str(run_root))

    loaded = LLMAssistant._load_user_prompts_from_disk("ESN-1")
    assert [entry["issue_id"] for entry in loaded] == ["a", "b"]
    assert loaded[0]["user_prompt"] == "prompt A"


def test_load_user_prompts_missing_dir_raises(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setenv("RUN_ARTIFACTS_DIR", str(tmp_path / "missing"))
    with pytest.raises(FileNotFoundError):
        LLMAssistant._load_user_prompts_from_disk("ESN-404")


@pytest.mark.asyncio
@patch("risk_evaluation.core.services.llm_assistant.RiskAnalysisAssistant")
async def test_run_parallel_llm_calls_empty_prompts(mock_assistant_class: MagicMock) -> None:
    assistant_impl = mock_assistant_class.return_value
    assistant_impl.load_system_prompt.return_value = "sys"
    assistant = LLMAssistant(num_channels=4)

    with patch.object(assistant, "_load_user_prompts_from_disk", return_value=[]):
        assert await assistant.run_parallel_llm_calls("ESN-1") == []


@pytest.mark.asyncio
@patch("risk_evaluation.core.services.llm_assistant.RiskAnalysisAssistant")
async def test_run_parallel_llm_calls_channel_exception(mock_assistant_class: MagicMock) -> None:
    assistant_impl = mock_assistant_class.return_value
    assistant_impl.load_system_prompt.return_value = "sys"
    assistant = LLMAssistant(num_channels=2)

    prompts = [
        {"issue_id": "i1", "user_prompt": "u1"},
        {"issue_id": "i2", "user_prompt": "u2"},
        {"issue_id": "i3", "user_prompt": "u3"},
    ]

    with patch.object(assistant, "_load_user_prompts_from_disk", return_value=prompts), patch.object(
        assistant,
        "_process_channel",
        side_effect=[
            [
                {"issue_id": "i1", "response": "r1", "error": None},
                {"issue_id": "i2", "response": "r2", "error": None},
            ],
            RuntimeError("channel-fail"),
        ],
    ):
        results = await assistant.run_parallel_llm_calls("ESN-1")

    assert len(results) == 3
    failed = [entry for entry in results if entry["error"] is not None]
    assert len(failed) == 1
    assert failed[0]["issue_id"] == "i3"
    assert "channel-fail" in failed[0]["error"]
