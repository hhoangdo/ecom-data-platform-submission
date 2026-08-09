from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml


def parse_ttl(value: str) -> int:
    if not value.endswith("h") or not value[:-1].isdigit():
        raise ValueError("TTL must use non-negative whole-hour h notation")
    hours = int(value[:-1])
    if not 0 < hours <= 6:
        raise ValueError("TTL must be between 1h and 6h")
    return hours


def render_profile(profiles: dict, profile: str, ttl: str | None, *, dry_run: bool) -> dict:
    if profile not in profiles["profiles"]:
        raise ValueError("unknown profile")
    if not dry_run:
        raise ValueError("only --dry-run is available in Topic 17")
    if profile == "suspended":
        if ttl is not None:
            raise ValueError("suspended does not accept TTL")
        ttl_hours = 0
    else:
        if ttl is None:
            raise ValueError("active profiles require TTL")
        ttl_hours = parse_ttl(ttl)
    return {"dry_run": True, "profile": profile, "ttl_hours": ttl_hours, "resources": profiles["profiles"][profile]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", choices=("suspended", "core", "rubric-evidence"))
    parser.add_argument("--ttl")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        profiles = yaml.safe_load(Path("configs/gke/profiles.yaml").read_text(encoding="utf-8"))
        print(json.dumps(render_profile(profiles, args.profile, args.ttl, dry_run=args.dry_run), sort_keys=True))
        return 0
    except (OSError, ValueError, yaml.YAMLError) as error:
        parser.error(str(error))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
