from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]


def _load_script():
    path = ROOT / "scripts/llm/run_evaluation.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _baselines() -> dict:
    return {
        "report": {"case_count": 60, "report": {"passed": False}},
        "agent_ab": {"assignment": [{"session": f"s{i}", "arm": "v1-primary"} for i in range(120)]},
        "model_ab": {"assignment": [{"session": f"s{i}", "arm": "v1-primary"} for i in range(120)]},
    }


def _rerun_ok(tuning: dict) -> dict:
    _ = tuning
    return {
        "report": {"case_count": 60, "report": {"passed": True}},
        "agent_ab": {"assignment": [{"session": f"s{i}", "arm": "v1-primary"} for i in range(120)]},
        "model_ab": {"assignment": [{"session": f"s{i}", "arm": "v1-primary"} for i in range(120)]},
    }


def test_bounded_retry_preserves_baselines_and_records_tuning() -> None:
    run = _load_script()
    result = run.bounded_eval_retry(
        _baselines(), tuning={"retrieval_top_k": 8}, diagnosis="recall shortfall",
        rerun=_rerun_ok,
    )
    assert result["retry_number"] == 1
    assert result["tuning"] == {"retrieval_top_k": 8}
    assert result["baselines"]["report"]["report"]["passed"] is False
    assert result["results"]["report"]["report"]["passed"] is True


def test_bounded_retry_refuses_second_retry_foreign_tuning_or_drift() -> None:
    run = _load_script()
    with pytest.raises(ValueError, match="tuning"):
        run.bounded_eval_retry(_baselines(), tuning={"seed": 1}, diagnosis="x", rerun=_rerun_ok)
    spent = _baselines()
    spent["report"]["retry_number"] = 1
    with pytest.raises(ValueError, match="retry"):
        run.bounded_eval_retry(spent, tuning={"retrieval_top_k": 8}, diagnosis="x", rerun=_rerun_ok)

    def drifting_rerun(tuning: dict) -> dict:
        _ = tuning
        payload = _rerun_ok(tuning)
        payload["agent_ab"]["assignment"] = payload["agent_ab"]["assignment"][:100]
        return payload

    with pytest.raises(ValueError, match="assignment"):
        run.bounded_eval_retry(_baselines(), tuning={"retrieval_top_k": 8}, diagnosis="x", rerun=drifting_rerun)


def test_novel_effective_date_boundary_proves_three_cases() -> None:
    run = _load_script()
    cases = [
        {"boundary": "immediately-before", "expected_visible": False},
        {"boundary": "at", "expected_visible": True},
        {"boundary": "immediately-after", "expected_visible": True},
    ]

    def probe(case: dict) -> dict:
        return {"visible": case["expected_visible"], "version": "v2", "content_hash": "ab" + "cd" * 31}

    result = run.prove_novel_idea(kind="effective-dated-boundary", cases=cases, probe_fn=probe)
    assert result["boundaries"] == ["immediately-before", "at", "immediately-after"]
    assert all(len(item["content_hash"]) == 64 for item in result["observations"])


def test_novel_citation_integrity_rejects_both_cases() -> None:
    run = _load_script()
    cases = [{"case": "tampered-hash"}, {"case": "unsupported-claim"}]

    def probe(case: dict) -> dict:
        return {
            "rejected": True, "source_hash": "12" * 32, "content_hash": "34" * 32,
            "safety_action": "reject",
        }

    result = run.prove_novel_idea(kind="citation-integrity", cases=cases, probe_fn=probe)
    assert result["rejected"] == 2

    def soft_probe(case: dict) -> dict:
        _ = case
        return {"rejected": False, "source_hash": "12" * 32, "content_hash": "34" * 32, "safety_action": "allow"}

    with pytest.raises(ValueError, match="reject"):
        run.prove_novel_idea(kind="citation-integrity", cases=cases, probe_fn=soft_probe)
