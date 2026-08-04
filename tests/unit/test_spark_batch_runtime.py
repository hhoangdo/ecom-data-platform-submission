import importlib.util
import csv
import hashlib
import json
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest

from compose_model import load_compose_model
from vina_bim_shop.lakehouse.spark.constants import DP3_GOLD_TABLES, REQUIRED_GOLD_TABLES
from vina_bim_shop.lakehouse.spark.evidence import DEFAULT_EVIDENCE_ROOT, capture_evidence
from vina_bim_shop.lakehouse.spark.layout_profile import (
    COMPACTION_EVIDENCE_BUCKET_COUNT,
    COMPACTION_EVIDENCE_LAYOUT_PROFILE,
    STANDARD_LAYOUT_PROFILE,
    compaction_evidence_target,
    validate_layout_profile,
)
from vina_bim_shop.lakehouse.spark.parity import compare_keyed_rows, run_parity_checks
from vina_bim_shop.lakehouse.spark.runner import (
    _run_command,
    build_section03_dbt_command,
    build_spark_submit_command,
)
from vina_bim_shop.lakehouse.spark import sql as spark_sql
from vina_bim_shop.lakehouse.spark.sql import (
    Section03SqlParameters,
    ordered_core_gold_queries,
    ordered_feature_queries,
    ordered_gold_queries,
)
from vina_bim_shop.lakehouse.spark.trino import run_gold_smoke_queries
from vina_bim_shop.lakehouse.spark.window import BatchWindow


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _section03_parameters() -> Section03SqlParameters:
    return Section03SqlParameters(
        drift_start_ts="2026-04-11T08:23:00Z",
        feature_cutoff_ts="2026-04-24T23:59:00Z",
        label_end_ts="2026-05-01T23:59:00Z",
        baseline_date="2026-04-10",
        psi_warning=0.1,
        psi_alert=0.15,
    )


def _load_script_module(script_relative_path: str, module_name: str):
    script_path = _repo_root() / script_relative_path
    assert script_path.is_file(), f"Expected script at {script_relative_path}."
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_root_compose_declares_batch_services_and_ui_ports() -> None:
    compose = load_compose_model(_repo_root())

    services = compose["services"]
    expected_services = {"spark-master", "spark-worker", "spark-history-server"}
    assert expected_services.issubset(services)

    for service_name in expected_services:
        assert services[service_name]["profiles"] == ["batch", "all"]

    assert services["spark-master"]["command"] == ["master"]
    assert "8085:8080" in services["spark-master"]["ports"]
    assert services["spark-worker"]["command"] == ["worker"]
    assert "ports" not in services["spark-worker"]
    assert services["spark-history-server"]["command"] == ["history"]
    assert "18080:18080" in services["spark-history-server"]["ports"]
    assert "spark-master" in services["spark-worker"]["depends_on"]
    assert "spark-master" in services["spark-history-server"]["depends_on"]


def test_env_example_documents_spark_batch_urls() -> None:
    env_example = (_repo_root() / ".env.example").read_text(encoding="utf-8")

    for expected_line in [
        "VBS_SPARK_MASTER_URL=spark://spark-master:7077",
        "VBS_SPARK_MASTER_UI_URL=http://localhost:8085",
        "VBS_SPARK_HISTORY_URL=http://localhost:18080",
    ]:
        assert expected_line in env_example


def test_spark_entrypoint_configures_iceberg_minio_and_history_server() -> None:
    entrypoint = (_repo_root() / "infra" / "spark" / "bin" / "entrypoint.sh").read_text(encoding="utf-8")

    expected_lines = [
        "export PYSPARK_PYTHON=python3",
        "export PYSPARK_DRIVER_PYTHON=python3",
        "spark.eventLog.dir s3a://${VBS_CHECKPOINTS_BUCKET:-checkpoints}/spark-events",
        "spark.history.fs.logDirectory s3a://${VBS_CHECKPOINTS_BUCKET:-checkpoints}/spark-events",
        "spark.sql.catalog.iceberg org.apache.iceberg.spark.SparkCatalog",
        "spark.sql.catalog.iceberg.type hive",
        "spark.sql.catalog.iceberg.uri ${VBS_HIVE_METASTORE_INTERNAL_URI:-thrift://hive-metastore:9083}",
        "spark.sql.catalog.iceberg.warehouse s3a://${VBS_SILVER_BUCKET:-silver}/warehouse",
        "spark.hadoop.fs.s3a.endpoint ${VBS_MINIO_INTERNAL_ENDPOINT:-http://minio:9000}",
        "spark.hadoop.fs.s3a.path.style.access true",
        "spark.hadoop.fs.s3a.connection.ssl.enabled false",
        "--webui-port 8080",
        "--webui-port 8081",
        "org.apache.spark.deploy.history.HistoryServer",
    ]
    for expected_line in expected_lines:
        assert expected_line in entrypoint


def test_spark_dockerfile_bundles_iceberg_s3a_and_gx_dependencies() -> None:
    dockerfile = (_repo_root() / "infra" / "spark" / "Dockerfile").read_text(encoding="utf-8")

    for expected_fragment in [
        "FROM apache/spark:4.0.0",
        "iceberg-spark-runtime-4.0_2.13-${ICEBERG_VERSION}.jar",
        "hadoop-aws-${HADOOP_AWS_VERSION}.jar",
        "bundle-${AWS_BUNDLE_VERSION}.jar",
        "python3 -m pip install --no-cache-dir",
        "ln -sf /usr/bin/python3 /usr/local/bin/python",
        "\"great-expectations==1.17.2\"",
        "\"pyarrow==19.0.1\"",
    ]:
        assert expected_fragment in dockerfile


