from __future__ import annotations

import configparser
from pathlib import Path
import tomllib
from uuid import uuid4

import pytest
import yaml
from fastapi import Body
from fastapi.testclient import TestClient

from vina_bim_shop.kafka.topics import all_topic_names, load_topic_config
from vina_bim_shop.llm import indexing
from vina_bim_shop.llm.adapters.feast_postgres import (
    CandidateIndexError,
    FeastPostgresAdapter,
    Section03AdapterError,
    _call_hook,
    _stored_value,
    _validated_vector as postgres_validated_vector,
    _vector_literal,
)
from vina_bim_shop.llm.adapters.datahub import DataHubReadBackError, DatahubIndexCatalogAdapter
from vina_bim_shop.llm.adapters.kagent import A2ATimeoutError, KagentCoordinatorAdapter
from vina_bim_shop.llm.adapters.llmd import LlmdInferenceAdapter
from vina_bim_shop.llm.api.common import DependencyUnavailable, create_contract_app
from vina_bim_shop.llm.contracts import ChatRequest, IndexValidationReport, ObservedGeneration, TimeWindow
from vina_bim_shop.llm.streaming import OfflineWriterContract, OnlineWriterContract
from vina_bim_shop.llm import section03_ingestion as section03
from vina_bim_shop.orchestration import rag_index_pipeline as rag


ROOT = Path(__file__).resolve().parents[3]


def test_coverage_omits_only_outside_declared_scope() -> None:
    scope = yaml.safe_load((ROOT / "configs/llm/test_scope.yaml").read_text(encoding="utf-8"))
    declared = {path.replace("\\", "/") for path in scope["production_roots"]}
    config = configparser.ConfigParser()
    config.read(ROOT / "configs/llm/coverage.ini", encoding="utf-8")
    omitted = {path.replace("\\", "/") for path in config["run"].get("omit", "").splitlines() if path.strip()}
    assert omitted
    for path in declared:
        assert not any(path == omitted_path or path.startswith(omitted_path.rstrip("*") ) for omitted_path in omitted)


def test_mutation_uses_only_the_authored_llm_quality_suites() -> None:
    configuration = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert configuration["tool"]["mutmut"]["pytest_add_cli_args_test_selection"] == [
        "tests/unit/llm",
        "tests/contract/llm",
        "tests/property/llm",
        "tests/integration/llm",
    ]
    assert "tmp/edai2-plan/03_data_generator_improvement.md" in configuration["tool"]["mutmut"]["also_copy"]


def test_common_contract_app_exposes_probes_metrics_and_sanitized_handlers() -> None:
    app = create_contract_app("quality-coverage")

    @app.get("/dependency")
    async def dependency() -> None:
        raise DependencyUnavailable("dependency_unavailable", "safe message")

    @app.post("/integer")
    async def integer(value: int = Body()) -> dict[str, int]:
        return {"value": value}

    client = TestClient(app)
    assert client.get("/healthz").json() == {"status": "ok", "service": "quality-coverage"}
    assert client.get("/readyz").json() == {"status": "ok", "service": "quality-coverage"}
    assert client.get("/metrics").status_code == 200
    assert client.get("/dependency").status_code == 409
    assert client.post("/integer", json="bad").status_code == 422


def test_topic_helpers_load_and_order_kafka_topics(tmp_path: Path) -> None:
    path = tmp_path / "topics.yaml"
    path.write_text(
        "source_topics: [source-a]\nderived_placeholder_topics: [derived-b]\nfeature_update_topics: [feature-c]\n",
        encoding="utf-8",
    )
    assert load_topic_config(path)["source_topics"] == ["source-a"]
    assert all_topic_names(path) == ["source-a", "derived-b", "feature-c"]
    path.write_text("- invalid\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping"):
        load_topic_config(path)


class _DagRun:
    def __init__(self, conf: object, run_id: object = "run-1") -> None:
        self.conf = conf
        self.run_id = run_id


