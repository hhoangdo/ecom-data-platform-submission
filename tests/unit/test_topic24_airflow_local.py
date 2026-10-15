"""Topic 24 LOCAL airflow fix (no lease): external postgres + small log PVCs.

Live-proven failures against `airflow/airflow --version 1.16.0` installed with
infra/helm/edai2/values/airflow.yaml:

1. The chart bundles `docker.io/bitnami/postgresql:16.1.0-debian-11-r15`,
   which upstream REMOVED -> ImagePullBackOff. The platform already runs its
   own postgres (`postgres-postgresql.edai2`, release `postgres`) whose creds
   are Vault-synced by ExternalSecret `postgres` -> k8s secret `postgres`
   (keys `username`/`password`/`database`). The bundled subchart must be
   disabled (`postgresql.enabled=false`, real key, chart values line 2630)
   and Airflow pointed at the platform Service. The airflow chart 1.16.0 has
   NO `passwordSecret+key` mechanism for the metadata DB: `data` offers only
   `metadataConnection.{user,pass,...}` (renders a literal into the
   chart-managed `airflow-metadata` Secret) or `metadataSecretName` (needs a
   `connection`-keyed secret nothing syncs). The fix therefore wires the REAL
   password with real chart keys: `secret:` (verbatim secretKeyRef envs,
   values line 347) + `extraEnv` (tpl-rendered string, values line 432) using
   kubelet `$(VAR)` expansion, with the chart-default conn envs switched off
   via `enableBuiltInSecretEnvVars` (values line 357).
2. `workers.persistence` + `triggerer.persistence` default to
   `enabled=true, size=100Gi` (chart values lines 691-700, 1656-1662); the
   worker/triggerer Deployments flip to StatefulSets with a `logs`
   volumeClaimTemplate, so live created `logs-airflow-worker-0` +
   `logs-airflow-triggerer-0` at 100Gi each (271Gi live total vs the 80Gi
   ceiling). Fix: `workers.persistence.size=4Gi` +
   `triggerer.persistence.size=4Gi` (real keys; durable 4Gi log PVCs kept,
   emptyDir rejected). Bound live total is 62Gi
   (postgres 16 + redpanda 8 + opensearch 8 + valkey 4 + clickhouse 16 +
   vault 10); airflow renders 4+4+1(redis)=9Gi -> 71Gi <= 80Gi.

Runtime shape this suite pins (all asserted against `helm template`):
- images: exactly {apache/airflow:2.10.5, redis:7.2-bookworm,
  quay.io/prometheus/statsd-exporter:v0.28.0}; zero `bitnami/postgresql`.
- PVCs: `logs` 4Gi x2 + `redis-db` 1Gi; each <= 8Gi; rendered total (9Gi) +
  bound (62Gi) <= 80Gi. Predicted runtime PVC names `logs-airflow-worker-0`
  / `logs-airflow-triggerer-0` (claim + StatefulSet + ordinal 0) feed the
  leased-agent handoff (uninstall -> delete ONLY those two -> reinstall).
- DB auth: every workload pod defines `AIRFLOW_DB_PASSWORD` from
  secretKeyRef {postgres,password} BEFORE `AIRFLOW__DATABASE__SQL_ALCHEMY_CONN`
  whose value is exactly the `$(...)`-expansion template (no literal);
  chart-default conn envs absent; nothing references the orphaned
  chart-default `airflow-metadata` Secret (it renders with the bundled-host
  default and dies with `helm uninstall`; deleting it early is out of scope).
- Services: ClusterIP or headless (`clusterIP: None`, worker/triggerer log
  readers) only; no LoadBalancer/NodePort/ExternalName/externalIPs.
"""

from __future__ import annotations

import base64
import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
VALUES_FILE = ROOT / "infra/helm/edai2/values/airflow.yaml"
POSTGRES_ES_FILE = ROOT / "infra" / "security" / "external-secrets" / "postgres.yaml"

