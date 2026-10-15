"""Narrow, local-only bootstrap for the existing Kagent Vault policy and role."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[2]
KAGENT_POLICY_PATH = Path("infra/security/vault/policies/kagent.hcl")
KAGENT_POLICY_TEXT = (ROOT / KAGENT_POLICY_PATH).read_text(encoding="utf-8")
EXPECTED_ROLE = {
    "bound_service_account_names": ["kagent-controller"],
    "bound_service_account_namespaces": ["kagent"],
    "token_policies": ["kagent"],
    "token_ttl": 3600,
    "token_max_ttl": 3600,
}
SHELL = "IFS= read -r VAULT_TOKEN; export VAULT_TOKEN; exec vault \"$@\""
Runner = Callable[..., subprocess.CompletedProcess]


def _validate_target(kubeconfig: str, context: str, namespace: str) -> None:
    if (not Path(kubeconfig).is_absolute() or context != "edai2-gke" or namespace != "vault"):
        raise ValueError("bootstrap requires the approved GKE target: absolute kubeconfig, context edai2-gke, namespace vault")


def _select_vault_pod(kubeconfig: str, context: str, namespace: str, runner: Runner) -> str:
    _validate_target(kubeconfig, context, namespace)
    command = ["kubectl", "--kubeconfig", kubeconfig, "--context", context,
               "-n", namespace, "get", "pod", "vault-0", "-o", "json"]
    proc = runner(command, input=b"", capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"Vault pod selection failed (exit code {proc.returncode})")
    output = proc.stdout.decode(errors="replace") if isinstance(proc.stdout, bytes) else str(proc.stdout or "")
    try:
        pod = json.loads(output)
    except json.JSONDecodeError as error:
        raise RuntimeError("Vault pod selection returned malformed metadata") from error
    metadata, spec, status = pod.get("metadata", {}), pod.get("spec", {}), pod.get("status", {})
    labels = metadata.get("labels", {})
    containers = spec.get("containers", [])
    statuses = status.get("containerStatuses", [])
    uid = metadata.get("uid")
    selected = any(item.get("name") == "vault" and item.get("ready") is True for item in statuses if isinstance(item, dict))
    if (metadata.get("name") != "vault-0" or metadata.get("namespace") != namespace or not isinstance(uid, str) or not uid
            or labels.get("app.kubernetes.io/instance") != "vault" or labels.get("app.kubernetes.io/name") != "vault"
            or labels.get("component") != "server" or not any(item.get("name") == "vault" for item in containers)
            or status.get("phase") != "Running" or not selected):
        raise RuntimeError("Vault pod selection did not identify one ready Vault server container")
    return uid


def _vault_command(kubeconfig: str, context: str, namespace: str, token: str,
                   *vault_args: str, input_text: str = "", pod_uid: str,
                   runner: Runner = subprocess.run) -> str:
    _validate_target(kubeconfig, context, namespace)
    if not token or "\n" in token or "\r" in token:
        raise ValueError("Vault token must be supplied as one non-empty stdin line")
    mutation = vault_args[:2] == ("policy", "write") or vault_args[0] == "write"
    if mutation and _select_vault_pod(kubeconfig, context, namespace, runner) != pod_uid:
        raise RuntimeError("Vault pod changed before the requested mutation")
    command = [
        "kubectl", "--kubeconfig", kubeconfig, "--context", context,
        "-n", namespace, "exec", "-i", "vault-0", "-c", "vault", "--", "sh", "-c", SHELL, "sh", *vault_args,
    ]
    proc = runner(command, input=f"{token}\n{input_text}".encode(), capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"Vault command {vault_args[0]} failed (exit code {proc.returncode})")
    output = proc.stdout.decode(errors="replace") if isinstance(proc.stdout, bytes) else str(proc.stdout or "")
    return output


def _read_role(data: dict) -> dict:
    raw = data.get("data")
    if not isinstance(raw, dict):
        raise RuntimeError("existing kagent role response is malformed")
    role = dict(raw)
    if "token_policies" in role and "policies" in role:
        if _names(role["token_policies"]) != _names(role["policies"]):
            raise RuntimeError("existing kagent role differs from the approved binding")
    policies = role.get("token_policies", role.get("policies"))
    if (_names(role.get("bound_service_account_names")) != EXPECTED_ROLE["bound_service_account_names"]
            or _names(role.get("bound_service_account_namespaces")) != EXPECTED_ROLE["bound_service_account_namespaces"]
            or _names(policies) != EXPECTED_ROLE["token_policies"]
            or role.get("token_ttl") != EXPECTED_ROLE["token_ttl"]
            or role.get("token_max_ttl") != EXPECTED_ROLE["token_max_ttl"]
            or role.get("audience", "") not in ("", None)
            or role.get("bound_service_account_namespace_selector", "") not in ("", None)):
        raise RuntimeError("existing kagent role differs from the approved binding")
    return role


def _names(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    return []


def bootstrap_kagent_vault(kubeconfig: str, context: str, namespace: str, token: str,
                           *, runner: Runner = subprocess.run) -> list[str]:
    """Create only missing kagent policy/role; reject any existing mismatch."""
    _validate_target(kubeconfig, context, namespace)
    pod_uid = _select_vault_pod(kubeconfig, context, namespace, runner)
    policy_names = json.loads(_vault_command(
        kubeconfig, context, namespace, token, "policy", "list", "-format=json", pod_uid=pod_uid, runner=runner,
    ))
    role_listing = json.loads(_vault_command(
        kubeconfig, context, namespace, token, "list", "-format=json", "auth/kubernetes/role", pod_uid=pod_uid, runner=runner,
    ))
    if not isinstance(policy_names, list) or not isinstance(role_listing, (dict, list)):
        raise RuntimeError("Vault policy or Kubernetes role inventory is malformed")
    role_keys = role_listing if isinstance(role_listing, list) else role_listing.get("data", {}).get("keys")
    if not isinstance(role_keys, list) or not all(isinstance(key, str) for key in role_keys):
        raise RuntimeError("Vault Kubernetes role inventory is malformed")

    if "kagent" in policy_names:
        existing_policy = _vault_command(
            kubeconfig, context, namespace, token, "policy", "read", "kagent", pod_uid=pod_uid, runner=runner,
        )
        if existing_policy.rstrip("\n") != KAGENT_POLICY_TEXT.rstrip("\n"):
            raise RuntimeError("existing kagent policy differs from the checked-in policy")

    if "kagent" in role_keys:
        existing_role = json.loads(_vault_command(
            kubeconfig, context, namespace, token, "read", "-format=json", "auth/kubernetes/role/kagent", pod_uid=pod_uid, runner=runner,
        ))
        _read_role(existing_role)

    written: list[str] = []
    if "kagent" not in policy_names:
        _vault_command(
            kubeconfig, context, namespace, token,
            "policy", "write", "kagent", "-", input_text=KAGENT_POLICY_TEXT, pod_uid=pod_uid, runner=runner,
        )
        written.append("kagent-policy")
    if "kagent" not in role_keys:
        _vault_command(
            kubeconfig, context, namespace, token,
            "write", "auth/kubernetes/role/kagent",
            "bound_service_account_names=kagent-controller",
            "bound_service_account_namespaces=kagent",
            "token_policies=kagent",
            "token_ttl=3600", "token_max_ttl=3600", pod_uid=pod_uid, runner=runner,
        )
        written.append("kagent-role")
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kubeconfig", required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--namespace", default="vault")
    args = parser.parse_args(argv)
    token = sys.stdin.readline().rstrip("\r\n")
    try:
        written = bootstrap_kagent_vault(args.kubeconfig, args.context, args.namespace, token)
    except (ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print("Kagent Vault bootstrap verified; created: " + (", ".join(written) if written else "none"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
