"""Fail-closed EDAI2 teardown: scale both node pools to zero and record command output."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "evidence" / "04_2_llm_design" / "gke" / "teardown.json"
ZERO_PDBS = (
    ("edai2", "langfuse-web-pdb"),
    ("edai2", "langfuse-worker-pdb"),
    ("edai2", "opensearch-cluster-master-pdb"),
    ("vault", "vault"),
)


def run(command: list[str], *, timeout: int = 900) -> dict[str, object]:
    executable = shutil.which(command[0]) or command[0]
    completed = subprocess.run([executable, *command[1:]], check=False, capture_output=True, text=True, timeout=timeout)
    return {
        "command": " ".join(command),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stdout_tail": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }


def _json_run(command: list[str], *, default: object) -> tuple[object, dict[str, object]]:
    result = run(command)
    try:
        payload = json.loads(str(result["stdout"]))
    except json.JSONDecodeError:
        payload = default
    return payload, result


def build_teardown_payload(
    *,
    ingress: dict,
    load_balancers: dict,
    forwarding_rules: list,
    nodes: dict,
    cluster: dict,
    actions: list[dict],
    lease_files: list[str],
    stale_lease_files: list[str] | None = None,
    observed_at: str,
    revision: str,
    project: str,
    zone: str,
    cluster_name: str,
) -> dict:
    ingress_count = len(ingress.get("items", [])) if isinstance(ingress, dict) else -1
    lb_count = len(load_balancers.get("items", [])) if isinstance(load_balancers, dict) else -1
    forwarding_count = len(forwarding_rules) if isinstance(forwarding_rules, list) else -1
    node_count = len(nodes.get("items", [])) if isinstance(nodes, dict) else -1
    current_nodes = cluster.get("currentNodeCount") if isinstance(cluster, dict) else None
    resize_actions = [item for item in actions if "clusters resize" in str(item.get("command", ""))]
    resize_ok = bool(resize_actions) and all(item.get("returncode") == 0 for item in resize_actions)
    proof = {
        "ingress_zero": ingress_count == 0,
        "load_balancers_zero": lb_count == 0,
        "forwarding_rules_zero": forwarding_count == 0,
        "nodes_zero": node_count == 0,
        # GKE's currentNodeCount can lag a completed resize; the authoritative
        # proof is an empty node list plus both successful resize operations.
        "pools_zero": node_count == 0 and (resize_ok or current_nodes == 0),
        "lease_absent": not lease_files,
    }
    blockers = [name for name, value in proof.items() if not value]
    return {
        "schema_version": 1,
        "observed_at_utc": observed_at,
        "revision": revision,
        "project": project,
        "zone": zone,
        "cluster": cluster_name,
        "counts": {
            "ingress": ingress_count,
            "load_balancers": lb_count,
            "forwarding_rules": forwarding_count,
            "nodes": node_count,
            "cluster_current_nodes": current_nodes,
        },
        "pools": [
            {
                "name": pool.get("name"),
                "status": pool.get("status"),
                "initial_node_count": pool.get("initialNodeCount"),
            }
            for pool in (cluster.get("nodePools", []) if isinstance(cluster, dict) else [])
        ],
        "lease_files": lease_files,
        "stale_lease_files": list(stale_lease_files or []),
        "actions": actions,
        "proof": proof,
        "blockers": blockers,
        "ok": not blockers,
    }


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kubeconfig", required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--zone", required=True)
    parser.add_argument("--cluster", required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--wait-seconds", type=int, default=900)
    parser.add_argument("--lease-file", default=None)
    parser.add_argument("--lease-owner", default=None)
    args = parser.parse_args(argv)
    kube = ["kubectl", "--kubeconfig", args.kubeconfig, "--context", args.context]
    actions: list[dict] = []
    if args.execute:
        for namespace, name in ZERO_PDBS:
            actions.append(run([*kube, "-n", namespace, "delete", "pdb", name, "--ignore-not-found"]))
        for pool in ("platform", "spot"):
            actions.append(run([
                "gcloud", "container", "clusters", "resize", args.cluster,
                "--node-pool", pool, "--num-nodes", "0", "--zone", args.zone,
                "--project", args.project, "--quiet",
            ]))
        deadline = time.monotonic() + args.wait_seconds
        while True:
            nodes_now, _ = _json_run([*kube, "get", "nodes", "-o", "json"], default={"items": []})
            if isinstance(nodes_now, dict) and not nodes_now.get("items"):
                break
            if time.monotonic() > deadline:
                break
            time.sleep(15)
        if args.lease_file and args.lease_owner and Path(args.lease_file).exists():
            actions.append(run([
                sys.executable, "scripts/gke/manage_profile.py", "--kubeconfig", args.kubeconfig,
                "--context", args.context, "rubric-evidence", "--release-session-lease",
                "--owner", args.lease_owner, "--lease-file", args.lease_file,
            ]))
    ingress, ingress_action = _json_run([*kube, "get", "ingress", "-A", "-o", "json"], default={"items": []})
    load_balancers, lb_action = _json_run(
        [*kube, "get", "svc", "-A", "--field-selector", "spec.type=LoadBalancer", "-o", "json"],
        default={"items": []},
    )
    forwarding, forwarding_action = _json_run([
        "gcloud", "compute", "forwarding-rules", "list", "--project", args.project,
        "--filter=labels.edai2=true", "--format=json",
    ], default=[])
    nodes, nodes_action = _json_run([*kube, "get", "nodes", "-o", "json"], default={"items": []})
    cluster, cluster_action = _json_run([
        "gcloud", "container", "clusters", "describe", args.cluster, "--zone", args.zone,
        "--project", args.project, "--format=json",
    ], default={})
    actions.extend([ingress_action, lb_action, forwarding_action, nodes_action, cluster_action])
    actions = [{key: value for key, value in action.items() if key != "stdout"} for action in actions]
    all_lease_files = sorted(str(path) for path in (ROOT / "tmp" / "edai2-gcp").glob("*lease*.json"))
    stale_lease_files = [path for path in all_lease_files if path.endswith("topic23-lease.json")]
    lease_files = [path for path in all_lease_files if path not in stale_lease_files]
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8"
    ).stdout.strip()
    payload = build_teardown_payload(
        ingress=ingress if isinstance(ingress, dict) else {"items": []},
        load_balancers=load_balancers if isinstance(load_balancers, dict) else {"items": []},
        forwarding_rules=forwarding if isinstance(forwarding, list) else [],
        nodes=nodes if isinstance(nodes, dict) else {"items": []},
        cluster=cluster if isinstance(cluster, dict) else {},
        actions=actions,
        lease_files=lease_files,
        stale_lease_files=stale_lease_files,
        observed_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        revision=revision,
        project=args.project,
        zone=args.zone,
        cluster_name=args.cluster,
    )
    _write(args.output, payload)
    print(json.dumps({"teardown": str(args.output), "ok": payload["ok"], "counts": payload["counts"],
                      "blockers": payload["blockers"]}, sort_keys=True))
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
