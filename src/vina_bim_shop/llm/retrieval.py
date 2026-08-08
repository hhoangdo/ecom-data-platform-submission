"""Async, hash-bound retrieval through the declared Feast boundary."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Callable
from datetime import UTC, datetime
from inspect import isawaitable
from time import perf_counter
from typing import Protocol, cast
from uuid import uuid4

from opentelemetry import trace

from .contracts import SearchMatch, SearchRequest, SearchResponse
from .ports import EmbeddingPort, FeastPort
from .safety import CitationIntegrityError, verify_knowledge_match, verify_reloaded_match


DEPENDENCY_TIMEOUT_SECONDS = 0.7
_RETRY_JITTER_MAX_SECONDS = 0.05
_TRACER = trace.get_tracer(__name__)


class IndexUnavailableError(RuntimeError):
    """Raised when retrieval has no verified active index."""

    def __init__(self) -> None:
        super().__init__("index_unavailable")


class DependencyTimeoutError(RuntimeError):
    """Raised when the bounded read dependency cannot complete."""

    def __init__(self) -> None:
        super().__init__("dependency_timeout")


class _ActiveIndexPort(Protocol):
    """Local structural requirements for a verified active retrieval index."""

    async def active_version(self) -> str | None: ...

    async def candidate_complete(self, index_version: str) -> bool: ...

    async def is_validated(self, index_version: str) -> bool: ...


class FeastRetrievalService:
    """Search one active index and re-load every cited immutable chunk."""

    def __init__(
        self,
        feast: FeastPort | None = None,
        *,
        embedder: EmbeddingPort | None = None,
        index_version: str = "unavailable",
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._feast = feast
        self._embedder = embedder
        del index_version
        self._clock = clock or (lambda: datetime.now(UTC))

    async def search(self, request: SearchRequest) -> SearchResponse:
        """Return verified matches or a typed, non-fabricated abstention."""

        effective_at = request.effective_at or self._clock()
        started = perf_counter()
        with _TRACER.start_as_current_span("retrieval.search") as span:
            try:
                async with asyncio.timeout(DEPENDENCY_TIMEOUT_SECONDS):
                    index_version, matches = await self._retrieve_with_one_retry(
                        request,
                        effective_at,
                    )
            except TimeoutError as error:
                span.set_attribute("retrieval.outcome", "dependency_timeout")
                raise DependencyTimeoutError() from error

            span.set_attribute("retrieval.index_version", index_version)
            span.set_attribute("retrieval.match_count", len(matches))
            elapsed_ms = (perf_counter() - started) * 1000
            if not matches:
                return SearchResponse(
                    request_id=uuid4(),
                    index_version=index_version,
                    embedding_model="BAAI/bge-small-en-v1.5",
                    matches=[],
                    retrieval_ms=elapsed_ms,
                    abstained=True,
                    reason="no_matching_policy_row",
                )
            return SearchResponse(
                request_id=uuid4(),
                index_version=index_version,
                embedding_model="BAAI/bge-small-en-v1.5",
                matches=matches,
                retrieval_ms=elapsed_ms,
                abstained=False,
                reason=None,
            )

    async def get_verified_chunk(
        self,
        chunk_id: str,
        content_sha256: str,
    ) -> SearchMatch:
        """Expose one hash-bound active-chunk reload to downstream consumers."""

        if self._feast is None:
            raise IndexUnavailableError()
        reloaded = await self._feast.get_verified_chunk(
            chunk_id=chunk_id,
            content_sha256=content_sha256,
        )
        if reloaded is None:
            raise CitationIntegrityError("citation_not_found")
        verified = verify_knowledge_match(reloaded)
        if (
            verified.citation.chunk_id != chunk_id
            or verified.citation.content_sha256 != content_sha256
        ):
            raise CitationIntegrityError("citation_request_mismatch")
        return verified

    async def is_ready(self) -> bool:
        """Report whether an active, validated index dependency is available."""

        try:
            await self._active_index_version()
        except Exception:
            return False
        return True

    async def _retrieve_with_one_retry(
        self,
        request: SearchRequest,
        effective_at: datetime,
    ) -> tuple[str, list[SearchMatch]]:
        try:
            return await self._retrieve_once(request, effective_at)
        except ConnectionError:
            await asyncio.sleep(random.uniform(0.0, _RETRY_JITTER_MAX_SECONDS))
            try:
                return await self._retrieve_once(request, effective_at)
            except ConnectionError as error:
                raise DependencyTimeoutError() from error

    async def _retrieve_once(
        self,
        request: SearchRequest,
        effective_at: datetime,
    ) -> tuple[str, list[SearchMatch]]:
        if self._feast is None or self._embedder is None:
            raise IndexUnavailableError()
        index_version = await self._active_index_version()
        vector = await self._embedder.embed_query(request.query)
        matches = await self._feast.search_documents(
            vector,
            top_k=request.top_k,
            category=None if request.category is None else request.category.value,
            effective_at=effective_at,
        )
        verified = [
            await self._reload_ranked_match(match)
            for match in matches
        ]
        return index_version, verified

    async def _active_index_version(self) -> str:
        if self._embedder is None:
            raise IndexUnavailableError()
        feast = self._verified_active_index_port()
        active_version = feast.active_version()
        if not isawaitable(active_version):
            raise IndexUnavailableError()
        index_version = await active_version
        if not isinstance(index_version, str) or not index_version:
            raise IndexUnavailableError()
        for gate in (feast.candidate_complete, feast.is_validated):
            gate_result = gate(index_version)
            if not isawaitable(gate_result) or await gate_result is not True:
                raise IndexUnavailableError()
        return index_version

    def _verified_active_index_port(self) -> _ActiveIndexPort:
        if self._feast is None:
            raise IndexUnavailableError()
        for gate_name in ("active_version", "candidate_complete", "is_validated"):
            if not callable(getattr(self._feast, gate_name, None)):
                raise IndexUnavailableError()
        return cast(_ActiveIndexPort, self._feast)

    async def _reload_ranked_match(self, match: SearchMatch) -> SearchMatch:
        if self._feast is None:
            raise IndexUnavailableError()
        reloaded = await self._feast.get_verified_chunk(
            chunk_id=match.citation.chunk_id,
            content_sha256=match.citation.content_sha256,
        )
        return verify_reloaded_match(match, reloaded)


__all__ = [
    "DEPENDENCY_TIMEOUT_SECONDS",
    "DependencyTimeoutError",
    "FeastRetrievalService",
    "IndexUnavailableError",
]
