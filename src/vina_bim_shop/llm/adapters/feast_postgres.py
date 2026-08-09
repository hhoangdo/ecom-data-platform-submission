"""PostgreSQL-owned candidate storage and exact pgvector retrieval."""

from __future__ import annotations

import hashlib
import inspect
import json
import math
import csv
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


class Section03AdapterError(RuntimeError):
    """Raised when the activation-only PostgreSQL/Feast/Valkey seam is incomplete."""


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
        feast_apply: Callable[[str | None], Any] | None = None,
        valkey_materialize: Callable[[str | None], Any] | None = None,
        feast_fingerprint: Callable[[], Any] | None = None,
        valkey_fingerprint: Callable[[], Any] | None = None,
    ) -> None:
        self._dsn = dsn
        self._connection_factory = connection_factory
        self._feast_apply = feast_apply
        self._valkey_materialize = valkey_materialize
        self._feast_fingerprint = feast_fingerprint
        self._valkey_fingerprint = valkey_fingerprint

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
        """Read only the stable active daily-health view."""

        async with self._connection() as connection:
            rows = await _fetch_all(connection, """
                SELECT monitoring_date, feature_name, window_days, baseline_date,
                       customer_count, mean_value, psi_vs_baseline, drift_status
                FROM edai2_section03_health_active
                WHERE feature_name = %s
                  AND monitoring_date >= %s AND monitoring_date < %s
                ORDER BY monitoring_date
                """, (feature_name, window.start.date(), window.end.date()))
        return [FeatureHealthPoint.model_validate(row) for row in rows]

    async def read_customer_snapshot(
        self,
        *,
        id: str,
        as_of: UtcDateTime,
    ) -> Section03FeatureRow | None:
        """Read one cutoff-safe active snapshot without changing the source schema."""

        async with self._connection() as connection:
            rows = await _fetch_all(connection, """
                SELECT id, event_timestamp, label, f_customer_total_orders_90d,
                       f_customer_paid_revenue_90d, f_customer_avg_order_value_90d,
                       f_customer_distinct_categories_90d, f_stream_views_60m,
                       f_stream_add_to_cart_60m, f_stream_checkout_started_60m,
                       f_stream_order_placed_60m, f_stream_cart_to_purchase_ratio_60m, created
                FROM edai2_section03_training_active
                WHERE id = %s AND event_timestamp <= %s AND created <= event_timestamp
                ORDER BY event_timestamp DESC LIMIT 1
                """, (id, as_of))
        return None if not rows else Section03FeatureRow.model_validate(rows[0])

    async def active_section03_manifest_hash(self) -> str | None:
        """Return the active immutable Section 03 identity for readiness gates."""

        async with self._connection() as connection:
            rows = await _fetch_all(connection, "SELECT manifest_sha256 FROM edai2_section03_active_version WHERE singleton = TRUE", None)
        return None if not rows or rows[0]["manifest_sha256"] is None else str(rows[0]["manifest_sha256"])

    async def fingerprint(self) -> tuple[str | None, str, str]:
        """Read the three activation fingerprints without changing active state."""

        if self._feast_fingerprint is None or self._valkey_fingerprint is None:
            raise Section03AdapterError(
                "Section 03 activation requires explicit Feast and Valkey fingerprint readback hooks"
            )
        active = await self.active_section03_manifest_hash()
        feast = await _call_hook(self._feast_fingerprint, "Feast")
        valkey = await _call_hook(self._valkey_fingerprint, "Valkey")
        return (active, feast, valkey)

    async def staged_section03_manifest_hash(self, manifest_sha256: str) -> str | None:
        """Read back immutable staging before a view switch."""

        async with self._connection() as connection:
            rows = await _fetch_all(
                connection,
                "SELECT manifest_sha256 FROM edai2_section03_version WHERE manifest_sha256 = %s",
                (manifest_sha256,),
            )
        return None if not rows else str(rows[0]["manifest_sha256"])

    async def stage(self, verified: Any) -> None:
        """Insert immutable verified-version metadata under the advisory transaction lock."""

        consumer = verified.manifest["consumer_contract"]
        async with self._connection() as connection:
            async with connection.transaction():
                await connection.execute("SELECT pg_advisory_xact_lock(hashtextextended('edai2-section03-loader', 0))")
                await connection.execute(
                    """INSERT INTO edai2_section03_version
                       (manifest_sha256, label_sha256, training_sha256, health_sha256, feature_cutoff, baseline_date, training_count, health_count)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (manifest_sha256) DO NOTHING""",
                    (verified.manifest_sha256, consumer["label"]["sha256"], consumer["training_join"]["sha256"], consumer["feature_health"]["sha256"], consumer["training_join"]["feature_cutoff_ts"], consumer["feature_health"]["baseline_date"], verified.training_count, verified.health_count),
                )
                with verified.training_path.open("r", encoding="utf-8", newline="") as handle:
                    for row in csv.DictReader(handle):
                        await connection.execute("""INSERT INTO edai2_section03_training_row
                            (manifest_sha256, id, event_timestamp, label, f_customer_total_orders_90d, f_customer_paid_revenue_90d, f_customer_avg_order_value_90d, f_customer_distinct_categories_90d, f_stream_views_60m, f_stream_add_to_cart_60m, f_stream_checkout_started_60m, f_stream_order_placed_60m, f_stream_cart_to_purchase_ratio_60m, created)
                            VALUES (%(manifest)s,%(id)s,%(event_timestamp)s,%(label)s,%(f_customer_total_orders_90d)s,%(f_customer_paid_revenue_90d)s,%(f_customer_avg_order_value_90d)s,%(f_customer_distinct_categories_90d)s,%(f_stream_views_60m)s,%(f_stream_add_to_cart_60m)s,%(f_stream_checkout_started_60m)s,%(f_stream_order_placed_60m)s,%(f_stream_cart_to_purchase_ratio_60m)s,%(created)s) ON CONFLICT DO NOTHING""", {**row, "manifest": verified.manifest_sha256})
                with verified.health_path.open("r", encoding="utf-8", newline="") as handle:
                    for row in csv.DictReader(handle):
                        await connection.execute("""INSERT INTO edai2_section03_health_row
                            (manifest_sha256, monitoring_date, feature_name, window_days, baseline_date, customer_count, mean_value, stddev_value, psi_vs_baseline, drift_status, warning_flag, alert_flag)
                            VALUES (%(manifest)s,%(monitoring_date)s,%(feature_name)s,%(window_days)s,%(baseline_date)s,%(customer_count)s,%(mean_value)s,%(stddev_value)s,%(psi_vs_baseline)s,%(drift_status)s,%(warning_flag)s,%(alert_flag)s) ON CONFLICT DO NOTHING""", {**row, "manifest": verified.manifest_sha256})
                await self._verify_staged(connection, verified, consumer)

    async def _verify_staged(self, connection: Any, verified: Any, consumer: dict[str, Any]) -> None:
        """Refuse a same-hash candidate unless all immutable rows match the verified bundle."""

        metadata_rows = await _fetch_all(
            connection,
            """SELECT manifest_sha256, label_sha256, training_sha256, health_sha256,
                      feature_cutoff, baseline_date, training_count, health_count
               FROM edai2_section03_version WHERE manifest_sha256 = %s""",
            (verified.manifest_sha256,),
        )
        expected = {
            "manifest_sha256": verified.manifest_sha256,
            "label_sha256": consumer["label"]["sha256"],
            "training_sha256": consumer["training_join"]["sha256"],
            "health_sha256": consumer["feature_health"]["sha256"],
            "feature_cutoff": consumer["training_join"]["feature_cutoff_ts"],
            "baseline_date": consumer["feature_health"]["baseline_date"],
            "training_count": verified.training_count,
            "health_count": verified.health_count,
        }
        if not metadata_rows or any(
            _stored_value(metadata_rows[0].get(key)) != _stored_value(value)
            for key, value in expected.items()
        ):
            raise Section03AdapterError("Section 03 staged metadata mismatch")
        training_rows = await _fetch_all(
            connection,
            "SELECT COUNT(*) AS row_count FROM edai2_section03_training_row WHERE manifest_sha256 = %s",
            (verified.manifest_sha256,),
        )
        if not training_rows or int(training_rows[0]["row_count"]) != verified.training_count:
            raise Section03AdapterError("Section 03 staged training row count mismatch")
        health_rows = await _fetch_all(
            connection,
            "SELECT COUNT(*) AS row_count FROM edai2_section03_health_row WHERE manifest_sha256 = %s",
            (verified.manifest_sha256,),
        )
        if not health_rows or int(health_rows[0]["row_count"]) != verified.health_count:
            raise Section03AdapterError("Section 03 staged health row count mismatch")

    async def switch_active(self, manifest_sha256: str) -> str | None:
        """Transactionally repoint the stable active views to one immutable version."""

        async with self._connection() as connection:
            async with connection.transaction():
                await connection.execute("SELECT pg_advisory_xact_lock(hashtextextended('edai2-section03-loader', 0))")
                previous_rows = await _fetch_all(
                    connection,
                    "SELECT manifest_sha256 FROM edai2_section03_active_version WHERE singleton = TRUE FOR UPDATE",
                    None,
                )
                previous = None if not previous_rows else previous_rows[0]["manifest_sha256"]
                switched = await _fetch_all(
                    connection,
                    """UPDATE edai2_section03_active_version
                       SET manifest_sha256 = %s, updated_at = CURRENT_TIMESTAMP
                       WHERE singleton = TRUE AND manifest_sha256 IS NOT DISTINCT FROM %s
                       RETURNING manifest_sha256""",
                    (manifest_sha256, previous),
                )
                if not switched:
                    raise CandidateIndexError("Section 03 active hash changed before switch")
        return previous

    async def restore_active(self, manifest_sha256: str | None) -> None:
        """Compensate a failed post-switch activation back to the recorded prior hash."""

        async with self._connection() as connection:
            async with connection.transaction():
                await connection.execute("SELECT pg_advisory_xact_lock(hashtextextended('edai2-section03-loader', 0))")
                await connection.execute("UPDATE edai2_section03_active_version SET manifest_sha256 = %s, updated_at = CURRENT_TIMESTAMP WHERE singleton = TRUE", (manifest_sha256,))

    async def apply_feast(self, manifest_sha256: str | None) -> None:
        """Expose the named apply phase; runtime wiring supplies the actual Feast client."""

        if self._feast_apply is None:
            raise Section03AdapterError("a Feast apply hook is required for Section 03 activation")
        result = self._feast_apply(manifest_sha256)
        if inspect.isawaitable(result):
            await result

    async def materialize_valkey(self, manifest_sha256: str | None) -> None:
        """Expose the named online-materialization phase; runtime wiring supplies Valkey."""

        if self._valkey_materialize is None:
            raise Section03AdapterError("a Valkey materialization hook is required for Section 03 activation")
        result = self._valkey_materialize(manifest_sha256)
        if inspect.isawaitable(result):
            await result


async def _fetch_all(
    connection: Any,
    sql: str,
    parameters: tuple[object, ...] | None,
) -> list[dict[str, Any]]:
    cursor = await connection.execute(sql, parameters)
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def _call_hook(hook: Callable[[], Any], dependency: str) -> str:
    result = hook()
    if inspect.isawaitable(result):
        result = await result
    if not isinstance(result, str) or not result:
        raise Section03AdapterError(f"{dependency} fingerprint readback is invalid")
    return result


def _stored_value(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


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
    "Section03AdapterError",
    "StaleActiveAliasError",
]
