from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from conftest import resolve_live_gke_target


ROOT = Path(__file__).resolve().parents[3]


def _documents(path: Path) -> list[dict]:
    return [item for item in yaml.safe_load_all(path.read_text(encoding="utf-8")) if item]


def test_platform_contract_files_are_present_and_pinned() -> None:
    """Removing the immutable catalog or ingress chart pin breaks the platform contract."""
    catalog = ROOT / "infra/helm/edai2/releases.yaml"
    ingress = ROOT / "infra/helm/edai2/values/ingress-nginx.yaml"
    assert catalog.is_file()
    assert ingress.is_file()
    releases = yaml.safe_load(catalog.read_text(encoding="utf-8"))
    assert releases["versions"] == {
        "gateway_api": "1.5.0",
        "agentgateway": "1.3.1",
        "substrate": "0.0.6",
        "kagent": "0.9.9",
        "agentregistry": "0.3.3",
        "llmd": "v0.7",
        "ingress_nginx_chart": "4.15.1",
    }
    assert yaml.safe_load(ingress.read_text(encoding="utf-8"))["chartVersion"] == "4.15.1"


def test_gateway_matrix_explicitly_denies_every_non_allow_pair() -> None:
    """Deleting a deny policy would permit a credential to reach an unrelated route."""
    policies = _documents(ROOT / "infra/agentgateway/edai2/policies.yaml")
    expected = {
        "model-route": "model",
        "retrieval-mcp": "retrieval-mcp",
        "drift-mcp": "drift-mcp",
        "coordinator-specialist": "a2a-specialist",
        "facade-coordinator": "a2a-facade",
    }
    allow = [item for item in policies if item["spec"]["effect"] == "allow"]
    deny = [item for item in policies if item["spec"]["effect"] == "deny"]
    assert {(item["spec"]["credential"], item["spec"]["routeClass"]) for item in allow} == set(expected.items())
    assert len(deny) == 20
    assert {
        (item["spec"]["credential"], item["spec"]["routeClass"])
        for item in deny
    } == {
        (credential, route)
        for credential in expected
        for route in expected.values()
        if expected[credential] != route
    }
    assert {item["spec"]["statusCode"] for item in deny} <= {401, 403}


def test_gateway_allow_credentials_use_exact_disjoint_secret_keys() -> None:
    """A reused secret key would collapse two independently authorized routes."""
    policies = _documents(ROOT / "infra/agentgateway/edai2/policies.yaml")
    allow = [item for item in policies if item["spec"]["effect"] == "allow"]
    bindings = {
        item["spec"]["credential"]: (item["spec"]["secretName"], item["spec"]["secretKey"])
        for item in allow
    }
    assert bindings == {
        "model-route": ("kagent-model-route-key", "api-key"),
        "retrieval-mcp": ("kagent-gateway-keys", "support-retrieval"),
        "drift-mcp": ("kagent-gateway-keys", "drift-detect"),
        "coordinator-specialist": ("kagent-gateway-keys", "coordinator-to-specialist"),
        "facade-coordinator": ("facade-gateway-key", "authorization"),
    }
    assert len(set(bindings.values())) == len(bindings)


def test_model_configs_workerpool_and_cpu_overlay_are_private_and_bounded() -> None:
    """A GPU, direct llm-d route, or invalid comparison state would violate the CPU contract."""
    configs = _documents(ROOT / "infra/kagent/edai2/model-configs.yaml")
    assert {item["metadata"]["name"] for item in configs} == {
        "default-model-config",
        "edai2-comparison",
    }
    for item in configs:
        spec = item["spec"]
        assert spec["provider"] == "OpenAI"
        assert spec["contextTokens"] == 4096
        assert spec["openAI"]["baseUrl"] == "http://agentgateway-proxy.edai2.svc.cluster.local:15000/v1"
        assert spec["apiKeySecret"] == "kagent-model-route-key"
        assert spec["apiKeySecretKey"] == "api-key"

    worker = _documents(ROOT / "infra/kagent/edai2/workerpool-scaledobject.yaml")
    assert worker[0]["metadata"]["name"] == "edai2-agents"
    assert worker[1]["spec"]["scaleTargetRef"] == {
        "apiVersion": "ate.dev/v1alpha1", "kind": "WorkerPool", "name": "edai2-agents"
    }

    overlay = ROOT / "infra/kustomize/llmd/overlays/cpu"
    rendered_sources = "\n".join(path.read_text(encoding="utf-8") for path in overlay.glob("*.yaml"))
    assert "nvidia.com/gpu" not in rendered_sources
    assert "runtimeClassName" not in rendered_sources
    assert "comparison-core: 0" in rendered_sources
    assert "comparison-model-ab: 1" in rendered_sources
    assert "comparison-factorial: 2" in rendered_sources
    assert "primary-factorial: 2" in rendered_sources
    assert "llm-d-inference-scheduler:v0.8.0" not in rendered_sources
    assert all("v0.7.0" in line for line in rendered_sources.splitlines() if "image:" in line)


def test_topic16_values_render_five_logical_agent_resources() -> None:
    """Changing Topic 14 values must not lose a logical agent or its snapshot contract."""
    values = ROOT / "infra/helm/edai2/values"
    agents: list[dict] = []
    for name in ("retrieval-agent.yaml", "drift-agent.yaml", "coordinator-agent.yaml"):
        loaded = yaml.safe_load((values / name).read_text(encoding="utf-8"))
        agents.extend(loaded["sandboxAgents"])
    assert len(agents) == 5
    assert {item["logicalAgent"] for item in agents} == {"retrieval", "drift", "coordinator"}
    assert next(item for item in agents if item["resourceName"] == "support")["environment"][0] == {
        "name": "EDAI2_LOGICAL_AGENT", "value": "retrieval"
    }
    assert all(item["snapshot"]["prefix"] == "agent-substrate" for item in agents)


def test_live_gke_target_rejects_missing_wrong_and_default_contexts(tmp_path: Path) -> None:
    """Removing explicit validation could make a live test use the user's default context."""
    kubeconfig = tmp_path / "fixture.yaml"
    kubeconfig.write_text(
        yaml.safe_dump({"current-context": "corporate", "contexts": [{"name": "gke_expected"}]}),
        encoding="utf-8",
    )
    with pytest.raises(pytest.UsageError):
        resolve_live_gke_target(live_gke=False, kubeconfig=None, context=None)
    with pytest.raises(pytest.UsageError):
        resolve_live_gke_target(live_gke=True, kubeconfig=str(kubeconfig), context="corporate")
    assert resolve_live_gke_target(live_gke=True, kubeconfig=str(kubeconfig), context="gke_expected") == (
        kubeconfig,
        "gke_expected",
    )


def test_render_only_kubeconfig_uses_an_explicit_non_live_context() -> None:
    """The local Kustomize command must not fall back to a user's default context."""
    fixture = ROOT / "tests/fixtures/kubernetes/render-only-kubeconfig.yaml"
    loaded = yaml.safe_load(fixture.read_text(encoding="utf-8"))
    assert loaded["current-context"] == "render-only"
    assert [item["name"] for item in loaded["contexts"]] == ["render-only"]
    assert loaded["clusters"] == [
        {"name": "render-only", "cluster": {"server": "https://127.0.0.1:65535"}}
    ]
    assert loaded["users"] == [{"name": "render-only", "user": {}}]
    assert "!tests/fixtures/kubernetes/render-only-kubeconfig.yaml" in (
        ROOT / ".gitignore"
    ).read_text(encoding="utf-8")
