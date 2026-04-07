"""Test fixtures for the Orchestrator service."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def local_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force local-only orchestrator settings so tests stay hermetic."""
    monkeypatch.setenv("ORCHESTRATOR_LOCAL_MODE", "true")
    monkeypatch.setenv("ORCHESTRATOR_USE_DYNAMODB", "false")
    monkeypatch.setenv("ORCHESTRATOR_CHECKPOINTER_TYPE", "memory")
    monkeypatch.setenv("DYNAMODB_ENDPOINT_URL", "")
    import orchestrator.config as cfg  # noqa: PLC0415

    monkeypatch.setattr(cfg, "ORCHESTRATOR_LOCAL_MODE", True)
    monkeypatch.setattr(cfg, "ORCHESTRATOR_USE_DYNAMODB", False)
    monkeypatch.setattr(cfg, "ORCHESTRATOR_CHECKPOINTER_TYPE", "memory")
    monkeypatch.setattr(cfg, "DYNAMODB_ENDPOINT_URL", "")


@pytest.fixture()
def client() -> Generator[TestClient]:
    """TestClient wired to the compiled LangGraph pipeline."""
    from orchestrator.main import app  # noqa: PLC0415

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