def test_rag_airflow_helpers_fail_closed_and_round_trip_handoff(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="dag_run.conf"):
        rag._new_runtime_from_airflow_context({})
    with pytest.raises(RuntimeError, match="shared local handoff_root"):
        rag._handoff_path_from_airflow_context({"dag_run": _DagRun({})})
    context = {"dag_run": _DagRun({"handoff_root": str(tmp_path)})}
    handoff_path = rag._handoff_path_from_airflow_context(context)
    rag._write_handoff(handoff_path, {"stage": "parse_sources"})
    assert rag._read_handoff(handoff_path) == {"stage": "parse_sources"}
    with pytest.raises(RuntimeError, match="Airflow task instance"):
        rag._runtime_from_airflow_context("parse_sources", context)


@pytest.mark.asyncio
async def test_streaming_writer_contracts_reject_live_writes() -> None:
    class Store:
        def __init__(self) -> None:
            self.checkpoints: list[tuple[str, str, int, int]] = []
            self.dlqs: list[dict[str, object]] = []

        async def persist_outbox(self, consumer_group: str, event_id: str, event: dict[str, object]) -> bool:
            raise AssertionError("invalid events must not reach the outbox")

        async def acknowledge_destination(self, destination: str, event: dict[str, object]) -> None:
            raise AssertionError("invalid events must not reach a destination")

        async def advance_checkpoint(self, consumer_group: str, topic: str, partition: int, offset: int) -> None:
            self.checkpoints.append((consumer_group, topic, partition, offset))

        async def publish_dlq(self, envelope: dict[str, object]) -> None:
            self.dlqs.append(envelope)

    store = Store()
    assert (await OfflineWriterContract(store).write({"event": "offline"})).status == "dlq"
    assert (await OnlineWriterContract(store).write({"event": "online"})).status == "dlq"
    assert [record["consumer_group"] for record in store.dlqs] == [
        "edai2-feast-offline-writer-v1",
        "edai2-feast-online-writer-v1",
    ]
    assert store.checkpoints == [
        ("edai2-feast-offline-writer-v1", "customer_feature_updates.v1", 0, 0),
        ("edai2-feast-online-writer-v1", "customer_feature_updates.v1", 0, 0),
    ]


def _minimal_handoff() -> dict[str, object]:
    return {
        "source_root": "sources",
        "index_version": "candidate-v1",
        "evaluation_path": "evaluation.json",
        "expected_active_version": None,
        "promote": False,
        "completed_stages": [],
        "versions": None,
        "chunks": None,
        "vectors": None,
        "report": None,
        "validation": None,
        "prior_active_version": None,
        "active_index_version": None,
        "promotion_started": False,
    }


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("source_root", "", "missing required run configuration"),
        ("expected_active_version", 1, "invalid expected active version"),
        ("promote", "false", "invalid promotion flag"),
        ("completed_stages", "parse_sources", "invalid completed stages"),
        ("completed_stages", ["chunk"], "not an ordered prefix"),
        ("versions", {}, "invalid document versions"),
        ("chunks", {}, "invalid chunks"),
        ("vectors", {}, "invalid embeddings"),
        ("report", [], "invalid candidate report"),
        ("validation", [], "invalid validation report"),
        ("prior_active_version", 1, "invalid prior_active_version"),
        ("promotion_started", "false", "invalid promotion state"),
    ],
)
def test_rag_handoff_rehydration_rejects_invalid_state(
    field: str, value: object, message: str
) -> None:
    handoff = _minimal_handoff()
    handoff[field] = value
    with pytest.raises(ValueError, match=message):
        rag.RagIndexStageRuntime.from_handoff(handoff, pipeline=rag.RagIndexPipeline())


