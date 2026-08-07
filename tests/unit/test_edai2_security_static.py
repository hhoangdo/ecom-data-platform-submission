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
