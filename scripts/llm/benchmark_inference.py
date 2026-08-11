"""Validate fixed benchmark definitions without contacting inference endpoints."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


FACTORIAL_ORDER = ["cache_off+load_aware", "cache_on+load_aware", "cache_off+prefix_aware", "cache_on+prefix_aware"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--phase", choices=("warmup", "factorial", "agent-startup", "experiment"), default="factorial")
    parser.add_argument("--models", nargs="*", default=["primary", "comparison"])
    parser.add_argument("--prompts", default="configs/llm/warmup_prompts.json")
    parser.add_argument("--requests-file", default="configs/llm/benchmark_requests.json")
    parser.add_argument("--global-concurrency", type=int, default=1)
    parser.add_argument("--output")
    args = parser.parse_args()
    if not args.dry_run:
        parser.error("live benchmark execution belongs to a future GKE evidence topic; use --dry-run")
    report = {
        "phase": args.phase,
        "models": args.models,
        "factorial_order": FACTORIAL_ORDER,
        "global_concurrency": args.global_concurrency,
        "prompts": args.prompts,
        "requests_file": args.requests_file,
        "live_execution": False,
    }
    if args.output:
        Path(args.output).write_text(json.dumps(report, sort_keys=True) + "\n", encoding="utf-8")
    else:
        print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
