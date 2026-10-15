"""Fail-closed local checks for Topic 24's live evidence envelope."""

from __future__ import annotations

import importlib.util
import hashlib
import base64
import json
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]


def _module():
    spec = importlib.util.spec_from_file_location("capture_topic24", ROOT / "scripts/qa/capture_edai2_evidence.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _entry(key: str) -> dict:
    return {
        "namespace": "vault" if key == "vault_status" else "edai2",
        "service_name": key,
        "service_uid": f"service-{key}",
        "service_port": 80,
        "target_port": 8080,
        "selector_sha256": "a" * 64,
        "ready_endpoint_uids": [f"pod-{key}"],
    }


def _live_resources(module, proof_root: Path) -> dict:
    build = json.loads((proof_root / "tmp/edai2-gcp/topic24-finalize/remote-build-provenance.json").read_text())
    repo = f"{build['target']['region']}-docker.pkg.dev/{build['target']['project_id']}/{build['target']['artifact_registry_repository']}/{build['target']['image_name']}"
    tag = build["target"]["tag"]
    runtime_digest = getattr(module, "TEST_IMAGE_DIGEST", "sha256:" + "c" * 64)
    return {
        "namespace": "edai2",
        "collected_namespaces": list(module.TOPIC24_OWNED_NAMESPACES),
        "resources": {
            "pods": [
                {"metadata": {"name": "api", "uid": "pod-api"}, "spec": {"containers": [{"name": "api", "image": "example/api@sha256:" + "b" * 64}]}, "status": {"containerStatuses": [{"name": "api", "imageID": "containerd://sha256:" + "b" * 64}]}},
                {"metadata": {"name": "substrate-api", "uid": "pod-substrate"}, "spec": {"containers": [{"name": "ateapi", "image": f"{repo}:{tag}@{runtime_digest}"}]}, "status": {"containerStatuses": [{"name": "ateapi", "imageID": "containerd://" + runtime_digest, "ready": True}]}},
                {"metadata": {"name": "llmd-primary", "uid": "pod-model", "labels": {"app": "llmd-primary"}},
                 "spec": {"containers": [{"name": "model", "image": "example/llm@sha256:" + "d" * 64, "volumeMounts": [{"mountPath": "/models"}]}],
                          "initContainers": [{"name": "cache-init", "image": "example/cache@sha256:" + "e" * 64}]},
                 "status": {"containerStatuses": [{"name": "model", "imageID": "containerd://sha256:" + "d" * 64, "ready": True}],
                            "initContainerStatuses": [{"name": "cache-init", "imageID": "containerd://sha256:" + "e" * 64, "state": {"terminated": {"exitCode": 0}}}]}}
            ],
            "deployments": [{"metadata": {"name": "api", "uid": "dep-api", "labels": {"app.kubernetes.io/instance": "api", "helm.sh/chart": "api-1.0.0"}}, "spec": {"replicas": 1}}],
            "services": [{"metadata": {"name": "api", "uid": "svc-api"}, "spec": {"type": "ClusterIP"}}],
            "statefulsets": [],
            "daemonsets": [],
            "jobs": [],
            "cronjobs": [],
            "replicasets": [],
            "endpointslices": [],
            "persistentvolumeclaims": [],
            "custom_resources": [],
            "nodes": [{"metadata": {"name": "node-a", "uid": "node-a-uid"}, "status": {"conditions": [{"type": "Ready", "status": "True"}]}}],
        },
    }


def _proof_root(tmp_path: Path, module) -> tuple[Path, dict]:
    root = tmp_path / "proof-root"
    scratch = root / "tmp/edai2-gcp/topic24-finalize"
    output = scratch / "remote-build-output"
    (output / "sbom").mkdir(parents=True, exist_ok=True)
    (output / "sbom/sbom.spdx.json").write_text("{}", encoding="utf-8")
    for name in ("remote-build-provenance.json", "substrate-source-topic24-finalize.manifest.json", "substrate-source-topic24-finalize.tar.gz", "topic24-builder-job.yaml"):
        source = ROOT / "tmp/edai2-gcp/topic24-finalize" / name
        target = scratch / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    cache_root = root / "infra/kustomize/llmd/overlays/cpu"
    cache_root.mkdir(parents=True, exist_ok=True)
    for name in ("model-cache-manifest.json", "cache-init.py"):
        (cache_root / name).write_bytes((ROOT / "infra/kustomize/llmd/overlays/cpu" / name).read_bytes())
    build = json.loads((scratch / "remote-build-provenance.json").read_text())
    repo = f"{build['target']['region']}-docker.pkg.dev/{build['target']['project_id']}/{build['target']['artifact_registry_repository']}/{build['target']['image_name']}"
    tag = build["target"]["tag"]
    bundle_hash = build["source_bundle_sha256"]
    config = json.dumps({"architecture": "amd64", "os": "linux"}, separators=(",", ":")).encode()
    config_digest = "sha256:" + hashlib.sha256(config).hexdigest()
    manifest = json.dumps({"schemaVersion": 2, "mediaType": "application/vnd.oci.image.manifest.v1+json",
                           "config": {"mediaType": "application/vnd.oci.image.config.v1+json", "digest": config_digest, "size": len(config)},
                           "layers": []}, separators=(",", ":")).encode()
    manifest_digest = "sha256:" + hashlib.sha256(manifest).hexdigest()
    module.TEST_IMAGE_DIGEST = manifest_digest
    image_ref = f"{repo}:{tag}@{manifest_digest}"
    (output / "image-refs.txt").write_text(image_ref + "\n", encoding="utf-8")
    (output / "image-platform-provenance.json").write_text(json.dumps({
        "schema_version": 1, "image_ref": image_ref,
        "index_manifest_base64": base64.b64encode(manifest).decode(),
        "platform_manifest_base64": base64.b64encode(manifest).decode(),
        "config_blob_base64": base64.b64encode(config).decode(),
    }), encoding="utf-8")
    (output / "remote-tool-versions.txt").write_text(f"go version go1.26.3 linux/amd64\nko version v0.19.1\nKO_DOCKER_REPO={repo}\nBUILD_TAG={tag}\nBASE_IMAGE={build['base_image']['reference']}\n", encoding="utf-8")
    (output / "verified-inputs.sha256").write_text(
        f"{bundle_hash}  substrate-source-topic24-finalize.tar.gz\n"
        f"{build['go']['linux_amd64_archive_sha256']}  go.tar.gz\n"
        f"{build['ko']['linux_amd64_archive_sha256']}  ko.tar.gz\n", encoding="utf-8")
    (output / "ko-build.log").write_text("built\n", encoding="utf-8")
    local_job = yaml.safe_load((scratch / "topic24-builder-job.yaml").read_text())
    expected_builder = local_job["spec"]["template"]["spec"]["containers"][0]
    command = expected_builder.get("command", []) + expected_builder.get("args", [])
    safe_env = {item["name"]: item["value"] for item in expected_builder["env"] if item["name"] in {"BUILD_TAG", "SOURCE_BUNDLE_SHA256", "KO_DOCKER_REPO"}}
    command_hash = hashlib.sha256(json.dumps(command, separators=(",", ":")).encode()).hexdigest()
    (output / "job-completion.json").write_text(json.dumps({
        "schema_version": 1,
        "job": {"name": "topic24-substrate-api-build", "uid": "job-uid", "succeeded": 1,
                "start_time": "2026-01-01T00:00:00Z", "completion_time": "2026-01-01T00:10:00Z"},
        "complete_condition": {"type": "Complete", "status": "True", "last_transition_time": "2026-01-01T00:10:00Z"},
        "builder": {"image": expected_builder["image"], "command_sha256": command_hash,
                    "source_bundle_sha256": bundle_hash, "build_tag": tag, "ko_docker_repo": repo,
                    "job_manifest_sha256": hashlib.sha256((scratch / "topic24-builder-job.yaml").read_bytes()).hexdigest()},
        "source_bundle_sha256": bundle_hash,
        "source_manifest_sha256": build["source_manifest_sha256"],
        "image_ref": image_ref,
        "platform_image_digest": manifest_digest,
        "verified_archive": {"sha256": bundle_hash, "source_manifest_sha256": build["source_manifest_sha256"], "command_exit_code": 0},
        "verified_inputs_sha256": hashlib.sha256((output / "verified-inputs.sha256").read_bytes()).hexdigest(),
    }), encoding="utf-8")
    manifest_path = ROOT / "infra/kustomize/llmd/overlays/cpu/model-cache-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    primary = next(item for item in manifest["objects"] if item["name"] == "primary")
    marker = {
        "schema_version": 1,
        "manifest_file_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "init_script_sha256": hashlib.sha256((ROOT / "infra/kustomize/llmd/overlays/cpu/cache-init.py").read_bytes()).hexdigest(),
        "objects": [{key: primary[key] for key in ("name", "generation", "bytes", "sha256", "revision")}],
    }
    return root, marker


def _payload(module, kubeconfig: Path, tmp_path: Path, context: str = "edai2-gke") -> dict:
    endpoints = {key: _entry(key) | {"selector_sha256": module.selector_sha256({"app": key})} for key in module.PRIVATE_ENDPOINT_KEYS}
    root, marker = _proof_root(tmp_path, module)
    live = _live_resources(module, root)
    payload = {
        "provenance": module.topic24_provenance(kubeconfig, context),
        "private_endpoints": endpoints,
        "live_resources": live,
        "workload_provenance": module.topic24_workload_provenance(live, cache_marker=marker, root=root),
        "_test_cache_marker": marker,
    }
    assert not module._topic24_has_secret_material(payload)
    return payload


def _live_endpoint_runner(module, cache_marker=None):
    selectors = {key: {"app": key} for key in module.PRIVATE_ENDPOINT_KEYS}
    bindings = {key: {"namespace": "vault" if key == "vault_status" else "edai2", "service": key} for key in module.PRIVATE_ENDPOINT_KEYS}

    def runner(command):
        if command[1] == "exec":
            return cache_marker
        name = command[3] if command[1] == "get" else ""
        if command[1] == "get" and command[2] == "service":
            return {"metadata": {"uid": f"service-{name}"}, "spec": {"ports": [{"port": 80, "targetPort": 8080}], "selector": selectors[name]}}
        key = next(value.split("=", 1)[1] for value in command if value.startswith("kubernetes.io/service-name="))
        return {"items": [{"ports": [], "endpoints": [{"conditions": {"ready": True}, "targetRef": {"uid": f"pod-{key}"}}]}]}
    return bindings, runner


def _verify(module, payload, kubeconfig: Path, tmp_path: Path, context: str = "edai2-gke") -> None:
    bindings, runner = _live_endpoint_runner(module, payload.get("_test_cache_marker"))
    public_payload = {key: value for key, value in payload.items() if not key.startswith("_")}
    module.verify_topic24_inventory(public_payload, kubeconfig=kubeconfig, context=context, bindings=bindings, runner=runner, root=tmp_path / "proof-root")


def _kubeconfig(path: Path, context: str = "edai2-gke") -> None:
    path.write_text(
        "apiVersion: v1\nclusters:\n- name: target\n  cluster:\n    server: https://cluster.example.test\ncontexts:\n- name: "
        + context
        + "\n  context:\n    cluster: target\n    user: target\ncurrent-context: "
        + context
        + "\nusers:\n- name: target\n  user:\n    token: must-not-appear\n",
        encoding="utf-8",
    )


def test_topic24_inventory_requires_fresh_provenance_and_resource_backed_proof(tmp_path: Path) -> None:
    module = _module()
    kubeconfig = tmp_path / "kubeconfig"
    _kubeconfig(kubeconfig)
    payload = _payload(module, kubeconfig, tmp_path)
    _verify(module, payload, kubeconfig, tmp_path)
    assert "must-not-appear" not in json.dumps(payload)

    for broken in (
        payload | {"provenance": {}},
        payload | {"live_resources": {"namespace": "edai2", "resources": {}}},
    ):
        with pytest.raises(ValueError):
            _verify(module, broken, kubeconfig, tmp_path)


def test_topic24_rejects_unlinked_generic_runtime_image_digest(tmp_path: Path) -> None:
    module = _module()
    root, marker = _proof_root(tmp_path, module)
    live = _live_resources(module, root)
    live["resources"]["pods"][0]["status"]["containerStatuses"][0]["imageID"] = "containerd://sha256:" + "f" * 64
    with pytest.raises(ValueError, match="runtime image digest"):
        module.topic24_workload_provenance(live, cache_marker=marker, root=root)


def test_topic24_inventory_rejects_wrong_context_and_stale_fingerprints(tmp_path: Path) -> None:
    module = _module()
    kubeconfig = tmp_path / "kubeconfig"
    _kubeconfig(kubeconfig)
    payload = _payload(module, kubeconfig, tmp_path)
    with pytest.raises(ValueError, match="context"):
        _verify(module, payload, kubeconfig, tmp_path, "other-context")
    stale = json.loads(json.dumps(payload))
    stale["provenance"]["cluster_fingerprint"] = "0" * 64
    with pytest.raises(ValueError, match="provenance"):
        _verify(module, stale, kubeconfig, tmp_path)
    stale_time = json.loads(json.dumps(payload))
    stale_time["provenance"]["captured_at_utc"] = "2020-01-01T00:00:00Z"
    with pytest.raises(ValueError, match="stale"):
        _verify(module, stale_time, kubeconfig, tmp_path)
    altered_sources = json.loads(json.dumps(payload))
    altered_sources["provenance"]["source_sha256"][0] = "0" * 64
    with pytest.raises(ValueError, match="provenance"):
        _verify(module, altered_sources, kubeconfig, tmp_path)


def test_topic24_source_provenance_covers_all_runtime_inputs() -> None:
    module = _module()
    sources = module._topic24_source_hashes()
    required = {
        "infra/agentgateway/edai2/gateway.yaml",
        "infra/kustomize/llmd/overlays/cpu/cache-init.py",
        "infra/substrate/patches/standalone-valkey-0.0.6.patch",
        "infra/substrate/edai2/kustomization.yaml",
        "infra/kagent/edai2/model-configs.yaml",
        "infra/security/external-secrets/agentregistry.yaml",
        "infra/security/vault/policies/agentgateway.hcl",
        "infra/postgres/edai2/bootstrap-platform-databases.sh",
    }
    assert required <= set(sources)


def test_topic24_inventory_rejects_endpoint_mutations_and_empty_ready_sets(tmp_path: Path) -> None:
    module = _module()
    kubeconfig = tmp_path / "kubeconfig"
    _kubeconfig(kubeconfig)
    for field, value in (("service_uid", "altered-service"), ("service_port", 81), ("target_port", 81), ("selector_sha256", "c" * 64), ("ready_endpoint_uids", [])):
        payload = _payload(module, kubeconfig, tmp_path)
        payload["private_endpoints"]["grafana_ui"][field] = value
        with pytest.raises(ValueError):
            _verify(module, payload, kubeconfig, tmp_path)


def test_topic24_exclusions_need_live_resources_and_reject_forbidden_objects() -> None:
    module = _module()
    payload = {"live_resources": _live_resources(module, ROOT)}
    module.verify_platform_exclusions(payload, module.TOPIC24_FORBIDDEN_MARKERS)
    with pytest.raises(ValueError, match="resource"):
        module.verify_platform_exclusions({"live_resources": {"namespace": "edai2", "resources": {}}}, module.TOPIC24_FORBIDDEN_MARKERS)
    altered = json.loads(json.dumps(payload))
    altered["live_resources"]["resources"]["services"].append(
        {"metadata": {"name": "public"}, "spec": {"type": "LoadBalancer"}}
    )
    with pytest.raises(ValueError, match="forbidden"):
        module.verify_platform_exclusions(altered, module.TOPIC24_FORBIDDEN_MARKERS)


def test_live_collection_sanitizes_environment_literals_and_reads_custom_resources() -> None:
    module = _module()
    calls = []

    def runner(command):
        calls.append(command)
        if command[1] == "api-resources":
            return {"items": ["agents.kagent.dev", "tools.kagent.dev", "appsandboxagents", "remotemcpservers"]}
        if command[2] == "namespaces":
            return {"items": [{"metadata": {"name": n}} for n in module.TOPIC24_OWNED_NAMESPACES]}
        if command[1] == "get" and command[2].startswith("pods,"):
            return {"items": [{"kind": "Pod", "metadata": {"name": "api", "namespace": "edai2", "uid": "pod", "annotations": {"token": "never"}},
                               "spec": {"containers": [{"name": "api", "image": "example/api@sha256:" + "b" * 64,
                                                          "env": [{"name": "API_TOKEN", "value": "must-not-appear"}], "args": ["--token=never"]}]},
                               "status": {"containerStatuses": [{"name": "api", "imageID": "sha256:" + "b" * 64}]}}]}
        if command[1] == "get" and command[2] == "nodes":
            return {"items": [{"kind": "Node", "metadata": {"name": "node", "uid": "node"}}]}
        return {"items": [{"kind": "Agent", "metadata": {"name": "custom-agent"}}]}

    inventory = module.build_live_resource_inventory(runner=runner)
    rendered = json.dumps(inventory)
    assert "must-not-appear" not in rendered and "API_TOKEN" not in rendered and "--token" not in rendered
    assert inventory["resources"]["custom_resources"][0]["kind"] == "Agent"
    assert any(command[1] == "api-resources" for command in calls)


def test_live_collection_covers_owned_namespaces_and_excludes_system_pods() -> None:
    module = _module()
    owned = ["edai2", "kagent", "vault", "external-secrets", "cert-manager", "keda", "ingress-nginx"]
    calls = []

    def runner(command):
        calls.append(command)
        if command[1] == "api-resources":
            return {"items": []}
        if command[2] == "namespaces":
            return {"items": [{"metadata": {"name": n}} for n in owned]}
        if command[2] == "nodes":
            return {"items": []}
        return {"items": [{"kind": "Pod", "metadata": {"name": n, "namespace": n, "uid": n}, "spec": {}}
                          for n in [*owned, "kube-system"]]}

    result = module.build_live_resource_inventory(runner=runner)
    assert {p["metadata"]["namespace"] for p in result["resources"]["pods"]} == set(owned)
    assert result["collected_namespaces"] == sorted(owned)
    assert any(c[2].startswith("pods,") and "--all-namespaces" in c for c in calls)
    owned.remove("vault")
    with pytest.raises(ValueError, match="namespace collection"):
        module.build_live_resource_inventory(runner=runner)


@pytest.mark.parametrize("registry", ["docker.io", "registry-1.docker.io"])
def test_workload_provenance_records_version_tags_and_accepted_floating_images(tmp_path: Path, registry: str) -> None:
    module = _module()
    root, marker = _proof_root(tmp_path, module)
    live = _live_resources(module, root)
    pod = live["resources"]["pods"][0]
    pod["metadata"]["namespace"] = "kagent"
    pod["spec"]["containers"][0]["image"] = "ghcr.io/kagent-dev/kagent/controller:0.9.9"
    result = module.topic24_workload_provenance(live, cache_marker=marker, root=root)
    row = next(x for x in result["images"] if x["pod_uid"] == "pod-api")
    assert row["namespace"] == "kagent" and row["reference_kind"] == "version-tag"
    pod["metadata"].update(namespace="edai2", name="postgres-postgresql-0", labels={"app.kubernetes.io/instance": "postgres"})
    pod["spec"]["containers"][0]["image"] = f"{registry}/bitnami/postgresql:latest"
    result = module.topic24_workload_provenance(live, cache_marker=marker, root=root)
    assert next(x for x in result["images"] if x["pod_uid"] == "pod-api")["reference_kind"] == "accepted-floating-tag"
    pod["spec"]["containers"][0]["image"] = "example/unapproved:latest"
    with pytest.raises(ValueError, match="image"):
        module.topic24_workload_provenance(live, cache_marker=marker, root=root)
    pod["spec"]["containers"][0]["image"] = "ghcr.io/kagent-dev/kagent/controller:0.9.9"
    pod["status"]["containerStatuses"][0]["imageID"] += "trailing-garbage"
    with pytest.raises(ValueError, match="image"):
        module.topic24_workload_provenance(live, cache_marker=marker, root=root)
    pod["status"]["containerStatuses"][0]["imageID"] = "containerd://sha256:" + "b" * 64
    live["resources"]["pods"][2]["spec"]["containers"][0]["image"] = "ghcr.io/llm-d/llm-d-cpu:v0.7.0"
    with pytest.raises(ValueError, match="image"):
        module.topic24_workload_provenance(live, cache_marker=marker, root=root)


def test_exclusions_allow_retained_platform_stores_but_reject_bundled_duplicates() -> None:
    module = _module()
    live = _live_resources(module, ROOT)
    live["resources"]["statefulsets"].append({"kind": "StatefulSet", "metadata": {
        "namespace": "edai2", "name": "postgres-postgresql", "labels": {"app.kubernetes.io/instance": "postgres"}}})
    live["resources"]["endpointslices"].append({"kind": "EndpointSlice", "metadata": {
        "namespace": "edai2", "name": "postgres-postgresql-abcde", "labels": {"kubernetes.io/service-name": "postgres-postgresql"}}})
    live["resources"]["services"].append({"kind": "Service", "metadata": {
        "namespace": "edai2", "name": "postgres-postgresql", "labels": {"app.kubernetes.io/instance": "postgres"}}, "spec": {"type": "ClusterIP"}})
    module.verify_platform_exclusions({"live_resources": live}, module.TOPIC24_FORBIDDEN_MARKERS)
    live["resources"]["statefulsets"][-1]["metadata"]["name"] = "langfuse-postgresql"
    with pytest.raises(ValueError, match="bundled store"):
        module.verify_platform_exclusions({"live_resources": live}, module.TOPIC24_FORBIDDEN_MARKERS)


@pytest.mark.parametrize("kind", ["SandboxAgent", "RemoteMCPServer", "Agent", "Tool"])
def test_exclusions_reject_actual_application_and_builtin_resource_kinds(kind: str) -> None:
    module = _module()
    live = _live_resources(module, ROOT)
    live["resources"]["custom_resources"].append({"kind": kind, "metadata": {"namespace": "edai2", "name": "forbidden"}})
    with pytest.raises(ValueError, match="forbidden agent or tool"):
        module.verify_platform_exclusions({"live_resources": live}, module.TOPIC24_FORBIDDEN_MARKERS)


def test_topic24_secret_field_is_rejected_without_blocking_chart_names(tmp_path: Path) -> None:
    module = _module()
    kubeconfig = tmp_path / "kubeconfig"
    _kubeconfig(kubeconfig)
    payload = _payload(module, kubeconfig, tmp_path)
    payload["live_resources"]["resources"]["pods"][0]["metadata"]["labels"] = {"helm.sh/chart": "external-secrets-1.0.0"}
    payload["workload_provenance"] = module.topic24_workload_provenance(payload["live_resources"], cache_marker=payload["_test_cache_marker"], root=tmp_path / "proof-root")
    _verify(module, payload, kubeconfig, tmp_path)
    payload["live_resources"]["resources"]["pods"][0]["token"] = "redacted-token"
    with pytest.raises(ValueError, match="secret"):
        _verify(module, payload, kubeconfig, tmp_path)


def test_topic24_workload_provenance_rejects_missing_cache_and_substrate_linkage(tmp_path: Path) -> None:
    module = _module()
    with pytest.raises(ValueError, match="cache provenance"):
        module.verify_cache_runtime_provenance({})
    with pytest.raises(ValueError, match="build provenance"):
        module.verify_substrate_build_provenance(tmp_path, [])


def test_topic24_substrate_proof_binds_build_digest_and_cache_generation(tmp_path: Path) -> None:
    module = _module()
    root, marker = _proof_root(tmp_path, module)
    live = _live_resources(module, root)
    result = module.verify_substrate_build_provenance(root, live)
    assert result["source_bundle_sha256"]
    assert result["image_ref"].endswith("@" + module.TEST_IMAGE_DIGEST)
    assert len(result["sbom_sha256"]) == 64
    changed = json.loads(json.dumps(live))
    changed["resources"]["pods"][1]["status"]["containerStatuses"][0]["imageID"] = "containerd://sha256:" + "f" * 64
    with pytest.raises(ValueError, match="source-built digest"):
        module.verify_substrate_build_provenance(root, changed)
    changed_marker = json.loads(json.dumps(marker))
    changed_marker["objects"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="pinned generations and hashes"):
        module.verify_cache_runtime_provenance(changed_marker, root=root)


def test_topic24_registry_proof_resolves_index_to_amd64_child(tmp_path: Path) -> None:
    module = _module()
    config = json.dumps({"architecture": "amd64", "os": "linux"}, separators=(",", ":")).encode()
    config_hash = "sha256:" + hashlib.sha256(config).hexdigest()
    child = json.dumps({"schemaVersion": 2, "config": {"digest": config_hash}, "layers": []}, separators=(",", ":")).encode()
    child_hash = "sha256:" + hashlib.sha256(child).hexdigest()
    index = json.dumps({"schemaVersion": 2, "manifests": [{"digest": child_hash, "platform": {"os": "linux", "architecture": "amd64"}}]}, separators=(",", ":")).encode()
    index_hash = "sha256:" + hashlib.sha256(index).hexdigest()
    reference = f"registry.example.test/substrate:topic24@{index_hash}"
    artifact = tmp_path / "image-platform-provenance.json"
    artifact.write_text(json.dumps({"schema_version": 1, "image_ref": reference,
                                    "index_manifest_base64": base64.b64encode(index).decode(),
                                    "platform_manifest_base64": base64.b64encode(child).decode(),
                                    "config_blob_base64": base64.b64encode(config).decode()}), encoding="utf-8")
    assert module.verify_registry_platform_provenance(artifact, reference) == child_hash
    tampered = json.loads(artifact.read_text())
    tampered["platform_manifest_base64"] = base64.b64encode(config).decode()
    artifact.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ValueError, match="platform digest provenance"):
        module.verify_registry_platform_provenance(artifact, reference)


def test_topic24_cache_provenance_is_bound_to_pinned_generation_and_hashes(tmp_path: Path) -> None:
    module = _module()
    manifest = json.loads((ROOT / "infra/kustomize/llmd/overlays/cpu/model-cache-manifest.json").read_text())
    primary = next(item for item in manifest["objects"] if item["name"] == "primary")
    marker = {
        "schema_version": 1,
        "manifest_file_sha256": module.hashlib.sha256((ROOT / "infra/kustomize/llmd/overlays/cpu/model-cache-manifest.json").read_bytes()).hexdigest(),
        "init_script_sha256": module.hashlib.sha256((ROOT / "infra/kustomize/llmd/overlays/cpu/cache-init.py").read_bytes()).hexdigest(),
        "objects": [{key: primary[key] for key in ("name", "generation", "bytes", "sha256", "revision")}],
    }
    assert module.verify_cache_runtime_provenance(marker)["objects"] == marker["objects"]
    altered = json.loads(json.dumps(marker))
    altered["objects"][0]["generation"] = "1"
    with pytest.raises(ValueError, match="cache provenance"):
        module.verify_cache_runtime_provenance(altered)

