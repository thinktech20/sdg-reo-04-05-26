"""Shared pytest fixtures for sdg-commons tests."""

from __future__ import annotations

import pytest

from commons.identity import UserContext


@pytest.fixture()
def user_context() -> UserContext:
    """A minimal :class:`UserContext` for use in tests."""
    return UserContext(
        sub="00000000-0000-0000-0000-000000000001",
        email="test.user@example.com",
        roles=["sdg-reader", "sdg-analyst"],
    )
