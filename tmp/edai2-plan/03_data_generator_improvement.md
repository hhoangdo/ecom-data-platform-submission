# Section 03 Data Generator Drift and Labels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a reproducible customer-order-frequency drift scenario, leakage-safe seven-day purchase labels, daily PSI monitoring, and a Feast-ready point-in-time feature/label export with matching generator, Spark, dbt, Airflow, DataHub, documentation, and evidence contracts. This plan is the mandatory E32-E34 prerequisite for `04.2_llm_design.md`.

**Architecture:** Keep `run_generation()` as the public generator entry point and add focused drift, label, and Section 03 evidence modules behind it. The generator redistributes a fixed number of order timestamps with normalized pre/post weights; Spark and dbt independently build the same point-in-time Gold features, exact two-column label, monitoring tables, alert table, and richer training join from configuration-derived timestamps. Airflow validates the DP3 contracts, DataHub records the expanded lineage, and a section-specific evidence package binds configuration, samples, metrics, a deterministic evidence image, and hashes in one manifest.

**Tech Stack:** Python 3.12, NumPy, Pandas, PyArrow, PyYAML, Pillow, pytest, Spark SQL/Iceberg, dbt Core with DuckDB, Trino, Great Expectations, Airflow, DataHub, Make.

## Global Constraints

- This is an implementation plan only; every checkbox and completion item below is not started.
- Preserve this approved decision verbatim: `DriftConfig scenario customer_order_frequency; enabled config; cutoff_fraction=0.65; abrupt mode; post_rate_multiplier=1.5; PSI warning=0.10 and alert=0.15; label_horizon_days=7.`
- Add the enabled values to `configs/generator/base.yaml`; do not hide them in Python, SQL, Airflow, or Make literals.
- Raise only the `smoke` profile's `history_days` from `7` to `14`, leaving every smoke entity count unchanged, because a 65% cutoff otherwise cannot supply the required seven complete pre-cutoff calendar days. The full and medium profiles retain their existing history windows.
- Keep every configured entity count, including `entities.orders`, fixed. Drift changes timestamp allocation only.
- Normalize the pre/post timestamp weights before sampling; do not create, clone, or remove orders to achieve the 1.5 rate multiplier.
- When `drift.enabled` is false, generated raw datasets must be byte-equivalent where the writer is deterministic and semantically frame-equivalent everywhere else to the current output for the same configuration and seed.
- Preserve the existing public `run_generation()` name, keyword-only parameters, defaults, return type, exception behavior, and `GenerationResult` fields exactly.
- Define the feature cutoff as the configured generator `end_ts` minus exactly seven days. Features may use only source events known at or before that cutoff.
- Define a purchase as a successful payment. Labels may use purchases strictly after the feature cutoff and at or before the cutoff plus seven days; no post-horizon row contributes.
- Emit the label artifact and Gold label table with exactly two ordered columns, `id,label`, one unique row per customer, and integer labels restricted to `0` or `1`.
- Define "one row per customer" as every unique non-null customer known by the feature cutoff (`customer.created_ts <= feature_cutoff_ts`). Apply this identical eligible cohort to labels, point-in-time features, the training join, Spark, dbt, Airflow validation, and E34 evidence; future customer identities are never introduced at prediction time.
- Keep the richer point-in-time join distinct from the exact label contract. Name it `ml_customer_purchase_training` in generator evidence, Spark, dbt, Airflow, DataHub, and documentation.
- Use baseline quantile bins for PSI, `epsilon=1e-6` for empty-bin proportions, warning at `psi >= 0.10`, and alert at `psi >= 0.15`.
- Feed PSI with per-customer order counts from equal trailing seven-complete-day UTC windows (the approved horizon), never cumulative or left-censored 90-day counts. Name this health feature `f_customer_order_frequency_7d` and persist `window_days=7`; the separate training feature remains `f_customer_total_orders_90d`.
- Section 03 produces a Feast-ready offline export contract only. Do not add the Feast package, a Feast server, an online store, materialization, ingestion, or serving; Section 04.2 owns those operations.
- Match the repository's current module, SQL, test, evidence, and command style. Make surgical changes only; do not refactor unrelated generator, Spark, dbt, orchestration, or lineage code.
- Do not change existing offline/streaming quality rates, taxonomy, customer affinity, payment behavior, schema-evolution behavior, or Kafka behavior.
- Use `apply_patch` for repository text edits. Preserve unrelated user changes. Do not stage or commit without a separate explicit request.
- Run commands through `rtk`; Python and pytest commands use `rtk uv run ...` as shown below.

---

## Sheet3 E32-E34 Traceability

| Cell | Points | Workbook requirement | Planned proof |
| --- | ---: | --- | --- |
| `Sheet3!E32` | 1 | Simulate drift and capture evidence showing generator configuration and the merged ID/label result. | Enabled `customer_order_frequency` drift, `config_snapshot.yaml`, `ml_customer_purchase_training.csv`, its sample, `section03_config_and_training_join.png`, and manifest hashes. |
| `Sheet3!E33` | 1 | Use generator configuration. | Typed `DriftConfig`, strict YAML validation, runtime timestamps derived from `base.yaml`, config-faithfulness tests, and the canonical snapshot embedded in the Section 03 manifest. |
| `Sheet3!E34` | 2 | Create a label table with two columns, ID and label, for joining with features for training. | `ml_customer_label.csv` and Gold `ml_customer_label`, both exactly `id,label`, unique by `id`, plus `ml_customer_purchase_training` as the separately named richer join. |

The workbook row text permits an entity-specific name such as `customer_id`, but this plan intentionally uses the stricter approved output spelling `id,label`.

## Current State

- `configs/generator/base.yaml` has scale, entity, quality, streaming, and output controls but no Section 03 drift mapping.
- `GeneratorConfig` is frozen, but it has no typed drift member and currently retains several scenario groups as untyped dictionaries.
- `offline/orders.py::_generate_orders` calls `random_timestamps(..., evening_bias=True)` and creates exactly `config.entities["orders"]` rows with a uniform day allocation plus the existing hourly bias.
- `generate_offline()` mutates order status after payment generation and returns customers, orders, payments, and dependent datasets in memory, so labels and evidence can be built without changing `run_generation()`.
- `write_evidence()` writes Section 01 evidence only. It has no drift configuration snapshot, PSI output, label, feature/label join, Section 03 report, Section 03 manifest, or E32 evidence image.
- Spark/dbt `feat_customer_90d` currently aggregates all available orders and sets `event_timestamp` to each customer's latest order. `feat_stream_60m` and `feat_customer_unified` likewise select latest available events without a fixed Section 03 cutoff.
- Spark and dbt currently agree on three feature tables. `REQUIRED_GOLD_TABLES`, parity checks, DP3 Airflow metadata, Great Expectations checks, and DataHub lineage all encode that three-table boundary.
- `deliverables/03_data_generator_improvement.md` and `configs/scenarios/README.md` explicitly describe Section 03 as unimplemented.
- No Feast dependency or runtime exists, which is correct for this section's Feast-ready-only boundary.

## Gaps, Scope, Non-Goals, and Dependencies

**Gaps:** There is no drift configuration or timestamp reweighting, no leakage-safe cutoff, no exact label artifact, no PSI implementation, no monitoring/alert outputs, no point-in-time training join, and no end-to-end Section 03 evidence or lineage.

**In scope:** One abrupt customer-order-frequency scenario; generator-local evidence; leakage-safe Gold feature, label, monitoring, alert, and training models; Spark/dbt parity; DP3 validation; DataHub lineage; schema and command documentation; deterministic evidence generation and tests.

**Non-goals:** Additional drift scenarios, changing order or entity counts, concept-drift simulation, model training, model evaluation, actual Feast installation/operation, online feature serving, new infrastructure services, and unrelated generator or lakehouse refactors.

**Dependencies:** Existing NumPy/Pandas/PyArrow/PyYAML/Pillow/DuckDB/pytest project dependencies; current generator frames; existing Spark/Iceberg and dbt-DuckDB paths; current Airflow DP3 and DataHub coursework lineage packages. No new third-party package is required.

## Time and Boundary Semantics

- Reuse `time_bounds(config)` for `start_ts` and `end_ts`; its configured inclusive end is the normalized `end_date` plus 23 hours and 59 minutes.
- `drift_start_ts = start_ts + (end_ts - start_ts) * drift.cutoff_fraction`. Strict parsing locks that configured value to `0.65`; a sampled timestamp is post-drift when `timestamp >= drift_start_ts`.
- `feature_cutoff_ts = end_ts - pd.Timedelta(days=drift.label_horizon_days)`. Strict parsing locks the horizon to `7`.
- `label_end_ts = feature_cutoff_ts + pd.Timedelta(days=drift.label_horizon_days)`, which equals `end_ts`.
- A feature source row is available only when both its event timestamp and `created_ts` are `<= feature_cutoff_ts`.
- The label/training cohort is customers with `created_ts <= feature_cutoff_ts`. PSI uses a stricter fixed cohort known by the end of `baseline_date`; the cohort never grows across monitoring dates, so customer acquisition cannot masquerade as feature drift.
- Offline 90-day features use `(feature_cutoff_ts - 90 days, feature_cutoff_ts]` after applying the availability rule.
- Stream features use events with `event_timestamp <= feature_cutoff_ts` and `created_ts <= feature_cutoff_ts`, then select the latest hourly record per entity at or before the cutoff.
- A positive label requires `payment_status == "success"`, `feature_cutoff_ts < payment_timestamp <= label_end_ts`, and `created_ts <= label_end_ts`.
- The PSI baseline date is the full calendar day immediately before `drift_start_ts.floor("D")`; this excludes a partially pre/post cutoff day. Its reference window is the seven complete UTC calendar days ending on `baseline_date`. Each monitoring date uses the same fixed cohort and its own seven complete UTC calendar days ending on that date; daily monitoring spans baseline date through `end_ts.floor("D")`. Enabled configuration fails early if the selected history cannot supply the complete baseline window.

## Exact File Map

