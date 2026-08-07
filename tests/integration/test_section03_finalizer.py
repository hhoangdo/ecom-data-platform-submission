from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
from typing import Any
import uuid

import pandas as pd
from PIL import Image
import pytest



_FINALIZER_PATH = Path(__file__).resolve().parents[2] / "scripts" / "generate" / "finalize_section03_evidence.py"
_FINALIZER_SPEC = importlib.util.spec_from_file_location("section03_finalizer", _FINALIZER_PATH)
if _FINALIZER_SPEC is None or _FINALIZER_SPEC.loader is None:
    raise ImportError(f"cannot load finalizer module: {_FINALIZER_PATH}")
finalizer = importlib.util.module_from_spec(_FINALIZER_SPEC)
_FINALIZER_SPEC.loader.exec_module(finalizer)


CANDIDATE_ARTIFACT_KEYS = (
    "config_snapshot",
    "labels",
    "feature_health_daily",
    "drift_alerts",
    "training_join",
    "labels_sample",
    "feature_health_sample",
    "drift_alerts_sample",
    "training_sample",
    "evidence_image",
    "quality_report",
)
FINAL_ARTIFACT_KEYS = set(CANDIDATE_ARTIFACT_KEYS) | {
    "spark_runtime_manifest",
    "airflow_runtime_manifest",
    "datahub_lineage",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bundle_id(artifact_hashes: dict[str, str]) -> str:
    return hashlib.sha256(
        json.dumps(artifact_hashes, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _csv_metadata(path: Path) -> tuple[int, list[str]]:
    frame = pd.read_csv(path)
    return len(frame), list(frame.columns)


def _write_candidate(
    evidence_root: Path,
    *,
    report_suffix: str = "",
    previous_bundle_id: str | None = None,
) -> dict[str, Any]:
    build_root = evidence_root / "runs" / f".candidate-build-{uuid.uuid4().hex}"
    sample_root = build_root / "sample_rows"
    sample_root.mkdir(parents=True)

    files: dict[str, tuple[str, bytes]] = {
        "config_snapshot": ("config_snapshot.yaml", b"schema_version: 1\nscale: medium\nseed: 42\n"),
        "labels": ("ml_customer_label.csv", b"id,label\nc001,1\nc002,0\n"),
        "feature_health_daily": (
            "agg_feature_health_daily.csv",
            b"monitoring_date,feature_name,window_days,baseline_date,customer_count,mean_value,stddev_value,psi_vs_baseline,drift_status,warning_flag,alert_flag\n"
            b"2026-04-10,f_customer_order_frequency_7d,7,2026-04-10,2,1.0,0.5,0.10,warning,true,false\n"
            b"2026-04-11,f_customer_order_frequency_7d,7,2026-04-10,2,1.2,0.6,0.16,alert,true,true\n",
        ),
        "drift_alerts": (
            "feature_drift_alerts.csv",
            b"alert_date,feature_name,psi_value,threshold,action\n"
            b"2026-04-11,f_customer_order_frequency_7d,0.16,0.15,Investigate customer_order_frequency drift\n",
        ),
        "training_join": (
            "ml_customer_purchase_training.csv",
            b"id,label,event_timestamp,created\n"
            b"c001,1,2026-04-24T23:59:00Z,2026-04-24T23:59:00Z\n"
            b"c002,0,2026-04-24T23:59:00Z,2026-04-24T23:59:00Z\n",
        ),
        "labels_sample": ("sample_rows/ml_customer_label.csv", b"id,label\nc001,1\nc002,0\n"),
        "feature_health_sample": (
            "sample_rows/agg_feature_health_daily.csv",
            b"monitoring_date,feature_name,window_days,baseline_date,customer_count,mean_value,stddev_value,psi_vs_baseline,drift_status,warning_flag,alert_flag\n"
            b"2026-04-11,f_customer_order_frequency_7d,7,2026-04-10,2,1.2,0.6,0.16,alert,true,true\n",
        ),
        "drift_alerts_sample": (
            "sample_rows/feature_drift_alerts.csv",
            b"alert_date,feature_name,psi_value,threshold,action\n"
            b"2026-04-11,f_customer_order_frequency_7d,0.16,0.15,Investigate customer_order_frequency drift\n",
        ),
        "training_sample": (
            "sample_rows/ml_customer_purchase_training.csv",
            b"id,label,event_timestamp,created\n"
            b"c001,1,2026-04-24T23:59:00Z,2026-04-24T23:59:00Z\n",
        ),
        "quality_report": (
            "section03_report.md",
            (
                "# Section 03 report\n\n"
                "## Spark/dbt Parity Runtime\nPending\n\n"
                "## Airflow DP3 Runtime\nPending\n\n"
                "## DataHub Lineage Runtime\nPending\n"
                f"{report_suffix}\n"
            ).encode("utf-8"),
        ),
    }
    for relative_path, content in files.values():
        path = build_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    image_path = build_root / "section03_config_and_training_join.png"
    Image.new("RGB", (1600, 900), "white").save(image_path)
    files["evidence_image"] = ("section03_config_and_training_join.png", image_path.read_bytes())

    artifact_hashes = {
        key: _sha256(build_root / relative_path)
        for key, (relative_path, _) in files.items()
    }
    candidate_id = _bundle_id(artifact_hashes)
    bundle_root = evidence_root / "runs" / candidate_id
    bundle_root.parent.mkdir(parents=True, exist_ok=True)
    if bundle_root.exists():
        shutil.rmtree(bundle_root)
    shutil.copytree(build_root, bundle_root)

    artifacts: dict[str, dict[str, Any]] = {}
    for key, (relative_path, _) in files.items():
        path = bundle_root / relative_path
        metadata: dict[str, Any] = {
            "path": f"runs/{candidate_id}/{relative_path}",
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        if key not in {"config_snapshot", "evidence_image", "quality_report"}:
            row_count, columns = _csv_metadata(path)
            metadata.update(row_count=row_count, columns=columns)
        artifacts[key] = metadata

    source_config_sha256 = hashlib.sha256(b"scale: medium\nseed: 42\n").hexdigest()
    candidate: dict[str, Any] = {
        "schema_version": 1,
        "section": "03_data_generator_improvement",
        "generated_at": "2026-08-07T00:00:00Z",
        "source_config_path": "configs/generator/base.yaml",
        "source_config_sha256": source_config_sha256,
        "bundle_id": candidate_id,
        "previous_bundle_id": previous_bundle_id,
        "config_snapshot": artifacts["config_snapshot"]["path"],
        "scale": "medium",
        "random_seed": 42,
        "history_days": 60,
        "windows": {
            "start_ts": "2026-03-03T23:59:00Z",
            "end_ts": "2026-05-01T23:59:00Z",
            "drift_start_ts": "2026-04-11T08:23:00Z",
            "feature_cutoff_ts": "2026-04-24T23:59:00Z",
            "label_end_ts": "2026-05-01T23:59:00Z",
            "baseline_date": "2026-04-10",
        },
        "drift_config": {
            "enabled": True,
            "scenario": "customer_order_frequency",
            "mode": "abrupt",
            "cutoff_fraction": 0.65,
            "post_rate_multiplier": 1.5,
            "psi_warning": 0.1,
            "psi_alert": 0.15,
            "label_horizon_days": 7,
        },
        "configured_entity_counts": {"customers": 2},
        "observed_entity_counts": {"customers": 2},
        "rate_summary": {"order_normalized_post_pre_ratio": 1.5},
        "consumer_contract": {
            "schema_version": 1,
            "label": {
                "artifact_key": "labels",
                "path": artifacts["labels"]["path"],
                "sha256": artifacts["labels"]["sha256"],
                "columns": ["id", "label"],
                "entity_key": "id",
            },
            "training_join": {
                "artifact_key": "training_join",
                "path": artifacts["training_join"]["path"],
                "sha256": artifacts["training_join"]["sha256"],
                "entity_key": "id",
                "event_timestamp_column": "event_timestamp",
                "feature_cutoff_ts": "2026-04-24T23:59:00Z",
                "point_in_time_rule": "event_timestamp <= as_of and created <= event_timestamp",
            },
            "feature_health": {
                "artifact_key": "feature_health_daily",
                "path": artifacts["feature_health_daily"]["path"],
                "sha256": artifacts["feature_health_daily"]["sha256"],
                "feature_name": "f_customer_order_frequency_7d",
                "window_days": 7,
                "baseline_date": "2026-04-10",
                "monitoring_start": "2026-04-10",
                "monitoring_end": "2026-04-11",
                "cohort_size": 2,
                "psi_column": "psi_vs_baseline",
                "status_column": "drift_status",
                "warning_threshold": 0.1,
                "alert_threshold": 0.15,
            },
        },
        "rubric_cells": {
            "E32": {
                "points": 1,
                "status": "Candidate",
                "required_checks": [
                    "configured_counts_preserved",
                    "streaming_distribution_inherited",
                    "training_join_one_to_one",
                    "point_in_time_safe",
                ],
                "artifact_keys": ["config_snapshot", "training_join", "evidence_image"],
            },
            "E33": {
                "points": 1,
                "status": "Candidate",
                "required_checks": ["configured_counts_preserved"],
                "artifact_keys": ["config_snapshot"],
            },
            "E34": {
                "points": 2,
                "status": "Candidate",
                "required_checks": ["labels_exact_schema", "labels_unique", "labels_binary"],
                "artifact_keys": ["labels", "labels_sample"],
            },
        },
        "checks": {
            "configured_counts_preserved": True,
            "streaming_distribution_inherited": True,
            "labels_exact_schema": True,
            "labels_unique": True,
            "labels_binary": True,
            "training_join_one_to_one": True,
            "point_in_time_safe": True,
            "psi_finite": True,
            "alert_threshold_respected": True,
        },
        "runtime_evidence": {"status": "pending", "spark": None, "airflow": None, "datahub": None},
        "artifacts": artifacts,
    }
    manifest_path = evidence_root / "section03_candidate_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(candidate, indent=2) + "\n", encoding="utf-8")
    return {"manifest": manifest_path, "bundle_id": candidate_id, "manifest_data": candidate}


def _write_runtime_root(
    root: Path,
    candidate: dict[str, Any],
    kind: str,
    *,
    status: str = "success",
    mutate: Any = None,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    nested = root / "nested" / f"{kind}_metrics.json"
    nested.parent.mkdir(parents=True, exist_ok=True)
    nested.write_text(json.dumps({"kind": kind, "rows": 2}) + "\n", encoding="utf-8")
    nested_metadata = {
        "path": nested.relative_to(root).as_posix(),
        "size_bytes": nested.stat().st_size,
        "sha256": _sha256(nested),
    }
    run_manifest: dict[str, Any] = {
        "status": status,
        "section": "03_data_generator_improvement",
        "mode": "section03",
        "run_id": f"{kind}-run-1",
        "bundle_id": candidate["bundle_id"],
        "candidate_bundle_id": candidate["bundle_id"],
        "config_sha256": candidate["source_config_sha256"],
        "source_config_sha256": candidate["source_config_sha256"],
        "scale": candidate["scale"],
        "random_seed": candidate["random_seed"],
        "feature_cutoff_ts": candidate["windows"]["feature_cutoff_ts"],
        "label_end_ts": candidate["windows"]["label_end_ts"],
        "artifacts": [nested_metadata],
    }
    if kind == "datahub":
        lineage = root / "lineage.json"
        lineage.write_text(json.dumps({"kind": "datahub", "status": "success"}) + "\n", encoding="utf-8")
        run_manifest["lineage"] = "lineage.json"
        run_manifest["artifacts"].append(
            {"path": "lineage.json", "size_bytes": lineage.stat().st_size, "sha256": _sha256(lineage)}
        )
    if mutate is not None:
        mutate(run_manifest, nested)
    (root / "run_manifest.json").write_text(json.dumps(run_manifest, indent=2) + "\n", encoding="utf-8")
    return root


def _runtime_roots(tmp_path: Path, candidate: dict[str, Any], *, mutate: Any = None) -> tuple[Path, Path, Path]:
    runtime_root = tmp_path / "runtime"
    return (
        _write_runtime_root(runtime_root / "spark", candidate, "spark", mutate=mutate),
        _write_runtime_root(runtime_root / "airflow", candidate, "airflow"),
        _write_runtime_root(runtime_root / "datahub", candidate, "datahub"),
    )


def test_finalize_promotes_fourteen_artifact_manifest_and_rebinds_paths(tmp_path: Path) -> None:
    evidence_root = tmp_path / "evidence"
    candidate = _write_candidate(evidence_root)
    spark_root, airflow_root, datahub_root = _runtime_roots(tmp_path, candidate["manifest_data"])
    active_manifest = evidence_root / "section03_manifest.json"

    result = finalizer.finalize_section03_evidence(
        candidate_manifest=candidate["manifest"],
        active_manifest=active_manifest,
        spark_root=spark_root,
        airflow_root=airflow_root,
        datahub_root=datahub_root,
        clean=True,
    )

    assert result == active_manifest
    final_manifest = json.loads(active_manifest.read_text(encoding="utf-8"))
    assert set(final_manifest["artifacts"]) == FINAL_ARTIFACT_KEYS
    assert final_manifest["runtime_evidence"]["status"] == "verified"
    final_id = final_manifest["bundle_id"]
    assert final_id != candidate["bundle_id"]
    assert final_manifest["previous_bundle_id"] is None
    assert not candidate["manifest"].exists()
    assert not (evidence_root / "runs" / candidate["bundle_id"]).exists()

    for metadata in final_manifest["artifacts"].values():
        assert metadata["path"].startswith(f"runs/{final_id}/")
        artifact_path = evidence_root / metadata["path"]
        assert artifact_path.is_file()
        assert metadata["sha256"] == _sha256(artifact_path)
        assert metadata["size_bytes"] == artifact_path.stat().st_size

    for runtime_name in ("spark", "airflow", "datahub"):
        runtime = final_manifest["runtime_evidence"][runtime_name]
        assert runtime["artifact_key"] in FINAL_ARTIFACT_KEYS
        assert runtime["path"] == final_manifest["artifacts"][runtime["artifact_key"]]["path"]

    final_report = evidence_root / final_manifest["artifacts"]["quality_report"]["path"]
    report = final_report.read_text(encoding="utf-8")
    assert "status=success" in report
    assert "Pending" not in report


def test_finalize_keeps_active_and_previous_verified_bundles(tmp_path: Path) -> None:
    evidence_root = tmp_path / "evidence"
    active_manifest = evidence_root / "section03_manifest.json"

    first = _write_candidate(evidence_root, report_suffix="first")
    first_roots = _runtime_roots(tmp_path / "first", first["manifest_data"])
    finalizer.finalize_section03_evidence(
        candidate_manifest=first["manifest"],
        active_manifest=active_manifest,
        spark_root=first_roots[0],
        airflow_root=first_roots[1],
        datahub_root=first_roots[2],
        clean=False,
    )
    first_manifest = json.loads(active_manifest.read_text(encoding="utf-8"))
    first_id = first_manifest["bundle_id"]

    second = _write_candidate(evidence_root, report_suffix="second")
    second_roots = _runtime_roots(tmp_path / "second", second["manifest_data"])
    finalizer.finalize_section03_evidence(
        candidate_manifest=second["manifest"],
        active_manifest=active_manifest,
        spark_root=second_roots[0],
        airflow_root=second_roots[1],
        datahub_root=second_roots[2],
        clean=True,
    )
    second_manifest = json.loads(active_manifest.read_text(encoding="utf-8"))
    assert second_manifest["previous_bundle_id"] == first_id
    assert (evidence_root / "runs" / first_id).is_dir()
    assert (evidence_root / "runs" / second_manifest["bundle_id"]).is_dir()


@pytest.mark.parametrize("runtime_kind", ["spark", "airflow", "datahub"])
def test_finalize_rejects_corrupt_recursive_runtime_and_preserves_active(
    tmp_path: Path,
    runtime_kind: str,
) -> None:
    evidence_root = tmp_path / "evidence"
    active_manifest = evidence_root / "section03_manifest.json"
    first = _write_candidate(evidence_root, report_suffix="active")
    first_roots = _runtime_roots(tmp_path / "active", first["manifest_data"])
    finalizer.finalize_section03_evidence(
        candidate_manifest=first["manifest"],
        active_manifest=active_manifest,
        spark_root=first_roots[0],
        airflow_root=first_roots[1],
        datahub_root=first_roots[2],
        clean=True,
    )
    active_bytes = active_manifest.read_bytes()

    second = _write_candidate(evidence_root, report_suffix="corrupt")
    second_roots = _runtime_roots(tmp_path / "corrupt", second["manifest_data"])
    target = second_roots["spark airflow datahub".split().index(runtime_kind)] / "nested" / f"{runtime_kind}_metrics.json"
    target.write_text("tampered\n", encoding="utf-8")

    with pytest.raises(ValueError):
        finalizer.finalize_section03_evidence(
            candidate_manifest=second["manifest"],
            active_manifest=active_manifest,
            spark_root=second_roots[0],
            airflow_root=second_roots[1],
            datahub_root=second_roots[2],
            clean=True,
        )

    assert active_manifest.read_bytes() == active_bytes


def test_finalize_rejects_path_traversal_and_missing_runtime_artifact(tmp_path: Path) -> None:
    evidence_root = tmp_path / "evidence"
    candidate = _write_candidate(evidence_root)
    active_manifest = evidence_root / "section03_manifest.json"

    def mutate(run_manifest: dict[str, Any], nested: Path) -> None:
        run_manifest["artifacts"][0]["path"] = "../outside.json"

    roots = _runtime_roots(tmp_path, candidate["manifest_data"], mutate=mutate)
    with pytest.raises(ValueError):
        finalizer.finalize_section03_evidence(
            candidate_manifest=candidate["manifest"],
            active_manifest=active_manifest,
            spark_root=roots[0],
            airflow_root=roots[1],
            datahub_root=roots[2],
        )


@pytest.mark.parametrize("runtime_kind", ["spark", "airflow", "datahub"])
def test_finalize_rejects_missing_recursive_artifact_for_each_runtime(
    tmp_path: Path,
    runtime_kind: str,
) -> None:
    evidence_root = tmp_path / "evidence"
    candidate = _write_candidate(evidence_root)
    roots = _runtime_roots(tmp_path, candidate["manifest_data"])
    index = ["spark", "airflow", "datahub"].index(runtime_kind)
    (roots[index] / "nested" / f"{runtime_kind}_metrics.json").unlink()

    with pytest.raises(ValueError):
        finalizer.finalize_section03_evidence(
            candidate_manifest=candidate["manifest"],
            active_manifest=evidence_root / "section03_manifest.json",
            spark_root=roots[0],
            airflow_root=roots[1],
            datahub_root=roots[2],
        )


def test_finalize_rejects_symlinked_runtime_file_without_os_symlink_dependency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence_root = tmp_path / "evidence"
    candidate = _write_candidate(evidence_root)
    roots = _runtime_roots(tmp_path, candidate["manifest_data"])
    symlinked_path = roots[0] / "nested" / "spark_metrics.json"
    original_is_symlink = Path.is_symlink

    def report_symlink(path: Path) -> bool:
        return path == symlinked_path or original_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", report_symlink)
    with pytest.raises(ValueError, match="symlink"):
        finalizer.finalize_section03_evidence(
            candidate_manifest=candidate["manifest"],
            active_manifest=evidence_root / "section03_manifest.json",
            spark_root=roots[0],
            airflow_root=roots[1],
            datahub_root=roots[2],
        )


@pytest.mark.parametrize(
    "field, value",
    [
        ("status", "failed"),
        ("config_sha256", "wrong-config"),
        ("scale", "smoke"),
        ("feature_cutoff_ts", "2026-04-23T23:59:00Z"),
        ("candidate_bundle_id", "f" * 64),
    ],
)
def test_finalize_rejects_runtime_status_or_identity_mismatch(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    evidence_root = tmp_path / "evidence"
    candidate = _write_candidate(evidence_root)

    def mutate(run_manifest: dict[str, Any], nested: Path) -> None:
        run_manifest[field] = value

    roots = _runtime_roots(tmp_path, candidate["manifest_data"], mutate=mutate)
    with pytest.raises(ValueError):
        finalizer.finalize_section03_evidence(
            candidate_manifest=candidate["manifest"],
            active_manifest=evidence_root / "section03_manifest.json",
            spark_root=roots[0],
            airflow_root=roots[1],
            datahub_root=roots[2],
        )


def test_finalize_rejects_unlisted_runtime_file(tmp_path: Path) -> None:
    evidence_root = tmp_path / "evidence"
    candidate = _write_candidate(evidence_root)
    roots = _runtime_roots(tmp_path, candidate["manifest_data"])
    (roots[0] / "unlisted.json").write_text("unexpected\n", encoding="utf-8")

    with pytest.raises(ValueError):
        finalizer.finalize_section03_evidence(
            candidate_manifest=candidate["manifest"],
            active_manifest=evidence_root / "section03_manifest.json",
            spark_root=roots[0],
            airflow_root=roots[1],
            datahub_root=roots[2],
        )


def test_finalize_same_id_identical_reuse_and_same_id_content_mismatch(tmp_path: Path) -> None:
    evidence_root = tmp_path / "evidence"
    active_manifest = evidence_root / "section03_manifest.json"
    first = _write_candidate(evidence_root, report_suffix="same")
    first_roots = _runtime_roots(tmp_path / "first", first["manifest_data"])
    finalizer.finalize_section03_evidence(
        candidate_manifest=first["manifest"],
        active_manifest=active_manifest,
        spark_root=first_roots[0],
        airflow_root=first_roots[1],
        datahub_root=first_roots[2],
        clean=False,
    )
    active_bytes = active_manifest.read_bytes()

    identical = _write_candidate(evidence_root, report_suffix="same")
    identical_roots = _runtime_roots(tmp_path / "identical", identical["manifest_data"])
    finalizer.finalize_section03_evidence(
        candidate_manifest=identical["manifest"],
        active_manifest=active_manifest,
        spark_root=identical_roots[0],
        airflow_root=identical_roots[1],
        datahub_root=identical_roots[2],
        clean=False,
    )
    assert active_manifest.read_bytes() == active_bytes

    mismatched = _write_candidate(evidence_root, report_suffix="same")
    (evidence_root / "runs" / mismatched["bundle_id"] / "ml_customer_label.csv").write_text(
        "id,label\nc001,0\nc002,0\n",
        encoding="utf-8",
    )
    mismatched_roots = _runtime_roots(tmp_path / "mismatched", mismatched["manifest_data"])
    with pytest.raises(ValueError):
        finalizer.finalize_section03_evidence(
            candidate_manifest=mismatched["manifest"],
            active_manifest=active_manifest,
            spark_root=mismatched_roots[0],
            airflow_root=mismatched_roots[1],
            datahub_root=mismatched_roots[2],
        )


def test_finalize_candidate_pointer_race_aborts_before_promotion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    evidence_root = tmp_path / "evidence"
    candidate = _write_candidate(evidence_root)
    roots = _runtime_roots(tmp_path, candidate["manifest_data"])
    active_manifest = evidence_root / "section03_manifest.json"

    def reject_race(path: Path, expected: tuple[str, str]) -> None:
        raise ValueError("candidate pointer changed before authoritative promotion")

    monkeypatch.setattr(finalizer, "_recheck_candidate_pointer", reject_race)
    with pytest.raises(ValueError, match="candidate pointer changed"):
        finalizer.finalize_section03_evidence(
            candidate_manifest=candidate["manifest"],
            active_manifest=active_manifest,
            spark_root=roots[0],
            airflow_root=roots[1],
            datahub_root=roots[2],
        )
    assert not active_manifest.exists()
    assert candidate["manifest"].exists()

    candidate = _write_candidate(evidence_root, report_suffix="missing")
    roots = _runtime_roots(tmp_path / "missing", candidate["manifest_data"])
    (roots[1] / "nested" / "airflow_metrics.json").unlink()
    with pytest.raises(ValueError):
        finalizer.finalize_section03_evidence(
            candidate_manifest=candidate["manifest"],
            active_manifest=active_manifest,
            spark_root=roots[0],
            airflow_root=roots[1],
            datahub_root=roots[2],
        )


def test_finalize_pre_replace_failure_preserves_prior_active(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    evidence_root = tmp_path / "evidence"
    active_manifest = evidence_root / "section03_manifest.json"
    first = _write_candidate(evidence_root, report_suffix="before")
    first_roots = _runtime_roots(tmp_path / "before", first["manifest_data"])
    finalizer.finalize_section03_evidence(
        candidate_manifest=first["manifest"],
        active_manifest=active_manifest,
        spark_root=first_roots[0],
        airflow_root=first_roots[1],
        datahub_root=first_roots[2],
        clean=True,
    )
    active_bytes = active_manifest.read_bytes()

    second = _write_candidate(evidence_root, report_suffix="replace-failure")
    second_roots = _runtime_roots(tmp_path / "replace-failure", second["manifest_data"])
    original_replace = finalizer.os.replace

    def fail_active_replace(source: Any, destination: Any) -> None:
        if Path(destination) == active_manifest:
            raise OSError("injected pre-replace failure")
        original_replace(source, destination)

    monkeypatch.setattr(finalizer.os, "replace", fail_active_replace)
    with pytest.raises(OSError, match="pre-replace"):
        finalizer.finalize_section03_evidence(
            candidate_manifest=second["manifest"],
            active_manifest=active_manifest,
            spark_root=second_roots[0],
            airflow_root=second_roots[1],
            datahub_root=second_roots[2],
        )
    assert active_manifest.read_bytes() == active_bytes


def test_finalize_post_promotion_cleanup_warning_is_nonfatal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    evidence_root = tmp_path / "evidence"
    candidate = _write_candidate(evidence_root)
    roots = _runtime_roots(tmp_path, candidate["manifest_data"])
    active_manifest = evidence_root / "section03_manifest.json"
    original_unlink = Path.unlink

    def fail_candidate_unlink(path: Path, *args: Any, **kwargs: Any) -> None:
        if path == candidate["manifest"]:
            raise OSError("injected cleanup failure")
        original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_candidate_unlink)
    with pytest.warns(UserWarning, match="cleanup"):
        result = finalizer.finalize_section03_evidence(
            candidate_manifest=candidate["manifest"],
            active_manifest=active_manifest,
            spark_root=roots[0],
            airflow_root=roots[1],
            datahub_root=roots[2],
        )

    assert result == active_manifest
    assert active_manifest.is_file()
    assert candidate["manifest"].is_file()


def test_finalize_post_promotion_identity_change_preserves_pointer_and_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence_root = tmp_path / "evidence"
    candidate = _write_candidate(evidence_root)
    roots = _runtime_roots(tmp_path, candidate["manifest_data"])
    active_manifest = evidence_root / "section03_manifest.json"
    original_pointer_state = finalizer._pointer_state
    calls = 0

    def change_after_promotion(path: Path) -> tuple[str, str]:
        nonlocal calls
        state = original_pointer_state(path)
        if path == candidate["manifest"]:
            calls += 1
            if calls >= 4:
                return ("0" * 64, "f" * 64)
        return state

    monkeypatch.setattr(finalizer, "_pointer_state", change_after_promotion)
    with pytest.warns(UserWarning, match="identity changed"):
        result = finalizer.finalize_section03_evidence(
            candidate_manifest=candidate["manifest"],
            active_manifest=active_manifest,
            spark_root=roots[0],
            airflow_root=roots[1],
            datahub_root=roots[2],
        )

    assert result == active_manifest
    assert active_manifest.is_file()
    assert candidate["manifest"].is_file()
    final_manifest = json.loads(active_manifest.read_text(encoding="utf-8"))
    assert (evidence_root / final_manifest["artifacts"]["labels"]["path"]).is_file()
