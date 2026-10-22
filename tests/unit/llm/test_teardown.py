from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _load_script():
    path = ROOT / "scripts" / "gke" / "teardown.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _payload(**overrides):
    script = _load_script()
    values = {
        "ingress": {"items": []},
        "load_balancers": {"items": []},
        "forwarding_rules": [],
        "nodes": {"items": []},
        "cluster": {"currentNodeCount": 0, "nodePools": [{"name": "platform", "status": "RUNNING", "initialNodeCount": 0}]},
        "actions": [],
        "lease_files": [],
        "observed_at": "2026-10-19T00:00:00Z",
        "revision": "a" * 40,
        "project": "p",
        "zone": "z",
        "cluster_name": "c",
    }
    values.update(overrides)
    return script.build_teardown_payload(**values)


def test_teardown_payload_passes_only_on_all_zero_proofs() -> None:
    payload = _payload()
    assert payload["ok"] is True
    assert payload["blockers"] == []
    assert payload["proof"]["pools_zero"] is True


def test_teardown_payload_names_every_nonzero_blocker() -> None:
    payload = _payload(
        ingress={"items": [{"metadata": {"name": "x"}}]},
        load_balancers={"items": [{"metadata": {"name": "y"}}]},
        forwarding_rules=[{"name": "z"}],
        nodes={"items": [{"metadata": {"name": "n"}}]},
        cluster={"currentNodeCount": 1},
        lease_files=["tmp/edai2-gcp/topic31-final-lease.json"],
    )
    assert payload["ok"] is False
    assert set(payload["blockers"]) == {
        "ingress_zero", "load_balancers_zero", "forwarding_rules_zero",
        "nodes_zero", "pools_zero", "lease_absent",
    }

def test_teardown_accepts_lagging_cluster_count_after_successful_resizes() -> None:
    """GKE currentNodeCount may lag; an empty node list plus successful resizes is authoritative."""
    payload = _payload(
        nodes={"items": []},
        cluster={"currentNodeCount": 1},
        actions=[
            {"command": "gcloud container clusters resize edai2 --node-pool platform --num-nodes 0", "returncode": 0},
            {"command": "gcloud container clusters resize edai2 --node-pool spot --num-nodes 0", "returncode": 0},
        ],
    )
    assert payload["ok"] is True
    assert payload["proof"]["pools_zero"] is True