| Action | Path | Responsibility |
| --- | --- | --- |
| Modify | `configs/generator/base.yaml` | Add the enabled drift mapping and `outputs.section03_evidence_root`. |
| Modify | `src/vina_bim_shop/generators/config.py` | Add frozen `DriftConfig`, strict parsing/validation, and resolved Section 03 evidence root. |
| Create | `src/vina_bim_shop/generators/drift.py` | Resolve windows, sample deterministic normalized drift timestamps, calculate realized rates, and calculate PSI. |
| Create | `src/vina_bim_shop/generators/labels.py` | Build exact purchase labels and the generator-local point-in-time feature/label join. |
| Create | `src/vina_bim_shop/generators/drift_evidence.py` | Build daily health/alerts and write all Section 03 artifacts, samples, image, hashes, report, and manifest. |
| Modify | `src/vina_bim_shop/generators/offline/orders.py` | Route order timestamp creation through the drift function without changing public order-builder signatures. |
| Modify | `src/vina_bim_shop/generators/runner.py` | Invoke Section 03 evidence after full offline data exists and merge returned paths while preserving `run_generation()`. |
| Modify | `src/vina_bim_shop/generators/writer.py` | Under the Section 03 lock, clean only abandoned staging and unreferenced candidate bundles after a replacement candidate verifies; never pre-delete the authoritative manifest or either retained verified bundle. |
| Modify | `scripts/generate/run_generator.py` | Report the Section 03 manifest path when enabled; keep all current CLI arguments compatible. |
| Create | `scripts/generate/verify_section03_manifest.py` | Independently fail closed on candidate/final manifest shape, containment, exact schemas/counts, transitive runtime inventories, consumer-contract bindings, hashes, checks, and the four-point rubric ceiling. |
| Create | `scripts/generate/finalize_section03_evidence.py` | Import verified Spark/Airflow/DataHub captures from the pending candidate into a new immutable final bundle and only then atomically promote the canonical verified manifest. |
| Create | `tests/integration/test_section03_finalizer.py` | Exercise successful promotion plus corrupt, missing, stale, recursive-inventory, pre-replace, retention, and candidate-pointer failure paths. |
| Create | `scripts/analytics/run_section03_dbt.py` | Load generator YAML, derive exact runtime timestamps, and call dbt with JSON `--vars` from that configuration. |
| Create | `scripts/orchestration/run_section03_dp3.py` | Trigger/poll the real Airflow coursework DAG and export the six task states plus DP3 artifacts into a temporary runtime-capture root. |
| Modify | `scripts/datahub/capture_evidence.py` | Add a Section 03 strict mode that verifies the seven-output DataFlow, schemas, assertions, indexed search, and rendered lineage capture. |
| Modify | `src/vina_bim_shop/lakehouse/spark/sql.py` | Parameterize the three existing feature queries and add label, daily health, alerts, and training queries in dependency order. |
| Modify | `src/vina_bim_shop/lakehouse/spark/constants.py` | Define the exact seven-table `DP3_GOLD_TABLES`, add all four new outputs to `GOLD_SERVING_TABLES`, and keep `REQUIRED_GOLD_TABLES` derived without duplicates. |
| Modify | `src/vina_bim_shop/lakehouse/spark/job.py` | Load the generator config for feature stages and pass typed Section 03 SQL parameters. |
| Modify | `src/vina_bim_shop/lakehouse/spark/runner.py` | Forward the generator config to Spark and pass the same derived vars to dbt/parity. |
| Modify | `src/vina_bim_shop/lakehouse/spark/parity.py` | Compare dbt/Spark and canonical-generator keyed rows for labels, monitoring, alerts, and training, plus retained aggregates. |
| Modify | `scripts/spark/run_batch.py` | Expose and forward the selected generator config and scale to Spark and dbt parity. |
| Modify | `infra/analytics/dbt/dbt_project.yml` | Declare that Section 03 vars are required; do not duplicate generator values as dbt defaults. |
| Modify | `infra/analytics/dbt/models/silver/stg_commerce_events.sql` | Align nested-ID extraction, deterministic dedup ranking, and ambiguity rejection with the generator/Spark normalization contract. |
| Modify | `infra/analytics/dbt/models/gold/feat_customer_90d.sql` | Compute a customer-complete, 90-day feature snapshot known at the cutoff. |
| Modify | `infra/analytics/dbt/models/gold/feat_stream_60m.sql` | Exclude stream rows unavailable at the cutoff. |
| Modify | `infra/analytics/dbt/models/gold/feat_customer_unified.sql` | Join only cutoff-safe offline and stream snapshots. |
| Create | `infra/analytics/dbt/models/gold/ml_customer_label.sql` | Build exact `id,label` from successful payments in the horizon. |
| Create | `infra/analytics/dbt/models/gold/agg_feature_health_daily.sql` | Compute daily customer-order features, baseline bins, PSI, and statuses. |
| Create | `infra/analytics/dbt/models/gold/feature_drift_alerts.sql` | Filter alert-level daily PSI rows and attach the prescribed action. |
| Create | `infra/analytics/dbt/models/gold/ml_customer_purchase_training.sql` | Join exact labels to cutoff-safe unified features for the Feast-ready export. |
| Modify | `infra/analytics/dbt/models/gold/_features.yml` | Preserve and tighten the three feature contracts at the fixed cutoff. |
| Create | `infra/analytics/dbt/models/gold/_drift.yml` | Enforce schemas, constraints, keys, accepted values, and relationships for four new tables. |
| Create | `infra/analytics/dbt/tests/assert_ml_customer_label_matches_horizon.sql` | Recompute successful purchases in the seven-day horizon and fail on label differences. |
| Create | `infra/analytics/dbt/tests/assert_training_features_are_point_in_time.sql` | Recompute pre-cutoff features and fail on post-cutoff leakage or value differences. |
| Create | `infra/analytics/dbt/tests/assert_drift_alert_threshold.sql` | Fail when an alert row has PSI below 0.15 or a wrong status/action. |
| Create | `infra/analytics/dbt/tests/assert_commerce_event_dedup_unambiguous.sql` | Fail when tied duplicate winners disagree on any normalized feature field. |
| Modify | `src/vina_bim_shop/orchestration/mini_coursework_pipeline.py` | Expand DP3 outputs and validate table-specific schemas, keys, thresholds, and cutoff semantics. |
| Modify | `infra/orchestration/airflow/dags/mini_coursework_pipeline.py` | Forward the three required Section 03 DAG-conf values to the existing six-stage implementation without consulting Airflow Variables. |
| Modify | `infra/orchestration/airflow/bootstrap/seed_coursework_metadata.py` | Seed the seven-table DP3 output list. |
| Modify | `src/vina_bim_shop/datahub_lineage/spark_lineage.py` | Add exact upstreams for the four new Gold outputs and correct cutoff-safe feature upstreams. |
| Modify | `src/vina_bim_shop/datahub_lineage/coursework_pipelines.py` | Publish all seven DP3 outputs, schemas, descriptions, and assertion targets. |
| Modify | `tests/unit/test_generator_config.py` | Cover typed values and every invalid drift configuration. |
| Create | `tests/unit/test_section03_drift.py` | Cover deterministic sampling, disabled equivalence, counts, realized rate ratio, labels, leakage, PSI bins, and thresholds. |
| Modify | `tests/unit/test_generator_module_split.py` | Permit the three focused modules (`drift`, `labels`, `drift_evidence`) while preserving the test's real legacy re-export/importability rules; do not invent a module-size rule the repository does not have. |
| Create | `tests/unit/test_section03_manifest_verifier.py` | Parametrize every fail-closed manifest rejection, including traversal, extra/missing keys, schema/count drift, rebinding, hash mismatch, false checks, and score inflation. |
| Create | `tests/unit/test_section03_dbt_contract.py` | Fail first on absent models/required vars, then verify wrapper argument construction, parent-inclusive selection, schemas, and no duplicated defaults. |
| Create | `tests/integration/test_section03_generator.py` | Cover canonical Section 03 artifact schemas, samples, hashes, report, and manifest integrity. |
| Modify | `tests/integration/test_generator_cli.py` | Cover the CLI's Section 03 completion output and resolved evidence path. |
| Modify | `tests/integration/test_section01_generator.py` | Reassert all pre-existing Section 01 keys/artifacts and disabled-mode equivalence after runner integration. |
| Modify | `tests/unit/test_spark_batch_runtime.py` | Cover parameterized Spark SQL, Gold order, cutoff predicates, and parity comparisons. |
| Modify | `tests/unit/test_orchestration_runtime.py` | Cover the expanded DP3 runtime validation payload and blocking failures. |
| Modify | `tests/unit/test_airflow_coursework_metadata.py` | Cover seeded seven-table DP3 metadata. |
| Modify | `tests/unit/test_datahub_coursework_lineage.py` | Cover exact new inputs, outputs, schemas, assertions, and lineage edges. |
| Create | `tests/unit/test_section03_documentation.py` | Prevent the placeholder/out-of-scope wording from returning and verify commands/contracts. |
| Modify | `Makefile` | Add `generate-section03`, `build-section03-dbt`, and `test-section03` targets and help text. |
| Modify | `scripts/README.md` | Document the generator and dbt Section 03 command surfaces. |
| Modify | `README.md` | Add the reproducible Section 03 path and remove the obsolete drift-out-of-scope statement. |
| Modify | `configs/scenarios/README.md` | Document the implemented scenario and canonical YAML ownership. |
| Modify | `deliverables/03_data_generator_improvement.md` | Replace the placeholder with decisions, contracts, commands, evidence, thresholds, limitations, and Feast boundary. |
| Modify | `architecture/masterplan.md` | Mark Section 03 drift/labels implemented without claiming ML or Feast runtime completion. |
| Modify | `architecture/domain/business-context.md` | Describe the campaign scenario and AI impact without changing unrelated domain assumptions. |
| Modify | `architecture/diagrams/schema_design.puml` | Add the Section 03 Gold feature, label, monitoring, alert, and training relationships to the canonical schema diagram source. |
| Modify | `architecture/diagrams/erd/physical_gold_model.puml` | Add four Gold entities and their feature/label/monitoring relationships. |
| Modify | `architecture/diagrams/erd/gold_layer_ERD.dbml` | Mirror the four tables, keys, fields, and relationships in DBML. |
| Modify | `tests/unit/test_section02_schema_design.py` | Extend physical-schema assertions for the four new Gold contracts without weakening Section 02 checks. |
| Modify | `tests/unit/test_datahub_capture_evidence.py` | Expect assertions and evidence for every expanded DP3 output. |
| Regenerate | `evidence/03_data_generator_improvement/runs/<bundle_id>/config_snapshot.yaml` | Canonical parsed configuration and resolved window snapshot. |
| Regenerate | `evidence/03_data_generator_improvement/runs/<bundle_id>/ml_customer_label.csv` | Exact unique two-column label output. |
| Regenerate | `evidence/03_data_generator_improvement/runs/<bundle_id>/agg_feature_health_daily.csv` | Daily feature distribution and PSI evidence. |
| Regenerate | `evidence/03_data_generator_improvement/runs/<bundle_id>/feature_drift_alerts.csv` | Alert-level PSI rows. |
| Regenerate | `evidence/03_data_generator_improvement/runs/<bundle_id>/ml_customer_purchase_training.csv` | Feast-ready cutoff-safe feature/label join. |
| Regenerate | `evidence/03_data_generator_improvement/runs/<bundle_id>/sample_rows/*.csv` | Deterministic 20-row samples sorted by stable keys. |
| Regenerate | `evidence/03_data_generator_improvement/runs/<bundle_id>/section03_config_and_training_join.png` | E32 image showing config and merged output. |
| Regenerate | `evidence/03_data_generator_improvement/runs/<bundle_id>/section03_report.md` | Scenario rationale, measured rates, PSI, labels, leakage policy, and limitations. |
| Regenerate | `evidence/03_data_generator_improvement/section03_candidate_manifest.json` | Atomic pointer/manifest for the latest generator-only pending candidate; never replaces a prior verified root. |
| Regenerate | `evidence/03_data_generator_improvement/section03_manifest.json` | Authoritative strict verified inventory, schemas, counts, windows, runtime proofs, checks, and source config path; absent until the first complete finalization. |
| Regenerate | `evidence/03_data_generator_improvement/runs/<bundle_id>/runtime/spark/run_manifest.json` | Real seven-table Spark/dbt/generator keyed-parity proof and transitive artifact inventory imported only during finalization. |
| Regenerate | `evidence/03_data_generator_improvement/runs/<bundle_id>/runtime/airflow/run_manifest.json` | Real six-task Airflow run and hash-bound seven-table DP3 validation imported only during finalization. |
| Regenerate | `evidence/03_data_generator_improvement/runs/<bundle_id>/runtime/datahub/lineage.json` | Indexed seven-output DataHub lineage/assertion proof imported only during finalization. |

## Exact Interfaces and Algorithms

### Configuration contract

Add these types to `generators/config.py`; field names are also the canonical YAML keys:

```python
DriftScenario = Literal["customer_order_frequency"]
DriftMode = Literal["abrupt"]


@dataclass(frozen=True)
class DriftConfig:
    enabled: bool
    scenario: DriftScenario
    cutoff_fraction: float
    mode: DriftMode
    post_rate_multiplier: float
    psi_warning: float
    psi_alert: float
    label_horizon_days: int


@dataclass(frozen=True)
class GeneratorConfig:
    # Preserve every current field in its current order.
    drift: DriftConfig
    section03_evidence_root: Path
```

Add this exact mapping to `configs/generator/base.yaml`:

```yaml
outputs:
  raw_root: data/raw
  evidence_root: evidence/01_data_generator
  section03_evidence_root: evidence/03_data_generator_improvement

drift:
  enabled: true
  scenario: customer_order_frequency
  cutoff_fraction: 0.65
  mode: abrupt
  post_rate_multiplier: 1.5
  psi_warning: 0.10
  psi_alert: 0.15
  label_horizon_days: 7
```