RELEASE = "airflow"
CHART = "airflow"
REPO = "https://airflow.apache.org"
VERSION = "1.16.0"

# External DB wiring (must track values/airflow.yaml exactly).
PLATFORM_HOST = "postgres-postgresql.edai2"
SECRET_NAME = "postgres"  # == ExternalSecret `postgres` target.name
SECRET_KEY = "password"  # == one of its synced secretKeys
ENV_PASSWORD = "AIRFLOW_DB_PASSWORD"
ENV_CONN = "AIRFLOW__DATABASE__SQL_ALCHEMY_CONN"
EXPECTED_CONN_VALUE = (
    "postgresql://postgres:$(" + ENV_PASSWORD + ")@"
    + PLATFORM_HOST + ":5432/postgres?sslmode=disable"
)
DISABLED_BUILTIN_CONN_ENVS = {
    "AIRFLOW__CORE__SQL_ALCHEMY_CONN",
    "AIRFLOW__DATABASE__SQL_ALCHEMY_CONN",
    "AIRFLOW_CONN_AIRFLOW_DB",
}

# Bundled-postgres evidence (live-proven removed upstream).
GONE_BITNAMI_IMAGE = "docker.io/bitnami/postgresql:16.1.0-debian-11-r15"
EXPECTED_IMAGES = {
    "apache/airflow:2.10.5",
    "quay.io/prometheus/statsd-exporter:v0.28.0",
    "redis:7.2-bookworm",
}

# PVC budget: bound live total 62Gi + rendered airflow <= 80Gi ceiling.
BOUND_PVC_GI = 62  # postgres 16 + redpanda 8 + opensearch 8 + valkey 4 + clickhouse 16 + vault 10
PVC_CEILING_GI = 80
EXPECTED_LOG_PVC_GI = 4
EXPECTED_REDIS_PVC_GI = 1
EXPECTED_LOG_PVC_NAMES = {"logs-airflow-worker-0", "logs-airflow-triggerer-0"}

_SIZE_RE = re.compile(r"^(\d+)Gi$")
_IMAGE_RE = re.compile(r"^\s*image:\s*[\"']?([^\"'\s]+)", re.MULTILINE)


def _load_values() -> dict:
    loaded = yaml.safe_load(VALUES_FILE.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), "airflow.yaml must parse as a dict"
    return loaded