def test_rag_helpers_reject_invalid_context_and_persisted_handoff(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="must be a RagIndexPipeline"):
        rag._pipeline_from_airflow_context({"rag_index_pipeline": object()})
    with pytest.raises(RuntimeError, match="string source_root"):
        rag._new_runtime_from_airflow_context({"dag_run": _DagRun({"source_root": 1})})
    with pytest.raises(RuntimeError, match="string or null"):
        rag._new_runtime_from_airflow_context(
            {"dag_run": _DagRun({"source_root": "s", "index_version": "v", "evaluation_path": "e", "expected_active_version": 1})}
        )
    with pytest.raises(RuntimeError, match="boolean"):
        rag._new_runtime_from_airflow_context(
            {"dag_run": _DagRun({"source_root": "s", "index_version": "v", "evaluation_path": "e", "promote": "yes"})}
        )
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("not-json", encoding="utf-8")
    with pytest.raises(RuntimeError, match="could not read"):
        rag._read_handoff(corrupt)
    non_object = tmp_path / "array.json"
    non_object.write_text("[]", encoding="utf-8")
    with pytest.raises(RuntimeError, match="not an object"):
        rag._read_handoff(non_object)


def test_rag_stage_runtime_rejects_out_of_order_or_missing_state(tmp_path: Path) -> None:
    runtime = rag.RagIndexStageRuntime(
        pipeline=rag.RagIndexPipeline(),
        source_root=tmp_path,
        index_version="candidate-v1",
        evaluation_path=tmp_path / "evaluation.json",
        expected_active_version=None,
    )
    with pytest.raises(ValueError, match="unsupported RAG index stage"):
        runtime.run_stage("unknown")
    with pytest.raises(ValueError, match="expected RAG index stage"):
        runtime.run_stage("chunk")
    with pytest.raises(ValueError, match="parse_sources must complete"):
        runtime._versions()
    with pytest.raises(ValueError, match="chunk must complete"):
        runtime._chunks()
    with pytest.raises(ValueError, match="embed must complete"):
        runtime._vectors()
    with pytest.raises(ValueError, match="candidate storage must complete"):
        runtime._report()
    runtime.completed_stages = list(rag.RAG_INDEX_STAGES)
    with pytest.raises(ValueError, match="already completed"):
        runtime.run_stage(rag.RAG_INDEX_STAGES[-1])


class _ShortEmbeddingModel:
    def encode(self, _texts: list[str], **_kwargs: object) -> list[list[float]]:
        return []


class _RowsCursor:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    async def fetchall(self) -> list[dict[str, object]]:
        return self._rows


class _RowsConnection:
    def __init__(self, rows: list[list[dict[str, object]]]) -> None:
        self._rows = rows

    async def execute(self, _sql: str, _parameters: object = None) -> _RowsCursor:
        if "pg_advisory_xact_lock" in _sql or not self._rows:
            return _RowsCursor([])
        return _RowsCursor(self._rows.pop(0))

    async def close(self) -> None:
        return None

    def transaction(self) -> "_RowsTransaction":
        return _RowsTransaction()


class _RowsTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, _type: object, _value: object, _traceback: object) -> bool:
        return False


@pytest.mark.asyncio
async def test_indexing_public_contracts_reject_invalid_boundary_values(tmp_path: Path) -> None:
    embedder = indexing.PinnedBgeEmbedder(model_loader=lambda *_args: _ShortEmbeddingModel())
    assert await embedder.embed([]) == []
    with pytest.raises(indexing.EmbeddingValidationError, match="count does not match"):
        await embedder.embed(["one"])
    with pytest.raises(indexing.EmbeddingValidationError, match="length 384"):
        indexing._validated_vector([1.0])
    with pytest.raises(indexing.EmbeddingValidationError, match="finite"):
        indexing._validated_vector([float("nan")] * 384)
    with pytest.raises(indexing.EmbeddingValidationError, match="normalized"):
        indexing._validated_vector([1.0] * 384)
    with pytest.raises(indexing.SourceParseError, match="source root does not exist"):
        indexing.parse_sources(tmp_path / "missing")
    with pytest.raises(indexing.SourceParseError, match="exactly eight expected files"):
        indexing.parse_sources(tmp_path)
    with pytest.raises(indexing.SourceParseError, match="pinned BGE model"):
        indexing.build_chunks([], tokenizer=object(), tokenizer_model="wrong", tokenizer_revision="0" * 40)
    with pytest.raises(indexing.CandidateValidationError, match="candidate storage"):
        await indexing.RagIndexPipeline().register_candidate_feature_view("candidate-v1")