Implement `_parse_drift_config(value: Any) -> DriftConfig`. Its key set is exactly the eight dataclass fields: reject every missing or unknown key, reject non-mappings and non-boolean `enabled`, and accept only the one scenario/mode. Every numeric field rejects booleans and nonfinite values before comparing against the approved fixed contract: `cutoff_fraction == 0.65`, `post_rate_multiplier == 1.5`, `psi_warning == 0.10`, `psi_alert == 0.15`, and a non-boolean integer `label_horizon_days == 7`. `enabled` may be `false` solely for legacy-equivalence runs; all seven remaining values stay fixed. Error messages name the dotted key and required value, for example `drift.cutoff_fraction must equal 0.65`. Runtime windows and thresholds are still derived from the validated `DriftConfig`; no consumer repeats magic literals.

When `evidence_root` is not overridden, resolve `section03_evidence_root` from `outputs.section03_evidence_root`. When tests or callers override `evidence_root`, resolve Section 03 evidence under `<evidence_root>/section03` so isolated runs never write canonical repository evidence.

### Runtime-window and drift sampling contract

Add these frozen values and functions to `generators/drift.py`:

```python
@dataclass(frozen=True)
class DriftWindow:
    start_ts: pd.Timestamp
    end_ts: pd.Timestamp
    drift_start_ts: pd.Timestamp
    feature_cutoff_ts: pd.Timestamp
    label_end_ts: pd.Timestamp
    baseline_date: date


@dataclass(frozen=True)
class DriftRateSummary:
    pre_count: int
    post_count: int
    pre_duration_days: float
    post_duration_days: float
    pre_rate_per_day: float
    post_rate_per_day: float
    normalized_post_pre_ratio: float


def resolve_drift_window(config: GeneratorConfig) -> DriftWindow: ...


def generate_order_timestamps_with_drift(
    rng: np.random.Generator,
    *,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
    size: int,
    drift: DriftConfig,
) -> pd.Series: ...


def summarize_drift_rates(
    timestamps: pd.Series,
    *,
    window: DriftWindow,
) -> DriftRateSummary: ...
```

Disabled behavior is exactly:

```python
if not drift.enabled:
    return random_timestamps(rng, start_ts, end_ts, size, evening_bias=True)
```

The disabled branch performs no random call, allocation, sort, or validation after entering the function before delegating. This preserves the current RNG stream for order items, payments, shipments, duplicates, and streaming events.

Enabled behavior must change timestamps without perturbing later stochastic decisions. Canonicalize and hash the supplied RNG's pre-call `bit_generator.state` with namespace `section03-order-timestamps-v1` to seed an isolated child `np.random.Generator`. Then call the unchanged legacy `random_timestamps(rng, start_ts, end_ts, size, evening_bias=True)` once and discard its values solely to advance the shared RNG by exactly the legacy amount; tests byte-compare the resulting shared RNG state with a direct legacy call. Use only the child RNG for the drift sampler below—never draw an extra value from the shared RNG.

The drift sampler uses one-minute candidate slots from `start_ts.floor("min")` through `end_ts.floor("min")`. Retain the current 24 hourly weights. For slot `t`, calculate `raw_weight[t] = hourly_weight[t.hour] * (drift.post_rate_multiplier if t >= drift_start_ts else 1.0)`, then calculate `probability = raw_weight / raw_weight.sum()`. Sample `size` slot indices with replacement using the isolated child RNG, add child-RNG seconds in `[0, 59]`, clip to the current inclusive generator bounds, and return a stable `pd.Series` in draw order. Do not round the cutoff to a day.

Rate evidence uses exact elapsed seconds on each side of `drift_start_ts`; it reports `(post_count / post_duration_days) / (pre_count / pre_duration_days)`. The canonical medium/seed-42 acceptance interval is inclusive `[1.35, 1.65]`.

### Label and feature/label join contract

Add these functions to `generators/labels.py`:

```python
LABEL_COLUMNS: tuple[str, str] = ("id", "label")


def build_purchase_labels(
    customers: pd.DataFrame,
    payments: pd.DataFrame,
    *,
    window: DriftWindow,
) -> pd.DataFrame: ...


def build_point_in_time_customer_features(
    customers: pd.DataFrame,
    orders: pd.DataFrame,
    payments: pd.DataFrame,
    commerce_events: pd.DataFrame,
    *,
    window: DriftWindow,
) -> pd.DataFrame: ...


def normalize_commerce_events_for_features(
    topic_events: Mapping[str, pd.DataFrame],
) -> pd.DataFrame: ...


def build_feature_label_join(
    labels: pd.DataFrame,
    features: pd.DataFrame,
) -> pd.DataFrame: ...
```

`build_purchase_labels` filters to `customers.created_ts <= window.feature_cutoff_ts`, then starts from unique non-null `customer_id` values in that prediction-time cohort. It detects successful payments using the exact horizon and availability predicates in Time and Boundary Semantics, left-joins positives back to every eligible customer, fills absence with `0`, casts `id` to Pandas `string` and `label` to `int8`, sorts by `id`, resets the index, and returns `list(frame.columns) == ["id", "label"]`. Duplicate/null IDs or a null/unparseable `created_ts` raise `ValueError` rather than being silently collapsed.

`build_point_in_time_customer_features` uses the same eligible-customer predicate and returns one row per eligible cohort ID at the single cutoff. Total-order and category features use eligible orders; paid-revenue and AOV features require a successful payment known by the cutoff; stream features use only eligible commerce events and the latest cutoff-safe hour. Eligible customers without activity receive numeric zeroes. `event_timestamp` and `created` are both the feature snapshot/materialization time `feature_cutoff_ts`; source availability is enforced separately with `source.created_ts <= feature_cutoff_ts`.

`normalize_commerce_events_for_features` is the one generator/Spark/dbt normalization contract. It selects only the raw `commerce_events` topic, parses dict-or-JSON `correlation_ids`/`payload`, extracts `customer_id`, `order_id`, `product_id`, and the feature-relevant payload fields with the same correlation-first/coalesce rules as `stg_commerce_events`, and converts event/created/ingest timestamps to UTC. For duplicate `event_id`, rank by `created_ts DESC`, `ingest_ts DESC`, then `event_timestamp DESC`; collapse byte-identical ties, but fail when tied winners differ in any normalized field. Generator evidence must call this adapter rather than consume raw nested topic rows. Spark and dbt use the same rank order and an ambiguity assertion, so intentional duplicates cannot make the three feature paths diverge.

`build_feature_label_join` validates the exact label schema and unique key, performs a validated `one_to_one` inner merge on `id`, returns columns in the exact training order below, and raises if any label lacks a feature row.

### PSI and daily monitoring contract

Add this exact public calculation interface to `generators/drift.py`:

```python
def calculate_psi(
    baseline: pd.Series,
    current: pd.Series,
    *,
    quantile_bins: int = 10,
    epsilon: float = 1e-6,
) -> float: ...
```

The function converts values to finite `float64`, rejects an empty input, requires `quantile_bins >= 2` and `0 < epsilon < 1`, and computes baseline edges at quantiles `0.0, 0.1, ..., 1.0` with exact Hyndman-Fan type 7 interpolation: for sorted zero-based values, `h=(n-1)*q`, `j=floor(h)`, and `x[j] + (h-j)*(x[min(j+1,n-1)]-x[j])`. Spark and dbt implement this formula from row numbers and arithmetic; approximate percentile functions are forbidden. Remove duplicate interior edges. If the baseline is constant, retain its value as one interior split. Apply `np.nextafter(edge, np.inf)` in Python and the equivalent SQL predicate `lower_edge < value AND value <= upper_edge`, so observations equal to a boundary remain in the lower bin, then add unbounded endpoints. Histogram both inputs with those same edges. Divide counts by each input length, replace zero proportions with `epsilon`, renormalize each probability vector to sum to one, and return:

```python
float(np.sum((current_p - baseline_p) * np.log(current_p / baseline_p)))
```

Round persisted PSI and every parity aggregate to 12 decimal places with round-half-even; return `0.0` for identical distributions after that rounding. The constant-zero-baseline/current-positive case must remain finite and positive; zero bins must never produce infinity or `NaN`. Cross-engine fixtures include odd/even lengths, repeated edges, boundary equality, zero bins, and a constant baseline; absolute parity tolerance remains `1e-9` only after this shared algorithm and rounding.

Add to `drift_evidence.py`:

```python
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


def build_feature_health_daily(
    customers: pd.DataFrame,
    orders: pd.DataFrame,
    *,
    window: DriftWindow,
    drift: DriftConfig,
) -> pd.DataFrame: ...


def build_feature_drift_alerts(
    feature_health: pd.DataFrame,
    *,
    alert_threshold: float,
) -> pd.DataFrame: ...


def write_section03_evidence(
    config: GeneratorConfig,
    datasets: Mapping[str, pd.DataFrame],
    topic_events: Mapping[str, pd.DataFrame],
) -> DriftEvidenceResult: ...
```

For each monitoring date, `build_feature_health_daily` first freezes the population to customers whose `created_ts` is known by `baseline_date 23:59:59.999999`. Define `window_start` as midnight UTC six dates before the monitoring date and `window_end` as that date's `23:59:59.999999` UTC. For every frozen customer count orders with `window_start <= order_timestamp <= window_end` and `order.created_ts <= window_end`; use these exact predicates in Python, Spark, and dbt. Compare that distribution with the identically sized seven-day window ending on `baseline_date`, persist `feature_name="f_customer_order_frequency_7d"` and `window_days=7`, and assign `stable`, `warning`, or `alert` with inclusive thresholds. `customer_count` is constant on every health row. A deterministic multiplier-1 control fixture must return the same baseline/current distributions and PSI `0.0`; it prevents an expanding-history implementation from passing. `build_feature_drift_alerts` returns only `psi_value >= alert_threshold` rows and the exact action `Investigate customer_order_frequency drift`.

### Preserved generator entry point

The definition in `runner.py` must remain textually compatible with this signature:

```python
def run_generation(
    *,
    config_path: str | Path,
    scale: str,
    mode: GenerationMode,
    raw_root: str | Path | None = None,
    evidence_root: str | Path | None = None,
    seed: int | None = None,
    clean: bool = False,
    publish_kafka: bool = False,
    kafka_bootstrap_servers: str | None = None,
    kafka_flush_timeout_seconds: float = 30.0,
) -> GenerationResult:
```

For `mode in {"offline", "full"}` with drift enabled, call `write_section03_evidence` only after payments have updated order status and, for `full`, after commerce events exist. For offline-only mode, pass an empty commerce frame and emit zero-valued stream features. Prefix merged `GenerationResult.evidence_paths` keys with `section03_` and leave `GenerationResult.evidence_root` pointing to the existing Section 01 root.

### Spark/dbt parameter and model contract

Add to `lakehouse/spark/sql.py`:

```python
@dataclass(frozen=True)
class Section03SqlParameters:
    drift_start_ts: str
    feature_cutoff_ts: str
    label_end_ts: str
    baseline_date: str
    psi_warning: float
    psi_alert: float
    psi_epsilon: float = 1e-6
    psi_quantile_bins: int = 10


def ordered_feature_queries(
    parameters: Section03SqlParameters,
) -> list[tuple[str, str]]: ...


def ordered_gold_queries(
    parameters: Section03SqlParameters,
) -> list[tuple[str, str]]: ...
```

Keep `ordered_core_gold_queries()` argument-free. `run_job()` loads `configs/generator/base.yaml` by default, derives `Section03SqlParameters` through the same window rules, and passes it for `full` and `features` stages. The ordered feature group is exactly `feat_customer_90d`, `feat_stream_60m`, `feat_customer_unified`, `ml_customer_label`, `agg_feature_health_daily`, `feature_drift_alerts`, `ml_customer_purchase_training`.