def _render() -> str:
    proc = subprocess.run(
        [
            "helm", "template", RELEASE, f"{CHART}/{CHART}",
            "--version", VERSION,
            "-n", "edai2",
            "-f", str(VALUES_FILE),
            "--dry-run=client",
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, f"helm template failed: {proc.stderr[:2000]}"
    return proc.stdout


def _render_docs() -> list[dict]:
    return [d for d in yaml.safe_load_all(_render()) if isinstance(d, dict)]


def _gibibytes(size: object) -> int:
    assert isinstance(size, str) and _SIZE_RE.match(size), f"PVC size must be NGi, got {size!r}"
    return int(_SIZE_RE.match(str(size)).group(1))  # type: ignore[union-attr]


def _workload_pods(docs: list[dict]) -> list[tuple[str, dict]]:
    pods = []
    for doc in docs:
        if doc.get("kind") in ("Deployment", "StatefulSet", "Job"):
            spec = (doc.get("spec") or {}).get("template", {}).get("spec", {})
            if spec.get("containers"):
                pods.append((str((doc.get("metadata") or {}).get("name")), spec))
    assert pods, "rendered manifests must contain workload pods"
    return pods


# --- values shape ---


def test_values_disables_bundled_postgres() -> None:
    values = _load_values()
    postgres = values.get("postgresql")
    assert isinstance(postgres, dict) and postgres.get("enabled") is False, (
        "airflow.yaml must set postgresql.enabled=false (bundled bitnami image is gone upstream)"
    )


def test_values_wires_db_password_from_platform_secret() -> None:
    values = _load_values()
    secret = values.get("secret")
    assert isinstance(secret, list) and secret, "airflow.yaml must define a `secret:` entry"
    matches = [e for e in secret if isinstance(e, dict) and e.get("envName") == ENV_PASSWORD]
    assert len(matches) == 1, f"exactly one `secret:` entry must set {ENV_PASSWORD}, got: {secret}"
    entry = matches[0]
    assert entry.get("secretName") == SECRET_NAME, f"secretName must be {SECRET_NAME!r}"
    assert entry.get("secretKey") == SECRET_KEY, f"secretKey must be {SECRET_KEY!r}"


def test_values_disables_chart_default_conn_envs() -> None:
    values = _load_values()
    gates = values.get("enableBuiltInSecretEnvVars")
    assert isinstance(gates, dict), "airflow.yaml must set enableBuiltInSecretEnvVars gates"
    for env_name in DISABLED_BUILTIN_CONN_ENVS:
        assert gates.get(env_name) is False, (
            f"enableBuiltInSecretEnvVars.{env_name} must be false "
            "(else pods use the chart-default bundled-postgres Secret)"
        )


def test_values_conn_template_uses_expansion_not_literal() -> None:
    values = _load_values()
    extra_env = values.get("extraEnv")
    assert isinstance(extra_env, str) and extra_env, "airflow.yaml must define extraEnv as a string"
    docs = list(yaml.safe_load_all(extra_env))
    assert len(docs) == 1 and isinstance(docs[0], list), "extraEnv must parse as one env list"
    matches = [e for e in docs[0] if isinstance(e, dict) and e.get("name") == ENV_CONN]
    assert len(matches) == 1, f"exactly one extraEnv entry must set {ENV_CONN}"
    assert matches[0].get("value") == EXPECTED_CONN_VALUE, (
        f"extraEnv {ENV_CONN} must be exactly the $()-expansion template, got: {matches[0]!r}"
    )


def test_values_shrinks_log_persistence() -> None:
    values = _load_values()
    for component in ("workers", "triggerer"):
        size = ((values.get(component) or {}).get("persistence") or {}).get("size")
        assert size == f"{EXPECTED_LOG_PVC_GI}Gi", (
            f"{component}.persistence.size must be {EXPECTED_LOG_PVC_GI}Gi "
            f"(100Gi default blows the 80Gi ceiling), got {size!r}"
        )


def test_values_secret_matches_postgres_externalsecret() -> None:
    manifest = yaml.safe_load(POSTGRES_ES_FILE.read_text(encoding="utf-8"))
    spec = manifest.get("spec") or {}
    assert (spec.get("target") or {}).get("name") == SECRET_NAME
    synced_keys = {e.get("secretKey") for e in spec.get("data") or [] if isinstance(e, dict)}
    assert SECRET_KEY in synced_keys, f"{SECRET_KEY!r} must be a synced postgres secretKey"
    values = _load_values()
    entry = next(
        e for e in (values.get("secret") or []) if isinstance(e, dict) and e.get("envName") == ENV_PASSWORD
    )
    assert entry.get("secretName") == (spec.get("target") or {}).get("name"), (
        "values secretName must EXACTLY equal the postgres ExternalSecret target.name"
    )
    assert entry.get("secretKey") in synced_keys, (
        "values secretKey must EXACTLY equal a synced postgres secretKey"
    )


def test_values_contains_no_literal_credential() -> None:
    values = _load_values()
    violations: list[str] = []

    def walk(node: object, path: str) -> None:
        if isinstance(node, dict):
            for key, val in node.items():
                lkey = str(key).lower()
                # `secretKey: password`-style entries NAME the secret data key;
                # they are references, not literals.
                if lkey in {"password", "pass", "passwd"} and isinstance(val, str) and val:
                    violations.append(f"{path}.{key}={val!r}")
                elif "password" in lkey and lkey not in {"secretkey", "secretkeys"}:
                    if isinstance(val, str) and val and val != SECRET_KEY:
                        violations.append(f"{path}.{key}={val!r}")
                if key == "value" and isinstance(val, str) and "://" in val and "@" in val:
                    userinfo = val.split("://", 1)[1].split("@", 1)[0]
                    if not re.fullmatch(r"[^:]+:\$\([A-Za-z_][A-Za-z0-9_]*\)", userinfo):
                        violations.append(f"{path}.{key} carries a non-reference userinfo: {val!r}")
                walk(val, f"{path}.{key}")
        elif isinstance(node, list):
            for idx, item in enumerate(node):
                walk(item, f"{path}[{idx}]")

    walk(values, "$")
    assert not violations, f"literal credential material in airflow.yaml: {violations}"


# --- render proofs ---


def test_render_bundled_postgres_statefulset_absent() -> None:
    docs = _render_docs()
    names = [str((d.get("metadata") or {}).get("name")) for d in docs if d.get("kind") == "StatefulSet"]
    assert names, "expected StatefulSets (redis/worker/triggerer) in render"
    assert not [n for n in names if "postgresql" in n or "postgres" in n], (
        f"bundled postgres StatefulSet must be absent, got: {names}"
    )


def test_render_has_no_gone_bitnami_image() -> None:
    manifest = _render()
    assert GONE_BITNAMI_IMAGE not in manifest, f"render still pulls gone image {GONE_BITNAMI_IMAGE}"
    assert "bitnami/postgresql" not in manifest, "render must contain ZERO bitnami/postgresql refs"


def test_render_workload_images_exact() -> None:
    docs = _render_docs()
    images = {m.group(1) for d in docs for m in _IMAGE_RE.finditer(yaml.safe_dump(d))}
    assert images == EXPECTED_IMAGES, (
        f"airflow workload images must be exactly the pinned set.\n"
        f"actual={sorted(images)}\nexpected={sorted(EXPECTED_IMAGES)}"
    )


def test_render_pvc_sizes_fit_budget() -> None:
    docs = _render_docs()
    claims: list[tuple[str, str, int]] = []
    for doc in docs:
        if doc.get("kind") != "StatefulSet":
            continue
        sts = str((doc.get("metadata") or {}).get("name"))
        for v in ((doc.get("spec") or {}).get("volumeClaimTemplates") or []):
            claim = str((v.get("metadata") or {}).get("name"))
            size = (v.get("spec") or {}).get("resources", {}).get("requests", {}).get("storage")
            claims.append((sts, claim, _gibibytes(size)))
    assert claims, "expected volumeClaimTemplates in render"
    for sts, claim, gib in claims:
        assert gib <= 8, f"StatefulSet {sts} claim {claim} is {gib}Gi, must be <= 8Gi each"
    by_claim = sorted((c, g) for _, c, g in claims)
    assert by_claim == [("logs", EXPECTED_LOG_PVC_GI), ("logs", EXPECTED_LOG_PVC_GI),
                        ("redis-db", EXPECTED_REDIS_PVC_GI)], (
        f"unexpected PVC shape: {by_claim}"
    )
    rendered_total = sum(g for _, _, g in claims)
    assert BOUND_PVC_GI + rendered_total <= PVC_CEILING_GI, (
        f"PVC budget blown: bound {BOUND_PVC_GI}Gi + rendered {rendered_total}Gi "
        f"> {PVC_CEILING_GI}Gi ceiling"
    )


def test_render_predicts_log_pvc_names() -> None:
    docs = _render_docs()
    predicted = {
        f"{claim}-{sts}-0"
        for doc in docs if doc.get("kind") == "StatefulSet"
        for sts in [str((doc.get("metadata") or {}).get("name"))]
        for v in (((doc.get("spec") or {}).get("volumeClaimTemplates")) or [])
        for claim in [str((v.get("metadata") or {}).get("name"))]
        if claim == "logs"
    }
    assert predicted == EXPECTED_LOG_PVC_NAMES, (
        f"leased-agent handoff PVC names drift: {sorted(predicted)}"
    )


def test_render_db_env_uses_secret_ref_not_literal() -> None:
    docs = _render_docs()
    pods = _workload_pods(docs)
    checked = 0
    for name, spec in pods:
        for container in spec.get("containers", []):
            env = container.get("env") or []
            by_name = {e.get("name"): e for e in env if isinstance(e, dict)}
            if ENV_CONN not in by_name and ENV_PASSWORD not in by_name:
                continue  # non-airflow sidecar (e.g. redis, statsd): no DB env expected
            checked += 1
            pw = by_name.get(ENV_PASSWORD)
            assert pw is not None, f"{name}/{container.get('name')}: missing {ENV_PASSWORD}"
            ref = (pw.get("valueFrom") or {}).get("secretKeyRef") or {}
            assert ref.get("name") == SECRET_NAME, f"{name}: secretKeyRef.name: {ref}"
            assert ref.get("key") == SECRET_KEY, f"{name}: secretKeyRef.key: {ref}"
            assert "value" not in pw, f"{name}: {ENV_PASSWORD} must not carry a literal value"
            conn = by_name.get(ENV_CONN)
            assert conn is not None, f"{name}/{container.get('name')}: missing {ENV_CONN}"
            assert conn.get("value") == EXPECTED_CONN_VALUE, (
                f"{name}: {ENV_CONN} must be the expansion template, got: {conn!r}"
            )
            # Password ordering: kubelet $(...) expansion needs the ref first.
            order = [e.get("name") for e in env if isinstance(e, dict)]
            assert order.index(ENV_PASSWORD) < order.index(ENV_CONN), (
                f"{name}/{container.get('name')}: {ENV_PASSWORD} must precede {ENV_CONN}"
            )
            for banned in DISABLED_BUILTIN_CONN_ENVS - {ENV_CONN}:
                assert banned not in by_name, (
                    f"{name}: chart-default {banned} must stay disabled (points at bundled postgres)"
                )
    assert checked >= 5, f"expected DB env on all airflow workloads, checked {checked}"


def test_render_orphan_metadata_secret_unreferenced() -> None:
    docs = _render_docs()
    secrets = [d for d in docs if d.get("kind") == "Secret"]
    assert any(str((d.get("metadata") or {}).get("name")) == "airflow-metadata" for d in secrets), (
        "chart-default airflow-metadata Secret must still render (proves nothing else mints it)"
    )
    for name, spec in _workload_pods(docs):
        for container in spec.get("containers", []) + spec.get("initContainers", []):
            for e in container.get("env") or []:
                ref = ((e.get("valueFrom") or {}).get("secretKeyRef") or {})
                assert ref.get("name") != "airflow-metadata", (
                    f"{name}: nothing may reference the orphaned chart-default secret: {e!r}"
                )
    for doc in secrets:
        if str((doc.get("metadata") or {}).get("name")) == "airflow-metadata":
            raw = base64.b64decode(doc["data"]["connection"]).decode()
            assert PLATFORM_HOST not in raw, (
                "orphan Secret must carry NO platform credential material"
            )


def test_render_services_private_only() -> None:
    docs = _render_docs()
    services = [d for d in docs if d.get("kind") == "Service"]
    assert services, "expected Services in render"
    for svc in services:
        name = str((svc.get("metadata") or {}).get("name"))
        spec = svc.get("spec") or {}
        stype = spec.get("type")  # absent == default ClusterIP
        assert stype in (None, "ClusterIP"), (
            f"Service {name} must stay ClusterIP/headless, got {stype}"
        )
        assert not spec.get("externalIPs"), f"Service {name} must not carry externalIPs"
        assert "loadBalancerIP" not in spec, f"Service {name} must not carry loadBalancerIP"