@pytest.mark.asyncio
async def test_feast_adapter_fails_closed_at_runtime_seams() -> None:
    adapter = FeastPostgresAdapter()
    with pytest.raises(CandidateIndexError, match="DSN or test-owned"):
        async with adapter._connection():
            pass
    with pytest.raises(Section03AdapterError, match="Feast apply hook"):
        await adapter.apply_feast(None)
    with pytest.raises(Section03AdapterError, match="Valkey materialization hook"):
        await adapter.materialize_valkey(None)
    applied: list[str | None] = []
    activated = FeastPostgresAdapter(
        feast_apply=applied.append,
        valkey_materialize=applied.append,
    )
    await activated.apply_feast("manifest")
    await activated.materialize_valkey("manifest")
    assert applied == ["manifest", "manifest"]
    assert await _call_hook(lambda: "fingerprint", "Feast") == "fingerprint"
    with pytest.raises(Section03AdapterError, match="fingerprint readback"):
        await _call_hook(lambda: "", "Valkey")


@pytest.mark.asyncio
async def test_feast_adapter_reads_candidate_and_activation_state_from_one_connection() -> None:
    connection = _RowsConnection(
        [
            [{"complete": True}],
            [{"validated": True}],
            [{"index_version": "candidate-v1"}],
            [{"manifest_sha256": "manifest-v1"}],
            [{"manifest_sha256": "manifest-v1"}],
            [{"manifest_sha256": "manifest-v1"}],
        ]
    )
    adapter = FeastPostgresAdapter(
        connection_factory=lambda: connection,
        feast_fingerprint=lambda: "feast-v1",
        valkey_fingerprint=lambda: "valkey-v1",
    )
    assert await adapter.candidate_complete("candidate-v1") is True
    assert await adapter.is_validated("candidate-v1") is True
    assert await adapter.active_version() == "candidate-v1"
    assert await adapter.active_section03_manifest_hash() == "manifest-v1"
    assert await adapter.staged_section03_manifest_hash("manifest-v1") == "manifest-v1"
    assert await adapter.fingerprint() == ("manifest-v1", "feast-v1", "valkey-v1")


@pytest.mark.asyncio
async def test_feast_adapter_reads_active_views_and_switches_with_a_fake_transaction() -> None:
    connection = _RowsConnection(
        [
            [
                {
                    "monitoring_date": "2026-01-02",
                    "feature_name": "f_customer_order_frequency_7d",
                    "window_days": 7,
                    "baseline_date": "2025-12-26",
                    "customer_count": 2,
                    "mean_value": 1.0,
                    "psi_vs_baseline": 0.1,
                    "drift_status": "stable",
                }
            ],
            [
                {
                    "id": "customer-1",
                    "event_timestamp": "2026-01-02T00:00:00Z",
                    "label": 1,
                    "f_customer_total_orders_90d": 2,
                    "f_customer_paid_revenue_90d": 10.0,
                    "f_customer_avg_order_value_90d": 5.0,
                    "f_customer_distinct_categories_90d": 1,
                    "f_stream_views_60m": 3,
                    "f_stream_add_to_cart_60m": 2,
                    "f_stream_checkout_started_60m": 1,
                    "f_stream_order_placed_60m": 1,
                    "f_stream_cart_to_purchase_ratio_60m": 0.5,
                    "created": "2026-01-02T00:00:00Z",
                }
            ],
            [{"manifest_sha256": "active-v0"}],
            [{"manifest_sha256": "candidate-v1"}],
        ]
    )
    adapter = FeastPostgresAdapter(connection_factory=lambda: connection)
    health = await adapter.read_feature_health(
        feature_name="f_customer_order_frequency_7d",
        window=TimeWindow(start="2026-01-01T00:00:00Z", end="2026-01-03T00:00:00Z"),
    )
    assert health[0].customer_count == 2
    snapshot = await adapter.read_customer_snapshot(id="customer-1", as_of="2026-01-02T00:00:00Z")
    assert snapshot is not None and snapshot.label == 1
    assert await adapter.switch_active("candidate-v1") == "active-v0"
    await adapter.restore_active("active-v0")


