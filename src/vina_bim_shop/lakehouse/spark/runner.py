"""Run the canonical Spark batch pipeline and collect its evidence summary."""

from __future__ import annotations

import json
import hashlib
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from vina_bim_shop.generators.config import load_generator_config
from vina_bim_shop.generators.drift import resolve_drift_window
from vina_bim_shop.lakehouse.spark.evidence import SECTION03_ARTIFACTS, capture_evidence
from vina_bim_shop.lakehouse.spark.executive_mart import export_executive_mart
from vina_bim_shop.lakehouse.spark.parity import run_parity_checks
from vina_bim_shop.lakehouse.spark.sql import Section03SqlParameters
from vina_bim_shop.lakehouse.spark.trino import run_gold_smoke_queries
from vina_bim_shop.lakehouse.spark.window import BatchWindow


RunCommand = Callable[[list[str]], subprocess.CompletedProcess[str]]
CaptureEvidence = Callable[..., dict[str, Any]]


def _run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, check=True, text=True, capture_output=True, encoding="utf-8", errors="replace")
    except subprocess.CalledProcessError as exc:
        if exc.stdout is not None:
            sys.stdout.write(exc.stdout)
        if exc.stderr is not None:
            sys.stderr.write(exc.stderr)
        sys.stdout.flush()
        sys.stderr.flush()
        raise


def _container_workspace_path(path: str | Path) -> str:
    value = Path(path).as_posix()
    return value if Path(path).is_absolute() else f"/workspace/{value}"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _section03_context(*, manifest_path: str | Path, generator_config: str | Path, generator_scale: str) -> dict[str, Any]:
    path = Path(manifest_path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("section") != "03_data_generator_improvement":
        raise ValueError("Section 03 candidate manifest identity is invalid")
    windows = manifest.get("windows")
    if not isinstance(windows, dict):
        raise ValueError("Section 03 candidate windows are missing")
    if manifest.get("scale") != generator_scale:
        raise ValueError("Section 03 candidate scale does not match the runtime")
    return {
        "section": "03_data_generator_improvement",
        "run_id": f"section03-{generator_scale}-seed{manifest['random_seed']}-spark",
        "candidate_bundle_id": manifest["bundle_id"],
        "candidate_manifest_sha256": _sha256(path),
        "source_config_sha256": manifest["source_config_sha256"],
        "scale": manifest["scale"],
        "random_seed": manifest["random_seed"],
        "feature_cutoff_ts": windows["feature_cutoff_ts"],
        "label_end_ts": windows["label_end_ts"],
    }


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
    submit_bin = os.getenv("VBS_SPARK_SUBMIT_BIN")
    if submit_bin:
        deploy_mode = os.getenv("VBS_SPARK_DEPLOY_MODE", "client")
        driver_service_url = os.getenv("VBS_SPARK_DRIVER_SERVICE_URL")
        command = [
            "--master",
            "spark://spark-master:7077",
            "--deploy-mode",
            deploy_mode,
            "--conf",
            "spark.eventLog.enabled=true",
            "--conf",
            "spark.eventLog.compress=true",
            "--conf",
            f"spark.eventLog.dir=s3a://{os.getenv('VBS_CHECKPOINTS_BUCKET', 'checkpoints')}/spark-events",
            "--conf",
            "spark.sql.session.timeZone=UTC",
            "--conf",
            "spark.sql.storeAssignmentPolicy=ANSI",
            "--conf",
            "spark.sql.shuffle.partitions=8",
            "--conf",
            "spark.driver.extraJavaOptions=-Duser.timezone=UTC",
            "--conf",
            "spark.executor.extraJavaOptions=-Duser.timezone=UTC",
            "--conf",
            "spark.executorEnv.PYTHONPATH=/workspace/src",
        ]
        driver_host = os.getenv("VBS_SPARK_DRIVER_HOST")
        if not driver_service_url and deploy_mode == "client" and driver_host:
            command.extend(
                [
                    "--conf",
                    f"spark.driver.host={driver_host}",
                    "--conf",
                    "spark.driver.bindAddress=0.0.0.0",
                ]
            )
        if deploy_mode == "cluster":
            raise ValueError(
                "Spark standalone cluster deploy mode does not support Python applications; "
                "configure VBS_SPARK_DRIVER_SERVICE_URL."
            )
        command.extend(
            [
                "/workspace/scripts/spark/job.py",
                *window.to_cli_args(),
                "--evidence-root",
                _container_workspace_path(evidence_root),
                "--stage",
                stage,
                "--generator-config",
                _container_workspace_path(generator_config),
                "--generator-scale",
                generator_scale,
            ]
        )
        if section03_manifest is not None:
            command.extend(
                [
                    "--section03-manifest",
                    _container_workspace_path(section03_manifest),
                ]
            )
        if driver_service_url:
            if deploy_mode != "client":
                raise ValueError("The Spark driver service requires standalone client deploy mode.")
            return [
                sys.executable,
                "/workspace/scripts/spark/submit_remote.py",
                "--service-url",
                driver_service_url,
                "--timeout-seconds",
                os.getenv("VBS_SPARK_DRIVER_SERVICE_TIMEOUT_SECONDS", "2400"),
                "--",
                *command,
            ]
        return [submit_bin, *command]

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
        "--all-gold",
    ]


def persist_run_summary(*, evidence_root: str | Path, summary: dict[str, Any]) -> Path:
    evidence_path = Path(evidence_root)
    evidence_path.mkdir(parents=True, exist_ok=True)
    destination = evidence_path / "run_batch_summary.json"
    destination.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return destination


def run_batch_pipeline(
    *,
    start_ts: str | None,
    end_ts: str | None,
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
        if mode != derived_window.mode:
            raise ValueError("mode does not match the config-derived Section 03 window")
        if start_ts is not None or end_ts is not None:
            if start_ts is None or end_ts is None:
                raise ValueError("Section 03 start_ts and end_ts must be supplied together")
            supplied_window = BatchWindow.from_args(start_ts=start_ts, end_ts=end_ts, mode=mode)
            if supplied_window.start_ts != derived_window.start_ts:
                raise ValueError("start_ts does not match the config-derived Section 03 window")
            if supplied_window.end_ts != derived_window.end_ts:
                raise ValueError("end_ts does not match the config-derived Section 03 window")
        window = derived_window
    else:
        if start_ts is None or end_ts is None:
            raise ValueError("start_ts and end_ts are required outside Section 03")
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
    }
    if section03_manifest is None:
        evidence_manifest = capture_evidence_fn(evidence_root=evidence_root)
        summary["evidence_artifact_count"] = len(evidence_manifest["artifacts"])
        persist_run_summary(evidence_root=evidence_root, summary=summary)
    else:
        optimization_count = int((Path(evidence_root) / "optimization" / "run_manifest.json").is_file())
        expected_artifact_count = len(SECTION03_ARTIFACTS) + optimization_count
        summary["evidence_artifact_count"] = expected_artifact_count
        persist_run_summary(evidence_root=evidence_root, summary=summary)
        evidence_manifest = capture_evidence_fn(
            evidence_root=evidence_root,
            section03_context=_section03_context(
                manifest_path=section03_manifest,
                generator_config=generator_config,
                generator_scale=generator_scale,
            ),
        )
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