def test_batch_window_normalizes_utc_hourly_ranges() -> None:
    window = BatchWindow.from_args(
        start_ts="2026-06-01T00:00:00+07:00",
        end_ts="2026-06-01T01:00:00+07:00",
        mode="hourly",
    )

    assert window.start_ts.isoformat() == "2026-05-31T17:00:00+00:00"
    assert window.end_ts.isoformat() == "2026-05-31T18:00:00+00:00"
    assert window.to_cli_args() == [
        "--start-ts",
        "2026-05-31T17:00:00Z",
        "--end-ts",
        "2026-05-31T18:00:00Z",
        "--mode",
        "hourly",
    ]


def test_batch_window_rejects_non_hourly_hourly_range() -> None:
    with pytest.raises(ValueError, match="exact one-hour UTC window"):
        BatchWindow.from_args(
            start_ts="2026-06-01T00:00:00Z",
            end_ts="2026-06-01T00:30:00Z",
            mode="hourly",
        )


def test_build_spark_submit_command_uses_containerized_workspace_paths() -> None:
    window = BatchWindow.from_args(
        start_ts="2026-06-01T00:00:00Z",
        end_ts="2026-06-01T01:00:00Z",
        mode="hourly",
    )

    command = build_spark_submit_command(window, evidence_root="evidence/05_spark_batch")

    assert command[:5] == ["docker", "compose", "exec", "-T", "spark-master"]
    command_text = command[-1]
    assert "cd /workspace" in command_text
    assert "PYTHONPATH=/workspace/src spark-submit" in command_text
    assert "scripts/spark/job.py" in command_text
    assert "--conf spark.eventLog.enabled=true" in command_text
    assert "--conf spark.eventLog.dir=s3a://checkpoints/spark-events" in command_text
    assert "--start-ts 2026-06-01T00:00:00Z" in command_text
    assert "--end-ts 2026-06-01T01:00:00Z" in command_text
    assert "--mode hourly" in command_text
    assert "--evidence-root /workspace/evidence/05_spark_batch" in command_text


def test_build_section03_commands_bind_config_scale_and_manifest() -> None:
    window = BatchWindow.from_args(
        start_ts="2026-03-03T23:59:00Z",
        end_ts="2026-05-01T23:59:00Z",
        mode="backfill",
    )

    spark_command = build_spark_submit_command(
        window,
        evidence_root="tmp/section03-runtime/spark",
        generator_config="configs/generator/base.yaml",
        generator_scale="medium",
        section03_manifest="evidence/03_data_generator_improvement/section03_candidate_manifest.json",
    )
    command_text = spark_command[-1]
    assert "--generator-config /workspace/configs/generator/base.yaml" in command_text
    assert "--generator-scale medium" in command_text
    assert "--section03-manifest /workspace/evidence/03_data_generator_improvement/section03_candidate_manifest.json" in command_text

    assert build_section03_dbt_command(
        generator_config="configs/generator/base.yaml",
        generator_scale="medium",
    ) == [
        sys.executable,
        "scripts/analytics/run_section03_dbt.py",
        "--config",
        "configs/generator/base.yaml",
        "--scale",
        "medium",
        "--project-dir",
        "infra/analytics/dbt",
        "--profiles-dir",
        "infra/analytics/dbt",
        "--all-gold",
    ]


def test_spark_stream_query_enforces_the_cutoff_safe_sixty_minute_window() -> None:
    query_map = dict(ordered_feature_queries(_section03_parameters()))
    stream_query = query_map["feat_stream_60m"]

    assert "events.event_timestamp > p.feature_cutoff_ts - interval 60 minutes" in stream_query
    assert "events.event_timestamp <= p.feature_cutoff_ts" in stream_query
    assert "events.created_ts <= p.feature_cutoff_ts" in stream_query


def test_run_command_uses_utf8_with_replacement(monkeypatch) -> None:
    recorded = {}

    def fake_run(command, **kwargs):
        recorded["command"] = command
        recorded["kwargs"] = kwargs
        return "ok"

    monkeypatch.setattr("vina_bim_shop.lakehouse.spark.runner.subprocess.run", fake_run)

    result = _run_command(["echo", "hello"])

    assert result == "ok"
    assert recorded == {
        "command": ["echo", "hello"],
        "kwargs": {
            "check": True,
            "text": True,
            "capture_output": True,
            "encoding": "utf-8",
            "errors": "replace",
        },
    }


def test_capture_evidence_writes_machine_verifiable_manifest(tmp_path: Path) -> None:
    def fake_get_json(url: str):
        if url.endswith("/json/"):
            return {"status": "ALIVE", "workers": 1}
        if url.endswith("/api/v1/applications"):
            return [{"id": "app-001", "name": "vina-bim-shop-batch"}]
        raise AssertionError(f"Unexpected URL: {url}")

    manifest = capture_evidence(
        evidence_root=tmp_path,
        master_url="http://localhost:8085",
        history_url="http://localhost:18080",
        get_json=fake_get_json,
    )

    assert DEFAULT_EVIDENCE_ROOT == Path("evidence/05_spark_batch")
    assert json.loads((tmp_path / "spark_master_status.json").read_text(encoding="utf-8"))["status"] == "ALIVE"
    assert json.loads((tmp_path / "spark_history_applications.json").read_text(encoding="utf-8"))[0]["id"] == "app-001"
    assert "spark_master_status.json" in manifest["artifacts"]
    assert not (tmp_path / "screenshots").exists()
    assert all(not artifact.startswith("screenshots/") for artifact in manifest["artifacts"])


