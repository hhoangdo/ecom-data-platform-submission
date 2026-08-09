from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from vina_bim_shop.llm.evaluation import (
    CallSample,
    CaseResult,
    EvaluationFailure,
    EvaluationReport,
    evaluate_cases,
    load_cases,
    nearest_rank_p95,
)


FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "llm" / "evaluation_cases.jsonl"


def _cases() -> list[object]:
    return load_cases(FIXTURE)


def _results(cases: list[object]) -> list[CaseResult]:
    results: list[CaseResult] = []
    for case in cases:
        kind = case.kind
        results.append(
            CaseResult(
                case_id=case.case_id,
                top4_chunk_ids=case.relevant_chunk_ids[:1] if kind == "grounded" else (),
                abstained=kind == "abstention",
                factual_claim_count=1 if kind == "grounded" else 0,
                cited_claim_count=1 if kind == "grounded" else 0,
                verified_cited_claim_count=1 if kind == "grounded" else 0,
                safety_action="reject" if kind == "injection" else "redact" if kind == "pii" else "allow",
                forbidden_disclosure=False,
                entered_inference=kind == "grounded",
            )
        )
    return results


def _calls(cases: list[object]) -> list[CallSample]:
    calls: list[CallSample] = []
    for index, case in enumerate(cases, start=1):
        if case.kind not in {"injection", "pii"}:
            calls.append(CallSample(case_id=case.case_id, operation="retrieval", elapsed_ms=float(100 + index)))
        if case.kind == "grounded":
            calls.append(CallSample(case_id=case.case_id, operation="generation", elapsed_ms=float(400 + index)))
    return calls


def test_fixture_is_exactly_partitioned_and_unique() -> None:
    cases = _cases()
    assert len(cases) == 60
    assert len({case.case_id for case in cases}) == 60
    assert [sum(case.category == category for case in cases) for category in (
        "returns", "shipping", "cancellation", "payments", "promotions", "warranties", "privacy", "marketplace_support"
    )] == [5, 5, 5, 5, 4, 4, 4, 4]
    assert sum(case.kind == "abstention" for case in cases) == 12
    assert sum(case.kind == "injection" for case in cases) == 6
    assert sum(case.kind == "pii" for case in cases) == 6


def test_evaluator_uses_locked_denominators_and_nearest_rank_p95() -> None:
    cases = _cases()
    report = evaluate_cases(cases, _results(cases), _calls(cases))
    assert report == EvaluationReport(
        case_count=60, recall_at_4=1.0, citation_precision=1.0,
        safety_pass_rate=1.0, retrieval_p95_ms=146.0, generation_p95_ms=435.0,
        passed=True,
    )
    assert nearest_rank_p95([1.0, 2.0, 3.0, 4.0]) == 4.0


def test_evaluator_fails_each_locked_aggregate_threshold_without_changing_denominators() -> None:
    cases = _cases()
    baseline_results = _results(cases)
    baseline_calls = _calls(cases)

    low_recall = [*baseline_results]
    for index in range(6):
        low_recall[index] = low_recall[index].model_copy(update={"top4_chunk_ids": ()})
    assert evaluate_cases(cases, low_recall, baseline_calls).model_dump() == {
        "case_count": 60, "recall_at_4": 30 / 36, "citation_precision": 1.0,
        "safety_pass_rate": 1.0, "retrieval_p95_ms": 146.0,
        "generation_p95_ms": 435.0, "passed": False,
    }

    low_precision = [*baseline_results]
    for index in range(4):
        low_precision[index] = low_precision[index].model_copy(update={"verified_cited_claim_count": 0})
    assert evaluate_cases(cases, low_precision, baseline_calls).citation_precision == 32 / 36
    assert evaluate_cases(cases, low_precision, baseline_calls).passed is False

    slow_retrieval = [
        call.model_copy(update={"elapsed_ms": 751.0}) if call.operation == "retrieval" else call
        for call in baseline_calls
    ]
    assert evaluate_cases(cases, baseline_results, slow_retrieval).retrieval_p95_ms == 751.0
    assert evaluate_cases(cases, baseline_results, slow_retrieval).passed is False


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda calls: calls.__setitem__(0, calls[0].model_copy(update={"status": "failed"})), "failed or timed out"),
        (lambda calls: calls.__setitem__(0, calls[0].model_copy(update={"retry_count": 1})), "silently retried"),
        (lambda calls: calls.__setitem__(0, calls[0].model_copy(update={"elapsed_ms": float("nan")})), "non-finite"),
        (lambda calls: calls.__setitem__(0, calls[0].model_copy(update={"case_id": "unknown"})), "unknown fixture"),
    ],
)
def test_evaluator_rejects_invalid_call_measurements(mutate: object, message: str) -> None:
    cases = _cases()
    calls = _calls(cases)
    mutate(calls)
    with pytest.raises(EvaluationFailure, match=message):
        evaluate_cases(cases, _results(cases), calls)


