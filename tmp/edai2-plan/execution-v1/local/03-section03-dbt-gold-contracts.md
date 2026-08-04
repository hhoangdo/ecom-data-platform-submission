# Section 03 dbt Gold Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Section 03 Task 5: derive dbt runtime boundaries from the validated generator config and build/test the seven leakage-safe DP3 Gold relations.

**Architecture:** `scripts/analytics/run_section03_dbt.py` loads `configs/generator/base.yaml`, selects `medium`, calls the shared window resolver, and passes JSON `--vars` to dbt. SQL has required vars without defaults and builds feature, label, health, alert, and training relations in one parent-inclusive graph.

**Tech Stack:** Python 3.12, dbt Core, DuckDB, SQL, PyYAML, pytest, `uv`, Make, `rtk`.

## Locked sources and execution policy

- Read `C:\Users\oou1hc\.codex\RTK.md`; every shell command begins with `rtk`.
- Section 03 source is `tmp/edai2-plan/03_data_generator_improvement.md`, SHA-256 `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`.
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

The operator invokes `run_section03_dbt.py --config configs/generator/base.yaml --scale medium --project-dir infra/analytics/dbt --profiles-dir infra/analytics/dbt --select +ml_customer_purchase_training +feature_drift_alerts`. The wrapper prints config, scale, drift start, feature cutoff, label end, and baseline date; it then runs that explicit parent-inclusive selector containing all seven DP3 models plus required ancestors. Nonzero dbt exit status is returned unchanged.

## Failure modes

Fail on absent/invalid config or scale, a required var with a default, a literal timestamp/threshold/horizon, wrong project/profile path, non-parent-inclusive selection, nondeterministic event ties, leakage, wrong label order/type/key, nonfinite PSI, invalid alert, relationship failure, or swallowed dbt exit status.

## Ordered test-first execution tasks

