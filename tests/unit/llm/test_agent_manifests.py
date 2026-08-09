"""Static contracts for the five Topic 14 SandboxAgent resources."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[3]
VALUES = {
    "retrieval": ROOT / "infra/helm/edai2/values/retrieval-agent.yaml",
    "drift": ROOT / "infra/helm/edai2/values/drift-agent.yaml",
    "coordinator": ROOT / "infra/helm/edai2/values/coordinator-agent.yaml",
}


def _documents() -> dict[str, dict[str, object]]:
    for path in VALUES.values():
        assert path.is_file(), f"missing Topic 14 values file: {path.relative_to(ROOT)}"
    return {
        name: yaml.safe_load(path.read_text(encoding="utf-8"))
        for name, path in VALUES.items()
    }


def _agents(documents: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    return [
        agent
        for document in documents.values()
        for agent in document["sandboxAgents"]  # type: ignore[index]
    ]


def test_five_resources_have_exactly_three_logical_identities() -> None:
    agents = _agents(_documents())

    assert {agent["resourceName"] for agent in agents} == {
        "support",
        "drift",
        "coordinator-v1-primary",
        "coordinator-v2-primary",
        "coordinator-v1-comparison",
    }
    assert {agent["logicalAgent"] for agent in agents} == {
        "retrieval",
        "drift",
        "coordinator",
    }


def test_every_agent_has_the_locked_substrate_runtime_and_snapshot_contract() -> None:
    agents = _agents(_documents())

    for agent in agents:
        sandbox = agent["sandboxAgent"]
        assert sandbox["platform"] == "substrate"
        assert sandbox["type"] == "Declarative"
        assert sandbox["declarative"]["runtime"] == "go"
        assert sandbox["substrate"]["workerPoolRef"]["name"] == "edai2-agents"
        assert agent["snapshot"]["prefix"] == "agent-substrate"
        assert agent["snapshot"]["logicalAgent"] == agent["logicalAgent"]
        assert agent["snapshot"]["runtimeVariant"] == agent["runtimeVariant"]
        assert agent["snapshot"]["suffix"] == "/"

    assert {
        (agent["resourceName"], agent["runtimeVariant"], agent["modelConfigRef"])
        for agent in agents
    } == {
        ("support", "v1-primary", "default-model-config"),
        ("drift", "v1-primary", "default-model-config"),
        ("coordinator-v1-primary", "v1-primary", "default-model-config"),
        ("coordinator-v2-primary", "v2-primary", "default-model-config"),
        ("coordinator-v1-comparison", "v1-comparison", "edai2-comparison"),
    }


def test_agent_values_are_fail_closed_and_gateway_only() -> None:
    documents = _documents()
    agents = _agents(documents)
    allowed_domains = {
        "kube-dns.kube-system.svc.cluster.local",
        "api.ate-system.svc.cluster.local",
        "atenet-router.ate-system.svc.cluster.local",
        "agentgateway-proxy.edai2.svc.cluster.local",
    }

    for document in documents.values():
        assert document["namespace"] == "edai2"
        assert document["proxy"]["url"] == (
            "http://agentgateway-proxy.edai2.svc.cluster.local:15000"
        )
        assert document["substrate"]["bucketName"] == ""
        assert "${" not in yaml.safe_dump(document)

    for agent in agents:
        assert set(agent["sandboxAgent"]["sandbox"]["network"]["allowedDomains"]) == allowed_domains
        env = {entry["name"]: entry["value"] for entry in agent["environment"]}
        assert env["EDAI2_LOGICAL_AGENT"] == agent["logicalAgent"]
        assert env["EDAI2_RUNTIME_VARIANT"] == agent["runtimeVariant"]
        rendered = (
            "gs://edai2-sentinel-bucket/"
            f"{agent['snapshot']['prefix']}/{agent['snapshot']['logicalAgent']}/"
            f"{agent['snapshot']['runtimeVariant']}{agent['snapshot']['suffix']}"
        )
        assert rendered.endswith(f"/{agent['runtimeVariant']}/")

    sandbox_text = yaml.safe_dump([agent["sandboxAgent"] for agent in agents])
    for forbidden in ("llm-d", "retrieval-mcp", "drift-mcp", "feast", "postgres", "valkey"):
        assert forbidden not in sandbox_text


def test_mcp_routes_and_credentials_have_intended_disjoint_bindings() -> None:
    documents = _documents()
    retrieval = documents["retrieval"]
    drift = documents["drift"]
    coordinator = documents["coordinator"]

    assert retrieval["remoteMcpServers"] == [{
        "name": "retrieval-mcp",
        "transport": "STREAMABLE_HTTP",
        "url": "http://retrieval-mcp.edai2.svc.cluster.local:8080/mcp",
        "credential": "retrievalMcp",
    }]
    assert drift["remoteMcpServers"] == [{
        "name": "drift-mcp",
        "transport": "STREAMABLE_HTTP",
        "url": "http://drift-mcp.edai2.svc.cluster.local:8080/mcp",
        "credential": "driftMcp",
    }]
    assert coordinator["remoteMcpServers"] == []

    references = {
        name: tuple(reference.values())
        for document in documents.values()
        for name, reference in document["credentialReferences"].items()
    }
    assert references == {
        "model": ("kagent-model-route-key", "api-key"),
        "retrievalMcp": ("kagent-gateway-keys", "support-retrieval"),
        "driftMcp": ("kagent-gateway-keys", "drift-detect"),
        "coordinatorSpecialist": ("kagent-gateway-keys", "coordinator-to-specialist"),
        "facadeCoordinator": ("facade-gateway-key", "authorization"),
    }
    assert len(set(references.values())) == 5

    bindings = {
        agent["resourceName"]: agent["credentialBindings"]
        for agent in _agents(documents)
    }
    assert bindings == {
        "support": ["retrievalMcp"],
        "drift": ["driftMcp"],
        "coordinator-v1-primary": ["coordinatorSpecialist"],
        "coordinator-v2-primary": ["coordinatorSpecialist"],
        "coordinator-v1-comparison": ["coordinatorSpecialist"],
    }
    assert coordinator["facadeCredentialBinding"] == "facadeCoordinator"
    assert all("model" not in binding for binding in bindings.values())
    assert all("facadeCoordinator" not in binding for binding in bindings.values())
