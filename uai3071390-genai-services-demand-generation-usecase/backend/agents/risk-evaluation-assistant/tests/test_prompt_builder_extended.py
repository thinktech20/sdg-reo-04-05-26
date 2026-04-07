"""Extended unit tests for prompt builder helper coverage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from risk_evaluation.core.utils import prompt_builder as pb


class _FakeMask:
    def __init__(self, values: list[bool]) -> None:
        self.values = values

    def any(self) -> bool:
        return any(self.values)


class _FakeSeries:
    def __init__(self, values: list[Any]) -> None:
        self._values = values

    def astype(self, _dtype: type[str]) -> "_FakeSeries":
        return _FakeSeries([str(v) for v in self._values])

    @property
    def values(self) -> list[Any]:
        return self._values

    def __eq__(self, other: object) -> _FakeMask:
        return _FakeMask([value == other for value in self._values])


class _FakeILoc:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def __getitem__(self, idx: int) -> Any:
        class _Row:
            def __init__(self, row: dict[str, Any]) -> None:
                self._row = row

            def to_dict(self) -> dict[str, Any]:
                return dict(self._row)

        return _Row(self._rows[idx])


class _FakeFrame:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self.iloc = _FakeILoc(rows)

    def __getitem__(self, key: object) -> Any:
        if isinstance(key, str):
            return _FakeSeries([row.get(key) for row in self._rows])
        if isinstance(key, _FakeMask):
            selected = [row for row, include in zip(self._rows, key.values) if include]
            return _FakeFrame(selected)
        raise TypeError(f"Unsupported key type: {type(key)!r}")


@pytest.fixture(autouse=True)
def _force_non_nan_for_strings(monkeypatch: Any) -> None:
    # tests/conftest.py installs pandas as MagicMock; make clean_scalar deterministic.
    monkeypatch.setattr(pb.pd, "isna", lambda _value: False, raising=False)


def test_basic_scalar_and_truncate_helpers() -> None:
    assert pb.clean_scalar(None) == ""
    assert pb.clean_scalar("  abc  ") == "abc"
    assert pb._truncate("", max_chars=10) == "N/A"
    assert pb._truncate("abcdef", max_chars=3).endswith("[truncated]")


def test_dedupe_and_select_chunks() -> None:
    chunks = [
        {"chunk_id": "1", "pdf_name": "a", "page_number": 1},
        {"chunk_id": "1", "pdf_name": "a", "page_number": 1},
        {"chunk_id": "2", "pdf_name": "a", "page_number": 2},
    ]
    deduped = pb._dedupe_chunks(chunks, ("chunk_id", "pdf_name", "page_number"))
    assert len(deduped) == 2

    selected = pb._select_chunks(chunks, 1, ("chunk_id", "pdf_name", "page_number"))
    assert len(selected) == 1


def test_section_formatters_cover_main_paths() -> None:
    assert "No IBAT" in pb.format_ibat_section({})
    assert "No heatmap" in pb.format_heatmap_section({})
    assert "No FSR" in pb.format_fsr_section([])
    assert "No ER" in pb.format_er_section([])

    heatmap = {
        "component": "Stator",
        "issue_name": "Leakage",
        "issue_grouping": "Stator-Issue",
        "issue_prompt": "Analyze stator leakage",
        "severity_criteria_1_light": "Minor",
        "severity_criteria_3_heavy": "Major",
    }
    assert "Severity Criteria" in pb.format_heatmap_section(heatmap)

    fsr = [{"chunk_id": "1", "pdf_name": "r.pdf", "page_number": 7, "chunk_text": "ctx"}]
    er = [{"er_number": "ER-1", "opened_at": "2025-01-01", "u_component": "Rotor"}]
    assert "FSR Chunk 1" in pb.format_fsr_section(fsr)
    assert "ER Chunk 1" in pb.format_er_section(er)


def test_build_user_prompt_success_and_error_paths(monkeypatch: Any) -> None:
    class _Template:
        def format(self, **kwargs: Any) -> str:
            return (
                f"{kwargs['heatmap_section']}\n"
                f"{kwargs['ibat_section']}\n"
                f"{kwargs['fsr_section']}\n"
                f"{kwargs['er_section']}\n"
                "value: nan"
            )

    monkeypatch.setattr(pb, "_load_prompt_template", lambda _: _Template())

    result = pb.build_user_prompt(
        ibat={"equip_serial_number": "ESN-1"},
        heatmap={"component": "Stator", "issue_name": "Leakage", "issue_prompt": "q"},
        fsr_chunks=[{"chunk_id": "1", "pdf_name": "a", "page_number": 1, "chunk_text": "x"}],
        er_chunks=[{"er_number": "ER-1", "chunk_index": 1, "opened_at": "now", "chunk_text": "y"}],
    )

    assert result.fsr_chunk_count == 1
    assert result.er_chunk_count == 1
    assert ": N/A" in result.user_prompt

    def _boom(_: str) -> Any:
        raise RuntimeError("template-fail")

    monkeypatch.setattr(pb, "_load_prompt_template", _boom)
    failed = pb.build_user_prompt({}, {}, [], [])
    assert failed.user_prompt.startswith("ERROR:")


def test_find_run_dir_and_collect_heatmap(monkeypatch: Any, tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    esn_a = run_root / "ESN-A"
    esn_b = run_root / "ESN-B"
    esn_a.mkdir(parents=True)
    esn_b.mkdir(parents=True)
    (esn_a / "heatmap.xlsx").write_text("x", encoding="utf-8")
    (esn_b / "heatmap.xlsx").write_text("x", encoding="utf-8")

    monkeypatch.setenv("RUN_ARTIFACTS_DIR", str(run_root))

    def _fake_read_excel(path: Path, engine: str | None = None) -> _FakeFrame:
        if "ESN-B" in str(path):
            return _FakeFrame([
                {
                    "issue_id": "issue-1",
                    "component": "Stator",
                    "issue_name": "Leakage",
                    "issue_grouping": "Stator-Issue",
                    "issue_question": "Prompt?",
                    "severity_criteria": "{'light': 'L', 'heavy': 'H'}",
                }
            ])
        return _FakeFrame([{"issue_id": "other"}])

    monkeypatch.setattr(pb.pd, "read_excel", _fake_read_excel)

    resolved = pb._find_run_dir("issue-1")
    assert resolved.name == "ESN-B"

    heatmap = pb.collect_heatmap_data("issue-1", resolved)
    assert heatmap["component"] == "Stator"
    assert heatmap["severity_criteria_1_light"] == "L"
    assert heatmap["severity_criteria_3_heavy"] == "H"


def test_collect_data_files_and_generate_prompt(monkeypatch: Any, tmp_path: Path) -> None:
    run_dir = tmp_path / "ESN-9"
    run_dir.mkdir(parents=True)

    (run_dir / "ibat_result.json").write_text(json.dumps([{"equip_serial_number": "E9"}]), encoding="utf-8")
    (run_dir / "fsr_result.json").write_text(
        json.dumps({"data": {"issue-x": [{"chunk_id": "c1", "Document Name": "d", "Page Number": 5, "Evidence": "ev", "ESN": "E9"}]}}),
        encoding="utf-8",
    )
    (run_dir / "er_result.json").write_text(
        json.dumps({"data": {"issue-x": [{"er_case_number": "ER-7", "chunk_text": "ctx", "opened_at": "2025", "status": "Open", "u_component": "Rotor", "u_field_action_taken": "Act"}]}}),
        encoding="utf-8",
    )

    ibat = pb.collect_ibat_data(run_dir)
    fsr = pb.collect_fsr_chunks("issue-x", run_dir)
    er = pb.collect_er_chunks("issue-x", run_dir)

    assert ibat["equip_serial_number"] == "E9"
    assert fsr[0]["pdf_name"] == "d"
    assert er[0]["er_number"] == "ER-7"

    monkeypatch.setattr(pb, "_find_run_dir", lambda issue_id: run_dir)
    monkeypatch.setattr(pb, "collect_heatmap_data", lambda issue_id, _: {"component": "Stator", "issue_name": "Leakage", "issue_prompt": "Q"})
    monkeypatch.setattr(pb, "collect_ibat_data", lambda _: {"equip_serial_number": "E9"})
    monkeypatch.setattr(pb, "collect_fsr_chunks", lambda issue_id, _: [{"chunk_id": "1", "pdf_name": "x", "page_number": 1, "chunk_text": "e"}])
    monkeypatch.setattr(pb, "collect_er_chunks", lambda issue_id, _: [{"er_number": "ER-1", "opened_at": "2025", "u_component": "Rotor", "chunk_text": "y"}])
    monkeypatch.setattr(
        pb,
        "build_user_prompt",
        lambda **_: pb.PromptBuildResult(user_prompt="final prompt", fsr_chunk_count=1, er_chunk_count=1),
    )

    pb.generate_user_prompt_for_LLM("issue-x")
    assert (run_dir / "user_prompt_issue-x.txt").read_text(encoding="utf-8") == "final prompt"
