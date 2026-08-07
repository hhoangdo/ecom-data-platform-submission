"""Application orchestration for the paused/manual local RAG index DAG."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path

from vina_bim_shop.llm.contracts import (
    IndexBuildReport,
    IndexValidationReport,
    KnowledgeChunk,
    KnowledgeDocumentVersion,
)
from vina_bim_shop.llm.indexing import EXPECTED_SOURCE_FILES, RagIndexPipeline


RAG_INDEX_STAGES = (
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
RAG_INDEX_STAGE_HANDOFF_KEY = "edai2_rag_index_stage_handoff"


@dataclass
class RagIndexStageRuntime:
    """Hold one manual DAG run's handoff state while executing real pipeline stages."""

    pipeline: RagIndexPipeline
    source_root: Path
    index_version: str
    evaluation_path: Path
    expected_active_version: str | None
    promote: bool = False
    completed_stages: list[str] = field(default_factory=list, init=False)
    versions: list[KnowledgeDocumentVersion] | None = field(default=None, init=False)
    chunks: list[KnowledgeChunk] | None = field(default=None, init=False)
    vectors: list[list[float]] | None = field(default=None, init=False)
    report: IndexBuildReport | None = field(default=None, init=False)
    validation: IndexValidationReport | None = field(default=None, init=False)
    prior_active_version: str | None = field(default=None, init=False)
    active_index_version: str | None = field(default=None, init=False)
    _promotion_started: bool = field(default=False, init=False)

    def run_stage(self, stage: str) -> dict[str, object]:
        """Execute exactly the next DAG stage and return its concrete handoff result."""

        if stage not in RAG_INDEX_STAGES:
            raise ValueError(f"unsupported RAG index stage: {stage}")
        if len(self.completed_stages) >= len(RAG_INDEX_STAGES):
            raise ValueError("all RAG index stages have already completed")
        expected_stage = RAG_INDEX_STAGES[len(self.completed_stages)]
        if stage != expected_stage:
            raise ValueError(f"expected RAG index stage {expected_stage}, got {stage}")
        result = asyncio.run(self._run_stage(stage))
        self.completed_stages.append(stage)
        return {"stage": stage, **result}

    def to_handoff(self) -> dict[str, object]:
        """Return the JSON-safe state stored between isolated Airflow tasks."""

        return {
            "source_root": str(self.source_root),
            "index_version": self.index_version,
            "evaluation_path": str(self.evaluation_path),
            "expected_active_version": self.expected_active_version,
            "promote": self.promote,
            "completed_stages": list(self.completed_stages),
            "versions": (
                [version.model_dump(mode="json") for version in self.versions]
                if self.versions is not None
                else None
            ),
            "chunks": (
                [chunk.model_dump(mode="json") for chunk in self.chunks]
                if self.chunks is not None
                else None
            ),
            "vectors": self.vectors,
            "report": self.report.model_dump(mode="json") if self.report else None,
            "validation": (
                self.validation.model_dump(mode="json") if self.validation else None
            ),
            "prior_active_version": self.prior_active_version,
            "active_index_version": self.active_index_version,
            "promotion_started": self._promotion_started,
        }

    @classmethod
    def from_handoff(
        cls,
        handoff: Mapping[str, object],
        *,
        pipeline: RagIndexPipeline,
    ) -> "RagIndexStageRuntime":
        """Rehydrate a stage runtime from a JSON-safe durable handoff document."""

        source_root = handoff.get("source_root")
        index_version = handoff.get("index_version")
        evaluation_path = handoff.get("evaluation_path")
        expected_active_version = handoff.get("expected_active_version")
        promote = handoff.get("promote")
        if not all(
            isinstance(value, str) and value
            for value in (source_root, index_version, evaluation_path)
        ):
            raise ValueError("RAG index handoff is missing required run configuration")
        if expected_active_version is not None and not isinstance(
            expected_active_version, str
        ):
            raise ValueError("RAG index handoff has an invalid expected active version")
        if not isinstance(promote, bool):
            raise ValueError("RAG index handoff has an invalid promotion flag")

        runtime = cls(
            pipeline=pipeline,
            source_root=Path(source_root),
            index_version=index_version,
            evaluation_path=Path(evaluation_path),
            expected_active_version=expected_active_version,
            promote=promote,
        )
        completed_stages = handoff.get("completed_stages")
        if not isinstance(completed_stages, list) or not all(
            isinstance(stage, str) for stage in completed_stages
        ):
            raise ValueError("RAG index handoff has invalid completed stages")
        if completed_stages != list(RAG_INDEX_STAGES[: len(completed_stages)]):
            raise ValueError("RAG index handoff stages are not an ordered prefix")
        runtime.completed_stages = list(completed_stages)

        raw_versions = handoff.get("versions")
        if raw_versions is not None:
            if not isinstance(raw_versions, list):
                raise ValueError("RAG index handoff has invalid document versions")
            runtime.versions = [
                KnowledgeDocumentVersion.model_validate(version)
                for version in raw_versions
            ]
        raw_chunks = handoff.get("chunks")
        if raw_chunks is not None:
            if not isinstance(raw_chunks, list):
                raise ValueError("RAG index handoff has invalid chunks")
            runtime.chunks = [
                KnowledgeChunk.model_validate(chunk) for chunk in raw_chunks
            ]
        raw_vectors = handoff.get("vectors")
        if raw_vectors is not None:
            if not isinstance(raw_vectors, list) or not all(
                isinstance(vector, list)
                and all(
                    isinstance(value, (int, float)) and not isinstance(value, bool)
                    for value in vector
                )
                for vector in raw_vectors
            ):
                raise ValueError("RAG index handoff has invalid embeddings")
            runtime.vectors = [
                [float(value) for value in vector] for vector in raw_vectors
            ]
        raw_report = handoff.get("report")
        if raw_report is not None:
            if not isinstance(raw_report, Mapping):
                raise ValueError("RAG index handoff has an invalid candidate report")
            runtime.report = IndexBuildReport.model_validate(raw_report)
        raw_validation = handoff.get("validation")
        if raw_validation is not None:
            if not isinstance(raw_validation, Mapping):
                raise ValueError("RAG index handoff has an invalid validation report")
            runtime.validation = IndexValidationReport.model_validate(raw_validation)
        for field_name in ("prior_active_version", "active_index_version"):
            value = handoff.get(field_name)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"RAG index handoff has an invalid {field_name}")
            setattr(runtime, field_name, value)
        promotion_started = handoff.get("promotion_started")
        if not isinstance(promotion_started, bool):
            raise ValueError("RAG index handoff has an invalid promotion state")
        runtime._promotion_started = promotion_started
        return runtime

    async def _run_stage(self, stage: str) -> dict[str, object]:
        if stage == "parse_sources":
            self.versions = self.pipeline.parse_candidate_sources(
                [str(self.source_root / filename) for filename in EXPECTED_SOURCE_FILES]
            )
            return {"document_version_count": len(self.versions)}
        if stage == "chunk":
            self.chunks = self.pipeline.chunk_candidate_sources(self._versions())
            return {"chunk_count": len(self.chunks)}
        if stage == "embed":
            self.vectors = await self.pipeline.embed_candidate_chunks(self._chunks())
            return {"embedding_count": len(self.vectors)}
        if stage == "postgres_upsert_candidate_and_pgvector_index":
            self.report = self.pipeline.build_candidate_report(
                self.index_version,
                self._versions(),
                self._chunks(),
                self._vectors(),
            )
            await self.pipeline.persist_candidate(
                self.report,
                self._versions(),
                self._chunks(),
                self._vectors(),
            )
            return {"index_version": self.report.index_version}
        if stage == "register_feast_feature_view":
            service = await self.pipeline.register_candidate_feature_view(self.index_version)
            return {"feature_service": service}
        if stage == "emit_candidate_lineage":
            urn = await self.pipeline.emit_candidate_lineage(
                self._report(),
                self._versions(),
                self._chunks(),
            )
            return {"candidate_lineage_urn": urn}
        if stage == "validate":
            self.validation = await self.pipeline.validate_candidate(
                self.index_version,
                self.evaluation_path,
            )
            return {"validation_passed": self.validation.passed}
        if stage == "promote_compare_and_swap":
            if not self.promote:
                return {"promotion": "not-requested"}
            self.prior_active_version = await self.pipeline.promote_compare_and_swap(
                self.index_version,
                self.expected_active_version,
            )
            self._promotion_started = True
            return {
                "promotion": "compare-and-swap",
                "previous_active_version": self.prior_active_version,
            }
        if stage == "emit_active_lineage_and_read_back":
            if not self.promote:
                return {"promotion": "not-requested"}
            if not self._promotion_started:
                raise ValueError("active lineage cannot run before compare-and-swap")
            self.active_index_version = await self.pipeline.emit_active_lineage_and_read_back(
                self.index_version,
                self.prior_active_version,
            )
            return {
                "promotion": "completed",
                "active_index_version": self.active_index_version,
            }
        raise ValueError(f"unsupported RAG index stage: {stage}")

    def _versions(self) -> list[KnowledgeDocumentVersion]:
        if self.versions is None:
            raise ValueError("parse_sources must complete before this stage")
        return self.versions

    def _chunks(self) -> list[KnowledgeChunk]:
        if self.chunks is None:
            raise ValueError("chunk must complete before this stage")
        return self.chunks

    def _vectors(self) -> list[list[float]]:
        if self.vectors is None:
            raise ValueError("embed must complete before this stage")
        return self.vectors

    def _report(self) -> IndexBuildReport:
        if self.report is None:
            raise ValueError("candidate storage must complete before this stage")
        return self.report


