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
import datetime
import hashlib
import json
import os
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
    "kv/edai2/platform/opensearch": ["username", "password"],
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


# Kubernetes-auth role bindings. The external-secrets role backs
# ClusterSecretStore/edai2-vault (serviceaccount external-secrets in namespace
# external-secrets) and maps to the external-secrets policy, which grants read
# on exactly the KV paths consumed by the checked-in ExternalSecrets.
# `vault write` upserts, so role creation is idempotent.
KUBERNETES_ROLE_BINDINGS: dict[str, dict[str, str]] = {
    "external-secrets": {
        "bound_service_account_names": "external-secrets",
        "bound_service_account_namespaces": "external-secrets",
        "token_policies": "external-secrets",
    },
}


def build_kubernetes_role_args(role: str) -> list[str]:
    """Return `vault write` k=v params for a bound kubernetes-auth role (fail-closed)."""
    try:
        binding = KUBERNETES_ROLE_BINDINGS[role]
    except KeyError:
        raise ValueError(f"unknown kubernetes-auth role: {role}") from None
    return [f"{key}={binding[key]}" for key in sorted(binding)]


def configure_kubernetes_roles(kubeconfig: str, context: str, namespace: str, token: str | None = None) -> list[str]:
    """Idempotently write every role in KUBERNETES_ROLE_BINDINGS. Returns roles written."""
    written: list[str] = []
    for role in sorted(KUBERNETES_ROLE_BINDINGS):
        _vault_exec(
            kubeconfig, context, namespace,
            "write", f"auth/kubernetes/role/{role}", *build_kubernetes_role_args(role),
            token=token,
        )
        written.append(role)
    return written


def recovery_secret_ref(namespace: str) -> dict:
    return {"namespace": namespace, "name": RECOVERY_SECRET_NAME}


