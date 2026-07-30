# Section 03 Candidate Evidence

## Run Context

Scale `medium`, seed `42`, history `60` days. This is local candidate evidence.

## Scenario and Rationale

`customer_order_frequency` uses an abrupt configured 1.5x post-cutoff order-rate multiplier.

## Fixed Counts

{"customers": 12000, "orders": 45000, "products": 6000, "promotions": 80, "sellers": 600}

## Realized Pre/Post Rates

{"order_normalized_post_pre_ratio": 1.518934890754, "order_post_count": 20246, "order_post_rate_per_day": 980.43583535109, "order_pre_count": 24754, "order_pre_rate_per_day": 645.475880052151, "stream_normalized_post_pre_ratio": 1.52176741148, "stream_post_count": 43011, "stream_pre_count": 52490}

## Point-in-Time and Label Policy

Features are cutoff-safe at `2026-04-24T23:59:00Z` and labels use the exclusive-start/inclusive-end horizon through `2026-05-01T23:59:00Z`.

## Daily PSI Summary

22 complete-day rows; maximum PSI `0.068131800343` for the fixed baseline-known cohort.

## Alerts

0 alert rows at the inclusive `0.15` threshold.

## Exact Label Contract

`id,label`; 11996 unique synthetic customer IDs.

## Feast-ready Training Join

11996 one-to-one rows with `event_timestamp == created == feature_cutoff_ts`.

## Quality Checks

{"alert_threshold_respected": true, "configured_counts_preserved": true, "labels_binary": true, "labels_exact_schema": true, "labels_unique": true, "point_in_time_safe": true, "psi_finite": true, "streaming_distribution_inherited": true, "training_join_one_to_one": true}

## Spark/dbt Parity Runtime

Pending

## Airflow DP3 Runtime

Pending

## DataHub Lineage Runtime

Pending

## Sheet3 E32-E34 Evidence

Candidate artifacts contribute to E32-E34 but earn zero rubric credit until strict runtime finalization.

## Reproduction Commands

`uv run python scripts/generate/run_generator.py --config configs/generator/base.yaml --scale medium --mode full --clean --seed 42`

## Limitations

Local candidate only. This does not prove Spark/dbt parity, Airflow, DataHub, Feast, GKE, GCP execution, or final rubric satisfaction.

