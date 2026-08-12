# Topic 26: KEDA, Agent HA, Registry, and Rollback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the three logical sandboxed agents are independently usable, registered, securely routed, genuinely multi-instance under KEDA, and recoverable across Helm, model, and index rollback paths.

**Architecture:** Topic 26 reuses Topic 25's handed-off `evidence-run` lease and immutable releases. KEDA scales three application Deployments and one Agent Substrate WorkerPool from one to two; overlapping sessions must land on distinct actor and pod identities. Agent Registry publication/read-back is digest-bound, and rollback tests restore exact prior Helm, ModelConfig, and active-index revisions.

**Tech Stack:** GKE, KEDA, Prometheus, kagent SandboxAgent, Agent Substrate/gVisor, agentgateway, Agent Registry/arctl, Helm, llm-d, PostgreSQL active-index alias, Playwright.

## Metadata

| Field | Decision |
|---|---|
| Phase | Live agent/deployment evidence; execution topic 26 |
| Authoritative source tasks | `04.2_llm_design.md` Task 9 |
| Primary rubric cells | `Sheet3!E7`, `Sheet3!E13:E15`, `Sheet3!E19:E21`, `Sheet3!E24` |
| Prerequisites | Topic 25 six SUCCESS records and `evidence-run` lease handoff |
| Blocked successors | Topic 27 and all later evidence topics |
| Runtime owner | Reused `evidence-run`; no second lease; remaining TTL must cover work and be <=6h total |
| Execution class | `GCP-write/live-evidence` |
| Branch rule | Same branch/common CI commit; serial execution |

## Global Constraints