def test_capture_evidence_includes_optimization_manifest_when_present(tmp_path: Path) -> None:
    optimization = tmp_path / "optimization"
    optimization.mkdir()
    (optimization / "run_manifest.json").write_text("{}", encoding="utf-8")

    def fake_get_json(url: str):
        if url.endswith("/json/"):
            return {"status": "ALIVE"}
        if url.endswith("/api/v1/applications"):
            return []
        raise AssertionError(f"Unexpected URL: {url}")

    manifest = capture_evidence(evidence_root=tmp_path, get_json=fake_get_json)

    assert "optimization/run_manifest.json" in manifest["artifacts"]


def test_run_gold_smoke_queries_writes_results_artifact(tmp_path: Path, monkeypatch) -> None:
    calls = []

    def fake_execute_trino_query(query: str, *, trino_url: str, user: str):
        calls.append((query, trino_url, user))
        return {"query": query, "columns": ["value"], "rows": [[1]], "stats": {}}

    monkeypatch.setattr("vina_bim_shop.lakehouse.spark.trino.execute_trino_query", fake_execute_trino_query)
    results = run_gold_smoke_queries(evidence_root=tmp_path, trino_url="http://localhost:8080", user="vina_analyst")

    assert set(results) == {
        "gold_inventory",
        "fact_order_count",
        "fact_order_paid_revenue",
        "hourly_kpi_sample",
    }
    assert len(calls) == 4
    assert json.loads((tmp_path / "trino_gold_smoke_results.json").read_text(encoding="utf-8"))["fact_order_count"]["rows"] == [[1]]


def test_execute_trino_query_preserves_column_metadata() -> None:
    from vina_bim_shop.lakehouse.spark.trino import execute_trino_query

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "columns": [
                    {"name": "table_name", "type": "varchar"},
                    {"name": "row_count", "type": "bigint"},
                ],
                "data": [["fact_order", 1800]],
                "stats": {"state": "FINISHED"},
            }

    result = execute_trino_query(
        "select * from iceberg.gold.fact_order",
        trino_url="http://localhost:8080",
        user="vina_analyst",
        post=lambda *args, **kwargs: FakeResponse(),
    )

    assert result["columns"] == ["table_name", "row_count"]
    assert result["column_metadata"] == [
        {"name": "table_name", "type": "varchar"},
        {"name": "row_count", "type": "bigint"},
    ]


def test_export_executive_mart_copies_all_gold_tables_from_trino(tmp_path: Path) -> None:
    import duckdb

    from vina_bim_shop.lakehouse.spark.executive_mart import export_executive_mart

    duckdb_path = tmp_path / "vina_bim_shop_executive.duckdb"
    evidence_root = tmp_path / "evidence"
    calls = []

    def fake_execute_query(query: str, *, trino_url: str, user: str):
        table_name = query.rsplit("iceberg.gold.", 1)[1].strip()
        calls.append((table_name, trino_url, user))
        return {
            "query": query,
            "columns": ["table_name", "row_number"],
            "column_metadata": [
                {"name": "table_name", "type": "varchar"},
                {"name": "row_number", "type": "bigint"},
            ],
            "rows": [[table_name, 1]],
            "stats": {"state": "FINISHED"},
        }

    manifest = export_executive_mart(
        duckdb_path=duckdb_path,
        evidence_root=evidence_root,
        trino_url="http://trino:8080",
        user="vina_analyst",
        execute_query=fake_execute_query,
        exported_at="2026-06-06T00:00:00+00:00",
    )

    assert duckdb_path.is_file()
    assert manifest["duckdb_path"] == str(duckdb_path)
    assert manifest["table_count"] == len(REQUIRED_GOLD_TABLES)
    assert manifest["total_row_count"] == len(REQUIRED_GOLD_TABLES)
    assert [call[0] for call in calls] == list(REQUIRED_GOLD_TABLES)

    with duckdb.connect(str(duckdb_path), read_only=True) as connection:
        gold_table_count = connection.execute(
            """
            select count(*)
            from information_schema.tables
            where table_schema = 'gold'
            """
        ).fetchone()[0]
        metadata_table_count = connection.execute("select count(*) from mart_metadata.table_manifest").fetchone()[0]
        fact_order_rows = connection.execute("select table_name, row_number from gold.fact_order").fetchall()

    assert gold_table_count == len(REQUIRED_GOLD_TABLES)
    assert metadata_table_count == len(REQUIRED_GOLD_TABLES)
    assert fact_order_rows == [("fact_order", 1)]
    assert (evidence_root / "executive_mart_export_manifest.json").is_file()
    assert "DuckDB Executive Mart Export Report" in (
        evidence_root / "executive_mart_export_report.md"
    ).read_text(encoding="utf-8")


def test_export_executive_mart_script_parses_args_and_prints_summary(monkeypatch, capsys, tmp_path: Path) -> None:
    module = _load_script_module("scripts/spark/export_executive_mart.py", "export_executive_mart_script")

    duckdb_path = tmp_path / "executive.duckdb"
    evidence_root = tmp_path / "evidence"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "export_executive_mart.py",
            "--duckdb-path",
            str(duckdb_path),
            "--evidence-root",
            str(evidence_root),
        ],
    )
    args = module.parse_args()
    assert args.duckdb_path == str(duckdb_path)
    assert args.evidence_root == str(evidence_root)

    calls = []

    def fake_export_executive_mart(**kwargs):
        calls.append(kwargs)
        return {"duckdb_path": str(duckdb_path), "table_count": 22, "total_row_count": 123}

    monkeypatch.setattr(module, "export_executive_mart", fake_export_executive_mart)
    module.main()

    assert calls == [{"duckdb_path": str(duckdb_path), "evidence_root": str(evidence_root)}]
    assert capsys.readouterr().out.strip() == (
        f"Exported 22 Gold tables and 123 rows to {duckdb_path}."
    )


