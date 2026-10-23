# Topic 28: RAG and Inference Benchmark Implementation Plan

> **For any agent (Codex / opencode / Claude / etc):** Work task-by-task in one session. Steps use checkbox (`- [ ]`) tracking. Auto-run without asking; only stop on safe-stop gates below.

> **Study-only simplified run (first iteration, overrides strict gates below):**
> - Repo root = current checkout (`<repo-root>`). Use `rtk` prefix if installed, else run commands directly.
> - Auto-run; no mid-run approvals. Only safe stops: budget/lease/capacity fail, missing index/model inputs, wrong context.
> - Happy-path first: canonical `canonical-evidence-<sha>` RAG run + DataHub read-back + factorial completes + agent startup matrix completes wins. Numeric gates (p95<=20s, >=5% gain, >=20%/>=5% startup) may stay `Partial` — record measured numbers honestly, one bounded retry max, then hand off.
> - Screenshots: viewport PNG + SHA + machine link + eyeball check is enough.
> - Study-mode relaxation v1 (study-first, single-agent): plan-doc SHA pins and manifest-byte equality are LOG-ONLY — record computed vs listed values, never block. Image remote-digest equality stays HARD.
> - Safety gates stay HARD: live budget preflight, exact kubeconfig/context, capacity ceilings. Numeric gates (p95, gains, startup) are record-and-continue `Partial`, one bounded retry max. No mid-run approvals.
> - PoC-first sprint (trial ends 2026-10-25): this topic is the readiness unlock — demo win = canonical `canonical-evidence-<sha>` index built + retrieval Ready flip + drift Section 03 activation with `import.json`. Do the local chart fixes FIRST with no lease (drift Job `/data/section03` mount, mesh-CR `description`/schema fields, `section03_report.md` re-pin) via owning topics, then run the lease. Benchmark numerics stay `Partial`. One lease, time-box, suspend pools-zero after, log spend/remaining/trial-hours.
>
> **Study-only contract amendment 2026-10-18 (operator directive):** ACME and recovery-sink/attestation requirements are REMOVED entirely for this topic (no public TLS, no sink upload). Budget gate uses bundle form; `project_purpose=personal-study` skips sink attestation in code. Spend refreshed 2026-10-18: `current=console=1963347 VND`, trial `7d` to `2026-10-25`, forecast `0`.

**Goal:** Produce measured, hash-bound proof for the RAG pipeline/lineage, serial two-model inference optimization, and agent warm-up/startup-cost improvement.

**Architecture:** A fresh budgeted `rubric-evidence` lease runs the real Airflow candidate-index pipeline and DataHub read-back. Inference uses a fixed 2×4×cold/warm factorial, one model at a time with two Ready replicas; the inactive model is forced to zero throughout the other model's factorial. Agent startup compares cold KEDA 0->1 against prewarmed state under fixed revisions and restores normal minimum one.

**Tech Stack:** Airflow, DataHub, Feast, PostgreSQL/pgvector, BGE embeddings, llm-d CPU, agentgateway, KEDA/Agent Substrate, Python benchmarking, Prometheus, Playwright.

## Metadata

| Field | Decision |
|---|---|
| Phase | Evidence lease 1 of 4; execution topic 28 |
| Authoritative source tasks | `04.2_llm_design.md` Tasks 2, 9, 12 |
| Primary rubric cells | `Sheet3!E5`, `Sheet3!E8`, `Sheet3!E9`, `Sheet3!E26` |
| Prerequisites | Topics 22-27 complete; fully suspended state; verified platform/releases/Section 03 |
| Blocked successors | Topics 29-32 |
| Runtime owner | `topic28-rag-benchmark`; fresh `rubric-evidence` lease <=6h |
| Execution class | `GCP-write/measured-evidence` |
| Branch rule | Same branch/common CI commit; serial |

## Global Constraints

