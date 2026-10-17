from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
from types import ModuleType


SECTION03_SOURCE_SHA256 = (
    "3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6"
)
SECTION03_MANIFEST_SHA256 = (
    "af7189d00a187e539bb777d89111d2860a97822f34c2c911adc3eadf6166f8ad"
)
SECTION03_BUNDLE_ID = (
    "f6d07b09a12107b19a4bfe45a7bda6f87ab9356021a90e2ec6f02f63b5602640"
)
STUDY_CARVED_RUNTIME_KEYS = frozenset({"spark_runtime_manifest", "airflow_runtime_manifest"})


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_verifier(repo_root: Path) -> ModuleType:
    verifier_path = repo_root / "scripts" / "generate" / "verify_section03_manifest.py"
    spec = importlib.util.spec_from_file_location("section03_contract_verifier", verifier_path)
    assert spec is not None and spec.loader is not None
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    return verifier


def _verify_study_manifest(verifier: ModuleType, manifest_path: Path) -> dict:
    """Strict-verify with an explicit study-only carve-out for two stale runtime manifests.

    Default (EDAI2_STUDY_MODE unset) is fail-closed: any strict failure propagates.
    With EDAI2_STUDY_MODE=1, only failures naming a key in STUDY_CARVED_RUNTIME_KEYS
    are exempted, and only after every other artifact is byte-verified strictly.
    """

    try:
        return verifier.verify_manifest(manifest_path, strict=True)
    except ValueError as error:
        if os.environ.get("EDAI2_STUDY_MODE") != "1":
            raise
        key = str(error).rsplit(" for ", 1)[-1].strip()
        if key not in STUDY_CARVED_RUNTIME_KEYS:
            raise
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        root = manifest_path.parent
        for name, metadata in manifest["artifacts"].items():
            if name in STUDY_CARVED_RUNTIME_KEYS:
                continue
            candidate = root / metadata["path"]
            assert candidate.is_file(), f"study carve-out blocked: {name} missing"
            assert candidate.stat().st_size == metadata["size_bytes"], (
                f"study carve-out blocked: {name} size mismatch"
            )
            assert _sha256(candidate) == metadata["sha256"], (
                f"study carve-out blocked: {name} hash mismatch"
            )
        print(
            "study-debt: EDAI2_STUDY_MODE=1 carves out "
            f"{sorted(STUDY_CARVED_RUNTIME_KEYS)} (stale since 8678c18); "
            "all other artifacts byte-verified"
        )
        return manifest


def test_canonical_section03_consumer_contract_is_strict_and_read_only() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    source_path = repo_root / "tmp" / "edai2-plan" / "03_data_generator_improvement.md"
    manifest_path = (
        repo_root / "evidence" / "03_data_generator_improvement" / "section03_manifest.json"
    )
    manifest_before = manifest_path.read_bytes()

    assert _sha256(source_path) == SECTION03_SOURCE_SHA256
    assert _sha256(manifest_path) == SECTION03_MANIFEST_SHA256

    verifier = _load_verifier(repo_root)
    manifest = verifier.verify_manifest(manifest_path, strict=True)

    assert manifest["section"] == "03_data_generator_improvement"
    assert manifest["bundle_id"] == SECTION03_BUNDLE_ID
    assert manifest["runtime_evidence"]["status"] == "verified"
    assert manifest["source_config_path"] == "configs/generator/base.yaml"
    assert manifest["source_config_sha256"] == (
        "5c5029fea77d93c3941d87d9a60f85cfe374f36899c3d3c1b028f3f5f3c3cd97"
    )
    assert manifest["configured_entity_counts"] == manifest["observed_entity_counts"]
    assert all(manifest["checks"].values())

    rubric = manifest["rubric_cells"]
    assert {cell: (entry["points"], entry["status"]) for cell, entry in rubric.items()} == {
        "E32": (1, "Satisfied"),
        "E33": (1, "Satisfied"),
        "E34": (2, "Satisfied"),
    }

    consumer = manifest["consumer_contract"]
    assert consumer["schema_version"] == 1
    assert consumer["label"] == {
        "artifact_key": "labels",
        "path": (
            "runs/f6d07b09a12107b19a4bfe45a7bda6f87ab9356021a90e2ec6f02f63b5602640/"
            "ml_customer_label.csv"
        ),
        "sha256": "526304d4e2d97a70ed6671993b2f5bc07e934dfbd72488cb98c32dcb924f0278",
        "columns": ["id", "label"],
        "entity_key": "id",
    }
    assert consumer["training_join"] == {
        "artifact_key": "training_join",
        "path": (
            "runs/f6d07b09a12107b19a4bfe45a7bda6f87ab9356021a90e2ec6f02f63b5602640/"
            "ml_customer_purchase_training.csv"
        ),
        "sha256": "d1ffb48689373260e2e47f2ea9e14c45e6bc9e8543561a57924b1e21fa4afbdd",
        "entity_key": "id",
        "event_timestamp_column": "event_timestamp",
        "feature_cutoff_ts": "2026-04-24T23:59:00Z",
        "point_in_time_rule": "event_timestamp <= as_of and created <= event_timestamp",
    }
    assert consumer["feature_health"] == {
        "artifact_key": "feature_health_daily",
        "path": (
            "runs/f6d07b09a12107b19a4bfe45a7bda6f87ab9356021a90e2ec6f02f63b5602640/"
            "agg_feature_health_daily.csv"
        ),
        "sha256": "0d9a304b49fdae14aca134a11b8e3420fd202bf093535f1d7904fae8d020963f",
        "feature_name": "f_customer_order_frequency_7d",
        "window_days": 7,
        "baseline_date": "2026-04-10",
        "monitoring_start": "2026-04-10",
        "monitoring_end": "2026-05-01",
        "cohort_size": 11966,
        "psi_column": "psi_vs_baseline",
        "status_column": "drift_status",
        "warning_threshold": 0.1,
        "alert_threshold": 0.15,
    }

    assert manifest["drift_config"]["scenario"] == "customer_order_frequency"
    assert manifest["drift_config"]["post_rate_multiplier"] == 1.5
    assert manifest["rate_summary"]["order_normalized_post_pre_ratio"] > 1.0
    assert manifest["rate_summary"]["stream_normalized_post_pre_ratio"] > 1.0
    assert manifest_path.read_bytes() == manifest_before