async def run_rag_index_pipeline(
    *,
    pipeline: RagIndexPipeline,
    source_root: Path,
    index_version: str,
    evaluation_path: Path,
    expected_active_version: str | None,
    promote: bool,
) -> dict[str, object]:
    """Run the ordered candidate stages; promotion remains an explicit opt-in."""

    report = await pipeline.build_candidate(
        [str(source_root / filename) for filename in EXPECTED_SOURCE_FILES],
        index_version,
    )
    validation = await pipeline.validate_candidate(index_version, evaluation_path)
    active_index_version: str | None = None
    if promote:
        active_index_version = await pipeline.promote(
            index_version,
            expected_active_version,
        )
    return {
        "stages": RAG_INDEX_STAGES,
        "candidate": report,
        "validation": validation,
        "active_index_version": active_index_version,
    }


def _pipeline_from_airflow_context(context: Mapping[str, object]) -> RagIndexPipeline:
    pipeline = context.get("rag_index_pipeline")
    if pipeline is None:
        return RagIndexPipeline()
    if not isinstance(pipeline, RagIndexPipeline):
        raise RuntimeError("rag_index_pipeline must be a RagIndexPipeline instance")
    return pipeline


def _new_runtime_from_airflow_context(
    context: Mapping[str, object],
) -> RagIndexStageRuntime:
    dag_run = context.get("dag_run")
    conf = getattr(dag_run, "conf", None)
    if not isinstance(conf, Mapping):
        raise RuntimeError(
            "manual RAG index DAG requires dag_run.conf with source_root, "
            "index_version, and evaluation_path"
        )
    source_root = conf.get("source_root")
    index_version = conf.get("index_version")
    evaluation_path = conf.get("evaluation_path")
    expected_active_version = conf.get("expected_active_version")
    promote = conf.get("promote", False)
    if not all(
        isinstance(value, str) and value
        for value in (source_root, index_version, evaluation_path)
    ):
        raise RuntimeError(
            "manual RAG index DAG requires string source_root, index_version, "
            "and evaluation_path values"
        )
    if expected_active_version is not None and not isinstance(
        expected_active_version, str
    ):
        raise RuntimeError("expected_active_version must be a string or null")
    if not isinstance(promote, bool):
        raise RuntimeError("promote must be a boolean and defaults to false")
    return RagIndexStageRuntime(
        pipeline=_pipeline_from_airflow_context(context),
        source_root=Path(source_root),
        index_version=index_version,
        evaluation_path=Path(evaluation_path),
        expected_active_version=expected_active_version,
        promote=promote,
    )