@pytest.mark.asyncio
async def test_feast_adapter_rejects_invalid_registration_validation_and_switch_readback() -> None:
    adapter = FeastPostgresAdapter()
    with pytest.raises(CandidateIndexError, match="index version"):
        await adapter.register_feast_feature_view("")
    with pytest.raises(CandidateIndexError, match="failed candidate validation"):
        await adapter.mark_validated("candidate-v1", type("Report", (), {"passed": False})())
    stale = FeastPostgresAdapter(connection_factory=lambda: _RowsConnection([[]]))
    with pytest.raises(Exception, match="active hash changed"):
        await stale.switch_active("candidate-v1")


@pytest.mark.asyncio
async def test_feast_adapter_persists_validation_and_awaits_runtime_hooks() -> None:
    async def factory() -> _RowsConnection:
        return _RowsConnection([])

    async def activation_hook(_manifest: str | None) -> None:
        return None

    async def fingerprint_hook() -> str:
        return "feast-v1"

    report = IndexValidationReport(
        index_version="candidate-v1",
        recall_at_4=1.0,
        citation_precision=1.0,
        safety_pass_rate=1.0,
        passed=True,
        failures=[],
    )
    adapter = FeastPostgresAdapter(
        connection_factory=factory,
        feast_apply=activation_hook,
        valkey_materialize=activation_hook,
    )
    await adapter.mark_validated("candidate-v1", report)
    await adapter.apply_feast("candidate-v1")
    await adapter.materialize_valkey("candidate-v1")
    assert await adapter.register_feast_feature_view("candidate-v1") == "ecommerce_knowledge_retrieval:candidate-v1"
    assert await _call_hook(fingerprint_hook, "Feast") == "feast-v1"


def test_feast_serialization_contract_rejects_invalid_vectors() -> None:
    assert _stored_value("value") == "value"
    assert _vector_literal([0.0, 1.0]) == "[0,1]"
    with pytest.raises(CandidateIndexError, match="length 384"):
        postgres_validated_vector([1.0])
    with pytest.raises(CandidateIndexError, match="finite"):
        postgres_validated_vector([float("nan")] * 384)


@pytest.mark.asyncio
async def test_datahub_readback_fails_closed_for_each_untrusted_response() -> None:
    emitted: list[dict[str, object]] = []

    async def emit(payload: dict[str, object]) -> None:
        emitted.append(payload)

    adapter = DatahubIndexCatalogAdapter(emit=emit)
    with pytest.raises(DataHubReadBackError, match="no emitted"):
        await adapter.read_back(index_version="candidate-v1")
    await adapter.emit_active(index_version="candidate-v1", previous_index_version="active-v0")
    with pytest.raises(DataHubReadBackError, match="not configured"):
        await adapter.read_back(index_version="candidate-v1")

    async def read_wrong_version(_version: str) -> dict[str, object]:
        return {**emitted[-1], "index_version": "other"}

    adapter = DatahubIndexCatalogAdapter(emit=emit, read=read_wrong_version)
    await adapter.emit_active(index_version="candidate-v2", previous_index_version="candidate-v1")
    with pytest.raises(DataHubReadBackError, match="wrong index version"):
        await adapter.read_back(index_version="candidate-v2")

    async def read_bad_edge(_version: str) -> dict[str, object]:
        return {**emitted[-1], "edges": []}

    adapter = DatahubIndexCatalogAdapter(emit=emit, read=read_bad_edge)
    await adapter.emit_active(index_version="candidate-v3", previous_index_version="candidate-v2")
    with pytest.raises(DataHubReadBackError, match="missing an active lineage edge"):
        await adapter.read_back(index_version="candidate-v3")


