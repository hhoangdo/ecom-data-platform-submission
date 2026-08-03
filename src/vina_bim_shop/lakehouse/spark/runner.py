"""Run the canonical Spark batch pipeline and collect its evidence summary."""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from vina_bim_shop.generators.config import load_generator_config
from vina_bim_shop.generators.drift import resolve_drift_window
from vina_bim_shop.lakehouse.spark.evidence import capture_evidence
from vina_bim_shop.lakehouse.spark.executive_mart import export_executive_mart
from vina_bim_shop.lakehouse.spark.parity import run_parity_checks
from vina_bim_shop.lakehouse.spark.sql import Section03SqlParameters
from vina_bim_shop.lakehouse.spark.trino import run_gold_smoke_queries
from vina_bim_shop.lakehouse.spark.window import BatchWindow


RunCommand = Callable[[list[str]], subprocess.CompletedProcess[str]]
CaptureEvidence = Callable[..., dict[str, Any]]


def _run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, text=True, capture_output=True, encoding="utf-8", errors="replace")


def _container_workspace_path(path: str | Path) -> str:
    value = Path(path).as_posix()
    return value if Path(path).is_absolute() else f"/workspace/{value}"


def _section03_runtime_context(
    *,
    generator_config: str | Path,
    generator_scale: str,
) -> tuple[BatchWindow, Section03SqlParameters]:
    config = load_generator_config(generator_config, scale=generator_scale)
    drift_window = resolve_drift_window(config)
    parameters = Section03SqlParameters(
        drift_start_ts=drift_window.drift_start_ts.isoformat() + "Z",
        feature_cutoff_ts=drift_window.feature_cutoff_ts.isoformat() + "Z",
        label_end_ts=drift_window.label_end_ts.isoformat() + "Z",
        baseline_date=drift_window.baseline_date.isoformat(),
        psi_warning=config.drift.psi_warning,
        psi_alert=config.drift.psi_alert,
    )
    window = BatchWindow.from_args(
        start_ts=drift_window.start_ts.isoformat() + "Z",
        end_ts=drift_window.end_ts.isoformat() + "Z",
        mode="backfill",
    )
    return window, parameters


def build_spark_submit_command(
    window: BatchWindow,
    *,
    evidence_root: str | Path,
    stage: str = "full",
    generator_config: str | Path = "configs/generator/base.yaml",
    generator_scale: str = "medium",
    section03_manifest: str | Path | None = None,
) -> list[str]:
    args = (
        " --evidence-root "
        + _container_workspace_path(evidence_root)
        + f" --stage {stage}"
        + f" --generator-config {_container_workspace_path(generator_config)}"
        + f" --generator-scale {generator_scale}"
    )
    if section03_manifest is not None:
        args += f" --section03-manifest {_container_workspace_path(section03_manifest)}"
    return [
        "docker",
        "compose",
        "exec",
        "-T",
        "spark-master",
        "bash",
        "-lc",
        "cd /workspace && "
        "PYTHONPATH=/workspace/src spark-submit "
        "--master spark://spark-master:7077 "
        "--deploy-mode client "
        "--conf spark.eventLog.enabled=true "
        "--conf spark.eventLog.dir=s3a://checkpoints/spark-events "
        "scripts/spark/job.py "
        + " ".join(window.to_cli_args())
        + args,
    ]


def build_section03_dbt_command(
    *,
    generator_config: str | Path,
    generator_scale: str,
) -> list[str]:
    return [
        sys.executable,
        "scripts/analytics/run_section03_dbt.py",
        "--config",
        str(generator_config),
        "--scale",
        generator_scale,
        "--project-dir",
        "infra/analytics/dbt",
        "--profiles-dir",
        "infra/analytics/dbt",
    ]


def persist_run_summary(*, evidence_root: str | Path, summary: dict[str, Any]) -> Path:
    evidence_path = Path(evidence_root)
    evidence_path.mkdir(parents=True, exist_ok=True)
    destination = evidence_path / "run_batch_summary.json"
    destination.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return destination


