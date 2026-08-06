from __future__ import annotations

import csv
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
from typing import Any, Iterable

from vina_bim_shop.lakehouse.spark.constants import REQUIRED_GOLD_TABLES
from vina_bim_shop.lakehouse.spark.trino import execute_trino_query


KEYED_COMPARISON_KEYS = {
    "ml_customer_label": ("id",),
    "ml_customer_purchase_training": ("id",),
    "agg_feature_health_daily": ("monitoring_date", "feature_name"),
    "feature_drift_alerts": ("alert_date", "feature_name"),
}
FLOAT_COLUMNS = {
    "ml_customer_purchase_training": {
        "f_customer_paid_revenue_90d",
        "f_customer_avg_order_value_90d",
        "f_stream_cart_to_purchase_ratio_60m",
    },
    "agg_feature_health_daily": {"mean_value", "stddev_value", "psi_vs_baseline"},
    "feature_drift_alerts": {"psi_value", "threshold"},
}


def _load_duckdb() -> Any:
    try:
        return importlib.import_module("duckdb")
    except ModuleNotFoundError as exc:
        raise RuntimeError("DuckDB parity checks require project dependencies; run via `uv run`.") from exc


def _duckdb_scalar(connection: Any, query: str) -> Any:
    return connection.execute(query).fetchone()[0]


def _trino_scalar(query: str, *, trino_url: str, user: str) -> Any:
    result = execute_trino_query(query, trino_url=trino_url, user=user)
    if not result["rows"]:
        return None
    return result["rows"][0][0]


def _duckdb_rows(connection: Any, table_name: str) -> list[dict[str, Any]]:
    cursor = connection.execute(f"select * from gold.{table_name}")
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def _trino_rows(table_name: str, *, trino_url: str, user: str) -> list[dict[str, Any]]:
    result = execute_trino_query(
        f"select * from iceberg.gold.{table_name}",
        trino_url=trino_url,
        user=user,
    )
    columns = result.get("columns", [])
    return [dict(zip(columns, row, strict=True)) for row in result.get("rows", [])]


