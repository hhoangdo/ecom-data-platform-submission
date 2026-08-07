# 12 — Section 03 Loader, Drift API, and MCP

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Task 4 end to end locally: strict verified Section 03 import, immutable PostgreSQL staging and active-view switching, Feast/Valkey activation, compensating rollback, drift API, and exact drift MCP contract.

**Architecture:** A verifier fingerprints the canonical Section 03 bundle before any write. An advisory-locked transaction stages one manifest hash, validates rows/counts/cutoffs, atomically switches stable PostgreSQL views, applies Feast, materializes Valkey, and rolls back/rematerializes the prior active version if any post-switch stage fails. Drift reads precomputed daily PSI and optionally enriches one ID; it never recomputes arbitrary-window or per-customer PSI. Each drift dependency call has an exact 1.5 s deadline and permits one jittered retry only for an idempotent connection failure.

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

Read `C:\Users\oou1hc\.codex\RTK.md` first. Locked hashes: Section 03 `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`; EDAI2 `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`; `tmp/rubic-check/Coursework Tracking (Public).xlsx` `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.

## Global constraints

Stay on the current branch and run serially. Use `apply_patch`; prefix every shell command with `rtk`; use `rtk uv run` for developer commands and `rtk make` for operator recipes. Topic 08 owns the baseline dependencies and lockfile: run `rtk uv lock --check`, and treat a missing prerequisite dependency as a `Partial` predecessor defect rather than editing `pyproject.toml` or `uv.lock`. Do not commit/stage, invoke GCP, auto-prune/stop Docker, or overwrite the canonical Section 03 evidence. After one bounded repair retry, report `Partial`.

## Read-only current-state refresh

- [ ] Run `rtk git status --short --branch`. Expected: branch and pre-existing changes recorded.
- [ ] Run `rtk proxy certutil -hashfile tmp/edai2-plan/03_data_generator_improvement.md SHA256`. Expected: output contains `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`.
- [ ] Run `rtk proxy certutil -hashfile tmp/edai2-plan/04.2_llm_design.md SHA256`. Expected: output contains `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`.
- [ ] Run `rtk proxy certutil -hashfile "tmp/rubic-check/Coursework Tracking (Public).xlsx" SHA256`. Expected: output contains `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- [ ] Run `rtk proxy powershell -NoProfile -Command "Select-String -Path tmp/edai2-plan/execution-v1/local/08-edai2-prerequisite-contracts.md -Pattern '^Status: Complete|\| Status \| Complete \|'"`. Expected: one completed predecessor record.
- [ ] Run `rtk uv lock --check`. Expected: exit 0 with the Topic 08-owned baseline lockfile unchanged.
- [ ] Run `rtk uv run python scripts/generate/verify_section03_manifest.py --manifest evidence/03_data_generator_improvement/section03_manifest.json --strict`. Expected: exit 0 and `runtime_evidence.status=verified`; no mutation.
- [ ] Run `rtk git diff --check`. Expected: exit 0 before scoped edits; otherwise stop this topic as `Partial`.

## Scope and non-goals

In scope: strict loader, fingerprint/no-op, different-hash activation, PostgreSQL advisory lock and view swap, Feast apply, Valkey materialization, compensating rollback, exact drift schemas, async API/MCP, probes/metrics, integration/unit/contract tests.

Non-goals: regenerating Section 03, changing `id,label`, live GCS upload, GKE Job, arbitrary PSI recomputation, per-customer PSI, charts, SandboxAgents, and screenshots.

## Exact file map

