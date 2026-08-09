"""Facade-only private A2A adapter with a fixed coordinator destination allowlist."""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, ClassVar, Literal

from ..contracts import ChatRequest, ChatResponse
from ..inference import IdempotentConnectionError


class A2ATimeoutError(TimeoutError):
    """A selected A2A destination exceeded its locked deadline."""

    def __init__(self) -> None:
        self.duration_ms = 22000.0
        super().__init__("dependency_timeout")


class KagentCoordinatorAdapter:
    """Call exactly one selected internal coordinator destination through injection."""

    destinations: ClassVar[dict[str, str]] = {
        "v1-primary": "coordinator-v1-primary",
        "v2-primary": "coordinator-v2-primary",
        "v1-comparison": "coordinator-v1-comparison",
    }

    def __init__(
        self,
        transport: Callable[[str, ChatRequest, str], Awaitable[ChatResponse]] | None = None,
        *,
        readiness: Callable[[], Awaitable[bool]] | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        jitter: Callable[[], float] = lambda: 0.05,
    ) -> None:
        self._transport = transport
        self._readiness = readiness
        self._sleep = sleep
        self._jitter = jitter

    deadline_seconds = 22

    async def is_ready(self) -> bool:
        """Report ready only through an explicit dependency health hook."""

        if self._readiness is None:
            return False
        try:
            return bool(await self._readiness())
        except Exception:
            return False

    async def chat(
        self,
        *,
        request: ChatRequest,
        runtime_variant: Literal["v1-primary", "v2-primary", "v1-comparison"],
        route_hint: Literal["support", "drift", "abstain"],
    ) -> ChatResponse:
        if runtime_variant not in self.destinations:
            raise ValueError("unallowlisted_coordinator_destination")
        if self._transport is None:
            raise ConnectionError("coordinator_dependency_unavailable")
        destination = self.destinations[runtime_variant]
        try:
            return await asyncio.wait_for(
                self._transport(destination, request, route_hint), timeout=self.deadline_seconds
            )
        except IdempotentConnectionError:
            await self._sleep(self._jitter())
            try:
                return await asyncio.wait_for(
                    self._transport(destination, request, route_hint), timeout=self.deadline_seconds
                )
            except asyncio.TimeoutError as exc:
                raise A2ATimeoutError() from exc
        except asyncio.TimeoutError as exc:
            raise A2ATimeoutError() from exc


__all__ = ["A2ATimeoutError", "KagentCoordinatorAdapter"]