- [ ] Add exact wrapper/path/var/schema assertions, then run `rtk uv run pytest tests/unit/test_section03_dbt_contract.py -q`; expected FAIL because the wrapper, four models, `_drift.yml`, and singular tests are absent.
- [ ] Implement `scripts/analytics/run_section03_dbt.py`, then run `rtk uv run pytest tests/unit/test_section03_dbt_contract.py -q`; expected FAIL only on missing SQL/YAML contracts while wrapper config derivation, direct argument array, parent-inclusive selection, and nonzero exit propagation pass.
- [ ] Implement the three cutoff-safe feature models and deterministic `stg_commerce_events.sql`, then run `rtk uv run pytest tests/unit/test_section03_dbt_contract.py -q`; expected FAIL only on the four new Gold models/schema/singular-test contracts.
- [ ] Implement `ml_customer_label.sql`, `agg_feature_health_daily.sql`, `feature_drift_alerts.sql`, `ml_customer_purchase_training.sql`, `_features.yml`, `_drift.yml`, and four exact singular tests, then run `rtk uv run pytest tests/unit/test_section03_dbt_contract.py -q`; expected PASS with no duplicated generator defaults.
- [ ] Run `rtk uv run python scripts/analytics/run_section03_dbt.py --config configs/generator/base.yaml --scale medium --project-dir infra/analytics/dbt --profiles-dir infra/analytics/dbt --select +ml_customer_purchase_training +feature_drift_alerts`; expected exit 0 with seven DP3 models plus ancestors built and every generic/singular test passing.
- [ ] Run `rtk uv run pytest tests/unit/test_section03_dbt_contract.py -q`; expected PASS with exact `id,label`, cutoff-safe training, finite PSI, valid alerts, and deterministic event dedup.
- [ ] Run `rtk git diff --check`, `rtk git status --short --branch`, and `rtk git ls-files --stage`; expected no whitespace errors, the original branch unchanged, only exact file-map paths changed, and the final index listing is byte-for-byte identical to the pre-topic listing. Pre-existing staged entries are user-owned; do not stage or unstage them.

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
| Status | **Complete — local dbt/DuckDB supporting proof only.** The wrapper derived every boundary from the validated medium config, the parent-inclusive dbt slice completed on its first attempt, and the focused contract suite is green. The local candidate remains correctly `runtime pending`; no strict promotion or rubric score is claimed. |
| Affected files | Modified only `infra/analytics/dbt/dbt_project.yml`, `infra/analytics/dbt/models/silver/stg_commerce_events.sql`, `infra/analytics/dbt/models/gold/feat_customer_90d.sql`, `infra/analytics/dbt/models/gold/feat_stream_60m.sql`, `infra/analytics/dbt/models/gold/feat_customer_unified.sql`, `infra/analytics/dbt/models/gold/_features.yml`, and this Completion Record. Created only `scripts/analytics/run_section03_dbt.py`, `infra/analytics/dbt/models/gold/ml_customer_label.sql`, `infra/analytics/dbt/models/gold/agg_feature_health_daily.sql`, `infra/analytics/dbt/models/gold/feature_drift_alerts.sql`, `infra/analytics/dbt/models/gold/ml_customer_purchase_training.sql`, `infra/analytics/dbt/models/gold/_drift.yml`, `infra/analytics/dbt/tests/assert_ml_customer_label_matches_horizon.sql`, `infra/analytics/dbt/tests/assert_training_features_are_point_in_time.sql`, `infra/analytics/dbt/tests/assert_drift_alert_threshold.sql`, `infra/analytics/dbt/tests/assert_commerce_event_dedup_unambiguous.sql`, and `tests/unit/test_section03_dbt_contract.py`. No dependency file changed. |
| Commands / exit codes | Pre-edit: `rtk git status --short --branch` → `0` on `feature/implement-edai2`; `rtk git branch --show-current` → `0`; `rtk git rev-parse HEAD` → `0` at `81d54aab0aa7eedd3aca767cefff23b986255de0`; `rtk git ls-files --stage` → `0`, 792 lines, normalized SHA-256 `8ff0515663cbb3ad42292fdd5c46a957bdefe2ca89244c539f79b905f40ad01e`; the three `rtk certutil -hashfile ... SHA256` source checks → `0` with exact locked matches; predecessor candidate hash and verifier → `0`, exact output `section03 manifest: PASS (runtime pending)`.<br>TDD: `rtk uv run pytest tests/unit/test_section03_dbt_contract.py -q` → `1` (`8 failed`) before implementation; the same command after the wrapper → `1` (`5 failed, 3 passed`); after deterministic staging and cutoff-safe existing features → `1` (`4 failed, 4 passed`); after the four new models, YAML contracts, and singular tests → `0` (`8 passed`); after `_features.yml` tightening → `0` (`8 passed`).<br>Runtime: `rtk uv run python scripts/analytics/run_section03_dbt.py --config configs/generator/base.yaml --scale medium --project-dir infra/analytics/dbt --profiles-dir infra/analytics/dbt --select +ml_customer_purchase_training +feature_drift_alerts` → `0`; dbt reported `PASS=88 WARN=0 ERROR=0 SKIP=0 TOTAL=88` (`13` table models, `12` view models, `62` data tests, one project hook). The corrected read-only DuckDB relation/schema inspection → `0`; two preceding inspection-only SQL attempts → `1` on reserved alias `rows`, then `1` on the corrected health column name before the final successful query. `rtk rg -n -i "password|secret|token|credential" infra/analytics/dbt/logs/dbt.log` → `1`, meaning no match. Final focused pytest → `0` (`8 passed`); `rtk git diff --check` → `0`; `rtk git status --short --branch` → `0`; `rtk git ls-files --stage` → `0`, still 792 lines and byte-for-byte equivalent after LF normalization with SHA-256 `8ff0515663cbb3ad42292fdd5c46a957bdefe2ca89244c539f79b905f40ad01e`. |
| Evidence + SHA-256 | Authoritative machine evidence: `infra/analytics/dbt/target/run_results.json` → `eda13eb3a10911e6d8322474b7a13f91a20ddf3889d8cbe7e7db8b7cfc85109d` (`88` results: `62 pass`, `26 success`, no failures; dbt elapsed `31.107697010040283` seconds); sanitized `infra/analytics/dbt/logs/dbt.log` → `cd53cc359e59bb631c1b07b1079bb833dd5f8820aa6b31fc018ccf9351de480f`; local `data/gold/vina_bim_shop.duckdb` → `bd3d7ad8ff2281ca632f17a521ae146f8d42c4f45282f92a923e79b28c6cbaec`.<br>Read-only relation proof: labels `11,996` rows / `11,996` distinct IDs / `4,395` positives / integer range `0..1`; training `11,996` rows / `11,996` distinct IDs / `4,395` positives / maximum `event_timestamp` and `created` both `2026-04-24 23:59:00`; feature rows offline `11,996`, stream `99,831`, unified `11,996`; health `22` rows from `2026-04-10` through `2026-05-01`, `7` stable / `15` warning / `0` alert, peak PSI `0.120526925411`, `0` nonfinite values; alerts `0` rows. Information-schema inspection confirmed exact two-column `id VARCHAR,label INTEGER` label order, exact 13-column training order/types, and declared health/alert schemas. Candidate manifest remains `8c0ff22ef528f4170506734f03c055aeec742e62bd9e94d7d0f703e47653bed7`, bundle `c220ab9dc815fb6ccff187b661a0fa483f8c16bcda368dd214a0f78633d6c92f`. |
| Screenshot QA | No screenshot was required, created, or claimed. Topic 03 owns machine-readable dbt and relation evidence only; successor topics retain final UI-capture ownership. |
| Cleanup / runtime release | One local dbt/DuckDB process ran serially and exited. The temporary pre-build recovery copy `C:\Users\oou1hc\AppData\Local\Temp\edai2-topic03-vina-bim-shop-before-81d54aa.duckdb` was removed after success (`removed=True`). `infra/analytics/dbt/target`, `infra/analytics/dbt/logs`, and the rebuilt ignored DuckDB database are retained because they are this topic's handoff evidence. No persistent service, container, Kind/GKE context, kubeconfig, Docker resource, cloud resource, or GCP runtime was acquired, stopped, pruned, or mutated. |
| Resource / budget gates | C: had `170.1 GiB` free before the `183,250,944`-byte recovery copy and build. Exactly one medium dbt runtime slice ran, completing in `48.2` seconds wall time (`31.107697010040283` seconds reported by dbt). No tuning retry, dependency installation, `uv add`, Kubernetes command, Docker command, live GCP mutation, or unrelated process termination occurred. |
| Rollback / recovery | The pre-build DuckDB copy was retained until all 88 dbt results and relation checks passed, then removed. If the ignored local database or dbt artifacts must be rebuilt, rerun the exact wrapper command against the unchanged canonical raw inputs and candidate identity; source rollback is the unstaged working-tree diff only. Do not stage/unstage user entries, reinterpret warning-level PSI as an alert, or promote the pending manifest here. |
| Limitations | This is local DuckDB/dbt evidence. It does not establish Spark parity, Airflow or DataHub runtime, Feast serving, strict candidate promotion, GKE behavior, GCP resources, or final UI evidence. The truthful alert table is empty because peak PSI is warning-level and below the configured alert boundary. |
| Rubric disposition | **Complete supporting implementation evidence for `Sheet3!E34` only.** Topic 07 remains sole primary owner and the satisfied rubric subtotal remains zero until strict promotion and successor-owned runtime proof. Local output is not GKE evidence. |
| Stop conditions | None triggered. Required predecessor status and identity were valid; all three locked SHA-256 values matched; disk headroom was ample; no pre-existing staged/index change appeared; focused tests, dbt build/tests, relation invariants, sanitization, whitespace, branch, and index gates passed; the empirical PSI result matched the predecessor without a tuning retry. |
| Successor handoff | **Topic 04 may proceed.** Use `scale=medium`, seed `42`, `drift_start_ts=2026-04-11T08:23:00Z`, `feature_cutoff_ts=2026-04-24T23:59:00Z`, `label_end_ts=2026-05-01T23:59:00Z`, `baseline_date=2026-04-10`, warning `0.10`, alert `0.15`, epsilon `0.000001`, bins `10`; wrapper selector `+ml_customer_purchase_training +feature_drift_alerts`; dbt result `88/88` successful/pass; label/training `11,996` rows with `4,395` positives; health `22` rows with peak PSI `0.120526925411`; alerts `0`. Consume the evidence hashes above, retain `runtime pending`/zero-credit semantics, and perform Spark parity in Topic 04 rather than treating local DuckDB as Spark, GKE, or final rubric proof. |
### Follow-up rebaseline — 2026-08-04

