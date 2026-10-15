"""Narrow, fail-closed adaptation of pinned Topic 24 chart output."""
from __future__ import annotations

import copy
import json
import os
import re
import sys

import yaml
try:
    from scripts.gke.topic24_capacity import _quantity
except ModuleNotFoundError:
    from topic24_capacity import _quantity

REGISTRY_DATABASE_MARKER = "postgresql://topic24-secret-reference.invalid/agentregistry"
SUBSTRATE_API_IMAGE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*@sha256:[0-9a-f]{64}$")
GSA_EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.iam\.gserviceaccount\.com$")
OWNED_RELEASES = {"substrate", "kagent", "agentgateway", "agentregistry", "postgres", "valkey",
                  "redpanda", "opensearch", "clickhouse", "airflow", "feast", "datahub", "prometheus",
                  "loki", "tempo", "grafana", "alloy", "langfuse", "jenkins", "vault",
                  "external-secrets", "cert-manager", "ingress-nginx", "keda"}


def render(documents: list[dict], *, substrate_api_image: str | None = None,
           atelet_wi_annotation: str | None = None) -> list[dict]:
    if substrate_api_image is not None and not SUBSTRATE_API_IMAGE_PATTERN.fullmatch(substrate_api_image):
        raise ValueError("substrate_api_image must be an image reference pinned by a sha256 digest")
    if atelet_wi_annotation is not None and not GSA_EMAIL_PATTERN.fullmatch(atelet_wi_annotation):
        raise ValueError("atelet WI annotation must be a Google service-account email")
    result = [copy.deepcopy(document) for document in documents if not (
        document.get("kind") == "ModelConfig" and document.get("metadata", {}).get("namespace") == "kagent"
        and document.get("metadata", {}).get("name") == "default-model-config")]
    substrate_api_containers = 0
    atelet_service_accounts = 0
    for document in result:
        metadata = document.get("metadata", {})
        labels = metadata.get("labels", {})
        release = labels.get("app.kubernetes.io/instance", labels.get("release"))
        substrate_component = metadata.get("namespace") == "edai2" and metadata.get("name") in {
            "ate-api-server", "ate-api-server-deployment", "ate-controller", "atelet", "dns", "atenet-router"}
        if (release in OWNED_RELEASES or substrate_component) and document.get("kind") in ("Deployment", "StatefulSet", "DaemonSet", "Job", "Pod"):
            pod = document["spec"] if document["kind"] == "Pod" else document["spec"]["template"]["spec"]
            for container in (pod.get("containers") or []) + (pod.get("initContainers") or []):
                resources = container["resources"] = container.get("resources") or {}
                requests = resources["requests"] = resources.get("requests") or {}
                limits = resources["limits"] = resources.get("limits") or {}
                for key, default, ceiling in (("cpu", "10m", "1"), ("memory", "64Mi", "2Gi")):
                    requests.setdefault(key, limits.get(key, default))
                    if key not in limits:
                        # Existing reservations must never be capped below their request.
                        limits[key] = requests[key] if _quantity(requests[key], memory=key == "memory") > _quantity(ceiling, memory=key == "memory") else ceiling
            if substrate_component and metadata.get("name") in ("ate-api-server", "ate-api-server-deployment"):
                api = next(c for c in pod["containers"] if c["name"] == "ate-api-server")
                if substrate_api_image is not None:
                    api["image"] = substrate_api_image
                    substrate_api_containers += 1
                args = api.setdefault("args", [])
                if any(a.startswith(("--redis-mode", "--redis-password-file")) for a in args):
                    raise ValueError("Pinned Substrate chart already declares the password adapter")
                args.extend(["--redis-mode=@env", "--redis-password-file=@env"])
                if any(a.startswith("--client-jwt-issuer=https://container.googleapis.com/") for a in args):
                    # GKE's public OIDC endpoint has public TLS roots, not the cluster API CA.
                    args[:] = ["--client-jwt-ca-cert=" if a.startswith("--client-jwt-ca-cert=") else a for a in args]
                api.setdefault("envFrom", []).append({"configMapRef": {"name": "substrate-api-env"}})
                api.setdefault("volumeMounts", []).append({"name": "redis-password", "mountPath": "/run/valkey-auth", "readOnly": True})
                pod.setdefault("volumes", []).append({"name": "redis-password", "secret": {"secretName": "valkey", "items": [{"key": "password", "path": "password"}]}})
        if (document.get("kind") == "ServiceAccount" and metadata.get("namespace") == "edai2"
                and metadata.get("name") == "atelet" and atelet_wi_annotation is not None):
            annotations = metadata.setdefault("annotations", {})
            annotations["iam.gke.io/gcp-service-account"] = atelet_wi_annotation
            atelet_service_accounts += 1
        if (document.get("kind"), metadata.get("name"), metadata.get("namespace", "edai2")) != (
                "Deployment", "agentregistry", "edai2"):
            continue
        metadata["namespace"] = "edai2"
        document["spec"]["strategy"] = {"type": "Recreate"}
        containers = document["spec"]["template"]["spec"]["containers"]
        registry = next(container for container in containers if container["name"] == "agentregistry")
        database = next(entry for entry in registry["env"] if entry["name"] == "AGENT_REGISTRY_DATABASE_URL")
        if database.get("value") != REGISTRY_DATABASE_MARKER:
            raise ValueError("Registry database marker differs from the prepared chart input")
        database.pop("value")
        database["valueFrom"] = {"secretKeyRef": {"name": "agentregistry", "key": "database-url"}}
    if REGISTRY_DATABASE_MARKER in json.dumps(result):
        raise ValueError("Unconsumed Registry database marker; refusing installation")
    for document in list(result):
        if document.get("kind") == "ConfigMap" and document.get("metadata", {}).get("name") == "ateapi-ca" and document.get("metadata", {}).get("namespace") == "edai2":
            ca = document.get("data", {}).get("ca.crt")
            if not ca:
                raise ValueError("Substrate CA is missing")
            result.append({"apiVersion": "v1", "kind": "ConfigMap", "metadata": {
                "name": "kagent-ateapi-ca", "namespace": "kagent"}, "data": {"ca.crt": ca}})
    if substrate_api_image is not None and substrate_api_containers != 1:
        raise ValueError(f"expected one ate-api-server container for substrate_api_image, found {substrate_api_containers}")
    if atelet_wi_annotation is not None and atelet_service_accounts != 1:
        raise ValueError(f"expected one existing edai2/atelet ServiceAccount for WI annotation, found {atelet_service_accounts}")
    return result


if __name__ == "__main__":
    try:
        documents = [document for document in yaml.safe_load_all(sys.stdin) if document]
        yaml.safe_dump_all(render(
            documents,
            substrate_api_image=os.environ.get("EDAI2_SUBSTRATE_API_IMAGE") or None,
            atelet_wi_annotation=os.environ.get("EDAI2_ATELET_WI_ANNOTATION") or None,
        ), sys.stdout, sort_keys=False)
    except (ValueError, KeyError, StopIteration):
        print("Topic 24 post-render adaptation rejected the chart output", file=sys.stderr)
        sys.exit(2)
