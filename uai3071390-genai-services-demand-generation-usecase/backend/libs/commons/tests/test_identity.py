"""Tests for commons.identity.UserContext."""

from __future__ import annotations

import pytest

from commons.identity import UserContext


def test_construction_with_defaults() -> None:
    user = UserContext(sub="abc-123", email="a@b.com")
    assert user.sub == "abc-123"
    assert user.email == "a@b.com"
    assert user.roles == []


def test_construction_with_roles() -> None:
    user = UserContext(sub="abc-123", email="a@b.com", roles=["admin", "viewer"])
    assert user.roles == ["admin", "viewer"]


def test_has_role_true(user_context: UserContext) -> None:
    assert user_context.has_role("sdg-reader") is True


def test_has_role_false(user_context: UserContext) -> None:
    assert user_context.has_role("sdg-admin") is False


def test_frozen_immutability() -> None:
    from dataclasses import FrozenInstanceError

    user = UserContext(sub="abc-123", email="a@b.com")
    with pytest.raises(FrozenInstanceError):
        user.sub = "changed"  # type: ignore[misc]


def test_fixture_fields(user_context: UserContext) -> None:
    assert "@" in user_context.email
    assert len(user_context.roles) == 2