def test_run_parity_checks_writes_json_and_markdown_reports(tmp_path: Path, monkeypatch) -> None:
    duckdb_path = tmp_path / "vina_bim_shop.duckdb"
    import duckdb

    connection = duckdb.connect(str(duckdb_path))
    connection.execute("create schema gold")
    for table_name in REQUIRED_GOLD_TABLES:
        if table_name == "fact_order":
            connection.execute(
                "create table gold.fact_order (official_paid_revenue double, gross_merchandise_value double)"
            )
        elif table_name == "fact_order_item":
            connection.execute("create table gold.fact_order_item (estimated_cost double, estimated_margin double)")
        elif table_name == "agg_hourly_reconciled_kpi":
            connection.execute("create table gold.agg_hourly_reconciled_kpi (official_paid_revenue double)")
        elif table_name == "ml_customer_label":
            connection.execute("create table gold.ml_customer_label (id varchar, label integer)")
        elif table_name == "ml_customer_purchase_training":
            connection.execute(
                "create table gold.ml_customer_purchase_training (id varchar, event_timestamp timestamp, label integer, f_customer_paid_revenue_90d double, f_customer_avg_order_value_90d double, f_stream_cart_to_purchase_ratio_60m double)"
            )
        elif table_name == "agg_feature_health_daily":
            connection.execute(
                "create table gold.agg_feature_health_daily (monitoring_date date, feature_name varchar, mean_value double, stddev_value double, psi_vs_baseline double)"
            )
        elif table_name == "feature_drift_alerts":
            connection.execute(
                "create table gold.feature_drift_alerts (alert_date date, feature_name varchar, psi_value double, threshold double)"
            )
        else:
            connection.execute(f"create table gold.{table_name} (dummy integer)")
    connection.close()

    def fake_execute_trino_query(query: str, *, trino_url: str, user: str):
        scalar = None if "sum(" in query.lower() else 0
        if "select *" in query.lower():
            return {"query": query, "columns": [], "rows": [], "stats": {}}
        return {"query": query, "columns": ["value"], "rows": [[scalar]], "stats": {}}

    monkeypatch.setattr("vina_bim_shop.lakehouse.spark.parity.execute_trino_query", fake_execute_trino_query)
    report = run_parity_checks(
        evidence_root=tmp_path,
        duckdb_path=duckdb_path,
        trino_url="http://localhost:8080",
        user="vina_analyst",
    )

    assert report["success"] is True
    assert (tmp_path / "dbt_parity_report.json").is_file()
    assert (tmp_path / "dbt_parity_report.md").is_file()
    assert "Overall success: PASS" in (tmp_path / "dbt_parity_report.md").read_text(encoding="utf-8")


