from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from vina_bim_shop.llm.adapters.feast_postgres import (
    CandidateIndexError,
    FeastPostgresAdapter,
    StaleActiveAliasError,
)
from vina_bim_shop.llm.contracts import (
    IndexBuildReport,
    KnowledgeCategory,
    KnowledgeChunk,
    KnowledgeDocumentVersion,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
EXTENSIONS_SQL = REPO_ROOT / "infra/postgres/edai2/001_extensions.sql"
INDEX_SQL = REPO_ROOT / "infra/postgres/edai2/002_knowledge_index.sql"


def _version() -> KnowledgeDocumentVersion:
    content = "Returns are accepted within thirty days."
    return KnowledgeDocumentVersion(
        source_path=Path("returns.md"),
        source_sha256="a" * 64,
        document_id="returns-policy",
        category=KnowledgeCategory.RETURNS,
        version="1.0.0",
        effective_from=datetime(2025, 1, 1, tzinfo=timezone.utc),
        effective_to=None,
        content=content,
        content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
    )


def _chunk(chunk_id: str = "b" * 64, content: str = "Returns are accepted.") -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id=chunk_id,
        source_sha256="a" * 64,
        document_id="returns-policy",
        category=KnowledgeCategory.RETURNS,
        version="1.0.0",
        effective_from=datetime(2025, 1, 1, tzinfo=timezone.utc),
        effective_to=None,
        ordinal=0,
        token_start=0,
        token_end=3,
        content=content,
        content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        tokenizer_model="BAAI/bge-small-en-v1.5",
        tokenizer_revision="5c38ec7c405ec4b44b94cc5a9bb96e735b38267a",
    )


def _report(chunk: KnowledgeChunk) -> IndexBuildReport:
    return IndexBuildReport(
        index_version="candidate-1",
        candidate_label="ci-bootstrap",
        document_count=8,
        document_version_count=9,
        chunk_count=1,
        embedding_dimension=384,
        source_sha256={"returns.md": "a" * 64},
        version_content_sha256={"returns-policy@1.0.0": "c" * 64},
        chunk_content_sha256={chunk.chunk_id: chunk.content_sha256},
        embedding_sha256={chunk.chunk_id: "d" * 64},
        embedding_model="BAAI/bge-small-en-v1.5",
        embedding_revision="5c38ec7c405ec4b44b94cc5a9bb96e735b38267a",
        tokenizer_model="BAAI/bge-small-en-v1.5",
        tokenizer_revision="5c38ec7c405ec4b44b94cc5a9bb96e735b38267a",
    )


class RecordingCursor:
    def __init__(self, connection: "RecordingConnection") -> None:
        self.connection = connection

    async def fetchall(self) -> list[dict[str, Any]]:
        return self.connection.rows.pop(0) if self.connection.rows else []


class RecordingTransaction:
    def __init__(self, connection: "RecordingConnection") -> None:
        self.connection = connection

    async def __aenter__(self) -> None:
        self.connection.transaction_count += 1

    async def __aexit__(self, *_args: object) -> None:
        return None


class RecordingConnection:
    def __init__(self, rows: list[list[dict[str, Any]]] | None = None) -> None:
        self.rows = rows or []
        self.statements: list[tuple[str, tuple[object, ...] | None]] = []
        self.transaction_count = 0

    def transaction(self) -> RecordingTransaction:
        return RecordingTransaction(self)

    async def execute(
        self, sql: str, parameters: tuple[object, ...] | None = None
    ) -> RecordingCursor:
        self.statements.append((sql, parameters))
        return RecordingCursor(self)

    async def close(self) -> None:
        return None


def test_migrations_own_pgvector_immutable_candidates_and_exact_scan() -> None:
    extension_sql = EXTENSIONS_SQL.read_text(encoding="utf-8")
    index_sql = INDEX_SQL.read_text(encoding="utf-8")
    combined = f"{extension_sql}\n{index_sql}".lower()

    assert "create extension if not exists vector" in combined
    assert "embedding vector(384)" in combined
    for table_name in [
        "edai2_rag_source",
        "edai2_rag_document_version",
        "edai2_rag_chunk",
        "edai2_rag_embedding",
        "edai2_rag_candidate_version",
        "edai2_rag_candidate_chunk",
        "edai2_rag_active_alias",
    ]:
        assert table_name in combined
    assert "btree" in combined
    assert "prevent_mutation" in combined
    assert "hnsw" not in combined
    assert "ivfflat" not in combined


