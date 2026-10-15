from __future__ import annotations

import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
OVERLAY = ROOT / "infra/kustomize/llmd/overlays/cpu"


def _rendered_documents() -> list[dict]:
    result = subprocess.run(
        ["kubectl", "kustomize", str(OVERLAY)],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return [item for item in yaml.safe_load_all(result.stdout) if item]


def test_primary_model_ingress_is_gateway_only() -> None:
    rendered = _rendered_documents()
    policies = [item for item in rendered if item.get("kind") == "NetworkPolicy"]
    assert len(policies) == 1
    policy = policies[0]
    assert policy["metadata"]["name"] == "llmd-primary-gateway-only"
    assert policy["metadata"]["namespace"] == "edai2"
    assert policy["spec"]["podSelector"] == {"matchLabels": {"app": "llmd-primary"}}
    assert policy["spec"]["policyTypes"] == ["Ingress"]
    assert policy["spec"]["ingress"] == [{
        "from": [{"podSelector": {"matchLabels": {"edai2.private-gateway": "true"}}}],
        "ports": [{"protocol": "TCP", "port": 8000}],
    }]
    assert "egress" not in policy["spec"]


def test_gateway_parameters_label_only_generated_gateway_pods() -> None:
    parameters = yaml.safe_load((ROOT / "infra/agentgateway/edai2/parameters.yaml").read_text(encoding="utf-8"))
    labels = parameters["spec"]["deployment"]["spec"]["template"]["metadata"]["labels"]
    assert labels == {"edai2.private-gateway": "true"}

