"""Fail closed before creating the dedicated local Kind smoke cluster."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml


CLUSTER_NAME = "edai2-lean"
CONTEXT = "kind-edai2-lean"
KUBECONFIG = "tmp/edai2-kind/kubeconfig"
NODE_IMAGE = "kindest/node:v1.35.5@sha256:ce977ae6d65918d0b58a5f8b5e940429c2ce42fa3a5619ec2bbc60b949c0ac95"
LIMITS = {
    "requests_cpu_millicores": 6000,
    "requests_memory_bytes": 16 * 1024**3,
    "limits_cpu_millicores": 10000,
    "limits_memory_bytes": 22 * 1024**3,
    "pods": 30,
    "pvcs": 8,
    "storage_bytes": 20 * 1024**3,
}
RENDER_KUBECONFIG = "tests/fixtures/kubernetes/render-only-kubeconfig.yaml"
RENDER_CONTEXT = "render-only"
EXPECTED_RESOURCE_QUOTA = {
    "requests.cpu": "6",
    "requests.memory": "16Gi",
    "limits.cpu": "10",
    "limits.memory": "22Gi",
    "pods": "30",
    "persistentvolumeclaims": "8",
    "requests.storage": "20Gi",
    "services.loadbalancers": "0",
}


def _quantity(value: Any, *, cpu: bool) -> int:
    """Parse only the bounded Kubernetes quantity forms used by this slice."""

    if not isinstance(value, str) or not value:
        raise ValueError("missing quantity")
    if cpu:
        if value.endswith("m") and value[:-1].isdigit():
            return int(value[:-1])
        if value.replace(".", "", 1).isdigit():
            return int(float(value) * 1000)
        raise ValueError(f"unparseable cpu quantity: {value}")
    for suffix, multiplier in (("Ki", 1024), ("Mi", 1024**2), ("Gi", 1024**3)):
        if value.endswith(suffix) and value[: -len(suffix)].isdigit():
            return int(value[: -len(suffix)]) * multiplier
    raise ValueError(f"unparseable memory/storage quantity: {value}")


def _documents(text: str) -> list[dict[str, Any]]:
    """Load only mapping documents and reject every other rendered value."""

    documents = list(yaml.safe_load_all(text))
    if not documents or any(not isinstance(document, dict) for document in documents):
        raise ValueError("manifest must contain mapping documents")
    return documents


def _hash(path: Path) -> str:
    """Return the SHA-256 of one local manifest."""

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _local_documents(manifest_root: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Read every checked local manifest and retain a deterministic hash inventory."""

    paths = sorted(manifest_root.glob("*.yaml"))
    if not paths:
        raise ValueError("manifest root is empty")
    documents: list[dict[str, Any]] = []
    hashes: dict[str, str] = {}
    for path in paths:
        hashes[path.as_posix()] = _hash(path)
        documents.extend(_documents(path.read_text(encoding="utf-8")))
    return documents, hashes


def _rendered_chart(manifest_root: Path) -> tuple[list[dict[str, Any]], str]:
    """Render the one local chart with an explicit non-default render context."""

    command = [
        "rtk",
        "proxy",
        "helm",
        "--kubeconfig",
        RENDER_KUBECONFIG,
        "--kube-context",
        RENDER_CONTEXT,
        "template",
        "edai2-retrieval-kind",
        "infra/helm/edai2/service-agent",
        "--namespace",
        CLUSTER_NAME,
        "-f",
        str(manifest_root / "retrieval-values.yaml"),
        "--set-string",
        "image.repository=edai2/retrieval-agent",
        "--set-string",
        "image.tag=kind-local",
        "--set",
        "image.pullPolicy=IfNotPresent",
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"helm render failed: {result.stderr.strip()}")
    return _documents(result.stdout), hashlib.sha256(result.stdout.encode("utf-8")).hexdigest()


def _compose_detected(lines: Iterable[str]) -> bool:
    """Detect Docker Compose labels without acting on any listed container."""

    for line in lines:
        item = json.loads(line)
        labels = item.get("Labels", {})
        if isinstance(labels, str):
            if "com.docker.compose." in labels:
                return True
        elif isinstance(labels, dict) and any(key.startswith("com.docker.compose.") for key in labels):
            return True
    return False


