"""Fail-closed static smoke/rollback command contract."""

from __future__ import annotations

import argparse
import json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--release", choices=("retrieval", "drift", "coordinator", "llmd-primary"))
    parser.add_argument("--streaming-writers", action="store_true")
    parser.add_argument("--prove-atomic-rollback", action="store_true")
    parser.add_argument("--prove-model-rollback", action="store_true")
    args = parser.parse_args()
    if not args.dry_run:
        parser.error("live smoke and rollback execution belongs to a future GKE evidence topic; use --dry-run")
    print(json.dumps({"live_execution": False, "release": args.release, "streaming_writers": args.streaming_writers}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