def test_section03_parity_binds_manifest_and_reports_all_keyed_families(tmp_path: Path, monkeypatch) -> None:
    import duckdb

    rows = {
        "ml_customer_label": [{"id": "c-001", "label": "1"}],
        "ml_customer_purchase_training": [
            {
                "id": "c-001",
                "event_timestamp": "2026-04-24T23:59:00Z",
                "label": "1",
                "f_customer_total_orders_90d": "2",
                "f_customer_paid_revenue_90d": "42.125000000000",
                "f_customer_avg_order_value_90d": "21.062500000000",
                "f_customer_distinct_categories_90d": "1",
                "f_stream_views_60m": "3",
                "f_stream_add_to_cart_60m": "2",
                "f_stream_checkout_started_60m": "1",
                "f_stream_order_placed_60m": "1",
                "f_stream_cart_to_purchase_ratio_60m": "0.500000000000",
                "created": "2026-04-24T23:59:00Z",
            }
        ],
        "agg_feature_health_daily": [
            {
                "monitoring_date": "2026-04-10",
                "feature_name": "f_customer_order_frequency_7d",
                "window_days": "7",
                "baseline_date": "2026-04-10",
                "customer_count": "1",
                "mean_value": "0.000000000000",
                "stddev_value": "0.000000000000",
                "psi_vs_baseline": "0.000000000000",
                "drift_status": "stable",
                "warning_flag": "false",
                "alert_flag": "false",
            }
        ],
        "feature_drift_alerts": [
            {
                "alert_date": "2026-04-10",
                "feature_name": "f_customer_order_frequency_7d",
                "psi_value": "0.150000000000",
                "threshold": "0.150000000000",
                "action": "Investigate customer_order_frequency drift",
            }
        ],
    }
    manifest_root = tmp_path / "manifest-root"
    bundle_root = manifest_root / "runs" / "test-bundle"
    bundle_root.mkdir(parents=True)
    artifacts = {}
    for artifact_key, table_name in {
        "labels": "ml_customer_label",
        "training_join": "ml_customer_purchase_training",
        "feature_health_daily": "agg_feature_health_daily",
        "drift_alerts": "feature_drift_alerts",
    }.items():
        path = bundle_root / f"{table_name}.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[table_name][0]))
            writer.writeheader()
            writer.writerows(rows[table_name])
        artifacts[artifact_key] = {
            "path": path.relative_to(manifest_root).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    config_path = _repo_root() / "configs" / "generator" / "base.yaml"
    manifest = manifest_root / "section03_candidate_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "source_config_path": "configs/generator/base.yaml",
                "source_config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
                "bundle_id": "test-bundle",
                "artifacts": artifacts,
            }
        ),
        encoding="utf-8",
    )

    duckdb_path = tmp_path / "vina_bim_shop.duckdb"
    connection = duckdb.connect(str(duckdb_path))
    connection.execute("create schema gold")
    for table_name in REQUIRED_GOLD_TABLES:
        if table_name == "fact_order":
            connection.execute(
                "create table gold.fact_order (official_paid_revenue double, gross_merchandise_value double)"
            )
        elif table_name == "fact_order_item":
            connection.execute("create table gold.fact_order_item (estimated_cost double, estimated_margin double)")
        elif table_name == "agg_hourly_reconciled_kpi":
            connection.execute("create table gold.agg_hourly_reconciled_kpi (official_paid_revenue double)")
        elif table_name == "ml_customer_label":
            connection.execute("create table gold.ml_customer_label (id varchar, label integer)")
            connection.execute("insert into gold.ml_customer_label values ('c-001', 1)")
        elif table_name == "ml_customer_purchase_training":
            connection.execute(
                "create table gold.ml_customer_purchase_training (id varchar, event_timestamp timestamp, label integer, f_customer_total_orders_90d integer, f_customer_paid_revenue_90d double, f_customer_avg_order_value_90d double, f_customer_distinct_categories_90d integer, f_stream_views_60m integer, f_stream_add_to_cart_60m integer, f_stream_checkout_started_60m integer, f_stream_order_placed_60m integer, f_stream_cart_to_purchase_ratio_60m double, created timestamp)"
            )
            connection.execute(
                "insert into gold.ml_customer_purchase_training values ('c-001', '2026-04-24 23:59:00', 1, 2, 42.125, 21.0625, 1, 3, 2, 1, 1, 0.5, '2026-04-24 23:59:00')"
            )
        elif table_name == "agg_feature_health_daily":
            connection.execute(
                "create table gold.agg_feature_health_daily (monitoring_date date, feature_name varchar, window_days integer, baseline_date date, customer_count bigint, mean_value double, stddev_value double, psi_vs_baseline double, drift_status varchar, warning_flag boolean, alert_flag boolean)"
            )
            connection.execute(
                "insert into gold.agg_feature_health_daily values ('2026-04-10', 'f_customer_order_frequency_7d', 7, '2026-04-10', 1, 0, 0, 0, 'stable', false, false)"
            )
        elif table_name == "feature_drift_alerts":
            connection.execute(
                "create table gold.feature_drift_alerts (alert_date date, feature_name varchar, psi_value double, threshold double, action varchar)"
            )
            connection.execute(
                "insert into gold.feature_drift_alerts values ('2026-04-10', 'f_customer_order_frequency_7d', 0.15, 0.15, 'Investigate customer_order_frequency drift')"
            )
        else:
            connection.execute(f"create table gold.{table_name} (dummy integer)")
    connection.close()

    def fake_execute_trino_query(query: str, *, trino_url: str, user: str):
        lower = query.lower()
        if "select * from iceberg.gold." in lower:
            table_name = query.rsplit("iceberg.gold.", 1)[1].strip()
            return {
                "query": query,
                "columns": list(rows[table_name][0]) if table_name in rows else [],
                "rows": [list(row.values()) for row in rows.get(table_name, [])],
                "stats": {},
            }
        if "sum(" in lower:
            return {"query": query, "columns": ["value"], "rows": [[None]], "stats": {}}
        table_name = query.rsplit("iceberg.gold.", 1)[1].strip()
        return {"query": query, "columns": ["value"], "rows": [[len(rows.get(table_name, []))]], "stats": {}}

    monkeypatch.setattr("vina_bim_shop.lakehouse.spark.parity.execute_trino_query", fake_execute_trino_query)
    report = run_parity_checks(
        evidence_root=tmp_path / "evidence",
        duckdb_path=duckdb_path,
        trino_url="http://localhost:8080",
        user="vina_analyst",
        section03_manifest=manifest,
        generator_config="configs/generator/base.yaml",
        generator_scale="medium",
        dbt_command=["python", "scripts/analytics/run_section03_dbt.py"],
        spark_command=["docker", "compose", "exec"],
    )

    assert report["success"] is True
    assert report["section03_manifest"]["source_config_sha256"] == hashlib.sha256(config_path.read_bytes()).hexdigest()
    assert all(
        item["mismatch_count"] == 0
        for family in ("generator_vs_dbt", "generator_vs_spark", "dbt_vs_spark")
        for item in report["keyed_comparisons"][family]
    )


@pytest.mark.parametrize(
    ("table_name", "key_columns", "rows"),
    [
        ("ml_customer_label", ("id",), [{"id": "c-001", "label": 1}]),
        (
            "ml_customer_purchase_training",
            ("id",),
            [{"id": "c-001", "label": 1, "f": 12.345678901234}],
        ),
        (
            "agg_feature_health_daily",
            ("monitoring_date", "feature_name"),
            [{"monitoring_date": "2026-04-10", "feature_name": "f_customer_order_frequency_7d", "psi": 0.1}],
        ),
        (
            "feature_drift_alerts",
            ("alert_date", "feature_name"),
            [{"alert_date": "2026-04-10", "feature_name": "f_customer_order_frequency_7d", "action": "Investigate"}],
        ),
    ],
)
def test_keyed_full_row_comparison_requires_exact_keys_and_tolerates_only_rounded_floats(
    table_name: str,
    key_columns: tuple[str, ...],
    rows: list[dict[str, object]],
) -> None:
    matching = [dict(row) for row in rows]
    for row in matching:
        if "f" in row:
            row["f"] = float(row["f"]) + 5e-13

    result = compare_keyed_rows(
        table_name=table_name,
        expected_rows=rows,
        actual_rows=matching,
        key_columns=key_columns,
    )
    assert result["mismatch_count"] == 0
    assert result["missing_key_count"] == 0
    assert result["extra_key_count"] == 0

    changed = [dict(row) for row in rows]
    changed[0][key_columns[0]] = "c-002" if key_columns[0] == "id" else "2026-04-11"
    mismatch = compare_keyed_rows(
        table_name=table_name,
        expected_rows=rows,
        actual_rows=changed,
        key_columns=key_columns,
    )
    assert mismatch["mismatch_count"] >= 1
    assert mismatch["missing_key_count"] == 1
    assert mismatch["extra_key_count"] == 1


