"""Facade-only coordinator routing with grounded abstention on every failure."""

from __future__ import annotations

import inspect
from time import perf_counter
from typing import Literal
from uuid import UUID, uuid4

from .contracts import ChatRequest, ChatResponse, ToolCallRecord
from .inference import ContextTooLargeError
from .ports import CoordinatorAgentPort
from .routing import KeywordRouteStrategy, RouteStrategy, stable_bucket
from .safety import CitationIntegrityError, inspect_message, redact_sensitive_text, verify_grounded_chat_response
from .telemetry import TelemetryRecorder


RuntimeVariant = Literal["v1-primary", "v2-primary", "v1-comparison"]
Experiment = Literal["agent", "model"]
PROMOTED_RUNTIME: RuntimeVariant = "v1-primary"


class CommerceAgentCoordinator:
    """Use one injected coordinator A2A port and never invoke specialists directly."""

    def __init__(
        self,
        agent: CoordinatorAgentPort | None = None,
        strategy: RouteStrategy | None = None,
        *,
        experiment: Experiment | None = None,
        telemetry: TelemetryRecorder | None = None,
    ) -> None:
        self._agent = agent
        self._strategy = strategy or KeywordRouteStrategy()
        self._experiment = experiment
        self._telemetry = telemetry

    @property
    def promoted_runtime(self) -> RuntimeVariant:
        return PROMOTED_RUNTIME

    async def is_ready(self) -> bool:
        if self._agent is None:
            return False
        probe = getattr(self._agent, "is_ready", None)
        if probe is None:
            return False
        try:
            result = probe()
            return bool(await result) if inspect.isawaitable(result) else bool(result)
        except Exception:
            return False

    def _abstain(
        self,
        *,
        safety_action: Literal["reject", "abstain"],
        tool_calls: list[ToolCallRecord] | None = None,
    ) -> ChatResponse:
        return ChatResponse(
            request_id=uuid4(), route="abstain", answer="I cannot provide a verified answer.",
            claims=[], agent_name="commerce-coordinator", agent_version="local-facade",
            model_version="unavailable", index_version=None, tool_calls=tool_calls or [],
            safety_action=safety_action,
        )

    def _runtime_for(self, session_id: UUID) -> RuntimeVariant:
        if self._experiment == "agent":
            return self.assign_agent_experiment(session_id)
        if self._experiment == "model":
            return self.assign_model_experiment(session_id)
        return PROMOTED_RUNTIME

    def _record(self, request: ChatRequest, route: str, runtime: str, response: ChatResponse) -> ChatResponse:
        if self._telemetry is not None:
            self._telemetry.record_coordinator(
                session_id=str(request.session_id), route=route, runtime_variant=runtime,
                destination=f"coordinator-{runtime}", experiment=self._experiment or "promoted",
                response=response,
            )
        return response

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Select one route/destination or return a typed grounded abstention."""

        decision = inspect_message(request.message)
        if decision.action == "reject":
            return self._record(request, "abstain", "none", self._abstain(safety_action="reject"))
        route = request.route if request.route != "auto" else self._strategy.route(request.message)
        runtime = self._runtime_for(request.session_id)
        if route == "abstain" or self._agent is None:
            return self._record(request, route, runtime, self._abstain(safety_action="abstain"))
        safe_request = request.model_copy(update={"message": redact_sensitive_text(request.message)}) if decision.action == "redact" else request
        started = perf_counter()
        try:
            response = await self._agent.chat(request=safe_request, runtime_variant=runtime, route_hint=route)
        except ContextTooLargeError:
            raise
        except TimeoutError as exc:
            tool = "search_ecommerce_knowledge" if route == "support" else "detect_customer_order_drift"
            duration = getattr(exc, "duration_ms", round((perf_counter() - started) * 1000, 3))
            return self._record(request, route, runtime, self._abstain(safety_action="abstain", tool_calls=[ToolCallRecord(tool=tool, status="timed_out", duration_ms=duration, error_code="dependency_timeout")]))
        except Exception:
            tool = "search_ecommerce_knowledge" if route == "support" else "detect_customer_order_drift"
            return self._record(request, route, runtime, self._abstain(safety_action="abstain", tool_calls=[ToolCallRecord(tool=tool, status="failed", duration_ms=round((perf_counter() - started) * 1000, 3), error_code="dependency_failure")]))
        try:
            verify_grounded_chat_response(response, expected_route=route)
        except CitationIntegrityError:
            return self._record(request, route, runtime, self._abstain(safety_action="abstain", tool_calls=response.tool_calls))
        if decision.action == "redact":
            response = response.model_copy(update={"safety_action": "redact"})
        return self._record(request, route, runtime, response)

    def assign_agent_experiment(self, session_id: UUID) -> Literal["v1-primary", "v2-primary"]:
        return "v2-primary" if stable_bucket("agent_exp_v1", session_id) >= 90 else "v1-primary"

    def assign_model_experiment(self, session_id: UUID) -> Literal["v1-primary", "v1-comparison"]:
        return "v1-comparison" if stable_bucket("model_exp_v1", session_id) >= 90 else "v1-primary"


__all__ = ["CommerceAgentCoordinator", "PROMOTED_RUNTIME"]
