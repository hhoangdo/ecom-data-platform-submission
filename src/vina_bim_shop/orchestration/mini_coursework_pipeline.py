"""Pure runtime functions for the rubric-facing DP1, DP2, and DP3 DAG.

The Airflow adapter resolves connection metadata and forwards it here.  Keeping
the work in this module makes the six stages directly testable without an
Airflow installation.
"""
from __future__ import annotations

import json
import hashlib
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

import pandas as pd

from vina_bim_shop.lakehouse.bronze import render_batch_snapshot_key, render_event_key
from vina_bim_shop.lakehouse.spark.constants import (
    BRONZE_BATCH_DATASETS,
    BRONZE_EVENT_TOPICS,
    REQUIRED_GOLD_TABLES,
    SILVER_TABLES,
)
from vina_bim_shop.lakehouse.spark.runner import run_core_transform, run_feature_compute
from vina_bim_shop.lakehouse.spark.sql import ordered_core_gold_queries, ordered_feature_queries
from vina_bim_shop.lakehouse.spark.trino import execute_trino_query
from vina_bim_shop.lakehouse.spark.window import BatchWindow
from vina_bim_shop.generators.config import load_generator_config
from vina_bim_shop.generators.drift import resolve_drift_window
from vina_bim_shop.quality.reports import ValidationReport

from .paths import DOCS_ROOT, REPO_ROOT, _slugify_run_id, _utc_now, _write_json
from .quality_helpers import _render_docs, _validate_pandas_dataframe, _window_payload
from .subprocess_helpers import _get_json, _run_command, _working_directory


FEATURE_TABLES = (
    "feat_customer_90d",
    "feat_stream_60m",
    "feat_customer_unified",
    "ml_customer_label",
    "agg_feature_health_daily",
    "feature_drift_alerts",
    "ml_customer_purchase_training",
)
STRICT_SECTION03_CONF_KEYS = frozenset(
    {
        "generator_config_path",
        "generator_scale",
        "section03_candidate_manifest_sha256",
    }
)
SECTION03_CANDIDATE_MANIFEST_PATH = "evidence/03_data_generator_improvement/section03_candidate_manifest.json"
DP3_TABLE_CONTRACTS: dict[str, dict[str, Any]] = {
    "feat_customer_90d": {
        "columns": [
            "customer_id", "event_timestamp", "f_customer_total_orders_90d",
            "f_customer_paid_revenue_90d", "f_customer_avg_order_value_90d",
            "f_customer_distinct_categories_90d", "created",
        ],
        "key": ["customer_id", "event_timestamp"],
        "allow_empty": False,
    },
    "feat_stream_60m": {
        "columns": [
            "customer_id", "event_timestamp", "f_stream_views_60m", "f_stream_add_to_cart_60m",
            "f_stream_checkout_started_60m", "f_stream_order_placed_60m",
            "f_stream_cart_to_purchase_ratio_60m", "created",
        ],
        "key": ["customer_id", "event_timestamp"],
        "allow_empty": False,
    },
    "feat_customer_unified": {
        "columns": [
            "customer_id", "event_timestamp", "f_customer_total_orders_90d",
            "f_customer_paid_revenue_90d", "f_customer_avg_order_value_90d",
            "f_customer_distinct_categories_90d", "f_stream_views_60m",
            "f_stream_add_to_cart_60m", "f_stream_checkout_started_60m",
            "f_stream_order_placed_60m", "f_stream_cart_to_purchase_ratio_60m", "created",
        ],
        "key": ["customer_id", "event_timestamp"],
        "allow_empty": False,
    },
    "ml_customer_label": {
        "columns": ["id", "label"],
        "key": ["id"],
        "allow_empty": False,
    },
    "agg_feature_health_daily": {
        "columns": [
            "monitoring_date", "feature_name", "window_days", "baseline_date", "customer_count",
            "mean_value", "stddev_value", "psi_vs_baseline", "drift_status", "warning_flag", "alert_flag",
        ],
        "key": ["monitoring_date", "feature_name"],
        "allow_empty": False,
    },
    "feature_drift_alerts": {
        "columns": ["alert_date", "feature_name", "psi_value", "threshold", "action"],
        "key": ["alert_date", "feature_name"],
        "allow_empty": True,
    },
    "ml_customer_purchase_training": {
        "columns": [
            "id", "event_timestamp", "label", "f_customer_total_orders_90d",
            "f_customer_paid_revenue_90d", "f_customer_avg_order_value_90d",
            "f_customer_distinct_categories_90d", "f_stream_views_60m",
            "f_stream_add_to_cart_60m", "f_stream_checkout_started_60m",
            "f_stream_order_placed_60m", "f_stream_cart_to_purchase_ratio_60m", "created",
        ],
        "key": ["id"],
        "allow_empty": False,
    },
}
CORE_GOLD_TABLES = tuple(table_name for table_name, _query in ordered_core_gold_queries())
STAGE_FUNCTION_NAMES = (
    "ingest_raw_to_bronze",
    "validate_bronze",
    "transform_bronze_to_silver_gold",
    "validate_silver_gold",
    "compute_offline_features",
    "validate_offline_features",
)
STAGE_DETAILS = {
    "ingest_raw_to_bronze": ("dp1_ingest", "dp1_raw_to_bronze.ingest_raw_to_bronze"),
    "validate_bronze": ("dp1_validate", "dp1_raw_to_bronze.validate_bronze"),
    "transform_bronze_to_silver_gold": (
        "dp2_transform",
        "dp2_bronze_to_silver_gold.transform_bronze_to_silver_gold",
    ),
    "validate_silver_gold": (
        "dp2_validate",
        "dp2_bronze_to_silver_gold.validate_silver_gold",
    ),
    "compute_offline_features": ("dp3_compute", "dp3_offline_features.compute_offline_features"),
    "validate_offline_features": (
        "dp3_validate",
        "dp3_offline_features.validate_offline_features",
    ),
}


