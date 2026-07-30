"""Run the Section 03 dbt graph with config-derived runtime variables."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Sequence

from vina_bim_shop.generators.config import load_generator_config
from vina_bim_shop.generators.drift import resolve_drift_window


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SELECTORS = (
    "+ml_customer_purchase_training",
    "+feature_drift_alerts",
)


def _utc_iso(value: object) -> str:
    timestamp = value
    if getattr(timestamp, "tzinfo", None) is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    return timestamp.isoformat().replace("+00:00", "Z")


def _resolve_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def build_section03_vars(config_path: str | Path, scale: str) -> dict[str, object]:
    """Derive dbt variables from the validated generator configuration."""

    config = load_generator_config(_resolve_path(config_path), scale=scale)
    window = resolve_drift_window(config)
    return {
        "drift_start_ts": _utc_iso(window.drift_start_ts),
        "feature_cutoff_ts": _utc_iso(window.feature_cutoff_ts),
        "label_end_ts": _utc_iso(window.label_end_ts),
        "baseline_date": window.baseline_date.isoformat(),
        "psi_warning": config.drift.psi_warning,
        "psi_alert": config.drift.psi_alert,
        "psi_epsilon": 1e-6,
        "psi_quantile_bins": 10,
    }


def build_dbt_command(
    *,
    dbt_executable: str,
    project_dir: str,
    profiles_dir: str,
    variables: dict[str, object],
    selectors: Sequence[str],
) -> list[str]:
    """Build the shell-free dbt argument array."""

    return [
        dbt_executable,
        "build",
        "--project-dir",
        project_dir,
        "--profiles-dir",
        profiles_dir,
        "--vars",
        json.dumps(variables, sort_keys=True, separators=(",", ":")),
        "--select",
        *selectors,
    ]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build leakage-safe Section 03 dbt Gold contracts."
    )
    parser.add_argument(
        "--config",
        default="configs/generator/base.yaml",
        help="Validated generator YAML.",
    )
    parser.add_argument(
        "--scale",
        required=True,
        choices=("smoke", "medium", "coursework"),
    )
    parser.add_argument(
        "--project-dir",
        default="infra/analytics/dbt",
    )
    parser.add_argument(
        "--profiles-dir",
        default="infra/analytics/dbt",
    )
    parser.add_argument(
        "--select",
        nargs="+",
        default=list(DEFAULT_SELECTORS),
    )
    args = parser.parse_args(argv)
    if tuple(args.select) != DEFAULT_SELECTORS:
        parser.error(
            "--select must be the parent-inclusive Section 03 graph: "
            + " ".join(DEFAULT_SELECTORS)
        )
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    project_path = _resolve_path(args.project_dir)
    profiles_path = _resolve_path(args.profiles_dir)
    try:
        if not (project_path / "dbt_project.yml").is_file():
            raise ValueError(f"invalid dbt project directory: {args.project_dir}")
        if not (profiles_path / "profiles.yml").is_file():
            raise ValueError(f"invalid dbt profiles directory: {args.profiles_dir}")
        variables = build_section03_vars(args.config, args.scale)
    except (OSError, ValueError) as exc:
        print(f"section03 dbt: {exc}", file=sys.stderr)
        return 2

    dbt_executable = shutil.which("dbt")
    if dbt_executable is None:
        print("section03 dbt: dbt executable not found", file=sys.stderr)
        return 127

    print(f"config={args.config}")
    print(f"scale={args.scale}")
    print(f"drift_start_ts={variables['drift_start_ts']}")
    print(f"feature_cutoff_ts={variables['feature_cutoff_ts']}")
    print(f"label_end_ts={variables['label_end_ts']}")
    print(f"baseline_date={variables['baseline_date']}")
    command = build_dbt_command(
        dbt_executable=dbt_executable,
        project_dir=args.project_dir,
        profiles_dir=args.profiles_dir,
        variables=variables,
        selectors=args.select,
    )
    completed = subprocess.run(command, check=False, cwd=PROJECT_ROOT)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
