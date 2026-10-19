from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
CASES = ROOT / "tests/fixtures/llm/evaluation_cases.jsonl"


def _load_script():
    path = ROOT / "scripts/llm/run_evaluation.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _live_chat(case) -> dict:
    if case.kind == "grounded":
        return {
            "top4_chunk_ids": list(case.relevant_chunk_ids)[:4] or ["x"],
            "abstained": False, "factual_claim_count": 1, "cited_claim_count": 1,
            "verified_cited_claim_count": 1, "safety_action": "allow",
            "forbidden_disclosure": False, "retrieval_ms": 100.0, "generation_ms": 500.0,
        }
    if case.kind == "abstention":
        return {
            "top4_chunk_ids": (), "abstained": True, "factual_claim_count": 0,
            "cited_claim_count": 0, "verified_cited_claim_count": 0, "safety_action": "abstain",
            "forbidden_disclosure": False, "retrieval_ms": 100.0, "generation_ms": 0.0,
        }
    if case.kind == "injection":
        return {
            "top4_chunk_ids": (), "abstained": False, "factual_claim_count": 0,
            "cited_claim_count": 0, "verified_cited_claim_count": 0, "safety_action": "reject",
            "forbidden_disclosure": False, "retrieval_ms": 0.0, "generation_ms": 0.0,
        }
    return {
        "top4_chunk_ids": (), "abstained": False, "factual_claim_count": 0,
        "cited_claim_count": 0, "verified_cited_claim_count": 0, "safety_action": "redact",
        "forbidden_disclosure": False, "retrieval_ms": 0.0, "generation_ms": 0.0,
    }


def test_live_evaluation_runs_exactly_sixty_cases() -> None:
    """The primary evaluation is exactly the 60 static routed cases."""
    run = _load_script()
    report = run.run_live_evaluation(
        cases_path=CASES, chat_fn=_live_chat, revision="d" * 40,
        route_manifest_hash="e" * 64,
    )
    assert report["report"]["case_count"] == 60
    assert report["route_manifest_hash"] == "e" * 64


def test_agent_ab_promotes_only_on_locked_improvement() -> None:
    """A 2-point quality gain with no safety/tool/p95 regression promotes."""
    run = _load_script()
    uuids = run.stable_uuids("agent_exp_v1", 60)

    def session_fn(arm: str, session: str) -> dict:
        improved = arm == "v2-primary"
        return {
            "grounded": 0.86 if improved else 0.83, "citation_precision": 0.9,
            "safety_pass": True, "tool_failed": False, "latency_ms": 1000.0, "cost": 0.01,
        }

    result = run.run_ab_experiment(
        kind="agent", experiment="agent_exp_v1", sessions_per_arm=60, uuids=uuids,
        runtime_a="v1-primary", runtime_b="v2-primary", session_fn=session_fn,
        index_version="canonical-evidence-" + "f" * 40, prior_alias="v1-primary",
    )
    assert result["decision"] == "promote" and result["alias"] == "v2-primary"
    assert len(result["assignment"]) == 120


def test_agent_ab_holds_prior_alias_on_safety_regression() -> None:
    run = _load_script()
    uuids = run.stable_uuids("agent_exp_v1", 60)

    def session_fn(arm: str, session: str) -> dict:
        return {
            "grounded": 0.9, "citation_precision": 0.95,
            "safety_pass": arm == "v1-primary", "tool_failed": False,
            "latency_ms": 1000.0, "cost": 0.01,
        }

    result = run.run_ab_experiment(
        kind="agent", experiment="agent_exp_v1", sessions_per_arm=60, uuids=uuids,
        runtime_a="v1-primary", runtime_b="v2-primary", session_fn=session_fn,
        index_version="canonical-evidence-" + "f" * 40, prior_alias="v1-primary",
    )
    assert result["decision"] == "hold" and result["alias"] == "v1-primary"


def test_model_ab_requires_all_gates_plus_cost() -> None:
    run = _load_script()
    uuids = run.stable_uuids("model_exp_v1", 60)

    def session_fn(arm: str, session: str) -> dict:
        cheap = arm == "v1-comparison"
        return {
            "grounded": 0.9, "citation_precision": 0.95, "safety_pass": True,
            "tool_failed": False, "latency_ms": 500.0 if cheap else 600.0,
            "retrieval_ms": 100.0, "generation_ms": 500.0,
            "cost": 0.008 if cheap else 0.010,
        }

    result = run.run_ab_experiment(
        kind="model", experiment="model_exp_v1", sessions_per_arm=60, uuids=uuids,
        runtime_a="v1-primary", runtime_b="v1-comparison", session_fn=session_fn,
        index_version="canonical-evidence-" + "f" * 40, prior_alias="v1-primary",
    )
    assert result["decision"] == "promote" and result["alias"] == "v1-comparison"


def test_stable_uuids_are_deterministic_and_unique() -> None:
    run = _load_script()
    first, second = run.stable_uuids("exp", 60), run.stable_uuids("exp", 60)
    assert first == second and len(set(first)) == 120
    assert run.stable_uuids("other", 60) != first
