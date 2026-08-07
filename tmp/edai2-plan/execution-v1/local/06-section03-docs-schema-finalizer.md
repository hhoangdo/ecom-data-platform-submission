# Section 03 Documentation, Schema, and Finalizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Section 03 Task 9 and the testable finalizer portion of Task 10: exact public documentation/schema/Make contracts plus fail-closed immutable-bundle finalization mechanics.

**Architecture:** Tests lock the public generator→dbt/Spark→Airflow/DataHub→finalizer path and the four new Gold relationships. The finalizer validates candidate/runtime trees recursively under a lock, writes a new immutable bundle, and atomically replaces only the canonical manifest; Topic 07 owns real execution.

**Tech Stack:** Markdown, Make, PlantUML, DBML, Python 3.12, pytest, SHA-256, `uv`, `rtk`.

## Locked sources and execution policy

- Read `C:\Users\oou1hc\.codex\RTK.md`; every shell command begins with `rtk`.
- Section 03 source is `tmp/edai2-plan/03_data_generator_improvement.md`, SHA-256 `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`.
- EDAI2 source is `tmp/edai2-plan/04.2_llm_design.md`, SHA-256 `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`.
- Rubric source is `tmp/rubic-check/Coursework Tracking (Public).xlsx`, SHA-256 `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- Work on the current branch in one serial session. Do not create a worktree or branch and do not stage, commit, push, or open a PR.
- Do not regenerate/promote canonical evidence, start services, mutate GCP/Kubernetes, prune Docker, or stop containers in this topic.

## Metadata

| Field | Decision |
|---|---|
| Phase | 6 — documentation/schema and finalizer mechanics |
| Source tasks | Section 03 Task 9 and Task 10 Steps 1–2 |
| Rubric contribution | Supporting evidence for `Sheet3!E32:E34`; Topic 07 is sole primary owner |
| Prerequisites | Topic 05 Completion Record |
| Blocked successors | Topic 07 |
| Runtime ownership | Documentation/finalizer test operator; one serial session |
| Local/GCP class | Local-only; no runtime/GCP mutation |

## Global constraints

- Public docs state configured targets separately from measured values and never claim strict success before Topic 07.
- Section 03 is Feast-ready offline export only; Feast installation/materialization/serving remains EDAI2.
- Make recipes use `uv run`; documented operator calls use `rtk make`.
- The four new Gold entities and three relationships are consistent across PlantUML and DBML.
- Finalizer verification is recursive, path-contained, symlink rejecting, identity bound, active-plus-previous retaining, and fail closed before atomic replace.
- Post-promotion housekeeping failure warns and preserves uncertain pointers/bundles; it never rolls back a verified promoted root.

## Current-state refresh — read-only planning phase

```text
rtk git status --short --branch
rtk git branch --show-current
rtk rg -n "Section 03|Feast|generate-section03|ml_customer_label|agg_feature_health_daily|feature_drift_alerts|ml_customer_purchase_training" Makefile scripts/README.md README.md configs/scenarios/README.md deliverables/03_data_generator_improvement.md architecture tests/unit
rtk uv run pytest tests/unit/test_section03_documentation.py tests/unit/test_section02_schema_design.py tests/unit/test_script_surface_documentation.py tests/integration/test_section03_finalizer.py -q
```

Expected: the same branch is recorded; current documentation/schema/finalizer gaps are identified without generated evidence mutation.

## Scope and non-goals

In scope: exact docs, Make targets, schema diagrams, documentation/schema tests, finalizer implementation, and synthetic finalizer tests. Non-goals: real generator/dbt/Spark/Airflow/DataHub execution, canonical promotion, Feast runtime, GCP, or unrelated prose/diagram restyling.

## Exact file map

| Action | Exact path | Responsibility |
|---|---|---|
| Modify | `Makefile` | Add `generate-section03`, `build-section03-dbt`, and `test-section03` recipes/help. |
| Modify | `scripts/README.md` | Document generator/dbt/verifier/finalizer command surfaces. |
| Modify | `README.md` | Add reproducible Section 03 path and remove obsolete exclusion. |
| Modify | `configs/scenarios/README.md` | Document scenario and canonical YAML ownership. |
| Modify | `deliverables/03_data_generator_improvement.md` | Replace placeholder with exact contracts, evidence, limits, and rubric traceability. |
| Modify | `architecture/masterplan.md` | Mark drift/labels implemented without claiming ML/Feast runtime. |
| Modify | `architecture/domain/business-context.md` | Describe campaign scenario and AI impact without unrelated domain changes. |
| Modify | `architecture/diagrams/schema_design.puml` | Add Section 03 Gold feature/label/health/alert/training relationships. |
| Modify | `architecture/diagrams/erd/physical_gold_model.puml` | Add four Gold entities and relationships. |
| Modify | `architecture/diagrams/erd/gold_layer_ERD.dbml` | Mirror exact tables, keys, fields, and relationships. |
| Create | `tests/unit/test_section03_documentation.py` | Lock values, commands, evidence paths, scope, and rubric mapping. |
| Modify | `tests/unit/test_section02_schema_design.py` | Extend physical-schema assertions without weakening Section 02. |
| Modify | `tests/unit/test_script_surface_documentation.py` | Verify new public command surfaces. |
| Create | `scripts/generate/finalize_section03_evidence.py` | Verify/import/rebind/promote immutable strict evidence safely. |
| Create | `tests/integration/test_section03_finalizer.py` | Exercise success, failure, identity, retention, and housekeeping paths. |

## Interfaces and data flow

Documented operator targets are `rtk make generate-section03 SCALE=medium SEED=42`, `rtk make build-section03-dbt SCALE=medium`, and `rtk make test-section03`; recipes themselves invoke `uv run`. The finalizer consumes the candidate manifest plus exact Spark/Airflow/DataHub capture roots and produces an immutable final bundle and canonical manifest only after strict verification.

## Failure modes

Fail on placeholder/out-of-scope wording, missing fixed values/cells/paths, wrong label schema/name, Feast boundary drift, missing diagram entity/relation, wrong Make recipe prefix, unresolved docs command, traversal/symlink, stale/missing recursive capture, config/run/scale/cutoff mismatch, same-ID content mismatch, pointer identity race, pre-replace failure, unsafe cleanup, or modified unrelated documentation.

## Ordered test-first execution tasks

- [ ] Add exact documentation/schema/command assertions, then run `rtk uv run pytest tests/unit/test_section03_documentation.py tests/unit/test_section02_schema_design.py tests/unit/test_script_surface_documentation.py -q`; expected FAIL because public docs, schema sources, and Make targets are incomplete.
- [ ] Implement the three Make recipes with `uv run` and update the seven exact Markdown files, then run `rtk uv run pytest tests/unit/test_section03_documentation.py tests/unit/test_script_surface_documentation.py -q`; expected PASS for fixed values, `Sheet3!E32:E34`, commands, evidence paths, and Feast-ready-only wording.
- [ ] Update `architecture/diagrams/schema_design.puml`, `architecture/diagrams/erd/physical_gold_model.puml`, and `architecture/diagrams/erd/gold_layer_ERD.dbml`, then run `rtk uv run pytest tests/unit/test_section02_schema_design.py -q`; expected PASS with four entities and label→training, unified-feature→training, and health→alert relationships.
- [ ] Add synthetic hash-valid candidate/Spark/Airflow/DataHub trees plus all corrupt/stale/identity/retention/housekeeping cases, then run `rtk uv run pytest tests/integration/test_section03_finalizer.py -q`; expected FAIL because the finalizer is absent.
- [ ] Implement `scripts/generate/finalize_section03_evidence.py`, then run `rtk uv run pytest tests/integration/test_section03_finalizer.py -q`; expected PASS for fourteen-key recursive inventory, strict rebinding, identical same-ID reuse, mismatched same-ID rejection, atomic replace, active-plus-previous retention, candidate identity race, and nonfatal post-promotion cleanup warnings.
- [ ] Run `rtk uv run pytest tests/unit/test_section03_documentation.py tests/unit/test_section02_schema_design.py tests/unit/test_script_surface_documentation.py tests/integration/test_section03_finalizer.py -q`; expected PASS with zero failures, skips, or xfails in the listed files.
- [ ] Run `rtk git diff --check`, `rtk git status --short --branch`, and `rtk git ls-files --stage`; expected no whitespace errors, the original branch unchanged, only exact file-map paths changed, no generated canonical evidence change, and the final index listing is byte-for-byte identical to the pre-topic listing. Pre-existing staged entries are user-owned; do not stage or unstage them.

## Evidence and screenshot ownership

Topic 06 owns documentation/schema/finalizer test logs only. It creates no canonical screenshot or runtime proof. Topic 07 owns the generated 1600×900 image, original-resolution QA, runtime captures, strict hashes, and score.

## Cleanup

Synthetic finalizer fixtures clean their own temporary directories. Do not remove a real candidate, strict root, active/previous bundle, service volume, or user file. No runtime is acquired.

## Rubric table

| Workbook cell | Supporting proof | Ownership rule |
|---|---|---|
| `Sheet3!E32:E34` | Public contracts, schema traceability, and tested strict promotion mechanics | Supporting only; Topic 07 executes/promotes |

## Definition of Done

Exact docs/Make/schema tests pass; finalizer synthetic tests pass every failure/retention invariant; no generated evidence or runtime is touched; scoped diff checks pass.

## Completion Record

| Field | Record |
|---|---|
| Status | Complete — local-only documentation/schema/finalizer mechanics implemented and synthetically verified; no canonical/runtime promotion performed. |
| Assumptions verified | Topic 05 Completion Record was read and records the reconciled Section 03 source SHA-256 `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`; the Topic 06 table entry remains stale at `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`. EDAI2 and workbook locks match. Branch stayed `feature/implement-edai2`; the current checkout and default Kubernetes context were not changed or used; no GCP/GKE/Kind/Kubernetes, Docker, Airflow, DataHub, Spark, or Trino runtime was contacted. |
| Current-state delta | Added the three Section 03 Make targets and operator documentation; replaced the Section 03 placeholder deliverable; documented canonical YAML ownership, campaign drift, exact `id,label`, seven-day cutoff/label policy, PSI thresholds, evidence boundaries, and Feast-ready offline scope; added the four Gold entities and explicit label→training, unified-feature→training, and health→alert relationships to PlantUML/DBML; added documentation/schema/script-surface tests; and added a strict finalizer that recursively verifies captures, rejects unsafe paths/symlinks/stale identities/mismatches, rewrites the fourteen-artifact inventory, promotes only after staged verification and candidate-pointer recheck, retains active plus previous bundles, and treats post-promotion cleanup warnings as nonfatal. The finalizer suite now explicitly covers missing artifacts for every runtime root, symlink rejection, and post-promotion pointer-identity preservation. No generated evidence, runtime root, Docker container, or staged index entry was changed. |
| Affected files | `Makefile`; `scripts/README.md`; `README.md`; `configs/scenarios/README.md`; `deliverables/03_data_generator_improvement.md`; `architecture/masterplan.md`; `architecture/domain/business-context.md`; `architecture/diagrams/schema_design.puml`; `architecture/diagrams/erd/physical_gold_model.puml`; `architecture/diagrams/erd/gold_layer_ERD.dbml`; `tests/unit/test_section03_documentation.py`; `tests/unit/test_section02_schema_design.py`; `tests/unit/test_script_surface_documentation.py`; `scripts/generate/finalize_section03_evidence.py`; `tests/integration/test_section03_finalizer.py`; and this Topic 06 Completion Record only. No other plan or Completion Record was changed. |
| Commands / exit codes | Source locks: `rtk proxy certutil.exe -hashfile tmp/edai2-plan/03_data_generator_improvement.md SHA256` `0`; `rtk proxy certutil.exe -hashfile tmp/edai2-plan/04.2_llm_design.md SHA256` `0`; `rtk proxy certutil.exe -hashfile tmp/rubic-check/Coursework Tracking (Public).xlsx SHA256` `0`. RED documentation/schema/script gate: `rtk uv run pytest tests/unit/test_section03_documentation.py tests/unit/test_section02_schema_design.py tests/unit/test_script_surface_documentation.py -q` `1` (`6 failed, 15 passed`); final documentation/script gate `0` (`9 passed`); schema gate `rtk uv run pytest tests/unit/test_section02_schema_design.py -q` `0` (`12 passed`); finalizer RED collection `rtk uv run pytest tests/integration/test_section03_finalizer.py -q` `1` (implementation absent); finalizer GREEN `0` (`21 passed`); scoped acceptance `rtk uv run pytest tests/unit/test_section03_documentation.py tests/unit/test_section02_schema_design.py tests/unit/test_script_surface_documentation.py tests/integration/test_section03_finalizer.py -q` `0` (`42 passed`, zero skips/xfails); Make dry-runs for `generate-section03`, `build-section03-dbt`, and `test-section03` `0`; `rtk git diff --check` `0`; pre/post index comparison `rtk proxy fc.exe /b ...` `0` (`FC: no differences encountered`); final `rtk git status --short --branch --untracked-files=all` is the required final command and returned `0`. |
| Evidence + SHA-256 | No repository test-log artifact was produced; pytest output was terminal-only. Recomputed locks: Section 03 actual `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6` (does not match Topic 06’s stale recorded value); EDAI2 `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`; workbook `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`. Synthetic fixtures were temporary and no canonical evidence artifact was produced. |
| Screenshot QA | No runtime screenshot is owned by Topic 06; no screenshot was generated or claimed. |
| Cleanup / runtime release | Pytest temporary fixture trees and the two exact external pre/post index snapshots were removed after comparison. No runtime was acquired; no service was started, stopped, pruned, deployed, or mutated. |
| Rubric disposition | Supports `Sheet3!E32:E34` only through public contracts, schema traceability, and tested strict promotion mechanics. Topic 07 remains the sole owner of live execution, canonical promotion, screenshot evidence, and any earned rubric score. |
| Limitations | The Section 03 source lock recorded in this topic is stale and must be reconciled by the plan owner before any strict rubric manifest claims. The current `scripts/generate/verify_section03_manifest.py` still has the generator-only eleven-artifact contract and no `--strict` CLI; Topic 07 must close that successor contract gap before invoking the documented strict verification command. The finalizer’s synthetic tests do not prove real Airflow, DataHub indexed search, Spark/Trino parity, GKE state, or screenshot evidence. |
| Successor handoff | Topic 07 must run `rtk uv run python scripts/generate/finalize_section03_evidence.py --candidate-manifest evidence/03_data_generator_improvement/section03_candidate_manifest.json --active-manifest evidence/03_data_generator_improvement/section03_manifest.json --spark-root tmp/section03-runtime/spark --airflow-root tmp/section03-runtime/airflow --datahub-root tmp/section03-runtime/datahub --clean`, then resolve and run the verifier’s strict command. It must use an explicitly named kubeconfig and context for every Kubernetes command, never treat local Kind output as GKE evidence, capture real Airflow/DataHub/Spark proof, perform 1600x900 original-resolution screenshot QA, and stop if source locks, recursive hashes, runtime identity, indexed search, or active/previous retention fail. |