@dataclass(frozen=True)
class CourseworkPipelineSettings:
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_region: str
    trino_url: str
    trino_user: str
    kafka_bootstrap_servers: str
    datahub_url: str
    raw_root: str
    bronze_bucket: str
    spark_evidence_root: str
    feature_tables: tuple[str, ...] = FEATURE_TABLES
    generator_config_path: str = "configs/generator/base.yaml"
    generator_scale: str = "medium"
    section03_candidate_manifest_path: str = SECTION03_CANDIDATE_MANIFEST_PATH
    section03_candidate_manifest_sha256: str | None = None
    strict_section03: bool = False

    @classmethod
    def for_tests(cls) -> "CourseworkPipelineSettings":
        return cls(
            minio_endpoint="http://minio:9000",
            minio_access_key="vina_minio",
            minio_secret_key="vina_minio_password",
            minio_region="us-east-1",
            trino_url="http://trino:8080",
            trino_user="vina_analyst",
            kafka_bootstrap_servers="kafka:29092",
            datahub_url="http://datahub-gms:8080",
            raw_root="/workspace/data/raw",
            bronze_bucket="bronze",
            spark_evidence_root="/workspace/evidence/08_airflow_gx/coursework_pipeline",
        )


def _url_from_connection(connection: Any, *, scheme: str) -> str:
    host = getattr(connection, "host", "")
    port = getattr(connection, "port", None)
    if not host:
        raise ValueError("Airflow connection is missing its host.")
    if host.startswith(("http://", "https://")):
        return host.rstrip("/")
    return f"{scheme}://{host}{f':{port}' if port else ''}"


def settings_from_airflow(
    *,
    get_connection: Callable[[str], Any],
    get_variable: Callable[..., Any],
    dag_run_conf: Mapping[str, Any] | None = None,
) -> CourseworkPipelineSettings:
    minio = get_connection("vbs_minio")
    trino = get_connection("vbs_trino")
    kafka = get_connection("vbs_kafka")
    datahub = get_connection("datahub_rest_default")
    strict_section03 = dag_run_conf is not None
    if strict_section03:
        if set(dag_run_conf) != set(STRICT_SECTION03_CONF_KEYS):
            raise ValueError("Section 03 DAG conf must contain exactly the three locked fields.")
        generator_config_path = str(dag_run_conf["generator_config_path"])
        generator_scale = str(dag_run_conf["generator_scale"])
        manifest_sha256 = str(dag_run_conf["section03_candidate_manifest_sha256"])
        if not generator_config_path or not generator_scale or len(manifest_sha256) != 64:
            raise ValueError("Section 03 DAG conf contains an invalid locked field.")
        features = FEATURE_TABLES
    else:
        features = get_variable("vbs_feature_tables", deserialize_json=True)
        generator_config_path = "configs/generator/base.yaml"
        generator_scale = "medium"
        manifest_sha256 = None
    return CourseworkPipelineSettings(
        minio_endpoint=_url_from_connection(minio, scheme="http"),
        minio_access_key=getattr(minio, "login", ""),
        minio_secret_key=getattr(minio, "password", ""),
        minio_region=(getattr(minio, "extra_dejson", {}) or {}).get("region", "us-east-1"),
        trino_url=_url_from_connection(trino, scheme="http"),
        trino_user=getattr(trino, "login", "vina_analyst"),
        kafka_bootstrap_servers=f"{getattr(kafka, 'host', '')}:{getattr(kafka, 'port', 29092)}",
        datahub_url=_url_from_connection(datahub, scheme="http"),
        raw_root=get_variable("vbs_raw_root"),
        bronze_bucket=get_variable("vbs_bronze_bucket"),
        spark_evidence_root=get_variable("vbs_spark_evidence_root"),
        feature_tables=tuple(features),
        generator_config_path=generator_config_path,
        generator_scale=generator_scale,
        section03_candidate_manifest_sha256=manifest_sha256,
        strict_section03=strict_section03,
    )


