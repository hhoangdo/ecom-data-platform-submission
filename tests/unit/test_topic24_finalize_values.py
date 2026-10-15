"""Pinned chart controls required before the Topic 24 runtime lease."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_langfuse_media_length_is_a_kubernetes_environment_string():
    values = yaml.safe_load((ROOT / "infra/helm/edai2/values/langfuse.yaml").read_text())
    assert values["s3"]["mediaUpload"]["maxContentLength"] == "1000000000"


def test_langfuse_uses_local_ddl_for_the_existing_single_node_clickhouse():
    values = yaml.safe_load((ROOT / "infra/helm/edai2/values/langfuse.yaml").read_text())
    assert values["clickhouse"]["deploy"] is False
    assert values["clickhouse"]["cluster"]["enabled"] is False


def test_kagent_uses_external_database_and_pinned_worker():
    values = yaml.safe_load((ROOT / "infra/helm/edai2/values/kagent.yaml").read_text())
    assert values["database"]["postgres"]["urlFile"] == "/vault/secrets/kagent-postgres-url"
    assert values["database"]["postgres"]["bundled"]["enabled"] is False
    assert values["substrateWorkerPool"]["ateomImage"] == "ghcr.io/kagent-dev/substrate/ateom-gvisor:v0.0.6"
    for component in ("kmcp", "kagent-tools", "grafana-mcp", "querydoc", "k8s-agent",
                      "kgateway-agent", "istio-agent", "promql-agent", "observability-agent",
                      "argo-rollouts-agent", "helm-agent", "cilium-policy-agent", "cilium-manager-agent", "cilium-debug-agent", "oauth2-proxy"):
        assert values[component]["enabled"] is False, component
    substrate = values["controller"]["substrate"]
    assert substrate["ateApiEndpoint"] == "dns:///api.edai2.svc:443"
    assert substrate["defaultWorkerPool"] == {"namespace": "kagent", "name": "edai2-agents"}


def test_model_configs_do_not_use_unsupported_context_field():
    docs = list(yaml.safe_load_all((ROOT / "infra/kagent/edai2/model-configs.yaml").read_text()))
    assert len(docs) == 2
    for doc in docs:
        assert doc["metadata"]["namespace"] == "edai2"
        assert "contextTokens" not in doc["spec"]


def test_workerpool_has_the_pinned_image_instead_of_synthetic_platform():
    docs = list(yaml.safe_load_all((ROOT / "infra/kagent/edai2/workerpool-scaledobject.yaml").read_text()))
    pool = docs[0]
    assert pool["metadata"]["namespace"] == "kagent"
    assert pool["spec"] == {"replicas": 1, "ateomImage": "ghcr.io/kagent-dev/substrate/ateom-gvisor:v0.0.6"}


def test_all_remaining_oci_charts_have_verified_artifact_digests():
    catalog = yaml.safe_load((ROOT / "infra/helm/edai2/releases.yaml").read_text())
    charts = {entry["name"]: entry for entry in catalog.get("oci_charts", [])}
    assert set(charts) == {"agentgateway", "agentgateway-crds", "substrate", "substrate-crds", "kagent", "kagent-crds", "agentregistry"}
    for entry in charts.values():
        assert entry["repo"].startswith("oci://")
        assert entry["artifact_digest"].startswith("sha256:")
        assert len(entry["artifact_digest"]) == 71


def test_registry_excludes_bundled_database_and_uses_chart_secret_control():
    values = yaml.safe_load((ROOT / "infra/helm/edai2/values/agentregistry.yaml").read_text())
    assert values["database"]["postgres"]["bundled"]["enabled"] is False
    assert values["config"]["existingSecret"] == "agentregistry"


def test_registry_database_url_does_not_copy_postgres_admin_credentials():
    secret = yaml.safe_load((ROOT / "infra/security/external-secrets/agentregistry.yaml").read_text())
    assert all(entry["remoteRef"]["key"] == "edai2/platform/agentregistry" for entry in secret["spec"]["data"])
    assert 'index . "api-token"' in secret["spec"]["target"]["template"]["data"]["database-url"]
