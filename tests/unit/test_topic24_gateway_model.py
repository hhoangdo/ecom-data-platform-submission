from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import tarfile
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
OVERLAY = ROOT / "infra/kustomize/llmd/overlays/cpu"
ROUTES = {
    "model-route": ("model-route", "/v1", "llmd-router", 8000),
    "retrieval-mcp": ("retrieval-mcp-route", "/mcp/retrieval", "retrieval-mcp", 8080),
    "drift-mcp": ("drift-mcp-route", "/mcp/drift", "drift-mcp", 8080),
    "coordinator-specialist": (
        "coordinator-specialist-route", "/a2a/specialist", "coordinator-agent", 8080
    ),
    "facade-coordinator": (
        "facade-coordinator-route", "/a2a/coordinator", "coordinator-agent", 8080
    ),
}
SECRET_NAMES = {
    "model-route": "gateway-auth-model-route",
    "retrieval-mcp": "gateway-auth-retrieval-mcp",
    "drift-mcp": "gateway-auth-drift-mcp",
    "coordinator-specialist": "gateway-auth-coordinator-specialist",
    "facade-coordinator": "gateway-auth-facade-coordinator",
}
CPU_IMAGE = "ghcr.io/llm-d/llm-d-cpu:v0.7.0@sha256:f4abcce2b3a3c00521d220dfeabe7aeb5b800823451f8f49fc2b3f9cb5441584"
CACHE_INIT_IMAGE = "python:3.14.8-slim-trixie@sha256:cfe2e24a75302a15934d37c2d86412893c0aa934dc3a97cbb439d04c01890ca9"


def documents(path: Path) -> list[dict]:
    return [item for item in yaml.safe_load_all(path.read_text(encoding="utf-8")) if item]


def load_cache_initializer(name: str):
    script_path = OVERLAY / "cache-init.py"
    module_spec = importlib.util.spec_from_file_location(name, script_path)
    assert module_spec and module_spec.loader
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def test_rendered_cache_manifest_is_mounted_at_the_initializer_path() -> None:
    rendered = subprocess.run(
        ["kubectl", "--kubeconfig", str(ROOT / "tmp/edai2-gcp/kubeconfig"),
         "--context", "edai2-gke", "kustomize", str(OVERLAY)],
        capture_output=True, text=True, check=True,
    ).stdout
    docs = [item for item in yaml.safe_load_all(rendered) if item]
    primary = next(item for item in docs if item["kind"] == "Deployment" and item["metadata"]["name"] == "llmd-primary")
    manifest = next(item for item in docs if item["kind"] == "ConfigMap" and item["metadata"]["name"] == "llmd-model-cache-manifest")
    assert manifest["metadata"].get("namespace") == primary["metadata"]["namespace"] == "edai2"
    module = load_cache_initializer("cache_init_rendered_mount")
    assert manifest["data"][module.MANIFEST_PATH.name].encode() == (OVERLAY / "model-cache-manifest.json").read_bytes()
    volume = next(item for item in primary["spec"]["template"]["spec"]["volumes"] if item["name"] == "model-cache-manifest")
    assert volume["configMap"]["name"] == manifest["metadata"]["name"]
    init = primary["spec"]["template"]["spec"]["initContainers"][0]
    mount = next(item for item in init["volumeMounts"] if item["name"] == "model-cache-manifest")
    assert Path(mount["mountPath"]) / module.MANIFEST_PATH.name == module.MANIFEST_PATH


def use_plain_tar_for_zstd_stream(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, bool | None]]:
    real_open = tarfile.open
    modes = []

    def open_plain_fixture(name=None, mode="r", *args, **kwargs):
        modes.append((mode, kwargs.get("stream")))
        kwargs.pop("stream", None)  # The suite runtime predates Python 3.13's stream parameter.
        return real_open(name, "r|" if mode == "r|zst" else mode, *args, **kwargs)

    monkeypatch.setattr(tarfile, "open", open_plain_fixture)
    return modes