- Use `rtk` prefix if installed, else run commands directly. Repo root = current checkout (`<repo-root>`).
- Fixed hashes: Section 03 `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`; EDAI2 `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`; `tmp/rubic-check/Coursework Tracking (Public).xlsx` `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- Do not create/switch branch/worktree, stage, or commit.
- Consume the completed local implementation. If a source/IaC/chart defect appears, capture it, release or suspend any owned runtime, mark this topic `Partial`, and return it to the owning local topic; do not patch implementation during a live cloud lease.
- Start only from suspended pools/no forwarding rule. Acquire a fresh lease only after a redacted `check_budget.py --live-external-preflight` verifies project lifecycle, billing linkage, exact IAM permissions, trial expiry, current spend/forecast, notification target, approved recovery sink, DNS, capacity, and context. Missing external source, model cache, index source, or permission is a safe stop.
- Require `EDAI2_GKE_KUBECONFIG=tmp/edai2-gcp/kubeconfig` and `EDAI2_GKE_CONTEXT=gke_${GOOGLE_CLOUD_PROJECT}_us-central1-a_edai2`. Every `kubectl` call includes `--kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT`; every Helm call includes `--kubeconfig $env:EDAI2_GKE_KUBECONFIG --kube-context $env:EDAI2_GKE_CONTEXT`; every script that queries or mutates Kubernetes receives both values. Never use or change the default kubeconfig/current context.
- `EDAI2_TFVARS_PATH` is absolute, resolves exactly to this repository's `tmp/edai2-gcp/coursework.auto.tfvars`, and remains untracked.
- Topic lease TTL <=6h; use the auto-suspend crash fallback.
- RAG source set is exactly 8 files, 9 effective-dated versions, 400-token chunks with 80-token overlap, normalized finite 384-d embeddings, candidate isolation, CAS promotion, and DataHub read-back.
- Factorial constants: two replicas for active model, inactive model exactly zero; cache off/on × load-aware/prefix-aware; five restart-cleared cold trials; 40 ordered warm requests; global concurrency 1; context 4096; max new tokens 128; temperature 0; top-p 1; seed 20260715; same image/weights/SKU/fixture.
- Never overlap primary and comparison factorials. Model A/B one-plus-one belongs to Topic 29.
- CPU generation p95 <=20s. Optimized warm TTFT and cost must not regress and at least one must improve >=5%; report factor effects/interaction.
- Agent prewarm passes only with startup p95 improvement >=20% and cost/100 improvement >=5% without quality/safety regression.
- If the first empirical run misses a numeric gate, permit exactly one bounded tuning retry that may change only cache mode, router choice, or warm-up count within the already locked factorial. Preserve baseline and retry evidence plus the diagnosed change; no model, data, replica, request, seed, concurrency, token, pricing, or threshold change is allowed. A gate still missed after that retry remains `Partial` or `Missing`.
- `Sheet3!E49` remains out of scope; no VM/Ansible.
- Owned screenshots use `1600x1000`, viewport/non-element crop, stable fully visible selectors, temporary PNG/signature/decode/full-load/atomic replace, complete manifest/hash/machine link/proves-does-not fields, original-resolution inspection, and rejection of blank/clipped/loading/login/home/error/stale/secret/PII.

## Read-Only Planning Refresh

1. `rtk git status --short --branch`
   - Expected: same branch/common CI revision and request-scoped state.
2. `rtk python -c "import hashlib; p=['tmp/edai2-plan/03_data_generator_improvement.md','tmp/edai2-plan/04.2_llm_design.md','tmp/rubic-check/Coursework Tracking (Public).xlsx']; print([hashlib.sha256(open(x,'rb').read()).hexdigest() for x in p])"`
   - Expected: fixed hashes.
3. `rtk rg -n "Status|suspended|Handoff" tmp/edai2-plan/execution-v1/gcp/27-observability-https-jenkins-evidence.md`
   - Expected: prior lease released, pools zero, no forwarding rule.
4. `rtk kubectl --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT cluster-info`
   - Expected: the dedicated kubeconfig resolves the approved GKE API; mismatch or failure is a safe stop.
5. `rtk uv run pytest tests/contract/llm/test_section03_contract.py tests/unit/llm/test_indexing.py tests/unit/llm/test_inference.py -q`
   - Expected: contract and deterministic benchmark fixtures pass locally.

## Scope

- Acquire a fresh <=6h lease.
- Run/promote the real RAG candidate index and verify DataHub lineage.
- Capture Airflow graph and DataHub lineage.
- Run serial fixed inference factorial with inactive model zero.
- Run agent cold/prewarmed startup matrix and restore KEDA min one.
- Produce machine evidence, suspend, and release.

## Non-Goals

- No A/B experiments, notebook execution, mutation/coverage/load tests, or A/B screenshot.
- No job rebuild, registry republish, documentation finalization, or persistent ingress.

## Exact File Map

| Role | Exact paths |
|---|---|
| Read | `data/knowledge/ecommerce/returns.md`, `data/knowledge/ecommerce/shipping.md`, `data/knowledge/ecommerce/cancellation.md`, `data/knowledge/ecommerce/payments.md` |
| Read | `data/knowledge/ecommerce/promotions.md`, `data/knowledge/ecommerce/warranties.md`, `data/knowledge/ecommerce/privacy.md`, `data/knowledge/ecommerce/marketplace_support.md` |
| Read | `configs/llm/models.yaml`, `configs/llm/warmup_prompts.json`, `configs/llm/benchmark_requests.json` |
| Read | `src/vina_bim_shop/orchestration/rag_index_pipeline.py`, `infra/orchestration/airflow/dags/rag_index_pipeline.py`, `infra/governance/recipes/edai2_rag.yml` |
| Execute | `scripts/llm/build_index.py`, `scripts/llm/benchmark_inference.py` |
| Execute | `scripts/gke/manage_profile.py`, `scripts/gke/check_budget.py`, `scripts/qa/capture_edai2_evidence.py` |
| Read external/untracked | `tmp/edai2-gcp/kubeconfig` |
| Consume | `evidence/04_2_llm_design/gke/platform_install.json`, `evidence/04_2_llm_design/cicd/jobs.json` |
| Generate immutable gate evidence | `evidence/04_2_llm_design/gke/gcp_preflight_topic28.json`, `evidence/04_2_llm_design/gke/cost_forecast_topic28.json` |
| Update append-only | `evidence/04_2_llm_design/gke/usage_ledger.json` |
| Generate | `evidence/04_2_llm_design/rag/index_run.json` |
| Generate | `evidence/04_2_llm_design/inference/benchmark.json` |
| Generate only for the single permitted retry | `evidence/04_2_llm_design/inference/benchmark_retry.json` |
| Generate | `evidence/04_2_llm_design/inference/cost_comparison.json` |
| Generate | `evidence/04_2_llm_design/inference/agent_startup.json` |
| Screenshot owner | `evidence/04_2_llm_design/screenshots/airflow_rag_graph.png` |
| Screenshot owner | `evidence/04_2_llm_design/screenshots/datahub_rag_lineage.png` |
| Update through capture CLI | `evidence/04_2_llm_design/screenshots/ui_manifest.json` |

## Interfaces, Data Flow, and Failure Modes

Eight trusted files -> parse versions -> chunk -> embed -> pgvector candidate -> Feast view -> candidate lineage -> 60-case gate -> CAS active alias -> active lineage/read-back.

Pinned cache generations -> active model two replicas/inactive zero -> fixed factorial samples -> per-factor/interaction analysis -> cost calculation.

WorkerPool min zero -> pending-chat Prometheus signal -> cold scale 0->1; prewarmed min one -> 3 agents × 20 sessions × 2 arms -> startup/cost/quality comparison -> restore min one.

Failure modes: RAG validation/lineage failure leaves old alias active; inactive model nonzero invalidates factorial cell; wrong replica count/revision/fixture invalidates measurements; missed performance gate is not relabeled; KEDA minimum not restored blocks cleanup.

## Ordered Test-First Execution Tasks

### Task 1: Gate cost, capacity, and fresh lease

- [ ] Run `rtk uv run python scripts/gke/check_budget.py --project $env:GOOGLE_CLOUD_PROJECT --billing-account-env GOOGLE_BILLING_ACCOUNT --budget-notification-target-env EDAI2_BUDGET_NOTIFICATION_TARGET --recovery-sink-env EDAI2_VAULT_RECOVERY_SINK --recovery-sink-attestation $env:EDAI2_RECOVERY_SINK_ATTESTATION --required-permissions configs/gke/required_permissions.json --dns-probes acme-staging-v02.api.letsencrypt.org,huggingface.co,storage.googleapis.com --live-external-preflight --preflight-output evidence/04_2_llm_design/gke/gcp_preflight_topic28.json --trial-expires-at $env:EDAI2_TRIAL_EXPIRES_AT --current-spend-usd $env:EDAI2_CURRENT_SPEND_USD --spend-observed-at $env:EDAI2_SPEND_OBSERVED_AT --usage-ledger evidence/04_2_llm_design/gke/usage_ledger.json --envelope configs/gke/cost_envelope.yaml --requested-profile rubric-evidence --requested-ttl 6h --output evidence/04_2_llm_design/gke/cost_forecast_topic28.json`.
  - Expected: fresh live project/billing/IAM/notification/recovery-sink/DNS/trial/spend/capacity gate passes with redacted output and available budget covers the worst-case lease.
- [ ] Run `rtk uv run python scripts/gke/manage_profile.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT rubric-evidence --ttl 6h --acquire-session-lease --owner topic28-rag-benchmark --commit-sha $env:EDAI2_COMMIT_SHA`.
  - Expected: fresh sole lease, exact commit, platform restored, ingress private unless capture route is explicitly enabled.

### Task 2: Run RAG DAG and lineage read-back

- [ ] Run `rtk powershell -NoProfile -Command 'if ($env:EDAI2_COMMIT_SHA -cnotmatch "^[0-9a-f]{40}$") { exit 28 }; $expected="canonical-evidence-" + $env:EDAI2_COMMIT_SHA; if ($env:EDAI2_INDEX_VERSION -cne $expected) { exit 29 }; "CANONICAL_INDEX_ID_GATE=PASS"'`.
  - Expected: exact lowercase identity `canonical-evidence-${EDAI2_COMMIT_SHA}` passes; `ci-bootstrap-*`, `test_idx_001`, abbreviated/uppercase commits, and every other index ID fail before the DAG runs.
- [ ] Run `rtk uv run python scripts/llm/build_index.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --trigger-airflow --dag-id rag_index_pipeline --source-root data/knowledge/ecommerce --index-version $env:EDAI2_INDEX_VERSION --index-purpose canonical-evidence --reject-index-purpose ci-bootstrap --reject-index-version-prefix ci-bootstrap- --reject-index-version test_idx_001 --reject-bootstrap-artifact-reuse --bootstrap-evidence evidence/04_2_llm_design/cicd/jobs.json --wait --promote-if-gates --verify-datahub --output evidence/04_2_llm_design/rag/index_run.json`.
  - Expected: exactly 8 files/9 versions, valid chunks/embeddings, 60-case gate, CAS promotion, source->version->chunk/embedding->candidate->active->Feast/API lineage and DataHub response hashes. Before promotion, the tool rejects every `ci-bootstrap-*` or `test_idx_001` identity and rejects any candidate whose artifact/content identity reuses Topic 25's bootstrap output; bootstrap evidence is never accepted as `Sheet3!E8:E9` proof.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --platform-inventory evidence/04_2_llm_design/gke/platform_install.json --private-endpoint-key airflow_web --loopback-only --tunnel-ttl 10m --capture airflow-rag-graph --viewport 1600x1000 --output evidence/04_2_llm_design/screenshots/airflow_rag_graph.png --manifest evidence/04_2_llm_design/screenshots/ui_manifest.json --machine-evidence evidence/04_2_llm_design/rag/index_run.json --strict`.
  - Expected: contextual Airflow DAG/run/stages image; absent/stale/mismatched inventory fields fail before tunneling, and the exact `127.0.0.1` port-forward child terminates in `finally` while its stable endpoint key/service UID is recorded.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --platform-inventory evidence/04_2_llm_design/gke/platform_install.json --private-endpoint-key datahub_frontend --loopback-only --tunnel-ttl 10m --capture datahub-rag-lineage --viewport 1600x1000 --output evidence/04_2_llm_design/screenshots/datahub_rag_lineage.png --manifest evidence/04_2_llm_design/screenshots/ui_manifest.json --machine-evidence evidence/04_2_llm_design/rag/index_run.json --strict`.
  - Expected: complete lineage URNs/active version are visible; absent/stale/mismatched inventory fields fail before tunneling, and the exact `127.0.0.1` port-forward child terminates in `finally` while its stable endpoint key/service UID is recorded.

### Task 3: Warm endpoints and enforce serial model state

- [ ] Run `rtk uv run python scripts/llm/benchmark_inference.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --phase warmup --models primary comparison --serial-models --active-replicas 2 --inactive-replicas 0 --prompts configs/llm/warmup_prompts.json --global-concurrency 1 --warm-each-endpoint`.
  - Expected: each active model's two endpoints warmed; inactive model remains zero; revision/Ready state recorded.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --verify-model-serial-state --benchmark-root evidence/04_2_llm_design/inference --active-replicas 2 --inactive-replicas 0 --strict`.
  - Expected: no timestamp shows both models nonzero during a factorial.

