from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from vina_bim_shop.llm.api.retrieval import app as retrieval_app
from vina_bim_shop.llm.contracts import KnowledgeCitation, SearchMatch, SearchRequest
from vina_bim_shop.llm.retrieval import (
    DEPENDENCY_TIMEOUT_SECONDS,
    DependencyTimeoutError,
    FeastRetrievalService,
    IndexUnavailableError,
)
from vina_bim_shop.llm.safety import CitationIntegrityError


NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)


def _match(content: str = "Returns are accepted within thirty days.") -> SearchMatch:
    return SearchMatch(
        content=content,
        score=0.75,
        citation=KnowledgeCitation(
            chunk_id="a" * 64,
            document_id="returns-policy",
            category="returns",
            version="1.0.0",
            effective_from=datetime(2025, 1, 1, tzinfo=timezone.utc),
            effective_to=None,
            content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        ),
    )


class FakeEmbedder:
    def __init__(self) -> None:
        self.queries: list[str] = []

    async def embed_query(self, query: str) -> list[float]:
        self.queries.append(query)
        return [0.0] * 384


class FakeFeast:
    def __init__(
        self,
        *,
        matches: list[SearchMatch] | None = None,
        reloaded: dict[str, SearchMatch | None] | None = None,
        outcomes: list[object] | None = None,
        delay_seconds: float = 0.0,
        active_version: str | None = "active-index",
    ) -> None:
        self.matches = matches or []
        self.reloaded = reloaded or {
            match.citation.chunk_id: match for match in self.matches
        }
        self.outcomes = list(outcomes or [])
        self.delay_seconds = delay_seconds
        self.active = active_version
        self.search_calls = 0
        self.search_arguments: list[tuple[int, str | None, datetime]] = []
        self.reload_arguments: list[tuple[str, str]] = []

    async def active_version(self) -> str | None:
        return self.active

    async def candidate_complete(self, index_version: str) -> bool:
        return index_version == "active-index"

    async def is_validated(self, index_version: str) -> bool:
        return index_version == "active-index"

    async def search_documents(
        self,
        vector: list[float],
        *,
        top_k: int,
        category: str | None,
        effective_at: datetime,
    ) -> list[SearchMatch]:
        assert len(vector) == 384
        self.search_calls += 1
        self.search_arguments.append((top_k, category, effective_at))
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        if self.outcomes:
            outcome = self.outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome  # type: ignore[return-value]
        return self.matches

    async def get_verified_chunk(
        self,
        *,
        chunk_id: str,
        content_sha256: str,
    ) -> SearchMatch | None:
        self.reload_arguments.append((chunk_id, content_sha256))
        return self.reloaded.get(chunk_id)


@pytest.mark.parametrize(
    ("top_k", "valid"),
    [(0, False), (1, True), (4, True), (8, True), (9, False)],
)
def test_search_request_top_k_boundaries(top_k: int, valid: bool) -> None:
    if valid:
        assert SearchRequest(query="returns", top_k=top_k).top_k == top_k
    else:
        with pytest.raises(ValidationError):
            SearchRequest(query="returns", top_k=top_k)


@pytest.mark.parametrize(
    ("length", "valid"),
    [(0, False), (1, True), (2000, True), (2001, False)],
)
def test_search_request_query_length_boundaries(length: int, valid: bool) -> None:
    if valid:
        assert len(SearchRequest(query="q" * length).query) == length
    else:
        with pytest.raises(ValidationError):
            SearchRequest(query="q" * length)


@pytest.mark.asyncio
async def test_search_filters_and_reloads_every_ranked_citation() -> None:
    first = _match()
    second = _match("Shipping is free over the stated threshold.").model_copy(
        update={"score": 0.5, "citation": _match("Shipping is free over the stated threshold.").citation.model_copy(update={"chunk_id": "b" * 64, "document_id": "shipping-policy", "category": "shipping"})}
    )
    feast = FakeFeast(matches=[first, second])
    service = FeastRetrievalService(
        feast=feast,
        embedder=FakeEmbedder(),
        clock=lambda: NOW,
    )

    response = await service.search(
        SearchRequest(
            query="returns",
            top_k=4,
            category="returns",
            effective_at=NOW,
        )
    )

    assert response.index_version == "active-index"
    assert response.matches == [first, second]
    assert response.abstained is False
    assert response.reason is None
    assert feast.search_arguments == [(4, "returns", NOW)]
    assert feast.reload_arguments == [
        (first.citation.chunk_id, first.citation.content_sha256),
        (second.citation.chunk_id, second.citation.content_sha256),
    ]


