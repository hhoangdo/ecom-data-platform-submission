"""Observed self-hosted inference boundary; no hosted SDK is imported."""

from __future__ import annotations

from typing import Literal, Sequence

from .contracts import ObservedGeneration, WarmupResult


class ObservedInferenceClient:
    """Expose measured generation and warm-up signatures for a later llm-d adapter."""

    async def generate(
        self,
        *,
        messages: Sequence[dict[str, str]],
        model_variant: Literal["primary", "comparison"],
        max_context_tokens: int = 4096,
    ) -> ObservedGeneration:
        """Reject live generation until a pinned local adapter is supplied."""

        raise NotImplementedError("inference runtime belongs to successor topics")

    async def warmup(
        self,
        model_variant: Literal["primary", "comparison"],
    ) -> WarmupResult:
        """Reject live warm-up until a pinned local adapter is supplied."""

        raise NotImplementedError("inference warm-up belongs to successor topics")


__all__ = ["ObservedInferenceClient"]