Define `DP3_GOLD_TABLES` in `spark/constants.py` as that exact ordered tuple. Add the four new outputs to `GOLD_SERVING_TABLES`, derive `REQUIRED_GOLD_TABLES` once, and assert uniqueness. `ordered_feature_queries(parameters)` must return exactly `DP3_GOLD_TABLES`; `ordered_core_gold_queries()` must return every required Gold query not in `DP3_GOLD_TABLES`. Do not use a `name.startswith("feat_")` split because labels, monitoring, alerts, and training are DP3 outputs despite their names.

Spark SQL literals come only from validated `Section03SqlParameters`. dbt has no fallback values for these vars: `run_section03_dbt.py` must supply the same names as JSON parsed from generator YAML, invoke dbt without a shell string, and propagate a nonzero exit code. Spark and dbt implement the same eligible-customer cohorts, availability predicates, baseline quantile boundaries, duplicate-edge collapse, `epsilon=1e-6`, renormalization, and inclusive status thresholds.

## Exact Output Schemas

### Section 03 CSV artifacts and matching Gold tables

| Output | Ordered columns and logical types | Key/invariant |
| --- | --- | --- |
| `ml_customer_label` | `id string`, `label int8/integer` | Exactly two columns; `id` non-null and unique; `label in {0,1}`. |
| `agg_feature_health_daily` | `monitoring_date date`, `feature_name string`, `window_days int32/integer`, `baseline_date date`, `customer_count int64/bigint`, `mean_value float64/double`, `stddev_value float64/double`, `psi_vs_baseline float64/double`, `drift_status string`, `warning_flag bool`, `alert_flag bool` | Key `(monitoring_date, feature_name)`; feature name always `f_customer_order_frequency_7d`, window exactly `7`; `customer_count` is the constant baseline-known cohort size; PSI finite and non-negative. |
| `feature_drift_alerts` | `alert_date date`, `feature_name string`, `psi_value float64/double`, `threshold float64/double`, `action string` | Key `(alert_date, feature_name)`; every PSI `>= 0.15`; threshold exactly `0.15`. |
| `ml_customer_purchase_training` | `id string`, `event_timestamp timestamp`, `label int8/integer`, `f_customer_total_orders_90d int64/bigint`, `f_customer_paid_revenue_90d float64/double`, `f_customer_avg_order_value_90d float64/double`, `f_customer_distinct_categories_90d int64/bigint`, `f_stream_views_60m int64/hugeint`, `f_stream_add_to_cart_60m int64/hugeint`, `f_stream_checkout_started_60m int64/hugeint`, `f_stream_order_placed_60m int64/hugeint`, `f_stream_cart_to_purchase_ratio_60m float64/double`, `created timestamp` | `id` non-null and unique and belongs to the cutoff-known cohort; every `event_timestamp` and `created` equals the fixed cutoff; exact label equality with `ml_customer_label`. |

`stddev_value` is the population standard deviation (`ddof=0`; Spark/dbt use `stddev_pop`), with an empty cohort rejected and a singleton cohort defined as `0.0`. Generator, Spark, and dbt canonicalize every health-table floating field with decimal round-half-even to 12 decimal places before equality checks. Health CSV uses fixed `%.12f`; other floats use stable `%.12g`. CSV dates use `YYYY-MM-DD`; timestamps use UTC ISO-8601 with `Z`; every CSV has UTF-8 headers, LF line endings, and no index. Empty alert output still contains its exact header.

### `config_snapshot.yaml`

Write these top-level keys in order: `schema_version`, `section`, `source_config_path`, `source_config_sha256`, `platform_name`, `scale`, `random_seed`, `history_days`, `entities`, `start_ts`, `end_ts`, `drift_start_ts`, `feature_cutoff_ts`, `label_end_ts`, `baseline_date`, `drift`. The nested drift mapping repeats every `DriftConfig` field. `source_config_path` is repository-relative with forward slashes, `source_config_sha256` hashes the exact YAML bytes parsed for the run, and timestamps are UTC ISO-8601 strings.

### Candidate and verified manifests

The evidence root contains immutable `runs/<bundle_id>/` directories, a generator-only `section03_candidate_manifest.json`, and the authoritative verified `section03_manifest.json`. Generation writes and verifies `runs/.staging-<uuid>/`, derives a candidate `bundle_id` as the lowercase SHA-256 of the sorted eleven-key generator artifact-hash inventory, renames the directory to `runs/<bundle_id>/`, and atomically replaces only the candidate pointer. It never creates or replaces the authoritative root. The verified root is absent before the first successful finalization, and any later generation or failed runtime capture leaves the prior verified root and bundle byte-for-byte intact.

Both manifest forms have exact top-level keys `schema_version`, `section`, `generated_at`, `source_config_path`, `source_config_sha256`, `bundle_id`, `previous_bundle_id`, `config_snapshot`, run identity (`scale`, `random_seed`, `history_days`), `windows`, `drift_config`, `configured_entity_counts`, `observed_entity_counts`, `rate_summary`, `consumer_contract`, `rubric_cells`, `checks`, `runtime_evidence`, and `artifacts`. `consumer_contract` declares the exact ordered `id,label` schema/path/hash; the `ml_customer_purchase_training` path/hash, entity key, event-time cutoff, and point-in-time rule; and the `agg_feature_health_daily` path/hash/schema, fixed `baseline_date`, available monitoring-date range, cohort size, feature name, and 0.10/0.15 status semantics. `checks` has exact booleans `configured_counts_preserved`, `streaming_distribution_inherited`, `labels_exact_schema`, `labels_unique`, `labels_binary`, `training_join_one_to_one`, `point_in_time_safe`, `psi_finite`, and `alert_threshold_respected`; writing either form raises if any is false.

A candidate has `runtime_evidence={"status":"pending","spark":null,"airflow":null,"datahub":null}` and exactly the eleven generator artifacts. Its `rubric_cells` contains E32/E33/E34 with points 1/1/2, `status: "Candidate"`, required checks, and artifact keys; it earns zero until finalization. `verify_section03_manifest.py --allow-runtime-pending` accepts this state only when the input basename is exactly `section03_candidate_manifest.json`; it rejects that flag for the authoritative root.

The finalizer accepts the candidate manifest plus three completed capture roots. It independently verifies each top manifest and its transitive inventory, copies generator and capture artifacts into a fresh final staging directory, replaces the report's three Pending runtime sections with measured Spark/dbt, Airflow, and DataHub summaries, and adds exact top-level artifact keys `spark_runtime_manifest`, `airflow_runtime_manifest`, and `datahub_lineage`. It sets `runtime_evidence.status="verified"`; the `spark`, `airflow`, and `datahub` objects each repeat the corresponding artifact key, relative path, size, and SHA-256 exactly. The final `bundle_id` is recalculated over the complete fourteen-key inventory, including the updated report hash and the three runtime top-manifest hashes; after deriving it, the finalizer rewrites every manifest artifact path and repeated `consumer_contract`/`runtime_evidence` path from the candidate directory to `runs/<final_bundle_id>/` and verifies those bindings. Artifact content must not embed `bundle_id`, avoiding a circular content identity. Every runtime verifier recursively checks the top manifest's internal relative paths, sizes, hashes, run identity, config hash, scale, cutoff, and success status before promotion.

Generation and finalization serialize candidate-pointer and root-manifest mutation with an exclusive `section03.lock`. `clean` is an execution option, never a manifest field. During generation, `clean=True` may remove abandoned staging directories and stale bundles referenced by neither the authoritative active/previous manifests nor the newly verified candidate, but only after the replacement candidate pointer is atomically installed. It cannot delete the authoritative root or either retained verified bundle.

Only after strict verification of the temporary final root succeeds does the finalizer rename the staging directory. While still holding the lock, it re-reads `section03_candidate_manifest.json` immediately before authoritative promotion and requires its manifest hash and `bundle_id` to equal the consumed candidate; a mismatch aborts before `os.replace`, exits nonzero, and preserves the prior verified root, pointer, and bundles. It then atomically replaces `section03_manifest.json`; from that instant the newly promoted root is authoritative and is never rolled back by housekeeping. Post-promotion pointer deletion and optional cleanup are best-effort, non-fatal housekeeping: unlink the candidate pointer only if it still has the consumed identity, never delete its bundle if pointer deletion failed or identity changed, and emit an explicit warning while returning success because strict evidence promotion already completed. With `--clean`, remove the consumed candidate bundle only when it is neither the new active nor `previous_bundle_id`, then remove abandoned staging/unreferenced candidates while retaining the active plus one previous verified bundle. Without `--clean`, remove the consumed pointer when safe but retain its unreferenced bundle for diagnosis. Any pre-promotion failure preserves the old root and can leave one pending candidate; any post-promotion housekeeping warning preserves the new valid root and every uncertain pointer/bundle.

Use these exact `consumer_contract` keys; every repeated path/hash must equal the matching `artifacts` entry or verification fails:

```json
{
  "schema_version": 1,
  "label": {"artifact_key": "labels", "path": "runs/<bundle_id>/ml_customer_label.csv", "sha256": "<64 lowercase hex>", "columns": ["id", "label"], "entity_key": "id"},
  "training_join": {"artifact_key": "training_join", "path": "runs/<bundle_id>/ml_customer_purchase_training.csv", "sha256": "<64 lowercase hex>", "entity_key": "id", "event_timestamp_column": "event_timestamp", "feature_cutoff_ts": "<UTC ISO-8601>", "point_in_time_rule": "event_timestamp <= as_of and created <= event_timestamp"},
  "feature_health": {"artifact_key": "feature_health_daily", "path": "runs/<bundle_id>/agg_feature_health_daily.csv", "sha256": "<64 lowercase hex>", "feature_name": "f_customer_order_frequency_7d", "window_days": 7, "baseline_date": "<YYYY-MM-DD>", "monitoring_start": "<YYYY-MM-DD>", "monitoring_end": "<YYYY-MM-DD>", "cohort_size": 1, "psi_column": "psi_vs_baseline", "status_column": "drift_status", "warning_threshold": 0.10, "alert_threshold": 0.15}
}
```

Angle-bracketed values above are generated typed values, not plan-time evidence or text to copy literally. Each `rubric_cells` value has exact keys `points`, `status`, `required_checks`, and `artifact_keys`; candidate status is `Candidate`, while final status is `Satisfied` only when every named check, all three recursive runtime proofs, and every named artifact binding verify.

The exact generator artifact-key set is `config_snapshot`, `labels`, `feature_health_daily`, `drift_alerts`, `training_join`, `labels_sample`, `feature_health_sample`, `drift_alerts_sample`, `training_sample`, `evidence_image`, and `quality_report`; the exact verified set adds `spark_runtime_manifest`, `airflow_runtime_manifest`, and `datahub_lineage`. Each value contains a forward-slash path below `runs/<bundle_id>/` relative to its root manifest, integer `row_count` for tabular artifacts, ordered `columns` for tabular artifacts, integer `size_bytes`, and lowercase SHA-256 `sha256`. Reject absolute paths, drive-qualified paths, empty segments, symlinks, and `..`; resolve and verify that every artifact stays below the named immutable bundle. Hash every final artifact except the root manifest after writing; sort artifact keys before JSON serialization.

### Samples, image, and report

- Write 20-row samples under `sample_rows/`, sorted by `id`; health and alert samples sort by date then feature name. Samples retain the full parent schema.
- Render `section03_config_and_training_join.png` at 1600x900 using Pillow and the bundled font fallback. The left panel lists the eight approved drift values and resolved windows; the right panel renders the first ten training rows including `id`, `label`, cutoff timestamp, and `f_customer_total_orders_90d`. A footer names both source CSVs. This is deterministic evidence visualization, not a claim of a live Feast UI.
- `section03_report.md` is the required Section 03 quality report. It contains Run Context, Scenario and Rationale, Fixed Counts, Realized Pre/Post Rates, Point-in-Time and Label Policy, Daily PSI Summary, Alerts, Exact Label Contract, Feast-ready Training Join, Quality Checks, Spark/dbt Parity Runtime, Airflow DP3 Runtime, DataHub Lineage Runtime, Sheet3 E32-E34 Evidence, Reproduction Commands, and Limitations in that order. All three runtime sections remain explicitly `Pending` in a candidate and are replaced only from verified captures during finalization.