def run_batch_pipeline(
    *,
    start_ts: str,
    end_ts: str,
    mode: str,
    evidence_root: str | Path = "evidence/05_spark_batch",
    generator_config: str | Path = "configs/generator/base.yaml",
    generator_scale: str = "medium",
    section03_manifest: str | Path | None = None,
    run_command: RunCommand = _run_command,
    capture_evidence_fn: CaptureEvidence = capture_evidence,
) -> dict[str, Any]:
    """Run Spark, dbt, parity, Trino, and export steps for one batch window.

    Returns the persisted run summary; subprocess or downstream validation failures
    propagate so orchestration records the batch as failed.
    """

    derived_window: BatchWindow | None = None
    if section03_manifest is not None:
        derived_window, _parameters = _section03_runtime_context(
            generator_config=generator_config,
            generator_scale=generator_scale,
        )
        supplied_window = BatchWindow.from_args(start_ts=start_ts, end_ts=end_ts, mode=mode)
        if supplied_window.start_ts != derived_window.start_ts:
            raise ValueError("start_ts does not match the config-derived Section 03 window")
        if supplied_window.end_ts != derived_window.end_ts:
            raise ValueError("end_ts does not match the config-derived Section 03 window")
    window = BatchWindow.from_args(start_ts=start_ts, end_ts=end_ts, mode=mode)
    spark_submit = build_spark_submit_command(
        window,
        evidence_root=evidence_root,
        generator_config=generator_config,
        generator_scale=generator_scale,
        section03_manifest=section03_manifest,
    )
    spark_result = run_command(spark_submit)

    dbt_command = build_section03_dbt_command(
        generator_config=generator_config,
        generator_scale=generator_scale,
    )
    dbt_result = run_command(dbt_command)
    if section03_manifest is None:
        parity_report = run_parity_checks(evidence_root=evidence_root)
    else:
        parity_report = run_parity_checks(
            evidence_root=evidence_root,
            section03_manifest=section03_manifest,
            generator_config=generator_config,
            generator_scale=generator_scale,
            dbt_command=dbt_command,
            spark_command=spark_submit,
        )
    trino_smoke = run_gold_smoke_queries(evidence_root=evidence_root)
    executive_mart = export_executive_mart(evidence_root=evidence_root)
    evidence_manifest = capture_evidence_fn(evidence_root=evidence_root)

    summary = {
        "window": {
            "start_ts": window.start_ts.isoformat().replace("+00:00", "Z"),
            "end_ts": window.end_ts.isoformat().replace("+00:00", "Z"),
            "mode": window.mode,
        },
        "spark_submit_command": spark_submit,
        "dbt_build_command": dbt_command,
        "spark_stdout": spark_result.stdout,
        "dbt_stdout": dbt_result.stdout,
        "generator_config": str(generator_config),
        "generator_scale": generator_scale,
        "section03_manifest": str(section03_manifest) if section03_manifest is not None else None,
        "parity_success": parity_report["success"],
        "trino_smoke_queries": list(trino_smoke),
        "executive_mart": {
            "duckdb_path": executive_mart["duckdb_path"],
            "table_count": executive_mart["table_count"],
            "total_row_count": executive_mart["total_row_count"],
        },
        "evidence_artifact_count": len(evidence_manifest["artifacts"]),
    }
    persist_run_summary(evidence_root=evidence_root, summary=summary)
    return summary


def run_spark_stage(
    *,
    stage: str,
    start_ts: str,
    end_ts: str,
    mode: str,
    evidence_root: str | Path,
    generator_config: str | Path = "configs/generator/base.yaml",
    generator_scale: str = "medium",
    section03_manifest: str | Path | None = None,
    run_command: RunCommand = _run_command,
) -> dict[str, Any]:
    window = BatchWindow.from_args(start_ts=start_ts, end_ts=end_ts, mode=mode)
    command = build_spark_submit_command(
        window,
        evidence_root=evidence_root,
        stage=stage,
        generator_config=generator_config,
        generator_scale=generator_scale,
        section03_manifest=section03_manifest,
    )
    result = run_command(command)
    return {
        "stage": stage,
        "window": {
            "start_ts": window.start_ts.isoformat().replace("+00:00", "Z"),
            "end_ts": window.end_ts.isoformat().replace("+00:00", "Z"),
            "mode": window.mode,
        },
        "spark_submit_command": command,
        "spark_stdout": result.stdout,
        "generator_config": str(generator_config),
        "generator_scale": generator_scale,
        "section03_manifest": str(section03_manifest) if section03_manifest is not None else None,
    }


def run_core_transform(**kwargs: Any) -> dict[str, Any]:
    return run_spark_stage(stage="core", **kwargs)


def run_feature_compute(**kwargs: Any) -> dict[str, Any]:
    return run_spark_stage(stage="features", **kwargs)
