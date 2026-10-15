"""Effective Pod requests and phase peaks for the approved Topic 24 envelope."""
from __future__ import annotations

import math
import copy


def _quantity(value: object, *, memory: bool) -> float:
    text = str(value)
    suffixes = {"Ki": 2**10, "Mi": 2**20, "Gi": 2**30, "Ti": 2**40,
                "K": 10**3, "M": 10**6, "G": 10**9, "T": 10**12}
    if memory:
        for suffix, multiplier in suffixes.items():
            if text.endswith(suffix):
                return float(text[:-len(suffix)]) * multiplier / 2**30
        return float(text) / 2**30
    return float(text[:-1]) / 1000 if text.endswith("m") else float(text)


def _requests(container: dict) -> tuple[float, float]:
    resources = container.get("resources", {})
    requests, limits = resources.get("requests", {}), resources.get("limits", {})
    values = [requests.get(key, limits.get(key)) for key in ("cpu", "memory")]
    if any(value is None for value in values):
        raise ValueError(f"Unbounded container {container.get('name')}")
    return _quantity(values[0], memory=False), _quantity(values[1], memory=True)


def pod_requests(pod: dict) -> tuple[float, float]:
    app = [0.0, 0.0]
    for container in pod.get("containers") or []:
        app = [a + b for a, b in zip(app, _requests(container))]
    sidecars, init_peak = [0.0, 0.0], [0.0, 0.0]
    for container in pod.get("initContainers") or []:
        current = _requests(container)
        if container.get("restartPolicy") == "Always":
            sidecars = [a + b for a, b in zip(sidecars, current)]
            current = sidecars
        else:
            current = [a + b for a, b in zip(sidecars, current)]
        init_peak = [max(a, b) for a, b in zip(init_peak, current)]
    overhead = pod.get("overhead", {})
    return tuple(max(a + s, i) + _quantity(overhead.get(key, 0), memory=key == "memory")
                 for a, s, i, key in zip(app, sidecars, init_peak, ("cpu", "memory")))


def workload_totals(documents: list[dict], *, eligible_nodes: int, peak: bool) -> dict:
    total = {"cpu": 0.0, "memory_gib": 0.0, "workloads": []}
    for doc in documents:
        kind, spec = doc.get("kind"), doc.get("spec", {})
        if kind not in ("Deployment", "StatefulSet", "DaemonSet", "Job", "Pod"):
            continue
        if kind == "Job" and not peak:
            continue
        if not peak and doc.get("metadata", {}).get("annotations", {}).get("helm.sh/hook"):
            continue
        count = eligible_nodes if kind == "DaemonSet" else int(spec.get("replicas", 1))
        if kind == "Job":
            count = int(spec.get("parallelism", 1))
        if peak and kind == "Deployment" and count:
            strategy = spec.get("strategy", {})
            if strategy.get("type", "RollingUpdate") == "RollingUpdate":
                surge = strategy.get("rollingUpdate", {}).get("maxSurge", "25%")
                count += math.ceil(count * float(surge[:-1]) / 100) if isinstance(surge, str) and surge.endswith("%") else int(surge)
        if not count:
            continue
        pod = copy.deepcopy(spec if kind == "Pod" else spec["template"]["spec"])
        annotations = (doc.get("metadata", {}) if kind == "Pod" else spec["template"].get("metadata", {})).get("annotations") or {}
        if annotations.get("vault.hashicorp.com/agent-inject") == "true" and not any(
                c.get("name") == "vault-agent" for c in pod.get("containers", [])):
            cpu_request, memory_request = (annotations.get("vault.hashicorp.com/agent-requests-" + suffix)
                                           for suffix in ("cpu", "mem"))
            if not cpu_request or not memory_request:
                raise ValueError("Unbounded projected Vault Agent injection")
            pod["containers"].append({"name": "vault-agent", "resources": {"requests": {
                "cpu": cpu_request, "memory": memory_request}}})
        cpu, memory = pod_requests(pod)
        total["cpu"] += cpu * count
        total["memory_gib"] += memory * count
        total["workloads"].append({"name": doc.get("metadata", {}).get("name"), "kind": kind,
                                   "replicas": count, "cpu": cpu * count, "memory_gib": memory * count})
    return total


def managed_projections(documents: list[dict]) -> list[dict]:
    """Project pinned controller Pods from their real admission and Gateway inputs."""
    result, seen = [], set()
    for doc in documents:
        kind, metadata = doc.get("kind"), doc.get("metadata", {})
        namespace, name = metadata.get("namespace"), metadata.get("name")
        if kind not in ("WorkerPool", "Gateway") or (kind, namespace, name) in seen:
            continue
        seen.add((kind, namespace, name))
        if kind == "WorkerPool":
            limits = [entry for d in documents if d.get("kind") == "LimitRange" and d.get("metadata", {}).get("namespace") == namespace
                      for entry in d["spec"]["limits"] if entry["type"] == "Container"]
            if len(limits) != 1:
                raise ValueError("WorkerPool needs one unambiguous admission default")
            resources = {"requests": limits[0]["defaultRequest"]}
            replicas = max([doc["spec"].get("replicas", 1)] + [d["spec"]["maxReplicaCount"]
                for d in documents if d.get("kind") == "ScaledObject" and d.get("metadata", {}).get("namespace") == namespace
                and d["spec"].get("scaleTargetRef", {}).get("kind") == "WorkerPool"
                and d["spec"]["scaleTargetRef"].get("name") == name])
        else:
            reference = doc["spec"]["infrastructure"]["parametersRef"]
            params = next(d for d in documents if d.get("kind") == "AgentgatewayParameters"
                and d.get("metadata", {}).get("namespace") == namespace and d["metadata"]["name"] == reference["name"])
            resources, replicas = params["spec"]["resources"], 1
        result.append({"kind": "Deployment", "metadata": {"name": "projection-" + name, "namespace": namespace},
            "spec": {"replicas": replicas, "template": {"spec": {"containers": [
                {"name": "generated", "resources": resources}]}}}})
    return result