def test_gateway_auth_has_five_route_scoped_allow_pairs_and_twenty_denials() -> None:
    policies = documents(ROOT / "infra/agentgateway/edai2/policies.yaml")
    assert len(policies) == 5
    observed = set()
    for policy in policies:
        assert policy["kind"] == "AgentgatewayPolicy"
        spec = policy["spec"]
        route_name, _, _, _ = ROUTES[policy["metadata"]["name"].removeprefix("auth-")]
        assert spec["targetRefs"] == [{
            "group": "gateway.networking.k8s.io", "kind": "HTTPRoute", "name": route_name
        }]
        auth = spec["traffic"]["apiKeyAuthentication"]
        assert auth["mode"] == "Strict"
        assert auth["secretSelector"] == {
            "matchLabels": {"edai2.gateway-auth-route": policy["metadata"]["name"].removeprefix("auth-")}
        }
        logical_route = policy["metadata"]["name"].removeprefix("auth-")
        authorization = spec["traffic"]["authorization"]
        assert authorization["action"] == "Require"
        assert authorization["policy"]["matchExpressions"] == [
            f"apiKey.route == '{logical_route}'"
        ]
        if logical_route == "model-route":
            # v1.3.1 removes inbound credentials after authentication; explicitly
            # restore the validated bearer token for vLLM's own API-key check.
            assert spec["backend"]["auth"]["passthrough"] == {}
        observed.add((policy["metadata"]["name"].removeprefix("auth-"), route_name))
    assert observed == {(name, details[0]) for name, details in ROUTES.items()}
    allowed_pairs = set()
    for policy in policies:
        route = policy["metadata"]["name"].removeprefix("auth-")
        expression = policy["spec"]["traffic"]["authorization"]["policy"]["matchExpressions"][0]
        for credential_route in ROUTES:
            if expression == f"apiKey.route == '{credential_route}'":
                allowed_pairs.add((route, credential_route))
    assert allowed_pairs == {(route, route) for route in ROUTES}
    assert len(allowed_pairs) == 5
    assert len(ROUTES) ** 2 - len(allowed_pairs) == 20


def test_private_routes_rewrite_service_paths_and_never_route_back_to_gateway() -> None:
    routes = {
        item["metadata"]["name"]: item
        for path in (
            ROOT / "infra/agentgateway/edai2/model-route.yaml",
            ROOT / "infra/agentgateway/edai2/mcp-routes.yaml",
            ROOT / "infra/agentgateway/edai2/a2a-routes.yaml",
        )
        for item in documents(path)
    }
    for logical_name, (route_name, prefix, backend, port) in ROUTES.items():
        route = routes[route_name]
        rule = route["spec"]["rules"][0]
        assert rule["matches"] == [{"path": {"type": "PathPrefix", "value": prefix}}]
        assert rule["backendRefs"] == [{"name": backend, "port": port}]
        if logical_name == "model-route":
            assert "filters" not in rule
        else:
            assert rule["filters"] == [{
                "type": "URLRewrite",
                "urlRewrite": {"path": {"type": "ReplacePrefixMatch", "replacePrefixMatch": "/mcp" if "mcp" in logical_name else "/"}},
            }]
    gateway = documents(ROOT / "infra/agentgateway/edai2/gateway.yaml")[0]
    assert gateway["spec"]["gatewayClassName"] == "agentgateway"
    assert gateway["spec"]["listeners"][0]["port"] == 8080
    parameters = documents(ROOT / "infra/agentgateway/edai2/parameters.yaml")[0]
    assert parameters["kind"] == "AgentgatewayParameters"
    assert parameters["spec"]["service"]["spec"]["type"] == "ClusterIP"
    assert parameters["spec"]["resources"]["requests"] == {"cpu": "100m", "memory": "128Mi"}


