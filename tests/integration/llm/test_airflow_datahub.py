from __future__ import annotations

import json
import runpy
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest

from vina_bim_shop.llm.adapters.datahub import (
    DataHubReadBackError,
    DatahubIndexCatalogAdapter,
)
from vina_bim_shop.llm.contracts import IndexBuildReport, IndexValidationReport
from vina_bim_shop.llm.indexing import RagIndexPipeline
from vina_bim_shop.orchestration.rag_index_pipeline import (
    RAG_INDEX_STAGES,
    RagIndexStageRuntime,
    run_rag_index_pipeline,
    run_rag_index_stage,
)
from vina_bim_shop.orchestration.specs import dag_specs_by_id


REPO_ROOT = Path(__file__).resolve().parents[3]
DAG_PATH = REPO_ROOT / "infra/orchestration/airflow/dags/rag_index_pipeline.py"
FEATURE_STORE_PATH = REPO_ROOT / "infra/feast/feature_store.yaml"
FEATURES_PATH = REPO_ROOT / "infra/feast/features.py"
RECIPE_PATH = REPO_ROOT / "infra/governance/recipes/edai2_rag.yml"
INDEX_SQL = REPO_ROOT / "infra/postgres/edai2/002_knowledge_index.sql"
SOURCE_ROOT = REPO_ROOT / "data/knowledge/ecommerce"


class FakeTokenizer:
    def encode(self, _text: str, *, add_special_tokens: bool) -> list[int]:
        assert add_special_tokens is False
        return [1, 2, 3]

    def decode(self, token_ids: list[int], **_kwargs: object) -> str:
        return " ".join(str(token) for token in token_ids)


class FakeEmbedder:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] + [0.0] * 383 for _ in texts]


class FakeStore:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.active: str | None = "prior-index"
        self.validated: set[str] = set()

    async def upsert_candidate(self, **_kwargs: object) -> None:
        self.calls.append("postgres_upsert_candidate_and_pgvector_index")

    async def register_feast_feature_view(self, index_version: str) -> str:
        self.calls.append("register_feast_feature_view")
        return f"feast:{index_version}"

    async def candidate_complete(self, _index_version: str) -> bool:
        return True

    async def mark_validated(
        self, index_version: str, _report: IndexValidationReport
    ) -> None:
        self.calls.append("validate")
        self.validated.add(index_version)

    async def is_validated(self, index_version: str) -> bool:
        return index_version in self.validated

    async def active_version(self) -> str | None:
        return self.active

    async def compare_and_swap_active(
        self, expected: str | None, next_version: str | None
    ) -> str | None:
        if self.active != expected:
            raise RuntimeError("stale alias")
        self.active = next_version
        self.calls.append("promote_compare_and_swap")
        return self.active


class FakeCatalog:
    def __init__(self, *, fail_read_back: bool = False) -> None:
        self.events: list[str] = []
        self.fail_read_back = fail_read_back

    async def emit_candidate(self, **_kwargs: object) -> str:
        self.events.append("emit_candidate_lineage")
        return "candidate-urn"

    async def emit_active(self, **_kwargs: object) -> str:
        self.events.append("emit_active_lineage_and_read_back")
        return "active-urn"

    async def emit_rollback(self, **_kwargs: object) -> str:
        self.events.append("emit_rollback_lineage")
        return "rollback-urn"

    async def read_back(self, **_kwargs: object) -> bool:
        if self.fail_read_back:
            raise DataHubReadBackError("missing active edge")
        return True


def _evaluation(path: Path, *, passed: bool = True) -> Path:
    path.write_text(
        json.dumps(
            {
                "index_version": "candidate-1",
                "recall_at_4": 1.0,
                "citation_precision": 1.0,
                "safety_pass_rate": 1.0,
                "passed": passed,
                "failures": [] if passed else ["candidate validation failed"],
            }
        ),
        encoding="utf-8",
    )
    return path


