"""Bind changed production Python to coverage and mutation configuration."""

from __future__ import annotations

import argparse
import configparser
import fnmatch
import subprocess
import sys
import tomllib
from pathlib import Path

import yaml


MUTATION_TEST_SELECTION = [
    "tests/unit/llm",
    "tests/contract/llm",
    "tests/property/llm",
    "tests/integration/llm",
]


def _git_lines(*args: str) -> set[str]:
    completed = subprocess.run(["git", *args], check=True, capture_output=True, text=True)
    return {line.strip().replace("\\", "/") for line in completed.stdout.splitlines() if line.strip()}


def _contains(root: str, path: str) -> bool:
    return path == root or path.startswith(root.rstrip("/") + "/")


def _omits_declared_path(pattern: str, declared_path: str) -> bool:
    normalized = pattern.replace("\\", "/")
    probe = declared_path.rstrip("/") + "/__scope_probe__.py"
    if fnmatch.fnmatchcase(declared_path, normalized) or fnmatch.fnmatchcase(probe, normalized):
        return True
    if not any(token in normalized for token in "*?["):
        return _contains(normalized, declared_path)
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--scope", type=Path, required=True)
    parser.add_argument("--coverage-config", type=Path, required=True)
    parser.add_argument("--pyproject", type=Path, required=True)
    args = parser.parse_args()
    try:
        _git_lines("rev-parse", "--verify", f"{args.base_ref}^{{commit}}")
        changed = _git_lines("diff", "--name-only", f"{args.base_ref}...HEAD") | _git_lines("diff", "--name-only") | _git_lines("diff", "--cached", "--name-only") | _git_lines("ls-files", "--others", "--exclude-standard")
        production = {path for path in changed if path.startswith("src/vina_bim_shop/") and path.endswith(".py")}
        scope = yaml.safe_load(args.scope.read_text(encoding="utf-8"))
        declared = [item.replace("\\", "/") for item in scope["production_roots"]]
        coverage = configparser.ConfigParser()
        coverage.read(args.coverage_config, encoding="utf-8")
        coverage_paths = [line.strip().replace("\\", "/") for line in coverage["run"]["source"].splitlines() if line.strip()]
        coverage_omits = [line.strip().replace("\\", "/") for line in coverage["run"].get("omit", "").splitlines() if line.strip()]
        pyproject = tomllib.loads(args.pyproject.read_text(encoding="utf-8"))
        mutation_paths = [item.replace("\\", "/") for item in pyproject["tool"]["mutmut"]["paths_to_mutate"]]
        mutation_tests = pyproject["tool"]["mutmut"]["pytest_add_cli_args_test_selection"]
    except (KeyError, OSError, subprocess.CalledProcessError, tomllib.TOMLDecodeError, yaml.YAMLError) as error:
        print(f"scope verification setup failed: {error}", file=sys.stderr)
        return 1
    declared_missing = [
        path
        for path in declared
        if not all(any(_contains(root, path) for root in targets) for targets in (coverage_paths, mutation_paths))
    ]
    if declared_missing:
        print("declared scope is not measured: " + ", ".join(sorted(declared_missing)), file=sys.stderr)
        return 1
    if mutation_tests != MUTATION_TEST_SELECTION:
        print("mutation test selection differs from the authored LLM quality suites", file=sys.stderr)
        return 1
    omitted_declared = [path for path in declared if any(_omits_declared_path(pattern, path) for pattern in coverage_omits)]
    if omitted_declared:
        print("declared scope is omitted: " + ", ".join(sorted(omitted_declared)), file=sys.stderr)
        return 1
    failures = [path for path in sorted(production) if not all(any(_contains(root, path) for root in targets) for targets in (declared, coverage_paths, mutation_paths))]
    if failures:
        print("scope omissions: " + ", ".join(failures), file=sys.stderr)
        return 1
    print("verified production scope: " + ", ".join(sorted(production)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
