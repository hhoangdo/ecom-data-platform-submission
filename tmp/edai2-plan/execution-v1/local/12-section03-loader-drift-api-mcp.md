# 12 — Section 03 Loader, Drift API, and MCP

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Task 4 end to end locally: strict verified Section 03 import, immutable PostgreSQL staging and active-view switching, Feast/Valkey activation, compensating rollback, drift API, and exact drift MCP contract.

**Architecture:** A verifier fingerprints the canonical Section 03 bundle before any write. An advisory-locked transaction stages one manifest hash, validates rows/counts/cutoffs, atomically switches stable PostgreSQL views, applies Feast, materializes Valkey, and rolls back/rematerializes the prior active version if any post-switch stage fails. Drift reads precomputed daily PSI and optionally enriches one ID; it never recomputes arbitrary-window or per-customer PSI.

**Tech Stack:** Python 3.12, uv, FastAPI, Pydantic v2, MCP, PostgreSQL, Feast, Valkey, SQL, pytest, SHA-256.

## Metadata

| Field | Locked value |
|---|---|
| Phase | Local/static implementation Topic 12 |
| Source task | `tmp/edai2-plan/04.2_llm_design.md` Task 4 |
| Sheet3 support | `Sheet3!E16:E18` |
| Predecessor Completion Record | `tmp/edai2-plan/execution-v1/local/08-edai2-prerequisite-contracts.md` must be `Complete` |
| Blocked successor | `tmp/edai2-plan/execution-v1/local/13-coordinator-inference-routing-telemetry.md` |
| Runtime ownership | One local verify/API session; optional test containers remain explicitly owned |
| Class | Local/static; no GCP mutation |

## Locked planning basis

Read `C:\Users\oou1hc\.codex\RTK.md` first. Locked hashes: Section 03 `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`; EDAI2 `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`; `tmp/rubic-check/Coursework Tracking (Public).xlsx` `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.

## Global constraints

Stay on the current branch and run serially. Use `apply_patch`; prefix every shell command with `rtk`; use `rtk uv run` for developer commands and `rtk make` for operator recipes. Dependency changes are handed to Topic 15 for `rtk uv add` plus `rtk git diff -- pyproject.toml uv.lock` inspection. Do not commit/stage, invoke GCP, auto-prune/stop Docker, or overwrite the canonical Section 03 evidence. After one bounded repair retry, report `Partial`.

## Read-only current-state refresh

- [ ] Run `rtk git status --short --branch`. Expected: branch and pre-existing changes recorded.
- [ ] Run `rtk proxy certutil -hashfile tmp/edai2-plan/03_data_generator_improvement.md SHA256`. Expected: output contains `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`.
- [ ] Run `rtk proxy certutil -hashfile tmp/edai2-plan/04.2_llm_design.md SHA256`. Expected: output contains `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`.
- [ ] Run `rtk proxy certutil -hashfile "tmp/rubic-check/Coursework Tracking (Public).xlsx" SHA256`. Expected: output contains `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- [ ] Run `rtk proxy powershell -NoProfile -Command "Select-String -Path tmp/edai2-plan/execution-v1/local/08-edai2-prerequisite-contracts.md -Pattern '^Status: Complete|\| Status \| Complete \|'"`. Expected: one completed predecessor record.
- [ ] Run `rtk uv run python scripts/generate/verify_section03_manifest.py --manifest evidence/03_data_generator_improvement/section03_manifest.json --strict`. Expected: exit 0 and `runtime_evidence.status=verified`; no mutation.
- [ ] Run `rtk git diff --check`. Expected: exit 0 before scoped edits; otherwise stop this topic as `Partial`.

## Scope and non-goals

In scope: strict loader, fingerprint/no-op, different-hash activation, PostgreSQL advisory lock and view swap, Feast apply, Valkey materialization, compensating rollback, exact drift schemas, async API/MCP, probes/metrics, integration/unit/contract tests.

Non-goals: regenerating Section 03, changing `id,label`, live GCS upload, GKE Job, arbitrary PSI recomputation, per-customer PSI, charts, SandboxAgents, and screenshots.

## Exact file map

| Action | Exact path | Responsibility |
|---|---|---|
| Create | `src/vina_bim_shop/llm/section03_ingestion.py` | Verify, fingerprint, stage, lock, activate, no-op, rollback |
| Create | `src/vina_bim_shop/llm/drift.py` | Window validation, peak/status selection, optional-ID enrichment, citations |
| Create | `src/vina_bim_shop/llm/adapters/feast_postgres.py` | PostgreSQL/Feast/Valkey ports and compensating activation adapter |
| Create | `src/vina_bim_shop/llm/api/drift.py` | FastAPI drift route, probes, metrics, exact errors |
| Create | `src/vina_bim_shop/llm/mcp/drift.py` | `detect_customer_order_drift` schema and adapter |
| Create | `scripts/feast/load_section03.py` | Verify-only and activation CLI |
| Create | `scripts/llm/smoke_drift.py` | Manifest-derived local API smoke |
| Create | `infra/feast/feature_store.yaml` | Registry/offline/online store references |
| Create | `infra/feast/features.py` | Stable Section 03 feature and daily-health definitions |
| Create | `infra/postgres/edai2/003_section03_features.sql` | Immutable version tables and stable active views |
| Create | `tests/integration/llm/test_section03_ingestion.py` | Transaction/no-op/different-hash/rollback tests |
| Create | `tests/unit/llm/test_drift.py` | Windows, thresholds, enrichment, citations, repeated equality |
| Create | `tests/contract/llm/test_section03_contract.py` | Manifest/schema/hash boundary |
| Consume | `tests/contract/llm/test_mcp_contracts.py` | Topic 11-owned shared MCP harness; drift assertions live in Topic 12-owned Section 03 contract test |

