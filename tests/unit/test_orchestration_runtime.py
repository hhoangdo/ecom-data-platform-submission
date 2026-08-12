import importlib
import importlib.util
import hashlib
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest
from compose_model import load_compose_model
from vina_bim_shop.orchestration import datahub_ingestion, hourly_batch
from vina_bim_shop.orchestration.specs import REQUIRED_DAG_IDS, dag_specs_by_id
from vina_bim_shop.quality.policies import (
    ValidationSeverity,
    gate_outcome_for_layer,
    should_fail_reconciliation,
)
from vina_bim_shop.quality.reports import ValidationReport


def test_required_airflow_dags_are_declared_with_manual_or_demo_schedules() -> None:
    dag_specs = dag_specs_by_id()

    assert REQUIRED_DAG_IDS == (
        "hourly_batch_lakehouse",
        "kafka_topic_bootstrap",
        "pinot_bootstrap",
        "datahub_ingestion",
        "reconciliation_report",
        "local_evidence_build",
        "mini_coursework_pipeline",
        "rag_index_pipeline",
    )
    assert tuple(dag_specs) == REQUIRED_DAG_IDS

    assert dag_specs["kafka_topic_bootstrap"].schedule == "manual"
    assert dag_specs["pinot_bootstrap"].schedule == "manual"
    assert dag_specs["datahub_ingestion"].schedule == "manual"
    assert dag_specs["local_evidence_build"].schedule == "manual"
    assert dag_specs["rag_index_pipeline"].schedule == "manual"
    assert dag_specs["hourly_batch_lakehouse"].schedule == "hourly_demo"
    assert dag_specs["reconciliation_report"].schedule == "hourly_demo"
    assert dag_specs["mini_coursework_pipeline"].schedule == "hourly_demo"


def test_required_airflow_dags_preserve_adr06_boundaries() -> None:
    dag_specs = dag_specs_by_id()

    assert dag_specs["hourly_batch_lakehouse"].supports_hourly_logical_window is True
    assert dag_specs["reconciliation_report"].supports_hourly_logical_window is True
    assert dag_specs["pinot_bootstrap"].supports_hourly_logical_window is False
    assert dag_specs["kafka_topic_bootstrap"].supports_hourly_logical_window is False

    for dag_id in REQUIRED_DAG_IDS:
        assert dag_specs[dag_id].monitors_flink is False


def test_quality_gate_policy_matches_adr06_failure_contract() -> None:
    bronze_warning = gate_outcome_for_layer("bronze_raw", success=False)
    assert bronze_warning.severity is ValidationSeverity.WARNING
    assert bronze_warning.blocks_dag is False
    assert bronze_warning.requires_quarantine is True

    silver_failure = gate_outcome_for_layer("silver", success=False)
    assert silver_failure.severity is ValidationSeverity.ERROR
    assert silver_failure.blocks_dag is True
    assert silver_failure.requires_quarantine is False

    gold_failure = gate_outcome_for_layer("gold_trino", success=False)
    assert gold_failure.severity is ValidationSeverity.ERROR
    assert gold_failure.blocks_dag is True

    pinot_warning = gate_outcome_for_layer("pinot_queries", success=False)
    assert pinot_warning.severity is ValidationSeverity.WARNING
    assert pinot_warning.blocks_dag is False

    datahub_warning = gate_outcome_for_layer("datahub", success=False)
    assert datahub_warning.severity is ValidationSeverity.WARNING
    assert datahub_warning.blocks_dag is False

    critical_datahub_failure = gate_outcome_for_layer("datahub", success=False, critical=True)
    assert critical_datahub_failure.blocks_dag is True


def test_reconciliation_is_the_only_pinot_path_that_escalates_to_failure() -> None:
    assert should_fail_reconciliation(pinot_success=False, reconciliation_success=True) is False
    assert should_fail_reconciliation(pinot_success=False, reconciliation_success=False) is True
    assert should_fail_reconciliation(pinot_success=True, reconciliation_success=False) is True


def test_pinot_bootstrap_dag_exists_without_flink_control_logic() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    dag_path = repo_root / "infra" / "orchestration" / "airflow" / "dags" / "pinot_bootstrap.py"
    dag_source = dag_path.read_text(encoding="utf-8")

    assert "pinot_bootstrap" in dag_source
    assert "vina_bim_shop.flink" not in dag_source
    assert "scripts/flink/run_" not in dag_source
    assert "restart" not in dag_source.lower()


