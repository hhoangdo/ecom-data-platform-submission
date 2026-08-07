from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
from types import ModuleType

import pandas as pd
import pytest

from vina_bim_shop.generators.runner import run_generation


def _verifier(repo_root: Path) -> ModuleType:
    path = repo_root / "scripts" / "generate" / "verify_section03_manifest.py"
    spec = importlib.util.spec_from_file_location("section03_manifest_verifier", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rewrite_health_and_rebind_bundle(
    manifest_path: Path,
    mutate_health: object,
    *,
    scale: str | None = None,
) -> Path:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    old_bundle_id = manifest["bundle_id"]
    old_bundle_root = manifest_path.parent / "runs" / old_bundle_id
    health_path = old_bundle_root / "agg_feature_health_daily.csv"
    health = pd.read_csv(health_path)
    mutate_health(health)  # type: ignore[operator]
    health.to_csv(health_path, index=False, lineterminator="\n")
    health_metadata = manifest["artifacts"]["feature_health_daily"]
    health_metadata["size_bytes"] = health_path.stat().st_size
    health_metadata["sha256"] = _hash(health_path)
    artifact_hashes = {
        key: metadata["sha256"]
        for key, metadata in manifest["artifacts"].items()
    }
    new_bundle_id = hashlib.sha256(
        json.dumps(artifact_hashes, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    new_bundle_root = old_bundle_root.with_name(new_bundle_id)
    old_bundle_root.rename(new_bundle_root)
    manifest["bundle_id"] = new_bundle_id
    if scale is not None:
        manifest["scale"] = scale
    for metadata in manifest["artifacts"].values():
        relative = Path(*Path(metadata["path"]).parts[2:])
        metadata["path"] = (Path("runs") / new_bundle_id / relative).as_posix()
    manifest["config_snapshot"] = manifest["artifacts"]["config_snapshot"]["path"]
    for contract_key, artifact_key in {
        "label": "labels",
        "training_join": "training_join",
        "feature_health": "feature_health_daily",
    }.items():
        contract = manifest["consumer_contract"][contract_key]
        contract["path"] = manifest["artifacts"][artifact_key]["path"]
        contract["sha256"] = manifest["artifacts"][artifact_key]["sha256"]
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest_path


@pytest.fixture(scope="module")
def candidate(tmp_path_factory: pytest.TempPathFactory) -> tuple[ModuleType, Path]:
    repo_root = Path(__file__).resolve().parents[2]
    root = tmp_path_factory.mktemp("section03-verifier")
    result = run_generation(
        config_path=repo_root / "configs" / "generator" / "base.yaml",
        scale="smoke",
        mode="offline",
        raw_root=root / "raw",
        evidence_root=root / "evidence",
        clean=True,
        seed=42,
    )
    return _verifier(repo_root), result.evidence_paths["section03_manifest"]


def test_candidate_manifest_verifier_accepts_runtime_pending(
    candidate: tuple[ModuleType, Path],
) -> None:
    verifier, manifest_path = candidate

    verified = verifier.verify_manifest(manifest_path, allow_runtime_pending=True)

    assert verified["runtime_evidence"]["status"] == "pending"


def test_strict_manifest_verifier_requires_the_final_runtime_contract(
    candidate: tuple[ModuleType, Path],
) -> None:
    verifier, manifest_path = candidate

    with pytest.raises(ValueError, match="final runtime evidence"):
        verifier.verify_manifest(manifest_path, strict=True)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda manifest: manifest["checks"].update({"psi_finite": False}), "check"),
        (lambda manifest: manifest["checks"].update({"extra": True}), "check"),
        (
            lambda manifest: manifest["artifacts"]["labels"].update({"path": "../labels.csv"}),
            "path",
        ),
        (
            lambda manifest: manifest["consumer_contract"]["label"].update({"sha256": "0" * 64}),
            "consumer",
        ),
        (lambda manifest: manifest["rubric_cells"].update({"E35": {}}), "rubric"),
    ],
)
def test_candidate_manifest_verifier_rejects_tampering(
    candidate: tuple[ModuleType, Path],
    tmp_path: Path,
    mutation: object,
    message: str,
) -> None:
    verifier, manifest_path = candidate
    copied_root = tmp_path / "section03"
    shutil.copytree(manifest_path.parent, copied_root)
    mutated_path = copied_root / "section03_candidate_manifest.json"
    manifest = json.loads(mutated_path.read_text(encoding="utf-8"))
    mutation(manifest)  # type: ignore[operator]
    mutated_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        verifier.verify_manifest(mutated_path, allow_runtime_pending=True)


def test_candidate_manifest_verifier_rejects_hash_consistent_medium_stable_health(
    candidate: tuple[ModuleType, Path],
    tmp_path: Path,
) -> None:
    verifier, manifest_path = candidate
    copied_root = tmp_path / "section03"
    shutil.copytree(manifest_path.parent, copied_root)
    mutated_path = copied_root / "section03_candidate_manifest.json"

    def make_stable(health: pd.DataFrame) -> None:
        health["psi_vs_baseline"] = 0.0
        health["drift_status"] = "stable"
        health["warning_flag"] = False
        health["alert_flag"] = False

    _rewrite_health_and_rebind_bundle(mutated_path, make_stable, scale="medium")

    with pytest.raises(
        ValueError,
        match="^canonical medium evidence requires at least one warning-or-alert day$",
    ):
        verifier.verify_manifest(mutated_path, allow_runtime_pending=True)


@pytest.mark.parametrize(
    ("psi_value", "status", "warning_flag", "alert_flag"),
    [
        (0.10, "stable", False, False),
        (0.15, "warning", True, False),
    ],
)
def test_candidate_manifest_verifier_rejects_inclusive_threshold_mismatch(
    candidate: tuple[ModuleType, Path],
    tmp_path: Path,
    psi_value: float,
    status: str,
    warning_flag: bool,
    alert_flag: bool,
) -> None:
    verifier, manifest_path = candidate
    copied_root = tmp_path / f"section03-{psi_value}"
    shutil.copytree(manifest_path.parent, copied_root)
    mutated_path = copied_root / "section03_candidate_manifest.json"

    def mismatch_boundary(health: pd.DataFrame) -> None:
        health.loc[0, "psi_vs_baseline"] = psi_value
        health.loc[0, "drift_status"] = status
        health.loc[0, "warning_flag"] = warning_flag
        health.loc[0, "alert_flag"] = alert_flag

    _rewrite_health_and_rebind_bundle(mutated_path, mismatch_boundary)

    with pytest.raises(ValueError, match="health threshold status is invalid"):
        verifier.verify_manifest(mutated_path, allow_runtime_pending=True)