@pytest.mark.asyncio
async def test_llmd_and_kagent_adapters_fail_closed_without_live_dependencies() -> None:
    request = ChatRequest(session_id=uuid4(), message="status")
    with pytest.raises(ConnectionError, match="coordinator_dependency"):
        await KagentCoordinatorAdapter().chat(request=request, runtime_variant="v1-primary", route_hint="support")
    adapter = KagentCoordinatorAdapter(readiness=None)
    assert await adapter.is_ready() is False

    async def failed_readiness() -> bool:
        raise RuntimeError("unavailable")

    assert await KagentCoordinatorAdapter(readiness=failed_readiness).is_ready() is False
    with pytest.raises(ValueError, match="unallowlisted"):
        await KagentCoordinatorAdapter().chat(request=request, runtime_variant="v1-unknown", route_hint="support")  # type: ignore[arg-type]
    with pytest.raises(Exception, match="private_llmd_unavailable"):
        await LlmdInferenceAdapter().generate([], "model")

    async def transport(_messages: object, _model: str) -> ObservedGeneration:
        return ObservedGeneration(
            text="ok", model_version="model", input_tokens=1, output_tokens=1,
            total_tokens=2, ttft_ms=1.0, generation_ms=2.0, finish_reason="stop",
        )

    assert (await LlmdInferenceAdapter(transport=transport).generate([], "model")).text == "ok"

    async def timeout_transport(_destination: str, _request: ChatRequest, _route: str) -> object:
        await __import__("asyncio").sleep(0.01)
        return object()

    timeout_adapter = KagentCoordinatorAdapter(transport=timeout_transport)
    timeout_adapter.deadline_seconds = 0
    with pytest.raises(A2ATimeoutError):
        await timeout_adapter.chat(request=request, runtime_variant="v1-primary", route_hint="support")


def test_rag_promotion_stage_transitions_remain_explicit(tmp_path: Path) -> None:
    class Pipeline:
        async def promote_compare_and_swap(self, _version: str, _expected: str | None) -> str:
            return "active-v0"

        async def emit_active_lineage_and_read_back(self, version: str, _prior: str | None) -> str:
            return version

    runtime = rag.RagIndexStageRuntime(
        pipeline=Pipeline(),  # type: ignore[arg-type]
        source_root=tmp_path,
        index_version="candidate-v1",
        evaluation_path=tmp_path / "evaluation.json",
        expected_active_version="active-v0",
        promote=True,
    )
    runtime.completed_stages = list(rag.RAG_INDEX_STAGES[:7])
    assert runtime.run_stage("promote_compare_and_swap") == {
        "stage": "promote_compare_and_swap",
        "promotion": "compare-and-swap",
        "previous_active_version": "active-v0",
    }
    assert runtime.run_stage("emit_active_lineage_and_read_back") == {
        "stage": "emit_active_lineage_and_read_back",
        "promotion": "completed",
        "active_index_version": "candidate-v1",
    }


