# EDAI2 Prerequisite and Repository Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement EDAI2 Tasks 0–1: consume the strict Section 03 contract read-only, lock exact Python dependencies, and create Pydantic v2/API/MCP/ports-adapters/repository/security foundations.

**Architecture:** A read-only prerequisite test verifies the sole canonical Section 03 consumer contract. Pydantic v2 schemas and Protocol ports define stable boundaries; concrete adapters point inward to ports; three FastAPI and two streamable-HTTP MCP contracts share exact typed models without runtime/network dependencies.

**Tech Stack:** Python 3.12, `uv`, Pydantic v2, FastAPI, MCP, Feast, psycopg, pgvector, sentence-transformers, HTTPX, OpenTelemetry, Langfuse, pytest, `rtk`.

## Locked sources and execution policy

- Read `C:\Users\oou1hc\.codex\RTK.md`; every shell command begins with `rtk`.
- Section 03 source is `tmp/edai2-plan/03_data_generator_improvement.md`, SHA-256 `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`.
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
- The only MCP tools are `search_ecommerce_knowledge(query, top_k=4, category=None, effective_at=None) -> SearchResponse` and `detect_customer_order_drift(id, baseline_window, candidate_window, feature_name) -> DriftDetectResponse`; MCP schemas byte-match OpenAPI components.
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
- [ ] Run `rtk git diff --check` and `rtk git status --short --branch`; expected no whitespace errors, the original branch unchanged, only exact file-map paths changed, and nothing staged.

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
| Status | Not started |
| Affected files | Record only exact file-map paths actually changed |
| Commands / exit codes | Record every checkbox command and numeric exit code, ending with `rtk git status --short --branch` |
| Evidence + SHA-256 | Record Section 03 manifest hash, dependency diff/log hashes, and test-log hashes |
| Screenshot QA | No screenshot required for Topic 08 |
| Cleanup / runtime release | Record temporary-test cleanup and `no runtime acquired` |
| Limitations | No RAG behavior, service runtime, image build, or deployment proof is created |
| Successor handoff | Provide locked dependency versions, contract symbols, config schemas, and focused test result to Topics 09 and 12 |
