"""kagent coordinator adapter boundary without a live endpoint."""

from __future__ import annotations

from typing import Literal

from ..contracts import ChatRequest, ChatResponse


class KagentCoordinatorAdapter:
    """Implement CoordinatorAgentPort through a later private A2A route."""

    async def chat(
        self,
        *,
        request: ChatRequest,
        runtime_variant: Literal["v1-primary", "v2-primary", "v1-comparison"],
        route_hint: Literal["support", "drift", "abstain"],
    ) -> ChatResponse:
        """Reject live agent calls in the contract-only phase."""

        raise NotImplementedError("kagent coordinator calls belong to successor topics")


__all__ = ["KagentCoordinatorAdapter"]