def _round_half_even_12(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.000000000001"), rounding=ROUND_HALF_EVEN))


def _normalise_scalar(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.isoformat() + "Z"
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        timestamp = value.strip()
        if timestamp.endswith(" UTC"):
            timestamp = timestamp[:-4] + "+00:00"
        elif timestamp.endswith("Z"):
            timestamp = timestamp[:-1] + "+00:00"
        else:
            return value
        try:
            parsed = datetime.fromisoformat(timestamp)
        except ValueError:
            return value
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return value


def _looks_like_float(column: str, expected: Any, actual: Any) -> bool:
    return (
        column in {name for names in FLOAT_COLUMNS.values() for name in names}
        or isinstance(expected, float)
        or isinstance(actual, float)
    )


def _values_equal(table_name: str, column: str, expected: Any, actual: Any) -> bool:
    expected = _normalise_scalar(expected)
    actual = _normalise_scalar(actual)
    if expected is None or actual is None:
        return expected is actual
    if _looks_like_float(column, expected, actual):
        try:
            expected_float = _round_half_even_12(float(expected))
            actual_float = _round_half_even_12(float(actual))
        except (TypeError, ValueError):
            return False
        return math.isfinite(expected_float) and math.isfinite(actual_float) and abs(expected_float - actual_float) <= 1e-9
    if isinstance(expected, bool) or isinstance(actual, bool):
        if isinstance(expected, str):
            expected = expected.lower() == "true"
        if isinstance(actual, str):
            actual = actual.lower() == "true"
        return expected == actual
    if isinstance(expected, int) and not isinstance(expected, bool):
        try:
            return expected == int(actual)
        except (TypeError, ValueError):
            return False
    if isinstance(actual, int) and not isinstance(actual, bool):
        try:
            return int(expected) == actual
        except (TypeError, ValueError):
            return False
    return expected == actual


def compare_keyed_rows(
    *,
    table_name: str,
    expected_rows: Iterable[dict[str, Any]],
    actual_rows: Iterable[dict[str, Any]],
    key_columns: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    keys = key_columns or KEYED_COMPARISON_KEYS[table_name]

    def keyed(rows: Iterable[dict[str, Any]]) -> tuple[dict[tuple[Any, ...], dict[str, Any]], int]:
        values: dict[tuple[Any, ...], dict[str, Any]] = {}
        duplicate_count = 0
        for row in rows:
            key = tuple(_normalise_scalar(row.get(column)) for column in keys)
            if key in values:
                duplicate_count += 1
            values[key] = row
        return values, duplicate_count

    expected, expected_duplicates = keyed(expected_rows)
    actual, actual_duplicates = keyed(actual_rows)
    missing_keys = sorted(set(expected) - set(actual), key=str)
    extra_keys = sorted(set(actual) - set(expected), key=str)
    field_mismatch_count = 0
    for key in sorted(set(expected) & set(actual), key=str):
        expected_row = expected[key]
        actual_row = actual[key]
        columns = set(expected_row) | set(actual_row)
        if any(
            not _values_equal(table_name, column, expected_row.get(column), actual_row.get(column))
            for column in columns
        ):
            field_mismatch_count += 1
    duplicate_count = expected_duplicates + actual_duplicates
    return {
        "table_name": table_name,
        "key_columns": list(keys),
        "mismatch_count": len(missing_keys) + len(extra_keys) + field_mismatch_count + duplicate_count,
        "missing_key_count": len(missing_keys),
        "extra_key_count": len(extra_keys),
        "field_mismatch_count": field_mismatch_count,
        "duplicate_key_count": duplicate_count,
        "missing_keys": [list(key) for key in missing_keys],
        "extra_keys": [list(key) for key in extra_keys],
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_generator_rows(manifest_path: str | Path) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    manifest_file = Path(manifest_path).resolve()
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    required_artifacts = {
        "labels": "ml_customer_label",
        "training_join": "ml_customer_purchase_training",
        "feature_health_daily": "agg_feature_health_daily",
        "drift_alerts": "feature_drift_alerts",
    }
    rows_by_table: dict[str, list[dict[str, Any]]] = {}
    for artifact_key, table_name in required_artifacts.items():
        artifact = manifest.get("artifacts", {}).get(artifact_key)
        if not isinstance(artifact, dict):
            raise RuntimeError(f"Section 03 manifest is missing artifact {artifact_key!r}.")
        relative_path = Path(str(artifact["path"]))
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise RuntimeError(f"Section 03 artifact path is not repository-relative: {relative_path}")
        artifact_path = (manifest_file.parent / relative_path).resolve()
        try:
            artifact_path.relative_to(manifest_file.parent)
        except ValueError as exc:
            raise RuntimeError(f"Section 03 artifact escapes manifest root: {relative_path}") from exc
        if _sha256(artifact_path) != artifact["sha256"]:
            raise RuntimeError(f"Section 03 artifact hash mismatch: {artifact_key}")
        with artifact_path.open("r", encoding="utf-8", newline="") as handle:
            rows_by_table[table_name] = list(csv.DictReader(handle))
    source_config = Path(str(manifest["source_config_path"]))
    if source_config.is_absolute() or ".." in source_config.parts:
        raise RuntimeError("Section 03 source config path is not repository-relative.")
    repo_root = Path(__file__).resolve().parents[4]
    source_config_path = (repo_root / source_config).resolve()
    if _sha256(source_config_path) != manifest["source_config_sha256"]:
        raise RuntimeError("Section 03 source config hash mismatch.")
    return rows_by_table, {
        "manifest_path": str(manifest_file),
        "manifest_sha256": _sha256(manifest_file),
        "bundle_id": manifest.get("bundle_id"),
        "source_config_path": str(source_config).replace("\\", "/"),
        "source_config_sha256": manifest["source_config_sha256"],
    }


def _keyed_report(
    *,
    family: str,
    table_name: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    return {
        "name": f"{table_name}.keyed_row_mismatch_count",
        "comparison": family,
        "table_name": table_name,
        "mismatch_count": result["mismatch_count"],
        "missing_key_count": result["missing_key_count"],
        "extra_key_count": result["extra_key_count"],
        "field_mismatch_count": result["field_mismatch_count"],
        "success": result["mismatch_count"] == 0,
    }


def run_parity_checks(
    *,
    evidence_root: str | Path,
    duckdb_path: str | Path = "data/gold/vina_bim_shop.duckdb",
    trino_url: str = os.getenv("VBS_TRINO_URL", "http://localhost:8080"),
    user: str = os.getenv("VBS_TRINO_USER", "vina_analyst"),
    section03_manifest: str | Path | None = None,
    generator_config: str | Path | None = None,
    generator_scale: str | None = None,
    dbt_command: list[str] | None = None,
    spark_command: list[str] | None = None,
) -> dict[str, Any]:
    comparisons: list[dict[str, Any]] = []
    keyed_comparisons: dict[str, list[dict[str, Any]]] = {
        "generator_vs_dbt": [],
        "generator_vs_spark": [],
        "dbt_vs_spark": [],
    }
    relation_errors: dict[str, dict[str, str]] = {"duckdb": {}, "spark_trino": {}}
    duckdb = _load_duckdb()
    duckdb_connection = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        dbt_rows: dict[str, list[dict[str, Any]]] = {}
        spark_rows: dict[str, list[dict[str, Any]]] = {}
        for table_name in REQUIRED_GOLD_TABLES:
            try:
                duckdb_value = _duckdb_scalar(duckdb_connection, f"select count(*) from gold.{table_name}")
            except Exception as exc:
                duckdb_value = None
                relation_errors["duckdb"][table_name] = f"{type(exc).__name__}: {exc}"
            try:
                trino_value = _trino_scalar(
                    f"select count(*) from iceberg.gold.{table_name}",
                    trino_url=trino_url,
                    user=user,
                )
            except Exception as exc:
                trino_value = None
                relation_errors["spark_trino"][table_name] = f"{type(exc).__name__}: {exc}"
            comparison = {
                "name": f"{table_name}.row_count",
                "duckdb": duckdb_value,
                "spark_trino": trino_value,
                "delta": None if duckdb_value is None or trino_value is None else trino_value - duckdb_value,
                "tolerance": 0,
                "success": (
                    duckdb_value is not None
                    and trino_value is not None
                    and duckdb_value == trino_value
                ),
            }
            if table_name in relation_errors["duckdb"] or table_name in relation_errors["spark_trino"]:
                comparison["errors"] = {
                    source: errors[table_name]
                    for source, errors in relation_errors.items()
                    if table_name in errors
                }
            comparisons.append(comparison)

        for table_name in KEYED_COMPARISON_KEYS:
            try:
                dbt_rows[table_name] = _duckdb_rows(duckdb_connection, table_name)
            except Exception as exc:
                dbt_rows[table_name] = []
                relation_errors["duckdb"][table_name] = f"{type(exc).__name__}: {exc}"
            try:
                spark_rows[table_name] = _trino_rows(table_name, trino_url=trino_url, user=user)
            except Exception as exc:
                spark_rows[table_name] = []
                relation_errors["spark_trino"][table_name] = f"{type(exc).__name__}: {exc}"

        for name, duckdb_query, trino_query in [
            (
                "fact_order.official_paid_revenue",
                "select round(sum(official_paid_revenue), 2) from gold.fact_order",
                "select round(sum(official_paid_revenue), 2) from iceberg.gold.fact_order",
            ),
            (
                "fact_order.gross_merchandise_value",
                "select round(sum(gross_merchandise_value), 2) from gold.fact_order",
                "select round(sum(gross_merchandise_value), 2) from iceberg.gold.fact_order",
            ),
            (
                "fact_order_item.estimated_cost",
                "select round(sum(estimated_cost), 2) from gold.fact_order_item",
                "select round(sum(estimated_cost), 2) from iceberg.gold.fact_order_item",
            ),
            (
                "fact_order_item.estimated_margin",
                "select round(sum(estimated_margin), 2) from gold.fact_order_item",
                "select round(sum(estimated_margin), 2) from iceberg.gold.fact_order_item",
            ),
            (
                "agg_hourly_reconciled_kpi.official_paid_revenue",
                "select round(sum(official_paid_revenue), 2) from gold.agg_hourly_reconciled_kpi",
                "select round(sum(official_paid_revenue), 2) from iceberg.gold.agg_hourly_reconciled_kpi",
            ),
        ]:
            try:
                duckdb_value = _duckdb_scalar(duckdb_connection, duckdb_query)
            except Exception as exc:
                duckdb_value = None
                relation_errors["duckdb"][name] = f"{type(exc).__name__}: {exc}"
            try:
                trino_value = _trino_scalar(trino_query, trino_url=trino_url, user=user)
            except Exception as exc:
                trino_value = None
                relation_errors["spark_trino"][name] = f"{type(exc).__name__}: {exc}"
            delta = None if duckdb_value is None or trino_value is None else round(trino_value - duckdb_value, 2)
            comparison = {
                "name": name,
                "duckdb": duckdb_value,
                "spark_trino": trino_value,
                "delta": delta,
                "tolerance": 0.01,
                "success": (
                    name not in relation_errors["duckdb"]
                    and name not in relation_errors["spark_trino"]
                    and (
                        (duckdb_value is None and trino_value is None)
                        or (
                            duckdb_value is not None
                            and trino_value is not None
                            and abs(delta) <= 0.01
                        )
                    )
                ),
            }
            if name in relation_errors["duckdb"] or name in relation_errors["spark_trino"]:
                comparison["errors"] = {
                    source: errors[name]
                    for source, errors in relation_errors.items()
                    if name in errors
                }
            comparisons.append(comparison)

        generator_rows: dict[str, list[dict[str, Any]]] | None = None
        manifest_binding: dict[str, Any] | None = None
        if section03_manifest is not None:
            generator_rows, manifest_binding = _load_generator_rows(section03_manifest)
            for table_name, keys in KEYED_COMPARISON_KEYS.items():
                keyed_comparisons["generator_vs_dbt"].append(
                    _keyed_report(
                        family="generator_vs_dbt",
                        table_name=table_name,
                        result=compare_keyed_rows(
                            table_name=table_name,
                            expected_rows=generator_rows[table_name],
                            actual_rows=dbt_rows[table_name],
                            key_columns=keys,
                        ),
                    )
                )
                keyed_comparisons["generator_vs_spark"].append(
                    _keyed_report(
                        family="generator_vs_spark",
                        table_name=table_name,
                        result=compare_keyed_rows(
                            table_name=table_name,
                            expected_rows=generator_rows[table_name],
                            actual_rows=spark_rows[table_name],
                            key_columns=keys,
                        ),
                    )
                )

        for table_name, keys in KEYED_COMPARISON_KEYS.items():
            keyed_comparisons["dbt_vs_spark"].append(
                _keyed_report(
                    family="dbt_vs_spark",
                    table_name=table_name,
                    result=compare_keyed_rows(
                        table_name=table_name,
                        expected_rows=dbt_rows[table_name],
                        actual_rows=spark_rows[table_name],
                        key_columns=keys,
                    ),
                )
            )
        comparisons.extend(keyed_comparisons["dbt_vs_spark"])
        if section03_manifest is not None:
            comparisons.extend(keyed_comparisons["generator_vs_dbt"])
            comparisons.extend(keyed_comparisons["generator_vs_spark"])
    finally:
        duckdb_connection.close()

    all_keyed = [item for family in keyed_comparisons.values() for item in family]
    report = {
        "success": all(comparison["success"] for comparison in comparisons) and all(
            comparison["success"] for comparison in all_keyed
        ),
        "comparisons": comparisons,
        "keyed_comparisons": keyed_comparisons,
        "generator_config": str(generator_config) if generator_config is not None else None,
        "generator_scale": generator_scale,
        "dbt_command": dbt_command,
        "spark_command": spark_command,
        "section03_manifest": manifest_binding,
        "relation_errors": relation_errors,
    }
    evidence_path = Path(evidence_root)
    evidence_path.mkdir(parents=True, exist_ok=True)
    (evidence_path / "dbt_parity_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    markdown_rows = [
        "# dbt Parity Report",
        "",
        f"Overall success: {'PASS' if report['success'] else 'FAIL'}",
        "",
        "| Check | DuckDB | Spark/Trino | Delta | Success |",
        "| --- | ---: | ---: | ---: | --- |",
        *[
            f"| {comparison['name']} | {comparison.get('duckdb', comparison.get('mismatch_count'))} | {comparison.get('spark_trino', comparison.get('mismatch_count'))} | {comparison.get('delta', comparison.get('mismatch_count', 0))} | {'PASS' if comparison['success'] else 'FAIL'} |"
            for comparison in comparisons
        ],
        "",
        "## Keyed comparison families",
        "",
        *[
            f"- {family}: {len([item for item in items if item['success']])}/{len(items)} PASS"
            for family, items in keyed_comparisons.items()
            if items
        ],
    ]
    (evidence_path / "dbt_parity_report.md").write_text("\n".join(markdown_rows), encoding="utf-8")
    if not report["success"]:
        raise RuntimeError("dbt parity checks failed.")
    return report
