"""Pure route-strategy boundary for support, drift, and abstention paths."""

from __future__ import annotations

import hashlib
from typing import Literal, Protocol
from uuid import UUID


class RouteStrategy(Protocol):
    """Classify a message without reaching a model, MCP server, or database."""

    def route(self, message: str) -> Literal["support", "drift", "abstain"]: ...


class KeywordRouteStrategy:
    """Small deterministic contract implementation used by local tests."""

    def route(self, message: str) -> Literal["support", "drift", "abstain"]:
        """Select drift for drift terms, support otherwise, and abstain on blank input."""

        normalized = message.strip().lower()
        if not normalized:
            return "abstain"
        if any(term in normalized for term in ("drift", "psi", "frequency")):
            return "drift"
        return "support"


def bounded_bucket(value: int) -> int:
    """Return the canonical percentage bucket.

    post: 0 <= _ < 100
    """

    return value % 100


def stable_bucket(salt: str, session_id: UUID) -> int:
    """Return the stable 0..99 experiment bucket for a salt/session pair."""

    digest = hashlib.sha256(f"{salt}:{session_id}".encode("utf-8")).hexdigest()
    return bounded_bucket(int(digest, 16))


__all__ = ["KeywordRouteStrategy", "RouteStrategy", "bounded_bucket", "stable_bucket"]