def resolve_admin_token_output(value: str, workspace: Path | None = None) -> Path:
    """Fail-closed resolve for --admin-token-output (study-only, gitignored-local-only).

    Only paths under ``tmp/edai2-gcp/`` are accepted. Anything outside that
    prefix, including ``evidence/`` or repo source dirs, raises ValueError.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError("admin token output must be a non-empty path")
    base = (workspace if workspace is not None else Path.cwd()).resolve()
    root = (base / "tmp" / "edai2-gcp").resolve()
    candidate = Path(value)
    candidate = candidate.resolve() if candidate.is_absolute() else (base / candidate).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        raise ValueError("admin token output must be under tmp/edai2-gcp/") from None
    for forbidden in ("evidence", "scripts", "infra", "src", "tests", "configs"):
        forbidden_root = (base / forbidden).resolve()
        try:
            candidate.relative_to(forbidden_root)
        except ValueError:
            continue
        raise ValueError(f"admin token output must not be under {forbidden}/")
    return candidate


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
    admin_policy_sha256: str | None = None,
) -> dict:
    evidence = {
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
    if admin_policy_sha256 is not None:
        evidence["admin_token"] = "gitignored-local-only"
        evidence["admin_policy_sha256"] = admin_policy_sha256
    return evidence


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


def verify_recovery(
    *,
    exec_fn,
    expected_bootstrap: dict,
    recovery_sink: str | None = None,
    attestation: dict | None = None,
) -> dict:
    """Prove KMS auto-unseal recovery with identical canary metadata.

    Status must show initialized and unsealed with no manual unseal step. Key
    names must match the bootstrap exactly (names only, values never read).
    Policy probes rerun the locked matrix with immediate token revocation.
    Study-only: recovery sink attestation is not required; when a sink and
    attestation are supplied they must bind an encrypted two-custodian sink.
    Role tokens and sink URIs never enter the returned evidence.
    """
    if not isinstance(expected_bootstrap, dict):
        raise ValueError("recovery evidence inputs are invalid")
    if recovery_sink is not None or attestation is not None:
        if not isinstance(recovery_sink, str) or not recovery_sink or not isinstance(attestation, dict):
            raise ValueError("recovery evidence inputs are invalid")
    try:
        status = json.loads(exec_fn("status", "-format=json"))
    except (RuntimeError, json.JSONDecodeError) as error:
        raise ValueError(f"vault status read failed: {error}") from error
    if status.get("initialized") is not True:
        raise ValueError("vault is not initialized after recovery")
    if status.get("sealed") is not False:
        raise ValueError("vault needs manual unseal; KMS auto-unseal failed")
    seal_type = status.get("seal_type", "")
    if not seal_type or seal_type != expected_bootstrap.get("seal_type"):
        raise ValueError("vault seal type drifted from bootstrap")
    live_keys: list[str] = []
    for path in KEY_MATRIX:
        try:
            live_keys.extend(json.loads(exec_fn("kv", "list", path)))
        except (RuntimeError, json.JSONDecodeError) as error:
            raise ValueError(f"vault key listing failed: {path}") from error
    key_names_match = sorted(live_keys) == sorted(expected_bootstrap.get("key_names", []))
    if not key_names_match:
        raise ValueError("vault key names drifted from bootstrap")
    policy_results: dict[str, bool] = {}
    for role, path, expect_allowed in PROBE_MATRIX:
        try:
            created = json.loads(exec_fn("token", "create", f"-policy={role}", "-format=json"))
            role_token = str(created["auth"]["client_token"])
        except (RuntimeError, KeyError, json.JSONDecodeError) as error:
            raise ValueError(f"vault canary token issue failed: {role}") from error
        try:
            try:
                exec_fn("kv", "get", "-format=json", path, token=role_token)
                allowed = True
            except RuntimeError:
                allowed = False
        finally:
            try:
                exec_fn("token", "revoke", role_token)
            except RuntimeError:
                pass
        label = f"{role}-{'allow' if expect_allowed else 'deny'}-{path.rsplit('/', 1)[-1]}"
        policy_results[label] = (allowed is expect_allowed)
    try:
        exec_fn("kv", "get", "-format=json", "kv/edai2/kagent/gateway-keys", token="invalid-probe-token")
        denied = False
    except RuntimeError:
        denied = True
    policy_results["cross-path-deny"] = denied
    if policy_results != {key: expected_bootstrap.get("policy_results", {}).get(key) for key in policy_results}:
        raise ValueError("vault policy canary drifted from bootstrap")
    if recovery_sink is None and attestation is None:
        return {
            "initialized": True, "seal_type": seal_type, "auto_unseal": True,
            "manual_unseal_required": False, "key_names_match": True,
            "policy_results": policy_results, "recovery_control": "not_applicable_personal_study",
        }
    assert isinstance(recovery_sink, str) and isinstance(attestation, dict)
    sink_hash = hashlib.sha256(recovery_sink.encode("utf-8")).hexdigest()
    custodians = attestation.get("custodians", [])
    if (
        attestation.get("sink_uri_sha256") != sink_hash
        or attestation.get("encrypted") is not True
        or not isinstance(custodians, list) or len(custodians) != 2 or len(set(custodians)) != 2
        or not all(isinstance(item, str) and item for item in custodians)
        or not attestation.get("attested_at")
    ):
        raise ValueError("recovery sink attestation is invalid")
    return {
        "initialized": True, "seal_type": seal_type, "auto_unseal": True,
        "manual_unseal_required": False, "key_names_match": True,
        "policy_results": policy_results, "recovery_sink_sha256": sink_hash,
        "custodians": len(custodians),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kubeconfig", required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--namespace", default="vault")
    parser.add_argument("--kms-key-id", required=False, default=None)
    parser.add_argument("--kubernetes-auth", action="store_true")
    parser.add_argument("--policies", default="infra/security/vault/policies")
    parser.add_argument("--redacted-output", required=True)
    parser.add_argument("--admin-token-output", default=None,
                        help="gitignored-local-only study admin token path (must be under tmp/edai2-gcp/)")
    parser.add_argument("--verify-recovery", action="store_true")
    parser.add_argument("--expected-bootstrap", default=None)
    parser.add_argument("--recovery-sink", default=None)
    parser.add_argument("--recovery-sink-attestation", default=None)
    args = parser.parse_args(argv)

    if args.verify_recovery:
        if args.expected_bootstrap is None:
            print("--verify-recovery requires --expected-bootstrap", file=sys.stderr)
            return 2
        if Path(args.redacted_output).exists():
            print("refusing to overwrite existing evidence", file=sys.stderr)
            return 2
        try:
            expected = json.loads(Path(args.expected_bootstrap).read_text(encoding="utf-8"))
            if args.recovery_sink_attestation is not None:
                attestation = json.loads(Path(args.recovery_sink_attestation).read_text(encoding="utf-8"))
            else:
                attestation = None
        except (OSError, json.JSONDecodeError) as error:
            print(f"recovery inputs unreadable: {error}", file=sys.stderr)
            return 2

        def _exec(*vault_args: str, token: str | None = None) -> str:
            return _vault_exec(args.kubeconfig, args.context, args.namespace, *vault_args, token=token)

        try:
            result = verify_recovery(
                exec_fn=_exec, expected_bootstrap=expected,
                recovery_sink=args.recovery_sink, attestation=attestation,
            )
        except ValueError as error:
            print(f"recovery verification failed: {error}", file=sys.stderr)
            return 1
        out_path = Path(args.redacted_output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("VAULT_RECOVERY=OK")
        return 0
    if args.kms_key_id is None:
        print("--kms-key-id is required for bootstrap", file=sys.stderr)
        return 2

    if Path(args.redacted_output).exists():
        print("refusing to overwrite existing evidence", file=sys.stderr)
        return 2
    admin_token_path: Path | None = None
    admin_policy_sha256: str | None = None
    if args.admin_token_output is not None:
        try:
            admin_token_path = resolve_admin_token_output(args.admin_token_output)
        except ValueError as exc:
            print(f"invalid --admin-token-output: {exc}", file=sys.stderr)
            return 2
        admin_policy_file = Path(args.policies) / "edai2-admin.hcl"
        try:
            admin_policy_sha256 = hashlib.sha256(admin_policy_file.read_bytes()).hexdigest()
        except OSError as exc:
            print(f"missing edai2-admin policy: {exc}", file=sys.stderr)
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
    admin_token_value = ""
    admin_accessor = ""
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
        if args.kubernetes_auth:
            configure_kubernetes_roles(args.kubeconfig, args.context, args.namespace, token=token)
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
        if admin_token_path is not None:
            admin_out = _vault_exec(args.kubeconfig, args.context, args.namespace,
                                    "token", "create", "-policy=edai2-admin",
                                    "-display-name=edai2-study-admin", "-orphan",
                                    "-format=json", token=token)
            admin_doc = json.loads(admin_out)
            admin_token_value = str(admin_doc["auth"]["client_token"])
            admin_accessor = str(admin_doc["auth"].get("accessor", ""))
            issued_at_utc = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
            token_payload = {
                "client_token": admin_token_value,
                "accessor": admin_accessor,
                "issued_at_utc": issued_at_utc,
                "policy": "edai2-admin",
            }
            assert admin_token_path is not None
            admin_token_path.parent.mkdir(parents=True, exist_ok=True)
            admin_token_path.write_text(json.dumps(token_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            os.chmod(admin_token_path, 0o600)
        _vault_exec(args.kubeconfig, args.context, args.namespace, "token", "revoke", "-self", token=token)
        root_revoked = True
    finally:
        token = "0" * 64
        recovery_key = "0" * 64
        admin_token_value = "0" * 64
        admin_accessor = "0" * 64
        del token, recovery_key, admin_token_value, admin_accessor
    evidence = build_redacted_evidence(
        kms_key_id=args.kms_key_id, seal_type=seal_type, key_names=populated,
        policy_results=policy_results, recovery_threshold=1, recovery_shares=1,
        root_revoked=root_revoked, admin_policy_sha256=admin_policy_sha256,
    )
    out_path = Path(args.redacted_output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("VAULT_BOOTSTRAP=OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