def settings_from_environment() -> CourseworkPipelineSettings:
    import os

    defaults = CourseworkPipelineSettings.for_tests()
    return CourseworkPipelineSettings(
        minio_endpoint=os.getenv("VBS_MINIO_INTERNAL_ENDPOINT", defaults.minio_endpoint),
        minio_access_key=os.getenv("VBS_MINIO_ROOT_USER", defaults.minio_access_key),
        minio_secret_key=os.getenv("VBS_MINIO_ROOT_PASSWORD", defaults.minio_secret_key),
        minio_region=os.getenv("VBS_MINIO_REGION", defaults.minio_region),
        trino_url=os.getenv("VBS_TRINO_URL", defaults.trino_url),
        trino_user=os.getenv("VBS_TRINO_USER", defaults.trino_user),
        kafka_bootstrap_servers=os.getenv("VBS_KAFKA_BOOTSTRAP_SERVERS", defaults.kafka_bootstrap_servers),
        datahub_url=os.getenv("VBS_DATAHUB_GMS_URL", defaults.datahub_url),
        raw_root=os.getenv("VBS_RAW_ROOT", defaults.raw_root),
        bronze_bucket=os.getenv("VBS_BRONZE_BUCKET", defaults.bronze_bucket),
        spark_evidence_root=os.getenv("VBS_SPARK_EVIDENCE_ROOT", defaults.spark_evidence_root),
        feature_tables=FEATURE_TABLES,
    )


