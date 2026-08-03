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
| Status | Partial — Spark SQL/config/parity implementation and relevant tests pass, but strict runtime promotion is blocked by the Docker Spark-image CA failure, missing required dbt relations, a fail-closed generator/dbt training mismatch, and a bounded local Spark SQL preflight that remains Partial/Missing after its one retry. |
| Affected files | Modified only `scripts/spark/run_batch.py`, `src/vina_bim_shop/lakehouse/spark/constants.py`, `src/vina_bim_shop/lakehouse/spark/job.py`, `src/vina_bim_shop/lakehouse/spark/parity.py`, `src/vina_bim_shop/lakehouse/spark/runner.py`, `src/vina_bim_shop/lakehouse/spark/sql.py`, `tests/unit/test_spark_batch_runtime.py`, and this Completion Record. `tests/unit/test_optional_duckdb_imports.py` was inspected and remained unchanged; no dbt, generator, orchestration, Kubernetes, or GCP file changed. |
| Commands / exit codes | Fresh preflight `rtk git status --short --branch` 0 on `feature/implement-edai2`; all three locked-source `rtk certutil -hashfile ... SHA256` checks 0; pre-edit `rtk git ls-files --stage` 0 with unchanged raw 84,466-byte SHA256 `aabace61a9bf41110fc1d2f3111163e00aa6e2dcde1e87263e4b48ee90bec19c`. Historical test-first RED `rtk uv run pytest tests/unit/test_spark_batch_runtime.py -q` 1 (expected missing `DP3_GOLD_TABLES`); fresh Spark runtime gate 0 (`33 passed`); fresh optional-DuckDB plus predecessor dbt contract gate 0 (`10 passed`); exact direct dbt wrapper `rtk uv run python scripts/analytics/run_section03_dbt.py --config configs/generator/base.yaml --scale medium --project-dir infra/analytics/dbt --profiles-dir infra/analytics/dbt` 0 (`PASS=88 WARN=0 ERROR=0 SKIP=0 TOTAL=88`); local DuckDB-backed parity sanity 1 with the report written and fail-closed; the earlier base-image fixture slice returned 0 in the prior execution slice, but the fresh bounded local Spark SQL preflight returned 1 because the image had no `python` executable, and its single `python3` retry returned 1 after Spark startup on a `TimestampType` fixture error—no further tuning retry was made; relevant Section 03/Spark acceptance 0 (`96 passed in 94.74s`); `rtk uv run pytest tests/unit -q` remains timed out at the 180-second bound with exit 124; `rtk uv run python -m py_compile ...` 0; `rtk git diff --check` 0; final record-only acceptance `rtk uv run pytest tests/unit/test_spark_batch_runtime.py tests/unit/test_optional_duckdb_imports.py -q` 0 (`35 passed`), `rtk git diff --check` 0, `rtk git diff --name-only` 0 with exactly the eight paths in Affected files, final `rtk git ls-files --stage` 0 with the unchanged raw index SHA256 above, and final `rtk git status --short --branch` 0 on the unchanged branch. |
| Evidence + SHA256 | Locked sources: Section03 `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`, EDAI2 `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`, rubric workbook `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`. Candidate manifest `evidence/03_data_generator_improvement/section03_candidate_manifest.json`: `8c0ff22ef528f4170506734f03c055aeec742e62bd9e94d7d0f703e47653bed7`; bundle `c220ab9dc815fb6ccff187b661a0fa483f8c16bcda368dd214a0f78633d6c92f`; bound config `configs/generator/base.yaml`: `5c5029fea77d93c3941d87d9a60f85cfe374f36899c3d3c1b028f3f5f3c3cd97`. Diagnostic report `tmp/section03-runtime/parity-dbt-sanity/dbt_parity_report.json`: `ad7f20441d8650084afd4a470f4d920a1f953e5dc0f4c0487b395d470de08400`; Markdown companion: `ac83fa1cc37be9a41cd265a3689d1ee5436794e1b868a1fb43f7fcbb7fa65447`. Report is `success=false`: dbt-vs-Spark keyed checks pass for all four DP3 tables; generator-vs-dbt and generator-vs-Spark each fail only `ml_customer_purchase_training` with 9,592 field mismatches; 16 required legacy relations are absent on each local side. Current dbt artifacts after the fresh wrapper run: `infra/analytics/dbt/target/manifest.json` `0cef60444ab4c5208e3381df737b34975a4e480759e3f227f566b4d88048ecc7`, `run_results.json` `aadfb7ebb1e2c7f35ed4be5ad62d746c5ce104b5b710c4b22c73578700c622ab`, `logs/dbt.log` `77c316ec0c7729fae12ead1c3f1cea3976f2d49cdd27a6d148ab364cd897c49d`, and local DuckDB `data/gold/vina_bim_shop.duckdb` `52f70910d274b0c188713c2b6e1cd76c12b63102225e09652ffa0479c902d6ea`. |
| Screenshot QA | `No screenshot required; report is machine evidence` |
| Cleanup / runtime release | `rtk docker compose ps` ended with `0 services`; the failed compose attempt acquired no persistent batch service, and the base Spark smoke used `--rm`. The three pre-existing Docupedia containers (`951a7be1161c`, `240ac59a8361`, `c27c1f2757ec`) were not stopped or pruned. The hash-bound parity report and canonical dbt artifacts were retained for review; no Kubernetes/GCP runtime or session-owned persistent table was created. |
| Limitations | The local/base-image Spark smoke is not Iceberg/Trino or GKE evidence. The earlier base-image slice was local syntax/analysis only; the fresh bounded slice is Partial/Missing after the single documented retry and supplies no authoritative Spark output claim. Full Spark/Iceberg runtime was not available because `infra/spark/Dockerfile` dependency download failed TLS CA verification (`curl` exit 60); no out-of-scope Dockerfile repair was made. The current Task 5 dbt artifact does not expose 16 relations in the retained all-Gold inventory, and its training features disagree with the locked generator on 9,592 customer keys (notably payment amount and stream-window semantics); Topic 04 does not authorize dbt/generator edits, so parity correctly fails closed. The wider unit suite exceeded its 180-second bound, while all 96 relevant Section 03/Spark tests passed. No E34 runtime/promotion claim or GKE claim is made. |
| Successor handoff | Topic 05 remains blocked on this gate. Before promotion, repair or explicitly authorize the upstream dbt/generator contract scope, rebuild the full required Gold inventory from the bound candidate `c220ab9dc815fb6ccff187b661a0fa483f8c16bcda368dd214a0f78633d6c92f` and config SHA `5c5029fea77d93c3941d87d9a60f85cfe374f36899c3d3c1b028f3f5f3c3cd97`, restore a trusted Spark image build, rerun the direct dbt wrapper, real Spark/Iceberg parity, and the three keyed comparison families, then replace the diagnostic failure report only with a zero-mismatch report. |
