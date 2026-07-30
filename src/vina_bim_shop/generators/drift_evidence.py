from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_EVEN
import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import TYPE_CHECKING, Any
import uuid

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import yaml

from vina_bim_shop.generators.config import DriftConfig, GeneratorConfig
from vina_bim_shop.generators.drift import (
    DriftWindow,
    calculate_psi,
    resolve_drift_window,
    summarize_drift_rates,
)
from vina_bim_shop.generators.labels import (
    build_feature_label_join,
    build_point_in_time_customer_features,
    build_purchase_labels,
    normalize_commerce_events_for_features,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


HEALTH_COLUMNS: tuple[str, ...] = (
    "monitoring_date",
    "feature_name",
    "window_days",
    "baseline_date",
    "customer_count",
    "mean_value",
    "stddev_value",
    "psi_vs_baseline",
    "drift_status",
    "warning_flag",
    "alert_flag",
)
ALERT_COLUMNS: tuple[str, ...] = (
    "alert_date",
    "feature_name",
    "psi_value",
    "threshold",
    "action",
)
ARTIFACT_FILENAMES: dict[str, str] = {
    "config_snapshot": "config_snapshot.yaml",
    "labels": "ml_customer_label.csv",
    "feature_health_daily": "agg_feature_health_daily.csv",
    "drift_alerts": "feature_drift_alerts.csv",
    "training_join": "ml_customer_purchase_training.csv",
    "labels_sample": "sample_rows/ml_customer_label.csv",
    "feature_health_sample": "sample_rows/agg_feature_health_daily.csv",
    "drift_alerts_sample": "sample_rows/feature_drift_alerts.csv",
    "training_sample": "sample_rows/ml_customer_purchase_training.csv",
    "evidence_image": "section03_config_and_training_join.png",
    "quality_report": "section03_report.md",
}
CHECK_KEYS: tuple[str, ...] = (
    "configured_counts_preserved",
    "streaming_distribution_inherited",
    "labels_exact_schema",
    "labels_unique",
    "labels_binary",
    "training_join_one_to_one",
    "point_in_time_safe",
    "psi_finite",
    "alert_threshold_respected",
)
REPORT_HEADINGS: tuple[str, ...] = (
    "Run Context",
    "Scenario and Rationale",
    "Fixed Counts",
    "Realized Pre/Post Rates",
    "Point-in-Time and Label Policy",
    "Daily PSI Summary",
    "Alerts",
    "Exact Label Contract",
    "Feast-ready Training Join",
    "Quality Checks",
    "Spark/dbt Parity Runtime",
    "Airflow DP3 Runtime",
    "DataHub Lineage Runtime",
    "Sheet3 E32-E34 Evidence",
    "Reproduction Commands",
    "Limitations",
)


@dataclass(frozen=True)
class DriftEvidenceResult:
    config_snapshot: Path
    labels: Path
    feature_health_daily: Path
    drift_alerts: Path
    training_join: Path
    labels_sample: Path
    feature_health_sample: Path
    drift_alerts_sample: Path
    training_sample: Path
    evidence_image: Path
    report: Path
    manifest: Path


def _round_12(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.000000000001"), rounding=ROUND_HALF_EVEN))


def _utc(value: object) -> pd.Timestamp:
    parsed = pd.Timestamp(value)
    return parsed.tz_localize("UTC") if parsed.tzinfo is None else parsed.tz_convert("UTC")


def build_feature_health_daily(
    customers: pd.DataFrame,
    orders: pd.DataFrame,
    *,
    window: DriftWindow,
    drift: DriftConfig,
) -> pd.DataFrame:
    if "customer_id" not in customers or "created_ts" not in customers:
        raise ValueError("customers must contain customer_id and created_ts")
    if customers["customer_id"].isna().any() or customers["customer_id"].astype("string").duplicated().any():
        raise ValueError("customer_id must be non-null and unique")
    customer_created = pd.to_datetime(customers["created_ts"], errors="coerce", utc=True)
    if customer_created.isna().any():
        raise ValueError("customers.created_ts must contain valid timestamps")
    baseline_end = _utc(window.baseline_date) + pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)
    cohort = (
        customers.loc[customer_created.le(baseline_end), "customer_id"]
        .astype("string")
        .sort_values(kind="stable")
        .reset_index(drop=True)
    )
    if cohort.empty:
        raise ValueError("baseline-known customer cohort must not be empty")
    if orders.empty:
        order_frame = pd.DataFrame(columns=["customer_id", "order_timestamp", "created_ts"])
    else:
        required = {"customer_id", "order_timestamp", "created_ts"}
        if not required.issubset(orders):
            raise ValueError("orders missing required health columns")
        order_frame = orders.copy()
        order_frame["customer_id"] = order_frame["customer_id"].astype("string")
        order_frame["order_timestamp"] = pd.to_datetime(
            order_frame["order_timestamp"], errors="coerce", utc=True
        )
        order_frame["created_ts"] = pd.to_datetime(order_frame["created_ts"], errors="coerce", utc=True)
        if order_frame[["order_timestamp", "created_ts"]].isna().any().any():
            raise ValueError("orders health timestamps must be valid")

    def distribution(monitoring_date: date) -> pd.Series:
        window_start = _utc(monitoring_date) - pd.Timedelta(days=6)
        window_end = _utc(monitoring_date) + pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)
        selected = order_frame.loc[
            order_frame["customer_id"].isin(set(cohort))
            & order_frame["order_timestamp"].between(window_start, window_end, inclusive="both")
            & order_frame["created_ts"].le(window_end)
        ]
        counts = selected.groupby("customer_id").size()
        return cohort.map(counts).fillna(0).astype("float64")

    baseline_distribution = distribution(window.baseline_date)
    end_date = _utc(window.end_ts).floor("D").date()
    rows: list[dict[str, object]] = []
    for monitoring_timestamp in pd.date_range(window.baseline_date, end_date, freq="D"):
        monitoring_date = monitoring_timestamp.date()
        current_distribution = distribution(monitoring_date)
        psi = calculate_psi(baseline_distribution, current_distribution)
        if psi >= drift.psi_alert:
            status = "alert"
        elif psi >= drift.psi_warning:
            status = "warning"
        else:
            status = "stable"
        rows.append(
            {
                "monitoring_date": monitoring_date,
                "feature_name": "f_customer_order_frequency_7d",
                "window_days": np.int32(7),
                "baseline_date": window.baseline_date,
                "customer_count": np.int64(len(cohort)),
                "mean_value": _round_12(float(current_distribution.mean())),
                "stddev_value": _round_12(float(current_distribution.std(ddof=0))),
                "psi_vs_baseline": _round_12(psi),
                "drift_status": status,
                "warning_flag": bool(psi >= drift.psi_warning),
                "alert_flag": bool(psi >= drift.psi_alert),
            }
        )
    return pd.DataFrame(rows, columns=list(HEALTH_COLUMNS))