def _docker_compose_detected() -> bool:
    """Read Docker's container inventory only."""

    result = subprocess.run(
        ["rtk", "docker", "ps", "--format", "{{json .}}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError("docker inventory failed")
    return _compose_detected(line for line in result.stdout.splitlines() if line.strip())


def _containers(document: dict[str, Any]) -> Iterable[dict[str, Any]]:
    """Yield all ordinary containers from a Pod template or Pod."""

    spec = document.get("spec", {})
    if document.get("kind") == "Deployment":
        spec = spec.get("template", {}).get("spec", {})
    return spec.get("containers", [])


def build_report(documents: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Calculate the bounded resource/service inventory from rendered resources."""

    totals = {
        "requests_cpu_millicores": 0,
        "requests_memory_bytes": 0,
        "limits_cpu_millicores": 0,
        "limits_memory_bytes": 0,
        "pods": 0,
        "pvcs": 0,
        "storage_bytes": 0,
    }
    service_types: list[str] = []
    service_names: list[str] = []
    keda_maxima: list[int] = []
    deployment_names: list[str] = []
    resource_quotas: list[dict[str, Any]] = []
    for document in documents:
        kind = document.get("kind")
        if kind == "Deployment":
            name = document.get("metadata", {}).get("name")
            if not isinstance(name, str):
                raise ValueError("deployment name is missing")
            deployment_names.append(name)
            replicas = document.get("spec", {}).get("replicas", 1)
            if not isinstance(replicas, int) or replicas < 0:
                raise ValueError("deployment replicas must be a non-negative integer")
            totals["pods"] += replicas
            for container in _containers(document):
                resources = container.get("resources", {})
                requests = resources.get("requests", {})
                limits = resources.get("limits", {})
                totals["requests_cpu_millicores"] += _quantity(requests.get("cpu"), cpu=True) * replicas
                totals["requests_memory_bytes"] += _quantity(requests.get("memory"), cpu=False) * replicas
                totals["limits_cpu_millicores"] += _quantity(limits.get("cpu"), cpu=True) * replicas
                totals["limits_memory_bytes"] += _quantity(limits.get("memory"), cpu=False) * replicas
        elif kind == "PersistentVolumeClaim":
            totals["pvcs"] += 1
            storage = document.get("spec", {}).get("resources", {}).get("requests", {}).get("storage")
            totals["storage_bytes"] += _quantity(storage, cpu=False)
        elif kind == "Service":
            name = document.get("metadata", {}).get("name")
            if not isinstance(name, str):
                raise ValueError("service name is missing")
            service_names.append(name)
            service_types.append(document.get("spec", {}).get("type", "ClusterIP"))
        elif kind == "ScaledObject":
            maximum = document.get("spec", {}).get("maxReplicaCount")
            if not isinstance(maximum, int):
                raise ValueError("KEDA maximum is missing")
            keda_maxima.append(maximum)
        elif kind == "ResourceQuota":
            resource_quotas.append(document)
    if any(service_type == "LoadBalancer" for service_type in service_types):
        raise ValueError("LoadBalancer service is forbidden")
    if any(maximum > 1 for maximum in keda_maxima):
        raise ValueError("KEDA maximum exceeds one")
    if deployment_names != ["edai2-retrieval-kind"]:
        raise ValueError("exactly one retrieval deployment is required")
    if service_names != ["edai2-retrieval-kind"]:
        raise ValueError("exactly one retrieval service is required")
    if resource_quotas:
        if len(resource_quotas) != 1:
            raise ValueError("resource quota contract requires exactly one ResourceQuota")
        quota = resource_quotas[0]
        metadata = quota.get("metadata", {})
        if (
            metadata.get("name") != "edai2-lean-bounds"
            or metadata.get("namespace") != CLUSTER_NAME
            or quota.get("spec", {}).get("hard") != EXPECTED_RESOURCE_QUOTA
        ):
            raise ValueError("resource quota contract does not match the locked bounds")
    if any(totals[key] > value for key, value in LIMITS.items()):
        raise ValueError("resource limit exceeded")
    return {"totals": totals, "service_types": service_types, "keda_maxima": keda_maxima}


def main() -> int:
    """Write one sanitized report or fail before Kind cluster creation."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--cluster-name", required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--kubeconfig", required=True)
    parser.add_argument("--manifest-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if (args.cluster_name, args.context, args.kubeconfig) != (CLUSTER_NAME, CONTEXT, KUBECONFIG):
        raise ValueError("Kind preflight requires the owned cluster, context, and kubeconfig")
    if _docker_compose_detected():
        raise RuntimeError("broad Docker Compose workload detected")
    local_documents, hashes = _local_documents(args.manifest_root)
    rendered_documents, rendered_hash = _rendered_chart(args.manifest_root)
    inventory = build_report([*local_documents, *rendered_documents])
    report = {
        "status": "passed",
        "scope": "local preflight; not GKE evidence",
        "cluster": CLUSTER_NAME,
        "context": CONTEXT,
        "kubeconfig": KUBECONFIG,
        "node_image": NODE_IMAGE,
        "manifest_hashes": {**hashes, "helm-template": rendered_hash},
        "broad_compose_detected": False,
        **inventory,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
