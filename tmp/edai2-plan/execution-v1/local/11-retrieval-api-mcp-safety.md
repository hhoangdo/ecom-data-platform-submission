# 11 — Retrieval API, MCP, and Deterministic Grounding

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the local Task 3 retrieval domain, FastAPI endpoint, streamable-HTTP MCP tool, deterministic citation validation, probes, metrics, and focused tests.

**Architecture:** `POST /v1/retrieval/search` and MCP `search_ecommerce_knowledge` adapt the same async `FeastRetrievalService`. The request carries `effective_at`; the service enforces a 700 ms dependency timeout, re-reads citation hashes, and never fabricates matches. Chat-level unsupported-claim and prompt-injection handling remains separate from route-level retrieval integrity.

**Tech Stack:** Python 3.12, uv, FastAPI, Pydantic v2, MCP streamable HTTP, Feast/pgvector port from Topic 10, OpenTelemetry, Prometheus, pytest, SHA-256.

## Metadata

| Field | Locked value |
|---|---|
| Phase | Local/static implementation Topic 11 |
| Source task | `tmp/edai2-plan/04.2_llm_design.md` Task 3 |
| Sheet3 support | `Sheet3!E10:E12`, `Sheet3!E62` |
| Predecessor Completion Record | `tmp/edai2-plan/execution-v1/local/10-rag-index-feast-airflow-datahub.md` must be `Complete` |
| Blocked successor | `tmp/edai2-plan/execution-v1/local/13-coordinator-inference-routing-telemetry.md` |
| Runtime ownership | One local uv/uvicorn session owned by the Topic 11 operator |
| Class | Local/static; no GCP mutation and no GKE rubric credit |

## Locked planning basis

- `C:\Users\oou1hc\.codex\RTK.md` must be read first; every shell command is prefixed with `rtk`.
- Section 03 plan SHA-256: `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`.
- EDAI2 master plan SHA-256: `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`.
- Rubric source `tmp/rubic-check/Coursework Tracking (Public).xlsx` SHA-256: `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- A hash mismatch stops execution and yields a truthful `Partial` Completion Record.

## Global constraints

- Stay on the current branch; use one serial implementation session.
- Use `apply_patch` for repository text edits.
- Do not stage, commit, create a branch/worktree, call GCP, or claim live deployment.
- Do not automatically prune or stop Docker resources.
- Developer recipes use `rtk uv run ...`; operator recipes use `rtk make ...`.
- A dependency change must use `rtk uv add ...`, then inspect `rtk git diff -- pyproject.toml uv.lock`; Topic 11 does not own those files, so hand the need to Topic 15 instead of editing them.
- After one bounded retry, preserve the failure as `Partial`; do not broaden scope.

## Read-only current-state refresh

- [ ] Run `rtk git status --short --branch`. Expected: current branch and unrelated user changes are recorded before edits.
- [ ] Run `rtk proxy certutil -hashfile tmp/edai2-plan/03_data_generator_improvement.md SHA256`. Expected: output contains `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`.
- [ ] Run `rtk proxy certutil -hashfile tmp/edai2-plan/04.2_llm_design.md SHA256`. Expected: output contains `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`.
- [ ] Run `rtk proxy certutil -hashfile "tmp/rubic-check/Coursework Tracking (Public).xlsx" SHA256`. Expected: output contains `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- [ ] Run `rtk proxy powershell -NoProfile -Command "Select-String -Path tmp/edai2-plan/execution-v1/local/10-rag-index-feast-airflow-datahub.md -Pattern '^Status: Complete|\| Status \| Complete \|'"`. Expected: one Completion Record match.
- [ ] Run `rtk git diff --check`. Expected: exit 0 before scoped edits; otherwise stop this topic as `Partial` without editing unrelated files.

## Scope and non-goals

In scope: typed retrieval contracts, async service, API/MCP adapters, route-local citation/hash validation, 700 ms timeout, stable errors, health/readiness/metrics, EP/BVA, unit and contract tests.

Non-goals: RAG ingestion/index construction, Section 03 ingestion, chat-level unsupported-claim/injection policy, Helm charts, SandboxAgents, live Feast/PostgreSQL, GKE, UI screenshots, and generic documentation.

## Exact file map

| Action | Exact path | Responsibility |
|---|---|---|
| Create | `src/vina_bim_shop/llm/retrieval.py` | `FeastRetrievalService`, query/filter rules, timeout, citation verification |
| Create | `src/vina_bim_shop/llm/api/retrieval.py` | FastAPI route, probes, metrics, error mapping |
| Create | `src/vina_bim_shop/llm/mcp/retrieval.py` | Exact `search_ecommerce_knowledge` MCP schema and adapter |
| Create | `src/vina_bim_shop/llm/safety.py` | Retrieval-result hash/support validator only; chat policy remains Topic 13 |
| Create | `tests/unit/llm/test_retrieval.py` | EP/BVA, timeouts, deterministic results, metrics/probes |
| Create | `tests/unit/llm/test_safety.py` | Citation discriminator/hash/support validation |
| Create | `tests/contract/llm/test_api_contracts.py` | Retrieval OpenAPI request/response/error contract |
| Create | `tests/contract/llm/test_mcp_contracts.py` | Retrieval MCP schema parity |
| Create | `tests/fixtures/llm/retrieval_smoke_request.json` | Exact local curl request without inline shell JSON |
| Consume | `src/vina_bim_shop/llm/contracts.py`, `src/vina_bim_shop/llm/ports.py` | Topic 09/10-owned shared contracts and retrieval port; no edits here |

