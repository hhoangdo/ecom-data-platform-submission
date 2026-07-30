from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
from types import ModuleType

import pytest

from vina_bim_shop.generators.runner import run_generation


def _verifier(repo_root: Path) -> ModuleType:
    path = repo_root / "scripts" / "generate" / "verify_section03_manifest.py"
    spec = importlib.util.spec_from_file_location("section03_manifest_verifier", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