def test_required_gold_table_inventory_matches_adr03_scope() -> None:
    assert len(REQUIRED_GOLD_TABLES) == len(set(REQUIRED_GOLD_TABLES))
    assert REQUIRED_GOLD_TABLES == (
        "dim_customer",
        "dim_seller",
        "dim_product",
        "dim_category",
        "dim_date",
        "dim_payment_method",
        "dim_order_status",
        "dim_shipment_status",
        "dim_shipping_method",
        "dim_promotion",
        "bridge_product_category",
        "fact_order",
        "fact_order_item",
        "fact_payment_attempt",
        "fact_shipment",
        "fact_inventory_snapshot",
        "fact_promotion_application",
        "obt_order_performance",
        "agg_hourly_reconciled_kpi",
        "feat_customer_90d",
        "feat_stream_60m",
        "feat_customer_unified",
        "ml_customer_label",
        "agg_feature_health_daily",
        "feature_drift_alerts",
        "ml_customer_purchase_training",
    )
    assert DP3_GOLD_TABLES == (
        "feat_customer_90d",
        "feat_stream_60m",
        "feat_customer_unified",
        "ml_customer_label",
        "agg_feature_health_daily",
        "feature_drift_alerts",
        "ml_customer_purchase_training",
    )


def test_spark_feature_queries_expose_created_output_contract() -> None:
    queries = dict(ordered_gold_queries(_section03_parameters()))

    assert "feature_cutoff_ts" in queries["feat_customer_90d"]
    assert "max(fo.created_ts) as created" not in queries["feat_customer_90d"]
    assert "created_ts <=" in queries["feat_customer_90d"]

    assert "max(created_ts) as created" in queries["feat_stream_60m"]
    assert "date_trunc('hour', event_timestamp) as event_timestamp" in queries["feat_stream_60m"]
    assert "group by customer_id, date_trunc('hour', event_timestamp)" in queries["feat_stream_60m"]
    assert "event_timestamp <=" in queries["feat_stream_60m"]
    assert "created_ts <=" in queries["feat_stream_60m"]

    assert "cast(p.feature_cutoff_ts as timestamp) as created" in queries["feat_customer_unified"]
    assert "partition by customer_id" in queries["feat_customer_unified"]
    assert "order by event_timestamp desc, created desc" in queries["feat_customer_unified"]
    assert "greatest(c.created, coalesce(s.created, c.created))" not in queries["feat_customer_unified"]


def test_section03_queries_are_ordered_and_cutoff_safe() -> None:
    parameters = _section03_parameters()
    feature_queries = ordered_feature_queries(parameters)
    query_map = dict(feature_queries)

    assert [name for name, _query in feature_queries] == list(DP3_GOLD_TABLES)
    assert [name for name, _query in ordered_core_gold_queries()] + [
        name for name, _query in feature_queries
    ] == list(REQUIRED_GOLD_TABLES)
    assert not set(name for name, _query in ordered_core_gold_queries()) & set(DP3_GOLD_TABLES)

    for query in query_map.values():
        assert parameters.feature_cutoff_ts in query
        assert "2026-03-03" not in query
        assert "2026-05-01" in query or "2026-04-10" in query

    offline = query_map["feat_customer_90d"]
    assert "customer.created_ts <=" in offline
    assert "orders.order_timestamp >" in offline
    assert "orders.order_timestamp <=" in offline
    assert "payment.is_payment_success" in offline
    assert "payment.payment_timestamp <=" in offline
    assert "payment.created_ts <=" in offline

    stream = query_map["feat_stream_60m"]
    assert "events.event_timestamp <=" in stream
    assert "events.created_ts <=" in stream

    unified = query_map["feat_customer_unified"]
    assert "order by event_timestamp desc, created desc" in unified
    assert "cast(p.feature_cutoff_ts as timestamp) as event_timestamp" in unified

    label = query_map["ml_customer_label"]
    assert "customer.created_ts <=" in label
    assert "payment.payment_timestamp >" in label
    assert "payment.payment_timestamp <=" in label
    assert "payment.created_ts <=" in label
    assert "select\n  cast(customer.id as string) as id,\n  cast(case" in label
    assert "label_timestamp" not in label

    health = query_map["agg_feature_health_daily"]
    assert "customer.created_ts < cast(p.baseline_date as timestamp) + interval 1 day" in health
    assert "p.window_days - 1" in health
    assert "row_number() over (order by feature_value, customer_id) - 1" in health
    assert "floor(position.position)" in health
    assert "select distinct" in health
    assert "edge.edge < counts.feature_value" in health
    assert "p.psi_epsilon" in health
    assert "sum(smoothed_probability) over" in health
    assert "bround(psi.psi_value, 12)" in health
    assert "psi_vs_baseline >= psi_alert" in health
    assert "psi_vs_baseline >= psi_warning" in health

    alerts = query_map["feature_drift_alerts"]
    assert "health.psi_vs_baseline >= p.psi_alert" in alerts
    assert "Investigate customer_order_frequency drift" in alerts

    training = query_map["ml_customer_purchase_training"]
    assert "from ml_customer_label label" in training
    assert "join feat_customer_unified features" in training
    assert training.index("label.id") < training.index("features.event_timestamp")


