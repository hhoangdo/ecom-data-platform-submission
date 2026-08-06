# Section 03 Airflow and DataHub Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Section 03 Tasks 7–8 contracts locally: seven-table DP3 validation, strict Airflow DAG-conf forwarding/capture, and exact DataHub lineage/assertion publication and read-back behavior.

**Architecture:** A thin Airflow DAG adapter forwards config path, scale, and candidate-manifest SHA-256 to the unchanged six-stage application. Table-specific validation writes hash-bindable artifacts. DataHub emits the exact seven-output graph and five assertions; live execution is deferred exclusively to Topic 07.

**Tech Stack:** Python 3.12, Airflow REST API, Trino, Great Expectations, DataHub/OpenSearch, pytest, `uv`, Make, `rtk`.

## Locked sources and execution policy

- Read `C:\Users\oou1hc\.codex\RTK.md`; every shell command begins with `rtk`.
- Section 03 source is `tmp/edai2-plan/03_data_generator_improvement.md`, SHA-256 `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`.
- EDAI2 source is `tmp/edai2-plan/04.2_llm_design.md`, SHA-256 `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`.
- Rubric source is `tmp/rubic-check/Coursework Tracking (Public).xlsx`, SHA-256 `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- Work on the current branch in one serial session. Do not create a worktree or branch and do not stage, commit, push, or open a PR.
- Do not start Airflow/DataHub, mutate GCP/Kubernetes, prune Docker, or stop containers in this topic. Topic 07 owns the live local runtime capture.

## Metadata

| Field | Decision |
|---|---|
| Phase | 5 — local orchestration/governance contracts |
| Source tasks | Section 03 Tasks 7–8 |
| Rubric contribution | Supporting evidence for `Sheet3!E32:E34`; Topic 07 is sole primary owner |
| Prerequisites | Topic 04 Completion Record |
| Blocked successors | Topic 06 |
| Runtime ownership | Local contract-test operator; one serial session |
| Local/GCP class | Local static/unit tests; no runtime/GCP mutation |

## Global constraints

- Strict Section 03 DAG conf contains exactly the required config path, scale, and candidate-manifest SHA-256; no Airflow Variable fallback is legal.
- Cutoff comes from config-aware Spark compute metadata, never `data_interval_end`.
- Preserve all six stage functions, TaskGroup IDs, dependency order, and failure propagation.
- `FEATURE_TABLES` and seeded metadata use exact seven-table dependency order.
- DataHub direct parents, schemas, assertions, ownership/tags, DP1/DP2 boundaries, and exception propagation are preserved.
- `run_section03_dp3.py` and `capture_evidence.py --section03` are implemented/tested here but executed live only by Topic 07.
- Candidate/runtime test output earns zero until Topic 07 finalization.

## Current-state refresh — read-only planning phase

```text
rtk git status --short --branch
rtk git branch --show-current
rtk rg -n "FEATURE_TABLES|DP3_TABLE_CONTRACTS|mini_coursework_pipeline|emit_spark_batch_lineage|emit_coursework_pipeline" src/vina_bim_shop/orchestration src/vina_bim_shop/datahub_lineage infra/orchestration scripts/datahub tests/unit
rtk uv run pytest tests/unit/test_orchestration_runtime.py tests/unit/test_airflow_coursework_metadata.py tests/unit/test_orchestration_dag_adapters.py tests/unit/test_datahub_coursework_lineage.py tests/unit/test_datahub_capture_evidence.py tests/unit/test_datahub_adr_boundaries.py -q
```

Expected: the same branch and current three-table behavior are recorded; no DAG trigger, metadata emit, or service startup occurs.

## Scope and non-goals

In scope: seven table contracts, strict DAG adapter/wrapper, detailed validation payloads, DataHub graph/assertions, sanitized capture code, and local tests. Non-goals: live Airflow/DataHub execution, browser capture, final evidence promotion, GKE/GCP, or changing DP1/DP2.

## Exact file map

| Action | Exact path | Responsibility |
|---|---|---|
| Modify | `src/vina_bim_shop/orchestration/mini_coursework_pipeline.py` | Expand DP3 outputs and table-specific validation. |
| Modify | `infra/orchestration/airflow/dags/mini_coursework_pipeline.py` | Forward three strict DAG-conf values without Variable fallback. |
| Modify | `infra/orchestration/airflow/bootstrap/seed_coursework_metadata.py` | Seed exact seven-table DP3 output order. |
| Create | `scripts/orchestration/run_section03_dp3.py` | Verify candidate, trigger/poll six tasks, and export matching sanitized runtime artifacts. |
| Modify | `src/vina_bim_shop/datahub_lineage/spark_lineage.py` | Add exact parents for four new Gold outputs and corrected feature parents. |
| Modify | `src/vina_bim_shop/datahub_lineage/coursework_pipelines.py` | Publish seven outputs, schemas, descriptions, and assertions. |
| Modify | `scripts/datahub/capture_evidence.py` | Add strict Section 03 emit/index/query/capture mode. |
| Modify | `tests/unit/test_orchestration_runtime.py` | Test DP3 metadata, validation facts, and blocking fixtures. |
| Modify | `tests/unit/test_airflow_coursework_metadata.py` | Test seeded seven-table metadata. |
| Modify | `tests/unit/test_orchestration_dag_adapters.py` | Test exact DAG-conf forwarding and unchanged graph. |
| Modify | `tests/unit/test_datahub_coursework_lineage.py` | Test exact inputs, outputs, schemas, assertions, and edges. |
| Modify | `tests/unit/test_datahub_capture_evidence.py` | Test strict indexed read-back and sanitized capture. |
| Modify | `tests/unit/test_datahub_adr_boundaries.py` | Preserve DP1/DP2 ownership and exception behavior. |

## Interfaces and data flow

Candidate identity plus config/scale enter `run_section03_dp3.py`; the application records `dp3_compute.json`, `dp3_validate.json`, and `quality/coursework_feature_contract.json`. DataHub publishes direct edges: feature parents, `ml_customer_label <- dim_customer,fact_payment_attempt`, `agg_feature_health_daily <- dim_customer,fact_order`, `feature_drift_alerts <- agg_feature_health_daily`, and `ml_customer_purchase_training <- ml_customer_label,feat_customer_unified`.

## Failure modes

Fail on missing strict DAG conf, Variable fallback, config/scale/cutoff/hash mismatch, missing table, wrong ordered columns/key, extra label column, duplicate/nonbinary label, training cutoff/created leakage, negative/nonfinite PSI, alert below `0.15`, stale task artifact, failed/timeout task, absent DataHub parent/schema/assertion, direct-GMS-only lookup without indexed search, or DP1/DP2 regression.

## Ordered test-first execution tasks

- [ ] Add seven-table Airflow metadata/validation fixtures and corrupt-table cases, then run `rtk uv run pytest tests/unit/test_orchestration_runtime.py tests/unit/test_airflow_coursework_metadata.py tests/unit/test_orchestration_dag_adapters.py -q`; expected FAIL because current DP3 assumes three generic feature tables.
- [ ] Implement `DP3_TABLE_CONTRACTS`, strict config/scale/manifest binding, exact validation queries, and thin DAG forwarding, then run `rtk uv run pytest tests/unit/test_orchestration_runtime.py tests/unit/test_airflow_coursework_metadata.py tests/unit/test_orchestration_dag_adapters.py -q`; expected PASS with unchanged six-stage DAG order and every corrupt fixture blocking.
- [ ] Add strict wrapper tests for candidate verification, REST trigger/poll, six matching terminal tasks, timeout/failure/stale artifact rejection, redaction, and output inventory, then run `rtk uv run pytest tests/unit/test_orchestration_runtime.py tests/unit/test_orchestration_dag_adapters.py -q`; expected FAIL until `scripts/orchestration/run_section03_dp3.py` is complete.
- [ ] Implement `scripts/orchestration/run_section03_dp3.py`, then run `rtk uv run pytest tests/unit/test_orchestration_runtime.py tests/unit/test_orchestration_dag_adapters.py -q`; expected PASS without contacting a live Airflow endpoint.
- [ ] Add exact seven-output DataHub graph/schema/assertion and indexed-read-back tests, then run `rtk uv run pytest tests/unit/test_datahub_coursework_lineage.py tests/unit/test_datahub_capture_evidence.py tests/unit/test_datahub_adr_boundaries.py -q`; expected FAIL because current lineage/capture covers only three DP3 outputs.
- [ ] Implement the exact DP3 lineage/assertions and `--section03` capture behavior, then run `rtk uv run pytest tests/unit/test_datahub_coursework_lineage.py tests/unit/test_datahub_capture_evidence.py tests/unit/test_datahub_adr_boundaries.py -q`; expected PASS with seven ordered outputs, exact parents/schemas/five assertions, indexed search, and intact DP1/DP2.
- [ ] Run `rtk uv run pytest tests/unit/test_orchestration_runtime.py tests/unit/test_airflow_coursework_metadata.py tests/unit/test_orchestration_dag_adapters.py tests/unit/test_datahub_coursework_lineage.py tests/unit/test_datahub_capture_evidence.py tests/unit/test_datahub_adr_boundaries.py -q`; expected PASS with zero failures, skips, or xfails in the listed files and no live service contact.
- [ ] Run `rtk git diff --check`, `rtk git status --short --branch`, and `rtk git ls-files --stage`; expected no whitespace errors, the original branch unchanged, only exact file-map paths changed, and the final index listing is byte-for-byte identical to the pre-topic listing. Pre-existing staged entries are user-owned; do not stage or unstage them.

## Evidence and screenshot ownership

Topic 05 owns local test logs only. Topic 07 owns live `tmp/section03-runtime/airflow` and `tmp/section03-runtime/datahub` captures and the deterministic `Sheet3!E32` image. No Topic 05 screenshot proves runtime or rubric satisfaction.

## Cleanup

Test fixtures remove temporary API/capture trees. No Airflow/DataHub runtime is acquired, so no service teardown occurs. Do not delete volumes, metadata, candidates, or unrelated files.

## Rubric table

| Workbook cell | Supporting proof | Ownership rule |
|---|---|---|
| `Sheet3!E32` | Table-specific runtime contract for training/health proof | Supporting only; live proof/promote in Topic 07 |
| `Sheet3!E33` | Config/scale/cutoff faithful orchestration metadata | Supporting only; live proof/promote in Topic 07 |
| `Sheet3!E34` | Exact label validation, lineage, and assertion targets | Supporting only; live proof/promote in Topic 07 |

## Definition of Done

All six orchestration/DataHub test files pass; strict wrapper/capture code is ready but not executed live; seven exact outputs/contracts/parents/assertions are preserved; no runtime/GCP mutation or adjacent refactor occurs.

## Completion Record

| Field | Record |
|---|---|
| Status | Complete — local contract implementation only; live Airflow/DataHub execution remains deferred to Topic 07. |
| Assumptions verified | Topic 04 predecessor Completion Record and immutable `tmp/section03-runtime/spark-strict-v4` boundary were read; Sheet3 values are `E32=1`, `E33=1`, `E34=2`; branch remained `feature/implement-edai2`; no default Kubernetes context, GCP, Docker, Airflow, or DataHub runtime was contacted. |
| Current-state delta | Expanded the six-stage local orchestration contract from three to seven DP3 outputs; added strict three-field DAG-conf binding, candidate-window/config/hash/cutoff checks, compute-metadata read-back, table-specific metrics, and matching sanitized Airflow task/artifact capture; and replaced the old three-output DataHub contract with exact seven-output schemas, direct parents, five assertions, indexed retry/read-back, and secret sanitization. Legacy empty-conf Airflow runs and default DP1/DP2 DataHub schema behavior remain compatible. The Topic 05 Section 03 lock was reconciled from the stale recorded value to the recomputed authoritative value `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`. |
| Affected files | `infra/orchestration/airflow/bootstrap/seed_coursework_metadata.py`; `infra/orchestration/airflow/dags/mini_coursework_pipeline.py`; `scripts/orchestration/run_section03_dp3.py`; `scripts/datahub/capture_evidence.py`; `src/vina_bim_shop/orchestration/mini_coursework_pipeline.py`; `src/vina_bim_shop/datahub_lineage/coursework_pipelines.py`; `src/vina_bim_shop/datahub_lineage/spark_lineage.py`; `tests/unit/test_orchestration_runtime.py`; `tests/unit/test_airflow_coursework_metadata.py`; `tests/unit/test_orchestration_dag_adapters.py`; `tests/unit/test_datahub_coursework_lineage.py`; `tests/unit/test_datahub_capture_evidence.py`; `tests/unit/test_datahub_adr_boundaries.py`; this Completion Record file. No predecessor record or runtime evidence root was changed. |
| Commands / exit codes | Pre-topic baseline `rtk uv run pytest` six-file command: `0` (`51 passed, 1 skipped`); DP3 RED: `1` (`5 failed`), initial DP3 GREEN: `0` (`27 passed`); strict wrapper RED: `1`, final wrapper-focused GREEN: `0` (`3 passed, 19 deselected`); DataHub RED: `1` (`7 failed`), DataHub GREEN: `0` (`31 passed`); final six-file acceptance `rtk uv run pytest tests/unit/test_orchestration_runtime.py tests/unit/test_airflow_coursework_metadata.py tests/unit/test_orchestration_dag_adapters.py tests/unit/test_datahub_coursework_lineage.py tests/unit/test_datahub_capture_evidence.py tests/unit/test_datahub_adr_boundaries.py -q`: `0` (`63 passed`, zero skips/xfails); `rtk uv run python -m compileall -q` targeted Topic 05 modules: `0`; `rtk git diff --check`: `0`; final `rtk git status --short --branch --untracked-files=all`: `0`; pre/post index `rtk fc.exe /b` comparison: `0`, `FC: no differences encountered`; all three `rtk certutil.exe -hashfile ... SHA256` lock checks: `0`. |
| Evidence + SHA-256 | No repository test-log artifact was produced; pytest output was terminal-only. Locked sources verified: Section 03 `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`; EDAI2 `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`; workbook `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`. No live Airflow/DataHub or screenshot evidence was generated. |
| Screenshot QA | No runtime screenshot is owned by Topic 05 |
| Cleanup / runtime release | Pytest temporary fixtures and the two exact external pre/post index snapshots were removed. No service was started, stopped, pruned, deployed, or otherwise mutated; no runtime acquired. |
| Rubric disposition | Supports E32 with seven table-specific DP3 contracts and training/health/alert checks; supports E33 with strict config/scale/candidate-hash forwarding and capture; supports E34 with exact `id,label`, five assertion targets, direct lineage, and indexed read-back. These are local supporting contracts only; no candidate or mock result earns live rubric credit in Topic 05. |
| Limitations | Local mocks prove request/contract/error handling but do not prove a real Airflow run, Trino result, DataHub GMS response, OpenSearch index hit, GKE state, or screenshot. `feature_drift_alerts` empty output is accepted only with its exact schema; live runtime must still prove the populated/empty case, all artifact hashes, indexed search, and UI evidence. |
| Successor handoff | Topic 07 should run `scripts/orchestration/run_section03_dp3.py` with the compatible `--section03-manifest`, `--run-id`, `--config`, `--scale`, `--output`, and `--strict` interface, then run `scripts/datahub/capture_evidence.py --section03 --section03-manifest ... --airflow-capture ... --output ... --strict`. Promote only after real six-task success, seven-output validation, indexed DataHub read-back, screenshot QA, and the strict finalizer. |
