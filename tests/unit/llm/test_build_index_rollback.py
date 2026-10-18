"""Index alias rollback contracts for Topic 26 evidence (Task 5)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
BUILD_INDEX = ROOT / "scripts/llm/build_index.py"


def _build_index():
    assert BUILD_INDEX.is_file(), "missing index builder"
    spec = importlib.util.spec_from_file_location("topic26_build_index", BUILD_INDEX)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeStore:
    """CAS-backed active alias store shaped like FeastPostgresAdapter."""

    def __init__(self, active: str | None, validated: set[str]) -> None:
        self.alias = active
        self.validated = set(validated)
        self.cas_calls: list[tuple] = []

    def active_version(self) -> str | None:
        return self.alias

    def is_validated(self, version: str) -> bool:
        return version in self.validated

    def compare_and_swap_active(self, expected: str | None, next_version: str | None) -> str | None:
        self.cas_calls.append((expected, next_version))
        if self.alias != expected:
            raise RuntimeError("active alias no longer matches the expected version")
        self.alias = next_version
        return self.alias


class AsyncStore(FakeStore):
    async def active_version(self):  # type: ignore[override]
        return super().active_version()

    async def is_validated(self, version: str) -> bool:  # type: ignore[override]
        return super().is_validated(version)

    async def compare_and_swap_active(  # type: ignore[override]
        self, expected: str | None, next_version: str | None
    ) -> str | None:
        return super().compare_and_swap_active(expected, next_version)


def test_injected_validation_failure_leaves_active_alias() -> None:
    module = _build_index()
    store = FakeStore("v3", validated=set())

    evidence = module.run_index_rollback(
        adapter=store,
        candidate_version="v4-bad",
        previous_good="v2",
        eval_fn=lambda: {"pass": True},
        inject_validation_failure=True,
    )

    assert store.alias == "v3"
    assert evidence["active_unchanged"] is True
    assert evidence["rollback_to"] == "v2"
    assert evidence["restored_current"] is True
    assert evidence["eval_pass"] is True


def test_async_adapter_bridge_returns_same_evidence() -> None:
    module = _build_index()
    store = AsyncStore("v3", validated=set())

    evidence = module.run_index_rollback(
        adapter=store,
        candidate_version="v4-bad",
        previous_good="v2",
        eval_fn=lambda: {"pass": True},
        inject_validation_failure=True,
    )

    assert store.alias == "v3"
    assert evidence["active_unchanged"] is True


def test_rollback_uses_compare_and_swap_with_current_expected() -> None:
    module = _build_index()
    store = FakeStore("v3", validated=set())

    module.run_index_rollback(
        adapter=store,
        candidate_version="v4-bad",
        previous_good="v2",
        eval_fn=lambda: {"pass": True},
        inject_validation_failure=True,
    )

    assert ("v3", "v2") in store.cas_calls
    assert store.cas_calls[-1][1] == "v3"


def test_validated_candidate_without_inject_promotes_then_restores() -> None:
    module = _build_index()
    store = FakeStore("v3", validated={"v4-good"})

    evidence = module.run_index_rollback(
        adapter=store,
        candidate_version="v4-good",
        previous_good="v2",
        eval_fn=lambda: {"pass": True},
        inject_validation_failure=False,
    )

    assert evidence["promoted"] is True
    assert evidence["rollback_to"] == "v2"
    assert store.alias == "v3"


def test_eval_regression_fails_closed() -> None:
    module = _build_index()
    store = FakeStore("v3", validated=set())

    with pytest.raises(ValueError, match="evaluation"):
        module.run_index_rollback(
            adapter=store,
            candidate_version="v4-bad",
            previous_good="v2",
            eval_fn=lambda: {"pass": False},
            inject_validation_failure=True,
        )


def test_main_accepts_index_rollback_flags() -> None:
    module = _build_index()

    args = module.parse_args(
        [
            "--kubeconfig",
            "kubeconfig",
            "--context",
            "edai2-gke",
            "--mode",
            "candidate",
            "--inject-validation-failure",
            "--verify-active-unchanged",
            "--rollback-to-previous",
            "--previous-good",
            "v2",
            "--restore-current",
            "--index-version",
            "v4-bad",
            "--output",
            "index.json",
            "--chat-base-url",
            "http://chat.local",
        ]
    )

    assert args.inject_validation_failure is True
    assert args.rollback_to_previous is True
    assert args.previous_good == "v2"
