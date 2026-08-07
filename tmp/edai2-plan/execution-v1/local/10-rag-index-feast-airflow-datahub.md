# RAG Index, Feast, Airflow, and DataHub Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete EDAI2 Task 2 by transactionally storing candidate chunks/vectors, registering Feast, orchestrating a paused/manual RAG DAG, publishing/read-back verifying DataHub lineage, and compare-and-swap promoting with compensation rollback.

**Architecture:** Topic 09 candidate inputs flow through exact `RagIndexPipeline` stages into immutable PostgreSQL candidate rows and `vector(384)`. Feast declares the feature/retrieval boundary; the shared adapter performs exact pgvector cosine search. Airflow orchestrates manual candidate builds; validation gates CAS promotion; post-CAS lineage/read-back failure compensates to the recorded prior alias.

**Tech Stack:** Python 3.12, PostgreSQL/pgvector, Feast, Airflow, DataHub/OpenSearch, Pydantic v2, pytest, `uv`, `rtk`.

## Locked sources and execution policy

- Read `C:\Users\oou1hc\.codex\RTK.md`; every shell command begins with `rtk`.
- Section 03 source is `tmp/edai2-plan/03_data_generator_improvement.md`, SHA-256 `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`.
- EDAI2 source is `tmp/edai2-plan/04.2_llm_design.md`, SHA-256 `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`.
- Rubric source is `tmp/rubic-check/Coursework Tracking (Public).xlsx`, SHA-256 `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- Work on the current branch in one serial session. Do not create a worktree or branch and do not stage, commit, push, or open a PR.
- Do not mutate GCP/Kubernetes or run canonical evidence deployment in this topic. Local integration fixtures may use only test-owned services. Do not prune Docker or stop unrelated containers.

## Metadata

| Field | Decision |
|---|---|
| Phase | 10 — candidate index/storage/orchestration/lineage |
| Source tasks | EDAI2 Task 2 index/Feast/Airflow/DataHub portion |
| Rubric contribution | Supporting evidence for `Sheet3!E8:E9` only |
| Prerequisites | Topic 09 Completion Record |
| Blocked successors | Topic 11 |
| Runtime ownership | Local integration-test operator; one serial session |
| Local/GCP class | Local implementation/tests; no GCP mutation |

## Global constraints

- Exact pipeline stages are `parse_sources -> chunk -> embed -> postgres_upsert_candidate_and_pgvector_index -> register_feast_feature_view -> emit_candidate_lineage -> validate -> promote_compare_and_swap -> emit_active_lineage_and_read_back`.
- PostgreSQL owns immutable candidate tables, `embedding vector(384)`, integrity indexes, and BTREE filter indexes.
- Retrieval applies category and effective-time filters before rank, computes exact cosine distance with `<=>`, orders by `(embedding <=> query_vector, chunk_id)`, returns `score=1.0-cosine_distance`, and performs no reranking.
- The nine-version corpus uses exact scan only; HNSW and IVFFlat are prohibited.
- Feast declares document features/retrieval service but does not claim Feast-managed pgvector index construction.
- The DAG is paused/manual. Retrying a failed pre-promotion stage is idempotent and never changes the active alias.
- Promotion records the prior alias and uses compare-and-swap. Failure in active-lineage emission or DataHub read-back compensates by compare-and-swapping back to that exact prior version, emits rollback lineage, and exits nonzero.
- Topic 10 does not run the Task 6/12 60-case harness and cannot claim canonical evidence.

## Current-state refresh — read-only planning phase

```text
rtk git status --short --branch
rtk git branch --show-current
rtk rg -n "RagIndexPipeline|vector\(384\)|rag_index_pipeline|edai2_rag|active" src/vina_bim_shop/llm src/vina_bim_shop/orchestration infra/feast infra/postgres infra/orchestration infra/governance scripts/llm tests/integration/llm
rtk uv run pytest tests/unit/llm/test_indexing.py tests/integration/llm/test_feast_pgvector.py tests/integration/llm/test_airflow_datahub.py -q
```

Expected: the same branch and Topic 09 source/chunk/embed baseline are recorded; no active alias, database, DAG, or DataHub state is mutated during refresh.

## Scope and non-goals

In scope: PostgreSQL candidate schema/transactions, exact pgvector adapter, Feast declarations, pipeline/application, paused DAG/spec, DataHub recipe/adapter/read-back, CLI wiring, and focused tests. Non-goals: retrieval API/MCP, canonical Task 12 evidence run, 60-case evaluation, agents/models, GKE/GCP, ANN, or public screenshots.

## Exact file map

| Action | Exact path | Responsibility |
|---|---|---|
| Modify | `src/vina_bim_shop/llm/indexing.py` | Implement full `RagIndexPipeline`, validation, CAS, compensation, and reports. |
| Modify | `src/vina_bim_shop/llm/adapters/feast_postgres.py` | Transactional candidate writes, exact pgvector query, Feast/direct equivalence, alias operations. |
| Modify | `src/vina_bim_shop/llm/adapters/datahub.py` | Emit candidate/active/rollback lineage and verify indexed read-back. |
| Create | `infra/feast/feature_store.yaml` | PostgreSQL registry/offline and pgvector-backed document retrieval configuration. |
| Create | `infra/feast/features.py` | Document entity/source/384-d feature view/retrieval service definitions. |
| Create | `infra/postgres/edai2/001_extensions.sql` | Enable `vector` extension. |
| Create | `infra/postgres/edai2/002_knowledge_index.sql` | Immutable source/version/chunk/embedding/candidate tables and active alias. |
| Create | `src/vina_bim_shop/orchestration/rag_index_pipeline.py` | Testable stage orchestration over `RagIndexPipeline`. |
| Create | `infra/orchestration/airflow/dags/rag_index_pipeline.py` | Thin paused/manual Airflow DAG wrapper. |
| Modify | `src/vina_bim_shop/orchestration/specs.py` | Register paused/manual candidate-index DAG contract. |
| Create | `infra/governance/recipes/edai2_rag.yml` | Source→version→chunk/embedding→candidate→active→Feast/API lineage metadata. |
| Modify | `scripts/llm/build_index.py` | Wire local candidate dry-run and later Airflow/promotion modes without implicit activation. |
| Modify | `tests/unit/llm/test_indexing.py` | Extend pipeline stage, idempotency, validation, CAS, compensation, and query tests. |
| Create | `tests/integration/llm/test_feast_pgvector.py` | Test storage, exact filtered rank/ties, Feast/direct equivalence, idempotency, rollback. |
| Create | `tests/integration/llm/test_airflow_datahub.py` | Test paused DAG, stages, lineage/read-back, failure isolation, and compensation. |

## Interfaces and data flow

Topic 09 yields versioned chunks and vectors. `RagIndexPipeline.build_candidate`, `validate_candidate`, `promote`, and `rollback` coordinate adapters. Candidate and active DataHub graphs include source file, document version, chunk, embedding, candidate index, single active alias, Feast retrieval service, and later API node. The adapter is the one query implementation used by direct tests and Feast service.

## Failure modes

Fail on candidate/source/hash/version mismatch, partial transaction, duplicate version with different content, missing/incomplete/nonfinite vector, wrong dimension, filter-after-rank, nondeterministic ties, approximate index, Feast/direct result mismatch, active alias mutation before validation, stale CAS expected value, DAG auto-schedule, stage retry changing alias, missing DataHub edge/schema/URN/read-back hash, or failed compensation.

## Local sentinel, CI bootstrap, and canonical evidence identities

This topic's local dry-run sentinel is exactly version `test_idx_001`, mode `candidate`, `dry_run=true`, evidence label `local-bootstrap-sentinel`, and no database write or active alias. Topic 25 separately owns the live CI bootstrap identity `ci-bootstrap-${EDAI2_COMMIT_SHA}` with purpose `ci-bootstrap`. Topic 28 owns the canonical evidence identity `canonical-evidence-${EDAI2_COMMIT_SHA}`, candidate/active/rollback lineage labels, CAS against the then-current active alias, and output `evidence/04_2_llm_design/rag/index_run.json`. None of the three identities may be relabelled, copied, or substituted for another.

## Ordered test-first execution tasks

- [ ] Add full pipeline-stage, transactional candidate, exact query/tie, Feast-equivalence, paused-DAG, lineage, CAS, and compensation tests, then run `rtk uv run pytest tests/unit/llm/test_indexing.py tests/integration/llm/test_feast_pgvector.py tests/integration/llm/test_airflow_datahub.py -q`; expected FAIL because storage, Feast, orchestration, and DataHub implementations are absent.
- [ ] Implement `001_extensions.sql`, `002_knowledge_index.sql`, and `feast_postgres.py`, then run `rtk uv run pytest tests/integration/llm/test_feast_pgvector.py -q`; expected PASS for transactional idempotent candidates, `vector(384)`, filter-before-rank, exact `<=>`, deterministic chunk-ID ties, no ANN, and Feast/direct equality.
- [ ] Implement the exact `RagIndexPipeline` stage sequence and validation/CAS/prior-alias compensation, then run `rtk uv run pytest tests/unit/llm/test_indexing.py tests/integration/llm/test_feast_pgvector.py -q`; expected PASS with failed validation preserving the prior alias and post-CAS failure restoring it.
- [ ] Implement `infra/feast/feature_store.yaml`, `infra/feast/features.py`, the orchestration application/DAG/spec, DataHub adapter/recipe, and CLI wiring, then run `rtk uv run pytest tests/integration/llm/test_airflow_datahub.py -q`; expected PASS with a paused/manual DAG, exact stage order, candidate/active/read-back graph, and rollback lineage.
- [ ] Run `rtk uv run python scripts/llm/build_index.py --mode candidate --index-version test_idx_001 --index-purpose local-bootstrap-sentinel --source-root data/knowledge/ecommerce --dry-run`; expected exit 0 with exactly 8 documents, 9 versions, at-most-400/80-overlap chunks, finite normalized 384-vectors, label `local-bootstrap-sentinel`, no database write, no active alias, and no CI/canonical evidence claim.
- [ ] Run `rtk uv run pytest tests/unit/llm/test_indexing.py tests/integration/llm/test_feast_pgvector.py tests/integration/llm/test_airflow_datahub.py -q`; expected PASS with tampered source/hash, overlapping intervals, incomplete embeddings, failed validation, stale CAS, and read-back failure all preserving or restoring the exact prior alias.
- [ ] Run `rtk git diff --check`, `rtk git status --short --branch`, and `rtk git ls-files --stage`; expected no whitespace errors, the original branch unchanged, only exact file-map paths changed, no canonical evidence output created, and the final index listing is byte-for-byte identical to the pre-topic listing. Pre-existing staged entries are user-owned; do not stage or unstage them.

## Evidence and screenshot ownership

Topic 10 owns local integration logs and the `local-bootstrap-sentinel` dry-run output only. It owns neither Topic 25's live CI bootstrap nor Topic 28's canonical `index_run.json`, Airflow/DataHub screenshots, or rubric satisfaction. Topic 28 must generate fresh candidate/active alias evidence and contextual Airflow/DataHub screenshots.

## Cleanup

Integration fixtures remove only test-owned schemas/records and restore the exact prior alias. Retain source/config/code/tests. Do not delete a real active/prior index, service volume, container, or cloud resource.

## Rubric table

| Workbook cell | Supporting proof | Ownership rule |
|---|---|---|
| `Sheet3!E8` | Exact Airflow text→version→400/80→384-d→Feast/pgvector candidate pipeline contract | Supporting only; bootstrap is not canonical evidence |
| `Sheet3!E9` | Exact source→candidate→active lineage/read-back/rollback contract | Supporting only; later live evidence owns satisfaction |

## Definition of Done

All three exact test files pass; storage/query/stage/DAG/lineage/CAS/compensation contracts match the source; bootstrap dry-run creates no active alias or canonical evidence; scoped diff checks pass.

## Completion Record

| Field | Record |
|---|---|
| Status | Not started |
| Affected files | Record only exact file-map paths actually changed |
| Commands / exit codes | Record every checkbox command and numeric exit code, ending with `rtk git status --short --branch` |
| Evidence + SHA-256 | Record integration/bootstrap log paths and hashes, or `no bootstrap report produced` |
| Screenshot QA | No canonical screenshot is owned by Topic 10 |
| Cleanup / runtime release | Record test-schema cleanup, prior-alias restoration, and `no external runtime acquired` |
| Limitations | Bootstrap `test_idx_001` cannot satisfy canonical `Sheet3!E8:E9` evidence |
| Successor handoff | Provide storage schema, pipeline/alias contracts, bootstrap identity, and passing test results to Topic 11 |