## Evidence Contract

The canonical root is `evidence/03_data_generator_improvement`. Only its strict `section03_manifest.json` is authoritative and it points to one verified immutable bundle; the candidate manifest is diagnostic and cannot satisfy a rubric cell or unblock Section 04.2. The configuration snapshot proves E33; exact label CSV proves E34; the PNG, samples, measured rates, health, alerts, and training join prove E32; strict Spark, Airflow, and DataHub runtime bindings prove the downstream contracts actually executed. The report distinguishes configured targets from measured seed-42 values. It must not describe generated numbers before final promotion succeeds.

The canonical run is `scale=medium`, `mode=full`, `seed=42`. Smoke runs are test fixtures only. Evidence regeneration is successful only if configured order/customer/product/seller/promotion counts match the manifest, the normalized post/pre rate is within `[1.35, 1.65]`, at least one warning-or-alert day exists, labels and training rows are nonempty and unique, all cutoff/leakage checks pass, Spark/Airflow/DataHub runtime status is verified, and every direct and transitive bundle/runtime hash validates.

## Ordered Tasks

### Task 1: Lock the typed configuration and validation contract

**Files:**
- Modify: `configs/generator/base.yaml`
- Modify: `src/vina_bim_shop/generators/config.py`
- Modify: `tests/unit/test_generator_config.py`

**Interfaces:**
- Produces: `DriftConfig`, `GeneratorConfig.drift`, and `GeneratorConfig.section03_evidence_root` used by every later task.
- Preserves: all existing `load_generator_config(...)` parameters and current scale/output override behavior.

- [ ] **Step 1: Record the pre-change configuration baseline.**

Run:

```text
rtk uv run pytest tests/unit/test_generator_config.py tests/integration/test_section01_generator.py -q
```

Expected: current tests pass before the new assertions are added; retain the output in the implementation handoff notes, not in generated evidence.

- [ ] **Step 2: Add failing tests for approved values and validation.**

Assert the loaded smoke config has the eight exact drift values, `history_days == 14`, all pre-existing entity counts unchanged, and an isolated `section03_evidence_root == tmp_path / "evidence" / "section03"` when the Section 01 evidence root is overridden. Parametrize one missing and one unknown key, non-boolean enabled, unsupported scenario/mode, booleans/NaN/infinity for every numeric field, and legal-looking but unapproved values (`cutoff_fraction=0.50`, `post_rate_multiplier=2.0`, `psi_warning=0.09`, `psi_alert=0.16`, `label_horizon_days=8`); match the exact dotted-key/required-value errors defined above.

Run:

```text
rtk uv run pytest tests/unit/test_generator_config.py -q
```

Expected: FAIL because `DriftConfig` and the YAML mapping do not exist.

- [ ] **Step 3: Add the exact YAML mapping and minimal typed parser.**

Implement `_parse_drift_config`, attach its result to `GeneratorConfig`, resolve the Section 03 root according to the override rule, and change only the smoke history from 7 to 14 days. Do not generalize other untyped configuration groups or alter any entity count.

- [ ] **Step 4: Run the focused configuration tests.**

Run:

```text
rtk uv run pytest tests/unit/test_generator_config.py -q
```

Expected: PASS; every invalid mapping raises its exact key-specific `ValueError` and the approved config loads unchanged.

### Task 2: Redistribute timestamps without changing counts or disabled output

**Files:**
- Create: `src/vina_bim_shop/generators/drift.py`
- Modify: `src/vina_bim_shop/generators/offline/orders.py`
- Create: `tests/unit/test_section03_drift.py`
- Modify: `tests/unit/test_generator_module_split.py`

**Interfaces:**
- Consumes: `DriftConfig` and existing `random_timestamps` hourly weights.
- Produces: `DriftWindow`, `DriftRateSummary`, `resolve_drift_window`, `generate_order_timestamps_with_drift`, and `summarize_drift_rates`.
- Preserves: `generate_orders(...)`, `_generate_orders(...)`, offline compatibility exports, and configured row counts.

- [ ] **Step 1: Write deterministic-window and sampling tests.**

Use fixed timestamps and seeded `np.random.default_rng` instances. Assert exact resolved windows, same-seed frame equality, different-seed inequality, fixed length, bounds, and stable draw order. Compare the shared RNG state after enabled sampling with the state after exactly one direct legacy timestamp call from the same pre-state. For a medium-like `size=45_000`, assert `1.35 <= normalized_post_pre_ratio <= 1.65` and both sides contain rows. Spy on `resolve_drift_window` and the sampler inputs to prove the validated `DriftConfig` object supplies the cutoff, multiplier, horizon, and thresholds; parser rejection of every alternative value prevents hidden literals from becoming a second deployment contract.

- [ ] **Step 2: Write the disabled-equivalence regression.**

Generate expected offline datasets while monkeypatching the new timestamp hook to call the pre-change `random_timestamps(..., evening_bias=True)`. Generate actual datasets with identical config/seed and `drift.enabled=false`. Use `pd.testing.assert_frame_equal(..., check_like=False, check_exact=True)` for every returned dataset. Write both through the actual production writer into separate temporary roots and compare relative inventories plus bytes for its deterministic Parquet, JSON, JSONL, and CSV outputs; semantic frame equality remains the gate only for a format whose repository writer embeds nondeterministic metadata. Also assert all configured entity counts and order-dependent row counts match.

Run:

```text
rtk uv run pytest tests/unit/test_section03_drift.py -q
```

Expected: FAIL on imports for the missing drift module/functions.

- [ ] **Step 3: Implement only the approved abrupt reweighting.**

Implement the candidate-slot/isolated-child/shared-RNG-advance algorithm exactly as specified, keep the disabled delegation first, and replace only the order timestamp assignment in `_generate_orders`. Add an enabled-versus-legacy end-to-end projection test keyed by stable IDs: exclude only timestamp fields and fields deterministically derived from timestamps, then require exact equality for customer/product/order-item choices, customer affinity/category/coupon choices, payment success/method/amount, shipment carrier/outcome, duplicate/schema-evolution decisions, and streaming event type/payload identities. A difference proves shared-RNG leakage and fails even if the rate ratio passes.

- [ ] **Step 4: Verify drift, equivalence, counts, and module boundaries.**

Run:

```text
rtk uv run pytest tests/unit/test_section03_drift.py tests/unit/test_generator_module_split.py -q
```

Expected: PASS; enabled output is reproducible and within ratio tolerance while preserving the legacy post-timestamp RNG state/non-time choices, disabled production outputs equal the legacy path, the three focused modules satisfy the real split-test rules, and all legacy imports remain available.

### Task 3: Build labels, point-in-time features, PSI, and alerts in memory

**Files:**
- Modify: `src/vina_bim_shop/generators/drift.py`
- Create: `src/vina_bim_shop/generators/labels.py`
- Create: `src/vina_bim_shop/generators/drift_evidence.py`
- Modify: `tests/unit/test_section03_drift.py`

**Interfaces:**
- Consumes: generator customers/orders/payments/commerce events and `DriftWindow`.
- Produces: the three label/feature functions, `calculate_psi`, daily health, alerts, and `DriftEvidenceResult` writer interface.

- [ ] **Step 1: Add exact label and leakage fixtures.**

Create a small fixture containing: one successful payment just before cutoff, one exactly at cutoff, one one second after cutoff, one exactly at horizon end, one one second after horizon, one failed payment, one late-created payment, an eligible customer with no payment, a customer created one second after the cutoff, and duplicate/null/unparseable customer-ID/time error cases. Assert only the two valid post-cutoff successful purchases label positive, every cutoff-known customer appears once, the future-created customer is absent, types are string/int8, and the output columns equal `LABEL_COLUMNS` exactly.

- [ ] **Step 2: Add point-in-time feature/join tests.**

Place customer creation, orders, payments, and events on both sides of the event-time and created-time cutoffs. Assert post-cutoff rows cannot change any feature, a later-created customer is absent from both labels and features, an eligible inactive customer remains with all-zero features, `created == event_timestamp == feature_cutoff_ts`, the PSI customer count stays constant at the baseline-known cohort size, merge validation is one-to-one, output order matches the schema table, and labels equal the exact two-column source.

- [ ] **Step 3: Add PSI zero-bin and threshold tests.**

Assert identical arrays return `0.0`; a constant-zero baseline versus positive current values returns finite positive PSI; repeated quantiles produce strictly increasing effective edges; empty/nonfinite-only inputs and invalid epsilon/bin counts raise; and statuses are `stable` at `0.099999`, `warning` at `0.10` and `0.149999`, and `alert` at `0.15`. Build an exact seven-day baseline/current fixture with the same stationary order pattern (equivalent raw multiplier 1.0) and require identical counts/PSI zero; add one older order outside each window and prove neither result changes. A resolved enabled history without seven complete pre-cutoff days must fail before generation.

Run:

```text
rtk uv run pytest tests/unit/test_section03_drift.py -q
```

Expected: FAIL because the label, PSI, health, and alert functions are absent.

- [ ] **Step 4: Implement the minimal pure builders.**

Implement the exact predicates, types, order, baseline-bin algorithm, and status boundaries. Keep file writing out of these pure builders so Spark/dbt fixture tests can use their results as a reference oracle.

- [ ] **Step 5: Run the complete pure-contract suite.**

Run:

```text
rtk uv run pytest tests/unit/test_section03_drift.py -q
```

Expected: PASS, including zero bins, horizon edges, created-time leakage, and threshold inclusivity.

### Task 4: Integrate section-specific artifacts with the unchanged runner and CLI

**Files:**
- Modify: `src/vina_bim_shop/generators/drift_evidence.py`
- Modify: `src/vina_bim_shop/generators/runner.py`
- Modify: `src/vina_bim_shop/generators/writer.py`
- Modify: `scripts/generate/run_generator.py`
- Create: `scripts/generate/verify_section03_manifest.py`
- Create: `tests/unit/test_section03_manifest_verifier.py`
- Create: `tests/integration/test_section03_generator.py`
- Modify: `tests/integration/test_generator_cli.py`
- Modify: `tests/integration/test_section01_generator.py`

**Interfaces:**
- Consumes: all Task 3 builders and current in-memory generator results.
- Produces: the complete artifact tree and `section03_*` entries in `GenerationResult.evidence_paths`.
- Preserves: the exact `run_generation()` signature and all existing Section 01 artifacts/keys.

- [ ] **Step 1: Add a signature and artifact contract test.**

Use `inspect.signature(run_generation)` to compare the ordered parameters/defaults to the preserved signature. Run the now-14-day smoke/full profile into a temporary root and also run the canonical medium fixture; assert the Section 03 tree, exact CSV columns/types, exact eligible-cohort label uniqueness, stable sample sorting, nonempty labels/training, finite PSI, alert threshold, population-standard-deviation/singleton behavior, image dimensions, required quality-report headings, the exact E32/E33/E34 `rubric_cells`, the embedded `consumer_contract`, and all manifest checks/hashes. Normalize raw nested/duplicated commerce events through the specified adapter. Join order-derived events back to their originating order ID, prove the configured lead/lag offsets are unchanged, require same-side assignment only for orders farther from `drift_start_ts` than the maximum event lead/lag, and explicitly allow legitimate boundary-crossing events inside that buffer. For canonical medium evidence, require at least 100 order-derived events on each side and `abs(stream_normalized_post_pre_ratio - order_normalized_post_pre_ratio) <= 0.20`; smaller fixtures test only offset/boundary inheritance and never claim a statistical ratio. Parametrize the standalone verifier against a valid temporary manifest and one mutation per invariant; it must reject path traversal, drive paths, symlinks, bundle/path mismatch, missing/extra artifact or check keys, wrong ordered columns/row counts, consumer-contract paths or hashes that do not bind to their named artifacts, byte/hash changes, false checks, rubric keys other than E32-E34, and a satisfied subtotal other than four.

- [ ] **Step 2: Add clean and disabled-mode tests.**

