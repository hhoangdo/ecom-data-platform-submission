from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("live-gke")
    group.addoption("--live-gke", action="store_true", default=False)
    group.addoption("--kubeconfig", default=None)
    group.addoption("--context", default=None)
