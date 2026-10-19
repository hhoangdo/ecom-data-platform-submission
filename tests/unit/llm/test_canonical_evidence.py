from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
COMMIT = "7233469eef8519aeb059da03a924bb6a180bed5b"
CANONICAL = f"canonical-evidence-{COMMIT}"


def _load_script():
    path = ROOT / "scripts/llm/build_index.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _dag_result() -> dict:
    return {
        "dag_id": "rag_index_pipeline",
        "run_id": "manual__2026-10-18",
        "state": "success",
        "index_version": CANONICAL,
        "candidate_label": "canonical-evidence",
        "document_count": 8,
        "document_version_count": 9,
        "chunk_count": 120,
        "embedding_dimension": 384,
        "gate_60_case": {"pass": True, "cases": 60},
        "promotion": {"previous_alias": "candidate-old", "active_alias": CANONICAL, "cas": True},
        "lineage": {
            "source": "data/knowledge/ecommerce",
            "versions": 9,
            "chunks": 120,
            "candidate": CANONICAL,
            "active": CANONICAL,
            "feast_view": "edai2_rag",
        },
        "content_sha256": ["aaa", "bbb"],
    }


def _datahub() -> dict:
    return {
        "dataset_urns": ["urn:li:dataset:(urn:li:dataPlatform:postgres,edai2.rag_chunks,PROD)"],
        "active_version": CANONICAL,
        "response_hashes": ["c" * 64],
    }


def _bootstrap() -> dict:
    return {"jobs": [{"image": "registry/edai2-rag-index:7233469", "expected_digest": "sha256:" + "d" * 64}]}


def test_canonical_identity_accepts_exact_lowercase_full_commit() -> None:
    build = _load_script()
    assert build.verify_canonical_identity(CANONICAL, COMMIT) == CANONICAL
    for bad in (
        "ci-bootstrap-abc", "test_idx_001", CANONICAL.upper(),
        "canonical-evidence-7233469", "canonical-evidence-" + COMMIT[:7],
    ):
        with pytest.raises(ValueError, match="index version"):
            build.verify_canonical_identity(bad, COMMIT)


def test_airflow_evidence_passes_on_complete_run() -> None:
    build = _load_script()
    result = build.verify_airflow_evidence(
        dag_result=_dag_result(), bootstrap_evidence=_bootstrap(), datahub=_datahub(),
        index_version=CANONICAL, expected_commit=COMMIT,
    )
    assert result["promoted"] is True and result["datahub_read_back"] is True


def test_airflow_evidence_rejects_bootstrap_artifact_reuse() -> None:
    """A candidate reusing bootstrap output is never Sheet3!E8:E9 proof."""
    build = _load_script()
    dag = _dag_result()
    dag["candidate_label"] = "ci-bootstrap"
    with pytest.raises(ValueError, match="bootstrap"):
        build.verify_airflow_evidence(
            dag_result=dag, bootstrap_evidence=_bootstrap(), datahub=_datahub(),
            index_version=CANONICAL, expected_commit=COMMIT,
        )
    dag = _dag_result()
    dag["content_sha256"] = ["sha256:" + "d" * 64]
    with pytest.raises(ValueError, match="bootstrap"):
        build.verify_airflow_evidence(
            dag_result=dag, bootstrap_evidence=_bootstrap(), datahub=_datahub(),
            index_version=CANONICAL, expected_commit=COMMIT,
        )


def test_airflow_evidence_rejects_failed_gate_or_datahub_mismatch() -> None:
    build = _load_script()
    dag = _dag_result()
    dag["gate_60_case"] = {"pass": False, "cases": 60}
    with pytest.raises(ValueError, match="gate"):
        build.verify_airflow_evidence(
            dag_result=dag, bootstrap_evidence=_bootstrap(), datahub=_datahub(),
            index_version=CANONICAL, expected_commit=COMMIT,
        )
    datahub = _datahub()
    datahub["active_version"] = "stale-version"
    with pytest.raises(ValueError, match="DataHub"):
        build.verify_airflow_evidence(
            dag_result=_dag_result(), bootstrap_evidence=_bootstrap(), datahub=datahub,
            index_version=CANONICAL, expected_commit=COMMIT,
        )


def _trigger_argv(**overrides: str) -> list[str]:
    base = {
        "--dag-id": "rag_index_pipeline",
        "--source-root": "data/knowledge/ecommerce",
        "--index-version": CANONICAL,
        "--index-purpose": "canonical-evidence",
        "--commit-sha": COMMIT,
        "--airflow-url": "https://airflow.example.com",
        "--airflow-auth-env": "EDAI2_AIRFLOW_AUTH",
        "--dag-result": "tmp/dag_result.json",
        "--bootstrap-evidence": "evidence/04_2_llm_design/cicd/jobs.json",
        "--output": "tmp/index_run.json",
    }
    base.update(overrides)
    argv: list[str] = ["--trigger-airflow"]
    for key, value in base.items():
        argv.extend([key, value])
    return argv


def test_trigger_airflow_requires_explicit_airflow_wiring() -> None:
    """--trigger-airflow never guesses operator inputs; all three must be explicit."""
    build = _load_script()
    for missing in ("--airflow-url", "--airflow-auth-env", "--dag-result"):
        argv: list[str] = ["--trigger-airflow"]
        base = {
            "--dag-id": "rag_index_pipeline",
            "--source-root": "data/knowledge/ecommerce",
            "--index-version": CANONICAL,
            "--index-purpose": "canonical-evidence",
            "--commit-sha": COMMIT,
            "--airflow-url": "https://airflow.example.com",
            "--airflow-auth-env": "EDAI2_AIRFLOW_AUTH",
            "--dag-result": "tmp/dag_result.json",
            "--bootstrap-evidence": "evidence/04_2_llm_design/cicd/jobs.json",
            "--output": "tmp/index_run.json",
        }
        for key, value in base.items():
            if key == missing:
                continue
            argv.extend([key, value])
        with pytest.raises(SystemExit):
            build.parse_args(argv)


def test_trigger_airflow_rejects_guessed_non_https_airflow_url() -> None:
    """Documented operator inputs only: localhost/http guesses never trigger a DAG."""
    build = _load_script()
    argv = _trigger_argv(**{"--airflow-url": "http://localhost:8080"})
    with pytest.raises(SystemExit):
        build.parse_args(argv)
    valid = build.parse_args(_trigger_argv())
    assert valid.airflow_url.startswith("https://")
