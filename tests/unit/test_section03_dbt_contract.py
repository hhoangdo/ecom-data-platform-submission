from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
from types import SimpleNamespace

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
DBT_ROOT = ROOT / "infra" / "analytics" / "dbt"
WRAPPER_PATH = ROOT / "scripts" / "analytics" / "run_section03_dbt.py"
DEFAULT_SELECTORS = (
    "+ml_customer_purchase_training",
    "+feature_drift_alerts",
)
REQUIRED_VARS = (
    "drift_start_ts",
    "feature_cutoff_ts",
    "label_end_ts",
    "baseline_date",
    "psi_warning",
    "psi_alert",
    "psi_epsilon",
    "psi_quantile_bins",
)
NEW_MODEL_PATHS = (
    DBT_ROOT / "models" / "gold" / "ml_customer_label.sql",
    DBT_ROOT / "models" / "gold" / "agg_feature_health_daily.sql",
    DBT_ROOT / "models" / "gold" / "feature_drift_alerts.sql",
    DBT_ROOT / "models" / "gold" / "ml_customer_purchase_training.sql",
)
SINGULAR_TEST_PATHS = (
    DBT_ROOT / "tests" / "assert_ml_customer_label_matches_horizon.sql",
    DBT_ROOT / "tests" / "assert_training_features_are_point_in_time.sql",
    DBT_ROOT / "tests" / "assert_drift_alert_threshold.sql",
    DBT_ROOT / "tests" / "assert_commerce_event_dedup_unambiguous.sql",
)


