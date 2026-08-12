from __future__ import annotations

import sys
from pathlib import Path

import pytest


SRC_PATH = Path(__file__).resolve().parents[1] / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register shared live-GKE opt-in once for every test subtree."""
    group = parser.getgroup("live-gke")
    group.addoption("--live-gke", action="store_true", default=False)
    group.addoption("--kubeconfig", default=None)
    group.addoption("--context", default=None)