def build_feature_drift_alerts(
    feature_health: pd.DataFrame,
    *,
    alert_threshold: float,
) -> pd.DataFrame:
    if tuple(feature_health.columns) != HEALTH_COLUMNS:
        raise ValueError("feature_health has an unexpected schema")
    selected = feature_health.loc[feature_health["psi_vs_baseline"].ge(alert_threshold)].copy()
    alerts = pd.DataFrame(
        {
            "alert_date": selected["monitoring_date"],
            "feature_name": selected["feature_name"],
            "psi_value": selected["psi_vs_baseline"].astype("float64"),
            "threshold": float(alert_threshold),
            "action": "Investigate customer_order_frequency drift",
        }
    )
    return alerts.sort_values(["alert_date", "feature_name"], kind="stable").reset_index(drop=True)[
        list(ALERT_COLUMNS)
    ]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iso_utc(value: object) -> str:
    timestamp = _utc(value)
    return timestamp.isoformat().replace("+00:00", "Z")


def _repo_relative(path: Path) -> str:
    repo_root = Path(__file__).resolve().parents[3]
    try:
        return path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _write_csv(path: Path, frame: pd.DataFrame, *, health: bool = False) -> None:
    output = frame.copy()
    for column in output.columns:
        if pd.api.types.is_datetime64_any_dtype(output[column]):
            output[column] = pd.to_datetime(output[column], utc=True).map(_iso_utc)
    for column in ("monitoring_date", "baseline_date", "alert_date"):
        if column in output:
            output[column] = output[column].map(lambda value: value.isoformat())
    path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(
        path,
        index=False,
        encoding="utf-8",
        lineterminator="\n",
        float_format="%.12f" if health else "%.12g",
    )