def _handoff_path_from_airflow_context(context: Mapping[str, object]) -> Path:
    dag_run = context.get("dag_run")
    conf = getattr(dag_run, "conf", None)
    handoff_root = conf.get("handoff_root") if isinstance(conf, Mapping) else None
    run_id = getattr(dag_run, "run_id", None)
    if not isinstance(handoff_root, str) or not handoff_root:
        raise RuntimeError(
            "manual RAG index DAG requires a shared local handoff_root in dag_run.conf"
        )
    if not isinstance(run_id, str) or not run_id:
        raise RuntimeError("manual RAG index DAG requires a non-empty Airflow run_id")
    digest = hashlib.sha256(run_id.encode("utf-8")).hexdigest()
    return Path(handoff_root) / f"{digest}.json"


def _write_handoff(path: Path, handoff: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f"{path.name}.tmp")
    temporary_path.write_text(
        json.dumps(handoff, sort_keys=True),
        encoding="utf-8",
    )
    temporary_path.replace(path)


def _read_handoff(path: Path) -> Mapping[str, object]:
    try:
        handoff = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"could not read persisted RAG index handoff at {path}"
        ) from error
    if not isinstance(handoff, Mapping):
        raise RuntimeError(f"persisted RAG index handoff at {path} is not an object")
    return handoff


