"""Coordinator boundary and deterministic independent experiment assignment."""

from __future__ import annotations

import hashlib
from typing import Literal
from uuid import UUID, uuid4

from .contracts import ChatRequest, ChatResponse
from .ports import CoordinatorAgentPort
from .routing import KeywordRouteStrategy, RouteStrategy


class CommerceAgentCoordinator:
    """Facade that selects one coordinator variant and never calls specialists directly."""

    def __init__(
        self,
        agent: CoordinatorAgentPort | None = None,
        strategy: RouteStrategy | None = None,
    ) -> None:
        self._agent = agent
        self._strategy = strategy or KeywordRouteStrategy()

    @staticmethod
    def _bucket(salt: str, session_id: UUID) -> int:
        digest = hashlib.sha256(f"{salt}:{session_id}".encode("utf-8")).hexdigest()
        return int(digest, 16) % 100

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Route through the injected coordinator port or return a safe abstention."""

        route = request.route if request.route != "auto" else self._strategy.route(request.message)
        if self._agent is None:
            return ChatResponse(
                request_id=uuid4(),
                route="abstain",
                answer="I cannot answer without a verified evidence service.",
                claims=[],
                agent_name="commerce-coordinator",
                agent_version="contract-only",
                model_version="unavailable",
                index_version=None,
                tool_calls=[],
                safety_action="abstain",
            )
        runtime_variant = self.assign_agent_experiment(request.session_id)
        return await self._agent.chat(
            request=request,
            runtime_variant=runtime_variant,
            route_hint=route,
        )

    def assign_agent_experiment(self, session_id: UUID) -> Literal["v1-primary", "v2-primary"]:
        """Assign the independent 90/10 agent experiment using its dedicated salt."""

        return "v2-primary" if self._bucket("agent_exp_v1", session_id) >= 90 else "v1-primary"

    def assign_model_experiment(
        self,
        session_id: UUID,
    ) -> Literal["v1-primary", "v1-comparison"]:
        """Assign the independent 90/10 model experiment using its dedicated salt."""

        return (
            "v1-comparison"
            if self._bucket("model_exp_v1", session_id) >= 90
            else "v1-primary"
        )


__all__ = ["CommerceAgentCoordinator"]