The training join/sample CSV contract was tightened to fixed `%.12f` serialization so Topic 04 can retain twelve-decimal numeric normalization without relaxing tolerance. The amended Section 03 source SHA-256 is `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`.

The medium seed-42 regeneration command `rtk uv run python scripts/generate/run_generator.py --scale medium --mode full --seed 42` exceeded the shell wrapper's 300-second limit (`124`), but its task-owned child completed and atomically published candidate bundle `1b4123b312da3d1aca70c2dc4f44cf68db248f3b43aad830e8519ca7bbab7fd3`. The candidate manifest SHA-256 is `4af7f8a84da020877bea580f6fc74a9011d371ac2a84a56f7053e83f76246ba1`; `rtk uv run python scripts/generate/verify_section03_manifest.py --manifest evidence/03_data_generator_improvement/section03_candidate_manifest.json --allow-runtime-pending` exited `0` with `section03 manifest: PASS (runtime pending)`. The prior `c220ab9dc815fb6ccff187b661a0fa483f8c16bcda368dd214a0f78633d6c92f` bundle remains present.

The candidate retains scale `medium`, seed `42`, the locked Section 03 windows, 11,996 one-to-one training rows, and the existing config SHA-256 `5c5029fea77d93c3941d87d9a60f85cfe374f36899c3d3c1b028f3f5f3c3cd97`. Topic 04 must consume the new candidate identity; no strict runtime or rubric credit is claimed by this follow-up alone.
