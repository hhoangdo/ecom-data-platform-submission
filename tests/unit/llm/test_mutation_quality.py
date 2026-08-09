from __future__ import annotations

import hashlib
import json
import struct
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import pytest

from vina_bim_shop.llm.adapters.datahub import DatahubIndexCatalogAdapter
from vina_bim_shop.llm.adapters.feast_postgres import (
    _candidate_digest,
    _stored_value,
    _validated_vector,
    _validation_digest,
    _vector_literal,
)
from vina_bim_shop.llm.indexing import RagIndexPipeline
from vina_bim_shop.llm.contracts import (
    ChatResponse,
    IndexBuildReport,
    IndexValidationReport,
    KnowledgeCategory,
    KnowledgeChunk,
    KnowledgeDocumentVersion,
    ObservedGeneration,
    ToolCallRecord,
)
from vina_bim_shop.llm.telemetry import InMemoryTelemetrySink, TelemetryRecorder
from vina_bim_shop.orchestration.specs import REQUIRED_DAG_IDS, dag_specs_by_id


def _generation() -> ObservedGeneration:
    return ObservedGeneration(
        text="sanitized answer",
        model_version="qwen-primary@sha256:unit",
        input_tokens=17,
        output_tokens=5,
        total_tokens=22,
        ttft_ms=4.5,
        generation_ms=9.25,
        finish_reason="stop",
    )


def test_orchestration_dag_inventory_is_exact_and_ordered() -> None:
    specs = dag_specs_by_id()
    assert tuple(specs) == REQUIRED_DAG_IDS
    assert [
        (spec.dag_id, spec.schedule, spec.supports_hourly_logical_window, spec.monitors_flink)
        for spec in specs.values()
    ] == [
        ("hourly_batch_lakehouse", "hourly_demo", True, False),
        ("kafka_topic_bootstrap", "manual", False, False),
        ("pinot_bootstrap", "manual", False, False),
        ("datahub_ingestion", "manual", False, False),
        ("reconciliation_report", "hourly_demo", True, False),
        ("local_evidence_build", "manual", False, False),
        ("mini_coursework_pipeline", "hourly_demo", True, False),
        ("rag_index_pipeline", "manual", False, False),
    ]


def test_telemetry_generation_and_prompt_budget_are_content_free_and_exact() -> None:
    sink = InMemoryTelemetrySink()
    recorder = TelemetryRecorder(sink)
    messages = [{"role": "user", "content": "alice@example.com asks about order 123"}, {"role": "assistant", "content": "draft"}]
    recorder.record_generation(model_variant="primary", generation=_generation(), messages=messages)
    recorder.record_prompt_budget(
        input_tokens=17,
        dropped_history_group_ids=["h-1", "h-2"],
        dropped_chunk_ids=["c-9"],
        messages=messages,
    )
    prompt_hash = hashlib.sha256("alice@example.com asks about order 123\ndraft".encode("utf-8")).hexdigest()
    assert [(event.name, dict(event.attributes)) for event in sink.events] == [
        (
            "llm.generation",
            {
                "llm.model_variant": "primary",
                "llm.model_version": "qwen-primary@sha256:unit",
                "llm.input_tokens": "17",
                "llm.output_tokens": "5",
                "llm.total_tokens": "22",
                "llm.ttft_ms": "4.5",
                "llm.generation_ms": "9.25",
                "llm.prompt_sha256": prompt_hash,
            },
        ),
        (
            "llm.prompt_budget",
            {
                "llm.input_tokens": "17",
                "llm.dropped_history_groups": "2",
                "llm.dropped_retrieval_chunks": "1",
                "llm.dropped_history_group_ids_sha256": hashlib.sha256("h-1\nh-2".encode("utf-8")).hexdigest(),
                "llm.dropped_retrieval_chunk_ids_sha256": hashlib.sha256("c-9".encode("utf-8")).hexdigest(),
                "llm.prompt_sha256": prompt_hash,
            },
        ),
    ]
    assert "alice@example.com" not in repr(sink.events)