def _write_image(
    path: Path,
    *,
    config: GeneratorConfig,
    window: DriftWindow,
    training: pd.DataFrame,
) -> None:
    image = Image.new("RGB", (1600, 900), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=20)
    title_font = ImageFont.load_default(size=28)
    draw.rectangle((0, 0, 1600, 70), fill="#17365d")
    draw.text((36, 20), "Section 03 configuration to training join", fill="white", font=title_font)
    draw.text((42, 100), "DRIFT CONFIGURATION", fill="#17365d", font=title_font)
    drift_lines = [
        f"enabled: {config.drift.enabled}",
        f"scenario: {config.drift.scenario}",
        f"mode: {config.drift.mode}",
        f"cutoff_fraction: {config.drift.cutoff_fraction}",
        f"post_rate_multiplier: {config.drift.post_rate_multiplier}",
        f"psi_warning: {config.drift.psi_warning}",
        f"psi_alert: {config.drift.psi_alert}",
        f"label_horizon_days: {config.drift.label_horizon_days}",
        f"drift_start_ts: {_iso_utc(window.drift_start_ts)}",
        f"feature_cutoff_ts: {_iso_utc(window.feature_cutoff_ts)}",
        f"label_end_ts: {_iso_utc(window.label_end_ts)}",
        f"baseline_date: {window.baseline_date.isoformat()}",
    ]
    y = 150
    for line in drift_lines:
        draw.text((42, y), line, fill="#222222", font=font)
        y += 38
    draw.line((750, 95, 750, 780), fill="#9aa9b8", width=2)
    draw.text((790, 100), "TRAINING JOIN (FIRST 10 SYNTHETIC IDS)", fill="#17365d", font=title_font)
    draw.text(
        (790, 145),
        "id | label | event_timestamp | f_customer_total_orders_90d",
        fill="#222222",
        font=font,
    )
    y = 190
    for row in training.head(10).itertuples(index=False):
        draw.text(
            (790, y),
            f"{row.id} | {int(row.label)} | {_iso_utc(row.event_timestamp)} | "
            f"{int(row.f_customer_total_orders_90d)}",
            fill="#222222",
            font=font,
        )
        y += 48
    draw.rectangle((0, 805, 1600, 900), fill="#eef3f8")
    draw.text(
        (42, 825),
        "Sources: config_snapshot.yaml and ml_customer_purchase_training.csv",
        fill="#17365d",
        font=font,
    )
    draw.text(
        (42, 860),
        "Candidate local evidence only; Spark, Airflow, DataHub, GKE, and rubric satisfaction are not proven.",
        fill="#7a1f1f",
        font=font,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=False)