@pytest.mark.asyncio
async def test_pipeline_uses_exact_stage_order_and_compensates_read_back_failure(
    tmp_path: Path,
) -> None:
    store = FakeStore()
    catalog = FakeCatalog(fail_read_back=True)
    pipeline = RagIndexPipeline(
        tokenizer=FakeTokenizer(),
        embedder=FakeEmbedder(),
        candidate_store=store,
        catalog=catalog,
    )

    with pytest.raises(DataHubReadBackError):
        await run_rag_index_pipeline(
            pipeline=pipeline,
            source_root=SOURCE_ROOT,
            index_version="candidate-1",
            evaluation_path=_evaluation(tmp_path / "evaluation.json"),
            expected_active_version="prior-index",
            promote=True,
        )

    assert RAG_INDEX_STAGES == (
        "parse_sources",
        "chunk",
        "embed",
        "postgres_upsert_candidate_and_pgvector_index",
        "register_feast_feature_view",
        "emit_candidate_lineage",
        "validate",
        "promote_compare_and_swap",
        "emit_active_lineage_and_read_back",
    )
    assert store.active == "prior-index"
    assert store.calls == [
        "postgres_upsert_candidate_and_pgvector_index",
        "register_feast_feature_view",
        "validate",
        "promote_compare_and_swap",
        "promote_compare_and_swap",
    ]
    assert catalog.events == [
        "emit_candidate_lineage",
        "emit_active_lineage_and_read_back",
        "emit_rollback_lineage",
    ]


def test_airflow_stage_callable_executes_real_pre_promotion_handoff(
    tmp_path: Path,
) -> None:
    store = FakeStore()
    catalog = FakeCatalog()
    runtime = RagIndexStageRuntime(
        pipeline=RagIndexPipeline(
            tokenizer=FakeTokenizer(),
            embedder=FakeEmbedder(),
            candidate_store=store,
            catalog=catalog,
        ),
        source_root=SOURCE_ROOT,
        index_version="candidate-1",
        evaluation_path=_evaluation(tmp_path / "evaluation.json"),
        expected_active_version="prior-index",
        promote=False,
    )

    results = [
        run_rag_index_stage(stage=stage, runtime=runtime) for stage in RAG_INDEX_STAGES
    ]

    assert [result["stage"] for result in results] == [
        "parse_sources",
        "chunk",
        "embed",
        "postgres_upsert_candidate_and_pgvector_index",
        "register_feast_feature_view",
        "emit_candidate_lineage",
        "validate",
        "promote_compare_and_swap",
        "emit_active_lineage_and_read_back",
    ]
    assert runtime.completed_stages == list(RAG_INDEX_STAGES)
    assert store.calls == [
        "postgres_upsert_candidate_and_pgvector_index",
        "register_feast_feature_view",
        "validate",
    ]
    assert catalog.events == ["emit_candidate_lineage"]
    assert store.active == "prior-index"
    assert results[-1]["promotion"] == "not-requested"