def test_study_mode_passes_through_strict_when_tree_matches_pins(monkeypatch, capsys) -> None:
    monkeypatch.setenv("EDAI2_STUDY_MODE", "1")
    repo_root = Path(__file__).resolve().parents[3]
    manifest_path = (
        repo_root / "evidence" / "03_data_generator_improvement" / "section03_manifest.json"
    )
    verifier = _load_verifier(repo_root)
    manifest = _verify_study_manifest(verifier, manifest_path)
    assert manifest["bundle_id"] == SECTION03_BUNDLE_ID
    assert "study-debt" not in capsys.readouterr().out
    rubric = manifest["rubric_cells"]
    assert {cell: (entry["points"], entry["status"]) for cell, entry in rubric.items()} == {
        "E32": (1, "Satisfied"),
        "E33": (1, "Satisfied"),
        "E34": (2, "Satisfied"),
    }
    assert manifest["consumer_contract"]["training_join"]["sha256"] == (
        "d1ffb48689373260e2e47f2ea9e14c45e6bc9e8543561a57924b1e21fa4afbdd"
    )


def _copy_runs_tree(repo_root: Path, dest: Path) -> Path:
    import shutil

    src = repo_root / "evidence" / "03_data_generator_improvement"
    shutil.copytree(src / "runs", dest / "runs")
    manifest = json.loads((src / "section03_manifest.json").read_text(encoding="utf-8"))
    manifest_copy = dest / "section03_manifest.json"
    manifest_copy.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_copy


def test_study_mode_carves_out_only_stale_runtime_manifests(monkeypatch, capsys, tmp_path) -> None:
    """Carve-out fires only for the two stale runtime keys, after byte-verifying the rest."""
    import pytest

    monkeypatch.setenv("EDAI2_STUDY_MODE", "1")
    repo_root = Path(__file__).resolve().parents[3]
    manifest_path = _copy_runs_tree(repo_root, tmp_path)
    verifier = _load_verifier(repo_root)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    stale = tmp_path / manifest["artifacts"]["spark_runtime_manifest"]["path"]
    stale.write_bytes(stale.read_bytes() + b"\n")
    carved = _verify_study_manifest(verifier, manifest_path)
    assert carved["bundle_id"] == SECTION03_BUNDLE_ID
    assert "study-debt" in capsys.readouterr().out

    manifest_path = _copy_runs_tree(repo_root, tmp_path / "second")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    victim = tmp_path / "second" / manifest["artifacts"]["training_join"]["path"]
    victim.write_bytes(victim.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="training_join"):
        _verify_study_manifest(verifier, manifest_path)
