"""Extended tests for risk_evaluation.core.agent_factory."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

from risk_evaluation.core.agent_factory import AssistantStage, RiskAnalysisAssistant


class _FakeColumns(list):
    @property
    def str(self) -> "_FakeColumns":
        return self

    def strip(self) -> list[str]:
        return [str(value).strip() for value in self]


class _FakeSeries:
    def __init__(self, values: list[str]) -> None:
        self._values = values

    @property
    def str(self) -> "_FakeSeries":
        return self

    def strip(self) -> list[str]:
        return [value.strip() for value in self._values]

    def unique(self) -> Any:
        values = self._values

        class _Unique:
            def tolist(self) -> list[str]:
                return list(dict.fromkeys(values))

        return _Unique()

    def __eq__(self, other: object) -> list[bool]:
        return [value == other for value in self._values]


class _FakeDataFrame:
    def __init__(self, rows: list[dict[str, str]]) -> None:
        self._rows = rows
        self.columns = _FakeColumns(["Component ", "Type "])

    def __getitem__(self, key: object) -> Any:
        if isinstance(key, str):
            return _FakeSeries([row.get(key, "") for row in self._rows])
        if isinstance(key, list):
            filtered = [row for row, include in zip(self._rows, key) if include]
            df = _FakeDataFrame(filtered)
            df.columns = _FakeColumns(["Component", "Type"])
            return df
        raise TypeError(f"Unsupported key {key!r}")

    def __setitem__(self, key: str, values: list[str]) -> None:
        for row, value in zip(self._rows, values):
            row[key] = value

    def iterrows(self) -> Any:
        for idx, row in enumerate(self._rows):
            yield idx, row

    def __len__(self) -> int:
        return len(self._rows)


@patch("risk_evaluation.core.agent_factory.LiteLLMModel")
def test_build_model_uses_config(mock_model_class: MagicMock) -> None:
    from risk_evaluation.core import agent_factory as af

    af.config.LITELLM_PROXY_API_KEY = "k"
    af.config.LITELLM_API_BASE = "http://base"
    af.config.LITELLM_MODEL_ID = "model-id"

    af.build_model()

    mock_model_class.assert_called_once()
    kwargs = mock_model_class.call_args.kwargs
    assert kwargs["model_id"] == "model-id"
    assert kwargs["client_args"]["api_key"] == "k"


@patch("risk_evaluation.core.agent_factory.boto3.Session")
def test_build_boto_session(mock_session: MagicMock) -> None:
    from risk_evaluation.core import agent_factory as af

    af.config.AWS_REGION = "us-east-1"
    af.build_boto_session()
    mock_session.assert_called_once_with(region_name="us-east-1")


@patch("risk_evaluation.core.agent_factory.Agent")
def test_build_agent(mock_agent_class: MagicMock) -> None:
    from risk_evaluation.core import agent_factory as af

    af.build_agent(model=MagicMock(), tools=[MagicMock()], system_prompt="sys")
    mock_agent_class.assert_called_once()


def test_prompt_and_reference_loaders(monkeypatch: Any) -> None:
    assistant = RiskAnalysisAssistant(model_name="m")

    with patch("builtins.open", mock_open(read_data="system prompt")):
        assert assistant.load_system_prompt() == "system prompt"

    with patch("builtins.open", mock_open(read_data="prompt_template:\n  input_variables: ['tool_results','component_reference_data','query','component_type']\n  template: '{tool_results}'\n")):
        template = assistant._load_prompt_template("x.yaml")
        rendered = template.format(
            tool_results="ok",
            component_reference_data="ref",
            query="q",
            component_type="Stator",
        )
        assert "ok" in rendered

    with patch("risk_evaluation.core.agent_factory.pd.read_csv", return_value=_FakeDataFrame([
        {"Component": "Stator Core", "Type": "Stator"},
        {"Component": "Rotor Coil", "Type": "Rotor"},
    ])):
        markdown = assistant._load_component_reference_data()
        assert "Stator Core" in markdown
        assert "Rotor components" in markdown

    with patch("risk_evaluation.core.agent_factory.pd.read_csv", side_effect=RuntimeError("csv fail")):
        assert "not available" in assistant._load_component_reference_data()

    with patch("builtins.open", mock_open(read_data='[{"risk":"h"}]')):
        assert "risk" in assistant._load_severity_mapping_data()

    with patch("builtins.open", side_effect=RuntimeError("missing")):
        assert "not available" in assistant._load_severity_mapping_data()


@pytest.mark.asyncio
@patch("risk_evaluation.core.agent_factory.build_agent")
@patch("risk_evaluation.core.agent_factory.build_model")
async def test_invoke_with_prompt_and_cleanup(
    _mock_build_model: MagicMock,
    mock_build_agent: MagicMock,
) -> None:
    assistant = RiskAnalysisAssistant(model_name="m")
    agent = MagicMock()
    agent.invoke_async = AsyncMock(return_value=MagicMock(message={"content": [{"text": "reply"}]}))
    agent.cleanup = MagicMock()
    mock_build_agent.return_value = agent

    result = await assistant.invoke_with_prompt("sys", "user")
    assert result == "reply"
    agent.cleanup.assert_called_once()

    agent.invoke_async = AsyncMock(side_effect=RuntimeError("invoke fail"))
    with pytest.raises(RuntimeError):
        await assistant.invoke_with_prompt("sys", "user")


@pytest.mark.asyncio
@patch("risk_evaluation.core.agent_factory.build_agent")
@patch("risk_evaluation.core.agent_factory.build_model")
async def test_invoke_assistant_stages_and_parallel(
    _mock_build_model: MagicMock,
    mock_build_agent: MagicMock,
) -> None:
    assistant = RiskAnalysisAssistant(model_name="m")

    class _Template:
        def format(self, **kwargs: Any) -> str:
            return f"rendered-{sorted(kwargs.keys())}"

    assistant._load_prompt_template = MagicMock(return_value=_Template())
    assistant._load_component_reference_data = MagicMock(return_value="comp-ref")
    assistant._load_severity_mapping_data = MagicMock(return_value="sev-ref")

    agent = MagicMock()
    agent.invoke_async = AsyncMock(return_value=MagicMock(message={"content": [{"text": "ok"}]}))
    agent.cleanup = MagicMock()
    mock_build_agent.return_value = agent

    out_component = await assistant.invoke_assistant(
        tool_results={"x": 1},
        stage=AssistantStage.COMPONENT_VALIDATION,
        prompt_filename="p.yaml",
        input_params={"query": "q", "component_type": "Stator"},
    )
    assert out_component == "ok"

    out_combined = await assistant.invoke_assistant(
        tool_results={"x": 1},
        stage=AssistantStage.COMBINED_ANALYSIS,
        prompt_filename="p.yaml",
        input_params={"query": "q", "component_type": "Rotor"},
    )
    assert out_combined == "ok"

    with patch.object(assistant, "invoke_assistant", new=AsyncMock(side_effect=["a", "b"])):
        a, b = await assistant.run_parallel_assistant(
            tool_results_fsr={"a": 1},
            tool_results_er={"b": 2},
            prompt_filename_a="a.yaml",
            prompt_filename_b="b.yaml",
            input_params={"query": "q", "component_type": "Stator"},
        )
    assert a == "a"
    assert b == "b"
