# dbt Parity Report

Overall success: PASS

| Check | DuckDB | Spark/Trino | Delta | Success |
| --- | ---: | ---: | ---: | --- |
| dim_customer.row_count | 12000 | 12000 | 0 | PASS |
| dim_seller.row_count | 600 | 600 | 0 | PASS |
| dim_product.row_count | 6000 | 6000 | 0 | PASS |
| dim_category.row_count | 20 | 20 | 0 | PASS |
| dim_date.row_count | 61 | 61 | 0 | PASS |
| dim_payment_method.row_count | 5 | 5 | 0 | PASS |
| dim_order_status.row_count | 2 | 2 | 0 | PASS |
| dim_shipment_status.row_count | 4 | 4 | 0 | PASS |
| dim_shipping_method.row_count | 5 | 5 | 0 | PASS |
| dim_promotion.row_count | 81 | 81 | 0 | PASS |
| bridge_product_category.row_count | 7340 | 7340 | 0 | PASS |
| fact_order.row_count | 45000 | 45000 | 0 | PASS |
| fact_order_item.row_count | 165193 | 165193 | 0 | PASS |
| fact_payment_attempt.row_count | 45000 | 45000 | 0 | PASS |
| fact_shipment.row_count | 45000 | 45000 | 0 | PASS |
| fact_inventory_snapshot.row_count | 60000 | 60000 | 0 | PASS |
| fact_promotion_application.row_count | 58401 | 58401 | 0 | PASS |
| obt_order_performance.row_count | 45000 | 45000 | 0 | PASS |
| agg_hourly_reconciled_kpi.row_count | 1416 | 1416 | 0 | PASS |
| feat_customer_90d.row_count | 11996 | 11996 | 0 | PASS |
| feat_stream_60m.row_count | 53 | 53 | 0 | PASS |
| feat_customer_unified.row_count | 11996 | 11996 | 0 | PASS |
| ml_customer_label.row_count | 11996 | 11996 | 0 | PASS |
| agg_feature_health_daily.row_count | 22 | 22 | 0 | PASS |
| feature_drift_alerts.row_count | 0 | 0 | 0 | PASS |
| ml_customer_purchase_training.row_count | 11996 | 11996 | 0 | PASS |
| fact_order.official_paid_revenue | 146892037803.0 | 146892037803.0 | 0.0 | PASS |
| fact_order.gross_merchandise_value | 156003358000.0 | 156003358000.0 | 0.0 | PASS |
| fact_order_item.estimated_cost | 110524708660.09 | 110524708660.09 | 0.0 | PASS |
| fact_order_item.estimated_margin | 36367329142.91 | 36367329142.91 | 0.0 | PASS |
| agg_hourly_reconciled_kpi.official_paid_revenue | 146892037803.0 | 146892037803.0 | 0.0 | PASS |
| ml_customer_label.keyed_row_mismatch_count | 0 | 0 | 0 | PASS |
| ml_customer_purchase_training.keyed_row_mismatch_count | 0 | 0 | 0 | PASS |
| agg_feature_health_daily.keyed_row_mismatch_count | 0 | 0 | 0 | PASS |
| feature_drift_alerts.keyed_row_mismatch_count | 0 | 0 | 0 | PASS |
| ml_customer_label.keyed_row_mismatch_count | 0 | 0 | 0 | PASS |
| ml_customer_purchase_training.keyed_row_mismatch_count | 0 | 0 | 0 | PASS |
| agg_feature_health_daily.keyed_row_mismatch_count | 0 | 0 | 0 | PASS |
| feature_drift_alerts.keyed_row_mismatch_count | 0 | 0 | 0 | PASS |
| ml_customer_label.keyed_row_mismatch_count | 0 | 0 | 0 | PASS |
| ml_customer_purchase_training.keyed_row_mismatch_count | 0 | 0 | 0 | PASS |
| agg_feature_health_daily.keyed_row_mismatch_count | 0 | 0 | 0 | PASS |
| feature_drift_alerts.keyed_row_mismatch_count | 0 | 0 | 0 | PASS |

## Keyed comparison families

- generator_vs_dbt: 4/4 PASS
- generator_vs_spark: 4/4 PASS
- dbt_vs_spark: 4/4 PASS