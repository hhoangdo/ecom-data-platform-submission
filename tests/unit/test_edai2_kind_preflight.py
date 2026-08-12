from __future__ import annotations

import importlib.util
import re
import subprocess
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LEAN_IMAGE_MAX_BYTES = 512 * 1024 * 1024


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
        "containers/edai2/Dockerfile.kind-retrieval",
        "containers/edai2/Dockerfile.kind-retrieval.dockerignore",
        "containers/edai2/kind-retrieval-requirements.txt",
    )

    assert all((REPOSITORY_ROOT / path).is_file() for path in required_paths)


def test_kind_retrieval_image_has_a_small_locked_dependency_boundary() -> None:
    dockerfile = (REPOSITORY_ROOT / "containers/edai2/Dockerfile.kind-retrieval").read_text(encoding="utf-8")
    requirements = (REPOSITORY_ROOT / "containers/edai2/kind-retrieval-requirements.txt").read_text(encoding="utf-8")

    assert "python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c" in dockerfile
    assert "AS retrieval_agent_kind" in dockerfile
    assert "USER 10001:10001" in dockerfile
    assert "PYTHONPATH=/app/src" in dockerfile
    assert "pip install --no-cache-dir -r containers/edai2/kind-retrieval-requirements.txt" in dockerfile
    assert "pip install --no-cache-dir ." not in dockerfile
    assert all(line and "==" in line for line in requirements.splitlines())
    assert not re.search(r"^(feast|sentence-transformers|torch|pyarrow|pandas|dbt-|langfuse)==", requirements, re.MULTILINE)


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


def test_kind_preflight_rejects_resource_quota_contract_drift() -> None:
    module = _preflight_module()
    documents = [
        {"kind": "Namespace", "metadata": {"name": "edai2-lean"}},
        {
            "kind": "ResourceQuota",
            "metadata": {"name": "edai2-lean-bounds", "namespace": "edai2-lean"},
            "spec": {
                "hard": {
                    "requests.cpu": "7",
                    "requests.memory": "16Gi",
                    "limits.cpu": "10",
                    "limits.memory": "22Gi",
                    "pods": "30",
                    "persistentvolumeclaims": "8",
                    "requests.storage": "20Gi",
                    "services.loadbalancers": "0",
                }
            },
        },
        {
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
        },
        {
            "kind": "Service",
            "metadata": {"name": "edai2-retrieval-kind"},
            "spec": {"type": "ClusterIP"},
        },
    ]

    with pytest.raises(ValueError, match="resource quota contract"):
        module.build_report(documents)


def test_kind_runner_size_gates_and_verifies_the_loaded_node_image() -> None:
    text = (REPOSITORY_ROOT / "scripts/kind/run_edai2_lean.ps1").read_text(encoding="utf-8")

    build = "docker build --file containers/edai2/Dockerfile.kind-retrieval --target retrieval_agent_kind"
    create = "kind create cluster"
    load = "Invoke-KindImageLoad -Image edai2/retrieval-agent:kind-local"
    apply = "apply -f infra/kind/edai2-lean/namespace.yaml"
    assert build in text
    assert "$MaxImageBytes = 536870912" in text
    assert "docker image inspect" in text
    assert "crictl images --output=json" in text
    assert ".images | Where-Object" in text
    assert "$NodeImageId -ne $HostImageId" not in text
    build_position = text.index(build)
    create_position = text.index(create, build_position)
    load_position = text.index(load, create_position)
    apply_position = text.index(apply, load_position)
    assert build_position < create_position < load_position < apply_position


def test_kind_runner_cleanup_covers_partial_create_and_all_owned_artifacts() -> None:
    text = (REPOSITORY_ROOT / "scripts/kind/run_edai2_lean.ps1").read_text(encoding="utf-8")

    assert text.index("$ClusterCreateAttempted = $true") < text.index("kind create cluster")
    assert "kind get clusters" in text
    assert "port-forward.pid" in text
    assert "Remove-Item -LiteralPath $PidPath" in text
    assert "Remove-Item -LiteralPath $Kubeconfig" in text
    assert "requests.storage" in text
    assert "rtk proxy kubectl" in text


def test_kind_runner_is_valid_powershell() -> None:
    runner = REPOSITORY_ROOT / "scripts/kind/run_edai2_lean.ps1"
    command = f"""
$tokens = $null
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile('{runner.as_posix()}', [ref]$tokens, [ref]$errors) | Out-Null
if ($errors.Count -ne 0) {{ $errors | ForEach-Object {{ Write-Error $_.Message }}; exit 1 }}
exit 0
"""

    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_kind_runner_rejects_zero_exit_kind_load_error_before_apply() -> None:
    runner = REPOSITORY_ROOT / "scripts/kind/run_edai2_lean.ps1"
    command = f"""
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile('{runner.as_posix()}', [ref]$tokens, [ref]$errors)
$definition = $ast.Find({{ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Assert-KindImageLoadOutput' }}, $true)
if ($null -eq $definition) {{ throw 'missing image-load output guard' }}
. ([scriptblock]::Create($definition.Extent.Text))
try {{
    Assert-KindImageLoadOutput @('Image loading...', 'Error: context deadline exceeded')
    throw 'zero-exit Kind error was accepted'
}} catch {{
    if ($_.Exception.Message -notmatch 'kind image load emitted Error') {{ throw }}
}}
exit 0
"""

    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    text = runner.read_text(encoding="utf-8")
    assert text.index("Invoke-KindImageLoad") < text.index("apply -f infra/kind/edai2-lean/namespace.yaml")


def test_kind_image_loader_captures_native_stderr_without_terminating() -> None:
    text = (REPOSITORY_ROOT / "scripts/kind/run_edai2_lean.ps1").read_text(encoding="utf-8")
    start = text.index("function Invoke-KindImageLoad")
    end = text.index("function Convert-StorageToBytes", start)
    function_text = text[start:end]

    assert "$PreviousErrorActionPreference = $ErrorActionPreference" in function_text
    assert "$ErrorActionPreference = 'Continue'" in function_text
    assert "finally { $ErrorActionPreference = $PreviousErrorActionPreference }" in function_text
