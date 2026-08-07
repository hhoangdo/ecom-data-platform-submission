"""Pure route-strategy boundary for support, drift, and abstention paths."""

from __future__ import annotations

from typing import Literal, Protocol


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


__all__ = ["KeywordRouteStrategy", "RouteStrategy"]
