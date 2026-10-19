from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
JOBS_COMMIT = "7233469eef8519aeb059da03a924bb6a180bed5b"


def _load_script():
    path = ROOT / "scripts/qa/capture_edai2_evidence.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _jobs() -> dict:
    return json.loads((ROOT / "evidence/04_2_llm_design/cicd/jobs.json").read_text(encoding="utf-8"))


def test_jenkins_evidence_passes_on_six_digest_matched_records() -> None:
    """Six immutable existing records must pass before a browser session opens."""
    capture = _load_script()
    result = capture.verify_jenkins_evidence(
        _jobs(), expected_commit=JOBS_COMMIT, expected_jobs=6,
        require_buildkit_serialization=True, require_wave_order=True,
    )
    assert result["jobs"] == 6 and result["commit_sha"] == JOBS_COMMIT


def test_jenkins_evidence_rejects_commit_mismatch() -> None:
    capture = _load_script()
    with pytest.raises(ValueError, match="commit"):
        capture.verify_jenkins_evidence(
            _jobs(), expected_commit="0" * 40, expected_jobs=6,
            require_buildkit_serialization=True, require_wave_order=True,
        )


def test_jenkins_evidence_rejects_count_mismatch() -> None:
    capture = _load_script()
    with pytest.raises(ValueError, match="job count"):
        capture.verify_jenkins_evidence(
            _jobs(), expected_commit=JOBS_COMMIT, expected_jobs=5,
            require_buildkit_serialization=True, require_wave_order=True,
        )


def test_jenkins_evidence_rejects_broken_digest_chain() -> None:
    """A rematched tag without identical remote/pod/expected digests is a rebuild."""
    capture = _load_script()
    payload = _jobs()
    tampered = copy.deepcopy(payload)
    tampered["jobs"][0]["pod_image_digest"] = "sha256:" + "1" * 64
    with pytest.raises(ValueError, match="digest"):
        capture.verify_jenkins_evidence(
            tampered, expected_commit=JOBS_COMMIT, expected_jobs=6,
            require_buildkit_serialization=True, require_wave_order=True,
        )


def test_jenkins_evidence_rejects_wave_order_violation() -> None:
    capture = _load_script()
    payload = _jobs()
    tampered = copy.deepcopy(payload)
    tampered["waves"] = list(reversed(tampered["waves"]))
    with pytest.raises(ValueError, match="wave"):
        capture.verify_jenkins_evidence(
            tampered, expected_commit=JOBS_COMMIT, expected_jobs=6,
            require_buildkit_serialization=True, require_wave_order=True,
        )