## Interfaces, data flow, and failure modes

`SearchRequest(query: str, top_k: int=4, category: str|None, effective_at: UTC datetime|None)` accepts query length 1–2000 and `top_k` 1–8.

`SearchMatch` carries rank, chunk text, immutable document ID/version, category, effective interval, chunk SHA-256, and score. `SearchResponse` carries matches, typed abstention, active index version, request effective time, and discriminated knowledge citations bound to document/version/chunk hashes.

Flow: HTTP or MCP request -> validation -> async retrieval port -> 700 ms timeout -> effective-date/category filtering -> citation SHA re-read/support validation -> schema response -> metrics/trace.

Error mapping is exact:

| Condition | HTTP/status contract |
|---|---|
| Invalid query, `top_k`, category, or timestamp | `422` validation error |
| Empty/no active index or hash-invalid active alias | `409 index_unavailable` |
| Feast/pgvector call exceeds 700 ms or dependency fails | `503 dependency_timeout` |
| No matching policy row | 200 typed abstention with no fabricated match |
| Citation discriminator/hash mismatch | deterministic rejection before response |

Chat-level unsupported generated claims and injection handling are tested in Topic 13; Topic 11 validates retrieval artifacts, not model prose.

## Ordered test-first execution

- [ ] Add red EP/BVA cases and run `rtk uv run pytest tests/unit/llm/test_retrieval.py tests/unit/llm/test_safety.py tests/contract/llm/test_api_contracts.py tests/contract/llm/test_mcp_contracts.py -q`. Expected: nonzero because Task 3 implementation is absent, with failures covering `top_k` values 0, 1, 4, 8, and 9; query lengths 0, 1, 2000, and 2001; filters, timeout, citations, and empty index.
- [ ] Implement the four owned modules with `apply_patch`, then run `rtk uv run pytest tests/unit/llm/test_retrieval.py tests/unit/llm/test_safety.py -q`. Expected: exit 0; timeout is exactly 700 ms and tampered citations fail deterministically.
- [ ] Validate API/MCP parity with `rtk uv run pytest tests/contract/llm/test_api_contracts.py tests/contract/llm/test_mcp_contracts.py -q`. Expected: exit 0; both expose the same SearchRequest/SearchResponse/SearchMatch shapes and only the named MCP tool.
- [ ] Start the owned monitor with `rtk uv run uvicorn vina_bim_shop.llm.api.retrieval:app --host 127.0.0.1 --port 8081`, then in a second serial shell run `rtk curl.exe -sS -X POST http://127.0.0.1:8081/v1/retrieval/search -H "Content-Type: application/json" --data-binary @tests/fixtures/llm/retrieval_smoke_request.json`. Expected: schema-valid response or `409 index_unavailable`; never fabricated matches.
- [ ] Probe with `rtk curl.exe -sS http://127.0.0.1:8081/healthz`, `rtk curl.exe -sS http://127.0.0.1:8081/readyz`, and `rtk curl.exe -sS http://127.0.0.1:8081/metrics`. Expected: process health is independent of dependency readiness and metrics include stable service/route/status labels.
- [ ] Stop only the owned uvicorn monitor, then run `rtk uv run pytest tests/unit/llm/test_retrieval.py tests/unit/llm/test_safety.py tests/contract/llm/test_api_contracts.py tests/contract/llm/test_mcp_contracts.py -q` and `rtk git diff --check`. Expected: both exit 0.

## Evidence, screenshot ownership, and cleanup

Topic 11 owns command transcripts and SHA-256 hashes for focused test reports only. It owns no screenshot. The later GCP evidence topic captures deployed API/MCP proof. Stop only the Topic 11 uvicorn PID; retain no temporary token, server, database, or cloud lease.

## Rubric traceability

| Sheet3 cell | Local proof | Deferred proof |
|---|---|---|
| `Sheet3!E10` | Pydantic/OpenAPI/probe tests | Deployed FastAPI capture |
| `Sheet3!E11` | Async 700 ms timeout and nonblocking tests | Runtime trace |
| `Sheet3!E12` | MCP schema parity and deterministic errors | Helm/RemoteMCPServer proof |
| `Sheet3!E62` | Route-level citation integrity tests | Evaluation evidence |

## Definition of Done

All owned tests pass; local smoke returns only valid data or exact errors; no chart/shared dependency file was edited; the branch is unchanged; `rtk git diff --check` is clean; successor 13 receives exact paths and hashes.

## Completion Record

| Field | Execution value |
|---|---|
| Status | Not started |
| Current branch/status | Record final `rtk git status --short --branch` output |
| Affected files | Record only Topic 11-owned exact paths |
| Commands and exit codes | Record every red test, green test, smoke, probe, and diff check |
| Evidence hashes | Record SHA-256 of non-secret local reports |
| Screenshot QA | Not captured locally; no screenshot claim |
| Cleanup/runtime release | Record owned uvicorn PID stop; no cloud runtime acquired |
| Limitations | Record missing live Feast/GKE evidence or bounded-retry failure |
| Handoff | `tmp/edai2-plan/execution-v1/local/13-coordinator-inference-routing-telemetry.md` |
