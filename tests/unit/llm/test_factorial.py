from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
REQUESTS = [{"prompt": f"prompt {index}"} for index in range(40)]
PRICING = {"per_1k_prompt": 0.01, "per_1k_completion": 0.03}


def _load_script():
    path = ROOT / "scripts/llm/benchmark_inference.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _generate(model: str, cache: str, router: str, kind: str, index: int, request: dict):
    del model, router, request
    base = 4000.0 if kind == "cold" else (2000.0 if cache == "on" else 4000.0)
    return {
        "ttft_ms": base + index, "generation_ms": base * 2 + index,
        "prompt_tokens": 100, "completion_tokens": 50, "cache_hit": cache == "on" and kind == "warm",
    }


def _serial_state(active: str):
    def state() -> dict:
        return {"primary": 2 if active == "primary" else 0, "comparison": 2 if active == "comparison" else 0}

    return state


def test_factorial_runs_sixteen_serial_cells_with_locked_constants() -> None:
    """Two models times four configs times cold/warm, inactive always zero."""
    bench = _load_script()
    checks = {"n": 0}

    def state() -> dict:
        active = "primary" if checks["n"] < 4 else "comparison"
        checks["n"] += 1
        return {"primary": 2 if active == "primary" else 0, "comparison": 0 if active == "primary" else 2}

    order = ["primary", "comparison"]

    def switching_generate(model: str, cache: str, router: str, kind: str, index: int, request: dict):
        return _generate(model, cache, router, kind, index, request)

    payload = bench.run_factorial(
        generate=switching_generate, requests=REQUESTS, models=order,
        serial_state=state, pricing=PRICING,
    )
    assert len(payload["cells"]) == 16
    assert payload["constants"]["seed"] == 20260715
    assert all(cell["inactive_replicas"] == 0 for cell in payload["cells"])
    assert payload["gates"]["generation_p95_ms"] <= 20000

def test_factorial_rejects_nonzero_inactive_model() -> None:
    bench = _load_script()
    with pytest.raises(ValueError, match="inactive"):
        bench.run_factorial(
            generate=_generate, requests=REQUESTS, models=["primary"],
            serial_state=lambda: {"primary": 2, "comparison": 1}, pricing=PRICING,
        )


def test_verify_factorial_accepts_honest_miss_but_rejects_missing_samples() -> None:
    bench = _load_script()
    checks = {"n": 0}

    def state() -> dict:
        active = "primary" if checks["n"] < 4 else "comparison"
        checks["n"] += 1
        return {"primary": 2 if active == "primary" else 0, "comparison": 0 if active == "primary" else 2}

    def switching_generate(model: str, cache: str, router: str, kind: str, index: int, request: dict):
        return _generate(model, cache, router, kind, index, request)

    payload = bench.run_factorial(
        generate=switching_generate, requests=REQUESTS, models=["primary", "comparison"],
        serial_state=state, pricing=PRICING,
    )
    cost = {"totals": payload["cost_totals"]}
    result = bench.verify_inference_factorial(payload, cost)
    assert result["cells"] == 16
    del next(cell for cell in payload["cells"] if cell["thermal"] == "warm")["samples"][0]
    with pytest.raises(ValueError, match="sample"):
        bench.verify_inference_factorial(payload, cost)


def test_bounded_retry_refuses_second_retry_or_locked_change() -> None:
    bench = _load_script()
    baseline = {"retry_number": 0, "cells": [], "constants": dict(bench.LOCKED_CONSTANTS)}
    with pytest.raises(ValueError, match="locked"):
        bench.retry_factorial(
            baseline, generate=_generate, requests=REQUESTS, models=["primary"],
            serial_state=lambda: {"primary": 2, "comparison": 0}, pricing=PRICING,
            tuning={"seed": 1}, diagnosis="test",
        )
    retried = {"retry_number": 1}
    with pytest.raises(ValueError, match="retry"):
        bench.retry_factorial(
            retried, generate=_generate, requests=REQUESTS, models=["primary"],
            serial_state=lambda: {"primary": 2, "comparison": 0}, pricing=PRICING,
            tuning={"cache": "on"}, diagnosis="test",
        )


def test_agent_startup_matrix_compares_cold_and_prewarm() -> None:
    bench = _load_script()
    calls: list[tuple] = []

    def scale_pool(minimum: int) -> None:
        calls.append(("scale", minimum))

    def chat_session(agent: str, arm: str, session: int) -> dict:
        cold = arm == "cold"
        return {
            "startup_ms": (5000 if cold else 3000) + session,
            "ttft_ms": 2000.0, "cost": 0.010 if cold else 0.008,
            "quality": 0.9, "safety_pass": True, "pending_proof": {"from": 0, "to": 1} if cold else None,
        }

    result = bench.run_agent_startup_matrix(
        scale_pool=scale_pool, chat_session=chat_session,
        agents=["retrieval", "drift", "coordinator"], sessions_per_agent=20,
    )
    assert result["samples"] == 120
    assert calls[0] == ("scale", 0) and calls[-1] == ("scale", 1)
    assert result["startup_p95_improvement_pct"] >= 20
    assert result["cost_per_100_improvement_pct"] >= 5