def test_compaction_evidence_layout_profile_is_two_bucket_and_targeted() -> None:
    assert STANDARD_LAYOUT_PROFILE == "standard"
    assert COMPACTION_EVIDENCE_LAYOUT_PROFILE == "compaction-evidence"
    assert COMPACTION_EVIDENCE_BUCKET_COUNT == 2
    assert compaction_evidence_target("fact_order") == ("order_id", "order_date_key")
    assert compaction_evidence_target("fact_order_item") == ("order_item_id", "order_date_key")
    assert compaction_evidence_target("dim_customer") is None

    with pytest.raises(ValueError, match="Unsupported Spark layout profile"):
        validate_layout_profile("small-files")


def test_canonical_job_exposes_the_opt_in_compaction_evidence_profile() -> None:
    source = (_repo_root() / "src" / "vina_bim_shop" / "lakehouse" / "spark" / "job.py").read_text(
        encoding="utf-8"
    )

    assert '"--layout-profile"' in source
    assert "COMPACTION_EVIDENCE_LAYOUT_PROFILE" in source
    assert "repartitionByRange" in source
    assert "spark.sql.iceberg.distribution-mode" in source
    assert "compaction_layout_manifest.json" in source
    assert "layout_profile=args.layout_profile" in source


def test_gold_query_groups_partition_the_existing_combined_contract() -> None:
    assert hasattr(spark_sql, "ordered_core_gold_queries")
    assert hasattr(spark_sql, "ordered_feature_queries")

    core = spark_sql.ordered_core_gold_queries()
    features = spark_sql.ordered_feature_queries(_section03_parameters())

    assert core + features == ordered_gold_queries(_section03_parameters())
    assert [name for name, _query in features] == [
        "feat_customer_90d",
        "feat_stream_60m",
        "feat_customer_unified",
        "ml_customer_label",
        "agg_feature_health_daily",
        "feature_drift_alerts",
        "ml_customer_purchase_training",
    ]
    assert all(not name.startswith("feat_") for name, _query in core)
    assert len({name for name, _query in core + features}) == len(core + features)


def test_spark_batch_smoke_sql_reads_gold_tables_only() -> None:
    smoke_sql = (_repo_root() / "infra" / "lakehouse" / "trino" / "sql" / "spark_batch_smoke.sql").read_text(
        encoding="utf-8"
    )

    assert "SHOW TABLES FROM iceberg.gold" in smoke_sql
    assert "iceberg.gold.fact_order" in smoke_sql
    assert "iceberg.gold.agg_hourly_reconciled_kpi" in smoke_sql
    assert "INSERT INTO" not in smoke_sql
    assert "CREATE TABLE" not in smoke_sql
    assert "DROP TABLE" not in smoke_sql


def test_run_batch_script_parses_args_and_prints_summary(monkeypatch, capsys, tmp_path: Path) -> None:
    module = _load_script_module("scripts/spark/run_batch.py", "run_batch_script")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_batch.py",
            "--start-ts",
            "2026-06-01T00:00:00Z",
            "--end-ts",
            "2026-06-01T01:00:00Z",
            "--mode",
            "hourly",
            "--evidence-root",
            str(tmp_path),
        ],
    )
    args = module.parse_args()
    assert args.start_ts == "2026-06-01T00:00:00Z"
    assert args.end_ts == "2026-06-01T01:00:00Z"
    assert args.mode == "hourly"
    assert args.evidence_root == str(tmp_path)

    calls = []

    def fake_run_batch_pipeline(**kwargs):
        calls.append(kwargs)
        return {
            "window": {
                "start_ts": kwargs["start_ts"],
                "end_ts": kwargs["end_ts"],
                "mode": kwargs["mode"],
            }
        }

    monkeypatch.setattr(module, "run_batch_pipeline", fake_run_batch_pipeline)
    module.main()

    assert calls == [
            {
                "start_ts": "2026-06-01T00:00:00Z",
                "end_ts": "2026-06-01T01:00:00Z",
                "mode": "hourly",
                "generator_config": "configs/generator/base.yaml",
                "generator_scale": "medium",
                "section03_manifest": None,
                "evidence_root": str(tmp_path),
            }
    ]
    assert capsys.readouterr().out.strip() == (
        "Spark batch completed for 2026-06-01T00:00:00Z -> 2026-06-01T01:00:00Z (hourly)."
    )


def test_run_batch_script_forwards_section03_runtime_contract(monkeypatch, capsys, tmp_path: Path) -> None:
    module = _load_script_module("scripts/spark/run_batch.py", "run_batch_section03_script")
    manifest = tmp_path / "section03_candidate_manifest.json"
    manifest.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_batch.py",
            "--start-ts",
            "2026-03-03T23:59:00Z",
            "--end-ts",
            "2026-05-01T23:59:00Z",
            "--mode",
            "backfill",
            "--generator-config",
            "configs/generator/base.yaml",
            "--generator-scale",
            "medium",
            "--section03-manifest",
            str(manifest),
            "--evidence-root",
            str(tmp_path / "evidence"),
        ],
    )
    args = module.parse_args()
    assert args.generator_config == "configs/generator/base.yaml"
    assert args.generator_scale == "medium"
    assert args.section03_manifest == str(manifest)

    calls = []

    def fake_run_batch_pipeline(**kwargs):
        calls.append(kwargs)
        return {
            "window": {
                "start_ts": kwargs["start_ts"],
                "end_ts": kwargs["end_ts"],
                "mode": kwargs["mode"],
            }
        }

    monkeypatch.setattr(module, "run_batch_pipeline", fake_run_batch_pipeline)
    module.main()

    assert calls == [
        {
            "start_ts": "2026-03-03T23:59:00Z",
            "end_ts": "2026-05-01T23:59:00Z",
            "mode": "backfill",
            "generator_config": "configs/generator/base.yaml",
            "generator_scale": "medium",
            "section03_manifest": str(manifest),
            "evidence_root": str(tmp_path / "evidence"),
        }
    ]
    assert capsys.readouterr().out.strip() == (
        "Spark batch completed for 2026-03-03T23:59:00Z -> 2026-05-01T23:59:00Z (backfill)."
    )


