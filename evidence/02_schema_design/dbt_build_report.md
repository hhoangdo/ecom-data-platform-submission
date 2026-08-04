# Section 02 dbt Evidence Report

## Command Summary

- `dbt build --project-dir infra/analytics/dbt --profiles-dir infra/analytics/dbt` completed before artifact extraction.
- `dbt docs generate --project-dir infra/analytics/dbt --profiles-dir infra/analytics/dbt` produced `manifest.json` and `catalog.json` for summarized evidence.

## dbt Results

- Models: 56 (success=56)
- Tests: 90 (pass=90)
- Cataloged models by schema: bronze=16, gold=26, silver=14

## Gold Row Counts

- `agg_feature_health_daily`: 22 rows
- `agg_hourly_reconciled_kpi`: 1,416 rows
- `bridge_product_category`: 7,340 rows
- `dim_category`: 20 rows
- `dim_customer`: 12,000 rows
- `dim_date`: 61 rows
- `dim_order_status`: 2 rows
- `dim_payment_method`: 5 rows
- `dim_product`: 6,000 rows
- `dim_promotion`: 81 rows
- `dim_seller`: 600 rows
- `dim_shipment_status`: 4 rows
- `dim_shipping_method`: 5 rows
- `fact_inventory_snapshot`: 60,000 rows
- `fact_order`: 45,000 rows
- `fact_order_item`: 165,193 rows
- `fact_payment_attempt`: 45,000 rows
- `fact_promotion_application`: 58,401 rows
- `fact_shipment`: 45,000 rows
- `feat_customer_90d`: 11,996 rows
- `feat_customer_unified`: 11,996 rows
- `feat_stream_60m`: 53 rows
- `feature_drift_alerts`: 0 rows
- `ml_customer_label`: 11,996 rows
- `ml_customer_purchase_training`: 11,996 rows
- `obt_order_performance`: 45,000 rows

## Evidence Files

- `evidence/02_schema_design/dbt_test_results.csv`
- `evidence/02_schema_design/dbt_model_results.csv`
- `evidence/02_schema_design/dbt_catalog_summary.csv`
- `evidence/02_schema_design/schema_inventory.csv`
- `evidence/02_schema_design/table_row_counts.csv`
- `evidence/02_schema_design/run_manifest.json`
- `evidence/02_schema_design/screenshots/schema_design.png`
- `evidence/02_schema_design/screenshots/gold_schema_inventory.png`
- `evidence/02_schema_design/screenshots/dbt_test_summary.png`
