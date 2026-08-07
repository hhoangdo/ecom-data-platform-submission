# Data Generator Improvement — Section 03

Section 03 adds a reproducible customer-order-frequency drift scenario, a
leakage-safe seven-day purchase label, daily PSI monitoring, and a
Feast-ready offline feature/label export. It is a local contract and evidence
package; it does not install Feast, materialize an online store, or serve
features.

## Scope and rubric traceability

The public coursework mapping is fixed to the workbook cells below.

| Cell | Points | Contract and supporting proof |
| --- | ---: | --- |
| `Sheet3!E32` | 1 | The configured `customer_order_frequency` scenario records its configuration snapshot and the merged feature/label result. |
| `Sheet3!E33` | 1 | Generator, dbt/Spark, Airflow, and DataHub paths bind to the same validated YAML configuration, scale, seed, and timestamps. |
| `Sheet3!E34` | 2 | `ml_customer_label.csv` and Gold `ml_customer_label` contain exactly the ordered columns `id,label`; `ml_customer_purchase_training` is the separately named richer join. |

These are supporting local contracts only. Topic 07 owns real runtime
execution, strict promotion, screenshots, and the final rubric claim.

## Scenario and time policy

The canonical scenario is `customer_order_frequency` in
`configs/generator/base.yaml`. It redistributes a fixed number of order
timestamps between pre-drift and post-drift windows while preserving the
configured entity counts and seed. The monitoring feature is
`f_customer_order_frequency_7d`, calculated from equal trailing seven-day
windows. PSI uses fixed baseline bins, `epsilon=1e-6`, warning at `psi >= 0.10`;
alert at `psi >= 0.15`.

The feature cutoff is `end_ts - 7 days`. A label is one when the customer has
a successful payment strictly after that cutoff and no later than the
seven-day horizon. The eligible cohort is every non-null customer known by
the cutoff. Future customer identities are excluded. Feature rows and the
training join are therefore point-in-time safe and use the same cutoff.

## Output contracts

`ml_customer_label` is the exact two-column contract:

```text
id,label
```

`id` is unique and non-null; `label` is an integer in `{0,1}`. The richer
`ml_customer_purchase_training` output joins that label to cutoff-safe
features and retains `event_timestamp` and `created` at the fixed cutoff.
`agg_feature_health_daily` records the fixed cohort, seven-day window, PSI,
and status flags. `feature_drift_alerts` contains only rows at or above the
0.15 threshold and carries the action to investigate the drift.

## Reproducible local commands

The operator-facing commands use the repository's `rtk` wrapper. Make recipes
invoke `uv run` internally.

```powershell
rtk make generate-section03 SCALE=medium SEED=42
rtk make build-section03-dbt SCALE=medium
rtk make test-section03
```

The generator entry point remains
`scripts/generate/run_generator.py`; the configuration-derived dbt path is
`scripts/analytics/run_section03_dbt.py`. The finalizer consumes a pending
candidate plus Spark, Airflow, and DataHub capture roots; the exact CLI is
documented in the finalizer test contract and is intentionally not run in
this local documentation/schema topic.

## Evidence layout

Generator output is pending until the finalizer verifies all recursive
runtime inventories and atomically promotes a new immutable bundle.

```text
evidence/03_data_generator_improvement/section03_candidate_manifest.json
evidence/03_data_generator_improvement/section03_manifest.json
evidence/03_data_generator_improvement/runs/<bundle_id>/config_snapshot.yaml
evidence/03_data_generator_improvement/runs/<bundle_id>/ml_customer_label.csv
evidence/03_data_generator_improvement/runs/<bundle_id>/ml_customer_purchase_training.csv
evidence/03_data_generator_improvement/runs/<bundle_id>/section03_config_and_training_join.png
```

The candidate is generator-only and earns no live rubric credit. A verified
manifest must bind the generator artifacts to recursive Spark, Airflow, and
DataHub runtime captures, including hashes and run identity. No local
candidate, synthetic fixture, or mock service response is described as GKE,
Airflow, DataHub, or Trino runtime evidence.

## Finalizer boundary

`scripts/generate/finalize_section03_evidence.py` is fail-closed. It rejects
missing, corrupt, stale, unlisted, absolute, traversing, or symlinked files;
configuration, scale, cutoff, and run-identity mismatches; candidate-pointer
races; and same-ID content mismatches. It writes a fresh immutable bundle and
replaces only the canonical manifest after all checks pass. The previous
verified bundle is retained. A post-promotion cleanup warning preserves the
new bundle and reports uncertain housekeeping rather than rolling back a
verified promotion.

## Limits

Section 03 is a Feast-ready offline export only. Feast installation,
registry, materialization, online serving, and model training/serving belong
to EDAI2. There is no live Airflow/DataHub evidence in this topic. This
deliverable does not claim a Spark/Trino query, Kubernetes/GKE result, or
screenshot. Topic 07
must execute the real captures, run strict verification, and attach the
contextual 1600x900 evidence image before any rubric score is asserted.
