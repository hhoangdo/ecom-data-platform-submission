"""Fail-closed local entry point for the offline writer image."""

from __future__ import annotations

import argparse
import json

from vina_bim_shop.llm.streaming.offline_writer import OFFLINE_CONSUMER_GROUP, UPDATE_TOPIC


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Run long-lived for Deployment availability (streaming loop owns the consumer group).",
    )
    args = parser.parse_args()
    if args.serve:
        print(json.dumps({"consumer_group": OFFLINE_CONSUMER_GROUP, "destination": "offline", "topic": UPDATE_TOPIC, "mode": "serve"}, sort_keys=True), flush=True)
        import time

        while True:
            time.sleep(60)
    if not args.dry_run:
        parser.error("a runtime adapter is required; this static CLI only supports --dry-run")
    print(json.dumps({"consumer_group": OFFLINE_CONSUMER_GROUP, "destination": "offline", "topic": UPDATE_TOPIC}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
