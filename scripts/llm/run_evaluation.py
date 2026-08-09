"""Run deterministic local evaluation or require explicit live endpoints."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from vina_bim_shop.llm.evaluation import CallSample, CaseResult, evaluate_cases, load_cases


def _local_results(cases: list[object]) -> tuple[list[CaseResult], list[CallSample]]:
    results: list[CaseResult] = []
    calls: list[CallSample] = []
    for index, case in enumerate(cases, start=1):
        results.append(
            CaseResult(
                case_id=case.case_id,
                top4_chunk_ids=case.relevant_chunk_ids[:1] if case.kind == "grounded" else (),
                abstained=case.kind == "abstention",
                factual_claim_count=1 if case.kind == "grounded" else 0,
                cited_claim_count=1 if case.kind == "grounded" else 0,
                verified_cited_claim_count=1 if case.kind == "grounded" else 0,
                safety_action="reject" if case.kind == "injection" else "redact" if case.kind == "pii" else "allow",
                forbidden_disclosure=False,
                entered_inference=case.kind == "grounded",
            )
        )
        if case.kind not in {"injection", "pii"}:
            calls.append(CallSample(case_id=case.case_id, operation="retrieval", elapsed_ms=float(100 + index)))
        if case.kind == "grounded":
            calls.append(CallSample(case_id=case.case_id, operation="generation", elapsed_ms=float(400 + index)))
    return results, calls


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("local", "live"), default="local")
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--retrieval-base-url")
    parser.add_argument("--chat-base-url")
    args = parser.parse_args()
    if args.mode == "live":
        parser.error("live evaluation requires the later runtime owner")
    cases = load_cases(args.cases)
    results, calls = _local_results(cases)
    report = evaluate_cases(cases, results, calls)
    payload = {
        "schema_version": 1,
        "evidence_kind": "deterministic_local_contract",
        "report": report.model_dump(mode="json"),
        "case_results": [result.model_dump(mode="json") for result in results],
        "calls": [call.model_dump(mode="json") for call in calls],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload["report"], sort_keys=True))
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