def test_evaluator_rejects_invalid_fixture_rows_and_p95_samples(tmp_path: Path) -> None:
    blank = tmp_path / "blank.jsonl"
    blank.write_text("\n", encoding="utf-8")
    with pytest.raises(EvaluationFailure, match="blank fixture row"):
        load_cases(blank)
    malformed = tmp_path / "malformed.jsonl"
    malformed.write_text("not-json\n", encoding="utf-8")
    with pytest.raises(EvaluationFailure, match="invalid fixture row"):
        load_cases(malformed)
    with pytest.raises(EvaluationFailure, match="non-empty finite"):
        nearest_rank_p95([])


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda results, calls: results.pop(), "exactly one result"),
        (lambda results, calls: results.__setitem__(0, results[0].model_copy(update={"abstained": True})), "grounded case lacks"),
        (lambda results, calls: results.__setitem__(0, results[0].model_copy(update={"verified_cited_claim_count": 2})), "citation claim denominator"),
        (lambda results, calls: results.__setitem__(36, results[36].model_copy(update={"abstained": False})), "did not abstain"),
        (lambda results, calls: results.__setitem__(48, results[48].model_copy(update={"safety_action": "allow"})), "injection safety"),
        (lambda results, calls: results.__setitem__(54, results[54].model_copy(update={"forbidden_disclosure": True})), "pii safety"),
        (lambda results, calls: calls.__delitem__([call.operation for call in calls].index("generation")), "missing required generation"),
    ],
)
def test_evaluator_rejects_invalid_result_aggregates(mutate: object, message: str) -> None:
    cases = _cases()
    results = _results(cases)
    calls = _calls(cases)
    mutate(results, calls)
    with pytest.raises(EvaluationFailure, match=message):
        evaluate_cases(cases, results, calls)


def test_evaluator_fails_before_aggregation_for_missing_or_invalid_measurements() -> None:
    cases = _cases()
    calls = _calls(cases)
    with pytest.raises(EvaluationFailure, match="missing required retrieval"):
        evaluate_cases(cases, _results(cases), calls[1:])
    invalid = [*calls]
    invalid[0] = invalid[0].model_copy(update={"elapsed_ms": float("nan")})
    with pytest.raises(EvaluationFailure, match="non-finite"):
        evaluate_cases(cases, _results(cases), invalid)


def test_local_cli_emits_only_deterministic_contract_evidence(tmp_path: Path) -> None:
    output = tmp_path / "evaluation.json"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/llm/run_evaluation.py",
            "--mode",
            "local",
            "--cases",
            str(FIXTURE),
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert '"evidence_kind": "deterministic_local_contract"' in output.read_text(encoding="utf-8")


def test_mutation_verifier_rejects_unknown_statuses(tmp_path: Path) -> None:
    results = tmp_path / "results.txt"
    output = tmp_path / "mutation.json"
    results.write_text("killed\nsurvived\nunknown\n", encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/qa/verify_edai2_mutation_score.py",
            "--results-file",
            str(results),
            "--min-exclusive",
            "0.80",
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0
    assert "unknown/unclassified" in completed.stderr


def test_mutation_verifier_parses_mutmut_result_lines(tmp_path: Path) -> None:
    results = tmp_path / "results.txt"
    output = tmp_path / "mutation.json"
    results.write_text("pkg.module.mutant_1: killed\npkg.module.mutant_2: survived\n", encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/qa/verify_edai2_mutation_score.py",
            "--results-file",
            str(results),
            "--min-exclusive",
            "0.49",
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(output.read_text(encoding="utf-8"))["score"] == 0.5


def test_mutation_verifier_maps_mutmut_no_tests_to_authored_untested(tmp_path: Path) -> None:
    results = tmp_path / "results.txt"
    output = tmp_path / "mutation.json"
    results.write_text("pkg.module.mutant_1: killed\npkg.module.mutant_2: no tests\n", encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/qa/verify_edai2_mutation_score.py",
            "--results-file",
            str(results),
            "--min-exclusive",
            "0.49",
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(output.read_text(encoding="utf-8"))["counts"]["untested"] == 1


def test_scope_verifier_accepts_the_locked_base_reference() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/qa/verify_edai2_test_scope.py",
            "--base-ref",
            "a5fe6ff7d62e2bb57ec515febc4ab243f73bf2b5",
            "--scope",
            "configs/llm/test_scope.yaml",
            "--coverage-config",
            "configs/llm/coverage.ini",
            "--pyproject",
            "pyproject.toml",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_scope_verifier_rejects_an_omitted_declared_path(tmp_path: Path) -> None:
    coverage = tmp_path / "coverage.ini"
    coverage.write_text(
        Path("configs/llm/coverage.ini")
        .read_text(encoding="utf-8")
        .replace(
            "\n[report]",
            "\n    src/vina_bim_shop/llm/*\n\n[report]",
            1,
        ),
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/qa/verify_edai2_test_scope.py",
            "--base-ref",
            "a5fe6ff7d62e2bb57ec515febc4ab243f73bf2b5",
            "--scope",
            "configs/llm/test_scope.yaml",
            "--coverage-config",
            str(coverage),
            "--pyproject",
            "pyproject.toml",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0
    assert "declared scope is omitted" in completed.stderr
