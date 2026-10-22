from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
REVISION = "e" * 40


def _load_script():
    path = ROOT / "scripts/gke/capture_persistence_fingerprint.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _readers():
    return {
        "postgres": lambda: {"tables": ["edai2_rag_active_alias"], "alias": "canonical-evidence-abc"},
        "workloads": lambda: {"deployments": {"retrieval-agent": 3}},
        "jobs": lambda: {"digests": {"edai2-rag-index": "sha256:" + "a" * 64}},
    }


def test_pg_password_travels_over_stdin_never_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Process-list and audit-log exposure of the database password is forbidden."""
    fp = _load_script()
    seen: dict = {}

    class Completed:
        returncode = 0
        stdout = "ok\n"

    def fake_run(command: list[str], **kwargs: object):
        seen["command"] = command
        seen["input"] = kwargs.get("input")
        return Completed()

    monkeypatch.setattr(fp.subprocess, "run", fake_run)
    fp._exec("kc", "ctx", "edai2", "pod-0", ["psql", "-c", "SELECT 1;"], input_text="s3cret\n")
    assert "s3cret\n" not in " ".join(seen["command"])
    assert seen["input"] == "s3cret\n"


def test_capture_lists_every_subsystem_with_revision() -> None:
    fp = _load_script()
    assert set(fp.SUBSYSTEMS) >= {
        "postgres", "feast", "substrate_valkey", "redpanda", "clickhouse_langfuse",
        "opensearch_datahub", "agent_registry", "jenkins", "vault", "pvc", "gcs",
        "observability", "platform", "workloads",
    }
    payload = fp.capture_fingerprint(readers=_readers(), revision=REVISION)
    assert payload["revision"] == REVISION
    assert set(payload["subsystems"]) == set(_readers())


def test_compare_matches_identical_and_names_diffs() -> None:
    fp = _load_script()
    before = fp.capture_fingerprint(readers=_readers(), revision=REVISION)
    after = fp.capture_fingerprint(readers=_readers(), revision=REVISION)
    assert fp.compare_fingerprints(before, after)["match"] is True
    altered = fp.capture_fingerprint(
        readers={**_readers(), "workloads": lambda: {"deployments": {"retrieval-agent": 4}}},
        revision=REVISION,
    )
    result = fp.compare_fingerprints(before, altered)
    assert result["match"] is False and result["diffs"] == ["workloads"]


def test_vault_metadata_allowlist_never_copies_secrets(tmp_path: Path) -> None:
    """Admin tokens, shares, and recovery material must never enter the fingerprint."""
    fp = _load_script()
    bootstrap = json.loads((ROOT / "evidence/04_2_llm_design/security/vault_bootstrap.json").read_text(encoding="utf-8"))
    metadata = fp.vault_canary_metadata(bootstrap)
    text = json.dumps(metadata, sort_keys=True)
    assert "admin_token" not in text and "recovery_shares" not in text and "recovery_material" not in text
    for value in (bootstrap.get("admin_token"),):
        if value:
            assert str(value) not in text
    assert metadata["initialized"] is True and metadata["seal_type"] == bootstrap["seal_type"]
    assert metadata["key_names"] == bootstrap["key_names"]

def test_after_phase_writes_both_output_and_summary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The after phase must persist persistence_after.json, not only the summary."""
    fp = _load_script()
    monkeypatch.setattr(fp, "build_readers", lambda _args: {})
    monkeypatch.setattr(
        fp, "capture_fingerprint",
        lambda **_kwargs: {"revision": REVISION, "captured_at": "2026-10-19T00:00:00Z", "subsystems": {}},
    )
    before = tmp_path / "before.json"
    before.write_text(json.dumps({"revision": REVISION, "subsystems": {}}), encoding="utf-8")
    after = tmp_path / "after.json"
    summary = tmp_path / "summary.json"
    code = fp.main([
        "--kubeconfig", "k", "--context", "c", "--phase", "after",
        "--output", str(after), "--compare", str(before), "--summary", str(summary), "--strict",
    ])
    assert code == 0
    assert after.is_file()
    assert json.loads(summary.read_text(encoding="utf-8"))["match"] is True