Assert generator `clean=True` removes abandoned staging/sentinel data and unreferenced old candidates only after a replacement candidate verifies, retains the current candidate plus authoritative active/previous bundles, and never deletes the active manifest first. Inject failures after CSV write and after candidate-bundle rename but before candidate-pointer `os.replace`; every failure must leave the prior candidate and previously promoted manifest/artifact hashes valid. With a temporary config setting `enabled: false`, assert no Section 03 root or `section03_*` path key is emitted and all current Section 01 evidence remains present.

- [ ] **Step 3: Extend the CLI test.**

Assert return code zero, the existing `Generated Section 01 data` line remains, a new `Section 03 evidence:` line names the manifest, and the path exists under the temporary override rather than canonical repository evidence.

Run:

```text
rtk uv run pytest tests/unit/test_section03_manifest_verifier.py tests/integration/test_section03_generator.py tests/integration/test_generator_cli.py -q
```

Expected: FAIL because runner integration and Section 03 writing are absent.

- [ ] **Step 4: Implement deterministic writing and independent manifest validation.**

Within `runs/.staging-<uuid>`, write CSVs/config/samples first, render the image and report second, hash completed artifacts third, validate every check, derive the bundle ID, and rename the staging directory to its immutable final name. Ensure an empty alert DataFrame retains its schema. Build and independently verify a temporary root manifest, then atomically promote only that file with `os.replace`; cleanup happens afterward. Implement `verify_section03_manifest.py` without importing the generator writer: resolve every manifest-relative artifact below the named bundle, reject symlinks, enforce the exact artifact/check/rubric sets and ordered schemas, recompute rows/sizes/hashes/bundle ID, verify every consumer-contract path and SHA-256 against its referenced artifact, and reject any subtotal other than four. `--allow-runtime-pending` prints `section03 manifest: PASS (runtime pending)` only for generator tests; `--strict` requires final runtime proof and prints only `section03 manifest: PASS`.

- [ ] **Step 5: Run generator integration regressions.**

Run:

```text
rtk uv run pytest tests/unit/test_section03_manifest_verifier.py tests/integration/test_section03_generator.py tests/integration/test_section01_generator.py tests/integration/test_generator_cli.py -q
```

Expected: PASS; Section 01 behavior is retained and temporary runs leave canonical evidence untouched.

### Task 5: Implement leakage-safe dbt Gold models and contracts

**Files:**
- Create: `scripts/analytics/run_section03_dbt.py`
- Modify: `infra/analytics/dbt/dbt_project.yml`
- Modify: `infra/analytics/dbt/models/silver/stg_commerce_events.sql`
- Modify: `infra/analytics/dbt/models/gold/feat_customer_90d.sql`
- Modify: `infra/analytics/dbt/models/gold/feat_stream_60m.sql`
- Modify: `infra/analytics/dbt/models/gold/feat_customer_unified.sql`
- Create: `infra/analytics/dbt/models/gold/ml_customer_label.sql`
- Create: `infra/analytics/dbt/models/gold/agg_feature_health_daily.sql`
- Create: `infra/analytics/dbt/models/gold/feature_drift_alerts.sql`
- Create: `infra/analytics/dbt/models/gold/ml_customer_purchase_training.sql`
- Modify: `infra/analytics/dbt/models/gold/_features.yml`
- Create: `infra/analytics/dbt/models/gold/_drift.yml`
- Create: `infra/analytics/dbt/tests/assert_ml_customer_label_matches_horizon.sql`
- Create: `infra/analytics/dbt/tests/assert_training_features_are_point_in_time.sql`
- Create: `infra/analytics/dbt/tests/assert_drift_alert_threshold.sql`
- Create: `infra/analytics/dbt/tests/assert_commerce_event_dedup_unambiguous.sql`
- Create: `tests/unit/test_section03_dbt_contract.py`

**Interfaces:**
- Consumes: parsed generator YAML converted to dbt vars with the exact `Section03SqlParameters` names.
- Produces: seven ordered DP3 Gold tables with the exact schemas above.

- [ ] **Step 1: Add the failing dbt/wrapper contract test.**

Require the four new model paths, four singular-test paths, required-var calls without defaults, exact `id,label` YAML order, deterministic commerce-event rank order, and wrapper argument construction. The initial test fails because those contracts are absent. The wrapper test must also require parent-inclusive selection, the real `infra/analytics/dbt` project/profile paths, the selected scale, and propagation of a nonzero dbt return code.

Run:

```text
rtk uv run pytest tests/unit/test_section03_dbt_contract.py -q
```

Expected: FAIL on the missing Section 03 model/wrapper contracts, independently of dbt's selector behavior.

- [ ] **Step 2: Implement the configuration wrapper.**

Parse `--config`, defaulting to `configs/generator/base.yaml`; require `--scale`; default project/profile directories to the real `infra/analytics/dbt` paths; accept optional `--select`; load the selected scale, derive timestamps via `resolve_drift_window`, and serialize vars with `json.dumps`. The displayed operator command is prefixed by `rtk`, but the Python wrapper itself invokes the installed `uv`, `dbt`, or Python-module executable directly as an argument list without a shell string; it never depends on the developer-only `rtk` proxy. Test executable discovery and propagate the exact nonzero exit code. Print config, scale, and four resolved window values before execution, never secrets.

Declare all Section 03 vars with `var('name')` and no default in SQL; do not copy canonical timestamps, thresholds, or horizon values into `dbt_project.yml`. Add exact types, primary/foreign keys, `not_null`, `unique`, accepted labels/statuses, and relationships. The label model contract lists only `id` then `label`. The four singular tests recompute horizon truth, pre-cutoff feature truth, alert policy, and tied-commerce-event ambiguity; each returns violating rows.

- [ ] **Step 3: Make all three existing features point-in-time safe.**

Build customer-complete offline features from `dim_customer`, eligible `fact_order`, and successful `fact_payment_attempt` rows known by cutoff. Filter stream event and created timestamps before hourly aggregation. Force the unified `event_timestamp` to the one configured cutoff and keep `created` at or before it.

- [ ] **Step 4: Add label, monitoring, alert, and training models.**

Use successful payment attempts for labels; build equal seven-complete-day per-customer order-frequency counts for the fixed baseline-known cohort on every monitoring date; derive exact baseline quantile edges and PSI with epsilon/renormalization; filter alert rows at 0.15; and join labels one-to-one with unified features. Do not add label timestamps to the two-column model.

- [ ] **Step 5: Build through the config-faithful wrapper.**

Run:

```text
rtk uv run python scripts/analytics/run_section03_dbt.py --config configs/generator/base.yaml --scale medium --select +ml_customer_purchase_training +feature_drift_alerts
```

Expected: PASS; dbt builds the parent-inclusive dependency graph containing all seven DP3 models plus required core ancestors, all schema/singular tests succeed, `ml_customer_label` has exactly two columns, and no singular test returns a row. Rerun `rtk uv run pytest tests/unit/test_section03_dbt_contract.py -q`; expected PASS with no duplicated generator defaults.

### Task 6: Extend Spark Gold and dbt/Spark parity

**Files:**
- Modify: `src/vina_bim_shop/lakehouse/spark/sql.py`
- Modify: `src/vina_bim_shop/lakehouse/spark/constants.py`
- Modify: `src/vina_bim_shop/lakehouse/spark/job.py`
- Modify: `src/vina_bim_shop/lakehouse/spark/runner.py`
- Modify: `src/vina_bim_shop/lakehouse/spark/parity.py`
- Modify: `scripts/spark/run_batch.py`
- Modify: `tests/unit/test_spark_batch_runtime.py`

**Interfaces:**
- Consumes: validated generator configuration and `Section03SqlParameters` values identical to dbt vars.
- Produces: seven Spark/Iceberg DP3 tables and parity report rows matching dbt-DuckDB.
- Preserves: argument-free `ordered_core_gold_queries()`, the `core` stage, current batch-window semantics, and existing financial parity checks.

- [ ] **Step 1: Write failing SQL-order and leakage tests.**

Construct a `Section03SqlParameters` fixture and assert `DP3_GOLD_TABLES` and the exact seven-name query order. Inspect each rendered query for its supplied cutoff rather than the base-config literal; assert the cutoff-known label/training cohort, fixed baseline-known PSI cohort, equal seven-day baseline/current window predicates, both event and created-time predicates, successful-payment horizon logic, label select order only `id,label`, training dependency on label/unified features, and PSI baseline quantiles, epsilon, renormalization, and inclusive thresholds. Assert the core query names and DP3 names are disjoint and together equal `REQUIRED_GOLD_TABLES`.

- [ ] **Step 2: Write failing parity tests.**

Extend the existing mocked DuckDB/Trino test to retain aggregate comparisons but require zero-tolerance full-row comparisons named `ml_customer_label.keyed_row_mismatch_count`, `ml_customer_purchase_training.keyed_row_mismatch_count`, `agg_feature_health_daily.keyed_row_mismatch_count`, and `feature_drift_alerts.keyed_row_mismatch_count`. Full-outer join on `id`, `id`, `(monitoring_date,feature_name)`, and `(alert_date,feature_name)` respectively. Missing/extra keys, swapped IDs/labels, timestamps, strings, booleans, and integer fields are exact mismatches; persisted floating fields use absolute tolerance `1e-9` after 12-decimal round-half-even. The runtime report performs the same normalized full-row comparison from each canonical generator CSV named by the strict manifest to both dbt and Spark, with separate `generator_vs_dbt` and `generator_vs_spark` mismatch counts. Aggregate sums/maxima alone cannot pass parity.

Run:

```text
rtk uv run pytest tests/unit/test_spark_batch_runtime.py -q
```

Expected: FAIL because feature-query functions accept no parameters and the four Gold tables/parity checks are absent.

- [ ] **Step 3: Parameterize the Spark feature stage.**

Add `--generator-config` and `--generator-scale` to `spark/job.py`, defaulting compatibly to `configs/generator/base.yaml` and `medium`; load/validate that exact scale once, derive `Section03SqlParameters`, and pass the parameters only to full/features query groups. Forward both values through `scripts/spark/run_batch.py`, `build_spark_submit_command`, `run_spark_stage`, and `run_batch_pipeline`, print them in evidence, and persist them in the parity report. Do not alter generator `run_generation()`.

- [ ] **Step 4: Implement the seven Spark SQL queries.**

Mirror the dbt relations and exact output types. Build the PSI CTEs in this order: monitoring dates, fixed baseline-known customer/date grid, exact seven-day eligible-order windows, sorted baseline values with zero-based positions, exact type-7 quantile interpolation, distinct adjusted edges, baseline/current lower-exclusive-and-upper-inclusive bucket counts, epsilon-clipped normalized proportions, PSI aggregation, round-half-even persistence, status flags. Approximate percentile functions fail static tests. Cast label to integer and all date/timestamp fields explicitly.

- [ ] **Step 5: Register DP3 tables and parity comparisons.**

Add all four new names to `GOLD_SERVING_TABLES`, define the exact `DP3_GOLD_TABLES` tuple, derive `REQUIRED_GOLD_TABLES` without duplicates, and make full/core/features stages select by tuple membership rather than a name prefix. Keep DP3 persistence in dependency order; add the four keyed full-row comparisons without removing current row-count, aggregate, and finance checks. Replace the legacy nonexistent `--project-dir dbt --profiles-dir dbt` parity command with a direct argument-array call to `scripts/analytics/run_section03_dbt.py --project-dir infra/analytics/dbt --profiles-dir infra/analytics/dbt --config <path> --scale <scale>`; production code does not invoke `rtk`. The parity report records both commands, strict manifest/artifact hashes, dbt-vs-Spark plus generator-vs-each mismatch counts, and raises when any comparison fails.

- [ ] **Step 6: Run focused Spark/parity tests.**

Run:

```text
rtk uv run pytest tests/unit/test_spark_batch_runtime.py tests/unit/test_optional_duckdb_imports.py -q
```

Expected: PASS; rendered Spark SQL is cutoff-safe, all seven tables are ordered, and mocked dbt/Spark aggregates agree within their stated tolerances.

