"""Topic 24 DEFECT 3: no floating `:latest` workload images in pinned renders.

Approach (recorded): each test renders every chart pinned in
infra/helm/edai2/releases.yaml via `helm template <release> <chart> --repo
<repo-from-catalog> --version <pin> -n edai2 [-f values/<name>.yaml]
--dry-run=client` in a subprocess. This needs only the local Helm chart
cache (no `helm repo update`, no cluster) once warmed; the first run warms
it with plain metadata/template reads. Release `airflow` has no values file
in-repo, so it renders with chart defaults.

Verdict table (verified 2026-10-09, `helm template` per pin):
- postgres 18.12.4: `registry-1.docker.io/bitnami/postgresql:latest` --
  REAL workload image, pulled. Chart default is `tag: latest`
  (`helm show values bitnami/postgresql --version 18.12.4`) and the chart's
  own Chart.yaml annotations declare
  `image: registry-1.docker.io/bitnami/postgresql:latest` (appVersion
  18.6.0). Docker Hub has no `18.6.0` tag for bitnami/postgresql (HTTP 404),
  so pinning a versioned tag would be guessing upstream tags -- forbidden.
  Recorded as KNOWN-FLOATING (exact-hit asserted; any change fails).
- valkey 6.3.4: `registry-1.docker.io/bitnami/valkey:latest` -- same
  dead-end (chart default `tag: latest`, Chart appVersion 9.1.2, Docker Hub
  has no `9.1.2` tag -> 404). KNOWN-FLOATING.
- opensearch 2.38.0: main image pinned `opensearchproject/opensearch:2.19.6`
  (via Chart.AppVersion default). The `busybox:latest` fsgroup-volume
  initContainer (rendered while `persistence.enabled=true` with default
  `persistence.enableInitChown=true`) IS pulled, so values set
  `persistence.enableInitChown: false` (real chart key; podSecurityContext
  fsGroup: 1000 still owns the volume) -> no `:latest` remains.
- loki 7.3.0: `docker.io/grafana/loki-helm-test:latest` renders ONLY in
  `loki/templates/tests/test-canary.yaml`, a Pod annotated
  `"helm.sh/hook": test` (runs solely via `helm test`, never pulled as a
  workload). BENIGN-WITH-PROOF (hook annotation asserted).
- postgres/valkey `bitnami/os-shell:latest` (volumePermissions) and
  `bitnami/postgres-exporter:latest` / `bitnami/redis-exporter:latest`
  (metrics): `volumePermissions.enabled=false` and metrics disabled by
  default -> NOT rendered (absence asserted). BENIGN-WITH-PROOF.
- All other 13 pins (airflow, ingress-nginx, external-secrets, keda,
  cert-manager, redpanda, clickhouse, feast@corrected-url, datahub,
  prometheus, tempo, grafana, alloy, langfuse, jenkins): zero `:latest`.

The equality assertion is fail-closed in both directions: a NEW `:latest`
anywhere fails, and a documented entry disappearing (e.g. upstream finally
pins postgres) fails directing the editor to remove it from the allowlist.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CATALOG_FILE = ROOT / "infra/helm/edai2/releases.yaml"
VALUES_DIR = ROOT / "infra/helm/edai2/values"

# Release name -> Helm chart name when they differ (bitnami postgresql chart).
CHART_NAME_OVERRIDES = {"postgres": "postgresql"}

# Exact known-floating REAL workload images: chart-default `latest` with no
# versioned tag source in the chart's own docs (see module docstring).
# NEVER extend this without the dead-end proof above.
EXPECTED_FLOATING_REAL: dict[str, set[str]] = {
    "postgres": {"registry-1.docker.io/bitnami/postgresql:latest"},
    "valkey": {"registry-1.docker.io/bitnami/valkey:latest"},
}

# Benign helper image: helm-test hook only, never a workload container.
EXPECTED_BENIGN_TEST_HOOK: dict[str, set[str]] = {
    "loki": {"docker.io/grafana/loki-helm-test:latest"},
}

# Topic 24 LOCAL clickhouse fix (no lease): bitnami/clickhouse 9.4.4 defaults
# render `docker.io/bitnami/clickhouse:25.7.5-debian-12-r0` (shard) and
# `docker.io/bitnami/clickhouse-keeper:25.7.5-debian-12-r0` (keeper), both
# ImagePullBackOff live (`not found`; `bitnami/clickhouse*` repos are EMPTY,
# count 0). Chart.yaml appVersion is 25.7.5. Official upstream
# `clickhouse/clickhouse-server:25.7.5` PULLS but is INCOMPATIBLE with the
# bitnami chart layout (CrashLoop: needs CLICKHOUSE_USER/PASSWORD + writable
# users.d) -- ABANDONED. Fix reverts to Bitnami-layout images via the legacy
# registry: `docker.io/bitnamilegacy/clickhouse:25.7.5-debian-12-r0` and
# `docker.io/bitnamilegacy/clickhouse-keeper:25.7.5-debian-12-r0` (exact
# chart-default tags, verified to EXIST). Both `image.repository` and
# `keeper.image.repository` keys are overridden; tags keep chart defaults.
# 2026-10-14 Topic 24 ClickHouse version exception (user-approved recovery):
# Langfuse 4.50.0 requires ClickHouse >=25.12; retained 25.7.5 cannot run
# migration 39. Shard moves to official `clickhouse/clickhouse-server:26.4`
# (app 26.4.5.143, digest pinned at deploy); keeper stays legacy 25.7.5.
EXPECTED_CLICKHOUSE_PINNED: set[str] = {
    "docker.io/clickhouse/clickhouse-server@sha256:10c8dfc39d3fa015f3fbf44d77efa8f794a004e0ae1e509fbd1d4dfac88bb006",
    "docker.io/bitnamilegacy/clickhouse-keeper:25.7.5-debian-12-r0",
}
EXPECTED_CLICKHOUSE_LEGACY_SHARD: set[str] = {
    "docker.io/bitnamilegacy/clickhouse:25.7.5-debian-12-r0",
}
BROKEN_BITNAMI_CLICKHOUSE_IMAGES: set[str] = {
    "docker.io/bitnami/clickhouse:25.7.5-debian-12-r0",
    "docker.io/bitnami/clickhouse-keeper:25.7.5-debian-12-r0",
}
# Official-upstream image abandoned (entrypoint incompatible with bitnami
# chart layout). Must render ZERO refs to it.
ABANDONED_UPSTREAM_CLICKHOUSE_IMAGES: set[str] = {
    "docker.io/clickhouse/clickhouse-server:25.7.5",
}

_IMAGE_RE = re.compile(r"^\s*image:\s*[\"']?([^\"'\s]+)", re.MULTILINE)


def _catalog_pins() -> list[dict]:
    loaded = yaml.safe_load(CATALOG_FILE.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    charts = loaded.get("charts")
    assert isinstance(charts, list) and charts
    return charts


def _render(release: str, chart: str, repo: str, version: str) -> str:
    cmd = [
        "helm", "--kubeconfig", str(ROOT / "tmp/edai2-gcp/kubeconfig"),
        "--kube-context", "edai2-gke", "template", release, chart,
        "--repo", repo,
        "--version", version,
        "-n", "edai2",
    ]
    values_file = VALUES_DIR / f"{release}.yaml"
    if values_file.is_file():
        cmd += ["-f", str(values_file)]
    cmd += ["--dry-run=client"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    assert proc.returncode == 0, (
        f"helm template {release} ({chart} {version}) failed: {proc.stderr[:2000]}"
    )
    return proc.stdout


def _floating_images(manifest: str) -> set[str]:
    found: set[str] = set()
    for match in _IMAGE_RE.finditer(manifest):
        ref = match.group(1)
        if "@sha256:" in ref:
            continue  # digest-pinned
        # Strip a trailing @digest if a tag+digest combo is ever used.
        bare = ref.split("@")[0]
        if bare.endswith(":latest") or ":" not in bare.split("/")[-1]:
            found.add(ref)
    return found


def test_pins_cover_every_catalog_chart() -> None:
    pins = _catalog_pins()
    for entry in pins:
        release = str(entry["name"])
        chart = CHART_NAME_OVERRIDES.get(release, release)
        assert isinstance(entry["version"], str) and entry["version"]
        assert isinstance(entry["repo"], str) and entry["repo"].startswith("https://")
        assert chart, f"chart name missing for {release}"
    assert set(CHART_NAME_OVERRIDES) <= {e["name"] for e in pins}


def test_no_unexpected_latest_images_in_pinned_renders() -> None:
    actual: dict[str, set[str]] = {}
    for entry in _catalog_pins():
        release = str(entry["name"])
        chart = CHART_NAME_OVERRIDES.get(release, release)
        manifest = _render(release, chart, str(entry["repo"]), str(entry["version"]))
        floating = _floating_images(manifest)
        if floating:
            actual[release] = floating
    expected: dict[str, set[str]] = {
        **{k: set(v) for k, v in EXPECTED_FLOATING_REAL.items()},
        **{k: set(v) for k, v in EXPECTED_BENIGN_TEST_HOOK.items()},
    }
    assert actual == expected, (
        f":latest verdict drift.\nactual={actual}\nexpected={expected}"
    )


def test_loki_latest_is_test_hook_only() -> None:
    pins = {str(e["name"]): e for e in _catalog_pins()}
    entry = pins["loki"]
    manifest = _render("loki", "loki", str(entry["repo"]), str(entry["version"]))
    docs = [d for d in yaml.safe_load_all(manifest) if isinstance(d, dict)]
    carriers = [
        d for d in docs
        if "loki-helm-test:latest" in yaml.safe_dump(d)
    ]
    assert carriers, "expected the loki-helm-test render carrier"
    for doc in carriers:
        annotations = (doc.get("metadata") or {}).get("annotations") or {}
        assert annotations.get("helm.sh/hook") == "test", (
            f"loki-helm-test carrier must be a helm test hook: {doc.get('kind')}"
        )


def test_postgres_valkey_helper_images_not_rendered() -> None:
    pins = {str(e["name"]): e for e in _catalog_pins()}
    for release, chart in (("postgres", "postgresql"), ("valkey", "valkey")):
        entry = pins[release]
        manifest = _render(release, chart, str(entry["repo"]), str(entry["version"]))
        assert "os-shell" not in manifest, f"{release}: volumePermissions must stay disabled"
        assert "exporter" not in manifest, f"{release}: metrics must stay disabled"


def _clickhouse_manifest() -> str:
    pins = {str(e["name"]): e for e in _catalog_pins()}
    entry = pins["clickhouse"]
    return _render("clickhouse", "clickhouse", str(entry["repo"]), str(entry["version"]))


def _workload_images(manifest: str) -> set[str]:
    return {m.group(1) for m in _IMAGE_RE.finditer(manifest)}


def test_clickhouse_has_no_broken_bitnami_images() -> None:
    manifest = _clickhouse_manifest()
    for broken in BROKEN_BITNAMI_CLICKHOUSE_IMAGES:
        assert broken not in manifest, (
            f"clickhouse still renders broken image {broken}"
        )
    # Fail-closed in both directions: ZERO `docker.io/bitnami/` refs and ZERO
    # abandoned-upstream `clickhouse/clickhouse-server:25.7.5` refs. The
    # approved 26.4 exception (`clickhouse/clickhouse-server:26.4`) is the
    # ONLY permitted clickhouse-server ref.
    assert "docker.io/bitnami/" not in manifest, (
        "clickhouse must render ZERO docker.io/bitnami/ refs"
    )
    for abandoned in ABANDONED_UPSTREAM_CLICKHOUSE_IMAGES:
        assert abandoned not in manifest, (
            f"clickhouse still renders abandoned upstream image {abandoned}"
        )
    assert "docker.io/clickhouse/clickhouse-server@sha256:10c8dfc39d3fa015f3fbf44d77efa8f794a004e0ae1e509fbd1d4dfac88bb006" in manifest, (
        "clickhouse shard must render the approved 26.4 digest-pinned image"
    )


def test_clickhouse_workload_images_are_legacy_pinned() -> None:
    manifest = _clickhouse_manifest()
    images = _workload_images(manifest)
    assert images, "expected keeper+shard workload images in clickhouse render"
    assert images == EXPECTED_CLICKHOUSE_PINNED, (
        f"clickhouse images must be the pinned legacy images.\n"
        f"actual={sorted(images)}\nexpected={sorted(EXPECTED_CLICKHOUSE_PINNED)}"
    )
    assert not _floating_images(manifest), (
        f"clickhouse has floating images: {_floating_images(manifest)}"
    )


def test_clickhouse_single_replica_clusterip_only() -> None:
    manifest = _clickhouse_manifest()
    assert "os-shell" not in manifest, "clickhouse volumePermissions must stay disabled"
    docs = [d for d in yaml.safe_load_all(manifest) if isinstance(d, dict)]
    services = [d for d in docs if d.get("kind") == "Service"]
    assert services, "expected Services in clickhouse render"
    for svc in services:
        stype = ((svc.get("spec") or {}).get("type"))
        assert stype == "ClusterIP", (
            f"clickhouse Service {((svc.get('metadata') or {}).get('name'))} "
            f"must stay ClusterIP, got {stype}"
        )
    statefulsets = [d for d in docs if d.get("kind") == "StatefulSet"]
    assert len(statefulsets) == 2, (
        f"expected keeper+shard StatefulSets, got {len(statefulsets)}"
    )
    for sts in statefulsets:
        name = ((sts.get("metadata") or {}).get("name"))
        replicas = ((sts.get("spec") or {}).get("replicas"))
        assert replicas == 1, f"StatefulSet {name} must stay single-replica, got {replicas}"
