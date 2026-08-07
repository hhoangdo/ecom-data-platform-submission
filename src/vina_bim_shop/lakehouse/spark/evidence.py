from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


DEFAULT_EVIDENCE_ROOT = Path("evidence/05_spark_batch")
SECTION03_ARTIFACTS = (
    "spark_master_status.json",
    "spark_history_applications.json",
    "spark_job_manifest.json",
    "spark_table_row_counts.json",
    "pyspark_validation_report.json",
    "dbt_parity_report.json",
    "dbt_parity_report.md",
    "trino_gold_smoke_results.json",
    "executive_mart_export_manifest.json",
    "executive_mart_export_report.md",
    "version_matrix.json",
    "gx/validation_results.json",
    "run_batch_summary.json",
)
SECTION03_CONTEXT_KEYS = {
    "section",
    "run_id",
    "candidate_bundle_id",
    "candidate_manifest_sha256",
    "source_config_sha256",
    "scale",
    "random_seed",
    "feature_cutoff_ts",
    "label_end_ts",
}


def _get_json(url: str) -> Any:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _section03_inventory(evidence_path: Path) -> list[dict[str, Any]]:
    actual: set[str] = set()
    for path in evidence_path.rglob("*"):
        if path.is_symlink():
            raise ValueError("Section 03 Spark evidence must not contain symlinks")
        if path.is_file() and path.name != "run_manifest.json":
            actual.add(path.relative_to(evidence_path).as_posix())
    expected = set(SECTION03_ARTIFACTS)
    optional = "optimization/run_manifest.json"
    if optional in actual:
        expected.add(optional)
    if actual != expected:
        raise ValueError(
            "Section 03 Spark evidence inventory is incomplete or unlisted: "
            f"expected={sorted(expected)!r} actual={sorted(actual)!r}"
        )
    return [
        {
            "path": relative,
            "size_bytes": (evidence_path / relative).stat().st_size,
            "sha256": _sha256(evidence_path / relative),
        }
        for relative in sorted(actual)
    ]


def capture_evidence(
    *,
    evidence_root: str | Path = DEFAULT_EVIDENCE_ROOT,
    master_url: str = "http://localhost:8085",
    history_url: str = "http://localhost:18080",
    get_json: Callable[[str], Any] = _get_json,
    section03_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evidence_path = Path(evidence_root)
    evidence_path.mkdir(parents=True, exist_ok=True)

    master_status = get_json(f"{master_url.rstrip('/')}/json/")
    history_applications = get_json(f"{history_url.rstrip('/')}/api/v1/applications")

    (evidence_path / "spark_master_status.json").write_text(
        json.dumps(master_status, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (evidence_path / "spark_history_applications.json").write_text(
        json.dumps(history_applications, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    version_matrix = {
        "spark_image": "vina-bim-shop/spark:4.0.0-iceberg-1.10.1",
        "spark": "4.0.0",
        "iceberg_runtime": "1.10.1",
        "hadoop_aws": "3.4.1",
        "aws_bundle": "2.24.6",
        "great_expectations": "1.17.2",
    }
    (evidence_path / "version_matrix.json").write_text(
        json.dumps(version_matrix, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    artifacts = [
        "spark_master_status.json",
        "spark_history_applications.json",
        "spark_job_manifest.json",
        "spark_table_row_counts.json",
        "pyspark_validation_report.json",
        "dbt_parity_report.json",
        "dbt_parity_report.md",
        "trino_gold_smoke_results.json",
        "executive_mart_export_manifest.json",
        "executive_mart_export_report.md",
        "version_matrix.json",
        "gx/validation_results.json",
    ]
    if (evidence_path / "optimization" / "run_manifest.json").is_file():
        artifacts.append("optimization/run_manifest.json")

    if section03_context is None:
        manifest = {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "service_urls": {
                "spark_master_ui": master_url,
                "spark_history_server": history_url,
            },
            "artifacts": artifacts,
        }
    else:
        if set(section03_context) != SECTION03_CONTEXT_KEYS:
            raise ValueError("Section 03 Spark runtime context keys are invalid")
        if section03_context["section"] != "03_data_generator_improvement":
            raise ValueError("Section 03 Spark runtime section is invalid")
        strict_artifacts = _section03_inventory(evidence_path)
        manifest = {
            **section03_context,
            "status": "success",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "service_urls": {
                "spark_master_ui": master_url,
                "spark_history_server": history_url,
            },
            "conf": dict(section03_context),
            "artifacts": strict_artifacts,
        }
    (evidence_path / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return manifest
