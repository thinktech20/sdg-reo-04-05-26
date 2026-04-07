"""Unit tests for orchestrator.job_store.

Memory backend is tested directly; DynamoDB backend paths are covered via
monkeypatching to avoid real AWS calls.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import orchestrator.config as config
import orchestrator.job_store as job_store


@pytest.fixture(autouse=True)
def _reset_memory_store() -> None:
    """Clear the in-memory store between tests to prevent state bleed."""
    job_store._store.clear()


# ---------------------------------------------------------------------------
# In-memory backend
# ---------------------------------------------------------------------------


class TestMemoryBackend:
    def test_write_then_read(self) -> None:
        job_store.write_job("a1", "run", "PENDING")
        result = job_store.read_job("a1", "run")
        assert result is not None
        assert result["assessmentId"] == "a1"
        assert result["jobType"] == "run"
        assert result["status"] == "PENDING"

    def test_write_overwrites(self) -> None:
        job_store.write_job("a1", "run", "PENDING")
        job_store.write_job("a1", "run", "RUNNING", activeNode="risk_eval")
        result = job_store.read_job("a1", "run")
        assert result is not None
        assert result["status"] == "RUNNING"
        assert result["activeNode"] == "risk_eval"

    def test_read_missing_returns_none(self) -> None:
        assert job_store.read_job("no_such_id", "run") is None

    def test_different_job_types_stored_independently(self) -> None:
        job_store.write_job("a1", "run", "RUNNING")
        job_store.write_job("a1", "narrative", "PENDING")
        assert job_store.read_job("a1", "run")["status"] == "RUNNING"  # type: ignore[index]
        assert job_store.read_job("a1", "narrative")["status"] == "PENDING"  # type: ignore[index]

    def test_kwargs_stored(self) -> None:
        job_store.write_job("a2", "run", "COMPLETE", result={"score": 0.9}, errorMessage=None)
        r = job_store.read_job("a2", "run")
        assert r is not None
        assert r["result"] == {"score": 0.9}


# ---------------------------------------------------------------------------
# DynamoDB backend (mocked)
# ---------------------------------------------------------------------------


class TestDynamoDBBackend:
    @pytest.fixture(autouse=True)
    def _use_dynamodb(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(config, "ORCHESTRATOR_USE_DYNAMODB", True)

    def _make_table_mock(self) -> MagicMock:
        table = MagicMock()
        return table

    def test_write_updates_existing_execution_state_row(self, monkeypatch: pytest.MonkeyPatch) -> None:
        table = self._make_table_mock()
        table.query.return_value = {"Items": [{"esn": "ESN1", "createdAt": "2026-03-20T10:00:00Z"}]}
        monkeypatch.setattr(job_store, "_get_table", lambda: table)

        job_store.write_job("a1", "run", "RUNNING", persona="RE", esn="ESN1")

        table.update_item.assert_called_once()
        call_args = table.update_item.call_args
        assert call_args.kwargs["Key"] == {"esn": "ESN1", "createdAt": "2026-03-20T10:00:00Z"}
        assert ":status" in call_args.kwargs["ExpressionAttributeValues"]
        assert call_args.kwargs["ExpressionAttributeValues"][":status"] == "RUNNING"

    def test_write_updates_latest_row_when_duplicates_exist(self, monkeypatch: pytest.MonkeyPatch) -> None:
        table = self._make_table_mock()
        table.query.side_effect = [
            {
                "Items": [
                    {
                        "esn": "ESN1",
                        "createdAt": "2026-03-20T10:00:00Z",
                        "updatedAt": "2026-03-20T10:00:00Z",
                    }
                ],
                "LastEvaluatedKey": {"assessmentId": "a1", "workflowId": "RE_DEFAULT"},
            },
            {
                "Items": [
                    {
                        "esn": "ESN1",
                        "createdAt": "2026-03-20T10:01:00Z",
                        "updatedAt": "2026-03-20T10:02:00Z",
                    }
                ]
            },
        ]
        monkeypatch.setattr(job_store, "_get_table", lambda: table)

        job_store.write_job("a1", "run", "RUNNING", persona="RE", esn="ESN1")

        table.update_item.assert_called_once()
        assert table.update_item.call_args.kwargs["Key"] == {
            "esn": "ESN1",
            "createdAt": "2026-03-20T10:01:00Z",
        }

    def test_write_creates_row_when_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        table = self._make_table_mock()
        table.query.return_value = {"Items": []}
        monkeypatch.setattr(job_store, "_get_table", lambda: table)

        job_store.write_job("a1", "run", "PENDING", persona="RE", esn="ESN9")

        table.put_item.assert_called_once()
        item = table.put_item.call_args.kwargs["Item"]
        assert item["assessmentId"] == "a1"
        assert item["workflowId"] == "RE_DEFAULT"
        assert item["esn"] == "ESN9"
        assert item["status"] == "PENDING"

    def test_read_returns_latest_item(self, monkeypatch: pytest.MonkeyPatch) -> None:
        table = self._make_table_mock()
        table.query.side_effect = [
            {
                "Items": [
                    {
                        "status": "COMPLETE",
                        "result": {"ok": True},
                        "updatedAt": "2026-03-20T10:02:00Z",
                    }
                ]
            },
            {"Items": []},
        ]
        monkeypatch.setattr(job_store, "_get_table", lambda: table)

        result = job_store.read_job("a1", "run")
        assert result is not None
        assert result["assessmentId"] == "a1"
        assert result["jobType"] == "run"
        assert result["status"] == "COMPLETE"
        assert result["result"] == {"ok": True}

    def test_read_prefers_latest_across_duplicate_rows(self, monkeypatch: pytest.MonkeyPatch) -> None:
        table = self._make_table_mock()
        # read_job("run") probes RE_DEFAULT first, then OE_DEFAULT.
        table.query.side_effect = [
            {
                "Items": [
                    {
                        "status": "RUNNING",
                        "result": {"ok": False},
                        "updatedAt": "2026-03-20T10:00:00Z",
                    },
                    {
                        "status": "COMPLETE",
                        "result": {"ok": True},
                        "updatedAt": "2026-03-20T10:05:00Z",
                    },
                ]
            },
            {"Items": []},
        ]
        monkeypatch.setattr(job_store, "_get_table", lambda: table)

        result = job_store.read_job("a1", "run")
        assert result is not None
        assert result["status"] == "COMPLETE"
        assert result["result"] == {"ok": True}

    def test_read_returns_none_when_item_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        table = self._make_table_mock()
        table.query.side_effect = [{"Items": []}, {"Items": []}]
        monkeypatch.setattr(job_store, "_get_table", lambda: table)

        result = job_store.read_job("a1", "run")
        assert result is None

    def test_write_falls_back_to_memory_on_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        table = MagicMock()
        table.query.side_effect = Exception("DynamoDB unavailable")
        monkeypatch.setattr(job_store, "_get_table", lambda: table)

        # Should not raise; falls back to in-memory write
        job_store.write_job("a1", "run", "RUNNING")
        assert job_store._store[("a1", "run")]["status"] == "RUNNING"

    def test_read_falls_back_to_memory_on_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        table = MagicMock()
        table.query.side_effect = Exception("DynamoDB unavailable")
        monkeypatch.setattr(job_store, "_get_table", lambda: table)

        # Preload memory store to verify fallback works
        job_store._store[("a1", "run")] = {"assessmentId": "a1", "jobType": "run", "status": "PENDING"}
        result = job_store.read_job("a1", "run")
        assert result is not None
        assert result["status"] == "PENDING"


# ---------------------------------------------------------------------------
# bugfix/622621-ddb-payload — float→Decimal and 400 KB limit
# ---------------------------------------------------------------------------


class TestSanitizeForDynamoDB:
    """Tests for the local _sanitize_for_dynamodb helper in job_store."""

    def test_float_becomes_decimal(self) -> None:
        from decimal import Decimal
        result = job_store._sanitize_for_dynamodb(1.5)
        assert isinstance(result, Decimal)
        assert result == Decimal("1.5")

    def test_nan_becomes_string(self) -> None:
        result = job_store._sanitize_for_dynamodb(float("nan"))
        assert result == "nan"

    def test_inf_becomes_string(self) -> None:
        assert job_store._sanitize_for_dynamodb(float("inf")) == "inf"
        assert job_store._sanitize_for_dynamodb(float("-inf")) == "-inf"

    def test_non_float_passthrough(self) -> None:
        assert job_store._sanitize_for_dynamodb(42) == 42
        assert job_store._sanitize_for_dynamodb("s") == "s"
        assert job_store._sanitize_for_dynamodb(None) is None

    def test_nested_dict_and_list(self) -> None:
        from decimal import Decimal
        result = job_store._sanitize_for_dynamodb({"a": [1.1, {"b": 2.2}]})
        assert isinstance(result["a"][0], Decimal)
        assert isinstance(result["a"][1]["b"], Decimal)


class TestResultExcludedFromDynamoDB:
    """400 KB fix: result must be stored in memory, not written to DynamoDB."""

    @pytest.fixture(autouse=True)
    def _use_dynamodb(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(config, "ORCHESTRATOR_USE_DYNAMODB", True)

    def _make_table_mock(self) -> MagicMock:
        table = MagicMock()
        return table

    def test_result_not_in_dynamodb_update(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """result must be absent from ExpressionAttributeValues sent to DynamoDB."""
        table = self._make_table_mock()
        table.query.return_value = {
            "Items": [{"esn": "E1", "createdAt": "2026-01-01T00:00:00Z"}]
        }
        monkeypatch.setattr(job_store, "_get_table", lambda: table)

        big_result = {"findings": ["x"] * 1000}
        job_store.write_job("a1", "run", "COMPLETE", persona="RE", esn="E1", result=big_result)

        call_kwargs = table.update_item.call_args.kwargs
        attr_values = call_kwargs["ExpressionAttributeValues"]
        assert ":result" not in attr_values, "result must NOT be sent to DynamoDB"

    def test_result_stored_in_memory(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """result must be preserved in the in-memory store regardless of DynamoDB path."""
        table = self._make_table_mock()
        table.query.return_value = {
            "Items": [{"esn": "E1", "createdAt": "2026-01-01T00:00:00Z"}]
        }
        monkeypatch.setattr(job_store, "_get_table", lambda: table)

        big_result = {"data": "important"}
        job_store.write_job("a2", "run", "COMPLETE", persona="RE", esn="E1", result=big_result)

        assert job_store._store[("a2", "run")]["result"] == big_result

    def test_read_merges_result_from_memory(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """read_job must merge the in-memory result back into the DynamoDB status row."""
        table = self._make_table_mock()
        table.query.side_effect = [
            {
                "Items": [
                    {
                        "status": "COMPLETE",
                        "updatedAt": "2026-01-01T00:00:00Z",
                        # 'result' intentionally absent — 400 KB fix
                    }
                ]
            },
            {"Items": []},
        ]
        monkeypatch.setattr(job_store, "_get_table", lambda: table)

        # Pre-populate memory with the result
        job_store._store[("a3", "run")] = {
            "assessmentId": "a3",
            "jobType": "run",
            "status": "COMPLETE",
            "result": {"score": 99},
        }

        result = job_store.read_job("a3", "run")
        assert result is not None
        assert result["result"] == {"score": 99}

    def test_floats_sanitized_in_update_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """DynamoDB ExpressionAttributeValues must contain Decimal, not float."""
        from decimal import Decimal
        table = self._make_table_mock()
        table.query.return_value = {
            "Items": [{"esn": "E1", "createdAt": "2026-01-01T00:00:00Z"}]
        }
        monkeypatch.setattr(job_store, "_get_table", lambda: table)

        job_store.write_job(
            "a4", "run", "COMPLETE",
            persona="RE", esn="E1",
            nodeTimings={"risk_eval": 1.23},
        )

        attr_values = table.update_item.call_args.kwargs["ExpressionAttributeValues"]
        timings = attr_values[":nodeTimings"]
        assert isinstance(timings["risk_eval"], Decimal), (
            "float in nodeTimings must be Decimal before sending to DynamoDB"
        )

    def test_write_still_mirrors_to_memory_when_dynamodb_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Even when DynamoDB write throws, the result must be in memory."""
        table = self._make_table_mock()
        table.query.side_effect = Exception("DynamoDB unavailable")
        monkeypatch.setattr(job_store, "_get_table", lambda: table)

        job_store.write_job("a5", "run", "COMPLETE", result={"ok": True})
        assert job_store._store[("a5", "run")]["result"] == {"ok": True}