def test_telemetry_coordinator_preserves_only_correlated_outcome_and_tool_metadata() -> None:
    sink = InMemoryTelemetrySink()
    response = ChatResponse(
        request_id=UUID("00000000-0000-0000-0000-000000000123"),
        route="support",
        answer="private order detail must not be emitted",
        claims=[],
        agent_name="retrieval-agent",
        agent_version="v2",
        model_version="qwen-primary@sha256:unit",
        index_version=None,
        tool_calls=[
            ToolCallRecord(tool="search_ecommerce_knowledge", status="succeeded", duration_ms=12.5, error_code=None),
            ToolCallRecord(tool="detect_customer_order_drift", status="failed", duration_ms=3.0, error_code="dependency_unavailable"),
        ],
        safety_action="allow",
    )
    TelemetryRecorder(sink).record_coordinator(
        session_id="session-secret-42",
        route="support",
        runtime_variant="v2",
        destination="retrieval-agent",
        experiment="model-primary",
        response=response,
    )
    assert [event.name for event in sink.events] == ["coordinator.agent", "coordinator.tool", "coordinator.tool"]
    base = dict(sink.events[0].attributes)
    assert base == {
        "coordinator.session_sha256": hashlib.sha256(b"session-secret-42").hexdigest(),
        "coordinator.request_sha256": hashlib.sha256(str(response.request_id).encode("utf-8")).hexdigest(),
        "coordinator.route": "support",
        "coordinator.runtime_variant": "v2",
        "coordinator.destination": "retrieval-agent",
        "coordinator.experiment": "model-primary",
        "coordinator.safety_action": "allow",
        "coordinator.agent_name": "retrieval-agent",
        "coordinator.agent_version": "v2",
        "coordinator.model_version": "qwen-primary@sha256:unit",
        "coordinator.index_version": "",
    }
    assert dict(sink.events[1].attributes) == {
        **base,
        "coordinator.tool": "search_ecommerce_knowledge",
        "coordinator.tool_status": "succeeded",
        "coordinator.tool_duration_ms": "12.5",
        "coordinator.tool_error_code": "",
    }
    assert dict(sink.events[2].attributes) == {
        **base,
        "coordinator.tool": "detect_customer_order_drift",
        "coordinator.tool_status": "failed",
        "coordinator.tool_duration_ms": "3.0",
        "coordinator.tool_error_code": "dependency_unavailable",
    }
    assert "session-secret-42" not in repr(sink.events)
    assert response.answer not in repr(sink.events)


