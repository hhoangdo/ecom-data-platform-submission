"""Trusted-source parsing boundaries for the local EDAI2 RAG candidate."""

from __future__ import annotations

import hashlib
import json
import math
import re
import struct
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol, Sequence

from .contracts import (
    IndexBuildReport,
    IndexValidationReport,
    KnowledgeCategory,
    KnowledgeChunk,
    KnowledgeDocumentVersion,
)
from .ports import EmbeddingPort


EXPECTED_SOURCE_FILES = (
    "returns.md",
    "shipping.md",
    "cancellation.md",
    "payments.md",
    "promotions.md",
    "warranties.md",
    "privacy.md",
    "marketplace_support.md",
)
HEADER_KEYS = (
    "document_id",
    "category",
    "version",
    "effective_from",
    "effective_to",
)
VERSION_SEPARATOR = "<!-- version-separator -->\n"
DOCUMENT_ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
SEMVER_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
RFC3339_UTC_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$"
)
ENGLISH_WORD_PATTERN = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
BGE_MODEL = "BAAI/bge-small-en-v1.5"
BGE_REVISION = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class SourceParseError(ValueError):
    """Raised when a trusted source breaks the locked source contract."""


class EmbeddingValidationError(ValueError):
    """Raised when a pinned BGE embedding violates its local contract."""


class CandidateValidationError(RuntimeError):
    """Raised when a candidate cannot pass the validation or promotion gate."""


class CandidateStorePort(Protocol):
    """Storage and alias operations required by the candidate-index pipeline."""

    async def upsert_candidate(
        self,
        *,
        index_version: str,
        versions: Sequence[KnowledgeDocumentVersion],
        chunks: Sequence[KnowledgeChunk],
        vectors: Sequence[Sequence[float]],
        report: IndexBuildReport,
    ) -> None: ...

    async def register_feast_feature_view(self, index_version: str) -> str: ...

    async def candidate_complete(self, index_version: str) -> bool: ...

    async def mark_validated(
        self, index_version: str, report: IndexValidationReport
    ) -> None: ...

    async def is_validated(self, index_version: str) -> bool: ...

    async def active_version(self) -> str | None: ...

    async def compare_and_swap_active(
        self, expected: str | None, next_version: str | None
    ) -> str | None: ...


class IndexCatalogPort(Protocol):
    """Lineage operations required by the candidate-index pipeline."""

    async def emit_candidate(
        self,
        *,
        report: IndexBuildReport,
        versions: Sequence[KnowledgeDocumentVersion],
        chunks: Sequence[KnowledgeChunk],
    ) -> str: ...

    async def emit_active(
        self,
        *,
        index_version: str,
        previous_index_version: str | None,
    ) -> str: ...

    async def emit_rollback(
        self,
        *,
        failed_index_version: str,
        restored_index_version: str | None,
        reason: str,
    ) -> str: ...

    async def read_back(self, *, index_version: str) -> bool: ...


