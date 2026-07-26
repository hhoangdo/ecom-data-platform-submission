# Section 03 dbt Gold Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Section 03 Task 5: derive dbt runtime boundaries from the validated generator config and build/test the seven leakage-safe DP3 Gold relations.

**Architecture:** `scripts/analytics/run_section03_dbt.py` loads `configs/generator/base.yaml`, selects `medium`, calls the shared window resolver, and passes JSON `--vars` to dbt. SQL has required vars without defaults and builds feature, label, health, alert, and training relations in one parent-inclusive graph.

**Tech Stack:** Python 3.12, dbt Core, DuckDB, SQL, PyYAML, pytest, `uv`, Make, `rtk`.

## Locked sources and execution policy

- Read `C:\Users\oou1hc\.codex\RTK.md`; every shell command begins with `rtk`.
- Section 03 source is `tmp/edai2-plan/03_data_generator_improvement.md`, SHA-256 `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`.
- EDAI2 source is `tmp/edai2-plan/04.2_llm_design.md`, SHA-256 `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`.
- Rubric source is `tmp/rubic-check/Coursework Tracking (Public).xlsx`, SHA-256 `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- Work on the current branch in one serial session. Do not create a worktree or branch and do not stage, commit, push, or open a PR.
- Do not mutate GCP or Kubernetes. Do not prune Docker or stop unrelated containers.

## Metadata

| Field | Decision |
|---|---|
| Phase | 3 — local dbt Gold contract |
| Source tasks | Section 03 Task 5 |
| Rubric contribution | Supporting evidence for `Sheet3!E34` only; Topic 07 is sole primary owner |
| Prerequisites | Topic 02 Completion Record and candidate config/scale/window identity |
| Blocked successors | Topic 04 |
| Runtime ownership | Local analytics operator; one serial session |
| Local/GCP class | Local dbt/DuckDB; no GCP mutation |

## Global constraints

- No canonical timestamps, horizon, or PSI thresholds are copied into SQL or `dbt_project.yml`.
- Every Section 03 SQL var is `var('name')` without a default.
- `ml_customer_label` has exactly ordered columns `id,label`, unique IDs, and binary integer labels.
- `ml_customer_purchase_training` remains separate and joins label to cutoff-safe unified features one-to-one.
- Commerce-event normalization/dedup is deterministic and rejects tied winners that disagree.
- Health uses fixed baseline cohort and exact seven-complete-day windows; alerts require PSI `>=0.15`.
- Operator commands use `rtk`; the Python wrapper invokes an executable argument array directly and never embeds `rtk`.

## Current-state refresh — read-only planning phase

```text
rtk git status --short --branch
rtk git branch --show-current
rtk rg -n "feat_customer_90d|feat_stream_60m|feat_customer_unified|var\(" infra/analytics/dbt scripts/analytics tests/unit/test_section03_dbt_contract.py
rtk uv run pytest tests/unit/test_section03_dbt_contract.py -q
```

Expected: the same branch and current model boundary are recorded; the test either passes as a baseline or fails only on not-yet-implemented Task 5 contracts.

## Scope and non-goals

In scope: config wrapper, three existing feature corrections, four new Gold models, two YAML contract files, four singular tests, and focused contract tests. Non-goals: Spark implementation, live Airflow/DataHub, Feast runtime, GCP, generator default duplication, or unrelated dbt refactoring.

## Exact file map

| Action | Exact path | Responsibility |
|---|---|---|
| Create | `scripts/analytics/run_section03_dbt.py` | Parse config/scale, derive windows, construct exact dbt argument array, and propagate exit code. |
| Modify | `infra/analytics/dbt/dbt_project.yml` | Declare required Section 03 vars without copied defaults. |
| Modify | `infra/analytics/dbt/models/silver/stg_commerce_events.sql` | Normalize nested IDs and deterministic dedup ranking. |
| Modify | `infra/analytics/dbt/models/gold/feat_customer_90d.sql` | Build customer-complete cutoff-safe 90-day features. |
| Modify | `infra/analytics/dbt/models/gold/feat_stream_60m.sql` | Exclude unavailable event/created rows. |
| Modify | `infra/analytics/dbt/models/gold/feat_customer_unified.sql` | Join only cutoff-safe offline/stream snapshots. |
| Create | `infra/analytics/dbt/models/gold/ml_customer_label.sql` | Build exact `id,label` from successful horizon payments. |
| Create | `infra/analytics/dbt/models/gold/agg_feature_health_daily.sql` | Build daily fixed-cohort order-frequency PSI and status. |
| Create | `infra/analytics/dbt/models/gold/feature_drift_alerts.sql` | Filter alert rows and attach the prescribed action. |
| Create | `infra/analytics/dbt/models/gold/ml_customer_purchase_training.sql` | Join exact labels to unified point-in-time features. |
| Modify | `infra/analytics/dbt/models/gold/_features.yml` | Tighten the three feature contracts at the fixed cutoff. |
| Create | `infra/analytics/dbt/models/gold/_drift.yml` | Define exact schemas, keys, values, and relationships for four new tables. |
| Create | `infra/analytics/dbt/tests/assert_ml_customer_label_matches_horizon.sql` | Recompute horizon truth and return differences. |
| Create | `infra/analytics/dbt/tests/assert_training_features_are_point_in_time.sql` | Return post-cutoff leakage/value differences. |
| Create | `infra/analytics/dbt/tests/assert_drift_alert_threshold.sql` | Return PSI/status/action violations. |
| Create | `infra/analytics/dbt/tests/assert_commerce_event_dedup_unambiguous.sql` | Return disagreeing tied duplicate winners. |
| Create | `tests/unit/test_section03_dbt_contract.py` | Test exact paths, required vars, selection, argument array, schemas, and exit propagation. |

## Interfaces and data flow

The operator invokes `run_section03_dbt.py --config configs/generator/base.yaml --scale medium --project-dir infra/analytics/dbt --profiles-dir infra/analytics/dbt`. The wrapper prints config, scale, drift start, feature cutoff, label end, and baseline date; it then runs a parent-inclusive selector containing all seven DP3 models plus required ancestors. Nonzero dbt exit status is returned unchanged.

## Failure modes

Fail on absent/invalid config or scale, a required var with a default, a literal timestamp/threshold/horizon, wrong project/profile path, non-parent-inclusive selection, nondeterministic event ties, leakage, wrong label order/type/key, nonfinite PSI, invalid alert, relationship failure, or swallowed dbt exit status.

## Ordered test-first execution tasks

- [ ] Add exact wrapper/path/var/schema assertions, then run `rtk uv run pytest tests/unit/test_section03_dbt_contract.py -q`; expected FAIL because the wrapper, four models, `_drift.yml`, and singular tests are absent.
- [ ] Implement `scripts/analytics/run_section03_dbt.py`, then run `rtk uv run pytest tests/unit/test_section03_dbt_contract.py -q`; expected FAIL only on missing SQL/YAML contracts while wrapper config derivation, direct argument array, parent-inclusive selection, and nonzero exit propagation pass.
- [ ] Implement the three cutoff-safe feature models and deterministic `stg_commerce_events.sql`, then run `rtk uv run pytest tests/unit/test_section03_dbt_contract.py -q`; expected FAIL only on the four new Gold models/schema/singular-test contracts.
- [ ] Implement `ml_customer_label.sql`, `agg_feature_health_daily.sql`, `feature_drift_alerts.sql`, `ml_customer_purchase_training.sql`, `_features.yml`, `_drift.yml`, and four exact singular tests, then run `rtk uv run pytest tests/unit/test_section03_dbt_contract.py -q`; expected PASS with no duplicated generator defaults.
- [ ] Run `rtk uv run python scripts/analytics/run_section03_dbt.py --config configs/generator/base.yaml --scale medium --project-dir infra/analytics/dbt --profiles-dir infra/analytics/dbt`; expected exit 0 with seven DP3 models plus ancestors built and every generic/singular test passing.
- [ ] Run `rtk uv run pytest tests/unit/test_section03_dbt_contract.py -q`; expected PASS with exact `id,label`, cutoff-safe training, finite PSI, valid alerts, and deterministic event dedup.
- [ ] Run `rtk git diff --check` and `rtk git status --short --branch`; expected no whitespace errors, the original branch unchanged, only exact file-map paths changed, and nothing staged.

## Evidence and screenshot ownership

Topic 03 owns sanitized dbt command/test logs and relation schemas/counts for handoff. No screenshot is required or scoreable. Topic 07 binds the dbt result into strict evidence.

## Cleanup

Remove only local `infra/analytics/dbt/target` and `infra/analytics/dbt/logs` outputs if they were created and are not needed for handoff; do not delete source, candidates, containers, or cloud resources.

## Rubric table

| Workbook cell | Supporting proof | Ownership rule |
|---|---|---|
| `Sheet3!E34` | Exact two-column label plus cutoff-safe one-to-one training join | Supporting only; Topic 07 promotes |

## Definition of Done

All exact models/YAML/singular tests exist; the wrapper derives windows from config; focused and real local dbt commands pass; the label and training contracts are exact; scoped diff checks pass.

## Completion Record

| Field | Record |
|---|---|
| Status | Not started |
| Affected files | Record only exact file-map paths actually changed |
| Commands / exit codes | Record every checkbox command and numeric exit code, ending with `rtk git status --short --branch` |
| Evidence + SHA-256 | Record dbt/test-log paths and hashes, or `no artifact produced` |
| Screenshot QA | No screenshot required for Topic 03 |
| Cleanup / runtime release | Record local dbt output disposition and `no runtime acquired` |
| Limitations | Local dbt proof does not establish Spark/Airflow/DataHub runtime |
| Successor handoff | Provide derived vars, dbt command, model/test result, and output hashes to Topic 04 |