def test_each_gateway_auth_secret_is_an_eso_projection_of_one_vault_credential() -> None:
    files = sorted((ROOT / "infra/security/external-secrets").glob("gateway-auth-*.yaml"))
    assert len(files) == 5
    projections = {}
    for path in files:
        external_secret = documents(path)[0]
        route = external_secret["metadata"]["labels"]["edai2.gateway-auth-route"]
        target = external_secret["spec"]["target"]
        assert target["name"] == SECRET_NAMES[route]
        assert target["template"]["metadata"]["labels"] == {
            "edai2.gateway-auth-route": route
        }
        outputs = target["template"]["data"]
        assert outputs == {
            route: f'{{{{ dict "key" .gatewayKey "metadata" (dict "route" "{route}") | toJson }}}}'
        }
        source = external_secret["spec"]["data"]
        assert len(source) == 1 and source[0]["secretKey"] == "gatewayKey"
        projections[route] = source[0]["remoteRef"]
    assert projections == {
        "model-route": {"key": "edai2/kagent/gateway-keys", "property": "model-api-key"},
        "retrieval-mcp": {"key": "edai2/kagent/gateway-keys", "property": "support-authorization"},
        "drift-mcp": {"key": "edai2/kagent/gateway-keys", "property": "drift-authorization"},
        "coordinator-specialist": {"key": "edai2/kagent/gateway-keys", "property": "coordinator-authorization"},
        "facade-coordinator": {"key": "edai2/facade/gateway-entry", "property": "authorization"},
    }


def test_model_configs_use_generated_private_gateway_service() -> None:
    configs = documents(ROOT / "infra/kagent/edai2/model-configs.yaml")
    assert all(
        item["spec"]["openAI"]["baseUrl"]
        == "http://edai2-private-gateway.edai2.svc.cluster.local:8080/v1"
        for item in configs
    )


def test_agent_client_values_allow_and_use_the_generated_gateway_service() -> None:
    gateway = "edai2-private-gateway.edai2.svc.cluster.local"
    for name in ("retrieval-agent.yaml", "drift-agent.yaml", "coordinator-agent.yaml"):
        values = yaml.safe_load((ROOT / "infra/helm/edai2/values" / name).read_text(encoding="utf-8"))
        assert values["proxy"]["url"] == f"http://{gateway}:8080"
        for agent in values["sandboxAgents"]:
            assert gateway in agent["sandboxAgent"]["sandbox"]["network"]["allowedDomains"]


def test_cpu_primary_serves_cached_model_with_single_thread_and_ready_probe() -> None:
    primary = documents(OVERLAY / "patch-primary.yaml")[0]
    container = primary["spec"]["template"]["spec"]["containers"][0]
    assert container["args"] == [
        "--model", "/models/primary", "--served-model-name", "Qwen/Qwen2.5-1.5B-Instruct",
        "--host", "0.0.0.0", "--port", "8000", "--dtype", "bfloat16",
        "--max-model-len", "4096", "--max-num-seqs", "1",
    ]
    assert container["resources"]["requests"] == {"cpu": "1", "memory": "4Gi"}
    env = {item["name"]: item for item in container["env"]}
    assert {name: item["value"] for name, item in env.items() if "value" in item} == {
        "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "OMP_NUM_THREADS": "1",
        "VLLM_CPU_OMP_THREADS_BIND": "nobind", "VLLM_CPU_KVCACHE_SPACE": "1",
        "VLLM_CPU_SGL_KERNEL": "0",
    }
    assert env["VLLM_API_KEY"]["valueFrom"]["secretKeyRef"] == {
        "name": "kagent-model-route-key", "key": "api-key"
    }
    assert container["readinessProbe"]["httpGet"] == {"path": "/health", "port": 8000}
    assert primary["spec"]["template"]["spec"]["serviceAccountName"] == "edai2-retrieval-agent"
    comparison = documents(OVERLAY / "patch-comparison.yaml")[0]
    assert comparison["metadata"]["name"] == "llmd-comparison"
    assert comparison["spec"]["replicas"] == 0


