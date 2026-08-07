"""llm-d adapter boundary for pinned self-hosted model revisions."""

from __future__ import annotations

from typing import Sequence

from ..contracts import ObservedGeneration


class LlmdInferenceAdapter:
    """Implement InferencePort against a later digest-pinned local route."""

    async def generate(
        self,
        messages: Sequence[dict[str, str]],
        model: str,
    ) -> ObservedGeneration:
        """Reject live generation in the contract-only phase."""

        raise NotImplementedError("llm-d generation belongs to successor topics")


__all__ = ["LlmdInferenceAdapter"]