| Action | Exact path | Responsibility |
|---|---|---|
| Modify | `src/vina_bim_shop/llm/section03_ingestion.py` | Complete the Topic 08 scaffold with verify, fingerprint, stage, lock, activate, no-op, and rollback |
| Modify | `src/vina_bim_shop/llm/drift.py` | Complete the Topic 08 scaffold with window validation, population status, and optional-ID enrichment |
| Modify | `src/vina_bim_shop/llm/adapters/feast_postgres.py` | Complete the Topic 08 PostgreSQL/Feast/Valkey ports and compensating activation adapter |
| Modify | `src/vina_bim_shop/llm/api/drift.py` | Complete the Topic 08 FastAPI scaffold with the drift route, probes, metrics, and exact errors |
| Modify | `src/vina_bim_shop/llm/mcp/drift.py` | Complete the Topic 08 `detect_customer_order_drift` schema and adapter |
| Create | `scripts/feast/load_section03.py` | Verify-only and activation CLI |
| Create | `scripts/llm/smoke_drift.py` | Manifest-derived local API smoke |
| Modify | `infra/feast/feature_store.yaml` | Extend the Topic 10 store scaffold with Section 03 registry/offline/online references |
| Modify | `infra/feast/features.py` | Extend the Topic 10 feature scaffold with stable Section 03 feature and daily-health definitions |
| Create | `infra/postgres/edai2/003_section03_features.sql` | Immutable version tables and stable active views |
| Create | `tests/integration/llm/test_section03_ingestion.py` | Transaction/no-op/different-hash/rollback tests |
| Create | `tests/unit/llm/test_drift.py` | Windows, thresholds, enrichment, citations, repeated equality |
| Consume | `tests/contract/llm/test_section03_contract.py` | Topic 08-owned strict manifest/schema/hash prerequisite; do not weaken it |
| Modify | `tests/contract/llm/test_mcp_contracts.py` | Add drift byte-parity assertions to the Topic 08 shared MCP contract scaffold |

## Interfaces, data flow, and failure modes

The public Pydantic contract is byte-faithful to locked source lines 302–425:

```python
class DriftDetectRequest(BaseModel):
    id: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    baseline_window: TimeWindow
    candidate_window: TimeWindow
    feature_name: Literal["f_customer_order_frequency_7d"] = "f_customer_order_frequency_7d"

class DriftDetectResponse(BaseModel):
    request_id: UUID
    scope: Literal["population"]
    feature_name: Literal["f_customer_order_frequency_7d"]
    window_days: Literal[7]
    baseline_window: TimeWindow
    candidate_window: TimeWindow
    population_size: int
    candidate_day_count: int
    baseline_mean: float
    candidate_mean: float
    psi: float
    status: Literal["stable", "warning", "alert"]
    drift_detected: bool
    feature_service_version: str
    customer_context: Section03FeatureRow | None
    observed_at: UtcDateTime
```

There are no public peak-date, manifest-hash, citation-list, or `DriftFeatureContext` fields. The chat coordinator constructs any drift grounding citation internally from the verified response and active Section 03 evidence.

Flow: strict manifest/hash verification -> fingerprint lookup -> same-hash no-op or advisory lock -> immutable staging -> schema/count/cutoff validation -> transactional active-view switch -> Feast apply -> Valkey materialize -> fingerprint read-back -> success. Any failure after switch restores prior views, reapplies prior Feast registry state, and rematerializes prior Valkey values.

Staging rejects any label artifact not ordered exactly as `id,label`, any null/duplicate ID, label outside integer `{0,1}`, customer/feature/label cohort mismatch, cutoff/horizon mismatch, row-count mismatch, or source/result hash mismatch. Optional-ID lookup never changes the population PSI denominator.

Status boundaries are stable below 0.10, warning at `>=0.10`, alert at `>=0.15`. Baseline must match the manifest's complete baseline day; candidate duration is 1–30 complete UTC days. A syntactically valid absent optional ID returns `200` with `customer_context=null` and never changes the population PSI denominator; a malformed ID returns `422`.

| Condition | Contract |
|---|---|
| Invalid/non-UTC/overlap/duration/id/feature input | `422` |
| No verified active daily-health dataset | `409 feature_unavailable` |
| Syntactically valid optional ID is absent | `200` population response with `customer_context=null` |
| PostgreSQL/Feast/Valkey exceeds the exact 1.5 s deadline, or its one permitted connection retry fails | `503 dependency_timeout` |
| Same verified hash | successful fingerprint-checked no-op |
| Different verified hash | staged activation after all validation |
| Failure after view switch | compensating rollback; prior version active |

## Ordered test-first execution