def test_checked_in_dag_callable_uses_durable_stage_handoff(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class FakeDAG:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> "FakeDAG":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    class FakePythonOperator:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def __rshift__(self, other: "FakePythonOperator") -> "FakePythonOperator":
            return other

    class FakeTaskInstance:
        def __init__(self) -> None:
            self.task_id = ""
            self.values: dict[tuple[str, str], dict[str, object]] = {}

        def xcom_push(self, *, key: str, value: dict[str, object]) -> None:
            self.values[(self.task_id, key)] = json.loads(json.dumps(value))

        def xcom_pull(self, *, task_ids: str, key: str) -> dict[str, object] | None:
            return self.values.get((task_ids, key))

    class FakeDagRun:
        def __init__(self, conf: dict[str, object], *, run_id: str) -> None:
            self.conf = conf
            self.run_id = run_id

    airflow = types.ModuleType("airflow")
    airflow.DAG = FakeDAG
    operators = types.ModuleType("airflow.operators")
    python_operators = types.ModuleType("airflow.operators.python")
    python_operators.PythonOperator = FakePythonOperator
    monkeypatch.setitem(sys.modules, "airflow", airflow)
    monkeypatch.setitem(sys.modules, "airflow.operators", operators)
    monkeypatch.setitem(sys.modules, "airflow.operators.python", python_operators)
    dag_globals = runpy.run_path(str(DAG_PATH))

    store = FakeStore()
    catalog = FakeCatalog()
    task_instance = FakeTaskInstance()
    context = {
        "dag_run": FakeDagRun(
            {
                "source_root": str(SOURCE_ROOT),
                "index_version": "candidate-1",
                "evaluation_path": str(_evaluation(tmp_path / "evaluation.json")),
                "expected_active_version": "prior-index",
                "promote": False,
                "handoff_root": str(tmp_path / "handoffs"),
            },
            run_id="manual__candidate-1",
        ),
        "ti": task_instance,
        "rag_index_pipeline": RagIndexPipeline(
            tokenizer=FakeTokenizer(),
            embedder=FakeEmbedder(),
            candidate_store=store,
            catalog=catalog,
        ),
    }

    results = []
    for stage in RAG_INDEX_STAGES:
        task_instance.task_id = stage
        results.append(dag_globals["_run"](stage=stage, **context))

    assert [result["stage"] for result in results] == list(RAG_INDEX_STAGES)
    assert store.calls == [
        "postgres_upsert_candidate_and_pgvector_index",
        "register_feast_feature_view",
        "validate",
    ]
    assert catalog.events == ["emit_candidate_lineage"]
    assert store.active == "prior-index"
    assert results[-1]["promotion"] == "not-requested"
    assert all(
        set(value) == {"handoff_path"} for value in task_instance.values.values()
    )
    handoff_paths = {value["handoff_path"] for value in task_instance.values.values()}
    assert len(handoff_paths) == 1
    handoff = json.loads(Path(handoff_paths.pop()).read_text(encoding="utf-8"))
    assert handoff["completed_stages"] == list(RAG_INDEX_STAGES)


@pytest.mark.asyncio
async def test_datahub_adapter_requires_candidate_active_edges_and_read_back_hash() -> None:
    emitted: list[dict[str, object]] = []

    async def emit(payload: dict[str, object]) -> None:
        emitted.append(payload)

    async def read(_index_version: str) -> dict[str, object]:
        return emitted[-1]

    adapter = DatahubIndexCatalogAdapter(emit=emit, read=read)
    build = IndexBuildReport(
        index_version="candidate-1",
        candidate_label="ci-bootstrap",
        document_count=8,
        document_version_count=9,
        chunk_count=17,
        embedding_dimension=384,
        source_sha256={"returns.md": "a" * 64},
        version_content_sha256={"returns-policy@1.0.0": "b" * 64},
        chunk_content_sha256={"c" * 64: "d" * 64},
        embedding_sha256={"c" * 64: "e" * 64},
        embedding_model="BAAI/bge-small-en-v1.5",
        embedding_revision="5c38ec7c405ec4b44b94cc5a9bb96e735b38267a",
        tokenizer_model="BAAI/bge-small-en-v1.5",
        tokenizer_revision="5c38ec7c405ec4b44b94cc5a9bb96e735b38267a",
    )
    await adapter.emit_candidate(report=build, versions=[], chunks=[])
    await adapter.emit_active(
        index_version="candidate-1", previous_index_version="prior-index"
    )

    assert await adapter.read_back(index_version="candidate-1") is True
    assert emitted[-1]["edges"] == ["candidate-1->active", "active->feast", "feast->api"]


def test_paused_manual_dag_and_declared_lineage_contracts_exist() -> None:
    dag = DAG_PATH.read_text(encoding="utf-8")
    feature_store = FEATURE_STORE_PATH.read_text(encoding="utf-8")
    features = FEATURES_PATH.read_text(encoding="utf-8")
    recipe = RECIPE_PATH.read_text(encoding="utf-8")

    assert 'dag_id="rag_index_pipeline"' in dag
    assert "schedule=None" in dag
    assert "is_paused_upon_creation=True" in dag
    assert "catchup=False" in dag
    for stage in RAG_INDEX_STAGES:
        assert f'task_id="{stage}"' in dag
    assert dag_specs_by_id()["rag_index_pipeline"].schedule == "manual"
    assert dag_specs_by_id()["rag_index_pipeline"].supports_hourly_logical_window is False
    assert "type: postgres" in feature_store
    assert "ecommerce_knowledge_retrieval" in features
    assert "embedding" in features and "384" in features
    for node in ["source", "document_version", "chunk", "embedding", "candidate", "active", "feast", "api"]:
        assert node in recipe


def test_feast_declared_relation_matches_the_postgres_feature_schema() -> None:
    features = runpy.run_path(str(FEATURES_PATH))
    source = features["POSTGRES_DOCUMENT_SOURCE"]
    feature_view = features["DOCUMENT_FEATURE_VIEW"]
    migration = INDEX_SQL.read_text(encoding="utf-8")

    assert source["table"] == "edai2_rag_feast_document_feature"
    assert source["timestamp_field"] == "event_timestamp"
    assert "CREATE VIEW edai2_rag_feast_document_feature AS" in migration
    for selected_column in [
        "chunk.chunk_id",
        "chunk.document_id",
        "chunk.category",
        "embedding.embedding",
        "candidate.created_at AS event_timestamp",
    ]:
        assert selected_column in migration
    assert [feature["name"] for feature in feature_view["features"]] == [
        "chunk_id",
        "category",
        "embedding",
    ]
