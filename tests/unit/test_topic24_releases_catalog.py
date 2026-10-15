"""Topic 24 DEFECT 2: releases.yaml must pin every install-stage chart (local-only).

The catalog pins only 6 charts but the Topic 24 14-stage fail-fast order
(tmp/edai2-plan/execution-v1/gcp/24-compact-platform-install.md, Task 3)
installs: External Secrets/store/targets -> cert-manager/ingress/KEDA ->
PostgreSQL/pgvector/Valkey/Redpanda/OpenSearch/ClickHouse ->
Airflow/Feast/DataHub -> Prometheus/Loki/Tempo/Grafana/Alloy -> Langfuse ->
Gateway API -> agentgateway -> cache verification -> llm-d -> Substrate ->
kagent -> Agent Registry -> Jenkins.

Rule: every install-stage Helm component resolves to exactly one pinned
{ name, version, repo } entry or is explicitly reported missing. NEVER invent
a version: components with no in-repo version source are OMITTED and reported
as still-missing (see STILL_MISSING below with exact next step).

In-repo version sources inspected 2026-10-08:
- tests/integration/llm/test_gke_agents.py asserts versions.gateway_api
  1.5.0, agentgateway 1.3.1, substrate 0.0.6, kagent 0.9.9, agentregistry
  0.3.3, llmd v0.7, ingress_nginx_chart 4.15.1 + ingress chartVersion 4.15.1.
- tests/unit/llm/test_observability.py + scripts/gke/configure_evidence_ingress.py
  assert ingress chartVersion == catalog versions.ingress_nginx_chart == 4.15.1.
- infra/helm/edai2/values/*.yaml carry chartVersion ONLY for ingress-nginx
  (4.15.1); agentgateway.yaml carries version 1.3.1; agentregistry.yaml
  carries version 0.3.3. No other values file carries a chart version.
- Full-repo grep for chart versions / Helm repo URLs for postgres, valkey,
  redpanda, opensearch, clickhouse, datahub, prometheus, loki, tempo, grafana,
  alloy, langfuse, jenkins found NO chart-version pins and (except
  https://kubernetes.github.io/ingress-nginx in tmp plan 20 doc) NO repo URLs.
  DataHub v1.6.0 / opensearch image 2.19.3 / Langfuse v3 / postgres:16.4 are
  image/app tags, NOT Helm chart versions -> NOT usable as pins.
Conclusion (2026-10-08 update): the 13 components formerly listed in
STILL_MISSING were pinned by local chart-pin engineering against their
canonical upstream charts (bitnami postgres/valkey/clickhouse, redpanda,
opensearch-project, acryl/datahub, prometheus-community, grafana
loki/tempo/grafana/alloy, langfuse-k8s, jenkinsci). Each pin is the newest
patch in its stable minor at pin time AND template-proves clean with its
checked-in values file (`helm template <rel> <chart> -n edai2 -f
infra/helm/edai2/values/<name>.yaml --version <v>`, client-side, no --set
overrides). STILL_MISSING is therefore EMPTY; the fail-closed mechanism is
retained for future components.
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CATALOG_FILE = ROOT / "infra/helm/edai2/releases.yaml"

# Every Helm-installable component in the Topic 24 14-stage order.
# Non-chart stages (Gateway API CRDs, cache verification, llm-d Kustomize)
# are covered by `versions` pins, not `charts` entries (see
# test_versions_match_test_asserted_pins); they are listed here only when
# they correspond to a Helm release (agentgateway, substrate, kagent,
# agentregistry are deployed via Helm/Kustomize with version pins).
INSTALL_STAGE_CHARTS = [
    "external-secrets",  # stage: External Secrets/store/targets
    "cert-manager",  # stage: cert-manager/ingress/KEDA
    "ingress-nginx",  # stage: cert-manager/ingress/KEDA
    "keda",  # stage: cert-manager/ingress/KEDA
    "postgres",  # stage: PostgreSQL/pgvector/Valkey/Redpanda/OpenSearch/ClickHouse
    "valkey",
    "redpanda",
    "opensearch",
    "clickhouse",
    "airflow",  # stage: Airflow/Feast/DataHub
    "feast",
    "datahub",
    "prometheus",  # stage: Prometheus/Loki/Tempo/Grafana/Alloy
    "loki",
    "tempo",
    "grafana",
    "alloy",
    "langfuse",  # stage: Langfuse
    "jenkins",  # stage: Jenkins
]

# Components with NO in-repo chart-version source (see module docstring).
# Exact next step per component: owning topic must source the chart version
# from the authoritative upstream chart (Chart.yaml / chart releases) and the
# repo URL already used for that component's docs, add a
# `- { name: <n>, version: "<v>", repo: "<url>" }` entry to releases.yaml,
# and remove the name from this list. Do NOT guess a version.
#
# 2026-10-08 local chart-pin engineering (EDAI2 Topic 24, no lease): all 13
# components below were template-proven against their canonical upstream
# charts (`helm show values` + `helm template -n edai2 -f
# infra/helm/edai2/values/<name>.yaml`, client-side only, no cluster writes)
# and pinned in releases.yaml. List is now EMPTY; the mechanism stays so any
# future install-stage component without a pin fails this suite instead of
# being guessed.
STILL_MISSING: list[str] = []

EXPECTED_VERSIONS = {
    "gateway_api": "1.5.0",
    "agentgateway": "1.3.1",
    "substrate": "0.0.6",
    "kagent": "0.9.9",
    "agentregistry": "0.3.3",
    "llmd": "v0.7",
    "ingress_nginx_chart": "4.15.1",
}

EXPECTED_CHART_VERSIONS = {
    "airflow": "1.16.0",
    "feast": "0.45.0",
    "ingress-nginx": "4.15.1",
    "external-secrets": "0.20.2",
    "keda": "2.17.2",
    "cert-manager": "1.18.2",
    # Template-proven 2026-10-08 (newest patch in the stable minor at pin
    # time; see releases.yaml comments for chart sources). DO NOT change
    # these without re-running the template proof for the component.
    "postgres": "18.12.4",
    "valkey": "6.3.4",
    "redpanda": "26.2.4",
    "opensearch": "2.38.0",
    "clickhouse": "9.4.4",
    "datahub": "1.1.6",
    "prometheus": "29.36.1",
    "loki": "7.3.0",
    "tempo": "1.24.4",
    "grafana": "10.5.15",
    "alloy": "1.13.1",
    "langfuse": "2.1.4",
    "jenkins": "5.9.68",
}

# DEFECT 2 (2026-10-09): every pin's repo URL is locked. The feast entry
# previously pointed at `https://feast-dev.github.io/feast`, which 404s
# (domain now redirects to https://feast.dev with no index.yaml; `helm repo
# add` fails "failed to fetch .../index.yaml : 404 Not Found"). The
# canonical in-chart-documented source is
# `https://feast-helm-charts.storage.googleapis.com` (feast
# infra/charts/feast-feature-server README: "helm repo add feast-charts
# https://feast-helm-charts.storage.googleapis.com"), which serves feast
# 0.45.0 (`helm search repo feast --versions`). Version UNCHANGED.
EXPECTED_CHART_REPOS = {
    "airflow": "https://airflow.apache.org",
    "feast": "https://feast-helm-charts.storage.googleapis.com",
    "ingress-nginx": "https://kubernetes.github.io/ingress-nginx",
    "external-secrets": "https://charts.external-secrets.io",
    "keda": "https://kedacore.github.io/charts",
    "cert-manager": "https://charts.jetstack.io",
    "postgres": "https://charts.bitnami.com/bitnami",
    "valkey": "https://charts.bitnami.com/bitnami",
    "redpanda": "https://charts.redpanda.com",
    "opensearch": "https://opensearch-project.github.io/helm-charts",
    "clickhouse": "https://charts.bitnami.com/bitnami",
    "datahub": "https://helm.datahubproject.io",
    "prometheus": "https://prometheus-community.github.io/helm-charts",
    "loki": "https://grafana.github.io/helm-charts",
    "tempo": "https://grafana.github.io/helm-charts",
    "grafana": "https://grafana.github.io/helm-charts",
    "alloy": "https://grafana.github.io/helm-charts",
    "langfuse": "https://langfuse.github.io/langfuse-k8s",
    "jenkins": "https://charts.jenkins.io",
}


def _load_catalog() -> dict:
    loaded = yaml.safe_load(CATALOG_FILE.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), "releases.yaml must parse as a dict"
    return loaded


def test_releases_yaml_parses() -> None:
    assert CATALOG_FILE.is_file()
    assert isinstance(_load_catalog(), dict)


def test_every_chart_entry_has_name_version_repo() -> None:
    catalog = _load_catalog()
    charts = catalog.get("charts")
    assert isinstance(charts, list) and charts, "catalog must list charts"
    for entry in charts:
        assert set(entry) >= {"name", "version", "repo"}, f"entry missing name/version/repo: {entry}"
        assert isinstance(entry["name"], str) and entry["name"]
        assert isinstance(entry["version"], str) and entry["version"]
        assert isinstance(entry["repo"], str) and entry["repo"].startswith("https://")


def test_no_latest_anywhere() -> None:
    text = CATALOG_FILE.read_text(encoding="utf-8")
    assert "latest" not in text.lower(), "immutable-pin rule rejects `latest`"


def test_versions_match_test_asserted_pins() -> None:
    catalog = _load_catalog()
    assert catalog.get("versions") == EXPECTED_VERSIONS
    by_name = {entry["name"]: entry["version"] for entry in catalog.get("charts", [])}
    for name, version in EXPECTED_CHART_VERSIONS.items():
        assert by_name.get(name) == version, f"chart {name} must stay pinned at {version}"


def test_install_stage_components_resolve_or_reported_missing() -> None:
    catalog = _load_catalog()
    by_name: dict[str, list[dict]] = {}
    for entry in catalog.get("charts", []):
        by_name.setdefault(entry["name"], []).append(entry)
    for component in INSTALL_STAGE_CHARTS:
        pinned = by_name.get(component, [])
        if component in STILL_MISSING:
            assert not pinned, f"{component} is reported missing but also pinned"
        else:
            assert len(pinned) == 1, f"{component} must resolve to exactly one pinned entry"
    # The missing report must be exact: no extras, no omissions, no duplicates.
    assert sorted(STILL_MISSING) == sorted(set(STILL_MISSING))
    unresolved = [c for c in INSTALL_STAGE_CHARTS if c not in by_name]
    assert sorted(unresolved) == sorted(STILL_MISSING), (
        f"missing report drift: unresolved={sorted(unresolved)} report={sorted(STILL_MISSING)}"
    )


def test_catalog_has_no_duplicate_chart_names() -> None:
    catalog = _load_catalog()
    names = [entry["name"] for entry in catalog.get("charts", [])]
    assert len(names) == len(set(names)), f"duplicate chart names: {names}"


def test_repos_match_test_asserted_pins() -> None:
    catalog = _load_catalog()
    by_name = {entry["name"]: entry["repo"] for entry in catalog.get("charts", [])}
    for name, repo in EXPECTED_CHART_REPOS.items():
        assert by_name.get(name) == repo, f"chart {name} must use repo {repo}"