def test_cpu_overlay_uses_primary_as_private_backend_without_scheduler_deployment() -> None:
    resources = documents(OVERLAY / "patch-router.yaml")
    assert len(resources) == 1
    service = resources[0]
    assert service["kind"] == "Service" and service["metadata"]["name"] == "llmd-router"
    assert service["spec"] == {
        "type": "ClusterIP", "selector": {"app": "llmd-primary"},
        "ports": [{"port": 8000, "targetPort": 8000}],
    }


def test_model_cache_initializer_downloads_generation_pinned_archives_and_shares_emptydir() -> None:
    patch = documents(OVERLAY / "patch-model-cache-init.yaml")[0]
    pod_spec = patch["spec"]["template"]["spec"]
    assert patch["kind"] == "Deployment" and patch["metadata"]["name"] == "llmd-primary"
    checksums = patch["spec"]["template"]["metadata"]["annotations"]
    assert checksums["checksum/llmd-cache-init"] == hashlib.sha256((OVERLAY / "cache-init.py").read_bytes()).hexdigest()
    assert checksums["checksum/llmd-cache-manifest"] == hashlib.sha256((OVERLAY / "model-cache-manifest.json").read_bytes()).hexdigest()
    init = pod_spec["initContainers"][0]
    assert init["image"] == CACHE_INIT_IMAGE
    assert init["command"] == ["python", "/opt/edai2/cache-init.py"]
    assert init["resources"] == {
        "requests": {"cpu": "100m", "memory": "256Mi", "ephemeral-storage": "8Gi"},
        "limits": {"cpu": "500m", "memory": "512Mi", "ephemeral-storage": "8Gi"},
    }
    assert {mount["name"] for mount in init["volumeMounts"]} == {"model-cache", "model-cache-manifest", "cache-init-script"}
    model = documents(OVERLAY / "patch-primary.yaml")[0]["spec"]["template"]["spec"]["containers"][0]
    comparison = documents(OVERLAY / "patch-comparison.yaml")[0]["spec"]["template"]["spec"]["containers"][0]
    assert model["image"] == CPU_IMAGE
    assert comparison["image"] == CPU_IMAGE
    assert {mount["name"] for mount in model["volumeMounts"]} == {"model-cache"}
    assert next(mount for mount in model["volumeMounts"] if mount["name"] == "model-cache")["readOnly"] is True
    assert {volume["name"] for volume in pod_spec["volumes"]} == {
        "model-cache", "model-cache-manifest", "cache-init-script"
    }
    assert pod_spec["volumes"][0]["emptyDir"]["sizeLimit"] == "8Gi"
    manifest = json.loads((OVERLAY / "model-cache-manifest.json").read_text(encoding="utf-8"))
    manifest_file_hash = hashlib.sha256((OVERLAY / "model-cache-manifest.json").read_bytes()).hexdigest()
    assert manifest_file_hash == "67609f908cf96cfb28d0910411a55dc8cb0670766dd17feb2405cb951ebf2dba"
    entry = next(item for item in manifest["objects"] if item["name"] == "primary")
    assert entry["generation"] == "1791335619032151"
    assert entry["sha256"] == "bb3fd27eedd21aa689191b721df4b443bdfac40b0e50c667319b6173f8ac0afa"
    assert hashlib.sha256(json.dumps({"objects": manifest["objects"]}, sort_keys=True, separators=(",", ":")).encode()).hexdigest() == manifest["manifest_sha256"]
    script = (OVERLAY / "cache-init.py").read_text(encoding="utf-8")
    assert manifest_file_hash in script