### Task 4: Run fixed inference factorial

- [ ] Run `rtk uv run python scripts/llm/benchmark_inference.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --models primary comparison --serial-models --replicas 2 --inactive-model-replicas 0 --factorial cache=off,on router=load_aware,prefix_aware --order cache_off+load_aware,cache_on+load_aware,cache_off+prefix_aware,cache_on+prefix_aware --cold-trials 5 --warm-requests 40 --requests-file configs/llm/benchmark_requests.json --global-concurrency 1 --max-new-tokens 128 --temperature 0 --top-p 1 --seed 20260715 --pricing-snapshot evidence/04_2_llm_design/gke/cost_forecast_topic28.json --output evidence/04_2_llm_design/inference/benchmark.json --cost-output evidence/04_2_llm_design/inference/cost_comparison.json`.
  - Expected: 16 complete model/config/thermal cells with samples, metrics/constants/revisions/replicas/cache/route hits and honest gates; inactive model zero for every cell.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --verify-inference-factorial evidence/04_2_llm_design/inference/benchmark.json --cost evidence/04_2_llm_design/inference/cost_comparison.json --strict`.
  - Expected: p95/gain/cost/factor-effect rules pass or produce explicit failed `Sheet3!E5`; no missing sample is synthesized.
- [ ] Only if the preceding empirical gate fails, run once: `rtk uv run python scripts/llm/benchmark_inference.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --bounded-tuning-retry-from evidence/04_2_llm_design/inference/benchmark.json --retry-number 1 --allowed-tuning cache,router,warmup --preserve-baseline --output evidence/04_2_llm_design/inference/benchmark_retry.json --cost-output evidence/04_2_llm_design/inference/cost_comparison.json`.
  - Expected: the tool refuses a second retry or any locked-constant change, records the before/after configuration and diagnosis, and either passes the unchanged gate or leaves `Sheet3!E5` `Partial`/`Missing`.

### Task 5: Measure cold versus prewarmed agent startup

- [ ] Run `rtk uv run python scripts/llm/benchmark_inference.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --agent-startup-matrix cold,prewarmed --agents retrieval drift coordinator --sessions-per-agent 20 --model primary --index-version $env:EDAI2_INDEX_VERSION --worker-cold-min 0 --restore-worker-min 1 --output evidence/04_2_llm_design/inference/agent_startup.json`.
  - Expected: 120 samples, pending-chat 0->1 proof, startup/TTFT/CPU/cost/version/quality/safety fields, honest threshold result, and final WorkerPool one.
- [ ] Run `rtk kubectl --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT -n kagent get scaledobject,hpa,workerpool,pods -o wide`.
  - Expected: desired/current one after restoration.

### Task 6: Verify screenshots, evidence, and suspend

- [ ] Inspect the two owned screenshots at original resolution.
  - Expected: no rejected state and exact run/version selectors fully visible.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --verify-screenshot-topic 28 --expected-count 2 --manifest evidence/04_2_llm_design/screenshots/ui_manifest.json --strict`.
  - Expected: exit 0.
