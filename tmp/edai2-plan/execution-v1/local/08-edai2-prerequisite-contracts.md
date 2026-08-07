# EDAI2 Prerequisite and Repository Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement EDAI2 Tasks 0–1: consume the strict Section 03 contract read-only, lock exact Python dependencies, and create Pydantic v2/API/MCP/ports-adapters/repository/security foundations.

**Architecture:** A read-only prerequisite test verifies the sole canonical Section 03 consumer contract. Pydantic v2 schemas and Protocol ports define stable boundaries; concrete adapters point inward to ports; three FastAPI and two streamable-HTTP MCP contracts share exact typed models without runtime/network dependencies.

**Tech Stack:** Python 3.12, `uv`, Pydantic v2, FastAPI, MCP, Feast, psycopg, pgvector, sentence-transformers, HTTPX, OpenTelemetry, Langfuse, pytest, `rtk`.

## Locked sources and execution policy

- Read `C:\Users\oou1hc\.codex\RTK.md`; every shell command begins with `rtk`.
- Section 03 source is `tmp/edai2-plan/03_data_generator_improvement.md`, SHA-256 `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`.
- EDAI2 source is `tmp/edai2-plan/04.2_llm_design.md`, SHA-256 `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`.
- Rubric source is `tmp/rubic-check/Coursework Tracking (Public).xlsx`, SHA-256 `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- Work on the current branch in one serial session. Do not create a worktree or branch and do not stage, commit, push, or open a PR.
- Do not mutate Section 03 evidence, GCP, Kubernetes, containers, or external services.

## Metadata

| Field | Decision |
|---|---|
| Phase | 8 — EDAI2 prerequisite and foundation |
| Source tasks | EDAI2 Tasks 0–1 |
| Rubric contribution | Supporting only for `Sheet3!E32:E34` and `Sheet3!E59:E60` |
| Prerequisites | Topic 07 Completion Record and strict Section 03 manifest |
| Blocked successors | Topics 09 and 12 |
| Runtime ownership | Repository-contract operator; one serial session |
| Local/GCP class | Local-only; no GCP mutation |

## Global constraints

- Section 03 remains sole owner of `Sheet3!E32:E34`; EDAI2 reads exact `id,label`, training join, health, hashes, and verified runtime status without coercion or rewrite.
- All Pydantic models use v2 behavior and `extra="forbid"`; UTC timestamps reject non-UTC aware values.
- Stable APIs are `POST /v1/retrieval/search`, `POST /v1/drift/detect`, `POST /v1/chat`, and `GET /healthz`, `GET /readyz`, `GET /metrics` on every FastAPI service.
- The only MCP tools are `search_ecommerce_knowledge(query, top_k=4, category=None, effective_at=None) -> SearchResponse` and `detect_customer_order_drift(id=None, baseline_window, candidate_window, feature_name="f_customer_order_frequency_7d") -> DriftDetectResponse`; MCP schemas byte-match OpenAPI components.
- Exact focus classes are `RagIndexPipeline`, `FeastRetrievalService`, `DriftDetectionService`, `ObservedInferenceClient`, and `CommerceAgentCoordinator`; routing uses `RouteStrategy`.
- Exact six image/release identities are `edai2-rag-index`, `edai2-retrieval-agent`, `edai2-drift-agent`, `edai2-coordinator`, `edai2-feast-offline-writer`, and `edai2-feast-online-writer`; mutable `latest` is forbidden.
- Unit/contract tests have no runtime/network dependency.

## Current-state refresh — read-only planning phase

```text
rtk git status --short --branch
rtk git branch --show-current
rtk uv run python scripts/generate/verify_section03_manifest.py --manifest evidence/03_data_generator_improvement/section03_manifest.json --strict
rtk rg -n "pydantic|fastapi|mcp|feast|sentence-transformers" pyproject.toml uv.lock
rtk uv run pytest tests/contract/llm/test_section03_contract.py tests/unit/llm/test_contracts.py tests/contract/llm/test_api_contracts.py tests/contract/llm/test_mcp_contracts.py tests/unit/test_edai2_repository_contract.py tests/unit/test_edai2_security_static.py -q
```

Expected: strict Section 03 verification passes before EDAI2 work; the same branch and current dependency/contract baseline are recorded without network/runtime mutation.

## Scope and non-goals

In scope: strict prerequisite test, dependency locks, typed domain/contracts/ports/package exports/config loaders, API/MCP schemas, exact class/image/repository/security tests. Non-goals: RAG implementation, retrieval/drift/chat behavior, streaming writers, Docker implementation, CI, agents, Terraform/GKE, or evidence scoring.

## Exact file map

| Action | Exact paths | Responsibility |
|---|---|---|
| Modify | `pyproject.toml`, `uv.lock` | Lock exact runtime/dev dependencies under Python 3.12. |
| Create | `src/vina_bim_shop/llm/__init__.py`, `src/vina_bim_shop/llm/contracts.py`, `src/vina_bim_shop/llm/ports.py`, `src/vina_bim_shop/llm/indexing.py`, `src/vina_bim_shop/llm/retrieval.py`, `src/vina_bim_shop/llm/drift.py`, `src/vina_bim_shop/llm/section03_ingestion.py`, `src/vina_bim_shop/llm/inference.py`, `src/vina_bim_shop/llm/routing.py`, `src/vina_bim_shop/llm/coordinator.py`, `src/vina_bim_shop/llm/safety.py`, `src/vina_bim_shop/llm/evaluation.py`, `src/vina_bim_shop/llm/telemetry.py` | Domain/application types, Protocol consumers, five focus-class signatures, and docstrings. |
| Create | `src/vina_bim_shop/llm/adapters/__init__.py`, `src/vina_bim_shop/llm/adapters/feast_postgres.py`, `src/vina_bim_shop/llm/adapters/llmd.py`, `src/vina_bim_shop/llm/adapters/kagent.py`, `src/vina_bim_shop/llm/adapters/datahub.py` | Concrete adapter boundaries without live calls. |
| Create | `src/vina_bim_shop/llm/api/__init__.py`, `src/vina_bim_shop/llm/api/common.py`, `src/vina_bim_shop/llm/api/retrieval.py`, `src/vina_bim_shop/llm/api/drift.py`, `src/vina_bim_shop/llm/api/chat.py` | Three exact FastAPI schemas/probes/metrics surfaces. |
| Create | `src/vina_bim_shop/llm/mcp/__init__.py`, `src/vina_bim_shop/llm/mcp/retrieval.py`, `src/vina_bim_shop/llm/mcp/drift.py` | Two exact streamable-HTTP MCP schemas. |
| Create | `src/vina_bim_shop/llm/streaming/__init__.py`, `src/vina_bim_shop/llm/streaming/offline_writer.py`, `src/vina_bim_shop/llm/streaming/online_writer.py` | Typed writer contracts only; behavior belongs to later tasks. |
| Create | `configs/llm/models.yaml`, `configs/llm/routing.yaml`, `configs/llm/evaluation.yaml`, `configs/llm/warmup_prompts.json`, `configs/llm/benchmark_requests.json`, `configs/llm/test_scope.yaml`, `configs/llm/coverage.ini`, `configs/gke/profiles.yaml`, `configs/gke/cost_envelope.yaml` | Exact model/routing/evaluation/test/profile schema contracts without deployment. |
| Create | `tests/contract/llm/test_section03_contract.py` | Read-only strict prerequisite verification. |
| Create | `tests/unit/llm/test_contracts.py` | Pydantic v2 models, Protocols, focus classes, UTC and forbidden-extra tests. |
| Create | `tests/contract/llm/test_api_contracts.py` | Exact OpenAPI requests/responses/errors/probes. |
| Create | `tests/contract/llm/test_mcp_contracts.py` | Exact MCP tools and OpenAPI byte-equivalence. |
| Create | `tests/unit/test_edai2_repository_contract.py` | Package direction, five classes, six image names, and file boundary checks. |
| Create | `tests/unit/test_edai2_security_static.py` | Reject mutable tags, VM/Ansible/Cloud Build/hosted endpoints/plaintext secrets. |

## Interfaces and data flow

`tests/contract/llm/test_section03_contract.py` consumes only `evidence/03_data_generator_improvement/section03_manifest.json` and bound artifacts. Core contracts include `ApiError`, `SearchRequest/Response`, `DriftDetectRequest/Response`, `ChatRequest/Response`, citations, index reports, `EmbeddingPort`, `FeastPort`, `InferencePort`, `McpClientPort`, and `CoordinatorAgentPort`. Adapters depend on ports; core never imports adapters or infrastructure.

## Failure modes

Stop on pending/missing/tampered Section 03 evidence, schema coercion, unverified runtime, dependency resolution failure, hosted-LLM SDK, Pydantic v1 API, unbounded/extra fields, non-UTC timestamp, OpenAPI/MCP mismatch, forbidden import direction, wrong focus-class signature, wrong/mutable image identity, secret literal, VM/Ansible/Cloud Build/hosted endpoint, or unit-test network access.

## Ordered test-first execution tasks

- [ ] Run `rtk uv run pytest tests/contract/llm/test_section03_contract.py -q`; expected PASS only for a strict verified Section 03 root with exact `Sheet3!E32:E34`, `id,label`, join/health metadata, source/artifact hashes, and drift proof; otherwise stop before dependency changes.
- [ ] Run `rtk uv add fastapi pydantic mcp feast psycopg pgvector sentence-transformers httpx prometheus-client opentelemetry-sdk opentelemetry-instrumentation-fastapi langfuse`; expected exit 0 with Python 3.12-compatible runtime constraints written to `pyproject.toml` and `uv.lock` and no hosted-LLM SDK.
- [ ] Run `rtk uv add --dev pytest-asyncio pytest-cov hypothesis crosshair-tool mutmut locust playwright nbconvert`; expected exit 0 with exact dev constraints in `pyproject.toml` and `uv.lock`.
- [ ] Run `rtk git diff -- pyproject.toml uv.lock` and `rtk uv lock --check`; expected diff contains only the requested dependencies/transitive lock changes and the lock check exits 0.
- [ ] Add failing Pydantic v2/OpenAPI/MCP/focus-class/ports-adapters/image/security tests, then run `rtk uv run pytest tests/unit/llm/test_contracts.py tests/contract/llm/test_api_contracts.py tests/contract/llm/test_mcp_contracts.py tests/unit/test_edai2_repository_contract.py tests/unit/test_edai2_security_static.py -q`; expected FAIL because package/config contracts do not yet exist.
- [ ] Implement only the exact typed contracts, Protocols, focus-class signatures, API/MCP schema surfaces, config loaders, package exports, and public docstrings, then run `rtk uv run pytest tests/unit/llm/test_contracts.py tests/contract/llm/test_api_contracts.py tests/contract/llm/test_mcp_contracts.py tests/unit/test_edai2_repository_contract.py tests/unit/test_edai2_security_static.py -q`; expected PASS with no network/runtime dependency.
- [ ] Run `rtk uv run pytest tests/contract/llm/test_section03_contract.py tests/unit/llm/test_contracts.py tests/contract/llm/test_api_contracts.py tests/contract/llm/test_mcp_contracts.py tests/unit/test_edai2_repository_contract.py tests/unit/test_edai2_security_static.py -q`; expected PASS with exact Section 03 ownership, Pydantic v2, five focus classes, six image names, and API/MCP equality.
- [ ] Run `rtk git diff --check`, `rtk git status --short --branch`, and `rtk git ls-files --stage`; expected no whitespace errors, the original branch unchanged, only exact file-map paths changed, and the final index listing is byte-for-byte identical to the pre-topic listing. Pre-existing staged entries are user-owned; do not stage or unstage them.

## Evidence and screenshot ownership

Topic 08 owns dependency diffs and focused test logs. It references Topic 07 hashes for `Sheet3!E32:E34` without copying ownership. No screenshot or runtime evidence is created.

## Cleanup

Retain `pyproject.toml`/`uv.lock` changes and source/tests. Remove only test-managed temporary files. Do not modify Section 03 evidence or acquire a runtime.

## Rubric table

| Workbook cell | Supporting proof | Ownership rule |
|---|---|---|
| `Sheet3!E32:E34` | Read-only strict prerequisite contract | Section 03/Topic 07 remains owner |
| `Sheet3!E59:E60` | Ports/adapters, Strategy boundary, five exact typed focus classes | Supporting foundation; later documentation/evidence owns satisfaction |

## Definition of Done

Strict prerequisite passes; exact dependency commands and lock check pass; Pydantic v2/API/MCP/repository/security tests pass; five focus classes and six image identities are locked; no runtime/network/GCP mutation occurs.

## Completion Record

| Field | Record |
|---|---|
| Status | Complete - the stale Section 03 lock was corrected to the verified `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6` authorized by the plan owner. The strict prerequisite, contract/config acceptance set, and clean full repository regression pass. |
| Affected files | Modified: `pyproject.toml`, `uv.lock`, and this topic file (locked Section 03 hash plus this record). Created: `src/vina_bim_shop/llm/__init__.py`, `contracts.py`, `ports.py`, `indexing.py`, `retrieval.py`, `drift.py`, `section03_ingestion.py`, `inference.py`, `routing.py`, `coordinator.py`, `safety.py`, `evaluation.py`, `telemetry.py`; `src/vina_bim_shop/llm/adapters/__init__.py`, `feast_postgres.py`, `llmd.py`, `kagent.py`, `datahub.py`; `src/vina_bim_shop/llm/api/__init__.py`, `common.py`, `retrieval.py`, `drift.py`, `chat.py`; `src/vina_bim_shop/llm/mcp/__init__.py`, `retrieval.py`, `drift.py`; `src/vina_bim_shop/llm/streaming/__init__.py`, `offline_writer.py`, `online_writer.py`; `configs/llm/models.yaml`, `routing.yaml`, `evaluation.yaml`, `warmup_prompts.json`, `benchmark_requests.json`, `test_scope.yaml`, `coverage.ini`, `configs/gke/profiles.yaml`, `cost_envelope.yaml`; `tests/contract/llm/test_section03_contract.py`, `test_api_contracts.py`, `test_mcp_contracts.py`, `tests/unit/llm/test_contracts.py`, `tests/unit/test_edai2_repository_contract.py`, `tests/unit/test_edai2_security_static.py`. No Section 03 evidence or unrelated tracked file was edited. |
| Commands / exit codes | Before edits: `rtk git status --short --branch` 0 on the existing `feature/implement-edai2...origin/feature/implement-edai2` branch; `rtk git ls-files --stage` 0; locked-source SHA recomputation 0; strict Section 03 verifier 0 (`section03 manifest: PASS`). Test-first prerequisite probe before its creation: 1 (`file or directory not found`). After creation: `rtk uv run pytest tests/contract/llm/test_section03_contract.py -q` 0, 1 passed. Exact runtime `rtk uv add fastapi pydantic mcp feast psycopg pgvector sentence-transformers httpx prometheus-client opentelemetry-sdk opentelemetry-instrumentation-fastapi langfuse` 0; exact dev `rtk uv add --dev pytest-asyncio pytest-cov hypothesis crosshair-tool mutmut locust playwright nbconvert` 0; dependency diff inspection and `rtk uv lock --check` 0. Contract implementation red collection: 1 (`No module named vina_bim_shop.llm`); implementation focused tests: 17 passed; MCP schema equality check: 2 passed; config-contract red check: 1 (`KeyError: hub_revision`); corrected config-contract check: 1 passed; config parse/module import check: 0 (8 configs parsed, 24 modules imported); final post-record Topic 08 acceptance: 19 passed, 2 warnings. The first full regression run reported 572 passed and one transient Windows `WinError 5` temp-directory rename failure; the isolated failing test passed 2/2 and its full file passed 10/10. Clean rerun: `rtk uv run pytest -q` 0, 573 passed, 6 warnings in 320.91s. Final `rtk git diff --check` 0; final `rtk uv lock --check` 0; final `rtk git status --short --branch` 0; final `rtk git ls-files --stage` 0 with 857 entries and no index-writing command used, byte-for-byte identical to the pre-edit listing. |
| Evidence + SHA-256 | `evidence/03_data_generator_improvement/section03_manifest.json`: `af7189d00a187e539bb777d89111d2860a97822f34c2c911adc3eadf6166f8ad`; verified Section 03 bundle ID: `f6d07b09a12107b19a4bfe45a7bda6f87ab9356021a90e2ec6f02f63b5602640`. Locked sources: `tmp/edai2-plan/03_data_generator_improvement.md` `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`; `tmp/edai2-plan/04.2_llm_design.md` `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`; `tmp/rubic-check/Coursework Tracking (Public).xlsx` `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`. Dependency evidence: `pyproject.toml` `09a9bac54bb57e7646b44eca849368957935cabc9c24503a9c21bd86f4b46547`; `uv.lock` `641a9e0766e8830462949fb803a6f6f918b0ee249bee1871b10fe21409a963db`. Contract/config evidence: `tests/contract/llm/test_section03_contract.py` `18f2dc8398db0eca5da7197c340a17cef1e646bb1da8a2e97ccf6e09907c1910`; `tests/unit/llm/test_contracts.py` `d5d2d6a7d9e57afd47ef9d481de969b9e5f964fdeb8290090ee21ec7c9180382`; `tests/contract/llm/test_api_contracts.py` `2986809e4d527999b4ae40f6aa1a3539e218a024c53d861e86c6be8edde38fa6`; `tests/contract/llm/test_mcp_contracts.py` `5c5b3f6f8a5409ea4841818357cd7b5f3859cabe01a4de6d5deff777694abdc5`; `configs/llm/models.yaml` `f32537e4978eb6759835dc2549fdbda1ef70e6f6dee718ed09c4f69e4ff5c1d2`; `configs/llm/evaluation.yaml` `c7bc00b4c3e7af1ccf12f1d28cbd85bece393fc03a6ba5ea56ad613a679496de`; `configs/llm/benchmark_requests.json` `fb1f42e71fbf5d271bda60e158a14578e32faba55d0ac738e90e62ce0ce01af6`; `configs/gke/cost_envelope.yaml` `0ed8c89a65f3e42f092e7e3d03148f2e87cd943e04c14ff7d2feab2ac8b09fb1`. Machine evidence is command stdout; no separate Topic 08 log artifact was generated. |
| Screenshot QA | No screenshot was required, manufactured, or created. Topic 07 remains owner of its existing Section 03 image/runtime captures; Topic 08 records no UI, GKE, or Kind evidence. |
| Cleanup / runtime release | Tests cleaned their own temporary directories. No GCP mutation, Kubernetes or Kind command, Docker data prune, unrelated-container stop, deployment, or external-service call occurred. The only local environment change was the authorized `uv add` dependency resolution into the existing `.venv`; no cloud/runtime slice was acquired. |
| Rubric disposition | Supports `Sheet3!E32:E34` through a read-only strict prerequisite contract; Section 03/Topic 07 remains the sole owner and no points are double-counted. Supports `Sheet3!E59:E60` with the typed ports/adapters, `RouteStrategy`, five focus-class, API/MCP, repository, and security foundations; no direct empirical satisfaction or score is claimed here. |
| Limitations | This is a local contract foundation only. It does not claim RAG indexing, Feast/pgvector data, streaming behavior, live MCP traffic, model serving, GKE/Kubernetes readiness, GCP cost evidence, benchmark/evaluation measurements, UI captures, or deployment/rollback proof. The final regression retained six pre-existing/third-party warnings: FastAPI/httpx deprecation, Pydantic settings forward-reference warning, and four Section 03 pandas FutureWarnings. |
| Successor handoff | Topics 09 and 12 must consume the verified Section 03 manifest SHA/bundle above and the exact Pydantic/OpenAPI/MCP/config interfaces without renaming or reimplementing Section 03 ownership. Any future Kubernetes command must specify its intended kubeconfig and context; any Kind result is local preflight only, never GKE evidence. |
