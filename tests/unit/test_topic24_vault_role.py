"""Topic 24 Phase 0: Vault kubernetes-auth role ``external-secrets`` (local-only).

``ClusterSecretStore/edai2-vault`` authenticates with Vault kubernetes-auth
role ``external-secrets`` (serviceaccount ``external-secrets`` in namespace
``external-secrets``), but no such role or policy is defined and
``configure_vault.py`` never creates it -> store ``Ready=False
InvalidProviderConfig`` and all 15 ExternalSecrets ``SecretSyncedError``.

All tests are local-only: they read checked-in manifests and stub the Vault
wrappers. No lease is touched, no cluster is mutated, no secret values exist
anywhere in this file.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import stat
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
POLICIES_DIR = ROOT / "infra" / "security" / "vault" / "policies"
EXTERNAL_SECRETS_DIR = ROOT / "infra" / "security" / "external-secrets"
KUBERNETES_AUTH_FILE = ROOT / "infra" / "security" / "vault" / "kubernetes-auth.yaml"
CONFIGURE_VAULT_RELATIVE = "scripts/gke/configure_vault.py"

EXPECTED_ROLE = "external-secrets"
EXPECTED_SERVICE_ACCOUNT = "external-secrets"
EXPECTED_NAMESPACE = "external-secrets"


def _load_configure_vault():
    path = ROOT / CONFIGURE_VAULT_RELATIVE
    spec = importlib.util.spec_from_file_location("configure_vault", path)
    assert spec and spec.loader, f"missing module file: {CONFIGURE_VAULT_RELATIVE}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _external_secret_documents() -> list[dict]:
    """All ExternalSecret objects across the checked-in manifests."""
    documents: list[dict] = []
    for path in sorted(EXTERNAL_SECRETS_DIR.glob("*.yaml")):
        if path.name == "cluster-secret-store.yaml":
            continue
        for document in yaml.safe_load_all(path.read_text(encoding="utf-8")):
            if document and document.get("kind") == "ExternalSecret":
                documents.append(document)
    return documents


def _consumed_kv_data_paths() -> set[str]:
    """KV v2 policy paths consumed by the ExternalSecrets (derived, not hardcoded)."""
    paths: set[str] = set()
    for document in _external_secret_documents():
        for entry in document["spec"]["data"]:
            paths.add(f"kv/data/{entry['remoteRef']['key']}")
    return paths


def _policy_granted_paths(text: str) -> list[str]:
    return re.findall(r'path\s+"([^"]+)"', text)


def _policy_capabilities_blocks(text: str) -> list[str]:
    return re.findall(r"capabilities\s*=\s*(\[[^\]]*\])", text)


# --- kubernetes-auth ConfigMap ---


def test_kubernetes_auth_defines_external_secrets_role() -> None:
    auth = yaml.safe_load(KUBERNETES_AUTH_FILE.read_text(encoding="utf-8"))
    values = list(auth["data"].values())
    assert EXPECTED_ROLE in values, (
        f"role {EXPECTED_ROLE!r} missing from {KUBERNETES_AUTH_FILE.name} data: {values}"
    )


def test_kubernetes_auth_keeps_existing_five_roles() -> None:
    auth = yaml.safe_load(KUBERNETES_AUTH_FILE.read_text(encoding="utf-8"))
    values = list(auth["data"].values())
    for role in ("retrieval", "drift", "coordinator", "agentgateway", "jenkins"):
        assert role in values


# --- external-secrets policy ---


def test_external_secrets_policy_covers_exactly_consumed_kv_paths() -> None:
    documents = _external_secret_documents()
    assert len(documents) == 20, f"expected 20 ExternalSecrets, found {len(documents)}"
    expected = _consumed_kv_data_paths()
    assert len(expected) == 14, f"expected 14 unique KV paths, found {sorted(expected)}"
    policy_file = POLICIES_DIR / "external-secrets.hcl"
    assert policy_file.is_file(), "missing policy file external-secrets.hcl"
    granted = set(_policy_granted_paths(policy_file.read_text(encoding="utf-8")))
    assert granted == expected, (
        f"policy drift: missing={sorted(expected - granted)} extra={sorted(granted - expected)}"
    )


def test_external_secrets_policy_is_read_only_and_wildcard_free() -> None:
    policy_file = POLICIES_DIR / "external-secrets.hcl"
    assert policy_file.is_file(), "missing policy file external-secrets.hcl"
    text = policy_file.read_text(encoding="utf-8")
    assert "*" not in text, "policy must not use wildcards"
    for block in _policy_capabilities_blocks(text):
        assert block == '["read"]', f"policy must grant read only, found {block}"
    lowered = text.lower()
    for forbidden in ("sudo", "root", "admin", "create", "update", "delete"):
        assert forbidden not in lowered, f"policy must not contain {forbidden!r}"


def test_external_secrets_policy_denies_cross_paths() -> None:
    policy_file = POLICIES_DIR / "external-secrets.hcl"
    assert policy_file.is_file(), "missing policy file external-secrets.hcl"
    granted = set(_policy_granted_paths(policy_file.read_text(encoding="utf-8")))
    for probe in (
        "kv/data/edai2/kagent/other-keys",
        "kv/data/edai2/platform/other",
        "kv/edai2/kagent/gateway-keys",  # v1-style prefix must not appear
        "sys/policy",
        "auth/kubernetes/role",
        "database/creds/edai2-retrieval",
    ):
        assert probe not in granted, f"policy must not grant {probe!r}"


# --- configure_vault.py role creation (stubbed, no cluster) ---


def test_configure_vault_builds_external_secrets_role_args() -> None:
    module = _load_configure_vault()
    args = module.build_kubernetes_role_args(EXPECTED_ROLE)
    joined = " ".join(args)
    assert f"bound_service_account_names={EXPECTED_SERVICE_ACCOUNT}" in joined
    assert f"bound_service_account_namespaces={EXPECTED_NAMESPACE}" in joined
    assert f"token_policies={EXPECTED_ROLE}" in joined
    assert "*" not in joined


def test_configure_vault_writes_role_idempotently_with_stubs(monkeypatch) -> None:
    module = _load_configure_vault()
    calls: list[tuple[str, ...]] = []

    def fake_vault_exec(kubeconfig: str, context: str, namespace: str, *vault_args: str, token=None) -> str:
        calls.append(tuple(vault_args))
        return ""

    monkeypatch.setattr(module, "_vault_exec", fake_vault_exec)
    first = module.configure_kubernetes_roles("kubeconfig", "ctx", "vault", token="t")
    second = module.configure_kubernetes_roles("kubeconfig", "ctx", "vault", token="t")
    assert EXPECTED_ROLE in first
    assert first == second, "role creation must be repeatable"
    role_writes = [call for call in calls if call[:2] == ("write", f"auth/kubernetes/role/{EXPECTED_ROLE}")]
    assert len(role_writes) == 2, f"expected one idempotent role write per call, got {calls}"
    assert any(f"token_policies={EXPECTED_ROLE}" in call for call in role_writes)


def test_configure_vault_rejects_unknown_role() -> None:
    module = _load_configure_vault()
    try:
        module.build_kubernetes_role_args("no-such-role")
    except (KeyError, ValueError):
        return
    raise AssertionError("unknown role must fail closed")


def test_configure_vault_main_wires_role_creation() -> None:
    text = (ROOT / CONFIGURE_VAULT_RELATIVE).read_text(encoding="utf-8")
    assert "configure_kubernetes_roles" in text
    main_body = text.split("def main", 1)[1]
    assert "configure_kubernetes_roles" in main_body, "main() must invoke role creation"


# --- edai2-admin study-only policy (local-only, gitignored token path) ---

ADMIN_POLICY_FILE = POLICIES_DIR / "edai2-admin.hcl"
EXPECTED_ADMIN_TEXT = (
    'path "*" { capabilities = ["create","read","update","delete","list","sudo"] }\n'
    'path "sys/generate-root/*" { capabilities = ["deny"] }\n'
    'path "sys/rekey/*" { capabilities = ["deny"] }\n'
    'path "sys/seal" { capabilities = ["deny"] }\n'
)


def test_edai2_admin_policy_is_exact_study_only_grant() -> None:
    assert ADMIN_POLICY_FILE.is_file(), "missing policy file edai2-admin.hcl"
    text = ADMIN_POLICY_FILE.read_text(encoding="utf-8")
    assert text == EXPECTED_ADMIN_TEXT, f"edai2-admin.hcl must match spec exactly, got:\n{text!r}"


def test_edai2_admin_policy_has_exactly_three_deny_paths() -> None:
    assert ADMIN_POLICY_FILE.is_file(), "missing policy file edai2-admin.hcl"
    text = ADMIN_POLICY_FILE.read_text(encoding="utf-8")
    denies = re.findall(r'path\s+"([^"]+)"\s*\{\s*capabilities\s*=\s*\["deny"\]', text)
    assert sorted(denies) == ["sys/generate-root/*", "sys/rekey/*", "sys/seal"], (
        f"expected exactly the three spec deny paths, got {denies}"
    )
    assert 'capabilities = ["create","read","update","delete","list","sudo"]' in text


def test_configure_vault_accepts_admin_token_output_flag() -> None:
    text = (ROOT / CONFIGURE_VAULT_RELATIVE).read_text(encoding="utf-8")
    assert "--admin-token-output" in text, "main() must accept --admin-token-output"
    main_body = text.split("def main", 1)[1]
    assert "admin_token_output" in main_body


def test_configure_vault_refuses_admin_token_output_outside_tmp(tmp_path: Path) -> None:
    module = _load_configure_vault()
    assert hasattr(module, "resolve_admin_token_output"), "missing resolve_admin_token_output helper"
    workspace = tmp_path / "ws"
    (workspace / "tmp" / "edai2-gcp").mkdir(parents=True)
    for bad in (
        "/tmp/evil-admin.json",
        "tmp/other/admin-token.json",
        "admin-token.json",
        "tmp/edai2-gcp/../other/escape.json",
        "../escape.json",
        "",
    ):
        with pytest.raises(ValueError):
            module.resolve_admin_token_output(bad, workspace=workspace)
    good = module.resolve_admin_token_output("tmp/edai2-gcp/admin-token.json", workspace=workspace)
    assert good == (workspace / "tmp" / "edai2-gcp" / "admin-token.json").resolve()


def test_configure_vault_refuses_evidence_and_source_dirs(tmp_path: Path) -> None:
    module = _load_configure_vault()
    assert hasattr(module, "resolve_admin_token_output"), "missing resolve_admin_token_output helper"
    workspace = tmp_path / "ws"
    (workspace / "tmp" / "edai2-gcp").mkdir(parents=True)
    for source_dir in ("evidence", "scripts", "infra", "src", "tests", "configs"):
        (workspace / source_dir).mkdir(parents=True, exist_ok=True)
    for bad in (
        "evidence/admin-token.json",
        "evidence/04_2_llm_design/admin-token.json",
        "scripts/admin-token.json",
        "infra/admin-token.json",
        "src/admin-token.json",
        "tests/admin-token.json",
        "configs/admin-token.json",
        "tmp/edai2-gcp/../../evidence/sneaky.json",
        "tmp/edai2-gcp/../../scripts/sneaky.json",
    ):
        with pytest.raises(ValueError):
            module.resolve_admin_token_output(bad, workspace=workspace)


def test_configure_vault_policy_loop_auto_uploads_admin() -> None:
    text = (ROOT / CONFIGURE_VAULT_RELATIVE).read_text(encoding="utf-8")
    main_body = text.split("def main", 1)[1]
    assert 'glob("*.hcl")' in main_body, "policy upload loop must glob *.hcl so edai2-admin.hcl auto-uploads"
    assert '"policy", "write"' in main_body or "'policy', 'write'" in main_body or '"policy"' in main_body


def test_build_redacted_evidence_carries_admin_marker_without_token_material() -> None:
    module = _load_configure_vault()
    digest = "a" * 64
    evidence = module.build_redacted_evidence(
        kms_key_id="projects/p/locations/r/keyRings/k/cryptoKeys/c",
        seal_type="gcpckms",
        key_names=["model-api-key"],
        policy_results={"ok": True},
        recovery_threshold=1,
        recovery_shares=1,
        root_revoked=True,
        admin_policy_sha256=digest,
    )
    assert evidence["admin_token"] == "gitignored-local-only"
    assert evidence["admin_policy_sha256"] == digest
    assert evidence["root_revoked"] is True
    # Never token material: marker value must not look like a token, and no client_token key.
    assert "client_token" not in evidence
    assert "s." not in json.dumps(evidence)
    assert len(evidence["admin_policy_sha256"]) == 64


def _stub_vault_main(monkeypatch, tmp_path: Path, *, policies_dir: Path, token_rel: str, redacted: Path):
    """Stub kubectl/vault/subprocess for a full local main() run. Returns (module, calls, stdout-cap)."""
    module = _load_configure_vault()
    calls: list[tuple[str, ...]] = []
    probe_count = {"n": 0}
    fake_admin_token = "s.FAKEADMINTOKEN999"
    fake_accessor = "accessor-fake-123"

    class _Proc:
        def __init__(self, *, returncode=0, stdout="", stderr=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_vault_exec(kubeconfig: str, context: str, namespace: str, *vault_args: str, token=None) -> str:
        calls.append(tuple(vault_args))
        joined = " ".join(vault_args)
        if vault_args[:2] == ("status", "-format=json"):
            return json.dumps({"seal_type": "gcpckms", "initialized": True, "sealed": False})
        if vault_args[:2] == ("token", "create") and "-policy=edai2-admin" in vault_args:
            assert "-display-name=edai2-study-admin" in vault_args, f"missing display name: {vault_args}"
            assert "-orphan" in vault_args, f"study token must be orphan: {vault_args}"
            assert "-format=json" in vault_args
            return json.dumps({"auth": {"client_token": fake_admin_token, "accessor": fake_accessor}})
        if vault_args[:2] == ("token", "create"):
            return json.dumps({"auth": {"client_token": "s.probe-token"}})
        if vault_args[:3] == ("token", "revoke", "-self"):
            return ""
        if vault_args[:2] == ("token", "revoke"):
            return ""
        return ""

    def fake_kubectl(kubeconfig: str, context: str, *args: str, token=None) -> _Proc:
        arg_list = list(args)
        if "get" in arg_list and "secret" in arg_list:
            return _Proc(returncode=0, stdout="", stderr="")
        if "operator" in arg_list and "init" in arg_list:
            return _Proc(
                returncode=0,
                stdout=json.dumps({"root_token": "s.ROOTTOKEN", "recovery_keys_b64": ["UkVDT1ZFUllLRVk="]}),
            )
        if "cp" in arg_list:
            return _Proc(returncode=0, stdout="ok")
        if "kv" in arg_list and "get" in arg_list:
            if token == "invalid-probe-token":
                return _Proc(returncode=1, stdout="", stderr="permission denied")
            if token == "s.probe-token":
                probe_count["n"] += 1
                # First two PROBE_MATRIX rows expect allow=True, next two expect allow=False.
                if probe_count["n"] <= 2:
                    return _Proc(returncode=0, stdout="{}")
                return _Proc(returncode=1, stdout="", stderr="permission denied")
            return _Proc(returncode=1, stdout="", stderr="denied")
        return _Proc(returncode=0, stdout="", stderr="")

    def fake_subprocess_run(argv, **kwargs) -> _Proc:
        return _Proc(returncode=0, stdout="created", stderr="")

    monkeypatch.setattr(module, "_vault_exec", fake_vault_exec)
    monkeypatch.setattr(module, "_kubectl", fake_kubectl)
    monkeypatch.setattr(module.subprocess, "run", fake_subprocess_run)
    return module, calls, fake_admin_token, fake_accessor


def test_configure_vault_admin_token_file_0600_without_leak(tmp_path: Path, monkeypatch, capsys) -> None:
    import sys as _sys  # noqa: PLC0415

    monkeypatch.chdir(tmp_path)
    policies_dir = tmp_path / "policies"
    policies_dir.mkdir()
    (policies_dir / "dummy.hcl").write_text('path "kv/data/x" { capabilities = ["read"] }\n', encoding="utf-8")
    (policies_dir / "edai2-admin.hcl").write_text(EXPECTED_ADMIN_TEXT, encoding="utf-8")
    redacted = tmp_path / "out" / "evidence.json"
    token_rel = "tmp/edai2-gcp/admin-token.json"

    chmod_seen: list[tuple[object, int]] = []
    real_chmod = os.chmod

    def spy_chmod(path, mode):
        chmod_seen.append((path, mode))
        return real_chmod(path, mode)

    monkeypatch.setattr(os, "chmod", spy_chmod)

    module, calls, fake_admin_token, fake_accessor = _stub_vault_main(
        monkeypatch, tmp_path, policies_dir=policies_dir, token_rel=token_rel, redacted=redacted
    )
    rc = module.main([
        "--kubeconfig", "kc", "--context", "ctx", "--namespace", "vault",
        "--kms-key-id", "projects/p/locations/r/keyRings/k/cryptoKeys/c",
        "--kubernetes-auth",
        "--policies", str(policies_dir),
        "--redacted-output", str(redacted),
        "--admin-token-output", token_rel,
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert fake_admin_token not in out, "token value must never appear on stdout"

    token_path = tmp_path / token_rel
    assert token_path.is_file(), "admin token file must be written under tmp/edai2-gcp/"
    payload = json.loads(token_path.read_text(encoding="utf-8"))
    assert set(payload) == {"client_token", "accessor", "issued_at_utc", "policy"}
    assert payload["client_token"] == fake_admin_token
    assert payload["accessor"] == fake_accessor
    assert payload["policy"] == "edai2-admin"
    assert "T" in payload["issued_at_utc"]

    assert any(mode == 0o600 for _, mode in chmod_seen), f"file must be chmod 0600, got {chmod_seen}"
    if _sys.platform != "win32":
        assert stat.S_IMODE(os.stat(token_path).st_mode) == 0o600

    evidence = json.loads(redacted.read_text(encoding="utf-8"))
    assert evidence["admin_token"] == "gitignored-local-only"
    assert evidence["admin_policy_sha256"] == __import__("hashlib").sha256(
        (policies_dir / "edai2-admin.hcl").read_bytes()
    ).hexdigest()
    assert fake_admin_token not in json.dumps(evidence), "token value must never appear in evidence"
    assert evidence["root_revoked"] is True


def test_configure_vault_root_revoked_after_admin_token_with_scrub_ordering(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    policies_dir = tmp_path / "policies"
    policies_dir.mkdir()
    (policies_dir / "edai2-admin.hcl").write_text(EXPECTED_ADMIN_TEXT, encoding="utf-8")
    redacted = tmp_path / "out" / "evidence.json"
    token_rel = "tmp/edai2-gcp/admin-token.json"

    module, calls, fake_admin_token, _ = _stub_vault_main(
        monkeypatch, tmp_path, policies_dir=policies_dir, token_rel=token_rel, redacted=redacted
    )
    rc = module.main([
        "--kubeconfig", "kc", "--context", "ctx", "--namespace", "vault",
        "--kms-key-id", "projects/p/locations/r/keyRings/k/cryptoKeys/c",
        "--policies", str(policies_dir),
        "--redacted-output", str(redacted),
        "--admin-token-output", token_rel,
    ])
    assert rc == 0
    capsys.readouterr()

    create_idx = next(
        i for i, call in enumerate(calls)
        if call[:2] == ("token", "create") and "-policy=edai2-admin" in call
    )
    revoke_self_idx = next(i for i, call in enumerate(calls) if call == ("token", "revoke", "-self"))
    assert create_idx < revoke_self_idx, f"admin token must be created BEFORE revoke -self: {calls}"
    assert any(call == ("token", "revoke", "-self") for call in calls), "root must still be revoked"

    text = (ROOT / CONFIGURE_VAULT_RELATIVE).read_text(encoding="utf-8")
    main_body = text.split("def main", 1)[1]
    revoke_pos = main_body.find('"revoke", "-self"')
    if revoke_pos == -1:
        revoke_pos = main_body.find("'revoke', '-self'")
    assert revoke_pos != -1
    tail = main_body[revoke_pos:]
    assert '"0" * 64' in tail or "'0' * 64" in tail or '"0"*64' in tail, "memory must be scrubbed after revoke"
    assert "del " in tail, "token material must be deleted after scrub"


def _load_capture_evidence():
    path = ROOT / "scripts" / "qa" / "capture_edai2_evidence.py"
    spec = importlib.util.spec_from_file_location("capture_edai2_evidence", path)
    assert spec and spec.loader, "missing module file: scripts/qa/capture_edai2_evidence.py"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _minimal_bootstrap_payload(**extra: object) -> dict:
    return {
        "initialized": True,
        "seal_type": "gcpckms",
        "key_names": ["admin-user"],
        "policy_results": {"probe": True},
        "root_revoked": True,
        **extra,
    }


def test_verify_vault_bootstrap_accepts_gitignored_admin_marker() -> None:
    module = _load_capture_evidence()
    module.verify_vault_bootstrap(_minimal_bootstrap_payload(
        admin_token="gitignored-local-only",
        admin_policy_sha256="61d119119364056da5ec88b19b65c5cee956010596305776627c332d93545806",
    ))


def test_verify_vault_bootstrap_rejects_real_admin_token_value() -> None:
    module = _load_capture_evidence()
    with pytest.raises(ValueError, match="secret material"):
        module.verify_vault_bootstrap(_minimal_bootstrap_payload(admin_token="s.real-admin-token"))


def test_verify_vault_bootstrap_rejects_bad_admin_policy_sha() -> None:
    module = _load_capture_evidence()
    with pytest.raises(ValueError, match="secret material"):
        module.verify_vault_bootstrap(_minimal_bootstrap_payload(admin_policy_sha256="not-a-hash"))
