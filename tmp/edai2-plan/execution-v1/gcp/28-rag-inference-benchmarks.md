# Topic 28: RAG and Inference Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

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

- Read `C:\Users\oou1hc\.codex\RTK.md`; prefix all shell commands with `rtk`.
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

- **Status:** Not started; no benchmark/RAG cell claim.
- **Branch / revision:** Record exact `rtk git status --short --branch`; none recorded.
- **Affected files:** None at plan-authoring time.
- **Command / exit-code log:** No execution commands recorded.
- **Evidence / SHA-256 log:** No RAG/benchmark/startup evidence recorded.
- **Screenshot QA:** Two owned screenshots not captured.
- **Cleanup / runtime release:** No lease held by this plan artifact.
- **Limitations:** A failed numeric gate remains an honest lower score and must be handed to Topic 32.
- **Handoff:** Topic 29 starts only after suspended state and receives active index/model/config hashes and truthful gate results.
