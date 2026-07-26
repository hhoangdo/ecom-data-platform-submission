# 13 — Coordinator, Inference Routing, and Telemetry

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Task 5 chat facade, deterministic routing/experiments, observed inference adapter, strict token budgeting, safe timeout abstention, and correlated redacted telemetry.

**Architecture:** `POST /v1/chat` validates a fixed chat contract, chooses an explicit/automatic route hint and one of three coordinator A2A destinations, and uses the facade's only outbound adapter through agentgateway. Typed timeout results become recorded failed tool calls plus grounded abstention; they never cross-route or fabricate data.

**Tech Stack:** Python 3.12, uv, FastAPI, Pydantic v2, tiktoken-compatible budgeting, OpenTelemetry, Langfuse port, agentgateway A2A adapter, pytest.

## Metadata

| Field | Locked value |
|---|---|
| Phase | Local/static implementation Topic 13 |
| Source task | `tmp/edai2-plan/04.2_llm_design.md` Task 5 coordinator/inference portion |
| Sheet3 support | `Sheet3!E24:E26`, `Sheet3!E50`, `Sheet3!E54:E57` |
| Predecessor Completion Records | `tmp/edai2-plan/execution-v1/local/11-retrieval-api-mcp-safety.md`; `tmp/edai2-plan/execution-v1/local/12-section03-loader-drift-api-mcp.md`, both `Complete` |
| Blocked successor | `tmp/edai2-plan/execution-v1/local/14-agent-security-registry-notebooks.md` |
| Runtime ownership | Local uv test/API session only |
| Class | Local/static; no GCP mutation |

## Locked planning basis

Read `C:\Users\oou1hc\.codex\RTK.md`. Locked hashes: `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`, `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`, and rubric `tmp/rubic-check/Coursework Tracking (Public).xlsx` `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.

## Global constraints

Use current branch, serial execution, `apply_patch`, and `rtk` prefixes. No stage/commit/worktree/GCP/Docker auto-prune or stop. `rtk uv run` is developer mode; `rtk make` is operator mode. Dependency changes are handed to Topic 15 for `rtk uv add` plus `rtk git diff -- pyproject.toml uv.lock` inspection. One bounded retry, then `Partial`.

## Read-only current-state refresh

- [ ] Run `rtk git status --short --branch`. Expected: branch and unrelated changes captured.
- [ ] Run `rtk proxy certutil -hashfile tmp/edai2-plan/03_data_generator_improvement.md SHA256`. Expected: output contains `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`.
- [ ] Run `rtk proxy certutil -hashfile tmp/edai2-plan/04.2_llm_design.md SHA256`. Expected: output contains `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`.
- [ ] Run `rtk proxy certutil -hashfile "tmp/rubic-check/Coursework Tracking (Public).xlsx" SHA256`. Expected: output contains `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- [ ] Run `rtk proxy powershell -NoProfile -Command "Select-String -Path tmp/edai2-plan/execution-v1/local/11-retrieval-api-mcp-safety.md,tmp/edai2-plan/execution-v1/local/12-section03-loader-drift-api-mcp.md -Pattern '^Status: Complete|\| Status \| Complete \|'"`. Expected: two completed predecessor records.
- [ ] Run `rtk git diff --check`. Expected: exit 0.

## Scope and non-goals

In scope: chat schemas/API, observed inference/A2A adapters, routing Strategy, independent deterministic experiments, 3968/128 budgets, whole-turn/chunk dropping, timeout tool-call recording, citations/tool calls/versions, telemetry/redaction, unit tests.

Non-goals: SandboxAgent/registry manifests and notebooks (Topic 14), evaluation execution (Topic 15), platform manifests, live agent/model calls, charts, GCP, and screenshots.

## Exact file map

| Action | Exact path | Responsibility |
|---|---|---|
| Create | `src/vina_bim_shop/llm/inference.py` | `ObservedInferenceClient`, budgets, typed timeout results |
| Create | `src/vina_bim_shop/llm/routing.py` | Route hints and independent stable experiment assignment |
| Create | `src/vina_bim_shop/llm/coordinator.py` | `CommerceAgentCoordinator`, citations/tool calls/abstention |
| Create | `src/vina_bim_shop/llm/telemetry.py` | Redacted OTel/Langfuse attributes and dropped-content counters |
| Create | `src/vina_bim_shop/llm/adapters/llmd.py` | Observed private inference port |
| Create | `src/vina_bim_shop/llm/adapters/kagent.py` | Facade-only A2A adapter for three destinations |
| Create | `src/vina_bim_shop/llm/api/chat.py` | Exact chat FastAPI schema, probes, metrics |
| Create | `configs/llm/models.yaml` | Model IDs, 4096 context, 3968 input, 128 output, concurrency 1 |
| Create | `configs/llm/routing.yaml` | Salts, 90:10 assignment, destinations, promoted alias |
| Create | `tests/unit/llm/test_inference.py` | Budgets, timeout and telemetry tests |
| Create | `tests/unit/llm/test_coordinator.py` | Routes, citations/tool calls, experiments, negative dependency graph |
| Consume | `tests/unit/llm/test_safety.py` | Topic 11-owned retrieval integrity suite; chat injection/unsupported-claim cases live in Topic 13-owned coordinator tests |

