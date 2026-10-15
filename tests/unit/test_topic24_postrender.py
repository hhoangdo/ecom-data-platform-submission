import copy

import pytest
from pathlib import Path
import yaml

from scripts.gke.topic24_postrender import render


def deployment(value="postgresql://topic24-secret-reference.invalid/agentregistry"):
    return {"kind": "Deployment", "metadata": {"name": "agentregistry", "namespace": "edai2"},
            "spec": {"template": {"spec": {"containers": [{"name": "agentregistry", "env": [
                {"name": "AGENT_REGISTRY_DATABASE_URL", "value": value}]}]}}}}


def test_registry_database_marker_is_replaced_by_secret_reference():
    original = deployment()
    result = render([original])
    env = result[0]["spec"]["template"]["spec"]["containers"][0]["env"][0]
    assert env == {"name": "AGENT_REGISTRY_DATABASE_URL", "valueFrom": {
        "secretKeyRef": {"name": "agentregistry", "key": "database-url"}}}
    assert original == deployment()


def test_renderer_rejects_unexpected_literal_database_url():
    with pytest.raises(ValueError, match="database marker"):
        render([deployment("postgresql://unexpected.invalid/db")])


def test_renderer_preserves_unrelated_resources():
    service = {"kind": "Service", "metadata": {"name": "agentregistry"}, "spec": {"type": "ClusterIP"}}
    assert render([service]) == [copy.deepcopy(service)]


def test_registry_chart_omits_namespace_but_adaptation_binds_edai2():
    chart_output = deployment()
    del chart_output["metadata"]["namespace"]
    adapted = render([chart_output])[0]
    assert adapted["metadata"]["namespace"] == "edai2"
    assert "valueFrom" in adapted["spec"]["template"]["spec"]["containers"][0]["env"][0]


def test_owned_chart_workloads_have_bounded_init_and_application_containers():
    doc = {"kind": "Deployment", "metadata": {"name": "ate-controller", "namespace": "edai2",
        "labels": {"app.kubernetes.io/instance": "substrate"}}, "spec": {"template": {"spec": {
        "containers": [{"name": "api"}], "initContainers": [{"name": "init"}]}}}}
    adapted = render([doc])[0]
    for item in adapted["spec"]["template"]["spec"]["containers"] + adapted["spec"]["template"]["spec"]["initContainers"]:
        assert item["resources"]["requests"] == {"cpu": "10m", "memory": "64Mi"}


def test_chart_generated_kagent_modelconfig_is_filtered_without_touching_declared_models():
    chart = {"kind": "ModelConfig", "metadata": {"name": "default-model-config", "namespace": "kagent"}}
    declared = {"kind": "ModelConfig", "metadata": {"name": "default-model-config", "namespace": "edai2"}}
    assert render([chart, declared]) == [declared]


def test_chart_null_initcontainers_is_treated_as_empty():
    doc = {"kind": "Deployment", "metadata": {"name": "fixture", "labels": {
        "app.kubernetes.io/instance": "airflow"}}, "spec": {"template": {"spec": {
        "containers": [{"name": "app"}], "initContainers": None}}}}
    assert render([doc])[0]["spec"]["template"]["spec"]["containers"][0]["resources"]["requests"]["cpu"] == "10m"


def test_substrate_password_adapter_is_on_original_pinned_chart_output():
    doc = {"kind": "Deployment", "metadata": {"name": "ate-api-server-deployment", "namespace": "edai2"},
           "spec": {"template": {"spec": {"containers": [{"name": "ate-api-server", "args": ["--redis-cluster-address=@env"]}]}}}}
    pod = render([doc])[0]["spec"]["template"]["spec"]
    api = pod["containers"][0]
    assert "--redis-mode=@env" in api["args"]
    assert "--redis-password-file=@env" in api["args"]
    assert {"configMapRef": {"name": "substrate-api-env"}} in api["envFrom"]
    assert pod["volumes"][0]["secret"] == {"secretName": "valkey", "items": [{"key": "password", "path": "password"}]}


def test_legacy_chart_release_labels_and_null_resources_are_bounded():
    doc = {"kind": "Deployment", "metadata": {"name": "feast-feature-server", "labels": {"release": "feast"}},
           "spec": {"template": {"spec": {"containers": [{"name": "feature-server", "resources": None}]}}}}
    assert render([doc])[0]["spec"]["template"]["spec"]["containers"][0]["resources"]["requests"]["cpu"] == "10m"


def test_same_render_substrate_ca_is_shared_without_private_key():
    ca = {"kind": "ConfigMap", "metadata": {"name": "ateapi-ca", "namespace": "edai2"}, "data": {"ca.crt": "PUBLIC-CA"}}
    result = render([ca])
    assert result[-1] == {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {
        "name": "kagent-ateapi-ca", "namespace": "kagent"}, "data": {"ca.crt": "PUBLIC-CA"}}


def test_gke_oidc_discovery_uses_verified_public_system_roots():
    doc = {"kind": "Deployment", "metadata": {"name": "ate-api-server-deployment", "namespace": "edai2"},
           "spec": {"template": {"spec": {"containers": [{"name": "ate-api-server", "args": [
            "--client-jwt-issuer=https://container.googleapis.com/v1/projects/example/locations/us-central1-a/clusters/edai2",
            "--client-jwt-ca-cert=/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"]}]}}}}
    args = render([doc])[0]["spec"]["template"]["spec"]["containers"][0]["args"]
    assert "--client-jwt-ca-cert=" in args
    assert not any("insecure" in arg for arg in args)


def test_kagent_provider_input_is_private_even_before_filtering():
    values = yaml.safe_load((Path(__file__).resolve().parents[2] / "infra/helm/edai2/values/kagent.yaml").read_text())
    assert values["providers"]["openAI"]["model"] == "Qwen/Qwen2.5-1.5B-Instruct"
    assert values["providers"]["openAI"]["config"]["baseUrl"] == "http://edai2-private-gateway.edai2.svc.cluster.local:8080/v1"
