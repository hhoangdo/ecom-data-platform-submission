"""PostgreSQL-owned candidate storage and exact pgvector retrieval."""

from __future__ import annotations

import hashlib
import inspect
import json
import math
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from ..contracts import (
    FeatureHealthPoint,
    IndexBuildReport,
    IndexValidationReport,
    KnowledgeChunk,
    KnowledgeDocumentVersion,
    SearchMatch,
    Section03FeatureRow,
    TimeWindow,
    UtcDateTime,
)


class CandidateIndexError(ValueError):
    """Raised when a candidate cannot satisfy immutable storage rules."""


class StaleActiveAliasError(RuntimeError):
    """Raised when a compare-and-swap sees a different active index."""


ConnectionFactory = Callable[[], Any]


class FeastPostgresAdapter:
    """Own candidate writes, the active alias, and one exact search query.

    Importing this adapter is side-effect free.  A real connection is opened only
    when a DSN or a test-owned ``connection_factory`` is supplied, which keeps
    the local contract suite independent from the host libpq installation.
    """

    def __init__(
        self,
        *,
        dsn: str | None = None,
        connection_factory: ConnectionFactory | None = None,
    ) -> None:
        self._dsn = dsn
        self._connection_factory = connection_factory

    @asynccontextmanager
    async def _connection(self) -> AsyncIterator[Any]:
        connection: Any
        if self._connection_factory is not None:
            connection = self._connection_factory()
            if inspect.isawaitable(connection):
                connection = await connection
        else:
            if not self._dsn:
                raise CandidateIndexError(
                    "a PostgreSQL DSN or test-owned connection factory is required"
                )
            try:
                import psycopg
            except ImportError as error:  # pragma: no cover - host capability gate
                raise CandidateIndexError(
                    "psycopg/libpq is unavailable for a real PostgreSQL connection"
                ) from error
            connection = await psycopg.AsyncConnection.connect(self._dsn)
        try:
            yield connection
        finally:
            close = getattr(connection, "close", None)
            if close is not None:
                result = close()
                if inspect.isawaitable(result):
                    await result

    async def upsert_candidate(
        self,
        *,
        index_version: str,
        versions: Sequence[KnowledgeDocumentVersion],
        chunks: Sequence[KnowledgeChunk],
        vectors: Sequence[Sequence[float]],
        report: IndexBuildReport,
    ) -> None:
        """Write one immutable candidate atomically and idempotently."""

        if not index_version or report.index_version != index_version:
            raise CandidateIndexError("candidate report and requested index version differ")
        if len(chunks) != len(vectors):
            raise CandidateIndexError("embedding count does not match candidate chunks")
        normalized_vectors = [_validated_vector(vector) for vector in vectors]
        candidate_sha256 = _candidate_digest(report)

        async with self._connection() as connection:
            async with connection.transaction():
                existing = await _fetch_all(
                    connection,
                    """
                    SELECT candidate_sha256
                    FROM edai2_rag_candidate_version
                    WHERE index_version = %s
                    """,
                    (index_version,),
                )
                if existing:
                    stored_digest = str(existing[0]["candidate_sha256"])
                    if stored_digest != candidate_sha256:
                        raise CandidateIndexError(
                            "duplicate candidate version has different content"
                        )

                await connection.execute(
                    """
                    INSERT INTO edai2_rag_candidate_version
                        (index_version, candidate_sha256, document_count,
                         document_version_count, chunk_count, embedding_dimension)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (index_version) DO NOTHING
                    """,
                    (
                        index_version,
                        candidate_sha256,
                        report.document_count,
                        report.document_version_count,
                        report.chunk_count,
                        report.embedding_dimension,
                    ),
                )
                for version in versions:
                    existing_version = await _fetch_all(
                        connection,
                        """
                        SELECT source_sha256, content_sha256
                        FROM edai2_rag_document_version
                        WHERE document_id = %s AND version = %s
                        """,
                        (version.document_id, version.version),
                    )
                    if existing_version and (
                        str(existing_version[0]["source_sha256"])
                        != version.source_sha256
                        or str(existing_version[0]["content_sha256"])
                        != version.content_sha256
                    ):
                        raise CandidateIndexError(
                            "duplicate document version has different immutable content"
                        )
                    await connection.execute(
                        """
                        INSERT INTO edai2_rag_source (source_sha256, source_path)
                        VALUES (%s, %s)
                        ON CONFLICT (source_sha256) DO NOTHING
                        """,
                        (version.source_sha256, version.source_path.as_posix()),
                    )
                    await connection.execute(
                        """
                        INSERT INTO edai2_rag_document_version
                            (document_id, version, source_sha256, category,
                             effective_from, effective_to, content, content_sha256)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (document_id, version) DO NOTHING
                        """,
                        (
                            version.document_id,
                            version.version,
                            version.source_sha256,
                            version.category.value,
                            version.effective_from,
                            version.effective_to,
                            version.content,
                            version.content_sha256,
                        ),
                    )
                for chunk, vector in zip(chunks, normalized_vectors, strict=True):
                    await connection.execute(
                        """
                        INSERT INTO edai2_rag_chunk
                            (chunk_id, document_id, version, source_sha256, category,
                             effective_from, effective_to, ordinal, token_start, token_end,
                             content, content_sha256, tokenizer_model, tokenizer_revision)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (chunk_id) DO NOTHING
                        """,
                        (
                            chunk.chunk_id,
                            chunk.document_id,
                            chunk.version,
                            chunk.source_sha256,
                            chunk.category.value,
                            chunk.effective_from,
                            chunk.effective_to,
                            chunk.ordinal,
                            chunk.token_start,
                            chunk.token_end,
                            chunk.content,
                            chunk.content_sha256,
                            chunk.tokenizer_model,
                            chunk.tokenizer_revision,
                        ),
                    )
                    await connection.execute(
                        """
                        INSERT INTO edai2_rag_embedding
                            (chunk_id, embedding, embedding_sha256, embedding_model,
                             embedding_revision)
                        VALUES (%s, %s::vector, %s, %s, %s)
                        ON CONFLICT (chunk_id) DO NOTHING
                        """,
                        (
                            chunk.chunk_id,
                            _vector_literal(vector),
                            report.embedding_sha256[chunk.chunk_id],
                            report.embedding_model,
                            report.embedding_revision,
                        ),
                    )
                    await connection.execute(
                        """
                        INSERT INTO edai2_rag_candidate_chunk (index_version, chunk_id)
                        VALUES (%s, %s)
                        ON CONFLICT (index_version, chunk_id) DO NOTHING
                        """,
                        (index_version, chunk.chunk_id),
                    )

    async def register_feast_feature_view(self, index_version: str) -> str:
        """Return the declared Feast service identity without constructing an index."""

        if not index_version:
            raise CandidateIndexError("index version is required for Feast registration")
        return f"ecommerce_knowledge_retrieval:{index_version}"

    async def candidate_complete(self, index_version: str) -> bool:
        """Confirm that a candidate has immutable member chunks before validation."""

        async with self._connection() as connection:
            rows = await _fetch_all(
                connection,
                """
                SELECT
                    COUNT(member.chunk_id) = candidate.chunk_count
                    AND COUNT(embedding.chunk_id) = candidate.chunk_count
                    AND COALESCE(
                        BOOL_AND(vector_dims(embedding.embedding) = 384),
                        FALSE
                    ) AS complete
                FROM edai2_rag_candidate_version candidate
                LEFT JOIN edai2_rag_candidate_chunk member
                  ON member.index_version = candidate.index_version
                LEFT JOIN edai2_rag_embedding embedding
                  ON embedding.chunk_id = member.chunk_id
                WHERE candidate.index_version = %s
                GROUP BY candidate.index_version, candidate.chunk_count
                """,
                (index_version,),
            )
        return bool(rows and rows[0]["complete"])

    async def mark_validated(
        self, index_version: str, report: IndexValidationReport
    ) -> None:
        """Persist an explicit successful validation gate for later CAS promotion."""

        if not report.passed:
            raise CandidateIndexError("failed candidate validation cannot be recorded")
        async with self._connection() as connection:
            async with connection.transaction():
                await connection.execute(
                    """
                    UPDATE edai2_rag_candidate_version
                    SET validation_sha256 = %s, validated_at = CURRENT_TIMESTAMP
                    WHERE index_version = %s
                    """,
                    (_validation_digest(report), index_version),
                )

    async def is_validated(self, index_version: str) -> bool:
        """Return whether a candidate has a recorded successful validation."""

        async with self._connection() as connection:
            rows = await _fetch_all(
                connection,
                """
                SELECT validation_sha256 IS NOT NULL AS validated
                FROM edai2_rag_candidate_version
                WHERE index_version = %s
                """,
                (index_version,),
            )
        return bool(rows and rows[0]["validated"])

    async def active_version(self) -> str | None:
        """Read the one active alias without changing it."""

        async with self._connection() as connection:
            rows = await _fetch_all(
                connection,
                """
                SELECT index_version
                FROM edai2_rag_active_alias
                WHERE alias_name = 'active'
                """,
                None,
            )
        return None if not rows else rows[0]["index_version"]

    async def compare_and_swap_active(
        self, expected: str | None, next_version: str | None
    ) -> str | None:
        """Atomically set the active alias only when its prior value matches."""

        async with self._connection() as connection:
            async with connection.transaction():
                rows = await _fetch_all(
                    connection,
                    """
                    UPDATE edai2_rag_active_alias
                    SET index_version = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE alias_name = 'active'
                      AND index_version IS NOT DISTINCT FROM %s
                    RETURNING index_version
                    """,
                    (next_version, expected),
                )
        if not rows:
            raise StaleActiveAliasError("active alias no longer matches the expected version")
        return rows[0]["index_version"]

    async def search_documents(
        self,
        vector: Sequence[float],
        *,
        top_k: int,
        category: str | None,
        effective_at: UtcDateTime,
    ) -> list[SearchMatch]:
        """Search active chunks with one exact filtered cosine query."""

        return await self._search_exact(
            vector, top_k=top_k, category=category, effective_at=effective_at
        )

    async def search_documents_via_feast(
        self,
        vector: Sequence[float],
        *,
        top_k: int,
        category: str | None,
        effective_at: UtcDateTime,
    ) -> list[SearchMatch]:
        """Use the same PostgreSQL query behind the declared Feast boundary."""

        return await self._search_exact(
            vector, top_k=top_k, category=category, effective_at=effective_at
        )

    async def get_verified_chunk(
        self,
        *,
        chunk_id: str,
        content_sha256: str,
    ) -> SearchMatch | None:
        """Reload one active, hash-bound citation without similarity ranking."""

        async with self._connection() as connection:
            rows = await _fetch_all(
                connection,
                """
                SELECT chunk.chunk_id, chunk.document_id, chunk.category, chunk.version,
                       chunk.effective_from, chunk.effective_to, chunk.content,
                       chunk.content_sha256
                FROM edai2_rag_active_alias alias
                JOIN edai2_rag_candidate_chunk candidate
                  ON candidate.index_version = alias.index_version
                JOIN edai2_rag_chunk chunk ON chunk.chunk_id = candidate.chunk_id
                WHERE alias.alias_name = 'active'
                  AND chunk.chunk_id = %s
                  AND chunk.content_sha256 = %s
                LIMIT 1
                """,
                (chunk_id, content_sha256),
            )
        if not rows:
            return None
        row = rows[0]
        return SearchMatch(
            content=str(row["content"]),
            score=1.0,
            citation={
                "chunk_id": str(row["chunk_id"]),
                "document_id": str(row["document_id"]),
                "category": str(row["category"]),
                "version": str(row["version"]),
                "effective_from": row["effective_from"],
                "effective_to": row["effective_to"],
                "content_sha256": str(row["content_sha256"]),
            },
        )

    async def _search_exact(
        self,
        vector: Sequence[float],
        *,
        top_k: int,
        category: str | None,
        effective_at: UtcDateTime,
    ) -> list[SearchMatch]:
        if not 1 <= top_k <= 8:
            raise CandidateIndexError("top_k must be between 1 and 8")
        query_vector = _vector_literal(_validated_vector(vector))
        async with self._connection() as connection:
            rows = await _fetch_all(
                connection,
                """
                SELECT chunk.chunk_id, chunk.document_id, chunk.category, chunk.version,
                       chunk.effective_from, chunk.effective_to, chunk.content,
                       chunk.content_sha256,
                       embedding.embedding <=> %s::vector AS cosine_distance
                FROM edai2_rag_active_alias alias
                JOIN edai2_rag_candidate_chunk candidate
                  ON candidate.index_version = alias.index_version
                JOIN edai2_rag_chunk chunk ON chunk.chunk_id = candidate.chunk_id
                JOIN edai2_rag_embedding embedding ON embedding.chunk_id = chunk.chunk_id
                WHERE alias.alias_name = 'active'
                  AND (%s::text IS NULL OR chunk.category = %s)
                  AND chunk.effective_from <= %s
                  AND (chunk.effective_to IS NULL OR %s < chunk.effective_to)
                ORDER BY embedding.embedding <=> %s::vector, chunk.chunk_id
                LIMIT %s
                """,
                (
                    query_vector,
                    category,
                    category,
                    effective_at,
                    effective_at,
                    query_vector,
                    top_k,
                ),
            )
        ordered = sorted(
            rows,
            key=lambda row: (float(row["cosine_distance"]), str(row["chunk_id"])),
        )
        return [
            SearchMatch(
                content=str(row["content"]),
                score=float(1.0 - float(row["cosine_distance"])),
                citation={
                    "chunk_id": str(row["chunk_id"]),
                    "document_id": str(row["document_id"]),
                    "category": str(row["category"]),
                    "version": str(row["version"]),
                    "effective_from": row["effective_from"],
                    "effective_to": row["effective_to"],
                    "content_sha256": str(row["content_sha256"]),
                },
            )
            for row in ordered
        ]

    async def read_feature_health(
        self,
        *,
        feature_name: str,
        window: TimeWindow,
    ) -> Sequence[FeatureHealthPoint]:
        """Reserve Section 03 reads for the dedicated successor topic."""

        raise NotImplementedError("Feast feature reads belong to the Section 03 loader")

    async def read_customer_snapshot(
        self,
        *,
        id: str,
        as_of: UtcDateTime,
    ) -> Section03FeatureRow | None:
        """Reserve point-in-time Section 03 reads for the successor topic."""

        raise NotImplementedError("Section 03 point-in-time reads belong to the loader")


async def _fetch_all(
    connection: Any,
    sql: str,
    parameters: tuple[object, ...] | None,
) -> list[dict[str, Any]]:
    cursor = await connection.execute(sql, parameters)
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


def _validated_vector(vector: Sequence[float]) -> list[float]:
    values = [float(value) for value in vector]
    if len(values) != 384:
        raise CandidateIndexError("embedding vector must have length 384")
    if not all(math.isfinite(value) for value in values):
        raise CandidateIndexError("embedding vector must be finite")
    return values


def _vector_literal(vector: Sequence[float]) -> str:
    return "[" + ",".join(format(value, ".9g") for value in vector) + "]"


def _candidate_digest(report: IndexBuildReport) -> str:
    return hashlib.sha256(
        json.dumps(
            report.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _validation_digest(report: IndexValidationReport) -> str:
    return hashlib.sha256(
        json.dumps(
            report.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


__all__ = [
    "CandidateIndexError",
    "FeastPostgresAdapter",
    "StaleActiveAliasError",
]
