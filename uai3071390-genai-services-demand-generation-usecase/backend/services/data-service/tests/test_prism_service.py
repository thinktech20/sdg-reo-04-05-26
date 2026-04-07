from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from data_service.services import helpers as service_helpers
from data_service.services import prism_service


class _FakeNakshaClient:
    def __init__(
        self,
        rows: list[dict[str, Any]] | None = None,
        exc: Exception | None = None,
        markers: dict[str, str] | None = None,
    ) -> None:
        self._rows = rows or []
        self._exc = exc
        self._markers = markers or {"naksha_status": "success", "table_status": "available"}

    async def execute_sql(self, sql: str) -> list[dict[str, Any]]:
        if "information_schema.columns" in sql:
            return [
                {"column_name": "TURBINE_NUMBER", "column_comment": "Serial number"},
                {"column_name": "RISK_PROFILE", "column_comment": "Component/Risk profile"},
                {"column_name": "RPN", "column_comment": "Risk Priority Number"},
            ]
        if self._exc is not None:
            raise self._exc
        return self._rows

    def get_last_query_markers(self) -> dict[str, str]:
        return dict(self._markers)


@pytest.mark.asyncio
async def test_read_prism_success(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_log_event(**kwargs: Any) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(prism_service, "log_read_service_event", _fake_log_event)

    async def _fake_merge_descriptions(table_names: tuple[str, ...], db_client: Any = None) -> dict[str, str]:
        del table_names, db_client
        return {
            "TURBINE_NUMBER": "Serial number",
            "RISK_PROFILE": "Component/Risk profile",
            "RPN": "Risk Priority Number",
            "MODEL_ID": "Model ID",
            "COMPONENT": "Component",
        }

    monkeypatch.setattr(service_helpers, "merge_table_column_descriptions", _fake_merge_descriptions)

    rows = [{"TURBINE_NUMBER": "ESN001", "RISK_PROFILE": "BEARING", "RPN": "n/a", "MODEL_ID": ""}]
    response = await prism_service.read_prism_by_serial(
        serial_number="ESN001",
        requesting_user="may",
        metadata_filters={"component": "BEARING"},
        db_client=_FakeNakshaClient(rows=rows),
    )

    assert response["status"] == "success"
    assert response["record_count"] == 1
    assert response["data"][0]["MODEL_ID"] is None
    assert response["data"][0]["RPN"] == "n/a"
    assert response["metadata"]["serial_number"] == "ESN001"
    assert response["metadata"]["user"] == "may"
    assert response["metadata"]["request_id"] is None
    assert response["metadata"]["metadata_filters"]["component"] == "BEARING"

    assert captured["event"] == "read_prism_by_serial"
    assert captured["user"] == "may"
    assert captured["serial_number"] == "ESN001"
    assert captured["error"] is None
    assert isinstance(captured["duration_ms"], int)


@pytest.mark.asyncio
async def test_read_prism_unauthorized_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prism_service, "log_read_service_event", lambda **kwargs: None)
    monkeypatch.setattr(service_helpers, "merge_table_column_descriptions", AsyncMock(return_value={}))

    with pytest.raises(prism_service.PrismServiceError) as exc:
        await prism_service.read_prism_by_serial(
            serial_number="ESN001",
            requesting_user="may",
            db_client=_FakeNakshaClient(exc=RuntimeError("permission denied")),
        )

    assert exc.value.error_code == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_read_prism_system_error_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prism_service, "log_read_service_event", lambda **kwargs: None)
    monkeypatch.setattr(service_helpers, "merge_table_column_descriptions", AsyncMock(return_value={}))

    with pytest.raises(prism_service.PrismServiceError) as exc:
        await prism_service.read_prism_by_serial(
            serial_number="ESN001",
            requesting_user="may",
            db_client=_FakeNakshaClient(exc=RuntimeError("boom")),
        )

    assert exc.value.error_code == "SYSTEM_ERROR"
    assert exc.value.message == "An internal error occurred"


@pytest.mark.asyncio
async def test_read_prism_rejects_invalid_metadata_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prism_service, "log_read_service_event", lambda **kwargs: None)
    monkeypatch.setattr(service_helpers, "merge_table_column_descriptions", AsyncMock(return_value={}))

    with pytest.raises(prism_service.PrismServiceError) as exc:
        await prism_service.read_prism_by_serial(
            serial_number="ESN001",
            requesting_user="may",
            metadata_filters={"bad_field": "x"},
            db_client=_FakeNakshaClient(rows=[]),
        )

    assert exc.value.error_code == "INVALID_INPUT"