def _write_report(
    path: Path,
    *,
    config: GeneratorConfig,
    window: DriftWindow,
    rate_summary: dict[str, Any],
    health: pd.DataFrame,
    alerts: pd.DataFrame,
    labels: pd.DataFrame,
    training: pd.DataFrame,
    checks: dict[str, bool],
) -> None:
    sections = {
        "Run Context": (
            f"Scale `{config.scale}`, seed `{config.random_seed}`, history `{config.history_days}` days. "
            "This is local candidate evidence."
        ),
        "Scenario and Rationale": (
            "`customer_order_frequency` uses an abrupt configured 1.5x post-cutoff order-rate multiplier."
        ),
        "Fixed Counts": json.dumps(config.entities, sort_keys=True),
        "Realized Pre/Post Rates": json.dumps(rate_summary, sort_keys=True),
        "Point-in-Time and Label Policy": (
            f"Features are cutoff-safe at `{_iso_utc(window.feature_cutoff_ts)}` and labels use the "
            f"exclusive-start/inclusive-end horizon through `{_iso_utc(window.label_end_ts)}`."
        ),
        "Daily PSI Summary": (
            f"{len(health)} complete-day rows; maximum PSI "
            f"`{float(health['psi_vs_baseline'].max()):.12f}` for the fixed baseline-known cohort."
        ),
        "Alerts": f"{len(alerts)} alert rows at the inclusive `{config.drift.psi_alert}` threshold.",
        "Exact Label Contract": f"`id,label`; {len(labels)} unique synthetic customer IDs.",
        "Feast-ready Training Join": (
            f"{len(training)} one-to-one rows with `event_timestamp == created == feature_cutoff_ts`."
        ),
        "Quality Checks": json.dumps(checks, sort_keys=True),
        "Spark/dbt Parity Runtime": "Pending",
        "Airflow DP3 Runtime": "Pending",
        "DataHub Lineage Runtime": "Pending",
        "Sheet3 E32-E34 Evidence": (
            "Candidate artifacts contribute to E32-E34 but earn zero rubric credit until strict runtime finalization."
        ),
        "Reproduction Commands": (
            "`uv run python scripts/generate/run_generator.py --config configs/generator/base.yaml "
            f"--scale {config.scale} --mode full --clean --seed {config.random_seed}`"
        ),
        "Limitations": (
            "Local candidate only. This does not prove Spark/dbt parity, Airflow, DataHub, Feast, GKE, "
            "GCP execution, or final rubric satisfaction."
        ),
    }
    text = "# Section 03 Candidate Evidence\n\n"
    for heading in REPORT_HEADINGS:
        text += f"## {heading}\n\n{sections[heading]}\n\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def _tabular_metadata(
    path: Path,
    frame: pd.DataFrame,
    *,
    bundle_id: str,
    relative_name: str,
) -> dict[str, Any]:
    return {
        "path": f"runs/{bundle_id}/{relative_name}",
        "row_count": int(len(frame)),
        "columns": list(frame.columns),
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _file_metadata(path: Path, *, bundle_id: str, relative_name: str) -> dict[str, Any]:
    return {
        "path": f"runs/{bundle_id}/{relative_name}",
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _current_verified_bundle(section_root: Path) -> str | None:
    manifest_path = section_root / "section03_manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    bundle_id = manifest.get("bundle_id")
    return bundle_id if isinstance(bundle_id, str) else None


def _cleanup_section03(section_root: Path, *, retained_bundle: str) -> None:
    runs_root = section_root / "runs"
    if not runs_root.exists():
        return
    retained = {retained_bundle}
    for name in ("section03_manifest.json",):
        pointer = section_root / name
        if pointer.is_file():
            try:
                manifest = json.loads(pointer.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            for key in ("bundle_id", "previous_bundle_id"):
                if manifest.get(key):
                    retained.add(str(manifest[key]))
    for child in runs_root.iterdir():
        if child.name.startswith(".staging-"):
            shutil.rmtree(child)
        elif child.is_dir() and child.name not in retained:
            shutil.rmtree(child)


@contextmanager
def _section03_lock(section_root: Path) -> Any:
    section_root.mkdir(parents=True, exist_ok=True)
    lock_path = section_root / "section03.lock"
    with lock_path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _write_section03_evidence_unlocked(
    config: GeneratorConfig,
    datasets: "Mapping[str, pd.DataFrame]",
    topic_events: "Mapping[str, pd.DataFrame]",
    *,
    clean: bool = False,
) -> DriftEvidenceResult:
    required = {"customers", "orders", "payments"}
    if not required.issubset(datasets):
        raise ValueError("Section 03 evidence requires customers, orders, and payments")
    window = resolve_drift_window(config)
    section_root = config.section03_evidence_root
    runs_root = section_root / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    staging = runs_root / f".staging-{uuid.uuid4().hex}"
    staging.mkdir()
    try:
        normalized_events = normalize_commerce_events_for_features(topic_events)
        labels = build_purchase_labels(datasets["customers"], datasets["payments"], window=window)
        features = build_point_in_time_customer_features(
            datasets["customers"],
            datasets["orders"],
            datasets["payments"],
            normalized_events,
            window=window,
        )
        training = build_feature_label_join(labels, features)
        health = build_feature_health_daily(
            datasets["customers"],
            datasets["orders"],
            window=window,
            drift=config.drift,
        )
        if config.scale == "medium" and not health["warning_flag"].eq(True).any():
            raise ValueError(
                "canonical medium evidence requires at least one warning-or-alert day"
            )
        alerts = build_feature_drift_alerts(health, alert_threshold=config.drift.psi_alert)
        source_hash = _sha256(config.source_config_path)
        snapshot = {
            "schema_version": 1,
            "section": "03_data_generator_improvement",
            "source_config_path": _repo_relative(config.source_config_path),
            "source_config_sha256": source_hash,
            "platform_name": config.platform_name,
            "scale": config.scale,
            "random_seed": config.random_seed,
            "history_days": config.history_days,
            "entities": config.entities,
            "start_ts": _iso_utc(window.start_ts),
            "end_ts": _iso_utc(window.end_ts),
            "drift_start_ts": _iso_utc(window.drift_start_ts),
            "feature_cutoff_ts": _iso_utc(window.feature_cutoff_ts),
            "label_end_ts": _iso_utc(window.label_end_ts),
            "baseline_date": window.baseline_date.isoformat(),
            "drift": {
                "enabled": config.drift.enabled,
                "scenario": config.drift.scenario,
                "mode": config.drift.mode,
                "cutoff_fraction": config.drift.cutoff_fraction,
                "post_rate_multiplier": config.drift.post_rate_multiplier,
                "psi_warning": config.drift.psi_warning,
                "psi_alert": config.drift.psi_alert,
                "label_horizon_days": config.drift.label_horizon_days,
            },
        }
        (staging / ARTIFACT_FILENAMES["config_snapshot"]).write_text(
            yaml.safe_dump(snapshot, sort_keys=False),
            encoding="utf-8",
            newline="\n",
        )
        frames = {
            "labels": labels,
            "feature_health_daily": health,
            "drift_alerts": alerts,
            "training_join": training,
            "labels_sample": labels.sort_values("id", kind="stable").head(20),
            "feature_health_sample": health.sort_values(
                ["monitoring_date", "feature_name"], kind="stable"
            ).head(20),
            "drift_alerts_sample": alerts.sort_values(
                ["alert_date", "feature_name"], kind="stable"
            ).head(20),
            "training_sample": training.sort_values("id", kind="stable").head(20),
        }
        for key, frame in frames.items():
            _write_csv(
                staging / ARTIFACT_FILENAMES[key],
                frame,
                health=key in {"feature_health_daily", "feature_health_sample"},
            )
        _write_image(
            staging / ARTIFACT_FILENAMES["evidence_image"],
            config=config,
            window=window,
            training=training,
        )

        order_rate = summarize_drift_rates(datasets["orders"]["order_timestamp"], window=window)
        rate_summary: dict[str, Any] = {
            "order_pre_count": order_rate.pre_count,
            "order_post_count": order_rate.post_count,
            "order_pre_rate_per_day": _round_12(order_rate.pre_rate_per_day),
            "order_post_rate_per_day": _round_12(order_rate.post_rate_per_day),
            "order_normalized_post_pre_ratio": _round_12(order_rate.normalized_post_pre_ratio),
            "stream_pre_count": 0,
            "stream_post_count": 0,
            "stream_normalized_post_pre_ratio": None,
        }
        stream_inherited = True
        order_derived = normalized_events.dropna(subset=["order_id"])
        if not order_derived.empty:
            stream_timestamps = pd.to_datetime(
                order_derived["event_timestamp"],
                errors="raise",
                utc=True,
            ).dt.tz_convert(None)
            stream_rate = summarize_drift_rates(stream_timestamps, window=window)
            rate_summary.update(
                {
                    "stream_pre_count": stream_rate.pre_count,
                    "stream_post_count": stream_rate.post_count,
                    "stream_normalized_post_pre_ratio": _round_12(
                        stream_rate.normalized_post_pre_ratio
                    ),
                }
            )
            if config.scale == "medium":
                stream_inherited = (
                    stream_rate.pre_count >= 100
                    and stream_rate.post_count >= 100
                    and abs(
                        stream_rate.normalized_post_pre_ratio
                        - order_rate.normalized_post_pre_ratio
                    )
                    <= 0.20
                )
        observed_counts = {
            entity: int(len(datasets[entity]))
            for entity in config.entities
            if entity in datasets
        }
        checks = {
            "configured_counts_preserved": observed_counts == config.entities,
            "streaming_distribution_inherited": stream_inherited,
            "labels_exact_schema": list(labels.columns) == ["id", "label"],
            "labels_unique": bool(labels["id"].notna().all() and labels["id"].is_unique),
            "labels_binary": bool(labels["label"].isin([0, 1]).all()),
            "training_join_one_to_one": bool(
                len(training) == len(labels) and training["id"].is_unique
            ),
            "point_in_time_safe": bool(
                (training["event_timestamp"] == _utc(window.feature_cutoff_ts)).all()
                and (training["created"] == _utc(window.feature_cutoff_ts)).all()
            ),
            "psi_finite": bool(
                np.isfinite(health["psi_vs_baseline"].astype(float)).all()
                and health["psi_vs_baseline"].ge(0).all()
            ),
            "alert_threshold_respected": bool(
                alerts.empty or alerts["psi_value"].ge(config.drift.psi_alert).all()
            ),
        }
        if not all(checks.values()):
            failed = ", ".join(key for key, value in checks.items() if not value)
            raise ValueError(f"Section 03 evidence checks failed: {failed}")
        _write_report(
            staging / ARTIFACT_FILENAMES["quality_report"],
            config=config,
            window=window,
            rate_summary=rate_summary,
            health=health,
            alerts=alerts,
            labels=labels,
            training=training,
            checks=checks,
        )
        artifact_hashes = {
            key: _sha256(staging / relative)
            for key, relative in ARTIFACT_FILENAMES.items()
        }
        bundle_id = hashlib.sha256(
            json.dumps(
                artifact_hashes,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        final_root = runs_root / bundle_id
        if final_root.exists():
            shutil.rmtree(staging)
        else:
            os.replace(staging, final_root)
        artifacts: dict[str, dict[str, Any]] = {}
        for key, relative in ARTIFACT_FILENAMES.items():
            path = final_root / relative
            if key in frames:
                artifacts[key] = _tabular_metadata(
                    path,
                    frames[key],
                    bundle_id=bundle_id,
                    relative_name=relative,
                )
            else:
                artifacts[key] = _file_metadata(
                    path,
                    bundle_id=bundle_id,
                    relative_name=relative,
                )
        label_artifact = artifacts["labels"]
        training_artifact = artifacts["training_join"]
        health_artifact = artifacts["feature_health_daily"]
        consumer_contract = {
            "schema_version": 1,
            "label": {
                "artifact_key": "labels",
                "path": label_artifact["path"],
                "sha256": label_artifact["sha256"],
                "columns": ["id", "label"],
                "entity_key": "id",
            },
            "training_join": {
                "artifact_key": "training_join",
                "path": training_artifact["path"],
                "sha256": training_artifact["sha256"],
                "entity_key": "id",
                "event_timestamp_column": "event_timestamp",
                "feature_cutoff_ts": _iso_utc(window.feature_cutoff_ts),
                "point_in_time_rule": "event_timestamp <= as_of and created <= event_timestamp",
            },
            "feature_health": {
                "artifact_key": "feature_health_daily",
                "path": health_artifact["path"],
                "sha256": health_artifact["sha256"],
                "feature_name": "f_customer_order_frequency_7d",
                "window_days": 7,
                "baseline_date": window.baseline_date.isoformat(),
                "monitoring_start": health["monitoring_date"].min().isoformat(),
                "monitoring_end": health["monitoring_date"].max().isoformat(),
                "cohort_size": int(health["customer_count"].iloc[0]),
                "psi_column": "psi_vs_baseline",
                "status_column": "drift_status",
                "warning_threshold": config.drift.psi_warning,
                "alert_threshold": config.drift.psi_alert,
            },
        }
        rubric_cells = {
            "E32": {
                "points": 1,
                "status": "Candidate",
                "required_checks": [
                    "configured_counts_preserved",
                    "streaming_distribution_inherited",
                    "training_join_one_to_one",
                    "point_in_time_safe",
                ],
                "artifact_keys": ["config_snapshot", "training_join", "evidence_image"],
            },
            "E33": {
                "points": 1,
                "status": "Candidate",
                "required_checks": ["configured_counts_preserved"],
                "artifact_keys": ["config_snapshot"],
            },
            "E34": {
                "points": 2,
                "status": "Candidate",
                "required_checks": [
                    "labels_exact_schema",
                    "labels_unique",
                    "labels_binary",
                ],
                "artifact_keys": ["labels", "labels_sample"],
            },
        }
        manifest = {
            "schema_version": 1,
            "section": "03_data_generator_improvement",
            "generated_at": pd.Timestamp.now(tz="UTC").isoformat().replace("+00:00", "Z"),
            "source_config_path": snapshot["source_config_path"],
            "source_config_sha256": source_hash,
            "bundle_id": bundle_id,
            "previous_bundle_id": _current_verified_bundle(section_root),
            "config_snapshot": artifacts["config_snapshot"]["path"],
            "scale": config.scale,
            "random_seed": config.random_seed,
            "history_days": config.history_days,
            "windows": {
                "start_ts": _iso_utc(window.start_ts),
                "end_ts": _iso_utc(window.end_ts),
                "drift_start_ts": _iso_utc(window.drift_start_ts),
                "feature_cutoff_ts": _iso_utc(window.feature_cutoff_ts),
                "label_end_ts": _iso_utc(window.label_end_ts),
                "baseline_date": window.baseline_date.isoformat(),
            },
            "drift_config": snapshot["drift"],
            "configured_entity_counts": config.entities,
            "observed_entity_counts": observed_counts,
            "rate_summary": rate_summary,
            "consumer_contract": consumer_contract,
            "rubric_cells": rubric_cells,
            "checks": checks,
            "runtime_evidence": {
                "status": "pending",
                "spark": None,
                "airflow": None,
                "datahub": None,
            },
            "artifacts": artifacts,
        }
        pointer = section_root / "section03_candidate_manifest.json"
        temporary_pointer = section_root / f".{pointer.name}.{uuid.uuid4().hex}.tmp"
        temporary_pointer.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary_pointer, pointer)
        if clean:
            _cleanup_section03(section_root, retained_bundle=bundle_id)
        return DriftEvidenceResult(
            config_snapshot=final_root / ARTIFACT_FILENAMES["config_snapshot"],
            labels=final_root / ARTIFACT_FILENAMES["labels"],
            feature_health_daily=final_root / ARTIFACT_FILENAMES["feature_health_daily"],
            drift_alerts=final_root / ARTIFACT_FILENAMES["drift_alerts"],
            training_join=final_root / ARTIFACT_FILENAMES["training_join"],
            labels_sample=final_root / ARTIFACT_FILENAMES["labels_sample"],
            feature_health_sample=final_root / ARTIFACT_FILENAMES["feature_health_sample"],
            drift_alerts_sample=final_root / ARTIFACT_FILENAMES["drift_alerts_sample"],
            training_sample=final_root / ARTIFACT_FILENAMES["training_sample"],
            evidence_image=final_root / ARTIFACT_FILENAMES["evidence_image"],
            report=final_root / ARTIFACT_FILENAMES["quality_report"],
            manifest=pointer,
        )
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def write_section03_evidence(
    config: GeneratorConfig,
    datasets: "Mapping[str, pd.DataFrame]",
    topic_events: "Mapping[str, pd.DataFrame]",
    *,
    clean: bool = False,
) -> DriftEvidenceResult:
    with _section03_lock(config.section03_evidence_root):
        return _write_section03_evidence_unlocked(
            config,
            datasets,
            topic_events,
            clean=clean,
        )


__all__ = [
    "ALERT_COLUMNS",
    "DriftEvidenceResult",
    "HEALTH_COLUMNS",
    "build_feature_drift_alerts",
    "build_feature_health_daily",
    "write_section03_evidence",
]