def test_index_source_parsing_rejects_invalid_source_contracts(tmp_path: Path) -> None:
    with pytest.raises(indexing.SourceParseError, match="UTF-8 BOM"):
        indexing._validate_source_bytes(tmp_path / "shipping.md", b"\xef\xbb\xbfcontent\n")
    with pytest.raises(indexing.SourceParseError, match="LF-only"):
        indexing._validate_source_bytes(tmp_path / "shipping.md", b"content\r\n")
    with pytest.raises(indexing.SourceParseError, match="end with a newline"):
        indexing._validate_source_bytes(tmp_path / "shipping.md", b"content")
    returns = tmp_path / "returns.md"
    returns.write_bytes(b"content\n")
    with pytest.raises(indexing.SourceParseError, match="version separator"):
        indexing._parse_source_file(returns)
    shipping = tmp_path / "shipping.md"
    shipping.write_bytes(b"<!-- version-separator -->\n")
    with pytest.raises(indexing.SourceParseError, match="only returns"):
        indexing._parse_source_file(shipping)
    with pytest.raises(indexing.SourceParseError, match="outside a record"):
        indexing._parse_record(
            "plain text\n",
            source_path=shipping,
            source_sha256="0" * 64,
            expected_category=indexing.KnowledgeCategory.SHIPPING,
            word_minimum=1,
            word_maximum=2,
        )
    with pytest.raises(indexing.SourceParseError, match="malformed front matter"):
        indexing._parse_record(
            "---\nheader\n",
            source_path=shipping,
            source_sha256="0" * 64,
            expected_category=indexing.KnowledgeCategory.SHIPPING,
            word_minimum=1,
            word_maximum=2,
        )


class _IndexStore:
    def __init__(self, *, complete: bool = True, validated: bool = True, active: str | None = "active-v0") -> None:
        self.complete = complete
        self.validated = validated
        self.active = active
        self.marked: list[str] = []
        self.swaps: list[tuple[str | None, str | None]] = []

    async def candidate_complete(self, _version: str) -> bool:
        return self.complete

    async def mark_validated(self, version: str, _report: object) -> None:
        self.marked.append(version)

    async def is_validated(self, _version: str) -> bool:
        return self.validated

    async def active_version(self) -> str | None:
        return self.active

    async def compare_and_swap_active(self, expected: str | None, next_version: str | None) -> None:
        assert self.active == expected
        self.swaps.append((expected, next_version))
        self.active = next_version


class _IndexCatalog:
    def __init__(self, *, fail_active: bool = False) -> None:
        self.fail_active = fail_active
        self.rollbacks: list[tuple[str, str | None, str]] = []

    async def emit_active(self, **_kwargs: object) -> str:
        if self.fail_active:
            raise RuntimeError("lineage unavailable")
        return "urn:active"

    async def read_back(self, **_kwargs: object) -> bool:
        return True

    async def emit_rollback(
        self, *, failed_index_version: str, restored_index_version: str | None, reason: str
    ) -> str:
        self.rollbacks.append((failed_index_version, restored_index_version, reason))
        return "urn:rollback"


def _evaluation_payload(index_version: str, passed: bool) -> str:
    return (
        '{"index_version":"' + index_version
        + '","recall_at_4":1.0,"citation_precision":1.0,"safety_pass_rate":1.0,'
        + f'"passed":{str(passed).lower()},"failures":[]}}'
    )


@pytest.mark.asyncio
async def test_index_pipeline_validates_evidence_before_recording_candidate(tmp_path: Path) -> None:
    evidence = tmp_path / "evaluation.json"
    incomplete = _IndexStore(complete=False)
    with pytest.raises(indexing.CandidateValidationError, match="incomplete"):
        await indexing.RagIndexPipeline(candidate_store=incomplete).validate_candidate("candidate-v1", evidence)
    complete = _IndexStore()
    evidence.write_text("not-json", encoding="utf-8")
    with pytest.raises(indexing.CandidateValidationError, match="evaluation report is invalid"):
        await indexing.RagIndexPipeline(candidate_store=complete).validate_candidate("candidate-v1", evidence)
    evidence.write_text(_evaluation_payload("other", True), encoding="utf-8")
    with pytest.raises(indexing.CandidateValidationError, match="index version"):
        await indexing.RagIndexPipeline(candidate_store=complete).validate_candidate("candidate-v1", evidence)
    evidence.write_text(_evaluation_payload("candidate-v1", False), encoding="utf-8")
    with pytest.raises(indexing.CandidateValidationError, match="did not pass"):
        await indexing.RagIndexPipeline(candidate_store=complete).validate_candidate("candidate-v1", evidence)
    evidence.write_text(_evaluation_payload("candidate-v1", True), encoding="utf-8")
    report = await indexing.RagIndexPipeline(candidate_store=complete).validate_candidate("candidate-v1", evidence)
    assert report.passed is True
    assert complete.marked == ["candidate-v1"]


