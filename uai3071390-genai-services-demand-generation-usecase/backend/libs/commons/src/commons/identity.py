"""User identity context extracted from the ALB OIDC JWT header."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class UserContext:
    """Immutable bearer-identity propagated through every request.

    Fields are populated from the ``X-Amzn-OIDC-Data`` JWT decoded by the
    Foundation Services middleware layer.

    Attributes:
        sub:   OIDC subject — unique, stable user identifier (UUID string).
        email: User's email address from the ``email`` claim.
        roles: List of OneIDM group memberships mapped through MAP adapter.
    """

    sub: str
    email: str
    roles: list[str] = field(default_factory=list)

    def has_role(self, role: str) -> bool:
        """Return True if *role* is present in the roles list."""
        return role in self.roles
