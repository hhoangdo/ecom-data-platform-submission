# 15 — Evaluation, Test Quality, and Load Contracts

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the local Task 6 quality gates: exact 60-case fixture, locked metric math, EP/BVA, Hypothesis, bounded CrossHair, complete changed-file scope verification, coverage at least 91%, mutation score strictly above 0.80, and Locust contract tests.

**Architecture:** A deterministic evaluator emits per-case records before aggregates. Every required retrieval/inference call participates in denominators; missing, failed, timeout, non-finite, or silently retried calls fail before aggregation. The scope verifier binds changed production Python to both coverage and mutation configuration.

**Tech Stack:** Python 3.12, uv, pytest, pytest-cov, Hypothesis, CrossHair, mutmut, Locust contract tests, JSONL, SHA-256.

## Metadata

| Field | Locked value |
|---|---|
| Phase | Local executable quality Topic 15 |
| Source task | `tmp/edai2-plan/04.2_llm_design.md` Task 6 quality portion |
| Sheet3 support | `Sheet3!E27:E31`, `Sheet3!E61:E62` |
| Predecessor Completion Record | `tmp/edai2-plan/execution-v1/local/14-agent-security-registry-notebooks.md` must be `Complete` |
| Blocked successor | `tmp/edai2-plan/execution-v1/local/16-images-jenkins-ci.md` |
| Runtime ownership | One local uv test/mutation session |
| Class | Local executable; live Locust/deployed metrics deferred |

## Locked planning basis

Read `C:\Users\oou1hc\.codex\RTK.md`. Verify `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`, `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`, and rubric `tmp/rubic-check/Coursework Tracking (Public).xlsx` `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.

## Global constraints

Current branch and serial session only; `apply_patch`; developer recipes use `rtk uv run` and operator recipes use `rtk make`; no commit/stage/GCP/live Locust/auto Docker stop or prune. Dependency additions use `rtk uv add ...` because Topic 15 uniquely owns `pyproject.toml`/`uv.lock`; inspect `rtk git diff -- pyproject.toml uv.lock`. One bounded retry then `Partial`.

## Read-only current-state refresh

- [ ] Run `rtk git status --short --branch`. Expected: branch/pre-existing changes recorded.
- [ ] Run `rtk proxy certutil -hashfile tmp/edai2-plan/03_data_generator_improvement.md SHA256`. Expected: output contains `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`.
- [ ] Run `rtk proxy certutil -hashfile tmp/edai2-plan/04.2_llm_design.md SHA256`. Expected: output contains `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`.
- [ ] Run `rtk proxy certutil -hashfile "tmp/rubic-check/Coursework Tracking (Public).xlsx" SHA256`. Expected: output contains `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- [ ] Run `rtk proxy powershell -NoProfile -Command "Select-String -Path tmp/edai2-plan/execution-v1/local/14-agent-security-registry-notebooks.md -Pattern '^Status: Complete|\| Status \| Complete \|'"`. Expected: completed predecessor.
- [ ] Run `rtk git diff --check`. Expected: exit 0.

## Scope and non-goals

In scope: fixture/config/evaluator/CLI, metric math, EP/BVA, Hypothesis, CrossHair, scope verifier, coverage/mutation configuration and execution, Locust shape/contract test, local evidence reports.

Non-goals: CI/Docker definitions (Topic 16), live Locust HTML/CSV, deployed latency, GKE, screenshots, or relabeling a failed quality gate.

The verified changed-code scope explicitly includes the full LLM package, `src/vina_bim_shop/orchestration/rag_index_pipeline.py`, changed `src/vina_bim_shop/orchestration/specs.py`, and changed `src/vina_bim_shop/kafka/topics.py`; omission from either coverage or mutmut scope fails.

## Exact file map

| Action | Exact path | Responsibility |
|---|---|---|
| Modify | `pyproject.toml`, `uv.lock` | Test dependencies, coverage and mutmut configuration |
| Create | `src/vina_bim_shop/llm/evaluation.py` | Per-case evaluation and exact aggregate math |
| Create | `configs/llm/evaluation.yaml` | Exact gates and fixture partition |
| Create | `configs/llm/test_scope.yaml` | Changed production Python scope |
| Create | `configs/llm/coverage.ini` | Coverage inclusion/omission contract |
| Create | `tests/fixtures/llm/evaluation_cases.jsonl` | Exact 60 unique cases |
| Create | `tests/unit/llm/test_evaluation.py` | Counts, denominators, nearest-rank p95, missing-call failures |
| Create | `tests/property/llm/test_idempotency.py` | Bounded Hypothesis properties |
| Create | `tests/load/llm/locustfile.py` | Fixed one-user deployed load shape |
| Create | `tests/load/llm/test_locust_contract.py` | Static success/abstention/error and output-path contract |
| Create | `scripts/llm/run_evaluation.py` | Deterministic local/live evaluation CLI |
| Create | `scripts/qa/verify_edai2_test_scope.py` | Git-diff/untracked scope and mutmut coverage verifier |

## Interfaces, data flow, and failure modes

Inputs are the exact 60-case JSONL fixture, evaluation gates, changed/untracked Python inventory, coverage config, mutmut config, and deterministic fake retrieval/inference samples. The evaluator emits one immutable per-case record followed by aggregate metrics; coverage, mutation, CrossHair, Hypothesis, EP/BVA, and Locust-contract reports feed Topic 16 and the later evidence packager.

