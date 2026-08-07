"""Finalize a verified Section 03 candidate with strict runtime captures."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shutil
import sys
import time
from typing import Any, Iterator
import uuid
import warnings

import numpy as np
import pandas as pd
from PIL import Image


CANDIDATE_ARTIFACT_KEYS = {
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
RUNTIME_ARTIFACT_KEYS = {
    "spark_runtime_manifest",
    "airflow_runtime_manifest",
    "datahub_lineage",
}
FINAL_ARTIFACT_KEYS = CANDIDATE_ARTIFACT_KEYS | RUNTIME_ARTIFACT_KEYS
TABULAR_ARTIFACT_KEYS = {
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
EXPECTED_RUBRIC_POINTS = {"E32": 1, "E33": 1, "E34": 2}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bundle_id(artifact_hashes: dict[str, str]) -> str:
    return hashlib.sha256(
        json.dumps(artifact_hashes, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _load_candidate_verifier() -> Any:
    verifier_path = Path(__file__).with_name("verify_section03_manifest.py")
    spec = importlib.util.spec_from_file_location("section03_manifest_verifier_for_finalizer", verifier_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load manifest verifier: {verifier_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.verify_manifest


def _reject_unsafe_relative(value: str, *, description: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError(f"{description} must be a nonempty relative path")
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if (
        posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or "\\" in value
        or any(part in {"", ".", ".."} for part in posix.parts)
    ):
        raise ValueError(f"{description} is unsafe")
    return posix


def _contained_file(root: Path, value: str, *, description: str) -> Path:
    relative = _reject_unsafe_relative(value, description=description)
    candidate = root.joinpath(*relative.parts)
    if candidate.is_symlink() or any(
        parent.is_symlink() for parent in candidate.parents if parent != root.parent
    ):
        raise ValueError(f"{description} must not traverse a symlink")
    try:
        resolved_root = root.resolve(strict=True)
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ValueError(f"{description} is missing") from exc
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise ValueError(f"{description} escapes its root")
    if not resolved.is_file():
        raise ValueError(f"{description} must be a regular file")
    return resolved


def _candidate_file(evidence_root: Path, manifest: dict[str, Any], key: str) -> Path:
    bundle_id = manifest["bundle_id"]
    value = manifest["artifacts"][key]["path"]
    posix = _reject_unsafe_relative(value, description=f"candidate artifact {key}")
    if posix.parts[:2] != ("runs", bundle_id):
        raise ValueError(f"candidate artifact {key} does not match its bundle")
    return _contained_file(evidence_root, value, description=f"candidate artifact {key}")


def _metadata_for_file(key: str, path: Path, relative_path: str) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "path": relative_path,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }
    if key in TABULAR_ARTIFACT_KEYS:
        frame = pd.read_csv(path)
        metadata["row_count"] = len(frame)
        metadata["columns"] = list(frame.columns)
    return metadata


def _recursive_files(root: Path, *, description: str) -> list[Path]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError(f"{description} must be a real directory")
    files: list[Path] = []
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"{description} contains a symlink: {path.name}")
        if path.is_file():
            files.append(path)
        elif not path.is_dir():
            raise ValueError(f"{description} contains a non-file entry")
    return files


def _manifest_value(manifest: dict[str, Any], key: str) -> Any:
    if key in manifest:
        return manifest[key]
    conf = manifest.get("conf")
    if isinstance(conf, dict) and key in conf:
        return conf[key]
    return None


def _validate_runtime_capture(
    root: Path,
    *,
    kind: str,
    candidate: dict[str, Any],
    candidate_pointer_sha256: str,
) -> dict[str, Any]:
    root = root.resolve(strict=True)
    files = _recursive_files(root, description=f"{kind} capture root")
    top_path = root / "run_manifest.json"
    if top_path not in files:
        raise ValueError(f"{kind} capture is missing run_manifest.json")
    try:
        top = json.loads(top_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{kind} run manifest is not valid JSON") from exc
    if not isinstance(top, dict) or top.get("status") != "success":
        raise ValueError(f"{kind} runtime status is not success")
    if top.get("section") not in {None, "03_data_generator_improvement"}:
        raise ValueError(f"{kind} runtime section is invalid")

    conf = top.get("conf") if isinstance(top.get("conf"), dict) else {}
    identity_values = [
        top.get("bundle_id"),
        top.get("candidate_bundle_id"),
        conf.get("bundle_id"),
        conf.get("candidate_bundle_id"),
    ]
    if any(value is not None and value != candidate["bundle_id"] for value in identity_values):
        raise ValueError(f"{kind} runtime bundle identity does not match candidate")
    candidate_sha_values = [top.get("candidate_manifest_sha256"), conf.get("candidate_manifest_sha256")]
    if any(value is not None and value != candidate_pointer_sha256 for value in candidate_sha_values):
        raise ValueError(f"{kind} runtime candidate pointer hash is stale")
    config_values = [
        top.get("source_config_sha256"),
        top.get("config_sha256"),
        conf.get("source_config_sha256"),
        conf.get("config_sha256"),
    ]
    present_config_values = [value for value in config_values if value is not None]
    if not present_config_values or any(value != candidate["source_config_sha256"] for value in present_config_values):
        raise ValueError(f"{kind} runtime config hash does not match candidate")
    scale_values = [top.get("scale"), conf.get("scale")]
    present_scale_values = [value for value in scale_values if value is not None]
    if not present_scale_values or any(value != candidate["scale"] for value in present_scale_values):
        raise ValueError(f"{kind} runtime scale does not match candidate")
    cutoff_values = [
        top.get("feature_cutoff_ts"),
        top.get("cutoff_ts"),
        conf.get("feature_cutoff_ts"),
        conf.get("cutoff_ts"),
    ]
    present_cutoff_values = [value for value in cutoff_values if value is not None]
    if not present_cutoff_values or any(value != candidate["windows"]["feature_cutoff_ts"] for value in present_cutoff_values):
        raise ValueError(f"{kind} runtime feature cutoff does not match candidate")
    run_id = top.get("run_id") or top.get("dag_run_id") or conf.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError(f"{kind} runtime run identity is missing")
    if kind == "datahub" and top.get("lineage") != "lineage.json":
        raise ValueError("datahub runtime lineage binding is invalid")

    entries = top.get("artifacts")
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"{kind} runtime artifact inventory is missing")
    listed: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "size_bytes", "sha256"}:
            raise ValueError(f"{kind} runtime artifact metadata is invalid")
        relative = _reject_unsafe_relative(entry["path"], description=f"{kind} runtime artifact")
        value = relative.as_posix()
        if value in listed or value == "run_manifest.json":
            raise ValueError(f"{kind} runtime artifact inventory has a duplicate or reserved path")
        listed.add(value)
        path = _contained_file(root, value, description=f"{kind} runtime artifact {value}")
        if path.stat().st_size != entry["size_bytes"] or _sha256(path) != entry["sha256"]:
            raise ValueError(f"{kind} runtime artifact hash/size mismatch: {value}")

    actual = {path.relative_to(root).as_posix() for path in files if path != top_path}
    if actual != listed:
        raise ValueError(f"{kind} runtime recursive inventory is incomplete or unlisted")

    lineage_path = root / "lineage.json" if kind == "datahub" else None
    return {
        "kind": kind,
        "root": root,
        "top": top,
        "top_path": top_path,
        "top_sha256": _sha256(top_path),
        "run_id": run_id,
        "artifact_count": len(listed),
        "lineage_path": lineage_path,
    }


def _verify_candidate_tree(evidence_root: Path, candidate: dict[str, Any]) -> None:
    bundle_id = candidate["bundle_id"]
    bundle_root = evidence_root / "runs" / bundle_id
    files = _recursive_files(bundle_root, description="candidate bundle")
    expected = {
        _candidate_file(evidence_root, candidate, key).relative_to(bundle_root).as_posix()
        for key in CANDIDATE_ARTIFACT_KEYS
    }
    actual = {path.relative_to(bundle_root).as_posix() for path in files}
    if actual != expected:
        raise ValueError("candidate bundle contains missing or unlisted files")


def _validate_final_manifest(manifest_path: Path, manifest: dict[str, Any]) -> None:
    evidence_root = manifest_path.parent.resolve(strict=True)
    if manifest.get("section") != "03_data_generator_improvement":
        raise ValueError("final manifest section is invalid")
    bundle_id = manifest.get("bundle_id")
    if not isinstance(bundle_id, str) or len(bundle_id) != 64 or any(
        character not in "0123456789abcdef" for character in bundle_id
    ):
        raise ValueError("final bundle_id is invalid")
    checks = manifest.get("checks")
    if not isinstance(checks, dict) or set(checks) != CHECK_KEYS or not all(checks.values()):
        raise ValueError("final checks are not all true")
    if manifest.get("configured_entity_counts") != manifest.get("observed_entity_counts"):
        raise ValueError("final configured and observed counts differ")
    runtime = manifest.get("runtime_evidence")
    if not isinstance(runtime, dict) or set(runtime) != {"status", "spark", "airflow", "datahub"}:
        raise ValueError("final runtime evidence shape is invalid")
    if runtime["status"] != "verified":
        raise ValueError("final runtime evidence is not verified")
    rubric = manifest.get("rubric_cells")
    if not isinstance(rubric, dict) or set(rubric) != set(EXPECTED_RUBRIC_POINTS):
        raise ValueError("final rubric cells are invalid")
    if sum(entry.get("points", 0) for entry in rubric.values() if entry.get("status") == "Satisfied") != 4:
        raise ValueError("final rubric subtotal must equal four")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != FINAL_ARTIFACT_KEYS:
        raise ValueError("final artifact keys are invalid")
    hashes: dict[str, str] = {}
    for key, metadata in artifacts.items():
        if not isinstance(metadata, dict):
            raise ValueError(f"final metadata is invalid for {key}")
        required = {"path", "size_bytes", "sha256"}
        if key in TABULAR_ARTIFACT_KEYS:
            required |= {"row_count", "columns"}
        if set(metadata) != required:
            raise ValueError(f"final metadata keys are invalid for {key}")
        path = _contained_file(evidence_root, metadata["path"], description=f"final artifact {key}")
        relative = _reject_unsafe_relative(metadata["path"], description=f"final artifact {key}")
        if relative.parts[:2] != ("runs", bundle_id):
            raise ValueError(f"final artifact {key} is not in the final bundle")
        if path.stat().st_size != metadata["size_bytes"] or _sha256(path) != metadata["sha256"]:
            raise ValueError(f"final artifact hash/size mismatch for {key}")
        if bundle_id.encode("ascii") in path.read_bytes():
            raise ValueError(f"final artifact {key} embeds its own bundle identity")
        hashes[key] = metadata["sha256"]
        if key in TABULAR_ARTIFACT_KEYS:
            frame = pd.read_csv(path)
            if len(frame) != metadata["row_count"] or list(frame.columns) != metadata["columns"]:
                raise ValueError(f"final tabular metadata mismatch for {key}")
    if _bundle_id(hashes) != bundle_id:
        raise ValueError("final bundle hash does not match artifact inventory")

    contract = manifest.get("consumer_contract")
    if not isinstance(contract, dict) or set(contract) != {"schema_version", "label", "training_join", "feature_health"}:
        raise ValueError("final consumer contract is invalid")
    if contract["schema_version"] != 1:
        raise ValueError("final consumer schema version is invalid")
    for contract_key, artifact_key in {
        "label": "labels",
        "training_join": "training_join",
        "feature_health": "feature_health_daily",
    }.items():
        entry = contract[contract_key]
        if entry.get("artifact_key") != artifact_key:
            raise ValueError("final consumer artifact key binding is invalid")
        if entry.get("path") != artifacts[artifact_key]["path"] or entry.get("sha256") != artifacts[artifact_key]["sha256"]:
            raise ValueError("final consumer path/hash binding is invalid")
    if manifest.get("config_snapshot") != artifacts["config_snapshot"]["path"]:
        raise ValueError("final config snapshot binding is invalid")

    labels = pd.read_csv(_contained_file(evidence_root, artifacts["labels"]["path"], description="final labels"))
    training = pd.read_csv(_contained_file(evidence_root, artifacts["training_join"]["path"], description="final training join"))
    health = pd.read_csv(_contained_file(evidence_root, artifacts["feature_health_daily"]["path"], description="final feature health"))
    alerts = pd.read_csv(_contained_file(evidence_root, artifacts["drift_alerts"]["path"], description="final drift alerts"))
    if list(labels.columns) != ["id", "label"] or labels["id"].isna().any() or not labels["id"].is_unique:
        raise ValueError("final label contract is invalid")
    if not labels["label"].isin([0, 1]).all() or not labels.equals(training[["id", "label"]]):
        raise ValueError("final labels are not binary or do not match training")
    psi = pd.to_numeric(health["psi_vs_baseline"], errors="coerce")
    if not np.isfinite(psi).all() or not psi.ge(0).all():
        raise ValueError("final health PSI is invalid")
    warning = health["warning_flag"].astype(str).str.lower()
    alert = health["alert_flag"].astype(str).str.lower()
    warning_flags = warning.eq("true")
    alert_flags = alert.eq("true")
    expected_status = pd.Series(np.where(psi.ge(0.15), "alert", np.where(psi.ge(0.10), "warning", "stable")), index=health.index)
    if (
        not warning.isin({"true", "false"}).all()
        or not alert.isin({"true", "false"}).all()
        or not health["drift_status"].astype(str).eq(expected_status).all()
        or not warning_flags.eq(psi.ge(0.10)).all()
        or not alert_flags.eq(psi.ge(0.15)).all()
    ):
        raise ValueError("final health threshold status is invalid")
    alert_psi = pd.to_numeric(alerts["psi_value"], errors="coerce")
    thresholds = pd.to_numeric(alerts["threshold"], errors="coerce")
    if not np.isfinite(alert_psi).all() or not alert_psi.ge(0.15).all() or not thresholds.eq(0.15).all():
        raise ValueError("final alert threshold is invalid")
    expected_alerts = {
        (str(row.monitoring_date), str(row.feature_name), float(row.psi_vs_baseline))
        for row in health.loc[alert_flags].itertuples(index=False)
    }
    actual_alerts = {
        (str(row.alert_date), str(row.feature_name), float(row.psi_value))
        for row in alerts.itertuples(index=False)
    }
    if expected_alerts != actual_alerts:
        raise ValueError("final alert rows do not match health")
    with Image.open(_contained_file(evidence_root, artifacts["evidence_image"]["path"], description="final evidence image")) as image:
        if image.size != (1600, 900):
            raise ValueError("final evidence image dimensions are invalid")

    for runtime_name, artifact_key in {
        "spark": "spark_runtime_manifest",
        "airflow": "airflow_runtime_manifest",
        "datahub": "datahub_lineage",
    }.items():
        entry = runtime[runtime_name]
        if not isinstance(entry, dict) or set(entry) != {"artifact_key", "path", "size_bytes", "sha256"}:
            raise ValueError(f"final {runtime_name} binding is invalid")
        if entry["artifact_key"] != artifact_key or entry["path"] != artifacts[artifact_key]["path"]:
            raise ValueError(f"final {runtime_name} artifact binding is invalid")
        if entry["size_bytes"] != artifacts[artifact_key]["size_bytes"] or entry["sha256"] != artifacts[artifact_key]["sha256"]:
            raise ValueError(f"final {runtime_name} hash binding is invalid")


def _replace_report_sections(report: str, runtime_summaries: dict[str, dict[str, Any]]) -> str:
    replacements = {
        "Spark/dbt Parity Runtime": "spark",
        "Airflow DP3 Runtime": "airflow",
        "DataHub Lineage Runtime": "datahub",
    }
    for heading, kind in replacements.items():
        summary = runtime_summaries[kind]
        replacement = (
            f"## {heading}\n"
            f"status=success\n"
            f"run_id={summary['run_id']}\n"
            f"artifact_count={summary['artifact_count']}\n"
            f"manifest_sha256={summary['top_sha256']}\n"
        )
        pattern = re.compile(rf"^## {re.escape(heading)}\n.*?(?=^## |\Z)", re.MULTILINE | re.DOTALL)
        if pattern.search(report):
            report = pattern.sub(replacement, report, count=1)
        else:
            report = report.rstrip() + "\n\n" + replacement
    return report


def _pointer_state(path: Path) -> tuple[str, str]:
    if not path.is_file() or path.is_symlink():
        raise ValueError("candidate pointer is missing or unsafe")
    raw = path.read_bytes()
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("candidate pointer is not valid JSON") from exc
    if not isinstance(data, dict) or not isinstance(data.get("bundle_id"), str):
        raise ValueError("candidate pointer identity is missing")
    return hashlib.sha256(raw).hexdigest(), data["bundle_id"]


def _recheck_candidate_pointer(path: Path, expected: tuple[str, str]) -> None:
    if _pointer_state(path) != expected:
        raise ValueError("candidate pointer changed before authoritative promotion")


def _load_candidate(path: Path) -> tuple[dict[str, Any], tuple[str, str]]:
    before = _pointer_state(path)
    verify_manifest = _load_candidate_verifier()
    verify_manifest(path, allow_runtime_pending=True)
    data = json.loads(path.read_text(encoding="utf-8"))
    after = _pointer_state(path)
    if before != after:
        raise ValueError("candidate pointer changed during verification")
    _verify_candidate_tree(path.parent, data)
    return data, after


def _load_active(path: Path) -> tuple[dict[str, Any], bytes]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("active manifest is unsafe")
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("active manifest must be an object")
    _validate_final_manifest(path, data)
    return data, raw


@contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if os.name == "nt":
            import msvcrt

            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _copy_candidate_files(evidence_root: Path, staging: Path, candidate: dict[str, Any]) -> None:
    for key in CANDIDATE_ARTIFACT_KEYS:
        source = _candidate_file(evidence_root, candidate, key)
        relative = PurePosixPath(candidate["artifacts"][key]["path"]).parts[2:]
        destination = staging.joinpath(*relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _copy_runtime_files(staging: Path, runtime_roots: dict[str, dict[str, Any]]) -> None:
    for kind, summary in runtime_roots.items():
        destination = staging / "runtime" / kind
        shutil.copytree(summary["root"], destination)


def _runtime_metadata(staging: Path, final_id: str, kind: str, summary: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if kind == "datahub":
        relative = PurePosixPath("runtime", kind, "lineage.json")
        key = "datahub_lineage"
    else:
        relative = PurePosixPath("runtime", kind, "run_manifest.json")
        key = f"{kind}_runtime_manifest"
    path = staging.joinpath(*relative.parts)
    metadata = _metadata_for_file(key, path, f"runs/{final_id}/{relative.as_posix()}")
    return key, metadata


def _rewrite_manifest_for_final(
    candidate: dict[str, Any],
    *,
    staging: Path,
    final_id: str,
    previous_bundle_id: str | None,
    runtime_roots: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    artifacts: dict[str, dict[str, Any]] = {}
    for key in CANDIDATE_ARTIFACT_KEYS:
        relative = PurePosixPath(*PurePosixPath(candidate["artifacts"][key]["path"]).parts[2:])
        path = staging.joinpath(*relative.parts)
        artifacts[key] = _metadata_for_file(key, path, f"runs/{final_id}/{relative.as_posix()}")
    for kind, summary in runtime_roots.items():
        key, metadata = _runtime_metadata(staging, final_id, kind, summary)
        artifacts[key] = metadata

    final_manifest = deepcopy(candidate)
    final_manifest["bundle_id"] = final_id
    final_manifest["previous_bundle_id"] = previous_bundle_id
    final_manifest["config_snapshot"] = artifacts["config_snapshot"]["path"]
    final_manifest["artifacts"] = artifacts
    final_manifest["runtime_evidence"] = {
        "status": "verified",
        "spark": {"artifact_key": "spark_runtime_manifest", **{key: artifacts["spark_runtime_manifest"][key] for key in ("path", "size_bytes", "sha256")}},
        "airflow": {"artifact_key": "airflow_runtime_manifest", **{key: artifacts["airflow_runtime_manifest"][key] for key in ("path", "size_bytes", "sha256")}},
        "datahub": {"artifact_key": "datahub_lineage", **{key: artifacts["datahub_lineage"][key] for key in ("path", "size_bytes", "sha256")}},
    }
    for entry in final_manifest["rubric_cells"].values():
        entry["status"] = "Satisfied"
    for contract_key, artifact_key in {
        "label": "labels",
        "training_join": "training_join",
        "feature_health": "feature_health_daily",
    }.items():
        final_manifest["consumer_contract"][contract_key]["path"] = artifacts[artifact_key]["path"]
        final_manifest["consumer_contract"][contract_key]["sha256"] = artifacts[artifact_key]["sha256"]
    return final_manifest


def _remove_tree(path: Path) -> None:
    if path.exists() and not path.is_symlink():
        shutil.rmtree(path)


def _rename_staging_directory(source: Path, destination: Path) -> None:
    last_error: PermissionError | None = None
    for attempt in range(10):
        try:
            os.rename(source, destination)
            return
        except PermissionError as exc:
            last_error = exc
            if attempt == 9:
                break
            time.sleep(0.1)
    assert last_error is not None
    raise last_error


def _post_promotion_cleanup(
    *,
    candidate_manifest: Path,
    candidate_id: str,
    evidence_root: Path,
    active_id: str,
    previous_id: str | None,
    clean: bool,
    consumed_pointer: tuple[str, str],
) -> None:
    if not candidate_manifest.exists():
        return
    try:
        if _pointer_state(candidate_manifest) != consumed_pointer:
            warnings.warn(
                "Section 03 finalizer cleanup warning: candidate pointer identity changed; preserved pointer and bundle",
                UserWarning,
                stacklevel=2,
            )
            return
        candidate_manifest.unlink()
    except (OSError, ValueError) as exc:
        warnings.warn(
            f"Section 03 finalizer cleanup warning: could not remove candidate pointer ({exc})",
            UserWarning,
            stacklevel=2,
        )
        return

    if clean:
        candidate_bundle = evidence_root / "runs" / candidate_id
        if candidate_id not in {active_id, previous_id}:
            try:
                _remove_tree(candidate_bundle)
            except OSError as exc:
                warnings.warn(
                    f"Section 03 finalizer cleanup warning: could not remove consumed candidate bundle ({exc})",
                    UserWarning,
                    stacklevel=2,
                )
        runs_root = evidence_root / "runs"
        if runs_root.is_dir():
            for path in runs_root.iterdir():
                if not path.is_dir() or path.is_symlink() or not re.fullmatch(r"[0-9a-f]{64}", path.name):
                    continue
                if path.name not in {active_id, previous_id}:
                    try:
                        _remove_tree(path)
                    except OSError as exc:
                        warnings.warn(
                            f"Section 03 finalizer cleanup warning: could not remove stale bundle {path.name} ({exc})",
                            UserWarning,
                            stacklevel=2,
                        )


def finalize_section03_evidence(
    *,
    candidate_manifest: Path,
    active_manifest: Path,
    spark_root: Path,
    airflow_root: Path,
    datahub_root: Path,
    clean: bool = False,
) -> Path:
    """Strictly promote a candidate plus three runtime captures atomically."""

    candidate_manifest = Path(candidate_manifest)
    active_manifest = Path(active_manifest)
    spark_root = Path(spark_root)
    airflow_root = Path(airflow_root)
    datahub_root = Path(datahub_root)
    evidence_root = candidate_manifest.parent.resolve()
    if active_manifest.parent.resolve() != evidence_root:
        raise ValueError("candidate and active manifests must share an evidence root")
    if candidate_manifest.name != "section03_candidate_manifest.json":
        raise ValueError("candidate manifest basename is invalid")
    if active_manifest.name != "section03_manifest.json":
        raise ValueError("active manifest basename is invalid")
    if active_manifest.exists() and active_manifest.is_symlink():
        raise ValueError("active manifest must not be a symlink")

    lock_path = evidence_root / "section03.lock"
    with _exclusive_lock(lock_path):
        candidate, consumed_pointer = _load_candidate(candidate_manifest)
        previous_manifest: dict[str, Any] | None = None
        previous_raw: bytes | None = None
        if active_manifest.exists():
            previous_manifest, previous_raw = _load_active(active_manifest)
        previous_id = previous_manifest["bundle_id"] if previous_manifest else None
        runtime_roots = {
            "spark": _validate_runtime_capture(
                spark_root,
                kind="spark",
                candidate=candidate,
                candidate_pointer_sha256=consumed_pointer[0],
            ),
            "airflow": _validate_runtime_capture(
                airflow_root,
                kind="airflow",
                candidate=candidate,
                candidate_pointer_sha256=consumed_pointer[0],
            ),
            "datahub": _validate_runtime_capture(
                datahub_root,
                kind="datahub",
                candidate=candidate,
                candidate_pointer_sha256=consumed_pointer[0],
            ),
        }

        runs_root = evidence_root / "runs"
        runs_root.mkdir(parents=True, exist_ok=True)
        staging = runs_root / f".final-staging-{uuid.uuid4().hex}"
        final_root: Path | None = None
        temporary_manifest: Path | None = None
        promoted = False
        try:
            staging.mkdir()
            _copy_candidate_files(evidence_root, staging, candidate)
            _copy_runtime_files(staging, runtime_roots)
            report_relative = PurePosixPath(candidate["artifacts"]["quality_report"]["path"]).parts[2:]
            report_path = staging.joinpath(*report_relative)
            report_path.write_text(
                _replace_report_sections(report_path.read_text(encoding="utf-8"), runtime_roots),
                encoding="utf-8",
            )

            provisional_artifact_hashes: dict[str, str] = {}
            for key in CANDIDATE_ARTIFACT_KEYS:
                relative = PurePosixPath(candidate["artifacts"][key]["path"]).parts[2:]
                provisional_artifact_hashes[key] = _sha256(staging.joinpath(*relative))
            for kind, summary in runtime_roots.items():
                key = "datahub_lineage" if kind == "datahub" else f"{kind}_runtime_manifest"
                runtime_relative = Path("runtime") / kind / ("lineage.json" if kind == "datahub" else "run_manifest.json")
                provisional_artifact_hashes[key] = _sha256(staging / runtime_relative)
            final_id = _bundle_id(provisional_artifact_hashes)
            final_manifest = _rewrite_manifest_for_final(
                candidate,
                staging=staging,
                final_id=final_id,
                previous_bundle_id=previous_id,
                runtime_roots=runtime_roots,
            )

            if previous_manifest and previous_manifest["bundle_id"] == final_id:
                _validate_final_manifest(active_manifest, previous_manifest)
                active_hashes = {key: value["sha256"] for key, value in previous_manifest["artifacts"].items()}
                if active_hashes != {key: value["sha256"] for key, value in final_manifest["artifacts"].items()}:
                    raise ValueError("same-ID final bundle differs from active content")
                _remove_tree(staging)
                _post_promotion_cleanup(
                    candidate_manifest=candidate_manifest,
                    candidate_id=candidate["bundle_id"],
                    evidence_root=evidence_root,
                    active_id=previous_manifest["bundle_id"],
                    previous_id=previous_manifest.get("previous_bundle_id"),
                    clean=clean,
                    consumed_pointer=consumed_pointer,
                )
                return active_manifest

            final_root = runs_root / final_id
            if final_root.exists():
                raise ValueError("final bundle ID already exists with different content")
            # Directory promotion uses rename because Windows does not provide
            # replace semantics for non-empty directories; the authoritative
            # manifest below is still replaced atomically with os.replace.
            _rename_staging_directory(staging, final_root)
            staging = final_root
            temporary_manifest = evidence_root / f".section03_manifest-{uuid.uuid4().hex}.json"
            temporary_manifest.write_text(json.dumps(final_manifest, indent=2) + "\n", encoding="utf-8")
            _validate_final_manifest(temporary_manifest, final_manifest)
            _recheck_candidate_pointer(candidate_manifest, consumed_pointer)
            os.replace(temporary_manifest, active_manifest)
            promoted = True
        except Exception:
            if temporary_manifest is not None and temporary_manifest.exists():
                temporary_manifest.unlink()
            if not promoted:
                if final_root is not None and final_root.exists() and final_root != active_manifest:
                    _remove_tree(final_root)
                elif staging.exists() and staging != active_manifest:
                    _remove_tree(staging)
            raise

        if not promoted:
            raise RuntimeError("Section 03 finalizer did not promote a manifest")
        _post_promotion_cleanup(
            candidate_manifest=candidate_manifest,
            candidate_id=candidate["bundle_id"],
            evidence_root=evidence_root,
            active_id=final_manifest["bundle_id"],
            previous_id=final_manifest.get("previous_bundle_id"),
            clean=clean,
            consumed_pointer=consumed_pointer,
        )
        return active_manifest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Finalize a strict Section 03 evidence bundle.")
    parser.add_argument("--candidate-manifest", required=True)
    parser.add_argument("--active-manifest", required=True)
    parser.add_argument("--spark-root", required=True)
    parser.add_argument("--airflow-root", required=True)
    parser.add_argument("--datahub-root", required=True)
    parser.add_argument("--clean", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        active = finalize_section03_evidence(
            candidate_manifest=Path(args.candidate_manifest),
            active_manifest=Path(args.active_manifest),
            spark_root=Path(args.spark_root),
            airflow_root=Path(args.airflow_root),
            datahub_root=Path(args.datahub_root),
            clean=args.clean,
        )
    except Exception as exc:
        print(f"section03 finalizer: FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"section03 finalizer: PASS: {active}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