def test_prepare_spark_evidence_root_uses_root_exec_for_shared_workspace(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}

    def fake_run_command(command: list[str], *, cwd: Path | None = None) -> str:
        captured["command"] = command
        captured["cwd"] = cwd
        return ""

    monkeypatch.setattr(hourly_batch, "_run_command", fake_run_command)

    evidence_root = tmp_path / "runs" / "hourly_batch_lakehouse" / "spark_batch"
    hourly_batch._prepare_spark_evidence_root(evidence_root)

    command = captured["command"]
    assert isinstance(command, list)
    assert command[:7] == ["docker", "compose", "exec", "-T", "--user", "root", "spark-master"]
    assert command[7:9] == ["bash", "-lc"]
    assert "mkdir -p" in command[9]
    assert "chmod -R 0777" in command[9]
    assert evidence_root.as_posix() in command[9]
    assert captured["cwd"] == hourly_batch.REPO_ROOT


def test_section03_prepare_spark_evidence_root_uses_the_shared_bind_mount(monkeypatch, tmp_path) -> None:
    pipeline = importlib.import_module("vina_bim_shop.orchestration.mini_coursework_pipeline")

    def fail_if_docker_is_called(*_args, **_kwargs):
        raise AssertionError("Section 03 Airflow runtime must not require the Docker socket")

    monkeypatch.setattr(pipeline, "_run_command", fail_if_docker_is_called)
    evidence_root = tmp_path / "runs" / "section03" / "spark_features"

    pipeline._prepare_spark_evidence_root(evidence_root)

    assert evidence_root.is_dir()


