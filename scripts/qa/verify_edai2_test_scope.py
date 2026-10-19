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

GENERATED_MARKERS = ("generated", "vendor", "_pb2.py", "/__")


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(["git", "-C", str(repo), *args], check=False, capture_output=True, text=True)
    if completed.returncode:
        raise ValueError(f"git ref is invalid: {' '.join(args)}")
    return completed.stdout


def derive_scope(repo: Path, base: str, head: str, config: Path) -> dict:
    """Derive changed production Python between refs; generated/vendor/tests never qualify."""
    try:
        _git(repo, "rev-parse", "--verify", f"{base}^{{commit}}")
        _git(repo, "rev-parse", "--verify", f"{head}^{{commit}}")
        names = _git(repo, "diff", "--name-only", f"{base}...{head}")
        cfg = yaml.safe_load(config.read_text(encoding="utf-8"))
        _ = cfg["production_roots"]
    except (OSError, KeyError, yaml.YAMLError) as error:
        raise ValueError(f"scope derivation setup failed: {error}") from error
    files = sorted(
        line.strip().replace("\\", "/")
        for line in names.splitlines()
        if line.strip().replace("\\", "/").startswith("src/vina_bim_shop/")
        and line.strip().endswith(".py")
        and not any(marker in line for marker in GENERATED_MARKERS)
    )
    hashes = {}
    for path in files:
        blob = _git(repo, "show", f"{head}:{path}")
        import hashlib

        hashes[path] = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    return {"base": base, "head": head, "files": files, "hashes": hashes}


def write_coverage_report(coverage_data: dict, scope: dict, output: Path, fail_under: float) -> float:
    """Write the coverage JSON and fail closed below the locked floor."""
    try:
        percent = float(coverage_data["totals"]["percent_covered"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("coverage report is invalid") from error
    payload = {
        "percent": percent, "fail_under": fail_under, "passed": percent >= fail_under,
        "files": sorted(coverage_data.get("files", {})),
        "scope_files": scope.get("files", []), "scope_hashes": scope.get("hashes", {}),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    import json

    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if percent < fail_under:
        raise ValueError(f"coverage {percent} is below {fail_under}")
    return percent


def write_mutation_report(scope: dict, results_text: str, output: Path, min_exclusive: float, command: list[str]) -> dict:
    """Score classified mutants; unknown status and zero denominator fail closed."""
    import json
    from collections import Counter

    statuses = {"killed", "survived", "timeout", "suspicious", "untested"}
    values = [
        "untested" if value == "no tests" else value
        for value in (line.strip().rsplit(": ", 1)[-1].lower() for line in results_text.splitlines() if line.strip())
    ]
    unknown = [value for value in values if value not in statuses]
    if unknown:
        raise ValueError(f"unknown/unclassified statuses: {', '.join(sorted(set(unknown)))}")
    counts = Counter(values)
    denominator = sum(counts[status] for status in statuses)
    if denominator == 0:
        raise ValueError("mutation result has no classified denominator")
    score = counts["killed"] / denominator
    payload = {
        "counts": {status: counts[status] for status in sorted(statuses)},
        "denominator": denominator, "score": score, "min_exclusive": min_exclusive,
        "passed": score > min_exclusive, "command": command,
        "scope_files": scope.get("files", []), "scope_hashes": scope.get("hashes", {}),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not payload["passed"]:
        raise ValueError(f"mutation score {score:.6f} is not strictly greater than {min_exclusive}")
    return payload


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


def _scoped_main(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    """Derive the deterministic scope, then optionally measure coverage and mutation."""
    import json

    if args.base is None or args.head is None or args.config is None:
        parser.error("scope derivation requires --base, --head, and --config")
    try:
        scope = derive_scope(Path("."), args.base, args.head, args.config)
    except ValueError as error:
        parser.error(str(error))
    if args.check_only and args.output is None and not args.run_coverage and not args.run_mutation:
        print("verified production scope: " + ", ".join(scope["files"]))
        return 0
    if args.output is not None:
        if not args.strict:
            parser.error("scope output requires --strict")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(scope, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.run_coverage:
        for name in ("pytest_targets", "coverage_config", "coverage_output", "fail_under"):
            if getattr(args, name) is None:
                parser.error(f"--run-coverage requires --{name.replace('_', '-')}")
        targets = args.pytest_targets.split(",")
        command = [sys.executable, "-m", "coverage", "run", f"--rcfile={args.coverage_config}", "-m", "pytest", *targets, "-q"]
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
        if completed.returncode:
            print(completed.stdout[-2000:], file=sys.stderr)
            parser.error("coverage pytest run failed")
        report = subprocess.run(
            [sys.executable, "-m", "coverage", "json", "-o", str(args.coverage_output)], check=False, capture_output=True, text=True,
        )
        if report.returncode:
            parser.error("coverage JSON export failed")
        try:
            coverage_data = json.loads(Path(args.coverage_output).read_text(encoding="utf-8"))
            write_coverage_report(coverage_data, scope, Path(args.coverage_output), args.fail_under)
        except (OSError, ValueError) as error:
            parser.error(str(error))
        print(json.dumps({"coverage_output": str(args.coverage_output)}, sort_keys=True))
    if args.run_mutation:
        for name in ("mutation_output", "min_exclusive"):
            if getattr(args, name) is None:
                parser.error(f"--run-mutation requires --{name.replace('_', '-')}")
        command = [sys.executable, "-m", "mutmut", "run"]
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
        if completed.returncode:
            print(completed.stdout[-2000:], file=sys.stderr)
            parser.error("mutmut run failed")
        results = subprocess.run(["mutmut", "results"], check=False, capture_output=True, text=True)
        if results.returncode:
            parser.error("mutmut results failed")
        try:
            write_mutation_report(scope, results.stdout, Path(args.mutation_output), args.min_exclusive, command)
        except ValueError as error:
            parser.error(str(error))
        print(json.dumps({"mutation_output": str(args.mutation_output)}, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-ref", required=False, default=None)
    parser.add_argument("--scope", type=Path, required=False, default=None)
    parser.add_argument("--coverage-config", type=Path, required=False, default=None)
    parser.add_argument("--pyproject", type=Path, required=False, default=None)
    parser.add_argument("--base", required=False, default=None)
    parser.add_argument("--head", required=False, default=None)
    parser.add_argument("--config", type=Path, required=False, default=None)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--output", type=Path, required=False, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--run-coverage", action="store_true")
    parser.add_argument("--pytest-targets", required=False, default=None)
    parser.add_argument("--coverage-output", type=Path, required=False, default=None)
    parser.add_argument("--fail-under", type=float, required=False, default=None)
    parser.add_argument("--run-mutation", action="store_true")
    parser.add_argument("--mutation-output", type=Path, required=False, default=None)
    parser.add_argument("--min-exclusive", type=float, required=False, default=None)
    parser.add_argument("--fail-on-unknown-status", action="store_true")
    args = parser.parse_args()
    if args.base is not None or args.head is not None or args.config is not None or args.check_only or args.run_coverage or args.run_mutation:
        return _scoped_main(parser, args)
    for name in ("base_ref", "scope", "coverage_config", "pyproject"):
        if getattr(args, name) is None:
            parser.error(f"the following arguments are required: --{name.replace('_', '-')}")
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
