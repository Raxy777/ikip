"""Authorization decision types. Deny-by-default is the identity of this module."""
from __future__ import annotations

import enum
from dataclasses import dataclass


class Effect(enum.Enum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass(frozen=True)
class AccessDecision:
    """The result of an authorization check.

    `reason` is safe for audit logging but must NOT be surfaced to end users in a way
    that reveals the existence of restricted content.
    """

    effect: Effect
    reason: str

    @classmethod
    def deny(cls, reason: str) -> "AccessDecision":
        return cls(Effect.DENY, reason)

    @classmethod
    def allow(cls, reason: str = "authorized") -> "AccessDecision":
        return cls(Effect.ALLOW, reason)

    @property
    def allowed(self) -> bool:
        return self.effect is Effect.ALLOW