- [ ] Run `rtk uv run python scripts/gke/manage_profile.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT suspended --release-session-lease --owner topic28-rag-benchmark --require-evidence-manifest evidence/04_2_llm_design/inference/benchmark.json`.
  - Expected: both pools zero, ingress disabled, no forwarding rule.
- [ ] Run `rtk git status --short --branch`.
  - Expected: same branch/revision lineage recorded.

## Evidence and Screenshot Ownership

Topic 28 owns `index_run.json`, inference benchmark/cost, agent startup, and two RAG screenshots. It is the sole primary rubric owner for `Sheet3!E5`, `Sheet3!E8`, `Sheet3!E9`, and `Sheet3!E26`.

## Cleanup and Runtime Release

- Restore WorkerPool min one before suspend.
- Force both model Deployments to suspended-profile zero after evidence.
- Remove benchmark/load Jobs and any temporary capture route.
- Release `topic28-rag-benchmark`; verify pools zero/no forwarding rule.

## Rubric Traceability

| Cell | Points | Pass gate |
|---|---:|---|
| `Sheet3!E5` | 2 | complete honest fixed factorial and optimization comparison |
| `Sheet3!E8` | 2 | successful real RAG candidate/promotion pipeline |
| `Sheet3!E9` | 2 | DataHub lineage/contract read-back plus screenshot |
| `Sheet3!E26` | 2 | cold/prewarmed startup and cost improvement plus HA guidance evidence |

## Definition of Done

- [ ] Fresh gate/lease/context/branch and prerequisites pass.
- [ ] RAG and DataHub machine evidence plus two screenshots pass.
- [ ] Factorial constants hold, inactive model is zero, numeric gates are reported truthfully.
- [ ] Agent startup matrix is complete and WorkerPool restored.
- [ ] Owned evidence hashes are durable and images pass original-resolution QA.
- [ ] Runtime is suspended/released with zero pools/no forwarding rule.
- [ ] Final `rtk git status --short --branch` is in the record.

## Completion Record

- **Status:** Partial (2026-10-18 ~16:13Z, dependency order T28 after T26). Readiness still red, zero mutation.
- **Branch / revision:** `feature/implement-edai2`, HEAD `e651a86dfb7d509c28c58fe0116cddd3cf6ea1a5`. No stage/commit/push.
- **Spend / trial:** `2119176 VND` observed `2026-10-18T15:52:10+00:00` (`<24h`). Trial ends `2026-10-25T00:00Z` (~6d left).
- **Command / exit log:** backend `initialized` reused (`16:09:23Z`, age `217s <900s`, rev `e651a86`, no rotation). Gates reused (`ok:true`, spend `2119176`, no archive needed). Lease `topic28-rag-benchmark --lease-file tmp/edai2-gcp/topic28-lease.json` exit 0 (`16:13:17Z`). Units `test_canonical_evidence+test_factorial` 9 passed. Live read-only: `coordinator/drift/retrieval/llmd-primary /1` (0 Ready); `llmd-primary Init:Error 177×` (`cache-init.py` `HTTP 403 Forbidden` downloading model archive); `upload.json` partial (`uploaded:false`, 3 reasons: runs artifact absent, no GCS upload flags, no verified bundle); drift `section03Activation:null` (Job never created, correct — no verified bundle to consume); Airflow/DataHub UP but trigger/auth/XCom undiscovered (needs `--airflow-url/auth-env` + creds, not guessed). No mutation (activation would fail closed with no bundle; factorial needs 2 Ready llmd).
- **Evidence / SHA:** No `rag/index_run.json`, `inference/*` (would fabricate). `upload.json` partial stands (`bundle_id f6d07b09…`, `manifest_sha256 af7189d0…`).
- **Screenshot QA:** `airflow_rag_graph.png`, `datahub_rag_lineage.png` Missing; manifest untouched.
- **Cleanup:** No workload/route/pool/port-forward created. Lease released exit 0 (file absent). Cluster left UP for T27 (private gateway needs UP platform).
- **Limitations:** (1) Section 03 bundle unverified (runs absent, no GCS uploader) → no activation → services `/readyz 503` by design. (2) `llmd` model-cache 403 blocks factorial/startup (needs IAM fix + 2 Ready). (3) Airflow 5-hop discovery pending. Numerics unmeasured (honest Partial).
- **Handoff:** T27/T29 prerequisites NOT met (no index/model hashes). Next: owning-local Section 03 uploader + GCS bundle + llmd IAM fix + Airflow auth discovery, then fresh lease + fresh gates. T27 next per dependency order (private gateway can proceed verify-only on UP platform even while readiness red).

