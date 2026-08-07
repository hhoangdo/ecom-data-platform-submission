"""Retrieval application boundary with no database or network side effects."""

from __future__ import annotations

from uuid import uuid4

from .contracts import SearchRequest, SearchResponse
from .ports import FeastPort


class FeastRetrievalService:
    """Delegate verified vector retrieval through the Feast port only."""

    def __init__(
        self,
        feast: FeastPort | None = None,
        *,
        index_version: str = "unavailable",
    ) -> None:
        self._feast = feast
        self._index_version = index_version

    async def search(self, request: SearchRequest) -> SearchResponse:
        """Return a typed local abstention until a verified adapter is supplied."""

        if self._feast is None:
            return SearchResponse(
                request_id=uuid4(),
                index_version=self._index_version,
                embedding_model="BAAI/bge-small-en-v1.5",
                matches=[],
                retrieval_ms=0.0,
                abstained=True,
                reason="index_unavailable",
            )
        raise NotImplementedError("embedding and Feast adapters belong to successor topics")

    async def get_verified_chunk(self, chunk_id: str, content_sha256: str):
        """Expose the hash-bound chunk lookup boundary."""

        if self._feast is None:
            raise LookupError("index_unavailable")
        raise NotImplementedError("verified chunk lookup belongs to successor topics")


__all__ = ["FeastRetrievalService"]