### Task 7: Make Airflow DP3 validate table-specific Section 03 contracts

**Files:**
- Modify: `src/vina_bim_shop/orchestration/mini_coursework_pipeline.py`
- Modify: `infra/orchestration/airflow/dags/mini_coursework_pipeline.py`
- Modify: `infra/orchestration/airflow/bootstrap/seed_coursework_metadata.py`
- Create: `scripts/orchestration/run_section03_dp3.py`
- Modify: `tests/unit/test_orchestration_runtime.py`
- Modify: `tests/unit/test_airflow_coursework_metadata.py`

**Interfaces:**
- Consumes: the seven persisted Gold tables plus the exact generator config path, selected scale, and resolved cutoff recorded by DP3 compute metadata.
- Produces: `dp3_compute.json`, `dp3_validate.json`, and `quality/coursework_feature_contract.json` with table-specific results.
- Preserves: the six current stage functions, TaskGroup IDs, DAG dependencies, and failure propagation.

- [ ] **Step 1: Replace the generic three-table expectation in tests.**

Set `FEATURE_TABLES` and seeded `vbs_feature_tables` to the exact seven-name order. For a strict Section 03 run, DAG conf is the sole per-run authority and must contain `generator_config_path`, `generator_scale`, and `section03_candidate_manifest_sha256`; missing values fail before DP3 compute. Existing Airflow Variables may remain only as defaults for legacy non-Section-03 runs, and strict mode must prove no Variable fallback occurred. Assert compute metadata records the three submitted values plus `feature_cutoff_ts` returned by the config-aware Spark stage. Assert validation records `columns`, `row_count`, `unique_key_count`, `contract_success`, and table-specific metrics instead of assuming every table has `event_timestamp` and `created`.

- [ ] **Step 2: Add failure fixtures for each critical contract.**

Mock Trino results that expose an extra label column, duplicate label ID, non-binary label, training row with a wrong cutoff, training `created` after cutoff, negative/nonfinite PSI, alert below 0.15, and a missing table. Each fixture must make the DP3 gate block and raise `RuntimeError("Offline feature validation failed.")`.

Run:

```text
rtk uv run pytest tests/unit/test_orchestration_runtime.py tests/unit/test_airflow_coursework_metadata.py -q
```

Expected: FAIL because current DP3 metadata lists three tables and applies one feature schema to every table.

- [ ] **Step 3: Add a narrow `DP3_TABLE_CONTRACTS` mapping.**

Define exact ordered columns and keys for all seven tables. Feature tables require `customer_id,event_timestamp,created` and forbid `created_ts`; label requires exactly `id,label`; health uses `(monitoring_date,feature_name)`; alerts use `(alert_date,feature_name)` and allow zero rows; training requires its exact schema, unique `id`, one cutoff timestamp, and `created <= event_timestamp`.

- [ ] **Step 4: Query and validate exact runtime facts.**

Use `describe`, `count(*)`, `count(distinct key)`, label min/max, timestamp min/max, `sum(case when ...)` violation counts, PSI finiteness/non-negativity, and alert minimum PSI. The thin Airflow adapter passes the three required DAG-conf values unchanged to the six-stage implementation. That implementation reads the expected cutoff from the config/scale-faithful `dp3_compute.json`, byte-compares config path, scale, candidate-manifest SHA-256, and cutoff to the candidate manifest, and never derives them from the hourly DAG's `data_interval_end` or an Airflow Variable. Feed boolean result columns to the existing Great Expectations helper and persist the detailed Trino results in `dp3_validate.json`.

- [ ] **Step 5: Implement the strict Airflow trigger/capture wrapper and run regressions.**

The wrapper strict-verifies `section03_candidate_manifest.json`, calls Airflow's stable REST API with an environment-injected credential, and submits its config path, scale, and exact file SHA-256 as the three required DAG-conf values. It polls the DAG and all six task instances to a terminal state and exports only matching run/task metadata and hash-bound stage artifacts. It exits nonzero on timeout, any non-success task, DAG-conf/compute/cutoff mismatch, Variable fallback, missing seven-table DP3 output, or stale artifact. The existing deterministic Section 03 evidence image remains the contextual E32 screenshot; Airflow runtime is supplemental machine proof and does not add a browser dependency to this prerequisite plan.

Run:

```text
rtk uv run pytest tests/unit/test_orchestration_runtime.py tests/unit/test_airflow_coursework_metadata.py tests/unit/test_orchestration_dag_adapters.py -q
```

Expected: PASS; valid seven-table results pass, every corrupt fixture blocks, and the existing DAG chain remains unchanged.

### Task 8: Publish expanded DataHub lineage and assertions

**Files:**
- Modify: `src/vina_bim_shop/datahub_lineage/spark_lineage.py`
- Modify: `src/vina_bim_shop/datahub_lineage/coursework_pipelines.py`
- Modify: `scripts/datahub/capture_evidence.py`
- Modify: `tests/unit/test_datahub_coursework_lineage.py`
- Modify: `tests/unit/test_datahub_capture_evidence.py`

**Interfaces:**
- Consumes: canonical Iceberg dataset URNs and DP3 validation artifact names.
- Produces: seven DP3 output edges, dataset schemas, ownership/tags, and assertion targets.
- Preserves: `emit_spark_batch_lineage(...)`, `emit_coursework_pipeline(...)`, current dataflow/job IDs, DP1/DP2 lineage, and exception propagation.

- [ ] **Step 1: Write the complete expected lineage graph in tests.**

Require these direct parents: `feat_customer_90d <- [dim_customer,fact_order,fact_payment_attempt]`; `feat_stream_60m <- [stg_commerce_events]`; `feat_customer_unified <- [feat_customer_90d,feat_stream_60m]`; `ml_customer_label <- [dim_customer,fact_payment_attempt]`; `agg_feature_health_daily <- [dim_customer,fact_order]`; `feature_drift_alerts <- [agg_feature_health_daily]`; `ml_customer_purchase_training <- [ml_customer_label,feat_customer_unified]`.

- [ ] **Step 2: Require seven DP3 outputs and exact schemas.**

Assert the DP3 data job inputs are `dim_customer`, `fact_order`, `fact_payment_attempt`, and `stg_commerce_events`; outputs use the exact seven-table order. Assert `ml_customer_label` schema fields are exactly `id,label`; training and monitoring schema lists match Exact Output Schemas; assertion targets exist for uniqueness, binary labels, point-in-time safety, finite PSI, and alert threshold.

Run:

```text
rtk uv run pytest tests/unit/test_datahub_coursework_lineage.py tests/unit/test_datahub_capture_evidence.py -q
```

Expected: FAIL because current lineage publishes only three DP3 outputs.

- [ ] **Step 3: Extend constants, metadata, lineage, and assertions.**

Update only the DP3 portions of the existing mappings. Describe the training output as `Feast-ready offline point-in-time export; not a Feast runtime`. Continue attaching coursework ownership and tags through existing helpers. Point assertion evidence to `dp3_validate.json` and `coursework_feature_contract.json` rather than generator-local CSVs.

- [ ] **Step 4: Add strict Section 03 runtime capture and run DataHub regressions.**

Extend the existing capture script behind `--section03`; emit the updated flow/jobs, wait for search indexing, query the exact seven datasets and five assertions, and write only sanitized request/result JSON below the requested temporary output. Existing default capture behavior remains unchanged. The LLM plan later captures DataHub UI evidence for E9 after these contracts are ingested on GKE.

Run:

```text
rtk uv run pytest tests/unit/test_datahub_coursework_lineage.py tests/unit/test_datahub_capture_evidence.py tests/unit/test_datahub_adr_boundaries.py -q
```

Expected: PASS; all seven outputs and exact parents/assertions are present and DP1/DP2 boundaries remain intact.

### Task 9: Close schema, documentation, CLI, and Make discoverability

**Files:**
- Modify: `Makefile`
- Modify: `scripts/README.md`
- Modify: `README.md`
- Modify: `configs/scenarios/README.md`
- Modify: `deliverables/03_data_generator_improvement.md`
- Modify: `architecture/masterplan.md`
- Modify: `architecture/domain/business-context.md`
- Modify: `architecture/diagrams/schema_design.puml`
- Modify: `architecture/diagrams/erd/physical_gold_model.puml`
- Modify: `architecture/diagrams/erd/gold_layer_ERD.dbml`
- Create: `tests/unit/test_section03_documentation.py`
- Modify: `tests/unit/test_section02_schema_design.py`

**Interfaces:**
- Consumes: final command names, Gold/evidence schemas, and Feast boundary.
- Produces: one reproducible public path from generator through dbt/Spark evidence and rubric traceability.

- [ ] **Step 1: Add failing documentation and schema-source tests.**

Assert Section 03 is no longer called a placeholder or out of scope; all eight approved values, E32-E34 mapping, exact label schema, training name, cutoff/horizon, thresholds, evidence paths, and Feast-ready-only boundary appear in the Section 03 deliverable. Assert the three diagram sources contain all four new Gold tables and the label-to-training, features-to-training, health-to-alert relationships.

- [ ] **Step 2: Add exact Make target assertions.**

Require `.PHONY` and help entries for:

```make
generate-section03:
	rtk uv run python scripts/generate/run_generator.py --config configs/generator/base.yaml --scale $(SCALE) --mode full --clean --seed $(SEED)

build-section03-dbt:
	rtk uv run python scripts/analytics/run_section03_dbt.py --config configs/generator/base.yaml --scale $(SCALE)

test-section03:
	rtk uv run pytest tests/unit/test_section03_drift.py tests/integration/test_section03_generator.py
```

Make recipes invoke pinned workspace executables directly so they also work in CI; documented operator invocations are `rtk make generate-section03 SCALE=medium SEED=42`, `rtk make build-section03-dbt SCALE=medium`, and `rtk make test-section03`.

Run:

```text
rtk uv run pytest tests/unit/test_section03_documentation.py tests/unit/test_section02_schema_design.py -q
```

Expected: FAIL because current public docs say Section 03 is unimplemented and the targets/tables do not exist.

- [ ] **Step 3: Update only contradictory and Section 03-specific prose.**

Replace the deliverable completely; update command catalogs; document config ownership and measured-versus-configured values; remove only obsolete drift exclusions from shared docs; retain ML training, Feast operation, production hardening, and unrelated AI work as out of scope.

- [ ] **Step 4: Update schema sources consistently.**

Add the four tables with fields/types/keys from Exact Output Schemas. Draw `ml_customer_label -> ml_customer_purchase_training`, `feat_customer_unified -> ml_customer_purchase_training`, and `agg_feature_health_daily -> feature_drift_alerts`. Do not rename existing feature fields or restyle unrelated diagram content.

- [ ] **Step 5: Run documentation and command-surface tests.**

Run:

```text
rtk uv run pytest tests/unit/test_section03_documentation.py tests/unit/test_section02_schema_design.py tests/unit/test_script_surface_documentation.py -q
```

Expected: PASS; docs, schemas, commands, and scope boundaries agree.

### Task 10: Regenerate canonical evidence and run the final gate

**Files:**
- Create: `scripts/generate/finalize_section03_evidence.py`
- Create: `tests/integration/test_section03_finalizer.py`
- Regenerate: `evidence/03_data_generator_improvement/runs/<bundle_id>/**`
- Transient: `evidence/03_data_generator_improvement/section03_candidate_manifest.json` (absent after clean success; may remain after a warned post-promotion housekeeping failure)
- Regenerate: `evidence/03_data_generator_improvement/section03_manifest.json`

**Interfaces:**
- Consumes: the approved base config and completed Tasks 1-9.
- Produces: a tested fail-closed finalizer, canonical seed-42 evidence, and final verification output; no manual edits to generated artifacts.

- [ ] **Step 1: Specify finalizer success, failure, and retention before implementation.**