### Execution 2026-10-18 ~15:53-16:00Z — Partial, one lease, readiness still red (spend refreshed)
- **Status:** Partial. Fresh spend + backend + gate + lease; live RAG/factorial/startup still blocked on readiness (no mutation).
- **Branch / revision:** `feature/implement-edai2`, HEAD `e651a86dfb7d509c28c58fe0116cddd3cf6ea1a5` (unstaged, no stage/commit/push).
- **Spend:** `2119176 VND` observed `2026-10-18T15:52:10+00:00` (`<24h`; remaining `₫5,770,674 / ₫7,889,850`, 6d to `2026-10-25`). Trial `~152h` at gate.
- **Command / exit-code log:** backend `initialized` rotated (stale `03:45:44Z` → fresh `ok:true` rev `e651a86` obs `15:52:52Z`, exit 0). Bundle gate archived to `.stale-20261018T1552Z`, fresh `ok:true failures:[]` (wrapper exit 2, files authoritative). Lease `topic28-rag-benchmark --lease-file tmp/edai2-gcp/topic28-lease-r2.json` exit 0 (`15:53:45Z`). Units `canonical+factorial` 9 passed. Live (bounded read-only attempt): `coordinator/drift-agent/retrieval-agent/llmd-primary 0/1`, `comparison 0/0`; coordinator `/healthz 200` + `/readyz 503` (by design); edai2 jobs: no Section 03 import job (`datahub-*` Complete, `edai2-model-prefetch` Failed 11d, `redpanda-configuration` Complete). No manual import (drift release sole activation owner). Airflow trigger not attempted live (needs `--airflow-url/--auth-env` + creds; topic omits them). No mutation.
- **Evidence / SHA-256 log:** `gcp_preflight_topic28.json` SHA `fdd01b96f72ecc9ca982f80bad4b9739a1fd2d7dfda465596899f047e6e3cf42` (`ok:true`); `cost_forecast_topic28.json` SHA `a1408c775d6875fa0c78179441d74bfc51b38b8ba6f37137806e696f537e2efa` (`ok:true`, spend `2119176`). No `rag/index_run.json`, `inference/*` (would fabricate).
- **Screenshot QA:** `airflow_rag_graph.png`, `datahub_rag_lineage.png` Missing; manifest untouched.
- **Cleanup / runtime release:** No workload/route/pool/port-forward created; ingress zero, controller ClusterIP verified at release. Lease `topic28-rag-benchmark` (r2 file) released exit 0. Cluster left UP for T27.
- **Limitations:** Readiness unlock pending (Section 03 activation + canonical index); Airflow 5-hop discovery pending; numerics unmeasured.
- **Handoff:** Topic 29 prerequisites NOT met. Next: fresh lease + fresh gates only after readiness lands.

### Execution 2026-10-18 ~03:49-03:55Z — Partial, one lease, zero live mutations (readiness + Airflow-auth block)
- **Status:** Partial. Lease acquired + fresh gates passed; live RAG/factorial/startup blocked (details below). No job rebuilds, no substitutes.
- **Branch / revision:** `feature/implement-edai2`, HEAD `e651a86dfb7d509c28c58fe0116cddd3cf6ea1a5`. Working tree: Phase A + spend refresh + vault study-only + contract amendments (unstaged, no stage/commit/push).
- **Spend:** `1963347 VND` observed `2026-10-18T03:43:08+00:00` (`<24h`). Trial ends `2026-10-25T00:00Z` (`~164h` left at gate).
- **Command / exit-code log:** backend proof fresh at entry (`03:45:44Z`, `<900s`, no rotation needed). Bundle gate fresh `check_budget --live-external-preflight` wrote `ok:true failures:[]` (wrapper exit 2, files authoritative). Lease `manage_profile rubric-evidence --ttl 6h --acquire-session-lease --owner topic28-rag-benchmark --commit-sha e651a86 --lease-file tmp/edai2-gcp/topic28-lease.json` exit 0 (`03:49:02Z`). Units: `test_canonical_evidence+test_factorial` 9 passed. Live checks (bounded attempt, read-only): `llmd-primary 0/1`, `llmd-comparison 0/0` — factorial requires 2 Ready active + inactive zero, unrunnable; Airflow DAG trigger requires `--airflow-url/--airflow-auth-env/--dag-result` (topic omits them; no operator Airflow creds in-repo) — not attempted live (would fail closed or guess secrets). No mutation performed.
- **Evidence / SHA-256 log:** `gcp_preflight_topic28.json` SHA `fd656388613342661bbc5ecb41bc6d6a58832e073eef9ddcada65715ebcb94e6` (`ok:true`); `cost_forecast_topic28.json` SHA `620c7959e62088125f5ff0171d04b358011f9ac5e559eb78d25cfaced2aad33e` (`ok:true`). No `rag/index_run.json`, `inference/benchmark.json`, `cost_comparison.json`, `agent_startup.json` (live preconditions absent; generating them would fabricate).
- **Screenshot QA:** `airflow_rag_graph.png`, `datahub_rag_lineage.png` Missing; manifest untouched.
- **Cleanup / runtime release:** No workload/route/pool/port-forward created. Lease `topic28-rag-benchmark` released exit 0 (`lease_released:true`, file absent). Cluster left UP for T29.
- **Limitations:** (1) Readiness unlock pending (Section 03 activation + canonical index via drift release; sole activation owner, no manual import). (2) Airflow REST auth/trigger + XCom + DataHub verify still undiscovered end-to-end (5 hops). (3) Numeric gates unmeasured (honest Partial).
- **Handoff:** Topic 29 prerequisites NOT met (no index/model/config hashes). Owning-local readiness + Airflow-auth fixes first, then fresh ≤6h lease with fresh gates.

### Execution 2026-10-18 ~04:10Z — Partial, no lease (prerequisites unmet, foreknown churn)
- **Status:** Partial. No lease acquired; zero cloud mutation. Topic 27 closed Partial (no HTTPS routes, no Jenkins jobs); services `/readyz` 503 with pods Running/False and `llmd-primary` Pending; BGE model absent from workstation HF cache (Airflow REST auth/API, XCom readback, and DataHub verify unverified end-to-end — each a discovery hole under a single 6h lease with a one-retry rule).
- **Command / exit-code log:** Read-only cluster reads only (`cluster-info`, nodes, pods, endpoints, logs). Phase A CLIs verified locally (`--help` surfaces; unit GREEN incl. canonical-identity, airflow-evidence, factorial, startup-matrix). No `check_budget`/lease/mutation commands run for this topic.
- **Evidence / SHA-256 log:** No `gcp_preflight_topic28.json`, `cost_forecast_topic28.json`, `rag/index_run.json`, `inference/*`. Model cache (GCS) confirmed to hold embedding revision `5c38ec7c…` for a future leased run.
- **Screenshot QA:** `airflow_rag_graph.png`, `datahub_rag_lineage.png` Missing; manifest untouched.
- **Cleanup / runtime release:** No lease ever held by this topic; no pools/routes touched.
- **Limitations:** Readiness unlock (Section 03 activation + canonical index) still pending; Airflow trigger/auth contract still to prove.
- **Handoff:** Topic 29 prerequisites NOT met (no index/model/config hashes). Owning-local + readiness fixes first, then fresh ≤6h lease with fresh gates.

