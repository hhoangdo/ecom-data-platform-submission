from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

import numpy as np
import pandas as pd
from PIL import Image


TOP_LEVEL_KEYS = {
    "schema_version",
    "section",
    "generated_at",
    "source_config_path",
    "source_config_sha256",
    "bundle_id",
    "previous_bundle_id",
    "config_snapshot",
    "scale",
    "random_seed",
    "history_days",
    "windows",
    "drift_config",
    "configured_entity_counts",
    "observed_entity_counts",
    "rate_summary",
    "consumer_contract",
    "rubric_cells",
    "checks",
    "runtime_evidence",
    "artifacts",
}
ARTIFACT_KEYS = {
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
}
TABULAR_KEYS = {
    "labels",
    "feature_health_daily",
    "drift_alerts",
    "training_join",
    "labels_sample",
    "feature_health_sample",
    "drift_alerts_sample",
    "training_sample",
}
CHECK_KEYS = {
    "configured_counts_preserved",
    "streaming_distribution_inherited",
    "labels_exact_schema",
    "labels_unique",
    "labels_binary",
    "training_join_one_to_one",
    "point_in_time_safe",
    "psi_finite",
    "alert_threshold_respected",
}
RUBRIC_KEYS = {"E32", "E33", "E34"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_exact(actual: set[str], expected: set[str], name: str) -> None:
    if actual != expected:
        raise ValueError(f"{name} keys must be exact")


def _artifact_path(root: Path, value: str, *, bundle_id: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("artifact path must be a nonempty string")
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if (
        posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or "\\" in value
        or any(part in {"", ".", ".."} for part in posix.parts)
    ):
        raise ValueError("artifact path is unsafe")
    expected_prefix = ("runs", bundle_id)
    if posix.parts[:2] != expected_prefix:
        raise ValueError("artifact path does not match bundle")
    candidate = root.joinpath(*posix.parts)
    if candidate.is_symlink() or any(parent.is_symlink() for parent in candidate.parents if parent != root.parent):
        raise ValueError("artifact path must not traverse a symlink")
    resolved_root = root.resolve()
    resolved = candidate.resolve(strict=True)
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise ValueError("artifact path escapes the evidence root")
    return resolved


def _validate_strict_manifest(path: Path, manifest: dict[str, Any]) -> None:
    finalizer_path = Path(__file__).with_name("finalize_section03_evidence.py")
    spec = importlib.util.spec_from_file_location("section03_finalizer_for_verification", finalizer_path)
    if spec is None or spec.loader is None:
        raise ValueError("strict finalizer validator is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    validator = getattr(module, "_validate_final_manifest", None)
    if validator is None:
        raise ValueError("strict finalizer validator is unavailable")
    validator(path, manifest)


def verify_manifest(
    manifest_path: str | Path,
    *,
    allow_runtime_pending: bool = False,
    strict: bool = False,
) -> dict[str, Any]:
    path = Path(manifest_path)
    if strict and allow_runtime_pending:
        raise ValueError("strict verification cannot allow runtime pending")
    if allow_runtime_pending and path.name != "section03_candidate_manifest.json":
        raise ValueError("runtime pending is allowed only for the candidate manifest")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    if strict:
        _validate_strict_manifest(path, manifest)
        return manifest
    _require_exact(set(manifest), TOP_LEVEL_KEYS, "top-level")
    if manifest["schema_version"] != 1 or manifest["section"] != "03_data_generator_improvement":
        raise ValueError("manifest identity is invalid")
    bundle_id = manifest["bundle_id"]
    if not isinstance(bundle_id, str) or len(bundle_id) != 64 or any(
        character not in "0123456789abcdef" for character in bundle_id
    ):
        raise ValueError("bundle_id is invalid")
    checks = manifest["checks"]
    if not isinstance(checks, dict) or set(checks) != CHECK_KEYS:
        raise ValueError("check keys must be exact")
    if not all(value is True for value in checks.values()):
        raise ValueError("check values must all be true")
    rubric = manifest["rubric_cells"]
    if not isinstance(rubric, dict) or set(rubric) != RUBRIC_KEYS:
        raise ValueError("rubric keys must be exactly E32-E34")
    expected_points = {"E32": 1, "E33": 1, "E34": 2}
    for cell, points in expected_points.items():
        entry = rubric[cell]
        if set(entry) != {"points", "status", "required_checks", "artifact_keys"}:
            raise ValueError("rubric entry keys are invalid")
        if entry["points"] != points:
            raise ValueError("rubric points are invalid")
        if any(check not in CHECK_KEYS for check in entry["required_checks"]):
            raise ValueError("rubric required check is invalid")
        if any(key not in ARTIFACT_KEYS for key in entry["artifact_keys"]):
            raise ValueError("rubric artifact key is invalid")
    runtime = manifest["runtime_evidence"]
    if allow_runtime_pending:
        if runtime != {"status": "pending", "spark": None, "airflow": None, "datahub": None}:
            raise ValueError("runtime pending contract is invalid")
        if {entry["status"] for entry in rubric.values()} != {"Candidate"}:
            raise ValueError("rubric candidate status is invalid")
    elif runtime.get("status") != "verified":
        raise ValueError("runtime evidence is not verified")
    elif sum(
        entry["points"] for entry in rubric.values() if entry["status"] == "Satisfied"
    ) != 4:
        raise ValueError("rubric satisfied subtotal must equal four")

    artifacts = manifest["artifacts"]
    if not isinstance(artifacts, dict) or set(artifacts) != ARTIFACT_KEYS:
        raise ValueError("artifact keys must be exact")
    root = path.parent
    artifact_hashes: dict[str, str] = {}
    for key in sorted(ARTIFACT_KEYS):
        metadata = artifacts[key]
        required = {"path", "size_bytes", "sha256"}
        tabular = key in TABULAR_KEYS
        if tabular:
            required |= {"row_count", "columns"}
        if set(metadata) != required:
            raise ValueError(f"artifact metadata keys are invalid for {key}")
        artifact_path = _artifact_path(root, metadata["path"], bundle_id=bundle_id)
        if artifact_path.stat().st_size != metadata["size_bytes"]:
            raise ValueError(f"artifact size mismatch for {key}")
        digest = _sha256(artifact_path)
        if digest != metadata["sha256"]:
            raise ValueError(f"artifact hash mismatch for {key}")
        artifact_hashes[key] = digest
        if tabular:
            frame = pd.read_csv(artifact_path)
            if len(frame) != metadata["row_count"]:
                raise ValueError(f"artifact row count mismatch for {key}")
            if list(frame.columns) != metadata["columns"]:
                raise ValueError(f"artifact columns mismatch for {key}")
    calculated_bundle = hashlib.sha256(
        json.dumps(artifact_hashes, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if calculated_bundle != bundle_id:
        raise ValueError("bundle hash does not match artifact inventory")

    contract = manifest["consumer_contract"]
    if set(contract) != {"schema_version", "label", "training_join", "feature_health"}:
        raise ValueError("consumer contract keys are invalid")
    if contract["schema_version"] != 1:
        raise ValueError("consumer schema version is invalid")
    bindings = {
        "label": "labels",
        "training_join": "training_join",
        "feature_health": "feature_health_daily",
    }
    for contract_key, artifact_key in bindings.items():
        entry = contract[contract_key]
        if entry.get("artifact_key") != artifact_key:
            raise ValueError("consumer artifact binding is invalid")
        if entry.get("path") != artifacts[artifact_key]["path"]:
            raise ValueError("consumer path binding is invalid")
        if entry.get("sha256") != artifacts[artifact_key]["sha256"]:
            raise ValueError("consumer hash binding is invalid")
    if manifest["config_snapshot"] != artifacts["config_snapshot"]["path"]:
        raise ValueError("config snapshot binding is invalid")
    if manifest["configured_entity_counts"] != manifest["observed_entity_counts"]:
        raise ValueError("configured and observed counts differ")
    labels = pd.read_csv(_artifact_path(root, artifacts["labels"]["path"], bundle_id=bundle_id))
    training = pd.read_csv(
        _artifact_path(root, artifacts["training_join"]["path"], bundle_id=bundle_id)
    )
    health = pd.read_csv(
        _artifact_path(root, artifacts["feature_health_daily"]["path"], bundle_id=bundle_id)
    )
    alerts = pd.read_csv(
        _artifact_path(root, artifacts["drift_alerts"]["path"], bundle_id=bundle_id)
    )
    if list(labels.columns) != ["id", "label"] or labels["id"].isna().any() or not labels["id"].is_unique:
        raise ValueError("label contract is invalid")
    if not labels["label"].isin([0, 1]).all():
        raise ValueError("label values are invalid")
    if not labels.equals(training[["id", "label"]]):
        raise ValueError("training labels do not match exact label artifact")
    psi = pd.to_numeric(health["psi_vs_baseline"], errors="coerce")
    if not np.isfinite(psi).all() or not psi.ge(0).all():
        raise ValueError("health PSI contains nonfinite values")
    warning_values = health["warning_flag"].astype(str).str.lower()
    alert_values = health["alert_flag"].astype(str).str.lower()
    if not warning_values.isin({"true", "false"}).all() or not alert_values.isin(
        {"true", "false"}
    ).all():
        raise ValueError("health threshold status is invalid")
    warning_flags = warning_values.eq("true")
    alert_flags = alert_values.eq("true")
    expected_status = pd.Series(
        np.where(psi.ge(0.15), "alert", np.where(psi.ge(0.10), "warning", "stable")),
        index=health.index,
    )
    if (
        not health["drift_status"].astype(str).eq(expected_status).all()
        or not warning_flags.eq(psi.ge(0.10)).all()
        or not alert_flags.eq(psi.ge(0.15)).all()
    ):
        raise ValueError("health threshold status is invalid")
    if manifest["scale"] == "medium" and not warning_flags.any():
        raise ValueError(
            "canonical medium evidence requires at least one warning-or-alert day"
        )
    alert_psi = pd.to_numeric(alerts["psi_value"], errors="coerce")
    if (
        not np.isfinite(alert_psi).all()
        or not alert_psi.ge(0.15).all()
        or not pd.to_numeric(alerts["threshold"], errors="coerce").eq(0.15).all()
    ):
        raise ValueError("alert threshold is invalid")
    expected_alert_rows = {
        (str(row.monitoring_date), str(row.feature_name), float(row.psi_vs_baseline))
        for row in health.loc[alert_flags].itertuples(index=False)
    }
    actual_alert_rows = {
        (str(row.alert_date), str(row.feature_name), float(row.psi_value))
        for row in alerts.itertuples(index=False)
    }
    if expected_alert_rows != actual_alert_rows or len(actual_alert_rows) != len(alerts):
        raise ValueError("alert rows do not match health status")
    image_path = _artifact_path(root, artifacts["evidence_image"]["path"], bundle_id=bundle_id)
    with Image.open(image_path) as image:
        image.verify()
    with Image.open(image_path) as image:
        if image.size != (1600, 900):
            raise ValueError("evidence image dimensions are invalid")
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify a Section 03 evidence manifest.")
    parser.add_argument("--manifest", required=True)
    runtime_mode = parser.add_mutually_exclusive_group()
    runtime_mode.add_argument("--allow-runtime-pending", action="store_true")
    runtime_mode.add_argument("--strict", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = verify_manifest(
        args.manifest,
        allow_runtime_pending=args.allow_runtime_pending,
        strict=args.strict,
    )
    suffix = " (runtime pending)" if manifest["runtime_evidence"]["status"] == "pending" else ""
    print(f"section03 manifest: PASS{suffix}")


if __name__ == "__main__":
    main()
