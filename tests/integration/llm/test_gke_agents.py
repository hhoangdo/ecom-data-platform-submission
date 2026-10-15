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


def test_gateway_matrix_scopes_five_strict_keys_and_denies_the_other_twenty_pairs() -> None:
    """Route selectors and CEL metadata checks admit five pairs and reject the other twenty."""
    policies = _documents(ROOT / "infra/agentgateway/edai2/policies.yaml")
    expected = {
        "model-route": "model-route",
        "retrieval-mcp": "retrieval-mcp",
        "drift-mcp": "drift-mcp",
        "coordinator-specialist": "coordinator-specialist",
        "facade-coordinator": "facade-coordinator",
    }
    assert len(policies) == 5
    observed = set()
    for item in policies:
        assert item["kind"] == "AgentgatewayPolicy"
        credential = item["metadata"]["name"].removeprefix("auth-")
        route = expected[credential]
        spec = item["spec"]
        assert spec["targetRefs"] == [{
            "group": "gateway.networking.k8s.io", "kind": "HTTPRoute",
            "name": {
                "model-route": "model-route", "retrieval-mcp": "retrieval-mcp-route",
                "drift-mcp": "drift-mcp-route", "coordinator-specialist": "coordinator-specialist-route",
                "facade-coordinator": "facade-coordinator-route",
            }[credential],
        }]
        auth = spec["traffic"]["apiKeyAuthentication"]
        assert auth["mode"] == "Strict"
        assert auth["secretSelector"]["matchLabels"] == {"edai2.gateway-auth-route": route}
        authorization = spec["traffic"]["authorization"]
        assert authorization["action"] == "Require"
        expressions = authorization["policy"]["matchExpressions"]
        assert expressions == [f"apiKey.route == '{route}'"]
        if route == "model-route":
            assert spec["backend"]["auth"] == {"secretRef": {"name": "kagent-model-route-key"}}
        observed.add((credential, route))
    assert observed == set(expected.items())
    allowed_pairs = {
        (credential, key_route)
        for credential, route in expected.items()
        for key_route in expected.values()
        if f"apiKey.route == '{route}'" == f"apiKey.route == '{key_route}'"
    }
    assert allowed_pairs == set(expected.items())
    assert len(allowed_pairs) == 5
    assert len(expected) ** 2 - len(allowed_pairs) == 20


def test_gateway_keys_are_projected_as_route_metadata_json() -> None:
    """A plain or cross-route Secret would make strict route selectors accept the wrong key."""
    files = sorted((ROOT / "infra/security/external-secrets").glob("gateway-auth-*.yaml"))
    assert len(files) == 5
    expected = {
        "model-route": ("gateway-auth-model-route", "edai2/kagent/gateway-keys", "model-api-key"),
        "retrieval-mcp": ("gateway-auth-retrieval-mcp", "edai2/kagent/gateway-keys", "support-authorization"),
        "drift-mcp": ("gateway-auth-drift-mcp", "edai2/kagent/gateway-keys", "drift-authorization"),
        "coordinator-specialist": ("gateway-auth-coordinator-specialist", "edai2/kagent/gateway-keys", "coordinator-authorization"),
        "facade-coordinator": ("gateway-auth-facade-coordinator", "edai2/facade/gateway-entry", "authorization"),
    }
    observed = {}
    for path in files:
        item = _documents(path)[0]
        route = item["metadata"]["labels"]["edai2.gateway-auth-route"]
        name, vault_path, property_name = expected[route]
        assert item["spec"]["target"]["name"] == name
        assert item["spec"]["target"]["template"]["metadata"]["labels"] == {
            "edai2.gateway-auth-route": route
        }
        data = item["spec"]["data"]
        assert len(data) == 1 and data[0]["secretKey"] == "gatewayKey"
        observed[route] = (data[0]["remoteRef"]["key"], data[0]["remoteRef"]["property"])
        assert item["spec"]["target"]["template"]["data"][route] == (
            f'{{{{ dict "key" .gatewayKey "metadata" (dict "route" "{route}") | toJson }}}}'
        )
        assert observed[route] == (vault_path, property_name)
    assert set(observed) == set(expected)


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
        assert item["metadata"]["namespace"] == "edai2"
        assert "contextTokens" not in spec  # Not part of the pinned ModelConfig API.
        assert spec["openAI"]["baseUrl"] == "http://edai2-private-gateway.edai2.svc.cluster.local:8080/v1"
        assert spec["apiKeySecret"] == "kagent-model-route-key"
        assert spec["apiKeySecretKey"] == "api-key"

    worker = _documents(ROOT / "infra/kagent/edai2/workerpool-scaledobject.yaml")
    assert worker[0]["metadata"]["name"] == "edai2-agents"
    assert worker[0]["spec"]["ateomImage"] == "ghcr.io/kagent-dev/substrate/ateom-gvisor:v0.0.6"
    assert worker[1]["spec"]["scaleTargetRef"] == {
        "apiVersion": "ate.dev/v1alpha1", "kind": "WorkerPool", "name": "edai2-agents"
    }
    assert worker[1]["spec"]["pollingInterval"] == 15
    assert worker[1]["spec"]["cooldownPeriod"] == 60
    assert worker[1]["spec"]["triggers"] == [{
        "type": "prometheus",
        "metadata": {
            "serverAddress": "http://prometheus-server.edai2.svc.cluster.local",
            "metricName": "edai2_pending_chat_requests",
            "threshold": "1",
            "query": "sum(edai2_pending_chat_requests)",
        },
    }]

    overlay = ROOT / "infra/kustomize/llmd/overlays/cpu"
    rendered_sources = "\n".join(path.read_text(encoding="utf-8") for path in overlay.glob("*.yaml"))
    assert "nvidia.com/gpu" not in rendered_sources
    assert "--max-model-len" in rendered_sources and '"4096"' in rendered_sources
    assert "runtimeClassName" not in rendered_sources
    assert "comparison: 0" in rendered_sources
    assert "primary: 1" in rendered_sources
    assert "llm-d-inference-scheduler:v0.8.0" not in rendered_sources
    cpu_image = "ghcr.io/llm-d/llm-d-cpu:v0.7.0@sha256:f4abcce2b3a3c00521d220dfeabe7aeb5b800823451f8f49fc2b3f9cb5441584"
    cache_image = "python:3.14.8-slim-trixie@sha256:cfe2e24a75302a15934d37c2d86412893c0aa934dc3a97cbb439d04c01890ca9"
    assert f"image: {cpu_image}" in (overlay / "patch-primary.yaml").read_text(encoding="utf-8")
    assert f"image: {cpu_image}" in (overlay / "patch-comparison.yaml").read_text(encoding="utf-8")
    assert f"image: {cache_image}" in (overlay / "patch-model-cache-init.yaml").read_text(encoding="utf-8")
    assert sum("image:" in line for line in rendered_sources.splitlines()) == 3


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
