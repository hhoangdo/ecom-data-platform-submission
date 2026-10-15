from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/gke/bootstrap_kagent_vault.py"
POLICY = ROOT / "infra/security/vault/policies/kagent.hcl"


def _load_module():
    spec = importlib.util.spec_from_file_location("bootstrap_kagent_vault", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VaultStub:
    def __init__(self, *, policy: str | None = None, role: dict | None = None):
        self.policy = policy
        self.role = role
        self.calls: list[tuple[list[str], bytes]] = []
        self.pod_uid = "vault-pod-uid"

    def __call__(self, command: list[str], *, input: bytes, capture_output: bool, check: bool) -> subprocess.CompletedProcess:
        self.calls.append((command, input))
        if "get" in command and "pod" in command:
            pod = {
                "metadata": {"name": "vault-0", "namespace": "vault", "uid": self.pod_uid,
                             "labels": {"app.kubernetes.io/instance": "vault", "app.kubernetes.io/name": "vault", "component": "server"}},
                "spec": {"containers": [{"name": "vault"}]},
                "status": {"phase": "Running", "containerStatuses": [{"name": "vault", "ready": True}]},
            }
            return subprocess.CompletedProcess(command, 0, json.dumps(pod), "")
        shell_index = command.index("IFS= read -r VAULT_TOKEN; export VAULT_TOKEN; exec vault \"$@\"")
        vault_command = command[shell_index + 2:]
        if vault_command[:2] == ["policy", "list"]:
            return subprocess.CompletedProcess(command, 0, json.dumps(["default", *(["kagent"] if self.policy is not None else [])]), "")
        if vault_command[:2] == ["list", "-format=json"]:
            return subprocess.CompletedProcess(command, 0, json.dumps({"data": {"keys": ["kagent"] if self.role is not None else []}}), "")
        if vault_command[:2] == ["policy", "read"]:
            return subprocess.CompletedProcess(command, 0, self.policy or "", "")
        if vault_command[:2] == ["read", "-format=json"]:
            return subprocess.CompletedProcess(command, 0, json.dumps({"data": self.role}), "")
        if vault_command[:2] == ["policy", "write"]:
            self.policy = input.split(b"\n", 1)[1].decode()
            return subprocess.CompletedProcess(command, 0, "Success! Uploaded policy: kagent\n", "")
        if vault_command[0] == "write":
            self.role = {
                "bound_service_account_names": ["kagent-controller"],
                "bound_service_account_namespaces": ["kagent"],
                "token_policies": ["kagent"],
                "token_ttl": 3600,
                "token_max_ttl": 3600,
                "audience": "",
            }
            return subprocess.CompletedProcess(command, 0, "Success! Data written to: auth/kubernetes/role/kagent\n", "")
        raise AssertionError(vault_command)


def _expected_role() -> dict:
    return {
        "bound_service_account_names": ["kagent-controller"],
        "bound_service_account_namespaces": ["kagent"],
        "token_policies": ["kagent"],
        "token_ttl": 3600,
        "token_max_ttl": 3600,
        "audience": "",
    }


@pytest.mark.parametrize("existing", [False, True])
def test_bootstrap_accepts_actual_vault_cli_role_key_list(existing: bool) -> None:
    module = _load_module()

    class CliListStub(VaultStub):
        def __call__(self, command, **kwargs):
            result = super().__call__(command, **kwargs)
            if "auth/kubernetes/role" in command and "list" in command:
                keys = json.loads(result.stdout)["data"]["keys"]
                return subprocess.CompletedProcess(command, 0, json.dumps(keys), "")
            return result

    stub = CliListStub(policy=module.KAGENT_POLICY_TEXT if existing else None,
                       role=_expected_role() if existing else None)
    result = module.bootstrap_kagent_vault(str(ROOT / "tmp/kubeconfig"), "edai2-gke", "vault", "temporary-token", runner=stub)
    assert result == ([] if existing else ["kagent-policy", "kagent-role"])


def test_bootstrap_writes_only_missing_kagent_policy_and_role() -> None:
    module = _load_module()
    stub = VaultStub()

    result = module.bootstrap_kagent_vault(str(ROOT / "tmp" / "kubeconfig"), "edai2-gke", "vault", "temporary-token", runner=stub)

    shell_marker = "IFS= read -r VAULT_TOKEN; export VAULT_TOKEN; exec vault \"$@\""
    writes = [command[command.index(shell_marker) + 2:] for command, _ in stub.calls
              if shell_marker in command and "write" in command[command.index(shell_marker) + 2:]]
    assert result == ["kagent-policy", "kagent-role"]
    assert [call[:2] for call in writes] == [["policy", "write"], ["write", "auth/kubernetes/role/kagent"]]
    assert "audience" not in " ".join(writes[-1])
    assert stub.role == _expected_role()
    assert any("--context" in command and "edai2-gke" in command for command, _ in stub.calls)
    assert all(command[command.index("-c") + 1] == "vault" for command, _ in stub.calls if "exec" in command)
    role_write = next(command for command, _ in stub.calls if "write" in command and "auth/kubernetes/role/kagent" in command)
    role_args = role_write[role_write.index("IFS= read -r VAULT_TOKEN; export VAULT_TOKEN; exec vault \"$@\"") + 2:]
    assert "token_ttl=3600" in role_args and "token_max_ttl=3600" in role_args


def test_bootstrap_blocks_instead_of_overwriting_different_policy() -> None:
    module = _load_module()
    stub = VaultStub(policy='path "kv/data/*" { capabilities = ["read"] }\n')

    with pytest.raises(RuntimeError, match="existing kagent policy differs"):
        module.bootstrap_kagent_vault(str(ROOT / "tmp" / "kubeconfig"), "edai2-gke", "vault", "token", runner=stub)

    assert not any("write" in command[command.index("IFS= read -r VAULT_TOKEN; export VAULT_TOKEN; exec vault \"$@\"") + 2:]
                   for command, _ in stub.calls if "exec" in command)


def test_bootstrap_blocks_role_with_different_binding_or_audience() -> None:
    module = _load_module()
    stub = VaultStub(policy=POLICY.read_text(encoding="utf-8"), role={
        **_expected_role(), "bound_service_account_names": ["*"], "audience": "invented-audience",
    })

    with pytest.raises(RuntimeError, match="existing kagent role differs"):
        module.bootstrap_kagent_vault(str(ROOT / "tmp" / "kubeconfig"), "edai2-gke", "vault", "token", runner=stub)

    assert not any("write" in command[command.index("IFS= read -r VAULT_TOKEN; export VAULT_TOKEN; exec vault \"$@\"") + 2:]
                       for command, _ in stub.calls if "exec" in command)


def test_vault_token_is_sent_only_over_stdin() -> None:
    module = _load_module()
    stub = VaultStub()

    module.bootstrap_kagent_vault(str(ROOT / "tmp" / "kubeconfig"), "edai2-gke", "vault", "secret-token-value", runner=stub)

    assert all("secret-token-value" not in " ".join(command) for command, _ in stub.calls)
    assert all(input.startswith(b"secret-token-value\n") for command, input in stub.calls if "exec" in command)
    assert all(input == b"" for command, input in stub.calls if "get" in command)
    assert "secret-token-value" not in SCRIPT.read_text(encoding="utf-8")
    assert all("DO_NOT_ECHO" not in str(command) for command, _ in stub.calls)


@pytest.mark.parametrize("kwargs", [
    {"context": "default"},
    {"kubeconfig": "relative-kubeconfig"},
    {"namespace": "other"},
])
def test_bootstrap_rejects_wrong_scope_before_any_command(kwargs: dict) -> None:
    module = _load_module()
    stub = VaultStub()
    args = {"kubeconfig": str(ROOT / "tmp" / "kubeconfig"), "context": "edai2-gke", "namespace": "vault"}
    args.update(kwargs)

    with pytest.raises(ValueError, match="approved GKE target"):
        module.bootstrap_kagent_vault(args["kubeconfig"], args["context"], args["namespace"], "token", runner=stub)

    assert not stub.calls


def test_bootstrap_blocks_role_with_unbounded_or_different_ttl() -> None:
    module = _load_module()
    stub = VaultStub(policy=POLICY.read_text(encoding="utf-8"), role={**_expected_role(), "token_max_ttl": 0})

    with pytest.raises(RuntimeError, match="existing kagent role differs"):
        module.bootstrap_kagent_vault(str(ROOT / "tmp" / "kubeconfig"), "edai2-gke", "vault", "token", runner=stub)

    assert not any("write" in command for command, _ in stub.calls)


def test_bootstrap_rechecks_selected_pod_uid_before_mutation() -> None:
    module = _load_module()
    stub = VaultStub()
    changed = False

    def changing_runner(command: list[str], *, input: bytes, capture_output: bool, check: bool) -> subprocess.CompletedProcess:
        nonlocal changed
        if "get" in command and "pod" in command:
            if changed:
                stub.pod_uid = "replacement-vault-uid"
            else:
                changed = True
        return stub(command, input=input, capture_output=capture_output, check=check)

    with pytest.raises(RuntimeError, match="Vault pod changed"):
        module.bootstrap_kagent_vault(str(ROOT / "tmp" / "kubeconfig"), "edai2-gke", "vault", "token", runner=changing_runner)

    assert not any("write" in command for command, _ in stub.calls)


def test_vault_errors_do_not_reflect_raw_stderr() -> None:
    module = _load_module()
    command = ["kubectl", "--kubeconfig", str(ROOT / "tmp" / "kubeconfig"), "--context", "edai2-gke", "-n", "vault", "exec"]

    def failing_runner(command: list[str], *, input: bytes, capture_output: bool, check: bool) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(command, 1, b"", b"Authorization: secret-token-value")

    with pytest.raises(RuntimeError) as error:
        module._vault_command(str(ROOT / "tmp" / "kubeconfig"), "edai2-gke", "vault", "secret-token-value",
                             "policy", "list", pod_uid="vault-pod-uid", runner=failing_runner)

    assert "secret-token-value" not in str(error.value)
    assert "Authorization" not in str(error.value)


def test_bootstrap_uses_the_checked_in_exact_policy() -> None:
    module = _load_module()
    assert module.KAGENT_POLICY_PATH == Path("infra/security/vault/policies/kagent.hcl")
    assert module.KAGENT_POLICY_TEXT == POLICY.read_text(encoding="utf-8")