### Execution 2026-10-18 ~00:20Z — Partial, zero mutation (no lease acquired)
- **Status:** Partial. Prerequisites unmet (Topic 27 Partial, services `Ready=false`, Section 03 inactive) plus own CLI contracts absent; no lease acquired, no cloud mutation.
- **Command / exit-code log:** `build_index.py --help` → `--index-purpose` allows only `local-bootstrap-sentinel`; no `--trigger-airflow/--dag-id/--promote-if-gates/--verify-datahub` ("without storage writes" stub class). `benchmark_inference.py --help` → only `--phase {warmup,factorial,agent-startup,experiment}` + `--models/--prompts/--requests-file/--global-concurrency/--output`; no `--serial-models/--replicas/--inactive-model-replicas/--factorial/--cold-trials/--warm-requests/--seed/--pricing-snapshot/--cost-output/--bounded-tuning-retry-from/--agent-startup-matrix`. Canonical `canonical-evidence-<sha>` DAG, serial-state verify, 16-cell factorial, and 120-sample startup matrix all uninvokable as written.
- **Evidence / SHA-256 log:** No `gcp_preflight_topic28.json`, `cost_forecast_topic28.json`, `rag/index_run.json`, `inference/{benchmark,cost_comparison,agent_startup}.json`. No `ci-bootstrap` reuse (nothing ran).
- **Screenshot QA:** `airflow_rag_graph.png`, `datahub_rag_lineage.png` Missing; manifest untouched.
- **Cleanup / runtime release:** No lease, no pools touched, WorkerPool min untouched (already 1), cluster UP.
- **Limitations:** Readiness unlock (Section 03 activation + canonical index) still pending owning-local chart fixes (must run with NO lease first per PoC directive).
- **Handoff:** Topic 29 NOT unblocked by this topic (no index/model/config hashes produced). Owning-local fixes needed: Airflow trigger/promote/DataHub read-back path, serial-model factorial with inactive-zero enforcement, cost/pricing snapshot, single bounded-retry path.

### Execution 2026-10-18 ~16:31-16:33Z — Partial, one lease, zero mutation (upload unverified + llmd 403, readiness still red)
- **Status:** Partial. Fresh backend + reused bundle gate + lease + 9 units GREEN; live RAG/factorial/startup blocked on readiness (no mutation, no retry consumed).
- **Branch / revision:** `feature/implement-edai2`, HEAD `e651a86dfb7d509c28c58fe0116cddd3cf6ea1a5`. No stage/commit/push. No branches/worktrees created or switched.
- **Spend:** `2119176 VND` reused (`console=current=2119176.0`, `forecast=0.0`, observed `2026-10-18T15:52:10+00:00`). Trial ends `2026-10-25T00:00:00Z`. No spend re-observation this run (bundle reuse path).
- **Command / exit-code log:** backend proof stale at entry (obs `16:09:23Z`, age `~1306s >900s`, rev `e651a86` match) → archived to `.stale-20261018T1631Z`, `check_budget.py --operator-inputs tmp/edai2-gcp/operator-inputs.json --verify-private-backend initialized` exit 0, fresh obs `16:31:30Z` rev `e651a86` `ok:true`. Bundle gate reused (no archive): `gcp_preflight_topic28.json ok:true failures:[]`, `cost_forecast_topic28.json ok:true console=2119176.0 current=2119176.0`. Lease `manage_profile.py --kubeconfig <repo>/tmp/edai2-gcp/kubeconfig --context edai2-gke rubric-evidence --ttl 6h --acquire-session-lease --owner topic28-rag-benchmark --commit-sha e651a86dfb7d509c28c58fe0116cddd3cf6ea1a5 --lease-file tmp/edai2-gcp/topic28-lease.json` exit 0 (acquired `16:31:35Z`). Units `.venv\Scripts\python -m pytest tests/unit/llm/test_canonical_evidence.py tests/unit/llm/test_factorial.py -q` → 9 passed, exit 0. Live read-only: `kubectl get deploy coordinator drift-agent retrieval-agent llmd-primary` (default ns) → `Error from server (NotFound): deployments.apps "coordinator" not found` (+ same for drift-agent/retrieval-agent/llmd-primary), exit 1 (workloads live in `edai2` ns, not default); `-n edai2` → `coordinator 0/1`, `drift-agent 0/1`, `retrieval-agent 0/1`, `llmd-primary 0/1`, `llmd-comparison 0/0` (both llmd same image `ghcr.io/llm-d/llm-d-cpu:v0.7.0@sha256:f4abcce2…`). `llmd-primary` pod `Init:CrashLoopBackOff` (180 restarts), init `cache-init.py` `urllib.error.HTTPError: HTTP Error 403: Forbidden` in `download_archive`. `upload.json` partial (`uploaded:false`, 3 reasons: runs artifact absent, no GCS upload flags, no verified bundle). `helm get values edai2-drift-agent -n default` → `section03Activation: null` (release in default ns per `helm list`; `-n edai2` → `Error: release: not found`). No `helm upgrade`, no index/factorial/capture invocations (preconditions fail closed).
- **Evidence / SHA:** `gcp_preflight_topic28.json` SHA `fdd01b96f72ecc9ca982f80bad4b9739a1fd2d7dfda465596899f047e6e3cf42` (`ok:true`, reused). `cost_forecast_topic28.json` SHA `a1408c775d6875fa0c78179441d74bfc51b38b8ba6f37137806e696f537e2efa` (`ok:true`, spend `2119176`, reused). `upload.json` stands partial (`bundle_id f6d07b09…`, `manifest_sha256 af7189d0…`, `uploaded:false`). No `rag/index_run.json`, no `inference/*` (would fabricate). No gate JSONs written beyond the refreshed backend proof (tool-written); no evidence invented.
- **Screenshot QA:** `airflow_rag_graph.png`, `datahub_rag_lineage.png` Missing (only-on-success path not reached); `ui_manifest.json` untouched.
- **Cleanup:** No workload/route/pool/port-forward created; no manifest routes to disable (none). Lease `topic28-rag-benchmark` (`--lease-file tmp/edai2-gcp/topic28-lease.json`) released exit 0 (`{"lease_released": true}`), file absent (`Test-Path False`). Cluster left UP (no suspend; release path touches no pools).
- **Limitations:** (1) Section 03 bundle unverified → drift activation correctly unattempted (sole owner has no verified bundle; `section03Activation:null`). (2) `llmd-primary 0/1` + `comparison 0/0` with init 403 → factorial needs 2 Ready active + inactive 0 with same image/weights, unrunnable; startup matrix likewise unrunnable. (3) `operator-inputs.json` carries no `airflow-url`/`auth-env` keys (only `billing_console_url` matches url/auth/air substrings) → canonical index `Missing` path, no shim/creds guessed.
- **Handoff:** Drift activation attempted N. Index attempted N. Factorial attempted N (startup likewise N). Captures N. Lease released true. T29 prerequisites NOT met (no index/model hashes). Next: owning-local Section 03 uploader + verified GCS bundle, llmd cache 403/IAM fix to 2 Ready, Airflow URL/auth discovery via documented operator inputs — then fresh lease + fresh gates.