- Read `C:\Users\oou1hc\.codex\RTK.md`; prefix shell commands with `rtk`.
- Fixed hashes: Section 03 `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`; EDAI2 `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`; `tmp/rubic-check/Coursework Tracking (Public).xlsx` `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- No branch/worktree/stage/commit change; current revision must match six CI records.
- Consume the completed local implementation. If a source/IaC/chart defect appears, capture it, release or suspend any owned runtime, mark this topic `Partial`, and return it to the owning local topic; do not patch implementation during a live cloud lease.
- Require explicit GKE context and a fresh redacted `check_budget.py --live-external-preflight` result. Missing project lifecycle, billing linkage, exact IAM permission, trial/spend/notification/recovery-sink/DNS status, registry auth, Section 03, or another external input is a safe stop.
- Require `EDAI2_GKE_KUBECONFIG=tmp/edai2-gcp/kubeconfig` and `EDAI2_GKE_CONTEXT=gke_${GOOGLE_CLOUD_PROJECT}_us-central1-a_edai2`. Every `kubectl` call includes `--kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT`; every Helm call includes `--kubeconfig $env:EDAI2_GKE_KUBECONFIG --kube-context $env:EDAI2_GKE_CONTEXT`; every script that queries or mutates Kubernetes receives both values. Never use or change the default kubeconfig/current context.
- `EDAI2_TFVARS_PATH` is absolute, resolves exactly to this repository's `tmp/edai2-gcp/coursework.auto.tfvars`, and remains untracked.
- Do not acquire a second lease. Verify `evidence-run` owner, commit, expiry, and refcount zero before live work.
- KEDA bounds are min 1/max 2 normally, threshold 1, polling 15s, cooldown 60s. WorkerPool scale target is exact `ate.dev/v1alpha1`, `WorkerPool`, `edai2-agents`.
- Prove two simultaneous instances per logical agent with distinct session/actor IDs and WorkerPool pod UIDs; two idle replicas alone do not pass.
- Gateway credential matrices remain least privilege; raw messages/customer IDs do not enter metrics, screenshots, or evidence.
- One bounded retry only; truthful partial and safe handoff/suspend after repeated failure.
- `Sheet3!E49` remains out of scope.
- Owned UI screenshots are `agentregistry_agents.png` and `keda_scale.png` only. They are `1600x1000`, non-element-cropped, stable/fully visible, temporary-PNG/signature/decode/full-load/atomic-replace, manifest/hash/machine-linked, and inspected at original resolution.

## Read-Only Planning Refresh

1. `rtk git status --short --branch`
   - Expected: same CI branch/revision.
2. `rtk python -c "import hashlib; p=['tmp/edai2-plan/03_data_generator_improvement.md','tmp/edai2-plan/04.2_llm_design.md','tmp/rubic-check/Coursework Tracking (Public).xlsx']; print([hashlib.sha256(open(x,'rb').read()).hexdigest() for x in p])"`
   - Expected: fixed hashes.
3. `rtk rg -n "Status|SUCCESS|evidence-run|Handoff" tmp/edai2-plan/execution-v1/gcp/25-jenkins-six-workload-deploy.md`
   - Expected: six SUCCESS records and lease handoff.
4. `rtk kubectl --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT cluster-info`
   - Expected: the dedicated kubeconfig resolves the approved GKE API; mismatch or failure is a safe stop.
5. `rtk uv run python scripts/gke/manage_profile.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT lease-status --owner evidence-run --strict`
   - Expected: exact commit, zero child refs, valid expiry, enough remaining time; otherwise safely suspend/reacquire only through a revised plan.

## Scope

- Publish/read back the retrieval, drift, and coordinator registry versions.
- Prove KEDA API and WorkerPool scaling plus distinct concurrent actors.
- Exercise specialist/coordinator chats through authorized paths.
- Prove Helm, model, and index rollback/restore.
- Capture two contextual screenshots; Topic 29 owns the three kagent chat images.
- Preserve the handed-off lease for Topic 27 on success.

## Non-Goals

- No new builds or Jenkins job reruns.
- No public ingress or Jenkins/observability screenshots; Topic 27 owns those.
- No factorial benchmarks/A/B final measurements; Topics 28-29.

## Exact File Map

| Role | Exact paths |
|---|---|
| Read | `infra/kagent/edai2/model-configs.yaml`, `infra/kagent/edai2/workerpool-scaledobject.yaml` |
| Read | `infra/agentregistry/edai2/retrieval-agent.yaml`, `infra/agentregistry/edai2/drift-agent.yaml`, `infra/agentregistry/edai2/coordinator-agent.yaml` |
| Read | `infra/helm/edai2/workloads/retrieval.yaml`, `infra/helm/edai2/workloads/drift.yaml`, `infra/helm/edai2/workloads/coordinator.yaml` |
| Execute | `scripts/llm/publish_agents.py`, `scripts/llm/smoke_release.py`, `scripts/llm/build_index.py` |
| Execute | `scripts/gke/manage_profile.py`, `scripts/gke/check_budget.py`, `scripts/qa/capture_edai2_evidence.py` |
| Read external/untracked | `tmp/edai2-gcp/kubeconfig` |
| Consume | `evidence/04_2_llm_design/gke/platform_install.json` |
| Generate immutable gate evidence | `evidence/04_2_llm_design/gke/gcp_preflight_topic26.json`, `evidence/04_2_llm_design/gke/cost_forecast_topic26.json` |
| Update append-only | `evidence/04_2_llm_design/gke/usage_ledger.json` |
| Generate | `evidence/04_2_llm_design/agents/registry.json` |
| Generate | `evidence/04_2_llm_design/agents/chat_smoke.json` |
| Generate | `evidence/04_2_llm_design/gke/keda_ha.json` |
| Generate | `evidence/04_2_llm_design/rollbacks/helm.json`, `evidence/04_2_llm_design/rollbacks/model.json`, `evidence/04_2_llm_design/rollbacks/index.json` |
| Screenshot owner | `evidence/04_2_llm_design/screenshots/agentregistry_agents.png` |
| Screenshot owner | `evidence/04_2_llm_design/screenshots/keda_scale.png` |
| Update through capture CLI | `evidence/04_2_llm_design/screenshots/ui_manifest.json` |

## Interfaces, Data Flow, and Failure Modes

Commit/digest/config/tool/model hashes -> `arctl` publish -> read-back -> registry evidence.

Controlled Prometheus load -> KEDA ScaledObjects -> API Deployments and WorkerPool `/scale` -> two Ready targets -> overlapping sessions -> distinct actor/pod proof -> cooldown to one.

Rollback order: route traffic away -> Helm prior revision -> prior ModelConfig/digest -> prior active index alias -> smoke/evaluation -> restore current good revision.

Failure modes: registry read-back mismatch; unsupported registry rollback; KEDA metric stale; replicas scale but actors share one pod; actor/session IDs absent; credential denial on legal path or success on illegal path; prior revision unavailable; rollback smoke fails. Each produces a failed machine record and `Partial`/`Missing` cell, never a coerced pass.

## Ordered Test-First Execution Tasks

### Task 1: Verify live prerequisites and routing contracts

- [ ] Run `rtk uv run python scripts/gke/check_budget.py --project $env:GOOGLE_CLOUD_PROJECT --billing-account-env GOOGLE_BILLING_ACCOUNT --budget-notification-target-env EDAI2_BUDGET_NOTIFICATION_TARGET --recovery-sink-env EDAI2_VAULT_RECOVERY_SINK --recovery-sink-attestation $env:EDAI2_RECOVERY_SINK_ATTESTATION --required-permissions configs/gke/required_permissions.json --dns-probes acme-staging-v02.api.letsencrypt.org,huggingface.co,storage.googleapis.com --live-external-preflight --preflight-output evidence/04_2_llm_design/gke/gcp_preflight_topic26.json --trial-expires-at $env:EDAI2_TRIAL_EXPIRES_AT --current-spend-usd $env:EDAI2_CURRENT_SPEND_USD --spend-observed-at $env:EDAI2_SPEND_OBSERVED_AT --usage-ledger evidence/04_2_llm_design/gke/usage_ledger.json --envelope configs/gke/cost_envelope.yaml --requested-profile rubric-evidence --requested-ttl 6h --output evidence/04_2_llm_design/gke/cost_forecast_topic26.json`.
  - Expected: the residual lease and fresh live project/billing/IAM/notification/recovery-sink/DNS/trial/spend/capacity gates pass with redacted output only.
- [ ] Run `rtk uv run pytest tests/integration/llm/test_gke_agents.py tests/contract/llm/test_mcp_contracts.py -q --live-gke --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT`.
  - Expected: exact agent/MCP/gateway schemas and positive/negative credentials pass.

### Task 2: Publish and read back the three logical agents

- [ ] Run `rtk uv run python scripts/llm/publish_agents.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --templates infra/agentregistry/edai2 --commit-sha $env:EDAI2_COMMIT_SHA --publish --read-back --output evidence/04_2_llm_design/agents/registry.json --strict`.
  - Expected: retrieval, drift, and one logical coordinator identity bind digest, framework, provider/model, MCP references, and config hashes; coordinator read-back contains exactly the supplementary variants `v1-primary`, `v2-primary`, and `v1-comparison`, while the registry still has exactly three logical identities and five `SandboxAgent` resources.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --platform-inventory evidence/04_2_llm_design/gke/platform_install.json --private-endpoint-key agentregistry_ui --loopback-only --tunnel-ttl 10m --capture agentregistry-agents --viewport 1600x1000 --output evidence/04_2_llm_design/screenshots/agentregistry_agents.png --manifest evidence/04_2_llm_design/screenshots/ui_manifest.json --machine-evidence evidence/04_2_llm_design/agents/registry.json --strict`.
  - Expected: three logical agents, versions, digest/commit context visible; no generic registry home page. Absent/stale/mismatched inventory fields fail before tunneling, and the exact `127.0.0.1` port-forward child terminates in `finally`.

