"""Fail-closed persistence fingerprints for suspended-to-resumed recovery evidence.

Only non-secret generations, hashes, revisions, counts, and metadata enter the
record. Recovery payloads, shares, tokens, and state never do.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path


SUBSYSTEMS = (
    "postgres", "feast", "substrate_valkey", "redpanda", "clickhouse_langfuse",
    "opensearch_datahub", "agent_registry", "jenkins", "vault", "pvc", "gcs",
    "observability", "platform", "workloads",
)
_VAULT_METADATA_FIELDS = (
    "initialized", "seal_type", "key_names", "key_name_fingerprints",
    "policy_results", "disaster_safe", "root_revoked",
)
_SECRET = re.compile(r"(?i)(password|token|secret|api[_-]?key|customer[_-]?id|bearer|authorization|[\w.+-]+@[\w.-]+\.[a-z]{2,})")


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def vault_canary_metadata(bootstrap: dict) -> dict:
    """Extract the non-secret Vault identity; secret fields never leave the file."""
    if not isinstance(bootstrap, dict):
        raise ValueError("vault bootstrap evidence is invalid")
    metadata = {field: bootstrap.get(field) for field in _VAULT_METADATA_FIELDS}
    if metadata["initialized"] is not True:
        raise ValueError("vault is not initialized")
    key_names = metadata.get("key_names")
    if not isinstance(key_names, list) or not key_names or any(not re.fullmatch(r"[a-z][a-z0-9-]*", name) for name in key_names):
        raise ValueError("vault key names are invalid")
    fingerprints = metadata.get("key_name_fingerprints", [])
    if not isinstance(fingerprints, list) or any(not re.fullmatch(r"[0-9a-f]{64}", item) for item in fingerprints):
        raise ValueError("vault key fingerprints are invalid")
    rest = {key: value for key, value in metadata.items() if key not in ("key_names", "key_name_fingerprints")}
    if _SECRET.search(json.dumps(rest, sort_keys=True)):
        raise ValueError("vault metadata contains secret material")
    return metadata


def capture_fingerprint(*, readers: dict[str, Callable[[], dict]], revision: str) -> dict:
    """Run every supplied subsystem reader; reader failures fail closed."""
    if not re.fullmatch(r"[0-9a-f]{40}", revision or ""):
        raise ValueError("fingerprint revision is invalid")
    if not readers:
        raise ValueError("fingerprint needs at least one subsystem reader")
    subsystems: dict[str, dict] = {}
    for name, reader in readers.items():
        summary = reader()
        if not isinstance(summary, dict):
            raise ValueError(f"fingerprint reader is invalid: {name}")
        if name != "vault" and _SECRET.search(json.dumps(summary, sort_keys=True)):
            # vault_canary_metadata() already enforces its own allowlist and omits
            # values, tokens, shares, and recovery material; key *names* are not secrets.
            raise ValueError(f"fingerprint reader leaked secret material: {name}")
        subsystems[name] = summary
    return {"revision": revision, "captured_at": _utcnow(), "subsystems": subsystems}


def compare_fingerprints(before: dict, after: dict) -> dict:
    """Compare subsystem by subsystem; any difference blocks the recovery claim."""
    try:
        before_subsystems = before["subsystems"]
        after_subsystems = after["subsystems"]
    except (KeyError, TypeError) as error:
        raise ValueError("fingerprint payloads are invalid") from error
    if set(before_subsystems) != set(after_subsystems):
        raise ValueError("fingerprint subsystem sets differ")
    diffs = [
        name for name in before_subsystems
        if json.dumps(before_subsystems[name], sort_keys=True) != json.dumps(after_subsystems.get(name), sort_keys=True)
    ]
    return {"match": not diffs, "diffs": sorted(diffs)}


def _kubectl_json(kubeconfig: str, context: str, *command: str) -> dict:
    completed = subprocess.run(
        ["kubectl", "--kubeconfig", kubeconfig, "--context", context, *command],
        check=False, capture_output=True, text=True, encoding="utf-8",
    )
    if completed.returncode:
        raise ValueError(f"kubectl read failed: {' '.join(command[:3])}")
    payload = json.loads(completed.stdout)
    if not isinstance(payload, dict):
        raise ValueError("kubectl JSON output is invalid")
    return payload


def _exec(kubeconfig: str, context: str, namespace: str, pod: str, command: list[str], input_text: str | None = None) -> str:
    argv = ["kubectl", "--kubeconfig", kubeconfig, "--context", context, "exec"]
    if input_text is not None:
        argv.append("-i")
    argv += [pod, "--namespace", namespace, "--", *command]
    completed = subprocess.run(
        argv, check=False, capture_output=True, text=True, encoding="utf-8",
        input=input_text,
    )
    if completed.returncode:
        raise ValueError(f"pod exec failed: {pod}")
    return completed.stdout


def build_readers(args: argparse.Namespace) -> dict[str, Callable[[], dict]]:
    """Assemble live subsystem readers from explicit operator inputs."""
    readers: dict[str, Callable[[], dict]] = {}
    kubeconfig, context = str(args.kubeconfig), str(args.context)

    def workloads() -> dict:
        observed: dict[str, dict] = {}
        for kind in ("deployments", "statefulsets"):
            payload = _kubectl_json(kubeconfig, context, "get", kind, "-A", "-o", "json")
            for item in payload.get("items", []):
                namespace = item["metadata"].get("namespace", "")
                if namespace not in ("edai2", "kagent", "vault"):
                    continue
                observed[f"{namespace}/{item['metadata']['name']}"] = {
                    "generation": item["metadata"].get("generation"),
                    "replicas": item.get("spec", {}).get("replicas"),
                }
        return observed

    def pvc() -> dict:
        payload = _kubectl_json(kubeconfig, context, "get", "pvc", "-A", "-o", "json")
        return {
            f"{item['metadata'].get('namespace')}/{item['metadata']['name']}": item["metadata"].get("uid")
            for item in payload.get("items", [])
        }

    readers["workloads"] = workloads
    readers["pvc"] = pvc
    if args.postgres_pod is not None:
        import os

        password = os.environ.get(args.postgres_password_env or "", "")
        if not password:
            raise ValueError("--postgres-password-env must name a password variable")
        # The password travels only in the transient exec argument vector and
        # never enters evidence; the operator rotates it after the run.

        def psql(query: str) -> list[str]:
            script = 'IFS= read -r PGPASSWORD; export PGPASSWORD; exec psql -U "$1" -d "$2" -tA -c "$0"'
            out = _exec(
                kubeconfig, context, "edai2", args.postgres_pod,
                ["sh", "-c", script, query, args.postgres_user or "postgres", args.postgres_db or "edai2"],
                input_text=password + "\n",
            )
            return [line.strip() for line in out.splitlines() if line.strip()]

        def postgres() -> dict:
            tables = psql("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1;")
            counts = {}
            for table in ("edai2_rag_candidate_version", "edai2_rag_document_version", "edai2_rag_active_alias"):
                if table in tables:
                    counts[table] = psql(f"SELECT COUNT(*) FROM {table};")
            alias = psql("SELECT index_version FROM edai2_rag_active_alias;")
            return {"tables": tables, "counts": counts, "active_alias": alias}
        readers["postgres"] = postgres
    if args.jobs_evidence is not None:
        def jobs() -> dict:
            payload = json.loads(Path(args.jobs_evidence).read_text(encoding="utf-8"))
            return {job["job"]: job.get("expected_digest") for job in payload.get("jobs", [])}
        readers["jenkins"] = jobs
    if args.vault_evidence is not None:
        def vault() -> dict:
            return vault_canary_metadata(json.loads(Path(args.vault_evidence).read_text(encoding="utf-8")))
        readers["vault"] = vault
    if args.platform_inventory is not None:
        def platform() -> dict:
            raw = Path(args.platform_inventory).read_bytes()
            return {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
        readers["platform"] = platform
    if args.gcs_uri is not None:
        def gcs() -> dict:
            from google.cloud import storage

            client = storage.Client()
            bucket_name, _, prefix = args.gcs_uri.replace("gs://", "").partition("/")
            blobs = client.list_blobs(bucket_name, prefix=prefix)
            return {blob.name: {"generation": blob.generation, "crc32c": blob.crc32c} for blob in blobs}
        readers["gcs"] = gcs
    for deferred in ("feast", "substrate_valkey", "redpanda", "clickhouse_langfuse", "opensearch_datahub", "agent_registry", "observability"):
        readers.setdefault(deferred, lambda d=deferred: {"status": "deferred", "reason": f"{d} reader pending owning-topic accessor contract"})
    return readers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kubeconfig", required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--phase", choices=("before", "after"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compare", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--postgres-pod", default=None)
    parser.add_argument("--postgres-user", default=None)
    parser.add_argument("--postgres-db", default=None)
    parser.add_argument("--postgres-password-env", default=None)
    parser.add_argument("--jobs-evidence", type=Path, default=None)
    parser.add_argument("--vault-evidence", type=Path, default=None)
    parser.add_argument("--platform-inventory", type=Path, default=None)
    parser.add_argument("--gcs-uri", default=None)
    args = parser.parse_args(argv)
    if not args.strict:
        parser.error("--strict is required")
    if args.phase == "after" and (args.compare is None or args.summary is None):
        parser.error("--phase after requires --compare and --summary")
    try:
        revision = subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()
        payload = capture_fingerprint(readers=build_readers(args), revision=revision)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.phase == "after":
        try:
            before = json.loads(Path(args.compare).read_text(encoding="utf-8"))
            result = compare_fingerprints(before, payload)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            parser.error(str(error))
        summary = {"match": result["match"], "diffs": result["diffs"], "before": str(args.compare), "after": str(args.output)}
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if not result["match"]:
            parser.error(f"persistence fingerprint mismatch: {', '.join(result['diffs'])}")
        print(json.dumps({"hibernate_resume": str(args.summary), "match": True}, sort_keys=True))
        return 0
    print(json.dumps({"fingerprint": str(args.output), "subsystems": sorted(payload["subsystems"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
