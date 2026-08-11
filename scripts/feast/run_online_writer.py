"""Fail-closed local entry point for the online writer image."""

from __future__ import annotations

import argparse
import json

from vina_bim_shop.llm.streaming.offline_writer import ONLINE_CONSUMER_GROUP, UPDATE_TOPIC


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.dry_run:
        parser.error("a runtime adapter is required; this static CLI only supports --dry-run")
    print(json.dumps({"consumer_group": ONLINE_CONSUMER_GROUP, "destination": "online", "topic": UPDATE_TOPIC}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
