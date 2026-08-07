from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from vina_bim_shop.llm.contracts import KnowledgeCategory, KnowledgeDocumentVersion
from vina_bim_shop.llm.indexing import (
    BGE_MODEL,
    BGE_REVISION,
    QUERY_PREFIX,
    EmbeddingValidationError,
    PinnedBgeEmbedder,
    RagIndexPipeline,
    SourceParseError,
    build_chunks,
    canonical_chunk_id,
    parse_sources,
    resolve_effective_version,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
REPOSITORY_SOURCE_ROOT = REPOSITORY_ROOT / "data" / "knowledge" / "ecommerce"
BUILD_INDEX_SCRIPT = REPOSITORY_ROOT / "scripts" / "llm" / "build_index.py"

SOURCE_SPECS = {
    "returns.md": ("returns-policy", "returns"),
    "shipping.md": ("shipping-policy", "shipping"),
    "cancellation.md": ("cancellation-policy", "cancellation"),
    "payments.md": ("payments-policy", "payments"),
    "promotions.md": ("promotions-policy", "promotions"),
    "warranties.md": ("warranties-policy", "warranties"),
    "privacy.md": ("privacy-policy", "privacy"),
    "marketplace_support.md": (
        "marketplace-support-policy",
        "marketplace_support",
    ),
}


def _body(word_count: int) -> str:
    return "# Policy\n\n" + " ".join(["policy"] * word_count) + "\n"


def _record(
    *,
    document_id: str,
    category: str,
    version: str,
    effective_from: str,
    effective_to: str,
    word_count: int,
) -> str:
    return (
        "---\n"
        f"document_id: {document_id}\n"
        f"category: {category}\n"
        f"version: {version}\n"
        f"effective_from: {effective_from}\n"
        f"effective_to: {effective_to}\n"
        "---\n"
        f"{_body(word_count)}"
    )


def _write_valid_source_root(root: Path) -> Path:
    root.mkdir(parents=True)
    for filename, (document_id, category) in SOURCE_SPECS.items():
        path = root / filename
        if filename == "returns.md":
            historical = _record(
                document_id=document_id,
                category=category,
                version="1.0.0",
                effective_from="2025-01-01T00:00:00Z",
                effective_to="2026-01-01T00:00:00Z",
                word_count=160,
            )
            current = _record(
                document_id=document_id,
                category=category,
                version="1.1.0",
                effective_from="2026-01-01T00:00:00Z",
                effective_to="null",
                word_count=160,
            )
            path.write_bytes(
                (historical + "<!-- version-separator -->\n" + current).encode("utf-8")
            )
            continue

        path.write_bytes(
            _record(
                document_id=document_id,
                category=category,
                version="1.0.0",
                effective_from="2025-01-01T00:00:00Z",
                effective_to="null",
                word_count=300,
            ).encode("utf-8")
        )
    return root


def test_repository_sources_have_exact_inventory_and_nine_versions() -> None:
    records = parse_sources(REPOSITORY_SOURCE_ROOT)

    assert len(records) == 9
    assert {record.source_path.name for record in records} == set(SOURCE_SPECS)
    assert {
        (record.source_path.name, record.document_id, record.category.value)
        for record in records
    } == {
        (filename, document_id, category)
        for filename, (document_id, category) in SOURCE_SPECS.items()
    }
    assert sum(record.source_path.name == "returns.md" for record in records) == 2


def test_parser_rejects_noncanonical_bytes_and_unknown_metadata(tmp_path: Path) -> None:
    root = _write_valid_source_root(tmp_path / "knowledge")
    shipping_path = root / "shipping.md"
    canonical = shipping_path.read_bytes()

    invalid_forms = [
        b"\xef\xbb\xbf" + canonical,
        canonical.replace(b"\n", b"\r\n"),
        canonical.rstrip(b"\n"),
        canonical.replace(
            b"version: 1.0.0\n",
            b"version: 1.0.0\nowner: support\n",
        ),
        b"free text before a record\n" + canonical,
    ]

    for invalid in invalid_forms:
        shipping_path.write_bytes(invalid)
        with pytest.raises(SourceParseError):
            parse_sources(root)
    shipping_path.write_bytes(canonical)


def test_parser_rejects_out_of_bounds_body(tmp_path: Path) -> None:
    root = _write_valid_source_root(tmp_path / "knowledge")
    (root / "shipping.md").write_bytes(
        _record(
            document_id="shipping-policy",
            category="shipping",
            version="1.0.0",
            effective_from="2025-01-01T00:00:00Z",
            effective_to="null",
            word_count=10,
        ).encode("utf-8")
    )

    with pytest.raises(SourceParseError, match="word"):
        parse_sources(root)


def test_returns_effective_windows_are_adjacent_and_half_open(tmp_path: Path) -> None:
    records = parse_sources(_write_valid_source_root(tmp_path / "knowledge"))
    before = resolve_effective_version(
        records,
        "returns-policy",
        datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
    )
    at_transition = resolve_effective_version(
        records,
        "returns-policy",
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    after = resolve_effective_version(
        records,
        "returns-policy",
        datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
    )

    assert before.version == "1.0.0"
    assert at_transition.version == "1.1.0"
    assert after.version == "1.1.0"


def test_source_and_normalized_body_hashes_are_stable(tmp_path: Path) -> None:
    root = _write_valid_source_root(tmp_path / "knowledge")
    shipping_path = root / "shipping.md"
    shipping = next(
        record for record in parse_sources(root) if record.source_path == shipping_path
    )

    assert shipping.source_sha256 == hashlib.sha256(shipping_path.read_bytes()).hexdigest()
    assert shipping.content_sha256 == hashlib.sha256(
        shipping.content.encode("utf-8")
    ).hexdigest()


class FakeTokenizer:
    def __init__(self, token_count: int) -> None:
        self.token_count = token_count
        self.encode_calls: list[tuple[str, bool]] = []

    def encode(self, text: str, *, add_special_tokens: bool) -> list[int]:
        self.encode_calls.append((text, add_special_tokens))
        return list(range(self.token_count))

    def decode(
        self,
        token_ids: list[int],
        *,
        skip_special_tokens: bool,
        clean_up_tokenization_spaces: bool,
    ) -> str:
        assert not skip_special_tokens
        assert not clean_up_tokenization_spaces
        return " ".join(str(token_id) for token_id in token_ids)


def _version(content: str) -> KnowledgeDocumentVersion:
    return KnowledgeDocumentVersion(
        source_path=Path("shipping.md"),
        source_sha256="a" * 64,
        document_id="shipping-policy",
        category=KnowledgeCategory.SHIPPING,
        version="1.0.0",
        effective_from=datetime(2025, 1, 1, tzinfo=timezone.utc),
        effective_to=None,
        content=content,
        content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
    )


def test_chunking_uses_400_token_windows_with_80_token_overlap() -> None:
    chunks = build_chunks(
        [_version("canonical content")],
        tokenizer=FakeTokenizer(token_count=801),
        tokenizer_model="BAAI/bge-small-en-v1.5",
        tokenizer_revision="5c38ec7c405ec4b44b94cc5a9bb96e735b38267a",
    )

    assert [(chunk.ordinal, chunk.token_start, chunk.token_end) for chunk in chunks] == [
        (0, 0, 400),
        (1, 320, 720),
        (2, 640, 801),
    ]
    assert all(
        left.token_end - right.token_start == 80
        for left, right in zip(chunks, chunks[1:])
    )
    assert all(chunk.token_end - chunk.token_start <= 400 for chunk in chunks)
    assert all(chunk.version == "1.0.0" for chunk in chunks)


def test_chunking_normalizes_nfc_before_tokenization() -> None:
    tokenizer = FakeTokenizer(token_count=3)

    chunks = build_chunks(
        [_version("Cafe\u0301 policy")],
        tokenizer=tokenizer,
        tokenizer_model="BAAI/bge-small-en-v1.5",
        tokenizer_revision="5c38ec7c405ec4b44b94cc5a9bb96e735b38267a",
    )

    assert tokenizer.encode_calls == [("Café policy", False)]
    assert chunks[0].content_sha256 == hashlib.sha256(
        chunks[0].content.encode("utf-8")
    ).hexdigest()


def test_chunk_id_uses_canonical_jcs_field_order() -> None:
    expected_payload = (
        b'{"content_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
        b'"document_id":"shipping-policy","ordinal":2,"token_end":720,'
        b'"token_start":320,"tokenizer_revision":"5c38ec7c405ec4b44b94cc5a9bb96e735b38267a",'
        b'"version":"1.0.0"}'
    )

    assert canonical_chunk_id(
        document_id="shipping-policy",
        version="1.0.0",
        ordinal=2,
        token_start=320,
        token_end=720,
        content_sha256="a" * 64,
        tokenizer_revision="5c38ec7c405ec4b44b94cc5a9bb96e735b38267a",
    ) == hashlib.sha256(expected_payload).hexdigest()


class FakeEmbeddingModel:
    def __init__(self, vectors: list[list[float]] | None = None) -> None:
        self.vectors = vectors
        self.calls: list[tuple[list[str], bool, bool, bool]] = []

    def encode(
        self,
        texts: list[str],
        *,
        normalize_embeddings: bool,
        convert_to_numpy: bool,
        show_progress_bar: bool,
    ) -> list[list[float]]:
        self.calls.append(
            (texts, normalize_embeddings, convert_to_numpy, show_progress_bar)
        )
        return self.vectors or [[1.0] + [0.0] * 383 for _ in texts]


def test_embedding_config_pins_tokenizer_and_prefixes() -> None:
    config = yaml.safe_load(
        (REPOSITORY_ROOT / "configs" / "llm" / "models.yaml").read_text(
            encoding="utf-8"
        )
    )
    embedding = config["models"]["embedding"]

    assert embedding["model"] == BGE_MODEL
    assert embedding["hub_revision"] == BGE_REVISION
    assert embedding["tokenizer_model"] == BGE_MODEL
    assert embedding["tokenizer_revision"] == BGE_REVISION
    assert embedding["passage_prefix"] == ""
    assert embedding["query_prefix"] == QUERY_PREFIX
    assert embedding["normalize_embeddings"] is True
    assert embedding["dimension"] == 384


@pytest.mark.asyncio
async def test_pinned_embedder_keeps_passages_unprefixed_and_prefixes_queries() -> None:
    model = FakeEmbeddingModel()
    load_calls: list[tuple[str, str]] = []

    def load_model(model_name: str, revision: str) -> FakeEmbeddingModel:
        load_calls.append((model_name, revision))
        return model

    embedder = PinnedBgeEmbedder(model_loader=load_model)
    passages = await embedder.embed(["canonical chunk text"])
    query = await embedder.embed_query("where is my order")

    assert load_calls == [(BGE_MODEL, BGE_REVISION)]
    assert model.calls == [
        (["canonical chunk text"], True, True, False),
        ([QUERY_PREFIX + "where is my order"], True, True, False),
    ]
    assert len(passages[0]) == 384
    assert len(query) == 384


@pytest.mark.asyncio
async def test_pinned_embedder_rejects_invalid_vectors_and_moving_revisions() -> None:
    with pytest.raises(EmbeddingValidationError, match="immutable"):
        PinnedBgeEmbedder(revision="main")

    invalid = FakeEmbeddingModel(vectors=[[float("nan")] * 384])
    embedder = PinnedBgeEmbedder(model_loader=lambda _model, _revision: invalid)
    with pytest.raises(EmbeddingValidationError, match="finite"):
        await embedder.embed(["canonical chunk text"])


class FakeCandidateEmbedder:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[1.0] + [0.0] * 383 for _ in texts]


@pytest.mark.asyncio
async def test_candidate_pipeline_reports_deterministic_hashes_without_storage(
    tmp_path: Path,
) -> None:
    root = _write_valid_source_root(tmp_path / "knowledge")
    embedder = FakeCandidateEmbedder()
    pipeline = RagIndexPipeline(
        tokenizer=FakeTokenizer(token_count=3),
        embedder=embedder,
    )
    source_paths = [str(root / filename) for filename in SOURCE_SPECS]

    first = await pipeline.build_candidate(source_paths, "test_idx_001")
    second = await pipeline.build_candidate(source_paths, "test_idx_001")

    assert first.index_version == "test_idx_001"
    assert first.candidate_label == "ci-bootstrap"
    assert first.document_count == 8
    assert first.document_version_count == 9
    assert first.chunk_count == 9
    assert first.embedding_dimension == 384
    assert len(first.version_content_sha256) == 9
    assert len(first.chunk_content_sha256) == 9
    assert len(first.embedding_sha256) == 9
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert len(embedder.calls) == 2


def test_build_index_cli_requires_explicit_candidate_dry_run() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(BUILD_INDEX_SCRIPT),
            "--mode",
            "candidate",
            "--index-version",
            "test_idx_001",
            "--source-root",
            str(REPOSITORY_SOURCE_ROOT),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "--dry-run" in result.stderr


def test_build_index_report_hash_is_canonical() -> None:
    spec = importlib.util.spec_from_file_location("build_index", BUILD_INDEX_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    payload = {"chunk_count": 9, "index_version": "test_idx_001"}

    expected = hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    assert module.canonical_report_sha256(payload) == expected


def test_build_index_cli_accepts_only_the_topic10_local_sentinel_purpose() -> None:
    spec = importlib.util.spec_from_file_location("build_index", BUILD_INDEX_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    args = module.parse_args(
        [
            "--mode",
            "candidate",
            "--index-version",
            "test_idx_001",
            "--index-purpose",
            "local-bootstrap-sentinel",
            "--source-root",
            str(REPOSITORY_SOURCE_ROOT),
            "--dry-run",
        ]
    )

    assert args.index_purpose == "local-bootstrap-sentinel"