class PinnedBgeEmbedder:
    """Encode candidate passages and queries with the immutable BGE revision."""

    def __init__(
        self,
        *,
        model_name: str = BGE_MODEL,
        revision: str = BGE_REVISION,
        model_loader: Callable[[str, str], object] | None = None,
    ) -> None:
        if model_name != BGE_MODEL or revision != BGE_REVISION:
            raise EmbeddingValidationError("BGE model and revision must be immutable")
        self._model_name = model_name
        self._revision = revision
        self._model_loader = model_loader or _load_sentence_transformer
        self._model: object | None = None

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed passage text without a retrieval prefix."""

        return self._encode(list(texts))

    async def embed_query(self, query: str) -> list[float]:
        """Embed one query with BGE's exact retrieval prefix."""

        return self._encode([QUERY_PREFIX + query])[0]

    def _encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._get_model()
        vectors = model.encode(  # type: ignore[attr-defined]
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        if len(vectors) != len(texts):
            raise EmbeddingValidationError("embedding count does not match text count")
        return [_validated_vector(vector) for vector in vectors]

    def _get_model(self) -> object:
        if self._model is None:
            self._model = self._model_loader(self._model_name, self._revision)
        return self._model


def _load_sentence_transformer(model_name: str, revision: str) -> object:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(
        model_name,
        revision=revision,
        local_files_only=True,
    )


def _validated_vector(vector: Sequence[float]) -> list[float]:
    values = [float(value) for value in vector]
    if len(values) != 384:
        raise EmbeddingValidationError("embedding vector must have length 384")
    if not all(math.isfinite(value) for value in values):
        raise EmbeddingValidationError("embedding vector must be finite")
    norm = math.sqrt(sum(value * value for value in values))
    if not math.isclose(norm, 1.0, rel_tol=1e-6, abs_tol=1e-6):
        raise EmbeddingValidationError("embedding vector must be normalized")
    return values


def parse_sources(source_root: str | Path) -> list[KnowledgeDocumentVersion]:
    """Parse the exact canonical source inventory in deterministic path order."""

    root = Path(source_root)
    if not root.is_dir():
        raise SourceParseError(f"source root does not exist: {root}")

    paths = tuple(sorted(path for path in root.iterdir() if path.is_file()))
    if {path.name for path in paths} != set(EXPECTED_SOURCE_FILES):
        raise SourceParseError("source inventory must contain exactly eight expected files")

    records: list[KnowledgeDocumentVersion] = []
    for filename in EXPECTED_SOURCE_FILES:
        path = root / filename
        records.extend(_parse_source_file(path))

    if len(records) != 9:
        raise SourceParseError("source inventory must contain exactly nine versions")
    if len({(record.document_id, record.version) for record in records}) != len(records):
        raise SourceParseError("document/version pairs must be unique")
    return records


def resolve_effective_version(
    records: Sequence[KnowledgeDocumentVersion],
    document_id: str,
    effective_at: datetime,
) -> KnowledgeDocumentVersion:
    """Return the sole version eligible at a timezone-aware UTC instant."""

    if effective_at.tzinfo is None or effective_at.utcoffset() != timezone.utc.utcoffset(
        effective_at
    ):
        raise SourceParseError("effective_at must be timezone-aware UTC")

    eligible = [
        record
        for record in records
        if record.document_id == document_id
        and record.effective_from <= effective_at
        and (record.effective_to is None or effective_at < record.effective_to)
    ]
    if len(eligible) != 1:
        raise SourceParseError("effective date must select exactly one document version")
    return eligible[0]


def build_chunks(
    versions: Sequence[KnowledgeDocumentVersion],
    *,
    tokenizer: object,
    tokenizer_model: str,
    tokenizer_revision: str,
) -> list[KnowledgeChunk]:
    """Create deterministic 400-token windows for each version independently."""

    if tokenizer_model != BGE_MODEL:
        raise SourceParseError("tokenizer model must be the pinned BGE model")
    if not re.fullmatch(r"[0-9a-f]{40}", tokenizer_revision):
        raise SourceParseError("tokenizer revision must be an immutable SHA")

    chunks: list[KnowledgeChunk] = []
    for version in versions:
        canonical_content = unicodedata.normalize("NFC", version.content)
        token_ids = tokenizer.encode(canonical_content, add_special_tokens=False)  # type: ignore[attr-defined]
        if not token_ids:
            raise SourceParseError("tokenizer produced no tokens for a document version")
        for ordinal, token_start in enumerate(range(0, len(token_ids), 320)):
            token_end = min(token_start + 400, len(token_ids))
            content = tokenizer.decode(  # type: ignore[attr-defined]
                token_ids[token_start:token_end],
                skip_special_tokens=False,
                clean_up_tokenization_spaces=False,
            )
            content_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
            chunks.append(
                KnowledgeChunk(
                    chunk_id=canonical_chunk_id(
                        document_id=version.document_id,
                        version=version.version,
                        ordinal=ordinal,
                        token_start=token_start,
                        token_end=token_end,
                        content_sha256=content_sha256,
                        tokenizer_revision=tokenizer_revision,
                    ),
                    source_sha256=version.source_sha256,
                    document_id=version.document_id,
                    category=version.category,
                    version=version.version,
                    effective_from=version.effective_from,
                    effective_to=version.effective_to,
                    ordinal=ordinal,
                    token_start=token_start,
                    token_end=token_end,
                    content=content,
                    content_sha256=content_sha256,
                    tokenizer_model=tokenizer_model,
                    tokenizer_revision=tokenizer_revision,
                )
            )
    return chunks


def canonical_chunk_id(
    *,
    document_id: str,
    version: str,
    ordinal: int,
    token_start: int,
    token_end: int,
    content_sha256: str,
    tokenizer_revision: str,
) -> str:
    """Hash the RFC 8785-compatible JSON identity for one token window."""

    payload = {
        "document_id": document_id,
        "version": version,
        "ordinal": ordinal,
        "token_start": token_start,
        "token_end": token_end,
        "content_sha256": content_sha256,
        "tokenizer_revision": tokenizer_revision,
    }
    canonical_json = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def _parse_source_file(path: Path) -> list[KnowledgeDocumentVersion]:
    raw = path.read_bytes()
    _validate_source_bytes(path, raw)
    text = raw.decode("utf-8")
    source_sha256 = hashlib.sha256(raw).hexdigest()
    expected_category = KnowledgeCategory(path.stem)

    if path.name == "returns.md":
        if text.count(VERSION_SEPARATOR) != 1:
            raise SourceParseError("returns.md must contain exactly one version separator")
        record_texts = text.split(VERSION_SEPARATOR)
        if len(record_texts) != 2:
            raise SourceParseError("returns.md must contain exactly two records")
    else:
        if "<!-- version-separator -->" in text:
            raise SourceParseError("only returns.md may contain a version separator")
        record_texts = [text]

    records = [
        _parse_record(
            record_text,
            source_path=path,
            source_sha256=source_sha256,
            expected_category=expected_category,
            word_minimum=150 if path.name == "returns.md" else 300,
            word_maximum=350 if path.name == "returns.md" else 700,
        )
        for record_text in record_texts
    ]

    if path.name == "returns.md":
        _validate_returns_versions(records)
    elif len(records) != 1 or records[0].effective_to is not None:
        raise SourceParseError("single-record sources must have one current version")

    return records


def _validate_source_bytes(path: Path, raw: bytes) -> None:
    if raw.startswith(b"\xef\xbb\xbf"):
        raise SourceParseError(f"{path.name} must not contain a UTF-8 BOM")
    if b"\r" in raw:
        raise SourceParseError(f"{path.name} must use LF-only line endings")
    if not raw.endswith(b"\n"):
        raise SourceParseError(f"{path.name} must end with a newline")


def _parse_record(
    text: str,
    *,
    source_path: Path,
    source_sha256: str,
    expected_category: KnowledgeCategory,
    word_minimum: int,
    word_maximum: int,
) -> KnowledgeDocumentVersion:
    if not text.startswith("---\n"):
        raise SourceParseError(f"{source_path.name} contains text outside a record")
    header_end = text.find("\n---\n", len("---\n"))
    if header_end == -1:
        raise SourceParseError(f"{source_path.name} has malformed front matter")

    header = text[len("---\n") : header_end]
    body = text[header_end + len("\n---\n") :]
    if not body:
        raise SourceParseError(f"{source_path.name} record body is required")

    fields = _parse_header(header, source_path)
    document_id = fields["document_id"]
    if not DOCUMENT_ID_PATTERN.fullmatch(document_id):
        raise SourceParseError("document_id must be stable kebab-case")
    if not SEMVER_PATTERN.fullmatch(fields["version"]):
        raise SourceParseError("version must be SemVer")

    try:
        category = KnowledgeCategory(fields["category"])
    except ValueError as error:
        raise SourceParseError("category is not allowlisted") from error
    if category != expected_category:
        raise SourceParseError("category must match the source filename")

    effective_from = _parse_utc(fields["effective_from"])
    effective_to = (
        None if fields["effective_to"] == "null" else _parse_utc(fields["effective_to"])
    )
    if effective_to is not None and effective_from >= effective_to:
        raise SourceParseError("effective window must be non-empty")

    content = unicodedata.normalize("NFC", body)
    word_count = len(ENGLISH_WORD_PATTERN.findall(content))
    if not word_minimum <= word_count <= word_maximum:
        raise SourceParseError(
            f"{source_path.name} body word count {word_count} is outside "
            f"{word_minimum}-{word_maximum}"
        )

    return KnowledgeDocumentVersion(
        source_path=source_path,
        source_sha256=source_sha256,
        document_id=document_id,
        category=category,
        version=fields["version"],
        effective_from=effective_from,
        effective_to=effective_to,
        content=content,
        content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
    )


def _parse_header(header: str, source_path: Path) -> dict[str, str]:
    lines = header.split("\n")
    if len(lines) != len(HEADER_KEYS):
        raise SourceParseError(f"{source_path.name} has unknown or missing metadata")

    fields: dict[str, str] = {}
    for key, line in zip(HEADER_KEYS, lines, strict=True):
        prefix = f"{key}: "
        if not line.startswith(prefix) or not line[len(prefix) :]:
            raise SourceParseError(f"{source_path.name} has malformed {key}")
        fields[key] = line[len(prefix) :]
    return fields


def _parse_utc(value: str) -> datetime:
    if not RFC3339_UTC_PATTERN.fullmatch(value):
        raise SourceParseError("timestamp must be RFC3339 UTC with Z suffix")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise SourceParseError("timestamp is invalid") from error


def _validate_returns_versions(records: Sequence[KnowledgeDocumentVersion]) -> None:
    if len(records) != 2:
        raise SourceParseError("returns.md must contain exactly two versions")
    historical, current = records
    if (
        historical.document_id != current.document_id
        or historical.category != current.category
        or historical.version == current.version
        or historical.effective_to != current.effective_from
        or current.effective_to is not None
    ):
        raise SourceParseError("returns versions must be adjacent, distinct, and current")


class RagIndexPipeline:
    """Build, validate, and promote a locally testable candidate index."""

    def __init__(
        self,
        *,
        tokenizer: object | None = None,
        embedder: EmbeddingPort | None = None,
        candidate_store: CandidateStorePort | None = None,
        catalog: IndexCatalogPort | None = None,
    ) -> None:
        self._tokenizer = tokenizer
        self._embedder = embedder or PinnedBgeEmbedder()
        self._candidate_store = candidate_store
        self._catalog = catalog

    async def build_candidate(
        self,
        source_paths: Sequence[str],
        index_version: str,
    ) -> IndexBuildReport:
        """Run the candidate stages without changing an active alias."""

        versions = self.parse_candidate_sources(source_paths)
        chunks = self.chunk_candidate_sources(versions)
        vectors = await self.embed_candidate_chunks(chunks)
        report = self.build_candidate_report(index_version, versions, chunks, vectors)
        if self._candidate_store is not None:
            await self.persist_candidate(report, versions, chunks, vectors)
            await self.register_candidate_feature_view(index_version)
            await self.emit_candidate_lineage(report, versions, chunks)
        return report

    def parse_candidate_sources(
        self, source_paths: Sequence[str]
    ) -> list[KnowledgeDocumentVersion]:
        """Parse all required source files for the first candidate stage."""

        return parse_sources(_source_root(source_paths))

    def chunk_candidate_sources(
        self, versions: Sequence[KnowledgeDocumentVersion]
    ) -> list[KnowledgeChunk]:
        """Create deterministic 400/80 chunks for parsed candidate versions."""

        return build_chunks(
            versions,
            tokenizer=self._tokenizer or _load_tokenizer(),
            tokenizer_model=BGE_MODEL,
            tokenizer_revision=BGE_REVISION,
        )

    async def embed_candidate_chunks(
        self, chunks: Sequence[KnowledgeChunk]
    ) -> list[list[float]]:
        """Embed every candidate chunk and enforce the pinned vector contract."""

        vectors = await self._embedder.embed([chunk.content for chunk in chunks])
        if len(vectors) != len(chunks):
            raise EmbeddingValidationError("embedding count does not match chunk count")
        return [_validated_vector(vector) for vector in vectors]

    def build_candidate_report(
        self,
        index_version: str,
        versions: Sequence[KnowledgeDocumentVersion],
        chunks: Sequence[KnowledgeChunk],
        vectors: Sequence[Sequence[float]],
    ) -> IndexBuildReport:
        """Bind parsed content, chunks, and vectors into one candidate report."""

        if len(chunks) != len(vectors):
            raise EmbeddingValidationError("embedding count does not match candidate chunks")
        vector_hashes = {
            chunk.chunk_id: hashlib.sha256(
                struct.pack("<384f", *_validated_vector(vector))
            ).hexdigest()
            for chunk, vector in zip(chunks, vectors, strict=True)
        }
        return IndexBuildReport(
            index_version=index_version,
            candidate_label="ci-bootstrap",
            document_count=8,
            document_version_count=9,
            chunk_count=len(chunks),
            embedding_dimension=384,
            source_sha256={
                path.name: versions_for_path[0].source_sha256
                for path, versions_for_path in _versions_by_source_path(versions).items()
            },
            version_content_sha256={
                f"{version.document_id}@{version.version}": version.content_sha256
                for version in versions
            },
            chunk_content_sha256={
                chunk.chunk_id: chunk.content_sha256 for chunk in chunks
            },
            embedding_sha256=vector_hashes,
            embedding_model=BGE_MODEL,
            embedding_revision=BGE_REVISION,
            tokenizer_model=BGE_MODEL,
            tokenizer_revision=BGE_REVISION,
        )

    async def persist_candidate(
        self,
        report: IndexBuildReport,
        versions: Sequence[KnowledgeDocumentVersion],
        chunks: Sequence[KnowledgeChunk],
        vectors: Sequence[Sequence[float]],
    ) -> None:
        """Persist immutable candidate rows and pgvector values transactionally."""

        await self._require_store().upsert_candidate(
            index_version=report.index_version,
            versions=versions,
            chunks=chunks,
            vectors=vectors,
            report=report,
        )

    async def register_candidate_feature_view(self, index_version: str) -> str:
        """Declare the candidate retrieval feature service without building an ANN index."""

        return await self._require_store().register_feast_feature_view(index_version)

    async def emit_candidate_lineage(
        self,
        report: IndexBuildReport,
        versions: Sequence[KnowledgeDocumentVersion],
        chunks: Sequence[KnowledgeChunk],
    ) -> str:
        """Emit source-to-candidate lineage after immutable storage succeeds."""

        return await self._require_catalog().emit_candidate(
            report=report,
            versions=versions,
            chunks=chunks,
        )

    async def validate_candidate(
        self,
        index_version: str,
        evaluation_path: str | Path,
    ) -> IndexValidationReport:
        """Validate a complete candidate before any active-alias mutation."""

        store = self._require_store()
        if not await store.candidate_complete(index_version):
            raise CandidateValidationError(
                f"candidate {index_version} is incomplete and cannot be validated"
            )
        try:
            report = IndexValidationReport.model_validate(
                json.loads(Path(evaluation_path).read_text(encoding="utf-8"))
            )
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise CandidateValidationError("candidate evaluation report is invalid") from error
        if report.index_version != index_version:
            raise CandidateValidationError("candidate evaluation index version does not match")
        if not report.passed:
            raise CandidateValidationError("candidate evaluation did not pass")
        await store.mark_validated(index_version, report)
        return report

    async def promote(
        self,
        index_version: str,
        expected_active_version: str | None,
    ) -> str:
        """Promote with CAS and compensate to the recorded prior alias on failure."""

        prior_alias = await self.promote_compare_and_swap(
            index_version,
            expected_active_version,
        )
        return await self.emit_active_lineage_and_read_back(index_version, prior_alias)

    async def promote_compare_and_swap(
        self,
        index_version: str,
        expected_active_version: str | None,
    ) -> str | None:
        """Validate and compare-and-swap only; active lineage remains a later stage."""

        store = self._require_store()
        if not await store.is_validated(index_version):
            raise CandidateValidationError(
                f"candidate {index_version} must be validated before promotion"
            )

        prior_alias = await store.active_version()
        if prior_alias != expected_active_version:
            raise CandidateValidationError("active alias differs from the expected prior version")
        await store.compare_and_swap_active(prior_alias, index_version)
        return prior_alias

    async def emit_active_lineage_and_read_back(
        self,
        index_version: str,
        prior_alias: str | None,
    ) -> str:
        """Verify active lineage, compensating the exact recorded alias on failure."""

        store = self._require_store()
        catalog = self._require_catalog()
        try:
            await catalog.emit_active(
                index_version=index_version,
                previous_index_version=prior_alias,
            )
            await catalog.read_back(index_version=index_version)
        except Exception as error:
            try:
                await store.compare_and_swap_active(index_version, prior_alias)
            except Exception as compensation_error:
                raise CandidateValidationError(
                    "active lineage failed and alias compensation also failed"
                ) from compensation_error
            await catalog.emit_rollback(
                failed_index_version=index_version,
                restored_index_version=prior_alias,
                reason=str(error),
            )
            raise
        return index_version

    async def rollback(self, previous_index_version: str | None) -> str | None:
        """Compare-and-swap the active alias back to a recorded prior version."""

        store = self._require_store()
        catalog = self._require_catalog()
        active_version = await store.active_version()
        if active_version is None:
            raise CandidateValidationError("no active alias exists to roll back")
        await store.compare_and_swap_active(active_version, previous_index_version)
        await catalog.emit_rollback(
            failed_index_version=active_version,
            restored_index_version=previous_index_version,
            reason="explicit rollback",
        )
        return previous_index_version

    def _require_store(self) -> CandidateStorePort:
        if self._candidate_store is None:
            raise CandidateValidationError("candidate storage is not configured")
        return self._candidate_store

    def _require_catalog(self) -> IndexCatalogPort:
        if self._catalog is None:
            raise CandidateValidationError("DataHub lineage is not configured")
        return self._catalog


__all__ = [
    "EXPECTED_SOURCE_FILES",
    "BGE_MODEL",
    "BGE_REVISION",
    "CandidateValidationError",
    "EmbeddingValidationError",
    "PinnedBgeEmbedder",
    "QUERY_PREFIX",
    "RagIndexPipeline",
    "SourceParseError",
    "build_chunks",
    "canonical_chunk_id",
    "parse_sources",
    "resolve_effective_version",
]


def _source_root(source_paths: Sequence[str]) -> Path:
    paths = [Path(path) for path in source_paths]
    if not paths or {path.name for path in paths} != set(EXPECTED_SOURCE_FILES):
        raise SourceParseError("candidate build requires all eight expected source paths")
    parents = {path.parent for path in paths}
    if len(parents) != 1:
        raise SourceParseError("candidate source paths must share one source root")
    return parents.pop()


def _versions_by_source_path(
    versions: Sequence[KnowledgeDocumentVersion],
) -> dict[Path, list[KnowledgeDocumentVersion]]:
    grouped: dict[Path, list[KnowledgeDocumentVersion]] = {}
    for version in versions:
        grouped.setdefault(version.source_path, []).append(version)
    return grouped


def _load_tokenizer() -> object:
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(
        BGE_MODEL,
        revision=BGE_REVISION,
        local_files_only=True,
    )
