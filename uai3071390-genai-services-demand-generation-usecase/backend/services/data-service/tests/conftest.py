"""Test fixtures for the Data Service.

Sets USE_MOCK=true in sys.environ before importing the app so NakshaClient
returns mock fixtures without any HTTP calls.
"""

from __future__ import annotations

import sys
from collections.abc import Generator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

# Mock MCP-related modules BEFORE any imports that use them
# This prevents StreamableHTTPSessionManager from being initialized during test collection
sys.modules["mcp"] = MagicMock()
sys.modules["mcp.server"] = MagicMock()
sys.modules["mcp.server.fastmcp"] = MagicMock()
sys.modules["mcp.server.streamable_http_manager"] = MagicMock()
sys.modules["fastmcp"] = MagicMock()

# Skip collecting test_mcp_server.py - tests legacy functions that no longer exist
collect_ignore = ["test_mcp_server.py"]


@pytest.fixture(autouse=True)
def mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force USE_MOCK=true for every test."""
    monkeypatch.setenv("USE_MOCK", "true")
    monkeypatch.setenv("USE_MOCK_UNITS", "true")
    monkeypatch.setenv("USE_MOCK_ASSESSMENTS", "true")
    # Re-set the module-level value in config (already imported)
    import data_service.config as cfg  # noqa: PLC0415

    monkeypatch.setattr(cfg, "USE_MOCK", True)
    monkeypatch.setattr(cfg, "USE_MOCK_UNITS", True)
    monkeypatch.setattr(cfg, "USE_MOCK_ASSESSMENTS", True)


@pytest.fixture()
def client() -> Generator[TestClient]:
    """TestClient with a pre-seeded NakshaClient on app.state."""
    from data_service.main import app  # noqa: PLC0415

    with TestClient(app, raise_server_exceptions=True) as c:
        # Seed app.state (lifespan runs automatically with TestClient context manager)
        yield c
