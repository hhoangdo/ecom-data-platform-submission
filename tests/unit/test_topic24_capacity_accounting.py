import pytest
from pathlib import Path
import yaml

from scripts.gke.topic24_capacity import pod_requests, workload_totals
import scripts.gke.topic24_capacity as capacity


def container(cpu, memory):
    return {"name": "fixture", "resources": {"requests": {"cpu": cpu, "memory": memory}}}


def test_init_peak_and_restartable_sidecar_are_counted():
    pod = {"containers": [container("200m", "256Mi")], "initContainers": [
        {**container("50m", "128Mi"), "restartPolicy": "Always"}, container("1", "512Mi")]}
    assert pod_requests(pod) == (1.05, 0.625)


def test_missing_requests_cannot_disappear_from_capacity():
    with pytest.raises(ValueError, match="Unbounded"):
        pod_requests({"containers": [{"name": "missing"}]})


def test_daemonsets_and_rollout_surge_use_eligible_nodes_and_peak_replicas():
    docs = [{"kind": "DaemonSet", "metadata": {"name": "atelet"}, "spec": {"template": {
        "spec": {"containers": [container("50m", "128Mi")]}}}},
        {"kind": "Deployment", "metadata": {"name": "controller"}, "spec": {"replicas": 1,
        "template": {"spec": {"containers": [container("100m", "128Mi")]}}}}]
    result = workload_totals(docs, eligible_nodes=2, peak=True)
    assert result["cpu"] == pytest.approx(0.3)
    assert result["memory_gib"] == 0.5


def test_jobs_are_serialized_separately_from_steady_workloads():
    job = {"kind": "Job", "metadata": {"name": "fixture"}, "spec": {"template": {
        "spec": {"containers": [container("1", "4Gi")]}}}}
    assert workload_totals([job], eligible_nodes=1, peak=False)["cpu"] == 0
    assert workload_totals([job], eligible_nodes=1, peak=True)["cpu"] == 1


def test_null_initcontainers_matches_kubernetes_empty_list():
    assert pod_requests({"containers": [container("100m", "128Mi")], "initContainers": None}) == (0.1, 0.125)


def test_vault_remains_one_bounded_server_with_bounded_injector():
    values = yaml.safe_load((Path(__file__).resolve().parents[2] / "infra/helm/edai2/values/vault.yaml").read_text())
    assert values["server"]["ha"]["replicas"] == 1
    assert values["server"]["resources"]["requests"]["cpu"] == "100m"
    assert values["injector"]["resources"]["requests"]["memory"] == "128Mi"


def test_helm_test_hook_pods_are_not_steady_platform_runtime():
    pod = {"kind": "Pod", "metadata": {"name": "hook", "annotations": {"helm.sh/hook": "test"}},
           "spec": {"containers": [container("50m", "128Mi")]}}
    assert workload_totals([pod], eligible_nodes=2, peak=False)["cpu"] == 0
    assert workload_totals([pod], eligible_nodes=2, peak=True)["cpu"] == 0.05


def test_vault_injection_requests_are_in_the_effective_pod_projection():
    doc = {"kind": "Deployment", "metadata": {"name": "kagent-controller"}, "spec": {"replicas": 1,
        "template": {"metadata": {"annotations": {"vault.hashicorp.com/agent-inject": "true",
        "vault.hashicorp.com/agent-requests-cpu": "50m", "vault.hashicorp.com/agent-requests-mem": "128Mi"}},
        "spec": {"containers": [container("100m", "128Mi")]}}}}
    assert workload_totals([doc], eligible_nodes=2, peak=False)["cpu"] == pytest.approx(0.15)


def test_generated_workerpool_uses_admission_defaults_and_maximum_scale():
    docs = [
        {"kind": "WorkerPool", "metadata": {"name": "pool", "namespace": "kagent"}, "spec": {"replicas": 1}},
        {"kind": "ScaledObject", "metadata": {"namespace": "kagent"}, "spec": {
            "maxReplicaCount": 2, "scaleTargetRef": {"kind": "WorkerPool", "name": "pool"}}},
        {"kind": "LimitRange", "metadata": {"namespace": "kagent"}, "spec": {"limits": [
            {"type": "Container", "defaultRequest": {"cpu": "100m", "memory": "256Mi"}}]}}]
    projected = capacity.managed_projections(docs)
    assert workload_totals(projected, eligible_nodes=2, peak=False)["cpu"] == pytest.approx(0.2)


def test_null_template_annotations_have_no_injection():
    doc = {"kind": "Deployment", "metadata": {"name": "fixture"}, "spec": {"replicas": 1,
        "template": {"metadata": {"annotations": None}, "spec": {"containers": [container("100m", "128Mi")]}}}}
    assert workload_totals([doc], eligible_nodes=2, peak=False)["cpu"] == 0.1