def _load_wrapper():
    assert WRAPPER_PATH.is_file(), f"missing wrapper: {WRAPPER_PATH.relative_to(ROOT)}"
    spec = importlib.util.spec_from_file_location("run_section03_dbt", WRAPPER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _model_by_name(path: Path) -> dict[str, object]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {model["name"]: model for model in payload["models"]}


def _column_names(model: dict[str, object]) -> list[str]:
    return [column["name"] for column in model["columns"]]


def test_required_topic03_paths_exist() -> None:
    required = (
        WRAPPER_PATH,
        *NEW_MODEL_PATHS,
        DBT_ROOT / "models" / "gold" / "_drift.yml",
        *SINGULAR_TEST_PATHS,
    )
    missing = [path.relative_to(ROOT).as_posix() for path in required if not path.is_file()]
    assert missing == []


def test_wrapper_derives_exact_medium_vars() -> None:
    wrapper = _load_wrapper()

    actual = wrapper.build_section03_vars(
        ROOT / "configs" / "generator" / "base.yaml",
        "medium",
    )

    assert actual == {
        "drift_start_ts": "2026-04-11T08:23:00Z",
        "feature_cutoff_ts": "2026-04-24T23:59:00Z",
        "label_end_ts": "2026-05-01T23:59:00Z",
        "baseline_date": "2026-04-10",
        "psi_warning": 0.1,
        "psi_alert": 0.15,
        "psi_epsilon": 1e-6,
        "psi_quantile_bins": 10,
    }


def test_wrapper_builds_parent_inclusive_command_and_propagates_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wrapper = _load_wrapper()
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return SimpleNamespace(returncode=37)

    monkeypatch.setattr(wrapper.shutil, "which", lambda name: "C:/tools/dbt.exe")
    monkeypatch.setattr(wrapper.subprocess, "run", fake_run)

    return_code = wrapper.main(
        [
            "--config",
            "configs/generator/base.yaml",
            "--scale",
            "medium",
            "--project-dir",
            "infra/analytics/dbt",
            "--profiles-dir",
            "infra/analytics/dbt",
        ]
    )

    expected_vars = {
        "baseline_date": "2026-04-10",
        "drift_start_ts": "2026-04-11T08:23:00Z",
        "feature_cutoff_ts": "2026-04-24T23:59:00Z",
        "label_end_ts": "2026-05-01T23:59:00Z",
        "psi_alert": 0.15,
        "psi_epsilon": 1e-6,
        "psi_quantile_bins": 10,
        "psi_warning": 0.1,
    }
    assert return_code == 37
    assert captured["command"] == [
        "C:/tools/dbt.exe",
        "build",
        "--project-dir",
        "infra/analytics/dbt",
        "--profiles-dir",
        "infra/analytics/dbt",
        "--vars",
        json.dumps(expected_vars, sort_keys=True, separators=(",", ":")),
        "--select",
        *DEFAULT_SELECTORS,
    ]
    assert captured["kwargs"] == {"check": False, "cwd": ROOT}


def test_wrapper_rejects_non_parent_inclusive_selection() -> None:
    wrapper = _load_wrapper()

    with pytest.raises(SystemExit) as exc_info:
        wrapper.parse_args(
            [
                "--scale",
                "medium",
                "--select",
                "ml_customer_purchase_training",
            ]
        )

    assert exc_info.value.code == 2


def test_section03_sql_vars_are_required_without_copied_defaults() -> None:
    sql_paths = (
        DBT_ROOT / "models" / "silver" / "stg_commerce_events.sql",
        DBT_ROOT / "models" / "gold" / "feat_customer_90d.sql",
        DBT_ROOT / "models" / "gold" / "feat_stream_60m.sql",
        DBT_ROOT / "models" / "gold" / "feat_customer_unified.sql",
        *NEW_MODEL_PATHS,
        *SINGULAR_TEST_PATHS,
    )
    sql = "\n".join(path.read_text(encoding="utf-8") for path in sql_paths)
    project = (DBT_ROOT / "dbt_project.yml").read_text(encoding="utf-8")

    for name in REQUIRED_VARS:
        assert re.search(rf"var\(\s*['\"]{name}['\"]\s*\)", sql)
        assert not re.search(rf"var\(\s*['\"]{name}['\"]\s*,", sql)
        assert not re.search(rf"^\s*{name}\s*:", project, re.MULTILINE)
    for forbidden in ("2026-04-11", "2026-04-24", "2026-05-01", "0.10", "0.15"):
        assert forbidden not in sql
        assert forbidden not in project


def test_existing_models_encode_cutoff_and_deterministic_dedup() -> None:
    staging = (
        DBT_ROOT / "models" / "silver" / "stg_commerce_events.sql"
    ).read_text(encoding="utf-8").lower()
    offline = (
        DBT_ROOT / "models" / "gold" / "feat_customer_90d.sql"
    ).read_text(encoding="utf-8").lower()
    stream = (
        DBT_ROOT / "models" / "gold" / "feat_stream_60m.sql"
    ).read_text(encoding="utf-8").lower()
    unified = (
        DBT_ROOT / "models" / "gold" / "feat_customer_unified.sql"
    ).read_text(encoding="utf-8").lower()

    assert "created_ts desc" in staging
    assert "ingest_ts desc" in staging
    assert "event_timestamp desc" in staging
    assert "dim_customer" in offline
    assert "fact_payment_attempt" in offline
    assert "feature_cutoff_ts" in offline
    assert "event_timestamp <=" in stream
    assert "created_ts <=" in stream
    assert "feature_cutoff_ts" in unified


def test_drift_model_contracts_have_exact_order_and_types() -> None:
    drift_models = _model_by_name(DBT_ROOT / "models" / "gold" / "_drift.yml")

    label = drift_models["ml_customer_label"]
    assert _column_names(label) == ["id", "label"]
    assert [column["data_type"] for column in label["columns"]] == [
        "varchar",
        "integer",
    ]

    health = drift_models["agg_feature_health_daily"]
    assert _column_names(health) == [
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
    ]

    alerts = drift_models["feature_drift_alerts"]
    assert _column_names(alerts) == [
        "alert_date",
        "feature_name",
        "psi_value",
        "threshold",
        "action",
    ]

    training = drift_models["ml_customer_purchase_training"]
    assert _column_names(training) == [
        "id",
        "event_timestamp",
        "label",
        "f_customer_total_orders_90d",
        "f_customer_paid_revenue_90d",
        "f_customer_avg_order_value_90d",
        "f_customer_distinct_categories_90d",
        "f_stream_views_60m",
        "f_stream_add_to_cart_60m",
        "f_stream_checkout_started_60m",
        "f_stream_order_placed_60m",
        "f_stream_cart_to_purchase_ratio_60m",
        "created",
    ]


def test_singular_tests_recompute_source_truth() -> None:
    contents = {
        path.name: path.read_text(encoding="utf-8").lower()
        for path in SINGULAR_TEST_PATHS
    }

    assert "fact_payment_attempt" in contents["assert_ml_customer_label_matches_horizon.sql"]
    assert "full outer join" in contents["assert_training_features_are_point_in_time.sql"]
    assert "agg_feature_health_daily" in contents["assert_drift_alert_threshold.sql"]
    assert "raw_kafka_commerce_events" in contents[
        "assert_commerce_event_dedup_unambiguous.sql"
    ]