def _runtime_from_airflow_context(
    stage: str,
    context: Mapping[str, object],
) -> tuple[RagIndexStageRuntime, object, Path]:
    task_instance = context.get("ti")
    if not callable(getattr(task_instance, "xcom_pull", None)) or not callable(
        getattr(task_instance, "xcom_push", None)
    ):
        raise RuntimeError("manual RAG index DAG requires an Airflow task instance")
    if stage == RAG_INDEX_STAGES[0]:
        return (
            _new_runtime_from_airflow_context(context),
            task_instance,
            _handoff_path_from_airflow_context(context),
        )

    previous_stage = RAG_INDEX_STAGES[RAG_INDEX_STAGES.index(stage) - 1]
    handoff_reference = task_instance.xcom_pull(
        task_ids=previous_stage,
        key=RAG_INDEX_STAGE_HANDOFF_KEY,
    )
    if not isinstance(handoff_reference, Mapping):
        raise RuntimeError(
            f"missing persisted RAG index handoff from {previous_stage}; retry that "
            "upstream task instead of reconstructing candidate state"
        )
    handoff_path = handoff_reference.get("handoff_path")
    if not isinstance(handoff_path, str) or not handoff_path:
        raise RuntimeError(
            f"persisted RAG index handoff from {previous_stage} has no handoff_path"
        )
    return (
        RagIndexStageRuntime.from_handoff(
            _read_handoff(Path(handoff_path)),
            pipeline=_pipeline_from_airflow_context(context),
        ),
        task_instance,
        Path(handoff_path),
    )


def run_rag_index_stage(
    stage: str,
    *,
    runtime: RagIndexStageRuntime | None = None,
    **context: object,
) -> dict[str, object]:
    """Execute one real stage with an explicit runtime or durable Airflow handoff."""

    supplied_runtime = runtime or context.get("rag_index_runtime")
    if isinstance(supplied_runtime, RagIndexStageRuntime):
        return supplied_runtime.run_stage(stage)
    if supplied_runtime is not None:
        raise RuntimeError("rag_index_runtime must be a RagIndexStageRuntime instance")
    if stage not in RAG_INDEX_STAGES:
        raise ValueError(f"unsupported RAG index stage: {stage}")

    airflow_runtime, task_instance, handoff_path = _runtime_from_airflow_context(
        stage,
        context,
    )
    result = airflow_runtime.run_stage(stage)
    _write_handoff(handoff_path, airflow_runtime.to_handoff())
    task_instance.xcom_push(
        key=RAG_INDEX_STAGE_HANDOFF_KEY,
        value={"handoff_path": str(handoff_path)},
    )
    return result


__all__ = [
    "RAG_INDEX_STAGES",
    "RAG_INDEX_STAGE_HANDOFF_KEY",
    "RagIndexStageRuntime",
    "run_rag_index_pipeline",
    "run_rag_index_stage",
]
