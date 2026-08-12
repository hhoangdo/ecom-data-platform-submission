from __future__ import annotations

from pathlib import Path

import pytest
import yaml


def resolve_live_gke_target(
    *, live_gke: bool, kubeconfig: str | None, context: str | None
) -> tuple[Path, str]:
    """Validate explicit live-GKE inputs without creating a Kubernetes client."""
    if not live_gke:
        raise pytest.UsageError("--live-gke is required for a live Kubernetes fixture")
    if not kubeconfig or not context:
        raise pytest.UsageError("--kubeconfig and --context are required with --live-gke")

    path = Path(kubeconfig)
    if not path.is_absolute() or not path.is_file():
        raise pytest.UsageError("--kubeconfig must name an absolute readable file")

    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    names = {
        item.get("name")
        for item in loaded.get("contexts", [])
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    if context not in names:
        raise pytest.UsageError("--context is absent from the supplied kubeconfig")
    if not context.startswith("gke_"):
        raise pytest.UsageError("--context must be an explicit GKE context")
    return path, context


@pytest.fixture
def live_gke_target(pytestconfig: pytest.Config) -> tuple[Path, str]:
    """Expose only validated explicit live-GKE inputs to later live tests."""
    return resolve_live_gke_target(
        live_gke=bool(pytestconfig.getoption("live_gke")),
        kubeconfig=pytestconfig.getoption("kubeconfig"),
        context=pytestconfig.getoption("context"),
    )