## Interfaces, data flow, and failure modes

`DriftDetectRequest(id: str|None, baseline_window: UtcWindow, candidate_window: UtcWindow, feature_name: Literal["f_customer_order_frequency_7d"])`.

`DriftDetectResponse` includes population PSI, `stable|warning|alert`, deterministic peak date, baseline/candidate complete-day windows, optional `DriftFeatureContext`, active manifest hash, and `DriftEvidenceCitation` entries binding the canonical result artifact hash and each source hash.

Flow: strict manifest/hash verification -> fingerprint lookup -> same-hash no-op or advisory lock -> immutable staging -> schema/count/cutoff validation -> transactional active-view switch -> Feast apply -> Valkey materialize -> fingerprint read-back -> success. Any failure after switch restores prior views, reapplies prior Feast registry state, and rematerializes prior Valkey values.

Staging rejects any label artifact not ordered exactly as `id,label`, any null/duplicate ID, label outside integer `{0,1}`, customer/feature/label cohort mismatch, cutoff/horizon mismatch, row-count mismatch, or source/result hash mismatch. Optional-ID lookup never changes the population PSI denominator.

Status boundaries are stable below 0.10, warning at `>=0.10`, alert at `>=0.15`. Baseline must match the manifest's complete baseline day; candidate duration is 1–30 complete UTC days. Optional ID only enriches exact feature/label context.

| Condition | Contract |
|---|---|
| Invalid/non-UTC/overlap/duration/id/feature input | `422` |
| No verified active feature/hash or missing optional ID | `409 feature_unavailable` |
| PostgreSQL/Feast/Valkey timeout | `503 dependency_timeout` |
| Same verified hash | successful fingerprint-checked no-op |
| Different verified hash | staged activation after all validation |
| Failure after view switch | compensating rollback; prior version active |

## Ordered test-first execution

- [ ] Add red ingestion/drift/contract tests and run `rtk uv run pytest tests/integration/llm/test_section03_ingestion.py tests/unit/llm/test_drift.py tests/contract/llm/test_section03_contract.py tests/contract/llm/test_mcp_contracts.py -q`. Expected: nonzero with focused missing Task 4 behavior.
- [ ] Implement verifier and verify-only CLI, then run `rtk uv run python scripts/feast/load_section03.py --manifest evidence/03_data_generator_improvement/section03_manifest.json --strict --verify-only`. Expected: exit 0 only for complete hash-bound verified evidence and no PostgreSQL/Feast contact.
- [ ] Implement staging/advisory-lock/active-view/Feast/Valkey adapter and run `rtk uv run pytest tests/integration/llm/test_section03_ingestion.py -q`. Expected: exit 0; same-hash is a fingerprint no-op, different hash activates, injected Feast failure restores prior PostgreSQL/Feast/Valkey fingerprints.
- [ ] Implement drift service/API/MCP and run `rtk uv run pytest tests/unit/llm/test_drift.py tests/contract/llm/test_section03_contract.py tests/contract/llm/test_mcp_contracts.py -q`. Expected: exit 0 for exact windows, PSI thresholds, optional-ID enrichment, hash citations, and repeated-call equality.
- [ ] Start `rtk uv run uvicorn vina_bim_shop.llm.api.drift:app --host 127.0.0.1 --port 8082`, then run `rtk uv run python scripts/llm/smoke_drift.py --base-url http://127.0.0.1:8082 --section03-manifest evidence/03_data_generator_improvement/section03_manifest.json --candidate-days 7 --id fixture-customer-001`. Expected: schema-valid result or exact `409 feature_unavailable`; finite PSI, exact status, and hash-bound citations.
- [ ] Stop only the owned API monitor, then run `rtk uv run pytest tests/integration/llm/test_section03_ingestion.py tests/unit/llm/test_drift.py tests/contract/llm/test_section03_contract.py tests/contract/llm/test_mcp_contracts.py -q` and `rtk git diff --check`. Expected: both exit 0.

## Evidence, cleanup, and rubric

Topic 12 owns verify/import test reports and hashes, not a GKE Job or screenshot. Test containers are stopped only when explicitly created by this topic; never prune shared Docker. Canonical Section 03 files remain read-only.

| Sheet3 cell | Local proof | Deferred proof |
|---|---|---|
| `Sheet3!E16` | Drift API validation/probes tests | deployed API |
| `Sheet3!E17` | async Feast/Postgres/Valkey timeout tests | runtime trace |
| `Sheet3!E18` | MCP parity and activation safety | deployed MCP/Helm |

## Definition of Done

Strict verification, no-op, activation, rollback, API/MCP, windows, citations and tests pass; source contract remains exact; no live GCP mutation occurs; successor 13 gets the active-hash interface.

## Completion Record

| Field | Execution value |
|---|---|
| Status | Not started |
| Current branch/status | Record final `rtk git status --short --branch` |
| Affected files | Record Topic 12 exact paths only |
| Commands and exit codes | Record verify, red/green tests, smoke and diff check |
| Evidence hashes | Record SHA-256 of non-secret reports |
| Screenshot QA | Not captured locally |
| Cleanup/runtime release | Record owned uvicorn/test-container release or no runtime |
| Limitations | Record unavailable local dependencies or bounded-retry failure |
| Handoff | `tmp/edai2-plan/execution-v1/local/13-coordinator-inference-routing-telemetry.md` |