@pytest.mark.asyncio
async def test_index_pipeline_promotes_and_compensates_explicit_state_transitions() -> None:
    store = _IndexStore(validated=False)
    catalog = _IndexCatalog()
    pipeline = indexing.RagIndexPipeline(candidate_store=store, catalog=catalog)
    with pytest.raises(indexing.CandidateValidationError, match="must be validated"):
        await pipeline.promote_compare_and_swap("candidate-v1", "active-v0")
    store.validated = True
    store.active = "other"
    with pytest.raises(indexing.CandidateValidationError, match="active alias differs"):
        await pipeline.promote_compare_and_swap("candidate-v1", "active-v0")
    store.active = "active-v0"
    assert await pipeline.promote("candidate-v1", "active-v0") == "candidate-v1"
    assert store.swaps == [("active-v0", "candidate-v1")]
    store.active = None
    with pytest.raises(indexing.CandidateValidationError, match="no active alias"):
        await pipeline.rollback("active-v0")
    store.active = "candidate-v1"
    assert await pipeline.rollback("active-v0") == "active-v0"
    assert catalog.rollbacks[-1] == ("candidate-v1", "active-v0", "explicit rollback")
    failing_store = _IndexStore(active="candidate-v1")
    failing_catalog = _IndexCatalog(fail_active=True)
    failing = indexing.RagIndexPipeline(candidate_store=failing_store, catalog=failing_catalog)
    with pytest.raises(RuntimeError, match="lineage unavailable"):
        await failing.emit_active_lineage_and_read_back("candidate-v1", "active-v0")
    assert failing_store.swaps == [("candidate-v1", "active-v0")]
    assert failing_catalog.rollbacks == [("candidate-v1", "active-v0", "lineage unavailable")]


def _section03_rows() -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], dict[str, object]]:
    labels = [{"id": "customer-1", "label": "1"}]
    training = [{"id": "customer-1", "label": "1", "event_timestamp": "2026-01-01T00:00:00Z", "created": "2026-01-01T00:00:00Z"}]
    health = [{"feature_name": "orders", "window_days": "7", "baseline_date": "2025-12-25", "monitoring_date": "2026-01-01", "customer_count": "1"}]
    consumer: dict[str, object] = {
        "training_join": {"feature_cutoff_ts": "2026-01-01T00:00:00Z"},
        "feature_health": {"feature_name": "orders", "window_days": 7, "baseline_date": "2025-12-25", "monitoring_start": "2026-01-01", "monitoring_end": "2026-01-01", "cohort_size": 1},
    }
    return labels, training, health, consumer


@pytest.mark.parametrize(
    ("collection", "key", "value", "message"),
    [
        ("labels", "id", "", "unique non-empty"),
        ("labels", "label", "2", "binary integers"),
        ("training", "id", "other", "cohorts differ"),
        ("training", "label", "0", "labels differ"),
        ("training", "event_timestamp", "other", "cutoff differs"),
        ("health", "feature_name", "other", "feature differs"),
        ("health", "window_days", "8", "horizon differs"),
        ("health", "baseline_date", "other", "baseline differs"),
        ("health", "customer_count", "2", "cohort differs"),
    ],
)
def test_section03_rows_reject_each_consumer_contract_mismatch(
    collection: str, key: str, value: str, message: str
) -> None:
    labels, training, health, consumer = _section03_rows()
    {"labels": labels, "training": training, "health": health}[collection][0][key] = value
    with pytest.raises(ValueError, match=message):
        section03._validate_rows(labels, training, health, consumer)
