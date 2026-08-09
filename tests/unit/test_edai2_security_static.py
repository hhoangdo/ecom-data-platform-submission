from __future__ import annotations

import re
from pathlib import Path


def _scoped_files(root: Path) -> list[Path]:
    paths = [root / "src" / "vina_bim_shop" / "llm"]
    paths.extend([root / "configs" / "llm", root / "configs" / "gke"])
    text_suffixes = {".py", ".yaml", ".yml", ".json", ".ini"}
    return [
        path
        for directory in paths
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in text_suffixes
    ]


def test_static_contracts_reject_mutable_or_hosted_runtime_paths() -> None:
    root = Path(__file__).resolve().parents[2]
    text = "\n".join(path.read_text(encoding="utf-8") for path in _scoped_files(root)).lower()
    forbidden = [
        "api.openai.com",
        "api.anthropic.com",
        "ansible",
        "cloud build",
        "gcloud compute",
        "docker build",
        "kubectl apply",
        "helm install",
        "begin private key",
        "api_key",
        "secret_key",
        "password:",
    ]
    assert not any(value in text for value in forbidden)
    config_text = "\n".join(
        (root / directory).read_text(encoding="utf-8")
        for directory in [
            "configs/llm/models.yaml",
            "configs/llm/routing.yaml",
            "configs/gke/profiles.yaml",
            "configs/gke/cost_envelope.yaml",
        ]
    ).lower()
    assert ":latest" not in config_text
    assert "@latest" not in config_text


def test_all_declared_images_use_immutable_sha256_digests() -> None:
    root = Path(__file__).resolve().parents[2]
    models = (root / "configs" / "llm" / "models.yaml").read_text(encoding="utf-8")
    image_lines = [line.strip() for line in models.splitlines() if "image:" in line]
    assert len(image_lines) == 6
    assert all(re.search(r"@sha256:[0-9a-f]{64}$", line) for line in image_lines)


def test_topic17_iac_and_secret_contracts_are_static_and_scoped() -> None:
    root = Path(__file__).resolve().parents[2]
    terraform_root = root / "infra" / "terraform" / "edai2"
    assert all((terraform_root / name).is_file() for name in (
        "versions.tf", "providers.tf", "variables.tf", "main.tf", "outputs.tf",
        "terraform.tfvars.example",
    ))
    for module in ("gke", "artifact_registry", "gcs", "kms", "iam", "budget"):
        module_root = root / "infra" / "terraform" / "modules" / module
        assert all((module_root / name).is_file() for name in ("main.tf", "variables.tf", "outputs.tf"))

    sources = [
        path for directory in (root / "infra" / "terraform", root / "infra" / "security")
        for path in directory.rglob("*")
        if path.is_file() and path.suffix in {".tf", ".hcl", ".yaml", ".yml"}
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in sources)
    for required in ("us-central1-a", "COS_CONTAINERD", "e2-highmem-4", "e2-standard-8", "0.50", "0.75", "0.90", "1.00", "model-cache/", "agent-substrate/", "langfuse-events/", "airflow-logs/", "backups/"):
        assert required in text
    forbidden = ("google_compute_instance", "ansible", "cloud build", "service_account_key", "runtimeClassName", "api.openai.com", "password:")
    assert not any(value.lower() in text.lower() for value in forbidden)


def test_topic17_vault_external_secret_projection_is_disjoint() -> None:
    root = Path(__file__).resolve().parents[2]
    external = root / "infra" / "security" / "external-secrets"
    assert all((external / name).is_file() for name in (
        "cluster-secret-store.yaml", "chat-basic-auth.yaml", "jenkins-controller.yaml",
        "kagent-gateway-keys.yaml", "facade-gateway-key.yaml", "postgres.yaml",
        "clickhouse.yaml", "valkey.yaml", "redpanda.yaml", "airflow.yaml", "datahub.yaml",
        "langfuse.yaml", "agentregistry.yaml", "grafana.yaml",
    ))
    gateway = (external / "kagent-gateway-keys.yaml").read_text(encoding="utf-8")
    facade = (external / "facade-gateway-key.yaml").read_text(encoding="utf-8")
    store = (external / "cluster-secret-store.yaml").read_text(encoding="utf-8")
    assert "path: kv" in store
    assert "edai2/kagent/gateway-keys" in gateway
    assert all(key in gateway for key in ("model-api-key", "support-authorization", "drift-authorization", "coordinator-authorization", "api-key", "support-retrieval", "drift-detect", "coordinator-to-specialist"))
    assert "edai2/facade/gateway-entry" in facade
    assert "authorization" in facade
    assert "edai2/kagent/gateway-keys" not in facade
    assert "refreshInterval: 1h" in gateway
