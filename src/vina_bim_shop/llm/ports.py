"""Protocol ports for inward-facing EDAI2 application boundaries."""

from __future__ import annotations

from typing import Literal, Protocol, Sequence

from .contracts import (
    ChatRequest,
    ChatResponse,
    FeatureHealthPoint,
    SearchMatch,
    Section03FeatureRow,
    TimeWindow,
    UtcDateTime,
    ObservedGeneration,
)


class EmbeddingPort(Protocol):
    """Encode text into finite 384-dimensional vectors."""

    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...

    async def embed_query(self, query: str) -> list[float]: ...


class FeastPort(Protocol):
    """Read indexed documents and Section 03 feature-health data."""

    async def search_documents(
        self,
        vector: Sequence[float],
        *,
        top_k: int,
        category: str | None,
        effective_at: UtcDateTime,
    ) -> list[SearchMatch]: ...

    async def get_verified_chunk(
        self,
        *,
        chunk_id: str,
        content_sha256: str,
    ) -> SearchMatch | None: ...

    async def read_feature_health(
        self,
        *,
        feature_name: str,
        window: TimeWindow,
    ) -> Sequence[FeatureHealthPoint]: ...

    async def read_customer_snapshot(
        self,
        *,
        id: str,
        as_of: UtcDateTime,
    ) -> Section03FeatureRow | None: ...


class InferencePort(Protocol):
    """Generate through an observed self-hosted model adapter."""

    async def generate(
        self,
        messages: Sequence[dict[str, str]],
        model: str,
    ) -> ObservedGeneration: ...


class McpClientPort(Protocol):
    """Call one of the two allowlisted MCP tools."""

    async def call_tool(
        self,
        *,
        tool: Literal[
            "search_ecommerce_knowledge", "detect_customer_order_drift"
        ],
        arguments: dict[str, object],
    ) -> dict[str, object]: ...


class CoordinatorAgentPort(Protocol):
    """Call a selected coordinator runtime variant."""

    async def chat(
        self,
        *,
        request: ChatRequest,
        runtime_variant: Literal["v1-primary", "v2-primary", "v1-comparison"],
        route_hint: Literal["support", "drift", "abstain"],
    ) -> ChatResponse: ...


__all__ = [
    "CoordinatorAgentPort",
    "EmbeddingPort",
    "FeastPort",
    "InferencePort",
    "McpClientPort",
]