@pytest.mark.asyncio
async def test_candidate_write_is_transactional_idempotent_and_rejects_bad_vectors() -> None:
    connection = RecordingConnection()
    adapter = FeastPostgresAdapter(connection_factory=lambda: connection)
    version = _version()
    chunk = _chunk()

    await adapter.upsert_candidate(
        index_version="candidate-1",
        versions=[version],
        chunks=[chunk],
        vectors=[[1.0] + [0.0] * 383],
        report=_report(chunk),
    )

    assert connection.transaction_count == 1
    statements = "\n".join(sql for sql, _params in connection.statements).lower()
    assert "insert into edai2_rag_candidate_version" in statements
    assert "insert into edai2_rag_embedding" in statements
    assert "on conflict" in statements

    with pytest.raises(CandidateIndexError, match="length 384"):
        await adapter.upsert_candidate(
            index_version="candidate-1",
            versions=[version],
            chunks=[chunk],
            vectors=[[1.0]],
            report=_report(chunk),
        )


@pytest.mark.asyncio
async def test_candidate_write_rejects_a_duplicate_document_version_with_new_content() -> None:
    connection = RecordingConnection(
        rows=[
            [],
            [{"source_sha256": "f" * 64, "content_sha256": "f" * 64}],
        ]
    )
    adapter = FeastPostgresAdapter(connection_factory=lambda: connection)
    version = _version()
    chunk = _chunk()

    with pytest.raises(CandidateIndexError, match="duplicate document version"):
        await adapter.upsert_candidate(
            index_version="candidate-1",
            versions=[version],
            chunks=[chunk],
            vectors=[[1.0] + [0.0] * 383],
            report=_report(chunk),
        )


@pytest.mark.asyncio
async def test_candidate_complete_requires_every_declared_member_embedding() -> None:
    connection = RecordingConnection(rows=[[{"complete": False}]])
    adapter = FeastPostgresAdapter(connection_factory=lambda: connection)

    assert await adapter.candidate_complete("candidate-1") is False

    query = connection.statements[0][0].lower()
    assert "candidate.chunk_count" in query
    assert "count(member.chunk_id)" in query
    assert "count(embedding.chunk_id)" in query
    assert "vector_dims(embedding.embedding) = 384" in query


@pytest.mark.asyncio
async def test_exact_query_filters_before_rank_and_keeps_chunk_id_ties_stable() -> None:
    rows = [
        [
            {
                "chunk_id": "b" * 64,
                "document_id": "returns-policy",
                "category": "returns",
                "version": "1.0.0",
                "effective_from": datetime(2025, 1, 1, tzinfo=timezone.utc),
                "effective_to": None,
                "content": "Second stable tie.",
                "content_sha256": "b" * 64,
                "cosine_distance": 0.25,
            },
            {
                "chunk_id": "a" * 64,
                "document_id": "returns-policy",
                "category": "returns",
                "version": "1.0.0",
                "effective_from": datetime(2025, 1, 1, tzinfo=timezone.utc),
                "effective_to": None,
                "content": "First stable tie.",
                "content_sha256": "a" * 64,
                "cosine_distance": 0.25,
            },
        ],
        [
            {
                "chunk_id": "a" * 64,
                "document_id": "returns-policy",
                "category": "returns",
                "version": "1.0.0",
                "effective_from": datetime(2025, 1, 1, tzinfo=timezone.utc),
                "effective_to": None,
                "content": "First stable tie.",
                "content_sha256": "a" * 64,
                "cosine_distance": 0.25,
            },
            {
                "chunk_id": "b" * 64,
                "document_id": "returns-policy",
                "category": "returns",
                "version": "1.0.0",
                "effective_from": datetime(2025, 1, 1, tzinfo=timezone.utc),
                "effective_to": None,
                "content": "Second stable tie.",
                "content_sha256": "b" * 64,
                "cosine_distance": 0.25,
            },
        ],
    ]
    connection = RecordingConnection(rows=rows)
    adapter = FeastPostgresAdapter(connection_factory=lambda: connection)
    vector = [1.0] + [0.0] * 383
    effective_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    direct = await adapter.search_documents(
        vector, top_k=2, category="returns", effective_at=effective_at
    )
    feast = await adapter.search_documents_via_feast(
        vector, top_k=2, category="returns", effective_at=effective_at
    )

    assert [match.citation.chunk_id for match in direct] == ["a" * 64, "b" * 64]
    assert direct == feast
    assert all(match.score == 0.75 for match in direct)
    query = connection.statements[0][0].lower()
    assert query.index("where") < query.index("order by")
    assert "embedding <=> %s::vector" in query
    assert "order by embedding.embedding <=> %s::vector, chunk.chunk_id" in query
    assert "effective_from <= %s" in query
    assert "chunk.effective_to is null or %s < chunk.effective_to" in query


@pytest.mark.asyncio
async def test_compare_and_swap_rejects_a_stale_alias() -> None:
    connection = RecordingConnection(rows=[[], [{"index_version": "candidate-2"}]])
    adapter = FeastPostgresAdapter(connection_factory=lambda: connection)

    with pytest.raises(StaleActiveAliasError):
        await adapter.compare_and_swap_active("candidate-0", "candidate-1")
    assert await adapter.compare_and_swap_active("candidate-1", "candidate-2") == "candidate-2"