### Task 3: Prove KEDA and multi-instance HA

- [ ] Run `rtk uv run python scripts/llm/smoke_release.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --keda-ha --agents retrieval,drift,coordinator --api-min 1 --api-max 2 --worker-min 1 --worker-max 2 --threshold-rps 1 --overlapping-sessions 2 --output evidence/04_2_llm_design/gke/keda_ha.json`.
  - Expected: each API and WorkerPool reaches two Ready targets, each agent's overlapping sessions have distinct actor IDs and WorkerPool pod UIDs, then all return to one after cooldown.
- [ ] Run `rtk kubectl --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT -n edai2 get scaledobject,hpa,pods -l edai2.openai.com/evidence=keda -o wide`.
  - Expected: API transition state matches machine evidence.
- [ ] Run `rtk kubectl --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT -n kagent get scaledobject,hpa,workerpool,pods -l edai2.openai.com/evidence=keda -o wide`.
  - Expected: WorkerPool transition and pod identities match.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --platform-inventory evidence/04_2_llm_design/gke/platform_install.json --private-endpoint-key grafana_ui --loopback-only --tunnel-ttl 10m --capture keda-scale --viewport 1600x1000 --output evidence/04_2_llm_design/screenshots/keda_scale.png --manifest evidence/04_2_llm_design/screenshots/ui_manifest.json --machine-evidence evidence/04_2_llm_design/gke/keda_ha.json --strict`.
  - Expected: contextual KEDA/Prometheus/Ready transition with timestamps and replica identities. Absent/stale/mismatched inventory fields fail before tunneling, and the exact `127.0.0.1` port-forward child terminates in `finally`.

### Task 4: Verify the three functional chat paths as machine evidence

- [ ] Run `rtk uv run python scripts/llm/smoke_release.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --agent-chats retrieval,drift,coordinator --registry-evidence evidence/04_2_llm_design/agents/registry.json --output evidence/04_2_llm_design/agents/chat_smoke.json --strict`.
  - Expected: each named agent/version returns a grounded, non-PII response through its authorized tool/routing path. Topic 29 later owns the three contextual chat screenshots.

### Task 5: Prove three rollback classes

- [ ] Run `rtk uv run python scripts/llm/smoke_release.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --inject-helm-failure retrieval --failure-mode bad-readiness --verify-atomic-rollback --restore-current --output evidence/04_2_llm_design/rollbacks/helm.json`.
  - Expected: the retrieval candidate fails its readiness gate; Helm atomically restores the exact prior app plus agent/routing bundle and the restored retrieval `/readyz` and evaluation pass.
- [ ] Run `rtk helm --kubeconfig $env:EDAI2_GKE_KUBECONFIG --kube-context $env:EDAI2_GKE_CONTEXT history retrieval-agent --namespace edai2 --output json`.
  - Expected: the failed revision and immediately prior deployed revision match `rollbacks/helm.json`; the current revision is the restored good one.
- [ ] Run `rtk uv run python scripts/llm/smoke_release.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --verify-readyz retrieval --expected-revision-from evidence/04_2_llm_design/rollbacks/helm.json --strict`.
  - Expected: restored retrieval `/readyz` and its bound digest/config/routing revision pass.
- [ ] Run `rtk uv run python scripts/llm/smoke_release.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --inject-model-failure primary --failure-mode invalid-digest --active-active-replicas 2 --delete-one-healthy-primary-endpoint --verify-modelconfig-rollback --restore-current --output evidence/04_2_llm_design/rollbacks/model.json`.
  - Expected: the invalid primary digest never becomes Ready; deleting one healthy primary endpoint during active-active service still leaves the other serving, then the route returns to the exact prior primary digest/ModelConfig and quality smoke passes before current-state restoration.
- [ ] Run `rtk uv run python scripts/llm/build_index.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --mode candidate --inject-validation-failure --verify-active-unchanged --rollback-to-previous --restore-current --output evidence/04_2_llm_design/rollbacks/index.json`.
  - Expected: failed candidate never mutates active alias; explicit rollback/restore pass retrieval evaluation.

### Task 6: Verify captures and preserve handoff

- [ ] Inspect both owned PNGs at original resolution.
  - Expected: dimensions/context/selectors/redactions are correct and no rejected state appears.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --verify-screenshots agentregistry_agents.png,keda_scale.png --manifest evidence/04_2_llm_design/screenshots/ui_manifest.json --strict`.
  - Expected: exit 0; file hashes match linked machine evidence.
