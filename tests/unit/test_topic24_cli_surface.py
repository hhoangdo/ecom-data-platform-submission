"""Topic 24 command-surface contract: every Topic 24 CLI flag parses and behaves fail-closed.

Covers the D3/D4 planning deltas: ``manage_profile.py`` render/output/lease-TTL
flags and ``capture_edai2_evidence.py`` private-endpoint inventory verifiers.
All tests are local-only: tmp leases/files, the read-only dedicated kubeconfig,
and stub live runners. No lease is acquired, no cluster is mutated.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

DEDICATED_KUBECONFIG = "tmp/edai2-gcp/kubeconfig"
DEDICATED_CONTEXT = "edai2-gke"

EXPECTED_KEYS = ("agentregistry_ui", "grafana_ui", "airflow_web", "datahub_frontend", "vault_status")
EXPECTED_FIELDS = ("namespace", "service_name", "service_uid", "service_port", "target_port", "selector_sha256", "ready_endpoint_uids")


def _load(name: str, relative: str):
    path = Path(__file__).resolve().parents[2] / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, f"missing module file: {relative}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _endpoint_entry() -> dict:
    return {
        "namespace": "edai2",
        "service_name": "edai2-svc",
        "service_uid": "uid-1",
        "service_port": 80,
        "target_port": 8080,
        "selector_sha256": "a" * 64,
        "ready_endpoint_uids": ["ep-1"],
    }


def _five_key_inventory() -> dict:
    return {"private_endpoints": {key: _endpoint_entry() for key in EXPECTED_KEYS}}


# --- manage_profile.py: --render-only / --output ---


def test_manage_profile_render_only_writes_capacity_file(tmp_path: Path, capsys) -> None:
    module = _load("manage_profile", "scripts/gke/manage_profile.py")
    out = tmp_path / "platform_capacity.json"
    rc = module.main([
        "core", "--ttl", "2h", "--render-only",
        "--kubeconfig", DEDICATED_KUBECONFIG, "--context", DEDICATED_CONTEXT,
        "--output", str(out),
    ])
    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["profile"] == "core"
    assert payload["ttl_hours"] == 2
    assert payload["dry_run"] is True
    assert capsys.readouterr().out  # stdout render preserved


def test_manage_profile_output_requires_render_mode(tmp_path: Path) -> None:
    module = _load("manage_profile", "scripts/gke/manage_profile.py")
    out = tmp_path / "platform_capacity.json"
    with pytest.raises(SystemExit) as exc:
        module.main(["core", "--ttl", "2h", "--output", str(out)])
    assert exc.value.code == 2
    assert not out.exists()


# --- manage_profile.py: --resume-existing-ttl ---


def test_manage_profile_resume_existing_ttl_uses_lease(tmp_path: Path) -> None:
    module = _load("manage_profile", "scripts/gke/manage_profile.py")
    lease = tmp_path / "lease.json"
    module.acquire_lease(lease, owner="topic24-platform", profile="core", ttl_hours=2, commit_sha="b" * 40)
    out = tmp_path / "platform_install.json"
    rc = module.main([
        "core", "--resume-existing-ttl", "--owner", "topic24-platform",
        "--stage", "platform", "--lease-file", str(lease),
        "--kubeconfig", DEDICATED_KUBECONFIG, "--context", DEDICATED_CONTEXT,
        "--output", str(out),
    ])
    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ttl_hours"] == 2
    assert payload["stage"] == "platform"


def test_manage_profile_resume_existing_ttl_rejects_owner_mismatch(tmp_path: Path) -> None:
    module = _load("manage_profile", "scripts/gke/manage_profile.py")
    lease = tmp_path / "lease.json"
    module.acquire_lease(lease, owner="topic24-platform", profile="core", ttl_hours=2, commit_sha="b" * 40)
    with pytest.raises(SystemExit) as exc:
        module.main([
            "core", "--resume-existing-ttl", "--owner", "intruder",
            "--lease-file", str(lease),
            "--kubeconfig", DEDICATED_KUBECONFIG, "--context", DEDICATED_CONTEXT,
        ])
    assert exc.value.code == 2


def test_manage_profile_resume_existing_ttl_rejects_missing_lease(tmp_path: Path) -> None:
    module = _load("manage_profile", "scripts/gke/manage_profile.py")
    with pytest.raises(SystemExit) as exc:
        module.main([
            "core", "--resume-existing-ttl", "--owner", "topic24-platform",
            "--lease-file", str(tmp_path / "absent.json"),
            "--kubeconfig", DEDICATED_KUBECONFIG, "--context", DEDICATED_CONTEXT,
        ])
    assert exc.value.code == 2


# --- capture_edai2_evidence.py: key/field CSV contract ---


def test_capture_parses_exact_five_keys_and_seven_fields() -> None:
    module = _load("capture_edai2_evidence", "scripts/qa/capture_edai2_evidence.py")
    assert module.parse_key_list(",".join(EXPECTED_KEYS)) == list(EXPECTED_KEYS)
    assert module.require_exact_keys(list(EXPECTED_KEYS), list(EXPECTED_KEYS), "endpoints") is None
    with pytest.raises(ValueError):
        module.require_exact_keys(["grafana_ui"], list(EXPECTED_KEYS), "endpoints")
    with pytest.raises(ValueError):
        module.require_exact_keys(list(EXPECTED_KEYS) + ["extra"], list(EXPECTED_KEYS), "endpoints")
    assert module.parse_key_list("namespace,service_name") == ["namespace", "service_name"]
    with pytest.raises(ValueError):
        module.parse_key_list(" , ")


# --- capture_edai2_evidence.py: inventory + exclusion verifiers ---


def test_capture_verify_private_endpoint_inventory_accepts_exact_match() -> None:
    module = _load("capture_edai2_evidence", "scripts/qa/capture_edai2_evidence.py")
    module.verify_private_endpoint_inventory(_five_key_inventory(), list(EXPECTED_KEYS))


def test_capture_verify_private_endpoint_inventory_rejects_absent_or_extra_key() -> None:
    module = _load("capture_edai2_evidence", "scripts/qa/capture_edai2_evidence.py")
    missing = {"private_endpoints": {k: _endpoint_entry() for k in EXPECTED_KEYS[:4]}}
    with pytest.raises(ValueError):
        module.verify_private_endpoint_inventory(missing, list(EXPECTED_KEYS))
    extra = _five_key_inventory()
    extra["private_endpoints"]["stowaway"] = _endpoint_entry()
    with pytest.raises(ValueError):
        module.verify_private_endpoint_inventory(extra, list(EXPECTED_KEYS))
    stale = _five_key_inventory()
    stale["private_endpoints"]["grafana_ui"] = {"namespace": "edai2"}
    with pytest.raises(ValueError):
        module.verify_private_endpoint_inventory(stale, list(EXPECTED_KEYS))


def test_capture_verify_platform_exclusions_passes_clean_and_fails_forbidden() -> None:
    module = _load("capture_edai2_evidence", "scripts/qa/capture_edai2_evidence.py")
    module.verify_platform_exclusions({"private_endpoints": {}}, ["bundled-postgres", "public-loadbalancer"])
    with pytest.raises(ValueError):
        module.verify_platform_exclusions(
            {"releases": ["bundled-postgres"], "private_endpoints": {}},
            ["bundled-postgres", "public-loadbalancer"],
        )


# --- capture_edai2_evidence.py: Topic 24 CLI dispatch ---


def test_capture_cli_verify_inventory_and_exclusions(tmp_path: Path, monkeypatch, capsys) -> None:
    module = _load("capture_edai2_evidence", "scripts/qa/capture_edai2_evidence.py")
    inventory = tmp_path / "platform_install.json"
    inventory.write_text(json.dumps(_five_key_inventory()), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [
        "capture_edai2_evidence.py", "--verify-private-endpoint-inventory", str(inventory),
        "--kubeconfig", DEDICATED_KUBECONFIG, "--context", DEDICATED_CONTEXT,
        "--expected-keys", ",".join(EXPECTED_KEYS), "--strict",
    ])
    assert module.main() == 0
    assert "verified" in capsys.readouterr().out
    monkeypatch.setattr(sys, "argv", [
        "capture_edai2_evidence.py", "--verify-platform-exclusions", str(inventory),
        "--forbid", "bundled-postgres,bundled-valkey,rustfs,builtin-agents,builtin-tools,public-loadbalancer,app-sandboxagents",
        "--strict",
    ])
    assert module.main() == 0


def test_capture_cli_verify_inventory_rejects_wrong_keys(tmp_path: Path, monkeypatch) -> None:
    module = _load("capture_edai2_evidence", "scripts/qa/capture_edai2_evidence.py")
    inventory = tmp_path / "platform_install.json"
    inventory.write_text(json.dumps(_five_key_inventory()), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [
        "capture_edai2_evidence.py", "--verify-private-endpoint-inventory", str(inventory),
        "--kubeconfig", DEDICATED_KUBECONFIG, "--context", DEDICATED_CONTEXT,
        "--expected-keys", "grafana_ui", "--strict",
    ])
    with pytest.raises(SystemExit) as exc:
        module.main()
    assert exc.value.code == 2