Build synthetic hash-valid candidate/Spark/Airflow/DataHub capture trees. Parametrize corrupt, missing, and stale variants for each of the three runtime captures; a nested artifact missing from each runtime's recursive inventory; config hash, run identity, scale, and cutoff mismatches; path traversal and symlink input; failure after final-directory rename but immediately before authoritative `os.replace`; candidate-pointer identity change before the precondition; and post-promotion pointer-unlink/cleanup failure injection. Every pre-promotion case must exit nonzero and leave the prior authoritative manifest and all of its transitive hashes byte-identical. Post-promotion housekeeping failures must return success with an explicit warning, retain the newly promoted strict root, and preserve every pointer/bundle whose safe deletion is uncertain. The clean success case must prove fourteen-key recursive inventory verification, path rewrites to the final bundle, pointer removal, active-plus-previous retention, consumed-candidate cleanup only with `--clean`, and no deletion of an identity-mismatched candidate pointer.

Run:

```text
rtk uv run pytest tests/integration/test_section03_finalizer.py -q
```

Expected: FAIL because the finalizer is not implemented.

- [ ] **Step 2: Implement and verify the fail-closed finalizer.**

Implement the exact lock, recursive verification, staging, final-ID derivation, report rewrite, path rebinding, compare-and-delete candidate pointer, and post-promotion cleanup lifecycle from the manifest contract. The finalizer accepts `--clean` as a CLI flag only; it never serializes `clean` into either manifest.

Run:

```text
rtk uv run pytest tests/integration/test_section03_finalizer.py -q
```

Expected: PASS across success, every runtime corruption/staleness case, pre-replace candidate mismatch, post-promotion non-fatal housekeeping warnings, and active/previous retention.

- [ ] **Step 3: Run the canonical medium/full generator.**

Run:

```text
rtk uv run python scripts/generate/run_generator.py --config configs/generator/base.yaml --scale medium --mode full --clean --seed 42
```

Expected: exit `0`; current Section 01 completion text remains; the candidate manifest path is printed; configured medium entity counts remain customers `12000`, sellers `600`, products `6000`, orders `45000`, promotions `80`; Section 03 checks are all true; normalized rate is in `[1.35,1.65]`; a new immutable candidate bundle has `runtime_evidence.status="pending"`; any prior strict root remains active and unchanged.

- [ ] **Step 4: Validate manifest paths, schemas, and hashes independently.**

Run:

```text
rtk uv run python scripts/generate/verify_section03_manifest.py --manifest evidence/03_data_generator_improvement/section03_candidate_manifest.json --allow-runtime-pending
```

Expected: prints `section03 manifest: PASS (runtime pending)` and exits `0`; this is not final evidence and cannot unblock Section 04.2.

- [ ] **Step 5: Build dbt from parsed generator configuration.**

Run:

```text
rtk uv run python scripts/analytics/run_section03_dbt.py --config configs/generator/base.yaml --scale medium --project-dir infra/analytics/dbt --profiles-dir infra/analytics/dbt
```

Expected: exit `0`; dbt models and all generic/singular tests pass, including exact labels, point-in-time features, and alert policy.

- [ ] **Step 6: Run the Spark backfill/parity evidence path with batch services available.**

Run:

```text
rtk uv run python scripts/spark/run_batch.py --start-ts 2026-03-03T23:59:00Z --end-ts 2026-05-01T23:59:00Z --mode backfill --generator-config configs/generator/base.yaml --generator-scale medium --section03-manifest evidence/03_data_generator_improvement/section03_candidate_manifest.json --evidence-root tmp/section03-runtime/spark
```

Expected: exit `0`; seven DP3 tables are present; `runtime/spark/run_manifest.json` transitively hashes the Spark/dbt artifacts and binds the candidate/config/scale/cutoff; `dbt_parity_report.json` has `success: true`; keyed mismatch counts are zero for labels, training rows, health rows, and alerts across generator/Spark/dbt, while only explicitly documented floating-point fields use their stated tolerance.

- [ ] **Step 7: Start the existing local Airflow/DataHub dependencies without deleting persistent volumes.**

Run:

```text
rtk uv run python scripts/ctl.py compose up governance
rtk uv run python scripts/ctl.py compose up orchestration
```

Expected: Airflow webserver/scheduler and DataHub GMS/frontend/search are healthy; existing volumes are reused; no `down -v` command is run.

- [ ] **Step 8: Execute and capture the real six-task Airflow pipeline.**

Run:

```text
rtk uv run python scripts/orchestration/run_section03_dp3.py --airflow-url http://localhost:8082 --dag-id mini_coursework_pipeline --run-id section03-medium-seed42 --config configs/generator/base.yaml --scale medium --section03-manifest evidence/03_data_generator_improvement/section03_candidate_manifest.json --output tmp/section03-runtime/airflow --strict
```

Expected: exit `0`; all six existing task instances are `success`; DP3 compute/validation name all seven outputs and the manifest cutoff; the exported run manifest hashes task-state JSON, `dp3_compute.json`, `dp3_validate.json`, and `quality/coursework_feature_contract.json`. Airflow credentials come only from an implementation-session environment/Vault reference and are redacted.

- [ ] **Step 9: Emit, index, query, and capture DataHub lineage/assertions.**

Run:

```text
rtk uv run python scripts/datahub/capture_evidence.py --section03 --gms-url http://localhost:8087 --frontend-url http://localhost:9002 --airflow-capture tmp/section03-runtime/airflow --section03-manifest evidence/03_data_generator_improvement/section03_candidate_manifest.json --output tmp/section03-runtime/datahub --strict
```

Expected: exit `0`; the indexed `mini_coursework_pipeline` DataFlow and DP3 DataJob expose the exact seven outputs, direct parents, schemas, and five assertion targets; `lineage.json` contains sanitized emit acknowledgements, indexed-search hits, queried URNs, schema fields, edges, and assertion results. Direct GMS resolution without indexed search fails.

- [ ] **Step 10: Finalize a new immutable bundle and run the strict verifier.**

Run:

```text
rtk uv run python scripts/generate/finalize_section03_evidence.py --candidate-manifest evidence/03_data_generator_improvement/section03_candidate_manifest.json --active-manifest evidence/03_data_generator_improvement/section03_manifest.json --spark-root tmp/section03-runtime/spark --airflow-root tmp/section03-runtime/airflow --datahub-root tmp/section03-runtime/datahub --clean
rtk uv run python scripts/generate/verify_section03_manifest.py --manifest evidence/03_data_generator_improvement/section03_manifest.json --strict
```

Expected: the finalizer imports only recursively verified captures into a new fourteen-artifact bundle, updates all measured runtime report sections, strict-verifies a temporary root, atomically promotes it, removes the identity-matching consumed candidate pointer/bundle, and retains the active plus previous good bundle; the verifier prints `section03 manifest: PASS`. A missing/failed/stale capture exits nonzero, leaves the prior verified root active, and retains the pending candidate for diagnosis rather than fabricating proof.

- [ ] **Step 11: Run the focused Section 03 regression gate.**

Run:

```text
rtk uv run pytest tests/unit/test_generator_config.py tests/unit/test_generator_module_split.py tests/unit/test_section03_drift.py tests/unit/test_section03_manifest_verifier.py tests/unit/test_section03_dbt_contract.py tests/integration/test_section03_finalizer.py tests/integration/test_section03_generator.py tests/integration/test_section01_generator.py tests/integration/test_generator_cli.py tests/unit/test_spark_batch_runtime.py tests/unit/test_orchestration_runtime.py tests/unit/test_airflow_coursework_metadata.py tests/unit/test_orchestration_dag_adapters.py tests/unit/test_datahub_coursework_lineage.py tests/unit/test_datahub_capture_evidence.py tests/unit/test_datahub_adr_boundaries.py tests/unit/test_section03_documentation.py tests/unit/test_section02_schema_design.py -q
```

Expected: PASS with zero failures, skips, or xfails in the listed files.

- [ ] **Step 12: Run the full repository regression suite.**

Run:

```text
rtk uv run pytest -q
```

Expected: PASS. A failure outside Section 03 is resolved only when caused by these changes; otherwise preserve it and report the unrelated pre-existing failure without modifying adjacent code.

- [ ] **Step 13: Inspect scope before handoff.**

Run:

```text
rtk git status --short
rtk git diff --check
```

Expected: only files in Exact File Map plus deterministic Section 03 artifacts are changed; `rtk git diff --check` prints nothing; nothing is staged or committed.

## Definition of Done

- [ ] `base.yaml` owns the enabled approved scenario and every locked value; invalid configuration is rejected with key-specific errors.
- [ ] Enabled generation is deterministic for a seed, keeps all configured entity/order counts fixed, and realizes a normalized post/pre order rate in `[1.35,1.65]` for canonical medium seed 42.
- [ ] Disabled generation is equivalent to the current legacy timestamp path and consumes no extra RNG values.
- [ ] `run_generation()` retains its exact public signature, defaults, result type, and Section 01 behavior.
- [ ] The feature cutoff is exactly end minus seven days; the prediction cohort contains only customers known by that cutoff; labels use only successful purchases in the subsequent seven days; and customer-identity, created-time, and event-time leakage are excluded.
- [ ] Generator evidence and Gold `ml_customer_label` contain exactly unique `id,label` columns with binary integer labels and one row per cutoff-known customer.
- [ ] Generator, Spark, and dbt produce the named richer `ml_customer_purchase_training` join with one cutoff-safe row per label ID.
- [ ] Raw commerce events are flattened and deduplicated by one fail-closed contract before feature computation; legitimate drift-boundary crossings retain their lead/lag offsets and aggregate event inheritance passes.
- [ ] PSI uses a fixed baseline-known customer cohort, equal seven-complete-day order-frequency windows, exact cross-engine type-7 baseline quantiles, lower-bin boundary equality, 12-decimal persistence, and finite epsilon behavior; multiplier-1/control, out-of-window, cohort, zero-bin, repeated-edge, warning, alert, and parity fixtures pass.
- [ ] Daily health and alert outputs match their exact schemas; alert rows cannot fall below 0.15.
- [ ] Spark/dbt receive the same explicit config and scale through real repository paths, contain the same seven DP3 outputs, and parity checks pass for table counts, labels, features, PSI, alerts, and training aggregates.
- [ ] A real six-task Airflow run validates table-specific schemas, uniqueness, binary labels, the manifest-owned cutoff, PSI, and alert thresholds; task/stage JSON is hash-bound and verified.
- [ ] DataHub publishes and indexed-search verifies all exact parents, seven outputs, schemas, and assertion targets without changing DP1/DP2 lineage; sanitized lineage/search proof is hash-bound.
- [ ] Sheet3 E32, E33, and E34 each map through the strict `section03_manifest.json` to a generated, hash-bound artifact and an automated assertion; the candidate earns zero, the verified subtotal cannot exceed 4, and the embedded consumer contract is sufficient for Section 04.2.
- [ ] The section-specific snapshot, label, health, alerts, training join, samples, evidence image, report, Spark/Airflow/DataHub runtime proofs, and manifest are regenerated from medium/full seed 42 in one verified immutable bundle and every direct and transitive hash validates.
- [ ] Generation replaces only the candidate pointer; failed generation/finalization never replaces the prior strict root; strict verification requires `runtime_evidence.status="verified"` with Spark, Airflow, and DataHub bindings; successful cleanup retains only the active plus one previous verified bundle.
- [ ] Documentation and schema sources describe implemented behavior and clearly assign actual Feast operation to Section 04.2.
- [ ] Focused and full tests pass; the diff contains no unrelated refactor; no staging or commit occurs without explicit authorization.

## Completion Record

**Status:** Not started as of 2026-07-15.

- No implementation file, generated evidence artifact, schema model, command target, or test described by this plan has been created or changed as part of writing this plan.
- No implementation verification command or canonical evidence regeneration command in Ordered Tasks has been run.
- No runtime result, realized ratio, PSI value, alert count, label count, parity result, Airflow result, or DataHub result is claimed in advance.
- No file has been staged or committed.

Complete this record only after every Definition of Done item is verified. Record exact command outputs, canonical observed counts/rates/PSI, manifest hashes, any environment prerequisite used for the Spark/Airflow/DataHub runtime checks, and an explicit statement that no unrelated files were changed.