- [ ] Add red ingestion/drift/contract tests and run `rtk uv run pytest tests/integration/llm/test_section03_ingestion.py tests/unit/llm/test_drift.py tests/contract/llm/test_section03_contract.py tests/contract/llm/test_mcp_contracts.py -q`. Expected: nonzero with focused missing Task 4 behavior.
- [ ] Implement verifier and verify-only CLI, then run `rtk uv run python scripts/feast/load_section03.py --manifest evidence/03_data_generator_improvement/section03_manifest.json --strict --verify-only`. Expected: exit 0 only for complete hash-bound verified evidence and no PostgreSQL/Feast contact.
- [ ] Implement staging/advisory-lock/active-view/Feast/Valkey adapter and run `rtk uv run pytest tests/integration/llm/test_section03_ingestion.py -q`. Expected: exit 0; same-hash is a fingerprint no-op, different hash activates, injected Feast failure restores prior PostgreSQL/Feast/Valkey fingerprints.
- [ ] Implement drift service/API/MCP and run `rtk uv run pytest tests/unit/llm/test_drift.py tests/contract/llm/test_section03_contract.py tests/contract/llm/test_mcp_contracts.py -q`. Expected: exit 0 for exact windows, PSI thresholds, exact 1.5 s deadline, one jittered retry only for idempotent connection failure, absent optional-ID `customer_context=null`, malformed-ID `422`, public-schema byte parity, and repeated-call equality.
- [ ] Start the owned monitor hidden with `rtk powershell -NoProfile -Command '$d="tmp/edai2-local/topic12"; New-Item -ItemType Directory -Force -Path $d | Out-Null; $p=Start-Process -FilePath "rtk" -ArgumentList @("uv","run","uvicorn","vina_bim_shop.llm.api.drift:app","--host","127.0.0.1","--port","8082") -WindowStyle Hidden -PassThru -RedirectStandardOutput "$d/drift.stdout.log" -RedirectStandardError "$d/drift.stderr.log"; Set-Content -LiteralPath "$d/drift.pid" -Value $p.Id -NoNewline'`, then wait with `rtk powershell -NoProfile -Command '$ok=$false; 1..40 | ForEach-Object { & rtk curl.exe --fail-with-body -sS http://127.0.0.1:8082/healthz *> $null; if ($LASTEXITCODE -eq 0) { $ok=$true; break }; Start-Sleep -Milliseconds 250 }; if (-not $ok) { Write-Error "drift monitor did not become healthy"; exit 1 }'`, then run `rtk uv run python scripts/llm/smoke_drift.py --base-url http://127.0.0.1:8082 --section03-manifest evidence/03_data_generator_improvement/section03_manifest.json --candidate-days 7 --id fixture-customer-001 --output tmp/edai2-local/topic12/drift-response.json --status-output tmp/edai2-local/topic12/drift-status.txt`. Expected: the health gate exits 0 and the smoke CLI emits a schema-valid result or exact `409 feature_unavailable`; finite population PSI and exact status, with no undeclared public fields. If either command fails after the PID is written, run the following PID cleanup checkbox before returning from Topic 12.
- [ ] Stop and verify only the recorded monitor with `rtk powershell -NoProfile -Command '$monitorPid=[int](Get-Content -LiteralPath "tmp/edai2-local/topic12/drift.pid"); Stop-Process -Id $monitorPid; Wait-Process -Id $monitorPid -ErrorAction SilentlyContinue; if (Get-Process -Id $monitorPid -ErrorAction SilentlyContinue) { Write-Error "owned drift monitor still running"; exit 1 }'`, then run `rtk uv run pytest tests/integration/llm/test_section03_ingestion.py tests/unit/llm/test_drift.py tests/contract/llm/test_section03_contract.py tests/contract/llm/test_mcp_contracts.py -q` and `rtk git diff --check`. Expected: both checks exit 0 and the exact recorded PID is absent.

## Evidence, cleanup, and rubric

Topic 12 owns verify/import test reports and hashes plus `tmp/edai2-local/topic12/drift.pid`, `drift.stdout.log`, `drift.stderr.log`, `drift-response.json`, and `drift-status.txt`, not a GKE Job or screenshot. Test containers are stopped only when explicitly created by this topic; never prune shared Docker. Canonical Section 03 files remain read-only.

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