### Execution 2026-10-18 ~16:56-16:58Z — Partial, one lease, zero mutation (backend rotated, upload unverified + llmd 403)
- **Status:** Partial. Backend rotated + bundle gate reused + lease + 11 units GREEN; live RAG/factorial/startup blocked on readiness (no mutation, no retry consumed). Authoritative for Task 2 (subagent-driven run): this entry; prior entries are inline-run history.
- **Branch / revision:** `feature/implement-edai2`, HEAD `e651a86dfb7d509c28c58fe0116cddd3cf6ea1a5`. No stage/commit/push. No branches/worktrees created or switched. No staging/commit/push/PR.
- **Spend:** `2119176 VND` reused (`console=current=2119176.0`, `forecast=0.0`, observed `2026-10-18T15:52:10+00:00`). Trial ends `2026-10-25T00:00:00Z` (~6d left). No spend re-observation this run (bundle reuse path).
- **Command / exit-code log (FULL):** (1) Backend age check `python -c "import json,datetime; p=json.load(open('tmp/edai2-gcp/terraform-data/topic22-backend-initialized-proof.json')); ..."` → obs `2026-10-18T16:31:30.624320Z` rev `e651a86dfb7d509c28c58fe0116cddd3cf6ea1a5` age `1519s >900s` → rotate. (2) `Move-Item -Path tmp/edai2-gcp/terraform-data/topic22-backend-initialized-proof.json -Destination tmp/edai2-gcp/terraform-data/topic22-backend-initialized-proof.json.stale-20261018T1656Z` → moved. (3) `.venv\Scripts\python -m scripts.gke.check_budget --operator-inputs tmp/edai2-gcp/operator-inputs.json --verify-private-backend initialized` exit 0, fresh `observed_at_utc 2026-10-18T16:57:13.185596Z` rev `e651a86` `ok:true phase:initialized`. (4) Bundle gate verify `python -c "import json; ..."` → `gcp_preflight_topic28.json ok:true failures:[]`, `cost_forecast_topic28.json ok:true console=2119176.0 current=2119176.0` → reuse true, no archive, no `bundle-form --required-permissions` run. (5) Lease `.venv\Scripts\python scripts/gke/manage_profile.py --kubeconfig 'C:\Users\hhoangdo\Documents\Personal Projects\FSDS\ecom-data-platform-submission\tmp\edai2-gcp\kubeconfig' --context edai2-gke rubric-evidence --ttl 6h --acquire-session-lease --owner topic28-rag-benchmark --commit-sha e651a86dfb7d509c28c58fe0116cddd3cf6ea1a5 --lease-file tmp/edai2-gcp/topic28-lease.json` exit 0, `{"lease_acquired": true, "acquired_at_utc": "2026-10-18T16:57:22.262004+00:00"}`. (6) Units `.venv\Scripts\python -m pytest tests/unit/llm/test_canonical_evidence.py tests/unit/llm/test_factorial.py -q` → `11 passed in 1.50s` exit 0. (7) Live read-only `kubectl --kubeconfig 'C:\Users\hhoangdo\Documents\Personal Projects\FSDS\ecom-data-platform-submission\tmp\edai2-gcp\kubeconfig' --context edai2-gke -n edai2 get deploy coordinator drift-agent retrieval-agent llmd-primary llmd-comparison` exit 0 → `coordinator 0/1`, `drift-agent 0/1`, `retrieval-agent 0/1`, `llmd-primary 0/1`, `llmd-comparison 0/0` (28h/4d3h age). (8) `kubectl --kubeconfig '<abs>/tmp/edai2-gcp/kubeconfig' --context edai2-gke -n edai2 logs deploy/llmd-primary -c cache-init --tail=20` → `urllib.error.HTTPError: HTTP Error 403: Forbidden` in `download_archive` (`/opt/edai2/cache-init.py:135`); pod `llmd-primary-6b8d87f7c9-nvl59 0/1 Init:CrashLoopBackOff 185 restarts`. (9) Read `evidence/04_2_llm_design/section03/upload.json` → `partial uploaded:false bundle_id f6d07b09a12107b19a4bfe45a7bda6f87ab9356021a90e2ec6f02f63b5602640 manifest_sha256 af7189d00a187e539bb777d89111d2860a97822f34c2c911adc3eadf6166f8ad` 3 reasons (runs artifact absent; `load_section03.py` has no GCS upload flags `--gcs-prefix/--upload-only/--verify-upload` absent per Task-1 fail-closed guard; no verified bundle). (10) `helm --kubeconfig '<abs>/tmp/edai2-gcp/kubeconfig' --kube-context edai2-gke get values edai2-drift-agent -n default` exit 0 → `section03Activation: null`. No `helm upgrade` (upload unverified → sole owner has no bundle; `verify_namespace` smoke guard would precede any mutation — no mutation attempted). (11) Index guard: `operator-inputs.json` keys contain no `airflow-url`/`auth-env` (only `billing_console_url` matches url/auth/air); `scripts/llm/build_index.py --help` confirms `--trigger-airflow` surface; attempt `.venv\Scripts\python scripts/llm/build_index.py --kubeconfig '<abs>/tmp/edai2-gcp/kubeconfig' --context edai2-gke --trigger-airflow --dag-id rag_index_pipeline --source-root data/knowledge/ecommerce --index-version canonical-evidence-e651a86dfb7d509c28c58fe0116cddd3cf6ea1a5 --index-purpose canonical-evidence ... --wait --promote-if-gates --verify-datahub --output evidence/04_2_llm_design/rag/index_run.json` (without `--commit-sha/--airflow-url`) → `build_index.py: error: --trigger-airflow requires --commit-sha` exit 2; retry with `--commit-sha e651a86dfb7d509c28c58fe0116cddd3cf6ea1a5` (still no `--airflow-url`) → `build_index.py: error: --trigger-airflow requires --airflow-url` exit 2. Task-1 guard `build_index.py:78-79` requires explicit `https:// --airflow-url` (http/localhost guesses forbidden) + `--airflow-auth-env/--dag-result` — never guessed, no shim, index `Missing`. (12) Factorial/startup not invoked: requires active 2 Ready + inactive 0; observed `llmd-primary 0/1` + `comparison 0/0` → Partial, no synthesis, one-retry budget unconsumed. (13) Jobs `kubectl --kubeconfig '<abs>/tmp/edai2-gcp/kubeconfig' --context edai2-gke -n edai2 get jobs` → `datahub-* Complete`, `edai2-model-prefetch Failed 11d`, `redpanda-configuration Complete`; no Section 03 import Job (correct).
- **Evidence / SHA:** `gcp_preflight_topic28.json` SHA `fdd01b96f72ecc9ca982f80bad4b9739a1fd2d7dfda465596899f047e6e3cf42` (`ok:true`, reused). `cost_forecast_topic28.json` SHA `a1408c775d6875fa0c78179441d74bfc51b38b8ba6f37137806e696f537e2efa` (`ok:true`, spend `2119176`, reused). Backend proof refreshed (tool-written `initialized ok:true`). `upload.json` stands partial (`bundle_id f6d07b09…`, `manifest_sha256 af7189d0…`, `uploaded:false`). No `rag/index_run.json`, no `inference/*` (would fabricate). No gate JSONs rewritten beyond backend proof; no evidence invented.
- **Screenshot QA:** `airflow_rag_graph.png`, `datahub_rag_lineage.png` Missing (only-on-success path not reached); `ui_manifest.json` absent (glob `**/ui_manifest.json` → no files found), untouched.
- **Cleanup:** No workload/route/pool/port-forward created; no manifest routes to disable (none found). Lease release `.venv\Scripts\python scripts/gke/manage_profile.py --kubeconfig 'C:\Users\hhoangdo\Documents\Personal Projects\FSDS\ecom-data-platform-submission\tmp\edai2-gcp\kubeconfig' --context edai2-gke suspended --release-session-lease --owner topic28-rag-benchmark --lease-file tmp/edai2-gcp/topic28-lease.json` exit 0 (`{"lease_released": true}`), file absent (`Test-Path False`). Cluster left UP (no suspend; release touches no pools).
- **Limitations:** (1) Section 03 bundle unverified → drift activation correctly unattempted. (2) `llmd-primary 0/1` init 403 → factorial/startup unrunnable (needs 2 Ready active + 0 inactive, same image/weights). (3) Airflow URL/auth undiscovered in documented inputs → canonical index `Missing`. Numerics unmeasured (honest Partial).
- **Handoff:** Drift activation attempted N (upload partial → fail-closed, no `helm upgrade`). Index attempted Y (guarded trigger, exact errors above) → outcome Missing, no `index_run.json`. Factorial attempted N (0/1 + 0/0 ≠ 2 Ready/0) + startup N. Captures attempted N → Missing. Lease released true. T29 prerequisites NOT met. Next: owning-local Section 03 uploader + verified GCS bundle, llmd cache 403/IAM fix to 2 Ready, Airflow URL/auth discovery via documented operator inputs — then fresh lease + fresh gates.