@pytest.mark.asyncio
async def test_datahub_lineage_emits_exact_candidate_active_and_rollback_records() -> None:
    emitted: list[dict[str, object]] = []

    async def emit(payload: dict[str, object]) -> None:
        emitted.append(payload)

    async def read(index_version: str) -> dict[str, object]:
        assert index_version == "candidate-quality-1"
        return emitted[1]

    content = "Returns are accepted within thirty days."
    version = KnowledgeDocumentVersion(
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
    chunk = KnowledgeChunk(
        chunk_id="b" * 64,
        source_sha256=version.source_sha256,
        document_id=version.document_id,
        category=version.category,
        version=version.version,
        effective_from=version.effective_from,
        effective_to=None,
        ordinal=0,
        token_start=0,
        token_end=3,
        content="Returns are accepted.",
        content_sha256=hashlib.sha256(b"Returns are accepted.").hexdigest(),
        tokenizer_model="BAAI/bge-small-en-v1.5",
        tokenizer_revision="5c38ec7c405ec4b44b94cc5a9bb96e735b38267a",
    )
    report = IndexBuildReport(
        index_version="candidate-quality-1",
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
    adapter = DatahubIndexCatalogAdapter(emit=emit, read=read)

    assert await adapter.emit_candidate(report=report, versions=[version], chunks=[chunk]) == (
        "urn:li:dataProcessInstance:edai2-rag-candidate-candidate-quality-1"
    )
    assert emitted == [
        {
            "kind": "candidate",
            "index_version": "candidate-quality-1",
            "source_sha256": {"returns.md": "a" * 64},
            "version_nodes": ["returns-policy@1.0.0"],
            "chunk_nodes": ["b" * 64],
            "embedding_sha256": {"b" * 64: "d" * 64},
            "edges": [
                "source->document_version",
                "document_version->chunk",
                "chunk->embedding",
                "embedding->candidate",
            ],
        }
    ]

    assert await adapter.emit_active(
        index_version="candidate-quality-1", previous_index_version="active-quality-0"
    ) == "urn:li:dataProcessInstance:edai2-rag-active-candidate-quality-1"
    expected_active = {
        "kind": "active",
        "index_version": "candidate-quality-1",
        "previous_index_version": "active-quality-0",
        "edges": ["candidate-quality-1->active", "active->feast", "feast->api"],
    }
    expected_active["lineage_sha256"] = hashlib.sha256(
        json.dumps(expected_active, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert emitted[1] == expected_active
    assert await adapter.read_back(index_version="candidate-quality-1") is True

    assert await adapter.emit_rollback(
        failed_index_version="candidate-quality-1",
        restored_index_version="active-quality-0",
        reason="read-back-mismatch",
    ) == "urn:li:dataProcessInstance:edai2-rag-rollback-candidate-quality-1"
    assert emitted[2] == {
        "kind": "rollback",
        "failed_index_version": "candidate-quality-1",
        "restored_index_version": "active-quality-0",
        "reason": "read-back-mismatch",
        "edges": ["active->rollback"],
    }


def test_feast_serialization_and_report_digests_are_canonical_and_exact() -> None:
    vector = [1.2345678912] + [0.0] * 383
    assert _stored_value(datetime(2025, 1, 1, tzinfo=timezone.utc)) == "2025-01-01T00:00:00Z"
    assert _stored_value(Path("returns.md")) == "returns.md"
    assert _validated_vector(vector) == vector
    assert _vector_literal(vector[:3]) == "[1.23456789,0,0]"

    report = IndexBuildReport(
        index_version="candidate-quality-2",
        candidate_label="ci-bootstrap",
        document_count=8,
        document_version_count=9,
        chunk_count=2,
        embedding_dimension=384,
        source_sha256={"z.md": "a" * 64, "a.md": "b" * 64},
        version_content_sha256={"returns@2": "c" * 64, "returns@1": "d" * 64},
        chunk_content_sha256={"e" * 64: "f" * 64, "0" * 64: "1" * 64},
        embedding_sha256={"e" * 64: "2" * 64, "0" * 64: "3" * 64},
        embedding_model="BAAI/bge-small-en-v1.5",
        embedding_revision="5c38ec7c405ec4b44b94cc5a9bb96e735b38267a",
        tokenizer_model="BAAI/bge-small-en-v1.5",
        tokenizer_revision="5c38ec7c405ec4b44b94cc5a9bb96e735b38267a",
    )
    validation = IndexValidationReport(
        index_version=report.index_version,
        recall_at_4=0.875,
        citation_precision=1.0,
        safety_pass_rate=0.95,
        passed=False,
        failures=["citation-set-7"],
    )
    assert _candidate_digest(report) == hashlib.sha256(
        json.dumps(report.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert _validation_digest(validation) == hashlib.sha256(
        json.dumps(validation.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@pytest.mark.asyncio
async def test_rag_candidate_build_persists_the_complete_hash_bound_inventory() -> None:
    class Tokenizer:
        def encode(self, _text: str, *, add_special_tokens: bool) -> list[int]:
            assert add_special_tokens is False
            return [0, 1, 2]

        def decode(
            self,
            token_ids: list[int],
            *,
            skip_special_tokens: bool,
            clean_up_tokenization_spaces: bool,
        ) -> str:
            assert skip_special_tokens is False
            assert clean_up_tokenization_spaces is False
            return " ".join(str(token_id) for token_id in token_ids)

    class Embedder:
        async def embed(self, texts: list[str]) -> list[list[float]]:
            assert texts and all(text == "0 1 2" for text in texts)
            return [[1.0] + [0.0] * 383 for _ in texts]

    class Store:
        def __init__(self) -> None:
            self.calls: list[tuple[str, object]] = []

        async def upsert_candidate(self, **kwargs: object) -> None:
            self.calls.append(("upsert", kwargs))

        async def register_feast_feature_view(self, index_version: str) -> str:
            self.calls.append(("register", index_version))
            return f"ecommerce_knowledge_retrieval:{index_version}"

    class Catalog:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        async def emit_candidate(self, **kwargs: object) -> str:
            self.calls.append(kwargs)
            return "urn:quality-candidate"

    source_root = Path(__file__).resolve().parents[3] / "data" / "knowledge" / "ecommerce"
    source_paths = [str(path) for path in sorted(source_root.glob("*.md"))]
    store = Store()
    catalog = Catalog()
    report = await RagIndexPipeline(
        tokenizer=Tokenizer(), embedder=Embedder(), candidate_store=store, catalog=catalog
    ).build_candidate(source_paths, "candidate-quality-3")

    expected_source_hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(source_root.glob("*.md"))
    }
    assert report.index_version == "candidate-quality-3"
    assert report.source_sha256 == expected_source_hashes
    upsert = store.calls[0][1]
    assert [call[0] for call in store.calls] == ["upsert", "register"]
    assert upsert["index_version"] == report.index_version  # type: ignore[index]
    assert upsert["report"] == report  # type: ignore[index]
    versions = upsert["versions"]  # type: ignore[index]
    chunks = upsert["chunks"]  # type: ignore[index]
    vectors = upsert["vectors"]  # type: ignore[index]
    assert report.version_content_sha256 == {
        f"{version.document_id}@{version.version}": hashlib.sha256(
            version.content.encode("utf-8")
        ).hexdigest()
        for version in versions
    }
    assert report.chunk_content_sha256 == {
        chunk.chunk_id: hashlib.sha256(chunk.content.encode("utf-8")).hexdigest()
        for chunk in chunks
    }
    assert report.embedding_sha256 == {
        chunk.chunk_id: hashlib.sha256(struct.pack("<384f", *vector)).hexdigest()
        for chunk, vector in zip(chunks, vectors, strict=True)
    }
    assert catalog.calls == [{"report": report, "versions": versions, "chunks": chunks}]
