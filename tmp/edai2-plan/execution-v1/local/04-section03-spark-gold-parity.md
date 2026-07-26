# Section 03 Spark Gold and Parity Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Plan Task 6: render and test seven parameterized Spark Gold relations and prove keyed full-row parity against dbt and generator evidence.

**Architecture:** One parsed generator configuration creates `Section03SqlParameters` for Spark query rendering and exact keyed parity reports against generator/dbt outputs.

**Tech Stack:** Python 3.12, Spark SQL, DuckDB/Trino test doubles, pytest, `uv`, Make, `rtk`.

## Locked sources and acceptance procedure

- Read `C:\Users\oou1hc\.codex\RTK.md` before every operator session and prefix every shell command with `rtk`.
- Locked Section03 source: `tmp/edai2-plan/03_data_generator_improvement.md`, SHA256 `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`.
- Locked EDAI2 source: `tmp/edai2-plan/04.2_llm_design.md`, SHA256 `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`.
- Locked rubric source: `tmp/rubic-check/Coursework Tracking (Public).xlsx`, SHA256 `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- Preflight and final acceptance both run `rtk git status --short --branch`; record the output and reject a branch change during the serial session.
- Final acceptance also records SHA256s, evidence/screenshot QA, cleanup/runtime release, limitations, and successor handoff in the Completion Record.
- Keep one current branch and one serial session; any Kubernetes action sets `KUBECONFIG` and `--context` explicitly, never the corporate current context.
- Kind is local smoke only and never GKE/rubric evidence; do not run Docker prune or stop unrelated containers.

## Metadata

| Field | Decision |
|---|---|
| Phase | 4 — analytic parity |
| Source tasks | Section03 Task 6 |
| Rubric contribution | Supporting evidence for `Sheet3!E34` only; Topic 07 is sole primary owner |
| Prerequisites | Topic 03 Completion Record and candidate manifest identity |
| Blocked successors | Topic 05 only |
| Runtime ownership | Spark/parity operator; serial session |
| Local/GCP class | Local/mock Spark test; no GCP |

## Architecture and technology

The Spark stage accepts generator config/scale, calculates `Section03SqlParameters` once, and renders the same seven DP3 tables in dependency order. In strict Section 03 mode, `scripts/spark/run_batch.py` derives `start_ts`, `end_ts`, feature cutoff, label end, drift start, and baseline date from that parsed config and scale. Explicit `--start-ts`/`--end-ts` values are rejected unless they exactly match those derived values. Parity compares keyed full rows—generator versus dbt and generator versus Spark—not only aggregates. Float persistence is normalized at twelve decimal places with absolute tolerance `1e-9`; labels/keys/timestamps/strings are exact.

## Global constraints

The three locked hashes above remain authoritative. Work on the current branch in one serial session; do not create a worktree or branch and do not stage, commit, push, or open a PR. `REQUIRED_GOLD_TABLES` has no duplicates; core and DP3 sets are disjoint. No hard-coded cutoff/threshold/horizon. Operators use `rtk uv run`; Make recipes are `uv run`. Do not invoke GKE/GCP, prune Docker, or stop unrelated containers.

## Current-state refresh — read-only planning phase

```text
rtk git branch --show-current
rtk git status --short --branch
rtk uv run pytest tests/unit/test_spark_batch_runtime.py tests/unit/test_optional_duckdb_imports.py -q
rtk rg -n "GOLD_SERVING_TABLES|REQUIRED_GOLD_TABLES|ordered_core_gold_queries" src scripts tests
```

Expected: existing query order and test baseline are recorded without writing tables.

## Scope and non-goals

In scope: parameter propagation, SQL rendering, seven-table registration, full-row parity tests/reports. Out of scope: real cluster provisioning, running Airflow/DataHub, chart deployment, and modifying generator public APIs.

## Exact file map

| Action | Path |
|---|---|
| Modify | `src/vina_bim_shop/lakehouse/spark/sql.py`, `src/vina_bim_shop/lakehouse/spark/constants.py`, `src/vina_bim_shop/lakehouse/spark/job.py`, `src/vina_bim_shop/lakehouse/spark/runner.py`, `src/vina_bim_shop/lakehouse/spark/parity.py` |
| Modify | `scripts/spark/run_batch.py` |
| Modify | `tests/unit/test_spark_batch_runtime.py` |
| Modify | `tests/unit/test_optional_duckdb_imports.py` |

## Interfaces, data flow, and failure modes

Config/scale → derived batch/window timestamps and `Section03SqlParameters` → rendered Spark queries → seven persisted outputs → keyed comparison report. Fail on missing config/scale, an explicit batch timestamp that differs from the config-derived value, supplied cutoff not present in SQL, leakage predicates absent, inaccurate percentile shortcut, missing/extra key, nonexact label, nonfinite PSI, tolerance violation, or a candidate manifest/hash mismatch.

## Ordered test-first execution tasks

- [ ] Add failing query-order/leakage, strict config-derived batch-window, explicit mismatch, and four keyed full-row comparison tests, then run `rtk uv run pytest tests/unit/test_spark_batch_runtime.py -q`; expected FAIL because parameterized DP3 queries and strict batch semantics are absent.
- [ ] Thread `--generator-config` and `--generator-scale` through `job.py`, `runner.py`, `scripts/spark/run_batch.py`, and submit construction, then run `rtk uv run pytest tests/unit/test_spark_batch_runtime.py -q`; expected FAIL only on missing seven-query/table/parity contracts while config, scale, and derived start/end/cutoff metadata pass.
- [ ] Implement the seven exact Spark queries, type-7 PSI, ordered `DP3_GOLD_TABLES`, extended `GOLD_SERVING_TABLES`, and duplicate-free `REQUIRED_GOLD_TABLES`, then run `rtk uv run pytest tests/unit/test_spark_batch_runtime.py -q`; expected FAIL only on missing keyed parity report assertions.
- [ ] Implement generator-vs-dbt, generator-vs-Spark, and dbt-vs-Spark reports; production passes validated runtime values equivalent to `scripts/analytics/run_section03_dbt.py --project-dir infra/analytics/dbt --profiles-dir infra/analytics/dbt --config configs/generator/base.yaml --scale medium` as a direct argument array, then run `rtk uv run pytest tests/unit/test_spark_batch_runtime.py -q`; expected PASS with separate zero mismatch counts and bound manifest/config hashes.
- [ ] Run `rtk uv run pytest tests/unit/test_spark_batch_runtime.py tests/unit/test_optional_duckdb_imports.py -q`; expected PASS with cutoff-safe SQL, derived timestamps, ordered seven-table persistence, and no optional DuckDB import regression.
- [ ] Run `rtk git diff --check`, `rtk git status --short --branch`, and `rtk git ls-files --stage`; expected no whitespace errors, the original branch unchanged, only exact file-map paths changed, and the final index listing is byte-for-byte identical to the pre-topic listing. Pre-existing staged entries are user-owned; do not stage or unstage them.

## Evidence and screenshot ownership

The parity operator owns command logs and sanitized parity report containing candidate/config hashes and both comparison families. This is machine proof for finalization, not a GKE screenshot.

## Cleanup

Clean only session-owned local/mock tables and reports after hashes are retained; do not delete canonical bundles or unrelated Spark resources.

## Rubric table

| Cell | Parity contribution | Final scoring |
|---|---|---|
| Sheet3!E34 | Exact label key/values and training join | Section03 strict root required |

## Definition of Done

The seven outputs render in required order, all leakage/PSI parity tests pass, and a hash-bound no-mismatch report is available to runtime promotion.

## Completion Record

| Field | Record |
|---|---|
| Status | Not started |
| Affected files | Exact file map above |
| Commands / exit codes | Record every checkbox command and numeric exit code, ending with `rtk git status --short --branch` |
| Evidence + SHA256 | Record parity report/log SHA256 or `no artifact produced` |
| Screenshot QA | `No screenshot required; report is machine evidence` |
| Cleanup / runtime release | Record session-owned local table cleanup; no runtime acquired |
| Limitations | Mock/local parity is not Airflow or DataHub runtime proof |
| Successor handoff | Candidate/config hashes and parity report to plan 05 |