def build_coursework_run_root(*, run_id: str, settings: CourseworkPipelineSettings) -> Path:
    path = Path(settings.spark_evidence_root) / _slugify_run_id(run_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _window(start_ts: str, end_ts: str) -> BatchWindow:
    return BatchWindow.from_args(start_ts=start_ts, end_ts=end_ts, mode="hourly")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_z(value: object) -> str:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    return timestamp.isoformat().replace("+00:00", "Z")


def _section03_context(settings: CourseworkPipelineSettings) -> dict[str, Any] | None:
    if not settings.strict_section03:
        return None

    manifest_path = (REPO_ROOT / settings.section03_candidate_manifest_path).resolve()
    if not manifest_path.is_file():
        raise RuntimeError("Section 03 candidate manifest is missing.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_sha256 = _sha256(manifest_path)
    if manifest_sha256 != settings.section03_candidate_manifest_sha256:
        raise RuntimeError("Section 03 candidate manifest hash mismatch.")

    config_relative = Path(settings.generator_config_path)
    if config_relative.is_absolute() or ".." in config_relative.parts:
        raise RuntimeError("Section 03 generator config path must be repository-relative.")
    config_path = (REPO_ROOT / config_relative).resolve()
    if not config_path.is_file() or _sha256(config_path) != manifest.get("source_config_sha256"):
        raise RuntimeError("Section 03 source config hash mismatch.")
    if manifest.get("source_config_path") != config_relative.as_posix():
        raise RuntimeError("Section 03 source config path mismatch.")
    if manifest.get("scale") != settings.generator_scale:
        raise RuntimeError("Section 03 generator scale mismatch.")

    config = load_generator_config(config_path, scale=settings.generator_scale)
    drift_window = resolve_drift_window(config)
    parameters = {
        "drift_start_ts": _utc_z(drift_window.drift_start_ts),
        "feature_cutoff_ts": _utc_z(drift_window.feature_cutoff_ts),
        "label_end_ts": _utc_z(drift_window.label_end_ts),
        "baseline_date": drift_window.baseline_date.isoformat(),
    }
    manifest_windows = manifest.get("windows") or {}
    expected_windows = {
        "start_ts": _utc_z(drift_window.start_ts),
        "end_ts": _utc_z(drift_window.end_ts),
        **parameters,
    }
    if any(manifest_windows.get(key) != value for key, value in expected_windows.items()):
        raise RuntimeError("Section 03 candidate/config window mismatch.")

    return {
        "manifest": manifest,
        "manifest_sha256": manifest_sha256,
        "config_sha256": _sha256(config_path),
        "parameters": parameters,
        "window": BatchWindow.from_args(
            start_ts=expected_windows["start_ts"],
            end_ts=expected_windows["end_ts"],
            mode="backfill",
        ),
    }


def _load_section03_compute_metadata(
    *, run_root: Path, settings: CourseworkPipelineSettings, strict_context: dict[str, Any]
) -> dict[str, Any]:
    compute_path = run_root / "dp3_compute.json"
    if not compute_path.is_file():
        raise RuntimeError("Section 03 DP3 compute artifact is missing.")
    try:
        compute = json.loads(compute_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Section 03 DP3 compute artifact is unreadable: {exc}") from exc

    expected_parameters = strict_context["parameters"]
    if (
        compute.get("state") != "success"
        or compute.get("strict_section03") is not True
        or compute.get("generator_config_path") != settings.generator_config_path
        or compute.get("generator_config_sha256") != strict_context["config_sha256"]
        or compute.get("generator_scale") != settings.generator_scale
        or compute.get("section03_candidate_manifest_sha256") != strict_context["manifest_sha256"]
        or compute.get("feature_tables") != list(FEATURE_TABLES)
    ):
        raise RuntimeError("Section 03 DP3 compute metadata does not match the strict candidate.")
    if (
        compute.get("feature_cutoff_ts") != expected_parameters["feature_cutoff_ts"]
        or compute.get("section03_parameters") != expected_parameters
    ):
        raise RuntimeError("Section 03 DP3 compute metadata has a stale feature cutoff or parameters.")
    return compute


def _dp3_metric_query(table_name: str, cutoff_ts: str, baseline_date: str) -> tuple[list[str], str]:
    cutoff = f"from_iso8601_timestamp('{cutoff_ts}')"
    if table_name in {"feat_customer_90d", "feat_stream_60m", "feat_customer_unified"}:
        return (
            [
                "row_count", "unique_key_count", "missing_required_count",
                "created_after_event_count", "event_timestamp_min", "event_timestamp_max",
                "created_min", "created_max",
            ],
            f"""
            select count(*) as row_count,
                   count(distinct row(customer_id, event_timestamp)) as unique_key_count,
                   coalesce(sum(case when customer_id is null or event_timestamp is null or created is null then 1 else 0 end), 0) as missing_required_count,
                   coalesce(sum(case when created > event_timestamp then 1 else 0 end), 0) as created_after_event_count,
                   min(event_timestamp) as event_timestamp_min,
                   max(event_timestamp) as event_timestamp_max,
                   min(created) as created_min,
                   max(created) as created_max
            from iceberg.gold.{table_name}
            """,
        )
    if table_name == "ml_customer_label":
        return (
            [
                "row_count", "unique_key_count", "null_id_count", "nonbinary_label_count",
                "label_min", "label_max",
            ],
            """
            select count(*) as row_count,
                   count(distinct id) as unique_key_count,
                   coalesce(sum(case when id is null then 1 else 0 end), 0) as null_id_count,
                   coalesce(sum(case when label is null or label not in (0, 1) then 1 else 0 end), 0) as nonbinary_label_count,
                   min(label) as label_min,
                   max(label) as label_max
            from iceberg.gold.ml_customer_label
            """,
        )
    if table_name == "agg_feature_health_daily":
        return (
            [
                "row_count", "unique_key_count", "key_null_count", "feature_name_violation_count", "window_days_violation_count",
                "baseline_date_violation_count", "psi_nonfinite_count", "psi_negative_count", "psi_min",
            ],
            f"""
            select count(*) as row_count,
                   count(distinct row(monitoring_date, feature_name)) as unique_key_count,
                   coalesce(sum(case when monitoring_date is null or feature_name is null then 1 else 0 end), 0) as key_null_count,
                   coalesce(sum(case when feature_name is null or feature_name <> 'f_customer_order_frequency_7d' then 1 else 0 end), 0) as feature_name_violation_count,
                   coalesce(sum(case when window_days is null or window_days <> 7 then 1 else 0 end), 0) as window_days_violation_count,
                   coalesce(sum(case when baseline_date is null or cast(baseline_date as varchar) <> '{baseline_date}' then 1 else 0 end), 0) as baseline_date_violation_count,
                   coalesce(sum(case when psi_vs_baseline is null or not is_finite(psi_vs_baseline) then 1 else 0 end), 0) as psi_nonfinite_count,
                   coalesce(sum(case when psi_vs_baseline < 0 then 1 else 0 end), 0) as psi_negative_count,
                   min(psi_vs_baseline) as psi_min
            from iceberg.gold.agg_feature_health_daily
            """,
        )
    if table_name == "feature_drift_alerts":
        return (
            [
                "row_count", "unique_key_count", "key_null_count", "psi_nonfinite_count",
                "psi_below_threshold_count", "threshold_violation_count", "psi_min",
            ],
            """
            select count(*) as row_count,
                   count(distinct row(alert_date, feature_name)) as unique_key_count,
                   coalesce(sum(case when alert_date is null or feature_name is null then 1 else 0 end), 0) as key_null_count,
                   coalesce(sum(case when psi_value is null or not is_finite(psi_value) then 1 else 0 end), 0) as psi_nonfinite_count,
                   coalesce(sum(case when psi_value < 0.15 then 1 else 0 end), 0) as psi_below_threshold_count,
                   coalesce(sum(case when threshold is null or threshold <> 0.15 then 1 else 0 end), 0) as threshold_violation_count,
                   min(psi_value) as psi_min
            from iceberg.gold.feature_drift_alerts
            """,
        )
    if table_name == "ml_customer_purchase_training":
        return (
            [
                "row_count", "unique_key_count", "null_id_count", "event_cutoff_violation_count",
                "created_cutoff_violation_count", "created_after_event_count", "label_mismatch_count",
                "event_timestamp_min", "event_timestamp_max", "created_min", "created_max",
            ],
            f"""
            select count(*) as row_count,
                   count(distinct t.id) as unique_key_count,
                   coalesce(sum(case when t.id is null then 1 else 0 end), 0) as null_id_count,
                   coalesce(sum(case when t.event_timestamp is null or t.event_timestamp <> {cutoff} then 1 else 0 end), 0) as event_cutoff_violation_count,
                   coalesce(sum(case when t.created is null or t.created <> {cutoff} then 1 else 0 end), 0) as created_cutoff_violation_count,
                   coalesce(sum(case when t.created is null or t.event_timestamp is null or t.created > t.event_timestamp then 1 else 0 end), 0) as created_after_event_count,
                   coalesce(sum(case when l.id is null or t.label is null or t.label <> l.label or l.label is null then 1 else 0 end), 0) as label_mismatch_count,
                   min(t.event_timestamp) as event_timestamp_min,
                   max(t.event_timestamp) as event_timestamp_max,
                   min(t.created) as created_min,
                   max(t.created) as created_max
            from iceberg.gold.ml_customer_purchase_training t
            left join iceberg.gold.ml_customer_label l on t.id = l.id
            """,
        )
    raise KeyError(table_name)


def _dp3_table_facts(
    *, table_name: str, columns: list[str], settings: CourseworkPipelineSettings,
    cutoff_ts: str, baseline_date: str,
) -> dict[str, Any]:
    contract = DP3_TABLE_CONTRACTS[table_name]
    metric_names, query = _dp3_metric_query(table_name, cutoff_ts, baseline_date)
    values = execute_trino_query(query, trino_url=settings.trino_url, user=settings.trino_user)["rows"]
    raw_values = list(values[0]) if values else []
    metrics = dict(zip(metric_names, raw_values, strict=False))
    row_count = int(metrics.get("row_count") or 0)
    unique_key_count = int(metrics.get("unique_key_count") or 0)
    numeric_violations = [
        int(value or 0)
        for key, value in metrics.items()
        if key.endswith("_count") and key not in {"row_count", "unique_key_count"}
    ]
    schema_ok = columns == contract["columns"]
    count_ok = contract["allow_empty"] or row_count >= 1
    unique_ok = row_count == unique_key_count
    contract_success = schema_ok and count_ok and unique_ok and not any(numeric_violations)
    return {
        "table_name": table_name,
        "columns": columns,
        "key": list(contract["key"]),
        "row_count": row_count,
        "unique_key_count": unique_key_count,
        "contract_success": contract_success,
        "metrics": metrics,
    }


def _stage_payload(
    *,
    function_name: str,
    run_id: str,
    window: BatchWindow,
    payload: dict[str, Any],
) -> dict[str, Any]:
    artifact_name, task_id = STAGE_DETAILS[function_name]
    return {
        "schema_version": 1,
        "dag_id": "mini_coursework_pipeline",
        "run_id": run_id,
        "task_id": task_id,
        "stage": artifact_name,
        "window": _window_payload(window),
        "artifact": f"{artifact_name}.json",
        **payload,
    }


def _write_stage(
    *,
    function_name: str,
    run_id: str,
    window: BatchWindow,
    run_root: Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    result = _stage_payload(function_name=function_name, run_id=run_id, window=window, payload=payload)
    _write_json(run_root / result["artifact"], result)

    existing_path = run_root / "run_manifest.json"
    existing = json.loads(existing_path.read_text(encoding="utf-8")) if existing_path.is_file() else {}
    stages = {entry["task_id"]: entry for entry in existing.get("stages", [])}
    stages[result["task_id"]] = {
        "task_id": result["task_id"],
        "state": result.get("state", "success"),
        "artifact": result["artifact"],
    }
    manifest = {
        "schema_version": 1,
        "dag_id": "mini_coursework_pipeline",
        "run_id": run_id,
        "window": _window_payload(window),
        "stages": [
            stages[STAGE_DETAILS[name][1]]
            for name in STAGE_FUNCTION_NAMES
            if STAGE_DETAILS[name][1] in stages
        ],
        "updated_at": _utc_now(),
    }
    _write_json(existing_path, manifest)
    return result


def _raw_files(settings: CourseworkPipelineSettings) -> list[tuple[Path, str]]:
    raw_root = Path(settings.raw_root)
    files: list[tuple[Path, str]] = []
    for dataset in BRONZE_BATCH_DATASETS:
        files.extend((path, dataset) for path in sorted((raw_root / dataset).glob("*.parquet")))
    return files


def _event_files(settings: CourseworkPipelineSettings) -> list[tuple[Path, str]]:
    raw_root = Path(settings.raw_root) / "kafka_topics"
    return [
        (raw_root / topic / "events.jsonl", topic)
        for topic in (*BRONZE_EVENT_TOPICS, "dead_letter_events")
        if (raw_root / topic / "events.jsonl").is_file()
    ]


def _copy_to_bronze(
    *, source: Path, object_key: str, settings: CourseworkPipelineSettings
) -> None:
    """Upload a deterministic bronze object from the Airflow worker."""
    alias = "coursework"
    _run_command(
        [
            "mc",
            "alias",
            "set",
            alias,
            settings.minio_endpoint,
            settings.minio_access_key,
            settings.minio_secret_key,
        ]
    )
    _run_command(["mc", "cp", str(source), f"{alias}/{object_key}"])


def ingest_raw_to_bronze(
    *, run_id: str, start_ts: str, end_ts: str, settings: CourseworkPipelineSettings, run_root: Path
) -> dict[str, Any]:
    window = _window(start_ts, end_ts)
    date = window.start_ts.date().isoformat()
    batch_objects: list[str] = []
    for source, dataset in _raw_files(settings):
        key = render_batch_snapshot_key(dataset, date, source.name)
        _copy_to_bronze(source=source, object_key=key, settings=settings)
        batch_objects.append(key)
    event_objects: list[str] = []
    for source, topic in _event_files(settings):
        key = render_event_key(topic, date, source.name)
        _copy_to_bronze(source=source, object_key=key, settings=settings)
        event_objects.append(key)
    return _write_stage(
        function_name="ingest_raw_to_bronze",
        run_id=run_id,
        window=window,
        run_root=run_root,
        payload={
            "state": "success",
            "raw_batch_file_count": len(batch_objects),
            "raw_event_file_count": len(event_objects),
            "bronze_batch_objects": batch_objects,
            "bronze_event_objects": event_objects,
        },
    )


def _quality_dir(run_root: Path) -> Path:
    path = run_root / "quality"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _render_run_docs(quality_root: Path) -> None:
    reports = [
        ValidationReport(**json.loads(path.read_text(encoding="utf-8")))
        for path in sorted(quality_root.glob("*.json"))
    ]
    if reports:
        _render_docs(reports)


def validate_bronze(
    *, run_id: str, start_ts: str, end_ts: str, settings: CourseworkPipelineSettings, run_root: Path
) -> dict[str, Any]:
    window = _window(start_ts, end_ts)
    ingest = json.loads((run_root / "dp1_ingest.json").read_text(encoding="utf-8"))
    records = [
        {"path": path}
        for path in [*ingest["bronze_batch_objects"], *ingest["bronze_event_objects"]]
    ]
    report = _validate_pandas_dataframe(
        dataframe=pd.DataFrame(records or [{"path": None}]),
        datasource_name="coursework_bronze",
        asset_name="coursework_bronze_asset",
        suite_name="coursework_bronze_contract",
        layer="bronze_raw",
        expectations=[
            __import__("great_expectations").expectations.ExpectColumnValuesToNotBeNull(column="path"),
            __import__("great_expectations").expectations.ExpectTableRowCountToBeBetween(min_value=1),
        ],
        output_root=_quality_dir(run_root),
        window=_window_payload(window),
    )
    _render_run_docs(_quality_dir(run_root))
    return _write_stage(
        function_name="validate_bronze",
        run_id=run_id,
        window=window,
        run_root=run_root,
        payload={
            "state": "success",
            "gate": report.to_dict(),
            "gx_report": "quality/coursework_bronze_contract.json",
        },
    )


def _prepare_spark_evidence_root(run_root: Path) -> None:
    _run_command(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "--user",
            "root",
            "spark-master",
            "bash",
            "-lc",
            f"mkdir -p {shlex.quote(run_root.as_posix())} && chmod -R 0777 {shlex.quote(run_root.as_posix())}",
        ],
    )


def _latest_spark_application_id() -> str | None:
    applications = _get_json("http://spark-history-server:18080/api/v1/applications")
    if not isinstance(applications, list) or not applications:
        return None
    return str(applications[0].get("id")) if applications[0].get("id") else None


def transform_bronze_to_silver_gold(
    *, run_id: str, start_ts: str, end_ts: str, settings: CourseworkPipelineSettings, run_root: Path
) -> dict[str, Any]:
    window = _window(start_ts, end_ts)
    spark_root = run_root / "spark_core"
    _prepare_spark_evidence_root(spark_root)
    with _working_directory(REPO_ROOT):
        summary = run_core_transform(
            start_ts=start_ts,
            end_ts=end_ts,
            mode="hourly",
            evidence_root=spark_root,
        )
    return _write_stage(
        function_name="transform_bronze_to_silver_gold",
        run_id=run_id,
        window=window,
        run_root=run_root,
        payload={
            "state": "success",
            "spark_application_id": _latest_spark_application_id(),
            "core_gold_tables": list(CORE_GOLD_TABLES),
            "spark_summary": summary,
        },
    )


def _trino_count(table_name: str, settings: CourseworkPipelineSettings) -> int:
    return int(
        execute_trino_query(
            f"select count(*) from iceberg.gold.{table_name}",
            trino_url=settings.trino_url,
            user=settings.trino_user,
        )["rows"][0][0]
    )


def validate_silver_gold(
    *, run_id: str, start_ts: str, end_ts: str, settings: CourseworkPipelineSettings, run_root: Path
) -> dict[str, Any]:
    window = _window(start_ts, end_ts)
    gold_inventory = execute_trino_query(
        "show tables from iceberg.gold", trino_url=settings.trino_url, user=settings.trino_user
    )["rows"]
    observed = {row[0] for row in gold_inventory}
    gold_counts = {table_name: _trino_count(table_name, settings) for table_name in CORE_GOLD_TABLES}
    silver_inventory = execute_trino_query(
        "show tables from iceberg.silver", trino_url=settings.trino_url, user=settings.trino_user
    )["rows"]
    report = _validate_pandas_dataframe(
        dataframe=pd.DataFrame(
            [
                {
                    "core_gold_table_count": len(set(CORE_GOLD_TABLES) & observed),
                    "fact_order_rows": gold_counts.get("fact_order", 0),
                }
            ]
        ),
        datasource_name="coursework_core_gold",
        asset_name="coursework_core_gold_asset",
        suite_name="coursework_core_gold_contract",
        layer="gold_trino",
        expectations=[
            __import__("great_expectations").expectations.ExpectColumnValuesToBeBetween(
                column="core_gold_table_count", min_value=len(CORE_GOLD_TABLES)
            ),
            __import__("great_expectations").expectations.ExpectColumnValuesToBeBetween(
                column="fact_order_rows", min_value=1
            ),
        ],
        output_root=_quality_dir(run_root),
        window=_window_payload(window),
    )
    _render_run_docs(_quality_dir(run_root))
    result = _write_stage(
        function_name="validate_silver_gold",
        run_id=run_id,
        window=window,
        run_root=run_root,
        payload={
            "state": "success" if report.success else "failed",
            "silver_table_count": len(silver_inventory),
            "gold_row_counts": gold_counts,
            "gate": report.to_dict(),
            "gx_report": "quality/coursework_core_gold_contract.json",
        },
    )
    if report.blocks_dag and not report.success:
        raise RuntimeError("Core Silver/Gold validation failed.")
    return result


def compute_offline_features(
    *, run_id: str, start_ts: str, end_ts: str, settings: CourseworkPipelineSettings, run_root: Path
) -> dict[str, Any]:
    strict_context = _section03_context(settings)
    window = strict_context["window"] if strict_context else _window(start_ts, end_ts)
    spark_root = run_root / "spark_features"
    _prepare_spark_evidence_root(spark_root)
    spark_kwargs: dict[str, Any] = {
        "start_ts": window.start_ts.isoformat(),
        "end_ts": window.end_ts.isoformat(),
        "mode": "backfill" if strict_context else "hourly",
        "evidence_root": spark_root,
    }
    if strict_context:
        spark_kwargs.update(
            {
                "generator_config": settings.generator_config_path,
                "generator_scale": settings.generator_scale,
                "section03_manifest": settings.section03_candidate_manifest_path,
            }
        )
    with _working_directory(REPO_ROOT):
        summary = run_feature_compute(**spark_kwargs)
    columns = {
        table_name: [
            row[0]
            for row in execute_trino_query(
                f"describe iceberg.gold.{table_name}",
                trino_url=settings.trino_url,
                user=settings.trino_user,
            )["rows"]
        ]
        for table_name in settings.feature_tables
    }
    return _write_stage(
        function_name="compute_offline_features",
        run_id=run_id,
        window=window,
        run_root=run_root,
        payload={
            "state": "success",
            "spark_application_id": _latest_spark_application_id(),
            "feature_tables": list(settings.feature_tables),
            "feature_columns": columns,
            "spark_summary": summary,
            **(
                {
                    "strict_section03": True,
                    "generator_config_path": settings.generator_config_path,
                    "generator_scale": settings.generator_scale,
                    "section03_candidate_manifest_path": settings.section03_candidate_manifest_path,
                    "section03_candidate_manifest_sha256": strict_context["manifest_sha256"],
                    "generator_config_sha256": strict_context["config_sha256"],
                    "feature_cutoff_ts": strict_context["parameters"]["feature_cutoff_ts"],
                    "section03_parameters": strict_context["parameters"],
                }
                if strict_context
                else {}
            ),
        },
    )


def validate_offline_features(
    *, run_id: str, start_ts: str, end_ts: str, settings: CourseworkPipelineSettings, run_root: Path
) -> dict[str, Any]:
    strict_context = _section03_context(settings)
    window = strict_context["window"] if strict_context else _window(start_ts, end_ts)
    compute_metadata = (
        _load_section03_compute_metadata(run_root=run_root, settings=settings, strict_context=strict_context)
        if strict_context
        else None
    )
    cutoff_ts = (
        compute_metadata["feature_cutoff_ts"]
        if strict_context
        else "9999-12-31T23:59:59Z"
    )
    baseline_date = (
        compute_metadata["section03_parameters"]["baseline_date"]
        if strict_context
        else "1970-01-01"
    )
    rows: list[dict[str, Any]] = []
    for table_name in settings.feature_tables:
        columns = [
            row[0]
            for row in execute_trino_query(
                f"describe iceberg.gold.{table_name}",
                trino_url=settings.trino_url,
                user=settings.trino_user,
            )["rows"]
        ]
        rows.append(
            _dp3_table_facts(
                table_name=table_name,
                columns=columns,
                settings=settings,
                cutoff_ts=cutoff_ts,
                baseline_date=baseline_date,
            )
        )
    report_rows = [
        {
            "table_name": row["table_name"],
            "row_count": row["row_count"],
            "unique_key_count": row["unique_key_count"],
            "contract_success": row["contract_success"],
        }
        for row in rows
    ]
    report = _validate_pandas_dataframe(
        dataframe=pd.DataFrame(report_rows),
        datasource_name="coursework_features",
        asset_name="coursework_features_asset",
        suite_name="coursework_feature_contract",
        layer="gold_trino",
        expectations=[
            __import__("great_expectations").expectations.ExpectColumnValuesToBeInSet(
                column="contract_success", value_set=[True]
            ),
        ],
        output_root=_quality_dir(run_root),
        window=_window_payload(window),
    )
    _render_run_docs(_quality_dir(run_root))
    result = _write_stage(
        function_name="validate_offline_features",
        run_id=run_id,
        window=window,
        run_root=run_root,
        payload={
            "state": "success" if report.success and all(row["contract_success"] for row in rows) else "failed",
            "contract_success": report.success and all(row["contract_success"] for row in rows),
            "feature_results": rows,
            "gate": report.to_dict(),
            "gx_report": "quality/coursework_feature_contract.json",
            **(
                {
                    "strict_section03": True,
                    "generator_config_path": settings.generator_config_path,
                    "generator_scale": settings.generator_scale,
                    "section03_candidate_manifest_sha256": strict_context["manifest_sha256"],
                    "generator_config_sha256": strict_context["config_sha256"],
                    "feature_cutoff_ts": strict_context["parameters"]["feature_cutoff_ts"],
                }
                if strict_context
                else {}
            ),
        },
    )
    if report.blocks_dag and (not report.success or not all(row["contract_success"] for row in rows)):
        raise RuntimeError("Offline feature validation failed.")
    return result
