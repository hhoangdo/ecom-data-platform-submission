"""Topic 24 DEFECT 1: OpenSearch admin password must come from a secret ref.

Failing OpenSearch release: `opensearch/opensearch --version 2.38.0` installed
with infra/helm/edai2/values/opensearch.yaml; pod CrashLoopBackOff log::

    No custom admin password found. Please provide OPENSEARCH_INITIAL_ADMIN_PASSWORD

(2026-10-09 re-pin: chart 3.9.0 -> 2.38.0, app 2.19.6 -- DataHub 1.1.6
version-detects `OpenSearch expected 2.x`. The `extraEnvs`
OPENSEARCH_INITIAL_ADMIN_PASSWORD mechanism is unchanged on the 2.x line:
required since chart 2.18.0 / app 2.12.0 per the chart values comment, and
2.38.0 > 2.18.0. No `securityConfig.adminCredentialsSecret`-style key
exists in the 2.x chart schema -- `helm show values
opensearch/opensearch --version 2.38.0` carries only `extraEnvs` for this.)

Root cause: values/opensearch.yaml sets no `extraEnvs` entry, so the
StatefulSet renders no `OPENSEARCH_INITIAL_ADMIN_PASSWORD` env and the
   opensearchproject/opensearch:2.19.6 entrypoint refuses to bootstrap the demo
admin user (chart values comment confirms: "Chart version 2.18.0 and App
Version OpenSearch 2.12.0 onwards a custom strong password needs to be
provided ... Cluster will not spin-up without this").

Fix contract (TDD RED first):
- values/opensearch.yaml must wire `extraEnvs: [{name:
  OPENSEARCH_INITIAL_ADMIN_PASSWORD, valueFrom: {secretKeyRef: {name:
  opensearch, key: password}}}]` (chart renders `extraEnvs` verbatim into
  container `env:`, so any valid k8s EnvVar schema works; `valueFrom` keeps
  the literal out of git).
- Secret/key choice follows the in-repo remap convention (postgres:
  `auth.secretKeys.adminPasswordKey=password` on secret `postgres`;
  clickhouse: `auth.existingSecretKey=password` on secret `clickhouse`;
  valkey: `auth.existingSecretPasswordKey=password` on secret `valkey`):
  secret name == component (`opensearch`), key `password`.
- Sync (DEFECT 2): `infra/security/external-secrets/opensearch.yaml`
  (ExternalSecret) syncs Vault `kv/edai2/platform/opensearch`
  (keys `username`, `password` — clickhouse platform-store convention; the
  chart strictly needs only `password` today) -> target secret `opensearch`.
  `scripts/gke/configure_vault.py` KEY_MATRIX carries the same path so the
  bootstrap populates it, and the cross-file test below pins values
  secretKeyRef == manifest target/secretKey.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
VALUES_FILE = ROOT / "infra/helm/edai2/values/opensearch.yaml"
MANIFEST_FILE = ROOT / "infra" / "security" / "external-secrets" / "opensearch.yaml"
CONFIGURE_VAULT_FILE = ROOT / "scripts" / "gke" / "configure_vault.py"

SECRET_NAME = "opensearch"
SECRET_KEY = "password"
ENV_NAME = "OPENSEARCH_INITIAL_ADMIN_PASSWORD"

KV_PATH = "kv/edai2/platform/opensearch"
REMOTE_KEY = "edai2/platform/opensearch"
EXPECTED_KEYS = ["username", "password"]


def _load_values() -> dict:
    loaded = yaml.safe_load(VALUES_FILE.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), "opensearch.yaml must parse as a dict"
    return loaded


def test_opensearch_values_wires_admin_password_via_secret_ref() -> None:
    values = _load_values()
    extra_envs = values.get("extraEnvs")
    assert isinstance(extra_envs, list) and extra_envs, (
        "opensearch.yaml must define extraEnvs wiring OPENSEARCH_INITIAL_ADMIN_PASSWORD"
    )
    matches = [e for e in extra_envs if isinstance(e, dict) and e.get("name") == ENV_NAME]
    assert len(matches) == 1, (
        f"exactly one extraEnvs entry must set {ENV_NAME}, got: {extra_envs}"
    )
    entry = matches[0]
    assert "value" not in entry, "admin password must use valueFrom, never a literal `value:`"
    ref = (entry.get("valueFrom") or {}).get("secretKeyRef") or {}
    assert ref.get("name") == SECRET_NAME, f"secretKeyRef.name must be {SECRET_NAME!r}"
    assert ref.get("key") == SECRET_KEY, f"secretKeyRef.key must be {SECRET_KEY!r}"


def test_opensearch_values_contains_no_literal_password() -> None:
    values = _load_values()

    violations: list[str] = []

    def walk(node: object, path: str) -> None:
        if isinstance(node, dict):
            for key, val in node.items():
                # `key: password` / `adminPasswordKey: password` style references
                # name the secret data key; they are not literals.
                # The installer-disable FLAG (value "true" on a well-known
                # non-credential env name) is explicitly allowlisted.
                if key == "value" and isinstance(val, str) and val:
                    if node.get("name") == "DISABLE_INSTALL_DEMO_CONFIG":
                        walk(val, f"{path}.{key}")
                        continue
                    violations.append(f"{path}.{key}={val!r}")
                elif key not in {"key", "name", "secretKeyRef", "valueFrom"} and re.search(
                    r"passw", str(key), re.IGNORECASE
                ):
                    if isinstance(val, str) and val and val != SECRET_KEY:
                        violations.append(f"{path}.{key}={val!r}")
                walk(val, f"{path}.{key}")
        elif isinstance(node, list):
            for idx, item in enumerate(node):
                walk(item, f"{path}[{idx}]")

    walk(values, "$")
    assert not violations, f"literal password-looking scalars in opensearch.yaml: {violations}"


def test_opensearch_template_renders_admin_password_from_secret() -> None:
    proc = subprocess.run(
        [
            "helm", "template", "opensearch", "opensearch",
            "--repo", "https://opensearch-project.github.io/helm-charts",
            "--version", "2.38.0",
            "-n", "edai2",
            "-f", str(VALUES_FILE),
            "--dry-run=client",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, f"helm template failed: {proc.stderr[:2000]}"
    docs = [d for d in yaml.safe_load_all(proc.stdout) if isinstance(d, dict)]
    sts = [d for d in docs if d.get("kind") == "StatefulSet"]
    assert sts, "rendered manifests must contain a StatefulSet"
    found = False
    for st in sts:
        containers = (
            st.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
        )
        for container in containers:
            for env in container.get("env") or []:
                if env.get("name") == ENV_NAME:
                    ref = (env.get("valueFrom") or {}).get("secretKeyRef") or {}
                    assert ref.get("name") == SECRET_NAME, f"rendered secret name: {ref}"
                    assert ref.get("key") == SECRET_KEY, f"rendered secret key: {ref}"
                    assert "value" not in env, "rendered env must not carry a literal value"
                    found = True
    assert found, f"{ENV_NAME} with secretKeyRef not rendered in StatefulSet containers"


# --- DEFECT 2: nothing syncs the `opensearch` secret (KEY_MATRIX + ExternalSecret) ---


def _load_key_matrix() -> dict:
    spec = importlib.util.spec_from_file_location("configure_vault", CONFIGURE_VAULT_FILE)
    assert spec and spec.loader, "missing scripts/gke/configure_vault.py"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    matrix = module.KEY_MATRIX
    assert isinstance(matrix, dict), "KEY_MATRIX must be a dict"
    return matrix


def _load_manifest() -> dict:
    assert MANIFEST_FILE.is_file(), f"missing ExternalSecret manifest: {MANIFEST_FILE.name}"
    docs = [d for d in yaml.safe_load_all(MANIFEST_FILE.read_text(encoding="utf-8")) if isinstance(d, dict)]
    assert len(docs) == 1, f"{MANIFEST_FILE.name} must contain exactly one document"
    return docs[0]


def test_opensearch_key_matrix_entry() -> None:
    matrix = _load_key_matrix()
    assert KV_PATH in matrix, f"KEY_MATRIX missing {KV_PATH!r}"
    assert list(matrix[KV_PATH]) == EXPECTED_KEYS, (
        f"KEY_MATRIX[{KV_PATH!r}] must be exactly {EXPECTED_KEYS}"
    )


def test_opensearch_externalsecret_manifest() -> None:
    manifest = _load_manifest()
    assert manifest.get("apiVersion") == "external-secrets.io/v1"
    assert manifest.get("kind") == "ExternalSecret"
    spec = manifest.get("spec") or {}
    assert spec.get("refreshInterval") == "1h", "refreshInterval must match siblings (1h)"
    store = spec.get("secretStoreRef") or {}
    assert store.get("name") == "edai2-vault", "secretStoreRef.name must be edai2-vault"
    assert store.get("kind") == "ClusterSecretStore", "secretStoreRef.kind must be ClusterSecretStore"
    assert (spec.get("target") or {}).get("name") == SECRET_NAME, (
        f"target.name must be {SECRET_NAME!r}"
    )
    data = spec.get("data")
    assert isinstance(data, list) and data, "manifest data must be a non-empty list"
    mapped = {e.get("secretKey"): (e.get("remoteRef") or {}) for e in data if isinstance(e, dict)}
    assert sorted(mapped, key=str) == sorted(EXPECTED_KEYS), (
        f"manifest must map exactly {EXPECTED_KEYS}, got {sorted(mapped, key=str)}"
    )
    for secret_key, ref in mapped.items():
        assert ref.get("key") == REMOTE_KEY, f"remoteRef.key must be {REMOTE_KEY!r}"
        assert ref.get("property") == secret_key, "remoteRef.property must equal secretKey"


def test_opensearch_values_matches_externalsecret() -> None:
    values = _load_values()
    extra_envs = values.get("extraEnvs") or []
    entry = next(
        (e for e in extra_envs if isinstance(e, dict) and e.get("name") == ENV_NAME), None
    )
    assert entry is not None, f"extraEnvs must wire {ENV_NAME}"
    ref = (entry.get("valueFrom") or {}).get("secretKeyRef") or {}
    manifest = _load_manifest()
    spec = manifest.get("spec") or {}
    assert ref.get("name") == (spec.get("target") or {}).get("name"), (
        "values secretKeyRef.name must EXACTLY equal manifest target.name"
    )
    manifest_keys = {e.get("secretKey") for e in spec.get("data") or [] if isinstance(e, dict)}
    assert ref.get("key") in manifest_keys, (
        "values secretKeyRef.key must EXACTLY equal a manifest secretKey"
    )


def test_opensearch_sync_carries_no_literal_credential() -> None:
    manifest = _load_manifest()
    for entry in (manifest.get("spec") or {}).get("data") or []:
        assert set(entry) <= {"secretKey", "remoteRef"}, (
            f"data entries must be refs only, got: {entry}"
        )
        assert set((entry.get("remoteRef") or {})) <= {"key", "property"}, (
            f"remoteRef must be key/property refs only, got: {entry}"
        )
    matrix = _load_key_matrix()
    keys = matrix.get(KV_PATH)
    assert isinstance(keys, list) and keys, f"KEY_MATRIX[{KV_PATH!r}] must list key names"
    assert all(isinstance(k, str) for k in keys), "KEY_MATRIX carries key names only, never values"
