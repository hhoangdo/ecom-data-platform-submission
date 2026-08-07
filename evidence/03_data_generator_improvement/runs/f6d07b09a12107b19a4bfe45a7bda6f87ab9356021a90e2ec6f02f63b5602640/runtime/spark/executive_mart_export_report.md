# DuckDB Executive Mart Export Report

- Exported at: `2026-08-07T02:43:04.944986+00:00`
- DuckDB path: `data\gold\vina_bim_shop_executive.duckdb`
- Source: `trino://iceberg.gold`
- Tables: 26
- Rows: 539187

| Table | Source relation | Rows | Columns |
| --- | --- | ---: | ---: |
| `dim_customer` | `iceberg.gold.dim_customer` | 12000 | 16 |
| `dim_seller` | `iceberg.gold.dim_seller` | 600 | 16 |
| `dim_product` | `iceberg.gold.dim_product` | 6000 | 17 |
| `dim_category` | `iceberg.gold.dim_category` | 20 | 4 |
| `dim_date` | `iceberg.gold.dim_date` | 61 | 6 |
| `dim_payment_method` | `iceberg.gold.dim_payment_method` | 5 | 2 |
| `dim_order_status` | `iceberg.gold.dim_order_status` | 2 | 2 |
| `dim_shipment_status` | `iceberg.gold.dim_shipment_status` | 4 | 2 |
| `dim_shipping_method` | `iceberg.gold.dim_shipping_method` | 5 | 2 |
| `dim_promotion` | `iceberg.gold.dim_promotion` | 81 | 13 |
| `bridge_product_category` | `iceberg.gold.bridge_product_category` | 7340 | 7 |
| `fact_order` | `iceberg.gold.fact_order` | 45000 | 27 |
| `fact_order_item` | `iceberg.gold.fact_order_item` | 165193 | 25 |
| `fact_payment_attempt` | `iceberg.gold.fact_payment_attempt` | 45000 | 16 |
| `fact_shipment` | `iceberg.gold.fact_shipment` | 45000 | 18 |
| `fact_inventory_snapshot` | `iceberg.gold.fact_inventory_snapshot` | 60000 | 11 |
| `fact_promotion_application` | `iceberg.gold.fact_promotion_application` | 58401 | 14 |
| `obt_order_performance` | `iceberg.gold.obt_order_performance` | 45000 | 32 |
| `agg_hourly_reconciled_kpi` | `iceberg.gold.agg_hourly_reconciled_kpi` | 1416 | 21 |
| `feat_customer_90d` | `iceberg.gold.feat_customer_90d` | 11996 | 7 |
| `feat_stream_60m` | `iceberg.gold.feat_stream_60m` | 53 | 8 |
| `feat_customer_unified` | `iceberg.gold.feat_customer_unified` | 11996 | 12 |
| `ml_customer_label` | `iceberg.gold.ml_customer_label` | 11996 | 2 |
| `agg_feature_health_daily` | `iceberg.gold.agg_feature_health_daily` | 22 | 11 |
| `feature_drift_alerts` | `iceberg.gold.feature_drift_alerts` | 0 | 5 |
| `ml_customer_purchase_training` | `iceberg.gold.ml_customer_purchase_training` | 11996 | 13 |