def test_prepare_gx_docs_root_uses_root_exec_for_static_site_mount(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_command(command: list[str], *, cwd: Path | None = None) -> str:
        captured["command"] = command
        captured["cwd"] = cwd
        return ""

    monkeypatch.setattr(hourly_batch, "_run_command", fake_run_command)

    hourly_batch._prepare_gx_docs_root()

    command = captured["command"]
    assert isinstance(command, list)
    assert command[:7] == ["docker", "compose", "exec", "-T", "--user", "root", "gx-docs"]
    assert command[7:9] == ["sh", "-lc"]
    assert "mkdir -p /usr/share/nginx/html" in command[9]
    assert "chmod -R 0777 /usr/share/nginx/html" in command[9]
    assert captured["cwd"] == hourly_batch.REPO_ROOT


def test_airflow_webserver_allows_slow_local_plugin_startup() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    compose = load_compose_model(repo_root)
    env_vars = compose["services"]["airflow-webserver"]["environment"]

    assert int(env_vars["AIRFLOW__WEBSERVER__WEB_SERVER_MASTER_TIMEOUT"]) >= 300
    assert int(env_vars["AIRFLOW__WEBSERVER__WEB_SERVER_WORKER_TIMEOUT"]) >= 300


def test_run_datahub_ingestion_includes_all_repo_recipes(monkeypatch, tmp_path) -> None:
    calls: list[list[str]] = []

    def fake_build_run_root(_dag_id: str, _run_id: str):
        return tmp_path

    def fake_run_command(command: list[str], *, cwd: Path | None = None) -> str:
        calls.append(command)
        return "ok"

    monkeypatch.setattr(datahub_ingestion, "build_run_root", fake_build_run_root)
    monkeypatch.setattr(datahub_ingestion, "_run_command", fake_run_command)
    monkeypatch.setattr(
        datahub_ingestion,
        "_run_custom_lineage_emission",
        lambda: {
            "spark": "ok",
            "flink": "ok",
            "coursework_pipelines": {"status": "success"},
            "coursework_assertions": {"status": "success"},
        },
    )
    monkeypatch.setattr(datahub_ingestion, "_render_docs", lambda reports: reports)

    manifest = datahub_ingestion.run_datahub_ingestion(run_id="manual__2026-06-03T00:00:00+00:00")

    recipe_names = [Path(command[-1]).name for command in calls if command[:3] == ["datahub", "ingest", "run"]]
    assert recipe_names == [
        "kafka_topics.yml",
        "minio_storage.yml",
        "trino_tables.yml",
        "dbt_legacy.yml",
    ]
    assert manifest["status"] == "success"


def test_run_datahub_ingestion_fails_when_coursework_metadata_emission_fails(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(datahub_ingestion, "build_run_root", lambda _dag_id, _run_id: tmp_path)
    monkeypatch.setattr(datahub_ingestion, "_run_command", lambda command, cwd=None: "ok")
    monkeypatch.setattr(
        datahub_ingestion,
        "_run_custom_lineage_emission",
        lambda: {"coursework_pipelines": {"status": "failed", "reason": "missing assertions"}},
    )
    monkeypatch.setattr(datahub_ingestion, "_render_docs", lambda reports: reports)

    manifest = datahub_ingestion.run_datahub_ingestion(run_id="manual__coursework_failure")

    assert manifest["status"] == "failed"
    assert manifest["ingestion_results"]["custom_lineage"]["coursework_pipelines"]["status"] == "failed"


def test_run_datahub_ingestion_preserves_existing_quality_reports(monkeypatch, tmp_path) -> None:
    existing_report = ValidationReport(
        layer="bronze_raw",
        suite_name="bronze_raw_minio",
        success=False,
        status="warning",
        severity="warning",
        blocks_dag=False,
        requires_quarantine=True,
        summary="1/2 expectations passed.",
        artifacts=["quality/bronze_raw_minio.json"],
        details={
            "results": [
                {
                    "success": False,
                    "expectation_config": {
                        "type": "expect_column_values_to_not_be_null",
                        "kwargs": {"column": "path"},
                    },
                    "result": {"unexpected_count": 1},
                }
            ]
        },
    )
    quality_dir = tmp_path / "runs" / "hourly_batch_lakehouse" / "manual__2026" / "quality"
    quality_dir.mkdir(parents=True)
    (quality_dir / "bronze_raw_minio.json").write_text(
        json.dumps(existing_report.to_dict()),
        encoding="utf-8",
    )

    captured_reports: list[ValidationReport] = []

    def fake_render_docs(reports: list[ValidationReport]) -> None:
        captured_reports.extend(reports)

    monkeypatch.setattr(datahub_ingestion, "RUNS_ROOT", tmp_path / "runs")
    run_root = tmp_path / "runs" / "datahub_ingestion" / "manual__2026"
    monkeypatch.setattr(datahub_ingestion, "build_run_root", lambda _dag_id, _run_id: run_root)
    monkeypatch.setattr(datahub_ingestion, "_run_command", lambda command, cwd=None: "ok")
    monkeypatch.setattr(datahub_ingestion, "_run_custom_lineage_emission", lambda: {"spark": "ok", "flink": "ok"})
    monkeypatch.setattr(datahub_ingestion, "_render_docs", fake_render_docs)

    datahub_ingestion.run_datahub_ingestion(run_id="manual__2026-06-03T00:00:00+00:00")

    rendered_suites = {report.suite_name for report in captured_reports}
    assert rendered_suites == {"bronze_raw_minio", "datahub_ingestion"}
    assert (run_root / "run_manifest.json").is_file()


def test_legacy_hourly_wrapper_composes_the_six_coursework_stages(monkeypatch, tmp_path) -> None:
    spec = importlib.util.find_spec("vina_bim_shop.orchestration.mini_coursework_pipeline")
    assert spec is not None, "Expected the six-stage coursework pipeline runtime module."
    mini_coursework_pipeline = importlib.import_module(
        "vina_bim_shop.orchestration.mini_coursework_pipeline"
    )
    calls: list[str] = []

    monkeypatch.setattr(hourly_batch, "build_run_root", lambda _dag_id, _run_id: tmp_path)
    monkeypatch.setattr(
        hourly_batch,
        "settings_from_environment",
        lambda: mini_coursework_pipeline.CourseworkPipelineSettings.for_tests(),
    )

    for function_name in mini_coursework_pipeline.STAGE_FUNCTION_NAMES:
        def fake_stage(*, _function_name=function_name, **_kwargs):
            calls.append(_function_name)
            return {
                "stage": _function_name,
                "artifact": f"{mini_coursework_pipeline.STAGE_DETAILS[_function_name][0]}.json",
            }

        monkeypatch.setattr(hourly_batch, function_name, fake_stage)

    result = hourly_batch.run_hourly_batch_lakehouse(
        run_id="manual__2026-04-26T01:00:00+00:00",
        start_ts="2026-04-26T00:00:00+00:00",
        end_ts="2026-04-26T01:00:00+00:00",
    )

    assert calls == list(mini_coursework_pipeline.STAGE_FUNCTION_NAMES)
    assert result["manifest"]["stage_artifacts"] == [
        f"{mini_coursework_pipeline.STAGE_DETAILS[name][0]}.json"
        for name in mini_coursework_pipeline.STAGE_FUNCTION_NAMES
    ]


def test_coursework_dp1_copy_uses_airflow_minio_client(monkeypatch, tmp_path) -> None:
    pipeline = importlib.import_module("vina_bim_shop.orchestration.mini_coursework_pipeline")
    source = tmp_path / "customers" / "part-000.parquet"
    source.parent.mkdir()
    source.write_text("stub", encoding="utf-8")
    commands: list[list[str]] = []

    monkeypatch.setattr(pipeline, "_run_command", lambda command: commands.append(command) or "")

    pipeline._copy_to_bronze(
        source=source,
        object_key="bronze/batch/customers/snapshot_date=2026-04-26/part-000.parquet",
        settings=pipeline.CourseworkPipelineSettings.for_tests(),
    )

    assert commands == [
        [
            "mc",
            "alias",
            "set",
            "coursework",
            "http://minio:9000",
            "vina_minio",
            "vina_minio_password",
        ],
        [
            "mc",
            "cp",
            str(source),
            "coursework/bronze/batch/customers/snapshot_date=2026-04-26/part-000.parquet",
        ],
    ]


def test_coursework_spark_stages_run_from_the_compose_project_root(monkeypatch, tmp_path) -> None:
    pipeline = importlib.import_module("vina_bim_shop.orchestration.mini_coursework_pipeline")
    observed_working_directories: list[Path] = []

    def fake_spark_stage(**_kwargs):
        observed_working_directories.append(Path.cwd())
        return {"spark_stdout": "ok"}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(pipeline, "_prepare_spark_evidence_root", lambda _path: None)
    monkeypatch.setattr(pipeline, "run_core_transform", fake_spark_stage)
    monkeypatch.setattr(pipeline, "run_feature_compute", fake_spark_stage)
    monkeypatch.setattr(pipeline, "_latest_spark_application_id", lambda: "app-123")
    monkeypatch.setattr(
        pipeline,
        "execute_trino_query",
        lambda _query, **_kwargs: {"rows": [["event_timestamp"], ["created"]]},
    )

    run_root = tmp_path / "run"
    settings = pipeline.CourseworkPipelineSettings.for_tests()
    pipeline.transform_bronze_to_silver_gold(
        run_id="manual__2026-04-26T01:00:00+00:00",
        start_ts="2026-04-26T00:00:00+00:00",
        end_ts="2026-04-26T01:00:00+00:00",
        settings=settings,
        run_root=run_root,
    )
    pipeline.compute_offline_features(
        run_id="manual__2026-04-26T01:00:00+00:00",
        start_ts="2026-04-26T00:00:00+00:00",
        end_ts="2026-04-26T01:00:00+00:00",
        settings=settings,
        run_root=run_root,
    )

    assert observed_working_directories == [pipeline.REPO_ROOT, pipeline.REPO_ROOT]


def test_dp3_contracts_are_exactly_seven_tables_in_dependency_order() -> None:
    pipeline = importlib.import_module("vina_bim_shop.orchestration.mini_coursework_pipeline")

    assert pipeline.FEATURE_TABLES == (
        "feat_customer_90d",
        "feat_stream_60m",
        "feat_customer_unified",
        "ml_customer_label",
        "agg_feature_health_daily",
        "feature_drift_alerts",
        "ml_customer_purchase_training",
    )
    assert tuple(pipeline.DP3_TABLE_CONTRACTS) == pipeline.FEATURE_TABLES
    assert pipeline.DP3_TABLE_CONTRACTS["ml_customer_label"]["columns"] == ["id", "label"]
    assert pipeline.DP3_TABLE_CONTRACTS["feature_drift_alerts"]["allow_empty"] is True
    assert pipeline.DP3_TABLE_CONTRACTS["ml_customer_purchase_training"]["columns"][-1] == "created"


def test_settings_from_airflow_binds_strict_section03_conf_without_variable_fallback() -> None:
    pipeline = importlib.import_module("vina_bim_shop.orchestration.mini_coursework_pipeline")
    connections = {
        "vbs_minio": SimpleNamespace(
            host="minio", port=9000, login="user", password="password", extra_dejson={"region": "us-east-1"}
        ),
        "vbs_trino": SimpleNamespace(host="trino", port=8080, login="analyst"),
        "vbs_kafka": SimpleNamespace(host="kafka", port=29092),
        "datahub_rest_default": SimpleNamespace(host="http://datahub-gms:8080", port=None),
    }
    variable_calls: list[str] = []

    def get_variable(key: str, **_kwargs: object) -> object:
        variable_calls.append(key)
        return {
            "vbs_raw_root": "/workspace/data/raw",
            "vbs_bronze_bucket": "bronze",
            "vbs_spark_evidence_root": "/workspace/evidence/08_airflow_gx/coursework_pipeline",
        }[key]

    settings = pipeline.settings_from_airflow(
        get_connection=lambda key: connections[key],
        get_variable=get_variable,
        dag_run_conf={
            "generator_config_path": "configs/generator/base.yaml",
            "generator_scale": "medium",
            "section03_candidate_manifest_sha256": "a" * 64,
        },
    )

    assert settings.strict_section03 is True
    assert settings.generator_config_path == "configs/generator/base.yaml"
    assert settings.generator_scale == "medium"
    assert settings.section03_candidate_manifest_sha256 == "a" * 64
    assert "vbs_feature_tables" not in variable_calls


def test_validate_offline_features_emits_table_specific_contract_facts(monkeypatch, tmp_path) -> None:
    pipeline = importlib.import_module("vina_bim_shop.orchestration.mini_coursework_pipeline")
    expected_columns = {
        "feat_customer_90d": [
            "customer_id", "event_timestamp", "f_customer_total_orders_90d", "f_customer_paid_revenue_90d",
            "f_customer_avg_order_value_90d", "f_customer_distinct_categories_90d", "created",
        ],
        "feat_stream_60m": [
            "customer_id", "event_timestamp", "f_stream_views_60m", "f_stream_add_to_cart_60m",
            "f_stream_checkout_started_60m", "f_stream_order_placed_60m",
            "f_stream_cart_to_purchase_ratio_60m", "created",
        ],
        "feat_customer_unified": [
            "customer_id", "event_timestamp", "f_customer_total_orders_90d", "f_customer_paid_revenue_90d",
            "f_customer_avg_order_value_90d", "f_customer_distinct_categories_90d", "f_stream_views_60m",
            "f_stream_add_to_cart_60m", "f_stream_checkout_started_60m", "f_stream_order_placed_60m",
            "f_stream_cart_to_purchase_ratio_60m", "created",
        ],
        "ml_customer_label": ["id", "label"],
        "agg_feature_health_daily": [
            "monitoring_date", "feature_name", "window_days", "baseline_date", "customer_count",
            "mean_value", "stddev_value", "psi_vs_baseline", "drift_status", "warning_flag", "alert_flag",
        ],
        "feature_drift_alerts": ["alert_date", "feature_name", "psi_value", "threshold", "action"],
        "ml_customer_purchase_training": [
            "id", "event_timestamp", "label", "f_customer_total_orders_90d", "f_customer_paid_revenue_90d",
            "f_customer_avg_order_value_90d", "f_customer_distinct_categories_90d", "f_stream_views_60m",
            "f_stream_add_to_cart_60m", "f_stream_checkout_started_60m", "f_stream_order_placed_60m",
            "f_stream_cart_to_purchase_ratio_60m", "created",
        ],
    }

    def fake_query(query: str, **_kwargs: object) -> dict[str, object]:
        if query.startswith("describe iceberg.gold."):
            table_name = query.rsplit(".", 1)[-1]
            return {"rows": [[column] for column in expected_columns[table_name]]}
        if "from iceberg.gold." in query:
            table_name = query.split("from iceberg.gold.", 1)[1].split()[0]
            metric_rows = {
                "feat_customer_90d": [1, 1, 0, 0, 0, "2026-04-24T23:59:00Z", "2026-04-24T23:59:00Z", "2026-04-24T23:59:00Z", "2026-04-24T23:59:00Z"],
                "feat_stream_60m": [1, 1, 0, 0, 0, "2026-04-24T23:00:00Z", "2026-04-24T23:00:00Z", "2026-04-24T23:01:00Z", "2026-04-24T23:58:00Z"],
                "feat_customer_unified": [1, 1, 0, 0, 0, "2026-04-24T23:59:00Z", "2026-04-24T23:59:00Z", "2026-04-24T23:59:00Z", "2026-04-24T23:59:00Z"],
                "ml_customer_label": [1, 1, 0, 0, 0, 1],
                "agg_feature_health_daily": [1, 1, 0, 0, 0, 0, 0, 0, 0],
                "feature_drift_alerts": [0, 0, 0, 0, 0, 0, 0],
                "ml_customer_purchase_training": [1, 1, 0, 0, 0, 0, 0, "2026-04-24T23:59:00Z", "2026-04-24T23:59:00Z", "2026-04-24T23:59:00Z", "2026-04-24T23:59:00Z"],
            }
            return {"rows": [metric_rows[table_name]]}
        raise AssertionError(f"unexpected query: {query}")

    class PassingReport:
        success = True
        blocks_dag = False

        def to_dict(self) -> dict[str, object]:
            return {"success": True}

    monkeypatch.setattr(pipeline, "execute_trino_query", fake_query)
    monkeypatch.setattr(pipeline, "_validate_pandas_dataframe", lambda **_kwargs: PassingReport())
    monkeypatch.setattr(pipeline, "_render_run_docs", lambda _root: None)
    fake_ge = types.ModuleType("great_expectations")
    fake_ge.expectations = types.SimpleNamespace(
        ExpectColumnValuesToBeInSet=lambda **kwargs: kwargs,
    )
    monkeypatch.setitem(sys.modules, "great_expectations", fake_ge)

    result = pipeline.validate_offline_features(
        run_id="manual__section03",
        start_ts="2026-04-26T00:00:00+00:00",
        end_ts="2026-04-26T01:00:00+00:00",
        settings=pipeline.CourseworkPipelineSettings.for_tests(),
        run_root=tmp_path / "run",
    )

    rows = result["feature_results"]
    assert [row["table_name"] for row in rows] == list(expected_columns)
    assert all(row["columns"] == expected_columns[row["table_name"]] for row in rows)
    assert all(row["contract_success"] is True for row in rows)


def test_dp3_metric_queries_enforce_exact_alert_threshold_and_training_cutoff() -> None:
    pipeline = importlib.import_module("vina_bim_shop.orchestration.mini_coursework_pipeline")

    _alert_metrics, alert_query = pipeline._dp3_metric_query(
        "feature_drift_alerts", "2026-04-25T23:59:59Z", "2026-04-18"
    )
    _training_metrics, training_query = pipeline._dp3_metric_query(
        "ml_customer_purchase_training", "2026-04-25T23:59:59Z", "2026-04-18"
    )
    _feature_metrics, feature_query = pipeline._dp3_metric_query(
        "feat_customer_90d", "2026-04-25T23:59:59Z", "2026-04-18"
    )
    _health_metrics, health_query = pipeline._dp3_metric_query(
        "agg_feature_health_daily", "2026-04-25T23:59:59Z", "2026-04-18"
    )

    assert "threshold is null or threshold <> 0.15" in alert_query
    assert "alert_date is null or feature_name is null" in alert_query
    assert "monitoring_date is null or feature_name is null" in health_query
    assert "window_days is null or window_days <> 7" in health_query
    assert "baseline_date is null or cast(baseline_date as varchar) <>" in health_query
    assert "t.event_timestamp is null or t.event_timestamp <>" in training_query
    assert "t.created is null or t.created <>" in training_query
    assert "t.label is null or t.label <> l.label" in training_query
    assert "min(event_timestamp) as event_timestamp_min" in feature_query
    assert "min(t.event_timestamp) as event_timestamp_min" in training_query
    assert "min(psi_value) as psi_min" in alert_query


def test_dp3_stream_metric_query_allows_late_arrivals_but_enforces_cutoff_safety() -> None:
    pipeline = importlib.import_module("vina_bim_shop.orchestration.mini_coursework_pipeline")

    feature_metrics, feature_query = pipeline._dp3_metric_query(
        "feat_stream_60m", "2026-04-24T23:59:00Z", "2026-04-10"
    )

    assert "created_cutoff_violation_count" in feature_metrics
    assert "event_cutoff_violation_count" in feature_metrics
    assert "created is null or created >" in feature_query
    assert "event_timestamp is null or event_timestamp >" in feature_query
    assert "created > event_timestamp" not in feature_query


def test_validate_offline_features_requires_matching_dp3_compute_metadata(tmp_path) -> None:
    pipeline = importlib.import_module("vina_bim_shop.orchestration.mini_coursework_pipeline")
    settings = pipeline.CourseworkPipelineSettings.for_tests()
    expected_parameters = {
        "drift_start_ts": "2026-04-11T08:23:00Z",
        "feature_cutoff_ts": "2026-04-24T23:59:00Z",
        "label_end_ts": "2026-05-01T23:59:00Z",
        "baseline_date": "2026-04-10",
    }
    strict_context = {
        "manifest_sha256": "a" * 64,
        "config_sha256": "b" * 64,
        "parameters": expected_parameters,
    }
    run_root = tmp_path / "run"
    run_root.mkdir()
    (run_root / "dp3_compute.json").write_text(
        json.dumps(
            {
                "state": "success",
                "strict_section03": True,
                "generator_config_path": settings.generator_config_path,
                "generator_config_sha256": strict_context["config_sha256"],
                "generator_scale": settings.generator_scale,
                "section03_candidate_manifest_sha256": strict_context["manifest_sha256"],
                "feature_tables": list(pipeline.FEATURE_TABLES),
                "feature_cutoff_ts": "2026-04-23T23:59:00Z",
                "section03_parameters": {
                    **expected_parameters,
                    "feature_cutoff_ts": "2026-04-23T23:59:00Z",
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="compute"):
        pipeline._load_section03_compute_metadata(
            run_root=run_root,
            settings=settings,
            strict_context=strict_context,
        )


def _load_section03_wrapper():
    path = Path(__file__).resolve().parents[2] / "scripts" / "orchestration" / "run_section03_dp3.py"
    assert path.is_file(), "Expected the strict Section 03 Airflow wrapper script."
    spec = importlib.util.spec_from_file_location("run_section03_dp3", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_section03_wrapper_posts_exact_conf_and_exports_hash_bound_artifacts(monkeypatch, tmp_path) -> None:
    module = _load_section03_wrapper()
    repo_root = Path(__file__).resolve().parents[2]
    config_path = repo_root / "configs" / "generator" / "base.yaml"
    config_sha256 = hashlib.sha256(config_path.read_bytes()).hexdigest()
    candidate = tmp_path / "section03_candidate_manifest.json"
    candidate.write_text(
        json.dumps(
            {
                "bundle_id": "b" * 64,
                "source_config_path": "configs/generator/base.yaml",
                "source_config_sha256": config_sha256,
                "scale": "medium",
                "random_seed": 42,
                "windows": {
                    "drift_start_ts": "2026-04-11T08:23:00Z",
                    "feature_cutoff_ts": "2026-04-24T23:59:00Z",
                    "label_end_ts": "2026-05-01T23:59:00Z",
                    "baseline_date": "2026-04-10",
                },
                "runtime_evidence": {"status": "pending"},
            }
        ),
        encoding="utf-8",
    )
    candidate_sha256 = hashlib.sha256(candidate.read_bytes()).hexdigest()
    runs_root = tmp_path / "coursework_pipeline"
    run_root = runs_root / "run-1"
    (run_root / "quality").mkdir(parents=True)
    for artifact in (
        "dp1_ingest.json",
        "dp1_validate.json",
        "dp2_transform.json",
        "dp2_validate.json",
    ):
        (run_root / artifact).write_text(json.dumps({"state": "success"}), encoding="utf-8")
    seven_tables = [
        "feat_customer_90d", "feat_stream_60m", "feat_customer_unified",
        "ml_customer_label", "agg_feature_health_daily", "feature_drift_alerts",
        "ml_customer_purchase_training",
    ]
    (run_root / "dp3_compute.json").write_text(
        json.dumps(
            {
                "state": "success",
                "strict_section03": True,
                "generator_config_path": "configs/generator/base.yaml",
                "generator_config_sha256": config_sha256,
                "generator_scale": "medium",
                "section03_candidate_manifest_sha256": candidate_sha256,
                "feature_tables": seven_tables,
                "feature_cutoff_ts": "2026-04-24T23:59:00Z",
                "section03_parameters": {
                    "drift_start_ts": "2026-04-11T08:23:00Z",
                    "feature_cutoff_ts": "2026-04-24T23:59:00Z",
                    "label_end_ts": "2026-05-01T23:59:00Z",
                    "baseline_date": "2026-04-10",
                },
            }
        ),
        encoding="utf-8",
    )
    (run_root / "dp3_validate.json").write_text(
        json.dumps(
            {
                "state": "success",
                "strict_section03": True,
                "contract_success": True,
                "generator_config_path": "configs/generator/base.yaml",
                "generator_config_sha256": config_sha256,
                "generator_scale": "medium",
                "section03_candidate_manifest_sha256": candidate_sha256,
                "feature_cutoff_ts": "2026-04-24T23:59:00Z",
                "feature_results": [{"table_name": table, "contract_success": True} for table in seven_tables],
            }
        ),
        encoding="utf-8",
    )
    (run_root / "quality" / "coursework_feature_contract.json").write_text(
        json.dumps({"success": True}), encoding="utf-8"
    )
    class Response:
        def __init__(self, payload: dict[str, object]) -> None:
            self.payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return self.payload

    class Session:
        def __init__(self) -> None:
            self.posts: list[dict[str, object]] = []

        def post(self, _url: str, *, json: dict[str, object], **_kwargs: object) -> Response:
            self.posts.append(json)
            return Response({"dag_run_id": "run-1", "state": "queued"})

        def get(self, url: str, **_kwargs: object) -> Response:
            if url.endswith("/taskInstances"):
                return Response(
                    {
                        "task_instances": [
                            {"task_id": task_id, "state": "success"}
                            for task_id in module.TASK_IDS
                        ]
                    }
                )
            return Response({"dag_run_id": "run-1", "state": "success"})

    session = Session()
    monkeypatch.setattr(module, "COURSEWORK_RUNS_ROOT", runs_root)
    monkeypatch.setattr(module, "_new_run_id", lambda: "run-1")

    result = module.run_section03_dp3(
        candidate_manifest=candidate,
        airflow_url="http://localhost:8082",
        output_root=tmp_path / "output",
        username="airflow",
        password="secret-value",
        session=session,
        sleep=lambda _seconds: None,
        poll_interval_seconds=0,
    )

    assert session.posts[0]["conf"] == {
        "generator_config_path": "configs/generator/base.yaml",
        "generator_scale": "medium",
        "section03_candidate_manifest_sha256": candidate_sha256,
    }
    assert result["status"] == "success"
    output_text = (tmp_path / "output" / "run_manifest.json").read_text(encoding="utf-8")
    assert "secret-value" not in output_text
    task_state_path = tmp_path / "output" / "airflow_task_instances.json"
    assert task_state_path.is_file()
    for relative in module.REQUIRED_ARTIFACTS:
        assert (tmp_path / "output" / relative).read_bytes() == (run_root / relative).read_bytes()
    output_manifest = json.loads(output_text)
    assert {
        "path": "airflow_task_instances.json",
        "size_bytes": task_state_path.stat().st_size,
        "sha256": hashlib.sha256(task_state_path.read_bytes()).hexdigest(),
    } in output_manifest["artifacts"]


def test_section03_wrapper_fails_closed_when_runtime_artifacts_are_stale(monkeypatch, tmp_path) -> None:
    module = _load_section03_wrapper()
    config_path = Path(__file__).resolve().parents[2] / "configs" / "generator" / "base.yaml"
    candidate = tmp_path / "section03_candidate_manifest.json"
    candidate.write_text(
        json.dumps(
            {
                "bundle_id": "b" * 64,
                "source_config_path": "configs/generator/base.yaml",
                "source_config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
                "scale": "medium",
                "random_seed": 42,
                "windows": {
                    "drift_start_ts": "2026-04-11T08:23:00Z",
                    "feature_cutoff_ts": "2026-04-24T23:59:00Z",
                    "label_end_ts": "2026-05-01T23:59:00Z",
                    "baseline_date": "2026-04-10",
                },
            }
        ),
        encoding="utf-8",
    )

    class Response:
        def __init__(self, payload: dict[str, object]) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return self._payload

    class Session:
        def post(self, _url: str, **_kwargs: object) -> Response:
            return Response({"dag_run_id": "run-1", "state": "success"})

        def get(self, url: str, **_kwargs: object) -> Response:
            if url.endswith("/taskInstances"):
                return Response(
                    {
                        "task_instances": [
                            {"task_id": task_id, "state": "success"}
                            for task_id in module.TASK_IDS
                        ]
                    }
                )
            return Response({"dag_run_id": "run-1", "state": "success"})

    monkeypatch.setattr(module, "COURSEWORK_RUNS_ROOT", tmp_path / "missing-runs")
    monkeypatch.setattr(module, "_new_run_id", lambda: "run-1")

    with pytest.raises(RuntimeError, match="artifact"):
        module.run_section03_dp3(
            candidate_manifest=candidate,
            airflow_url="http://localhost:8082",
            output_root=tmp_path / "output",
            username="airflow",
            password="secret-value",
            session=Session(),
            timeout_seconds=0,
            sleep=lambda _seconds: None,
            poll_interval_seconds=0,
        )


def test_section03_wrapper_rejects_stale_cutoff_and_false_table_contract(tmp_path) -> None:
    module = _load_section03_wrapper()
    config_path = Path(__file__).resolve().parents[2] / "configs" / "generator" / "base.yaml"
    run_root = tmp_path / "run"
    (run_root / "quality").mkdir(parents=True)
    (run_root / "spark_features").mkdir()
    for relative in module.REQUIRED_ARTIFACTS:
        artifact_path = run_root / relative
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(json.dumps({"state": "success"}), encoding="utf-8")

    feature_tables = list(module.FEATURE_TABLES)
    expected_parameters = {
        "drift_start_ts": "2026-04-11T08:23:00Z",
        "feature_cutoff_ts": "2026-04-24T23:59:00Z",
        "label_end_ts": "2026-05-01T23:59:00Z",
        "baseline_date": "2026-04-10",
    }
    compute = {
        "state": "success",
        "strict_section03": True,
        "generator_config_path": "configs/generator/base.yaml",
        "generator_config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "generator_scale": "medium",
        "section03_candidate_manifest_sha256": "a" * 64,
        "feature_tables": feature_tables,
        "feature_cutoff_ts": "2026-04-23T23:59:00Z",
        "section03_parameters": {**expected_parameters, "feature_cutoff_ts": "2026-04-23T23:59:00Z"},
    }
    validate = {
        "state": "success",
        "strict_section03": True,
        "contract_success": True,
        "generator_config_path": "configs/generator/base.yaml",
        "generator_config_sha256": compute["generator_config_sha256"],
        "generator_scale": "medium",
        "section03_candidate_manifest_sha256": "a" * 64,
        "feature_cutoff_ts": expected_parameters["feature_cutoff_ts"],
        "feature_results": [{"table_name": table, "contract_success": True} for table in feature_tables],
    }
    (run_root / "dp3_compute.json").write_text(json.dumps(compute), encoding="utf-8")
    (run_root / "dp3_validate.json").write_text(json.dumps(validate), encoding="utf-8")
    (run_root / "quality" / "coursework_feature_contract.json").write_text(
        json.dumps({"success": True}), encoding="utf-8"
    )

    with pytest.raises(RuntimeError, match="cutoff"):
        module._validate_artifacts(
            run_root=run_root,
            candidate_sha256="a" * 64,
            scale="medium",
            config_path="configs/generator/base.yaml",
            expected_section03_parameters=expected_parameters,
        )

    compute["feature_cutoff_ts"] = expected_parameters["feature_cutoff_ts"]
    compute["section03_parameters"] = expected_parameters
    (run_root / "dp3_compute.json").write_text(json.dumps(compute), encoding="utf-8")
    validate["feature_results"][0]["contract_success"] = False
    (run_root / "dp3_validate.json").write_text(json.dumps(validate), encoding="utf-8")

    with pytest.raises(RuntimeError, match="contract"):
        module._validate_artifacts(
            run_root=run_root,
            candidate_sha256="a" * 64,
            scale="medium",
            config_path="configs/generator/base.yaml",
            expected_section03_parameters=expected_parameters,
        )