## Completion Record - 2026-10-19 final closeout (constraint-relaxed)

- **Status:** Completed with approved exceptions (Section 03 upload + llmd readiness completed; RAG runtime gap remains).
- **Branch / revision:** `feature/implement-edai2`, `a5c2111d46cf8805baee18ba98bfd2df9ec942c5`.
- **Evidence:** `section03/upload.json` -> `uploaded:true`, 15 objects / 1,985,131 bytes, `status:verified`, SHA-256 `024cfe3a971c1383a11dd214d9282112d7149f8556e9d9b333bdd262f48660ef`; GCS prefix `gs://edai2-data-280de6292ec9/section03/f6d07b09.../`; `edai2-retrieval-agent` and `edai2-drift-agent` now carry `iam.gke.io/gcp-service-account` annotations; `llmd-primary` reached `1/1` after the cache-init 403 was fixed.
- **Approved exceptions:** `rag/index_run.json`, `inference/*`, `airflow_rag_graph.png`, and `datahub_rag_lineage.png` were not produced. Airflow has no deployed DAGs; `RagIndexPipeline()` has no candidate store/catalog; `DatahubIndexCatalogAdapter` has no live emit/read ports; `FeastPostgresAdapter` requires Feast/Valkey hooks. E5/E8/E9/E26 remain unproven.
- **Cleanup:** T28 lease released; T31 teardown proves zero nodes/ingress/LB/forwarding/lease.
- **Handoff:** the service runtime, Airflow DAG image, and live DataHub adapter remain a separate implementation project.

## Readiness Addendum - 2026-10-22 (T27 direct runtime)

- **Status:** Completed with approved exceptions (unchanged). This addendum records the runtime readiness that unblocked T27; it does **not** convert the T28 canonical RAG/Airflow/DataHub/factorial/startup cells.
- **What changed:** `create_retrieval_service_from_environment` now builds a real `FeastPostgresAdapter` + `PinnedBgeEmbedder(model_path=...)` and fails closed without both; the drift and chat surfaces build real dependencies from the same environment; the direct coordinator performs a real retrieval HTTP call plus a real `llmd-primary` generation and returns a cited answer. Retrieval `/readyz` is 200, the service images are at `4f36cb1`, and a one-query smoke index (`t27-smoke-b119673b8a56`, 17 chunks) is persisted and active.
- **Remaining T28 exceptions:** the canonical 60-case gate/index, Airflow DAG, live DataHub emit/read-back, factorial/startup matrix, inference benchmark numerics, and the two RAG images. The T27 smoke index is explicitly **not** canonical evidence.
- **Evidence:** `rag/t27_smoke_index.json` SHA-256 `DC4F05C83429FAE142FAE5D28FDE75DE41B0E12F5EFA66A4EBC65E4560E896ED`; `rag/t27_smoke_validation.json` SHA-256 `220916CA2E8B459C9ABE0F07024929E8C903F251C3E0FA1AA294D396190CEA76`; `observability/topic27_live.json` SHA-256 `C822CACE63E2F960716F20573D0E967D2AC384F73F13EDEA616DA00C3B6F8F69`.
- **Handoff:** T28 stays Completed-with-approved-exceptions; no T28 status change, and E5/E8/E9/E26 remain unproven.