def test_cache_extractor_rejects_traversal_before_writing_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_cache_initializer("cache_init")
    archive = tmp_path / "unsafe.tar"
    outside = tmp_path / "escaped.txt"
    with tarfile.open(archive, "w") as tar:
        info = tarfile.TarInfo("model/../../escaped.txt")
        payload = b"must not escape"
        info.size = len(payload)
        import io
        tar.addfile(info, io.BytesIO(payload))
    use_plain_tar_for_zstd_stream(monkeypatch)
    with pytest.raises(ValueError, match="unsafe archive path"):
        module.validate_archive_members(archive)
    assert not outside.exists()


def test_cache_validator_rejects_link_members_before_extraction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_cache_initializer("cache_init_link")
    archive = tmp_path / "linked.tar"
    with tarfile.open(archive, "w") as tar:
        link = tarfile.TarInfo("model/weights-link")
        link.type = tarfile.SYMTYPE
        link.linkname = "weights.bin"
        tar.addfile(link)
    use_plain_tar_for_zstd_stream(monkeypatch)
    with pytest.raises(ValueError, match="unsupported archive entry type"):
        module.validate_archive_members(archive)


def test_cache_validation_uses_python_streaming_zstd_tar_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_cache_initializer("cache_init_stream_mode")
    archive = tmp_path / "model.tar"
    with tarfile.open(archive, "w") as tar:
        info = tarfile.TarInfo("model/weights.bin")
        payload = b"weights"
        info.size = len(payload)
        import io
        tar.addfile(info, io.BytesIO(payload))
    modes = use_plain_tar_for_zstd_stream(monkeypatch)
    assert module.validate_archive_members(archive) == "model"
    assert modes == [("r|zst", True)]


def test_cache_extraction_streams_a_second_pass_and_uses_data_filter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_cache_initializer("cache_init_stream_extract")
    archive = tmp_path / "model.tar"
    with tarfile.open(archive, "w") as tar:
        info = tarfile.TarInfo("model/weights.bin")
        payload = b"weights"
        info.size = len(payload)
        import io
        tar.addfile(info, io.BytesIO(payload))
    real_extract = tarfile.TarFile.extract
    modes = use_plain_tar_for_zstd_stream(monkeypatch)
    filters = []

    def extract_data_only(self, member, *args, **kwargs):
        filters.append(kwargs.get("filter"))
        return real_extract(self, member, *args, **kwargs)

    monkeypatch.setattr(tarfile.TarFile, "extract", extract_data_only)
    destination = tmp_path / "staged"
    destination.mkdir()
    assert module.validate_archive_members(archive) == "model"
    module.extract_validated_archive(archive, destination, "model")
    assert modes == [("r|zst", True), ("r|zst", True)]
    assert filters == ["data"]
    assert (destination / "model" / "weights.bin").read_bytes() == b"weights"


def test_cache_extractor_rejects_expanded_archive_over_five_gib_before_extracting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_cache_initializer("cache_init_expanded")
    monkeypatch.setattr(module, "MAX_EXPANDED_MODEL_BYTES", 5)
    archive = tmp_path / "oversized.tar"
    import io
    with tarfile.open(archive, "w") as tar:
        for name, payload in (("model/one", b"123"), ("model/two", b"456")):
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
    use_plain_tar_for_zstd_stream(monkeypatch)
    with pytest.raises(ValueError, match="expanded model archive exceeds"):
        module.validate_archive_members(archive)


def test_cache_extractor_stages_under_model_root_for_same_volume_promotion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_cache_initializer("cache_init_staging")
    model_root = tmp_path / "models"
    model_root.mkdir()
    monkeypatch.setattr(module, "MODEL_ROOT", model_root)
    with module.model_staging_directory() as temp:
        stage = Path(temp)
        assert stage.parent == model_root
        extracted = stage / "extract" / "primary"
        extracted.mkdir(parents=True)
        (extracted / "weights.bin").write_bytes(b"cached")
        module.promote_model_directory(extracted, model_root / "primary")
    assert (model_root / "primary" / "weights.bin").read_bytes() == b"cached"
