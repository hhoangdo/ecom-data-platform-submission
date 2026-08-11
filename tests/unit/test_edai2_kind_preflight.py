from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _preflight_module():
    path = REPOSITORY_ROOT / "scripts/kind/preflight_edai2_lean.py"
    spec = importlib.util.spec_from_file_location("edai2_kind_preflight", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_kind_preflight_assets_are_present() -> None:
    required_paths = (
        "infra/kind/edai2-lean/kind-config.yaml",
        "infra/kind/edai2-lean/namespace.yaml",
        "infra/kind/edai2-lean/resource-quota.yaml",
        "infra/kind/edai2-lean/limit-range.yaml",
        "infra/kind/edai2-lean/network-policy.yaml",
        "infra/kind/edai2-lean/retrieval-values.yaml",
        "scripts/kind/preflight_edai2_lean.py",
        "scripts/kind/run_edai2_lean.ps1",
    )

    assert all((REPOSITORY_ROOT / path).is_file() for path in required_paths)


def test_kind_preflight_render_uses_untruncated_proxy_output() -> None:
    module = _preflight_module()
    command = module._rendered_chart.__code__.co_consts

    assert "proxy" in command


def test_kind_preflight_rejects_an_extra_deployment_even_within_quota() -> None:
    module = _preflight_module()
    deployment = {
        "kind": "Deployment",
        "metadata": {"name": "edai2-retrieval-kind"},
        "spec": {
            "replicas": 1,
            "template": {
                "spec": {
                    "containers": [
                        {
                            "resources": {
                                "requests": {"cpu": "100m", "memory": "256Mi"},
                                "limits": {"cpu": "500m", "memory": "512Mi"},
                            }
                        }
                    ]
                }
            },
        },
    }
    extra = {**deployment, "metadata": {"name": "unowned-slice"}}

    with pytest.raises(ValueError, match="exactly one retrieval deployment"):
        module.build_report([deployment, extra])


def test_kind_preflight_rejects_an_extra_cluster_ip_service() -> None:
    module = _preflight_module()
    deployment = {
        "kind": "Deployment",
        "metadata": {"name": "edai2-retrieval-kind"},
        "spec": {
            "replicas": 1,
            "template": {
                "spec": {
                    "containers": [
                        {
                            "resources": {
                                "requests": {"cpu": "100m", "memory": "256Mi"},
                                "limits": {"cpu": "500m", "memory": "512Mi"},
                            }
                        }
                    ]
                }
            },
        },
    }
    service = {
        "kind": "Service",
        "metadata": {"name": "edai2-retrieval-kind"},
        "spec": {"type": "ClusterIP"},
    }
    extra = {**service, "metadata": {"name": "unowned-service"}}

    with pytest.raises(ValueError, match="exactly one retrieval service"):
        module.build_report([deployment, service, extra])
