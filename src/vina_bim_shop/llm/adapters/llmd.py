"""llm-d adapter boundary for pinned self-hosted model revisions."""

from __future__ import annotations

from typing import Awaitable, Callable, Sequence

from ..contracts import ObservedGeneration
from ..inference import IdempotentConnectionError


class LlmdInferenceAdapter:
    """Implement InferencePort through an injected private llm-d transport."""

    def __init__(
        self,
        transport: Callable[[Sequence[dict[str, str]], str], Awaitable[ObservedGeneration]] | None = None,
    ) -> None:
        self._transport = transport

    async def generate(
        self,
        messages: Sequence[dict[str, str]],
        model: str,
    ) -> ObservedGeneration:
        """Never fabricate a response when the private route is unavailable."""

        if self._transport is None:
            raise IdempotentConnectionError("private_llmd_unavailable")
        return await self._transport(messages, model)


__all__ = ["LlmdInferenceAdapter"]