@pytest.mark.asyncio
async def test_search_uses_utc_clock_when_effective_at_is_omitted() -> None:
    feast = FakeFeast(matches=[])
    service = FeastRetrievalService(
        feast=feast,
        embedder=FakeEmbedder(),
        clock=lambda: NOW,
    )

    response = await service.search(SearchRequest(query="returns"))

    assert response.abstained is True
    assert response.reason == "no_matching_policy_row"
    assert feast.search_arguments == [(4, None, NOW)]


@pytest.mark.asyncio
async def test_search_rejects_missing_active_index() -> None:
    service = FeastRetrievalService(feast=None, embedder=FakeEmbedder(), clock=lambda: NOW)

    with pytest.raises(IndexUnavailableError, match="index_unavailable"):
        await service.search(SearchRequest(query="returns"))


@pytest.mark.parametrize(
    "gate_name",
    ("active_version", "candidate_complete", "is_validated"),
)
@pytest.mark.asyncio
async def test_search_fails_closed_when_required_active_index_gate_is_absent(
    gate_name: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delattr(FakeFeast, gate_name)
    service = FeastRetrievalService(
        feast=FakeFeast(matches=[_match()]),
        embedder=FakeEmbedder(),
        index_version="active-index",
        clock=lambda: NOW,
    )

    with pytest.raises(IndexUnavailableError, match="index_unavailable"):
        await service.search(SearchRequest(query="returns"))


@pytest.mark.parametrize(
    "gate_name",
    ("active_version", "candidate_complete", "is_validated"),
)
@pytest.mark.asyncio
async def test_search_fails_closed_when_required_active_index_gate_is_not_callable(
    gate_name: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(FakeFeast, gate_name, object())
    service = FeastRetrievalService(
        feast=FakeFeast(matches=[_match()]),
        embedder=FakeEmbedder(),
        clock=lambda: NOW,
    )

    with pytest.raises(IndexUnavailableError, match="index_unavailable"):
        await service.search(SearchRequest(query="returns"))


@pytest.mark.asyncio
async def test_search_fails_closed_for_empty_active_alias() -> None:
    service = FeastRetrievalService(
        feast=FakeFeast(active_version=None),
        embedder=FakeEmbedder(),
        clock=lambda: NOW,
    )

    with pytest.raises(IndexUnavailableError, match="index_unavailable"):
        await service.search(SearchRequest(query="returns"))


@pytest.mark.asyncio
async def test_search_fails_closed_for_incomplete_active_candidate() -> None:
    service = FeastRetrievalService(
        feast=FakeFeast(active_version="candidate-index"),
        embedder=FakeEmbedder(),
        clock=lambda: NOW,
    )

    with pytest.raises(IndexUnavailableError, match="index_unavailable"):
        await service.search(SearchRequest(query="returns"))


@pytest.mark.asyncio
async def test_search_fails_closed_for_unvalidated_active_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def complete_candidate(_: FakeFeast, __: str) -> bool:
        return True

    monkeypatch.setattr(FakeFeast, "candidate_complete", complete_candidate)
    service = FeastRetrievalService(
        feast=FakeFeast(active_version="candidate-index"),
        embedder=FakeEmbedder(),
        clock=lambda: NOW,
    )

    with pytest.raises(IndexUnavailableError, match="index_unavailable"):
        await service.search(SearchRequest(query="returns"))


@pytest.mark.asyncio
async def test_search_retries_exactly_once_for_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    match = _match()
    feast = FakeFeast(matches=[match], outcomes=[ConnectionError("temporary"), [match]])
    monkeypatch.setattr("vina_bim_shop.llm.retrieval.random.uniform", lambda _a, _b: 0.0)
    service = FeastRetrievalService(feast=feast, embedder=FakeEmbedder(), clock=lambda: NOW)

    response = await service.search(SearchRequest(query="returns"))

    assert response.matches == [match]
    assert feast.search_calls == 2


@pytest.mark.asyncio
async def test_search_does_not_retry_non_connection_error() -> None:
    feast = FakeFeast(outcomes=[RuntimeError("backend rejected query")])
    service = FeastRetrievalService(feast=feast, embedder=FakeEmbedder(), clock=lambda: NOW)

    with pytest.raises(RuntimeError, match="backend rejected query"):
        await service.search(SearchRequest(query="returns"))

    assert feast.search_calls == 1


@pytest.mark.asyncio
async def test_search_enforces_the_exact_700_ms_dependency_deadline() -> None:
    feast = FakeFeast(delay_seconds=0.8)
    service = FeastRetrievalService(feast=feast, embedder=FakeEmbedder(), clock=lambda: NOW)

    assert DEPENDENCY_TIMEOUT_SECONDS == 0.7
    with pytest.raises(DependencyTimeoutError, match="dependency_timeout"):
        await service.search(SearchRequest(query="returns"))


@pytest.mark.asyncio
async def test_search_rejects_changed_reloaded_citation() -> None:
    original = _match()
    changed = _match("Tampered persisted content.")
    feast = FakeFeast(matches=[original], reloaded={original.citation.chunk_id: changed})
    service = FeastRetrievalService(feast=feast, embedder=FakeEmbedder(), clock=lambda: NOW)

    with pytest.raises(CitationIntegrityError, match="citation_reload_mismatch"):
        await service.search(SearchRequest(query="returns"))


@pytest.mark.asyncio
async def test_get_verified_chunk_rejects_a_self_consistent_wrong_citation() -> None:
    expected = _match()
    wrong = _match("Shipping terms differ from the requested returns policy.")
    wrong = wrong.model_copy(
        update={"citation": wrong.citation.model_copy(update={"chunk_id": "b" * 64})}
    )
    service = FeastRetrievalService(
        feast=FakeFeast(reloaded={expected.citation.chunk_id: wrong}),
        embedder=FakeEmbedder(),
        clock=lambda: NOW,
    )

    with pytest.raises(CitationIntegrityError, match="citation_request_mismatch"):
        await service.get_verified_chunk(
            expected.citation.chunk_id,
            expected.citation.content_sha256,
        )


def test_api_maps_service_errors_and_separates_liveness_from_readiness() -> None:
    original_service = retrieval_app.state.retrieval_service
    try:
        retrieval_app.state.retrieval_service = FeastRetrievalService(
            feast=None,
            embedder=FakeEmbedder(),
            clock=lambda: NOW,
        )
        client = TestClient(retrieval_app)

        assert client.get("/healthz").status_code == 200
        readiness = client.get("/readyz")
        assert readiness.status_code == 503
        assert readiness.json()["status"] == "not_ready"

        unavailable = client.post("/v1/retrieval/search", json={"query": "returns"})
        assert unavailable.status_code == 409
        assert unavailable.json()["code"] == "index_unavailable"
        assert set(unavailable.json()) == {"code", "message", "request_id"}

        metrics = client.get("/metrics")
        assert metrics.status_code == 200
        assert 'service="edai2-retrieval-agent"' in metrics.text
        assert 'route="/v1/retrieval/search"' in metrics.text
        assert 'status="409"' in metrics.text
    finally:
        retrieval_app.state.retrieval_service = original_service


def test_api_returns_validation_and_timeout_errors_without_fabricating_matches() -> None:
    original_service = retrieval_app.state.retrieval_service
    try:
        retrieval_app.state.retrieval_service = FeastRetrievalService(
            feast=FakeFeast(delay_seconds=0.8),
            embedder=FakeEmbedder(),
            clock=lambda: NOW,
        )
        client = TestClient(retrieval_app)

        invalid = client.post("/v1/retrieval/search", json={"query": "", "top_k": 0})
        assert invalid.status_code == 422
        assert invalid.json()["code"] == "validation_error"

        timeout = client.post("/v1/retrieval/search", json={"query": "returns"})
        assert timeout.status_code == 503
        assert timeout.json()["code"] == "dependency_timeout"
    finally:
        retrieval_app.state.retrieval_service = original_service