## Interfaces, data flow, and failure modes

`ChatRequest` has session UUID, messages, optional `route_hint=auto|support|drift|abstain`, and experiment eligibility. `ChatResponse` has answer/abstention, selected logical agent and runtime destination, model/config/index versions, discriminated citations, and recorded tool calls.

Destinations are exactly `coordinator-v1-primary`, `coordinator-v2-primary`, and `coordinator-v1-comparison`. No `v2-comparison`.

Input budget is exactly 3968 tokens and output budget 128 within context 4096. Reduction removes oldest complete history turns atomically, then lowest-ranked complete retrieval chunks; it never slices content. If fixed system/current-user content alone exceeds 3968, return `422 fixed_content_too_large`. Redacted telemetry records dropped turn/chunk counts, token totals and hashes, never content.

Agent experiment uses locked salt `agent_exp_v1` and stable UUID hash with 90:10 `v1-primary|v2-primary`. Model experiment uses independent salt `model_exp_v1` and 90:10 `v1-primary|v1-comparison`. Ordinary sessions use the promoted alias. The facade allowlist contains only these three A2A destinations.

A typed A2A/tool/model timeout is recorded as a failed tool call with duration/status and yields grounded abstention. It never invokes another route, specialist, MCP, model, Feast, or database directly.

## Ordered test-first execution

- [ ] Add red tests and run `rtk uv run pytest tests/unit/llm/test_inference.py tests/unit/llm/test_coordinator.py tests/unit/llm/test_safety.py -q`. Expected: nonzero for missing Task 5 implementation; cases cover routes, citations, timeouts, destinations, salts, 3968/128 boundaries, whole-item dropping, fixed-content 422 and redaction.
- [ ] Implement budgets/inference/telemetry, then run `rtk uv run pytest tests/unit/llm/test_inference.py -q`. Expected: exit 0; boundary 3968 accepted, 3969 reduced or fixed-content 422, output capped at 128, timeout is typed.
- [ ] Implement routing/coordinator/chat API, then run `rtk uv run pytest tests/unit/llm/test_coordinator.py tests/unit/llm/test_safety.py -q`. Expected: exit 0; exact destinations/salts/90:10 assignments and no cross-route fallback.
- [ ] Run `rtk uv run crosshair check src/vina_bim_shop/llm/routing.py --analysis_kind=PEP316 --per_condition_timeout=5 --max_uninteresting_iterations=64`. Expected: exit 0 with stable deterministic assignment and no counterexample.
- [ ] Start `rtk uv run uvicorn vina_bim_shop.llm.api.chat:app --host 127.0.0.1 --port 8083`, then run `rtk curl.exe -sS -X POST http://127.0.0.1:8083/v1/chat -H "Content-Type: application/json" -d "{\"session_id\":\"00000000-0000-4000-8000-000000000001\",\"messages\":[{\"role\":\"user\",\"content\":\"What is the returns policy?\"}],\"route_hint\":\"support\"}"`. Expected: typed grounded response if the A2A fake is configured, otherwise recorded dependency timeout plus abstention; never fabricated answer or alternate route.
- [ ] Stop only the owned monitor, then run `rtk uv run pytest tests/unit/llm/test_inference.py tests/unit/llm/test_coordinator.py tests/unit/llm/test_safety.py -q` and `rtk git diff --check`. Expected: both exit 0.

## Evidence, cleanup, rubric, and DoD

Hash local test/CrossHair reports. No screenshots or model-performance claims are owned. Stop only Topic 13 uvicorn; release no cloud runtime.

| Sheet3 cell | Local proof | Deferred proof |
|---|---|---|
| `Sheet3!E24:E26` | routing/budget/timeout/telemetry tests | deployed agent/model scaling |
| `Sheet3!E50` | facade-only A2A dependency graph | gateway negative matrix |
| `Sheet3!E54:E57` | trace attributes and independent experiment assignments | live traces/A-B results |

## Definition of Done

Exact schemas, budgets, assignments, destinations, timeout abstention, citations/tool calls, facade-only adapter, telemetry and focused tests pass; no live claims; Topic 14 can bind resources to the three destinations.

## Completion Record

| Field | Execution value |
|---|---|
| Status | Not started |
| Current branch/status | Record final `rtk git status --short --branch` |
| Affected files | Record Topic 13 exact paths only |
| Commands and exit codes | Record red/green tests, CrossHair, local smoke, diff check |
| Evidence hashes | Record non-secret report SHA-256 |
| Screenshot QA | Not captured locally |
| Cleanup/runtime release | Record owned uvicorn stop; no cloud runtime |
| Limitations | Record unexecuted live A2A/model proof or bounded failure |
| Handoff | `tmp/edai2-plan/execution-v1/local/14-agent-security-registry-notebooks.md` |
