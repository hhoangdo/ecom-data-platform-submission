"""Fail closed when mutmut statuses cannot prove the required score."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path


STATUSES = {"killed", "survived", "timeout", "suspicious", "untested"}


def _statuses(text: str) -> list[str]:
    values = [
        "untested" if value == "no tests" else value
        for value in (line.strip().rsplit(": ", 1)[-1].lower() for line in text.splitlines() if line.strip())
    ]
    unknown = [value for value in values if value not in STATUSES]
    if unknown:
        raise ValueError(f"unknown/unclassified statuses: {', '.join(unknown)}")
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-file", type=Path)
    parser.add_argument("--min-exclusive", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.results_file is None:
        completed = subprocess.run(["mutmut", "results", "--all", "true"], check=False, capture_output=True, text=True)
        if completed.returncode:
            print(completed.stderr, file=sys.stderr, end="")
            return completed.returncode
        raw = completed.stdout
    else:
        raw = args.results_file.read_text(encoding="utf-8")
    try:
        statuses = _statuses(raw)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    counts = Counter(statuses)
    denominator = sum(counts[status] for status in STATUSES)
    if denominator == 0:
        print("mutation result has no classified mutants", file=sys.stderr)
        return 1
    score = counts["killed"] / denominator
    payload = {"counts": {status: counts[status] for status in sorted(STATUSES)}, "denominator": denominator, "score": score, "min_exclusive": args.min_exclusive, "passed": score > args.min_exclusive}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not payload["passed"]:
        print(f"mutation score {score:.6f} is not strictly greater than {args.min_exclusive}", file=sys.stderr)
        return 1
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
