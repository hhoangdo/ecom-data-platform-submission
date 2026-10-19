from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]


def _load_script():
    path = ROOT / "scripts/qa/capture_edai2_evidence.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _runner(mapping: dict):
    calls: list[list[str]] = []

    def run(command: list[str], timeout: int):
        calls.append(command)
        for key, result in mapping.items():
            if any(key in part for part in command):
                if isinstance(result, TimeoutError):
                    raise result
                return result
        raise AssertionError(command)

    run.calls = calls  # type: ignore[attr-defined]
    return run


def test_property_crosshair_collects_explicit_results() -> None:
    """Hypothesis seed/examples and bounded CrossHair statuses are recorded, not inferred."""
    capture = _load_script()
    runner = _runner({
        "test_idempotency": {"exit_code": 0, "output": "2 passed in 1.0s", "seed": 0},
        "contracts": {"exit_code": 0, "output": "CHECKED 3 paths, no counterexample", "status": "pass"},
        "indexing": {"exit_code": 0, "output": "CHECKED 5 paths, no counterexample", "status": "pass"},
    })
    result = capture.collect_property_crosshair(
        hypothesis_target="tests/property/llm/test_idempotency.py",
        crosshair_targets=["src/vina_bim_shop/llm/contracts.py", "src/vina_bim_shop/llm/indexing.py"],
        per_condition_timeout=10, per_path_timeout=3, runner=runner, seed=0,
    )
    assert result["hypothesis"]["exit_code"] == 0
    assert result["crosshair"]["src/vina_bim_shop/llm/contracts.py"]["status"] == "pass"
    assert all("counterexample" in str(item) or item["status"] == "pass" for item in result["crosshair"].values())


def test_property_crosshair_records_timeout_as_timeout() -> None:
    capture = _load_script()
    runner = _runner({
        "test_idempotency": {"exit_code": 0, "output": "2 passed", "seed": 0},
        "contracts": TimeoutError(),
    })
    result = capture.collect_property_crosshair(
        hypothesis_target="tests/property/llm/test_idempotency.py",
        crosshair_targets=["src/vina_bim_shop/llm/contracts.py"],
        per_condition_timeout=10, per_path_timeout=3, runner=runner, seed=0,
    )
    assert result["crosshair"]["src/vina_bim_shop/llm/contracts.py"]["status"] == "timeout"
    assert result["passed"] is False


def test_property_crosshair_rejects_empty_targets() -> None:
    capture = _load_script()
    runner = _runner({})
    with pytest.raises(ValueError, match="target"):
        capture.collect_property_crosshair(
            hypothesis_target="", crosshair_targets=[],
            per_condition_timeout=10, per_path_timeout=3, runner=runner, seed=0,
        )