def test_section03_runtime_rejects_explicit_window_mismatch(tmp_path: Path) -> None:
    from vina_bim_shop.lakehouse.spark.runner import run_batch_pipeline

    with pytest.raises(ValueError, match="does not match the config-derived"):
        run_batch_pipeline(
            start_ts="2026-03-04T23:59:00Z",
            end_ts="2026-05-01T23:59:00Z",
            mode="backfill",
            generator_config="configs/generator/base.yaml",
            generator_scale="medium",
            section03_manifest="evidence/03_data_generator_improvement/section03_candidate_manifest.json",
            evidence_root=tmp_path,
            run_command=lambda _command: pytest.fail("window validation must happen before subprocess execution"),
        )


def test_run_batch_pipeline_accepts_custom_capture_evidence_function(monkeypatch, tmp_path: Path) -> None:
    from vina_bim_shop.lakehouse.spark.runner import run_batch_pipeline

    commands = []
    captured = {}

    def fake_run_command(command):
        commands.append(command)
        return SimpleNamespace(stdout="ok")

    def fake_run_parity_checks(*, evidence_root):
        assert Path(evidence_root) == tmp_path
        return {"success": True}

    def fake_run_gold_smoke_queries(*, evidence_root):
        assert Path(evidence_root) == tmp_path
        return {"fact_order_count": {"rows": [[1]]}}

    def fake_export_executive_mart(*, evidence_root):
        assert Path(evidence_root) == tmp_path
        return {
            "duckdb_path": "data/gold/vina_bim_shop_executive.duckdb",
            "table_count": len(REQUIRED_GOLD_TABLES),
            "total_row_count": 123,
        }

    def fake_capture_evidence_fn(*, evidence_root):
        captured["evidence_root"] = Path(evidence_root)
        return {"artifacts": ["run_manifest.json"]}

    monkeypatch.setattr("vina_bim_shop.lakehouse.spark.runner.run_parity_checks", fake_run_parity_checks)
    monkeypatch.setattr("vina_bim_shop.lakehouse.spark.runner.run_gold_smoke_queries", fake_run_gold_smoke_queries)
    monkeypatch.setattr("vina_bim_shop.lakehouse.spark.runner.export_executive_mart", fake_export_executive_mart)

    summary = run_batch_pipeline(
        start_ts="2026-06-01T00:00:00Z",
        end_ts="2026-06-01T01:00:00Z",
        mode="hourly",
        evidence_root=tmp_path,
        run_command=fake_run_command,
        capture_evidence_fn=fake_capture_evidence_fn,
    )

    assert len(commands) == 2
    assert captured["evidence_root"] == tmp_path
    assert summary["evidence_artifact_count"] == 1
    assert summary["executive_mart"] == {
        "duckdb_path": "data/gold/vina_bim_shop_executive.duckdb",
        "table_count": len(REQUIRED_GOLD_TABLES),
        "total_row_count": 123,
    }


def test_run_batch_pipeline_forwards_strict_section03_contract(monkeypatch, tmp_path: Path) -> None:
    from vina_bim_shop.lakehouse.spark.runner import run_batch_pipeline

    commands = []
    parity_calls = []

    def fake_run_command(command):
        commands.append(command)
        return SimpleNamespace(stdout="ok")

    def fake_run_parity_checks(**kwargs):
        parity_calls.append(kwargs)
        return {"success": True}

    def fake_run_gold_smoke_queries(*, evidence_root):
        return {"fact_order_count": {"rows": [[1]]}}

    def fake_export_executive_mart(*, evidence_root):
        return {
            "duckdb_path": "data/gold/vina_bim_shop_executive.duckdb",
            "table_count": len(REQUIRED_GOLD_TABLES),
            "total_row_count": 123,
        }

    monkeypatch.setattr("vina_bim_shop.lakehouse.spark.runner.run_parity_checks", fake_run_parity_checks)
    monkeypatch.setattr("vina_bim_shop.lakehouse.spark.runner.run_gold_smoke_queries", fake_run_gold_smoke_queries)
    monkeypatch.setattr("vina_bim_shop.lakehouse.spark.runner.export_executive_mart", fake_export_executive_mart)

    summary = run_batch_pipeline(
        start_ts="2026-03-03T23:59:00Z",
        end_ts="2026-05-01T23:59:00Z",
        mode="backfill",
        generator_config="configs/generator/base.yaml",
        generator_scale="medium",
        section03_manifest="evidence/03_data_generator_improvement/section03_candidate_manifest.json",
        evidence_root=tmp_path,
        run_command=fake_run_command,
        capture_evidence_fn=lambda *, evidence_root: {"artifacts": []},
    )

    assert len(commands) == 2
    assert "--generator-config /workspace/configs/generator/base.yaml" in commands[0][-1]
    assert "--generator-scale medium" in commands[0][-1]
    assert "--section03-manifest /workspace/evidence/03_data_generator_improvement/section03_candidate_manifest.json" in commands[0][-1]
    assert commands[1][1:2] == ["scripts/analytics/run_section03_dbt.py"]
    assert parity_calls == [
        {
            "evidence_root": tmp_path,
            "section03_manifest": "evidence/03_data_generator_improvement/section03_candidate_manifest.json",
            "generator_config": "configs/generator/base.yaml",
            "generator_scale": "medium",
            "dbt_command": commands[1],
            "spark_command": commands[0],
        }
    ]
    assert summary["generator_scale"] == "medium"
