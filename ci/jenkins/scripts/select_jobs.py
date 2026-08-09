"""Select fail-closed Topic 16 Jenkins jobs from git name-status records."""

from __future__ import annotations

import argparse
import fnmatch
import json
from pathlib import Path
from typing import Iterable

import yaml


ROOT = Path(__file__).resolve().parents[3]
MAP_PATH = ROOT / "ci/jenkins/change-map.yaml"


def changed_paths(change: str) -> list[str]:
    status, separator, payload = change.partition(":")
    if not separator or not payload:
        raise ValueError("change must use STATUS:path or RNNN:old:new form")
    if status.startswith("R"):
        old, rename_separator, new = payload.partition(":")
        if not rename_separator or not old or not new:
            raise ValueError("rename must contain both old and new paths")
        return [old, new]
    if status not in {"A", "M", "D", "T"}:
        raise ValueError(f"unsupported git status: {status}")
    return [payload]


def matches(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def select(changes: Iterable[str], force_all: bool = False) -> list[str]:
    mapping = yaml.safe_load(MAP_PATH.read_text(encoding="utf-8"))
    all_jobs = mapping["all_jobs"]
    if force_all:
        return all_jobs
    selected: set[str] = set()
    for change in changes:
        for path in changed_paths(change):
            if matches(path, mapping["shared_paths"]):
                return all_jobs
            matched = False
            for rule in mapping["rules"]:
                if matches(path, rule["paths"]):
                    selected.add(rule["job"])
                    matched = True
            if not matched:
                return all_jobs
    return sorted(selected) if selected else all_jobs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--change", action="append", default=[])
    parser.add_argument("--changes-file", type=Path)
    parser.add_argument("--force-all", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    changes = list(args.change)
    if args.changes_file is not None:
        changes.extend(line.strip().replace("\t", ":") for line in args.changes_file.read_text(encoding="utf-8").splitlines() if line.strip())
    print(json.dumps(select(changes, force_all=args.force_all)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
