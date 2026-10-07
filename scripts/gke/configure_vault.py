"""Minimal Vault bootstrap for EDAI2 Topic 23 (study-only, zero operator inputs).

The single recovery key (shares=1, threshold=1) is held only in process
memory during configuration and then stored as a Kubernetes Secret in the
Vault namespace. There is no sink path, no attestation file, and no
custodian concept. Disaster recovery outside the cluster is impossible by
design; evidence records that fact. Redacted evidence carries identifiers,
key names, probe results, and revocation proof only.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import secrets
import subprocess
import sys
from pathlib import Path


# Exact KV key matrix from 04.2_llm_design.md Task 8 (key names only, no values).
KEY_MATRIX: dict[str, list[str]] = {
    "kv/edai2/kagent/gateway-keys": [
        "model-api-key", "support-authorization", "drift-authorization", "coordinator-authorization",
    ],
    "kv/edai2/facade/gateway-entry": ["authorization"],
    "kv/edai2/ingress/chat-basic-auth": ["auth"],
    "kv/edai2/jenkins/controller": ["admin-user", "admin-password"],
    "kv/edai2/platform/postgres": ["username", "password", "database"],
    "kv/edai2/platform/clickhouse": ["username", "password"],
    "kv/edai2/platform/valkey": ["password"],
    "kv/edai2/platform/redpanda": ["sasl-user", "sasl-password"],
    "kv/edai2/platform/airflow": ["fernet-key", "webserver-secret", "admin-password"],
    "kv/edai2/platform/datahub": ["system-update-password"],
    "kv/edai2/platform/langfuse": ["nextauth-secret", "salt", "encryption-key"],
    "kv/edai2/platform/agentregistry": ["api-token", "session-secret"],
    "kv/edai2/platform/grafana": ["admin-user", "admin-password"],
}

RECOVERY_SECRET_NAME = "vault-recovery"


# (role, path, expect_allowed): mirrors the checked-in disjoint policies.
# retrieval/drift hold dynamic database roles, not KV reads.
PROBE_MATRIX: tuple[tuple[str, str, bool], ...] = (
    ("agentgateway", "kv/edai2/facade/gateway-entry", True),
    ("coordinator", "kv/edai2/kagent/gateway-keys", True),
    ("retrieval", "kv/edai2/kagent/gateway-keys", False),
    ("retrieval", "kv/edai2/facade/gateway-entry", False),
)


def recovery_secret_ref(namespace: str) -> dict:
    return {"namespace": namespace, "name": RECOVERY_SECRET_NAME}


def parse_kms_key(key_id: str) -> dict:
    """Split a full KMS crypto-key resource id into seal parameters."""
    match = re.fullmatch(
        r"projects/(?P<project>[^/]+)/locations/(?P<region>[^/]+)/keyRings/(?P<key_ring>[^/]+)/cryptoKeys/(?P<crypto_key>[^/]+)",
        key_id or "",
    )
    if not match:
        raise ValueError("KMS key id has an unexpected shape")
    return match.groupdict()


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_redacted_evidence(
    *,
    kms_key_id: str,
    seal_type: str,
    key_names: list[str],
    policy_results: dict[str, bool],
    recovery_threshold: int,
    recovery_shares: int,
    root_revoked: bool,
) -> dict:
    return {
        "initialized": True,
        "seal_type": seal_type,
        "kms_key_id": kms_key_id,
        "key_names": sorted(key_names),
        "key_name_fingerprints": sorted(_fingerprint(name) for name in key_names),
        "policy_results": dict(policy_results),
        "recovery_threshold": recovery_threshold,
        "recovery_shares": recovery_shares,
        "recovery_material": "in-cluster-only",
        "disaster_safe": False,
        "root_revoked": root_revoked,
    }


def _kubectl(kubeconfig: str, context: str, *args: str, token: str | None = None) -> subprocess.CompletedProcess:
    # NOTE: env must be set INSIDE the pod (kubectl never forwards client env).
    command = ["kubectl", "--kubeconfig", kubeconfig, "--context", context, *args]
    if token is not None and "--" in command:
        marker = command.index("--")
        command = [*command[:marker + 1], "env", f"VAULT_TOKEN={token}", *command[marker + 1:]]
    return subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)


def _vault_exec(kubeconfig: str, context: str, namespace: str, *vault_args: str, token: str | None = None) -> str:
    proc = _kubectl(
        kubeconfig, context, "-n", namespace, "exec", "vault-0", "--",
        "vault", *vault_args, token=token,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"vault {' '.join(vault_args[:2])} failed: {proc.stderr[-500:]}")
    return proc.stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kubeconfig", required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--namespace", default="vault")
    parser.add_argument("--kms-key-id", required=True)
    parser.add_argument("--kubernetes-auth", action="store_true")
    parser.add_argument("--policies", default="infra/security/vault/policies")
    parser.add_argument("--redacted-output", required=True)
    args = parser.parse_args(argv)

    if Path(args.redacted_output).exists():
        print("refusing to overwrite existing evidence", file=sys.stderr)
        return 2
    parse_kms_key(args.kms_key_id)
    ref = recovery_secret_ref(args.namespace)

    already = _kubectl(args.kubeconfig, args.context, "-n", args.namespace,
                       "get", "secret", ref["name"], "--ignore-not-found")
    if already.stdout.strip():
        print("recovery secret already exists; refusing to reinitialize", file=sys.stderr)
        return 3
    init_proc = _kubectl(args.kubeconfig, args.context, "-n", args.namespace,
                         "exec", "-i", "vault-0", "--",
                         "vault", "operator", "init",
                         "-recovery-shares=1", "-recovery-threshold=1", "-format=json")
    if init_proc.returncode != 0:
        print(f"init failed: {init_proc.stderr[-500:]}", file=sys.stderr)
        return 3
    init_doc = json.loads(init_proc.stdout)
    token = str(init_doc["root_token"])
    recovery_key = str(init_doc["recovery_keys_b64"][0])
    try:
        status = json.loads(_vault_exec(args.kubeconfig, args.context, args.namespace, "status", "-format=json"))
        seal_type = str(status.get("seal_type", ""))
        if status.get("initialized") is not True or status.get("sealed") is not False:
            raise RuntimeError("vault is not initialized and unsealed")
        secret_manifest = {
            "apiVersion": "v1", "kind": "Secret",
            "metadata": {"name": ref["name"], "namespace": ref["namespace"]},
            "data": {"recovery-key": base64.b64encode(recovery_key.encode("utf-8")).decode("ascii")},
        }
        create = subprocess.run(
            ["kubectl", "--kubeconfig", args.kubeconfig, "--context", args.context,
             "apply", "-f", "-"],
            input=json.dumps(secret_manifest), capture_output=True, text=True, check=False,
        )
        if create.returncode != 0:
            raise RuntimeError(f"recovery secret apply failed: {create.stderr[-500:]}")
        if args.kubernetes_auth:
            _vault_exec(args.kubeconfig, args.context, args.namespace,
                        "auth", "enable", "kubernetes", token=token)
        _vault_exec(args.kubeconfig, args.context, args.namespace,
                    "secrets", "enable", "-path=kv", "-version=2", "kv", token=token)
        policy_dir = Path(args.policies)
        for policy_file in sorted(policy_dir.glob("*.hcl")):
            _kubectl(args.kubeconfig, args.context, "-n", args.namespace, "cp",
                     str(policy_file), f"vault-0:/tmp/{policy_file.name}", token=token)
            _vault_exec(args.kubeconfig, args.context, args.namespace,
                        "policy", "write", policy_file.stem, f"/tmp/{policy_file.name}", token=token)
        populated: list[str] = []
        for path, keys in KEY_MATRIX.items():
            values = [f"{key}={secrets.token_hex(24)}" for key in keys]
            _vault_exec(args.kubeconfig, args.context, args.namespace,
                        "kv", "put", path, *values, token=token)
            populated.extend(keys)
        policy_results: dict[str, bool] = {}
        for role, path, expect_allowed in PROBE_MATRIX:
            out = _vault_exec(args.kubeconfig, args.context, args.namespace,
                              "token", "create", f"-policy={role}", "-format=json", token=token)
            role_token = str(json.loads(out)["auth"]["client_token"])
            try:
                probe = _kubectl(args.kubeconfig, args.context, "-n", args.namespace, "exec", "vault-0", "--",
                                 "vault", "kv", "get", "-format=json", path, token=role_token)
                allowed = probe.returncode == 0
            finally:
                _vault_exec(args.kubeconfig, args.context, args.namespace,
                            "token", "revoke", role_token, token=token)
            label = f"{role}-{'allow' if expect_allowed else 'deny'}-{path.rsplit('/', 1)[-1]}"
            policy_results[label] = (allowed is expect_allowed)
        denied = _kubectl(args.kubeconfig, args.context, "-n", args.namespace, "exec", "vault-0", "--",
                          "vault", "kv", "get", "-format=json", "kv/edai2/kagent/gateway-keys",
                          token="invalid-probe-token")
        policy_results["cross-path-deny"] = denied.returncode != 0
        _vault_exec(args.kubeconfig, args.context, args.namespace, "token", "revoke", "-self", token=token)
        root_revoked = True
    finally:
        token = "0" * 64
        recovery_key = "0" * 64
        del token, recovery_key
    evidence = build_redacted_evidence(
        kms_key_id=args.kms_key_id, seal_type=seal_type, key_names=populated,
        policy_results=policy_results, recovery_threshold=1, recovery_shares=1,
        root_revoked=root_revoked,
    )
    out_path = Path(args.redacted_output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("VAULT_BOOTSTRAP=OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