- [ ] Run `rtk uv run python scripts/gke/manage_profile.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT lease-status --owner evidence-run --require-refcount 0 --require-commit $env:EDAI2_COMMIT_SHA --strict`.
  - Expected: the handed-off lease remains unexpired with enough recorded TTL for Topic 27; otherwise execute the documented suspend path instead of handing it off.
- [ ] Run `rtk git status --short --branch`.
  - Expected: same branch/revision lineage and request-scoped changes only.

## Evidence and Screenshot Ownership

Topic 26 is primary owner of exactly `agentregistry_agents.png` and `keda_scale.png`, plus rollback, registry, KEDA, and chat-smoke machine records. Topic 29 owns all three kagent chat screenshots. Topic 31 audits without reassigning ownership.

## Cleanup and Runtime Release

- Restore every KEDA minimum to one and verify current/desired one.
- Restore current good Helm/model/index versions and registry alias.
- Keep `evidence-run` lease/refcount zero for Topic 27 only if remaining TTL is sufficient; otherwise suspend and require Topic 27 to acquire a fresh budgeted lease through a revised Completion Record.
- Remove load-generator pods and temporary route changes.

## Rubric Traceability

| Cells | Points | Topic 26 primary proof |
|---|---:|---|
| `Sheet3!E7` | 2 | Agent Registry release/UI/read-back |
| `Sheet3!E13:E15` | 5 | retrieval agent HA/KEDA, restricted sandbox, registry publication |
| `Sheet3!E19:E21` | 5 | drift agent HA/KEDA, restricted sandbox, registry publication |
| `Sheet3!E24` | 2 | coordinator routing, multiple workers, and KEDA scaling |

Rollback records support Topic 25/27 cells but do not duplicate their primary ownership. Topic 29 owns notebooks/chat UI and `Sheet3!E25`.

## Definition of Done

- [ ] Budget, lease, context, branch, CI commit, and routing tests pass.
- [ ] Registry contains exactly three logical agents with digest/config/tool read-back.
- [ ] Each logical agent proves two simultaneous distinct actors/pods and cooldown.
- [ ] Registry/KEDA screenshots pass strict QA and chat machine evidence passes.
- [ ] Helm/model/index rollback and current-state restoration pass.
- [ ] No job rebuild occurs; lease handoff to Topic 27 is safe.
- [ ] Final `rtk git status --short --branch` is recorded.

## Completion Record

- **Status:** Not started; no live agent/rollback claim.
- **Branch / revision:** Record exact `rtk git status --short --branch`; none recorded.
- **Affected files:** None at plan-authoring time.
- **Command / exit-code log:** No execution commands recorded.
- **Evidence / SHA-256 log:** No registry/KEDA/rollback evidence recorded.
- **Screenshot QA:** Two owned screenshots not captured.
- **Cleanup / runtime release:** No observed lease state.
- **Limitations:** Notebook, benchmark, A/B, observability, and recovery evidence remain later topics.
- **Handoff:** Topic 27 requires restored current versions, the two valid owned capture hashes, and an unexpired zero-refcount `evidence-run` lease.