Fixture duplication/count mismatch, missing required call, timeout/dependency failure, non-finite sample, unknown mutant status, coverage below 91%, mutation score at or below 0.80, CrossHair counterexample, Hypothesis failure, or Locust shape drift fails the topic. Failed/measured samples are never dropped, replaced, or relabeled.

## Exact fixture and metrics

Grounded counts by eight categories are `5,5,5,5,4,4,4,4` = 36; abstention = 12; safety = six injection + six PII = 12; total unique IDs = 60.

For grounded case i, `recall_i@4 = |top4 ∩ relevant| / |relevant|`; recall is macro mean across 36. Each grounded response must be non-abstained with a factual claim and citation. Citation precision denominator is all cited factual claims across 36. All 12 abstention cases must abstain. Safety denominator is exactly 12, so >=0.95 means 12/12.

Retrieval latency requires one call for each 48 non-safety cases. Generation includes every request entering inference and at least 36 grounded cases. Missing calls, dependency failures, timeouts, non-finite samples, or silently discarded retries fail before aggregation. `p95 = sorted_ms[ceil(0.95*n)-1]`; tagged warmups are excluded and measured failures remain.

## Ordered test-first execution

- [ ] Validate red fixture/evaluator tests with `rtk uv run pytest tests/unit/llm/test_evaluation.py tests/property/llm/test_idempotency.py -q`. Expected: nonzero before fixture/evaluator exists, specifically naming counts or metric contracts.
- [ ] Implement fixture/evaluator/config and rerun `rtk uv run pytest tests/unit/llm/test_evaluation.py tests/property/llm/test_idempotency.py -q`. Expected: exit 0 with bounded Hypothesis examples, exact partition and denominator math.
- [ ] Run EP/BVA/API safety coverage with `rtk uv run pytest tests/unit/llm/test_retrieval.py tests/unit/llm/test_drift.py tests/unit/llm/test_inference.py tests/unit/llm/test_coordinator.py tests/unit/llm/test_safety.py -q`. Expected: exit 0 and explicit boundary parametrization.
- [ ] Run `rtk uv run crosshair check src/vina_bim_shop/llm/safety.py src/vina_bim_shop/llm/routing.py --analysis_kind=PEP316 --per_condition_timeout=5 --max_uninteresting_iterations=64`. Expected: exit 0 with no counterexample.
- [ ] Run `rtk uv run python scripts/qa/verify_edai2_test_scope.py --base-ref $env:EDAI2_BASE_REF --scope configs/llm/test_scope.yaml --coverage-config configs/llm/coverage.ini --pyproject pyproject.toml`. Expected: exit 0; every changed/untracked production Python path is in coverage and mutmut scope.
- [ ] Run `rtk uv run pytest tests/unit/llm tests/contract/llm tests/property/llm tests/integration/llm --cov=src/vina_bim_shop --cov-config=configs/llm/coverage.ini --cov-report=term-missing --cov-report=html:evidence/04_2_llm_design/tests/coverage --cov-fail-under=91`. Expected: exit 0 and coverage >=91%.
- [ ] Run `rtk uv run mutmut run`, then `rtk uv run mutmut results`. Expected: all statuses classified and `killed/(killed+survived+timeout+suspicious+untested) > 0.80`; otherwise Topic 15 is Partial.
- [ ] Run `rtk uv run pytest tests/load/llm/test_locust_contract.py -q`. Expected: exit 0; one-user/concurrency shape covers success/abstention/error and exact future HTML/CSV paths.
- [ ] Run `rtk git diff -- pyproject.toml uv.lock` and `rtk git diff --check`. Expected: dependency diff is only required locked additions and whitespace check exits 0.

## Evidence, cleanup, rubric, and DoD

Topic 15 owns actual local coverage, mutation, CrossHair, Hypothesis, EP/BVA and contract results. Only deployed Locust HTML/CSV and live latency remain deferred. Remove local caches/reports only if the evidence contract does not retain them; stop no unrelated process.

| Sheet3 cell | Local proof | Deferred proof |
|---|---|---|
| `Sheet3!E27:E31` | executed coverage, mutation, EP/BVA, Hypothesis, CrossHair | contextual screenshot packaging |
| `Sheet3!E61:E62` | exact fixture/metrics and Locust contract | deployed measurements/HTML/CSV |

## Definition of Done

All local gates actually run and pass at locked thresholds; missing samples fail; no live metric is fabricated; Topic 16 receives verified test scope and dependency locks.

## Completion Record

| Field | Execution value |
|---|---|
| Status | Not started |
| Current branch/status | Record final `rtk git status --short --branch` |
| Affected files | Record Topic 15 paths and inspected dependency diff |
| Commands and exit codes | Record every quality command and actual code |
| Evidence hashes | Record coverage/mutation/CrossHair/test report hashes |
| Screenshot QA | Local report only; runtime screenshot deferred |
| Cleanup/runtime release | Record test cache/process cleanup; no cloud runtime |
| Limitations | Record live Locust/deployed latency or any failed gate |
| Handoff | `tmp/edai2-plan/execution-v1/local/16-images-jenkins-ci.md` |
