"""Feast/PostgreSQL adapter boundary with no connection at import time."""

from __future__ import annotations

from typing import Sequence

from ..contracts import FeatureHealthPoint, SearchMatch, Section03FeatureRow, TimeWindow, UtcDateTime


class FeastPostgresAdapter:
    """Implement the FeastPort boundary in a later runtime topic."""

    async def search_documents(
        self,
        vector: Sequence[float],
        *,
        top_k: int,
        category: str | None,
        effective_at: UtcDateTime,
    ) -> list[SearchMatch]:
        """Reject live retrieval until the verified local adapter is supplied."""

        raise NotImplementedError("PostgreSQL/pgvector retrieval belongs to successor topics")

    async def read_feature_health(
        self,
        *,
        feature_name: str,
        window: TimeWindow,
    ) -> Sequence[FeatureHealthPoint]:
        """Reject live feature reads until the Section 03 loader is supplied."""

        raise NotImplementedError("Feast feature reads belong to successor topics")

    async def read_customer_snapshot(
        self,
        *,
        id: str,
        as_of: UtcDateTime,
    ) -> Section03FeatureRow | None:
        """Reject live point-in-time reads until the Section 03 adapter is supplied."""

        raise NotImplementedError("Section 03 point-in-time reads belong to successor topics")


__all__ = ["FeastPostgresAdapter"]
