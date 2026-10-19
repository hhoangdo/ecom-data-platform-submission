# Topic 26: KEDA, Agent HA, Registry, and Rollback Implementation Plan

> **For any agent (Codex / opencode / Claude / etc):** Work task-by-task in one session. Steps use checkbox (`- [ ]`) tracking. Auto-run without asking; only stop on safe-stop gates below.

> **Study-only simplified run (first iteration, overrides strict gates below):**
> - Repo root = current checkout (`<repo-root>`). Use `rtk` prefix if installed, else run commands directly.
> - Auto-run; no mid-run approvals. Only safe stops: budget/lease/commit mismatch, wrong context, missing registry inputs. Reuse handed-off lease if TTL remains, else fresh lease — record which.
> - Happy-path first: registry publish/read-back + KEDA 1->2->1 + one Helm rollback + chat smoke wins. Distinct actor/pod-UID overlap proof, model/index rollback, strict cooldown timing may stay `Partial`.
> - Screenshots: viewport PNG + SHA + machine link + eyeball check is enough. Skip temp-PNG/signature/decode/atomic + proves/does-not prose for now.
> - Study-mode relaxation v1 (study-first, single-agent): plan-doc SHA pins and manifest-byte equality are LOG-ONLY — record computed vs listed values, never block. Image remote-digest equality stays HARD.
> - Safety gates stay HARD: live budget preflight, exact kubeconfig/context, capacity ceilings. Numeric/forensic gates are record-and-continue `Partial`, one bounded retry max. No mid-run approvals.
> - PoC-first sprint (trial ends 2026-10-25): demo win = registry publish/read-back + KEDA 1->2->1 + one Helm rollback + chat smoke where possible. Actor/pod-UID overlap proof, model/index rollback, strict cooldown timing stay `Partial`. Services may expose zero ready endpoints (readiness needs Topic 28) — chats then degrade to `Partial`; do not burn lease retrying. One lease, time-box, suspend pools-zero after, log spend/remaining/trial-hours.

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

- Use `rtk` prefix if installed, else run commands directly. Repo root = current checkout (`<repo-root>`).
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

- **Status:** Partial (2026-10-17 ~15:45Z, continuation run). Safe-stop after gate pass + read-only proof. PoC demo-win NOT landed: registry publish, KEDA 1->2->1, Helm rollback, chat smoke all blocked at implementation level (stubs + zero agent resources + zero Ready endpoints). No live workload mutation performed; cluster + lease preserved.
- **Branch / revision:** `feature/implement-edai2`, HEAD `071a9661f713f7a97b698de0964351d31e870d46` (CI images `7233469...`; HEAD drift is docs-only, LOG-ONLY per study relaxation). `git ls-files --stage` hash `4eee0113aa99c6f1fa268c2a40a451d86e4bdb8b1647897d3822b01d6eaf17e0` unchanged (no stage/commit/push). Working tree: `M` topic file (this record) + `M evidence/.../usage_ledger.json` (gate append-only) + 2 untracked gate files.
- **Spend (snapshot-refreshed):** prior bundle `1676924 VND` observed `2026-10-16T05:00Z` (34h stale) → refreshed `tmp/edai2-gcp/operator-inputs.json` + `monetary-inputs.json` to `current=console=1833686 VND` observed `2026-10-17T15:33:00+00:00` (from console snapshot: `7889850-6056164` remaining, 8 days left, ends `2026-10-25`). Trial remaining at gate `176.4h`, requested TTL 6h, budget `6311880 VND` envelope — headroom large.
- **Command / exit-code log:** SHA recompute 0 (three locked hashes match); `--verify-private-backend initialized` 0 after archiving stale proof to `.stale-20261017T1535Z` (first attempt exit 2 `TOPIC22_BUDGET_ERROR` was FileExists on existing proof — own-rot routine, recovered); bundle-form `check_budget --live-external-preflight` wrote `ok:true` records (wrapper reported exit 2, files authoritative — ruling below); `cluster-info` 0; `get deploy/nodes` 0; `get scaledobject,hpa/workerpool` 0; `helm list` 0; `publish_agents.py` with supported flags exit 0 but wrote NO file (`live_execution: requires_runtime_injected_runner` — stub by design, `main()` only prints a job plan); `pytest test_mcp_contracts.py` 0 (5 passed); `test_gke_agents --collect-only` 0 (no tests); all `--help` 0 (flag gaps proven); `helm history retrieval-agent` exit 1 (`release: not found` — no helm-managed workload releases, direct-manifest study-debt); `get endpoints` 0 (all three empty); `get sandboxagents/remotemcpservers` 0 (no resources). Topic-file raw-env gate command NOT run (rejected by implementation); topic-file `lease-status` NOT run (no such flags).
- **Evidence / SHA-256 log:** `gcp_preflight_topic26.json` SHA `a905dbe4231eda88c1ac67c4f8656aebccd900cb7ba5e01b3702e82ce9081213` (`ok:true`, `failures:[]`, `budget_ok:true`, `project_active:true`, `billing_linked:true`, counts `project:43/billing:7`); `cost_forecast_topic26.json` SHA `11c9968d63331a89c1d78b6562baca2dcda50fb7463cdd4d6c06a20717d1a82a` (`ok:true`, spend `1833686`, trial remaining `176.4h`). Superseded attempt-1 `48B preflight_error` records SHA `843404ae...` recorded then removed (own untracked failures). No `agents/registry.json`, `agents/chat_smoke.json`, `gke/keda_ha.json`, `rollbacks/{helm,model,index}.json` — generating them from stubs/direct writes would fabricate passes. Live reads: workers 1/1, services 0/1 (endpoints empty, by design); KEDA SO Ready True Active False, HPA `0/1`, replicas 1, WorkerPool 1/1; ModelConfigs 2 present; 0 SandboxAgent / 0 RemoteMCPServer (agent layer never applied); CRDs present.
- **Screenshot QA:** `agentregistry_agents.png`, `keda_scale.png` NOT captured (Missing). Capture script lacks `--capture/--viewport` (verified); no substitutes manufactured.
- **Cleanup / runtime release:** No workload mutation, no load-generator pods, no temp routes. Reused `evidence-run` lease (`acquired 2026-10-17T10:22:24Z`, commit `7233469`, ~47min left at gate time) — no second lease acquired (would fail `already held` + violate serial-lease rule). No suspend/release (cluster UP, 2 nodes; suspending would destroy another session's resumed platform). Backend proof rotated at HEAD `071a966` observed `15:34:07Z`.
- **Limitations:** (1) `publish_agents.py:262-277` is a plan-printer stub; live publish needs owning-topic injected runner. `smoke_release.py`/`build_index.py` same stub class (no `--keda-ha/--inject-*/--verify-*`); `manage_profile.py` has no `lease-status` and authorizes only `edai2-gke`. Never patched under lease — returned to owning local topics. (2) No helm-managed workload releases → `helm rollback` inapplicable. (3) Zero Ready endpoints + zero agent resources → KEDA/chat/registry wins unprovable; one bounded retry NOT spent on foreknown-Partial churn. (4) PoC Partial pre-accepted: actor/UID overlap, model/index rollback, strict cooldown, chat readiness.
- **Handoff:** Topic 27 BLOCKED on owning-topic implementation (registry publish path, KEDA/chat/rollback CLIs, agent resources applied, Section 03 activation + canonical index for Ready endpoints). Next session: fresh ≤6h `evidence-run` lease (current one near expiry), do NOT resume from `topic25-suspend-20261016.json` (cluster UP), re-verify spend freshness (<24h) + backend proof (<900s) before any mutation.

### Continuation 2026-10-17 ~23:56Z — execution run, Partial (no live mutation)
- **Status:** Partial. Live gates passed; every Topic 26 live path fail-closed with zero workload mutation. PoC demo-win NOT landed: `agents/registry.json`, `chat_smoke.json`, `gke/keda_ha.json`, `rollbacks/{helm,model,index}.json`, `agentregistry_agents.png`, `keda_scale.png` + manifest hashes all Missing (reasons below, no substitutes manufactured).
- **Branch / revision:** `feature/implement-edai2`, HEAD `071a9661f713f7a97b698de0964351d31e870d46`. `git status --short --branch` delta identical to planning snapshot (`M` usage_ledger + 5 code/test files + topic file; 8 untracked incl. `live_runner.py` + 5 new unit tests + 2 gate files). No stage/commit/push. Focused suite green: `67 passed, 1 skipped` (registry, live_runner, publish_agents_live, smoke_keda_chats, smoke_rollback, build_index_rollback, required_uis).
- **Spend / trial:** Reused bundle `current=console=1833686 VND` observed `2026-10-17T15:33:00Z` (~8.4h old at run, `<24h` fresh). Trial ends `2026-10-25T00:00Z` (~168h left), budget `6311880 VND`, forecast ceiling `4733910 VND` — headroom large. Reused gate files (no overwrite — `write_immutable_json` fail-closed): `gcp_preflight_topic26.json` SHA `a905dbe4…08213` (`ok:true`), `cost_forecast_topic26.json` SHA `11c9968d…17d1a82a` (`ok:true`).
- **Backend proof:** Stale proof (`15:34:07Z`, ~8.4h) archived to `topic22-backend-initialized-proof.json.stale-20261017T2355Z`, refreshed exit 0, new proof `ok:true` revision `071a966…` observed `2026-10-17T23:56:36Z`.
- **Lease:** `tmp/edai2-gcp/evidence-run-lease.json` absent before acquire (only `topic23-lease.json` present). Acquired exit 0: owner `evidence-run`, commit `071a966…`, TTL 6h, acquired `23:56:49Z` (expires ~05:56Z Oct 18). Ruling: `manage_profile.py` tracks no refcount/expiry — zero-refcount handoff is unprovable via CLI; file presence/owner/commit/TTL recorded instead. Context ruling: dedicated kubeconfig contains only `edai2-gke` (topic template `gke_…` name absent); used `edai2-gke` everywhere (authorized by `manage_profile EXPECTED_CONTEXT` + `live_runner` allowlist), never the default (default `current-context` unset).
- **Task 1:** `cluster-info` exit 0 (`136.115.175.17`); `pytest test_gke_agents.py test_mcp_contracts.py --live-gke` exit 0 (12 passed).
- **Task 2 (registry):** `publish_agents.py --publish --read-back` exit 1 fail-closed `ValueError: job commit mismatch for agent: retrieval` (`jobs.json` commit `7233469…` vs HEAD `071a966…`), no file written, no mutation. Second blocker unreached: `arctl` absent from PATH.
- **Task 3 (KEDA):** topic command as written exits 1 (`--keda-ha requires --strict`); with `--strict` exits 1 (`--keda-ha requires --chat-base-url` — flag omitted by topic). Live run impossible regardless: no `/load|/drain` routes anywhere in `src/` (probe HTTP contract unimplemented), pods and EndpointSlices `Ready=false` for all three services. No base URL guessed (would manufacture load against an uncontracted endpoint). No mutation.
- **Task 4 (chats):** exits 1 (`--agent-chats requires --chat-base-url`); plus `--registry-evidence` file absent. No file, no mutation.
- **Task 5 (rollbacks):** NOT executed live — unsafe under current preconditions. `prove_helm_rollback` runs bare `helm upgrade --set failureMode=` (no `--atomic`) then expects failure; a successful upgrade would mutate the already-`0/1` release before any restore. `prove_model_rollback` runs `kubectl set image` on `llmd-primary` (currently `0/1`) while eval-gated restore cannot pass (`/readyz` red). `prove_index_rollback` runs eval before `restore_current`, leaving the alias mutated on eval failure. Releases also live in `default` ns vs topic `-n edai2`. Zero mutation performed.
- **Task 6 (captures):** not attempted — machine evidence absent, `screenshots/` dir absent. No browser/tunnel launched.
- **Screenshot QA:** both owned PNGs Missing; manifest Missing. Nothing manufactured.
- **Cleanup:** no workload/route/pod/port-forward created; KEDA mins already 1; Helm/model/index/alias untouched. Cluster left UP (2 nodes Ready) for Topic 27; lease left held (fresh). No suspend (no repo-owned suspend mechanism verified; `manage_profile suspended` is dry-run render + lease release only).
- **Limitations:** (1) `jobs.json` pinned at `7233469…` vs HEAD `071a966…` — `resolve_bindings` fail-closed is correct per code but irreconcilable with topic's same-commit rule without owning-topic policy (rebuild/repin or explicit CI-commit publish). (2) Topic omits `--chat-base-url` required by both KEDA and chat CLIs; probe HTTP contract (`/load|/drain`) unimplemented in `src/`. (3) `manage_profile.py` has no `lease-status`/refcount — Topic 27 must check file owner/commit/acquired_at + 6h TTL manually. (4) Rollback probes mutate before their restore gates — require Ready preconditions + namespace alignment first. Never patched under lease; all returned to owning local topics.
- **Handoff:** Topic 27 BLOCKED on (1) jobs/HEAD commit alignment, (2) `--chat-base-url` + `/load|/drain` contract, (3) Ready services (Topic 28) + 5 `SandboxAgent`/`RemoteMCPServer` resources applied, (4) rollback preconditions. Handed over: cluster UP, backend proof at HEAD `23:56:36Z` (re-verify `<900s` before mutation — will be stale), reused preflight/forecast SHAs above (re-verify spend `<24h`), `evidence-run` lease file held+unexpired (reuse iff TTL remains at use, else release + acquire fresh through `manage_profile.py` with explicit `--lease-file`). Topic 27 unblock criteria NOT met: no restored-version proof (nothing mutated), no captures, no refcount proof possible.

### Finalize 2026-10-18 ~00:05Z — Tranche 0 forensics closed the topic (Partial, zero mutation)
- **Tranche 0 (suspended, read-only) results:** (1) `git diff 7233469…..HEAD --stat -- src infra configs containers ci` EMPTY — zero governing-source changes; delta is evidence JSONs + `tests/contract/llm/test_section03_contract.py` (test-only rename/assert flip) + plan files. Evidence commit `7233469…` preserves every digest equality; HEAD drift is LOG-ONLY. (2) Name mapping: releases `edai2-{retrieval-agent,drift-agent,coordinator,…}` in `default` ns (rev 2/1/1, `edai2-retrieval-agent` rev 1 superseded-failed); deployments/services in `edai2` ns (`retrieval-agent` etc.); `helm history retrieval-agent -n edai2` → `release: not found`. CLI assumes release==deployment==service short name — irreconcilable without code change. (3) Inventory holds exactly 1 registry-server image + 1 ateom-gvisor actor image (GKE-job path resolvable). (4) No Section 03 import Job ever ran (`section03/` = partial `upload.json` only, drift `/readyz` red by design); pods + EndpointSlices `Ready=false` for all three services. Manual import refused (drift release is sole activation owner).
- **Registry publish — BLOCKED both paths, zero mutation:** local `--publish` needs `arctl` (absent from PATH, no repo copy, `which arctl` exit 1 even inside `agentregistry` server pod; no pinned checksum to install verifiably → safe-stop input). `--submit-gke-job` is broken by design: `publish_and_readback` materializes `agent.yaml` into a workstation temp dir that `gke_job_runner` never mounts into the Job container (cwd dropped) — the in-cluster `arctl publish <local-tmp-path>` deterministically fails; fixing needs code patch under lease (prohibited). Not attempted live (foreknown churn; code read is the evidence).
- **KEDA/chats — BLOCKED, zero mutation:** topic omits required `--chat-base-url`; probe posts `/load|/chat|/drain`, but `src/` has no such routes (real: `/v1/chat`, `/v1/retrieval/search`, `/v1/drift/detect`) and `_http_post` hits the base URL directly (ClusterIP unreachable without operator port-forward). Even fixed, `Ready=false` everywhere voids distinct-actor/Ready-target proof (readiness is Topic 28's unlock). No base URL guessed, no shim built (would corrupt evidence provenance).
- **Rollbacks — NOT executed (unsafe):** `prove_helm_rollback` runs bare `helm upgrade --set failureMode=` (no `--atomic`) then expects failure — on the already-`0/1` `edai2-retrieval-agent` a no-effect success would mutate the release with no restore; `prove_model_rollback` runs `kubectl set image` on `llmd-primary` (`0/1`) while eval-gated restore cannot pass; index eval runs before `restore_current`. Preconditions (Ready services, name alignment) absent.
- **Lease released:** `manage_profile.py rubric-evidence --release-session-lease --owner evidence-run --lease-file tmp/edai2-gcp/evidence-run-lease.json` exit 0 (`lease_released:true`, file absent). One topic, one lease acquisition, one clean release. Cluster left UP (Topic 27 needs Jenkins/observability). Spend `1833686 VND` (~8.5h old, `<24h`), trial ~168h left, envelope headroom large — logged for Topic 27's fresh gate.
- **Limitations carried forward:** (a) GKE-job file delivery + route contracts + release/deployment name mapping → owning local topic (suspended, test-first, no lease). (b) Service readiness → Topic 28 (Section 03 activation + canonical index). (c) `manage_profile` has no lease-status/refcount.
- **Handoff:** Topic 27 MAY PROCEED on its own inputs — `jobs.json` present (6 jobs, `digest_match:true`, commit `7233469…`), Jenkins + Grafana/Prometheus/Loki/Tempo/Langfuse all UP, cluster UP, no lease file held (acquire fresh ≤6h `evidence-run` + fresh spend/backend gates before mutation). Topic 26 terminal state: Partial with Missing `registry.json`, `chat_smoke.json`, `keda_ha.json`, `rollbacks/*`, both PNGs + manifest (exact causes above, no substitutes). Numeric order preserved: 26 closed (Partial) before 27 starts.

### Execution 2026-10-18 ~16:12Z — Partial, one lease, zero mutation (dependency order T26 after T25)

- **Status:** Partial. Live gates passed; every T26 live path fail-closed with zero mutation. PoC demo-win NOT landed.
- **Branch / revision:** `feature/implement-edai2`, HEAD `e651a86dfb7d509c28c58fe0116cddd3cf6ea1a5`. No stage/commit/push.
- **Spend / trial:** `2119176 VND` observed `2026-10-18T15:52:10+00:00` (`<24h`, remaining `5,770,674/7,889,850`). Trial ends `2026-10-25T00:00Z` (~6d left).
- **Command / exit log:** backend `initialized` reused (`16:09:23Z`, age `146s <900s`, rev `e651a86`, no rotation needed). Bundle gate archived to `.stale-20261018T1611Z`, fresh `ok:true failures:[]` (exit 0, files authoritative). Lease `topic26-registry --lease-file tmp/edai2-gcp/topic26-lease.json` exit 0 (`16:12:30Z`, TTL 6h). Units `test_publish_agents_live+test_smoke_keda_chats` 14 passed. Live (bounded, read-only + one fail-closed publish): `publish_agents --publish --read-back --commit-sha e651a86` exit 1 `ValueError: job commit mismatch for agent: retrieval` (`jobs.json` `7233469…` vs HEAD `e651a86…`), no file, no mutation; endpoints `retrieval-agent,drift-agent` empty (deprecated Endpoints API, no Ready); KEDA SO `5/5 Ready True Active False`, min 1 max 2 nominal; `kagent` ns `0 SandboxAgent` (agent layer never applied). Rollbacks NOT executed (unsafe: releases in `default` vs deployments in `edai2`, `llmd-primary 0/1 CrashLoop`, services `0/1` — bare `helm upgrade` without `--atomic` would mutate with no restore). One bounded retry NOT spent on foreknown-Partial churn.
- **Evidence / SHA:** `gcp_preflight_topic26.json` `ok:true`, `cost_forecast_topic26.json` `ok:true` (spend `2119176`). No `agents/registry.json`, `chat_smoke.json`, `gke/keda_ha.json`, `rollbacks/*` (would fabricate). `git diff 7233469..HEAD --name-only` confirms zero `src/infra/configs/containers/ci` changes (scripts/tests only).
- **Screenshot QA:** `agentregistry_agents.png`, `keda_scale.png` Missing; manifest untouched. Nothing manufactured.
- **Cleanup:** No workload/route/pod/port-forward created; KEDA mins already 1; Helm/model/index untouched. Lease `topic26-registry` released exit 0 (file absent). Cluster left UP for T28 (readiness unlock next per dependency order, not numeric T27).
- **Limitations:** (1) `jobs.json` `7233469…` vs HEAD `e651a86…` — `resolve_bindings` fail-closed correct, needs owning-topic rebuild/repin policy. (2) Zero Ready endpoints + zero agent resources → KEDA/chat/registry wins unprovable (readiness is T28 unlock). (3) Release/deployment namespace split (`default` vs `edai2`) blocks rollback CLIs. Never patched under lease.
- **Handoff:** T28 readiness unlock next (Section 03 activation + canonical index + llmd 403 fix). T27 gateway/telemetry BLOCKED until Ready + Jenkins jobs land. Next: fresh lease + fresh gates per topic (backend `<900s`, spend `<24h`).

### Execution 2026-10-18 ~16:36Z — Partial, verify-only, zero mutation (readiness red)
- Authoritative for Task 4 (subagent-driven run): this 16:36Z entry; 16:12Z entry is prior inline-run history.
- **Status:** Partial. Live gates passed; every T26 live path fail-closed with zero workload mutation. PoC demo-win NOT landed: `agents/registry.json`, `chat_smoke.json`, `gke/keda_ha.json`, `rollbacks/{helm,model,index}.json`, `agentregistry_agents.png`, `keda_scale.png` all Missing (reasons below, no substitutes manufactured).
- **Branch / revision:** `feature/implement-edai2`, HEAD `e651a86dfb7d509c28c58fe0116cddd3cf6ea1a5`. No stage/commit/push. No worktree/branch switch.
- **Spend:** Reused bundle `2119176 VND` observed `2026-10-18T15:52:10+00:00` (`<24h` fresh, trial ends `2026-10-25T00:00Z`). Preflight `ok:true failures:[]`, forecast `ok:true` — no archive, no fresh `bundle-form` needed.
- **Backend:** Reused `topic22-backend-initialized-proof.json` (`observed 16:31:30Z`, age `~136s <900s`, rev `e651a86` match) — no rotation needed, no `.stale-*` created.
- **Lease:** Acquire: `manage_profile.py --kubeconfig 'C:\Users\hhoangdo\Documents\Personal Projects\FSDS\ecom-data-platform-submission\tmp\edai2-gcp\kubeconfig' --context edai2-gke rubric-evidence --ttl 6h --acquire-session-lease --owner topic26-registry --commit-sha e651a86dfb7d509c28c58fe0116cddd3cf6ea1a5 --lease-file tmp/edai2-gcp/topic26-lease.json` exit 0 (`16:34:09Z`, TTL 6h). Release: same `--kubeconfig`/`--context edai2-gke` with `--release-session-lease --owner topic26-registry --lease-file tmp/edai2-gcp/topic26-lease.json` exit 0 (`lease_released:true`, file absent). Cluster left UP.
- **Units:** `pytest tests/unit/llm/test_publish_agents_live.py tests/unit/llm/test_smoke_keda_chats.py -q` → 18 passed.
- **Live publish (fail-closed, no mutation):** `publish_agents.py --publish --read-back --commit-sha e651a86 --strict` exit 1 `ValueError: job commit mismatch for agent: retrieval` (`evidence/04_2_llm_design/cicd/jobs.json` commit `7233469eef8519aeb059da03a924bb6a180bed5b` vs HEAD `e651a86…`), no file written. Parse-only probe via `resolve_bindings(..., allow_ci_commit=7233469…)` → `PARSE_OK` 3 agents (`retrieval,drift,coordinator` bound at `7233469`); NOT used to publish (no owning-topic policy for wrong-commit publish).
- **Live read-only state:** `endpoints retrieval-agent/drift-agent/coordinator` all exist with EMPTY address lists (deprecated `v1 Endpoints` warning); `scaledobject -n edai2` 5/5 `Ready True Active False`, min 1 max 2 nominal; `sandboxagents -n kagent` → `No resources found` (agent layer never applied). Deploys `retrieval/drift/coordinator` all `0/1`.
- **Rollbacks NOT executed (unsafe, machine-verified):** releases `edai2-{retrieval-agent,drift-agent,coordinator}` live in `default` ns (rev 2/1/1) vs Deployments in `edai2` ns; agent deploys `0/1`, `llmd-primary 0/1`, `llmd-comparison 0/0`; bare `helm upgrade --set failureMode=` without `--atomic` would mutate with no restore, and eval-gated model/index restores cannot pass with `/readyz` red.
- **Screenshot QA / captures:** none attempted — machine evidence absent (`Missing`). Nothing manufactured; no tunnel/browser launched.
- **Cleanup:** No workload/route/pod/port-forward created; KEDA mins already 1; Helm/model/index/alias untouched.
- **Limitations:** (1) `jobs.json` pinned at `7233469…` vs HEAD `e651a86…` — fail-closed correct, needs owning-topic rebuild/repin policy. (2) Zero Ready endpoints + zero agent resources → registry/KEDA/chat wins unprovable (readiness is T28 unlock). (3) Release/deployment namespace split (`default` vs `edai2`) blocks rollback CLIs as written. Never patched under lease. One retry max: zero retries spent (foreknown-Partial churn).
- **Handoff:** T28 readiness unlock next. Next session: fresh lease + fresh gates per topic (backend `<900s`, spend `<24h`); do NOT resume from any suspend file (cluster UP).

### Execution 2026-10-18 ~17:03Z — Partial, verify-only, zero mutation (readiness red)
- Authoritative for Task 3 (subagent-driven run): this entry; prior entries are inline-run history.
- **Status:** Partial. Live gates passed; every T26 live path fail-closed with zero workload mutation. PoC demo-win NOT landed: `agents/registry.json`, `chat_smoke.json`, `gke/keda_ha.json`, `rollbacks/{helm,model,index}.json`, `agentregistry_agents.png`, `keda_scale.png` all Missing (reasons below, no substitutes manufactured).
- **Branch / revision:** `feature/implement-edai2`, HEAD `e651a86dfb7d509c28c58fe0116cddd3cf6ea1a5`. No stage/commit/push. No worktree/branch switch.
- **Spend / bundle gate:** Reused (no archive, no refresh): `gcp_preflight_topic26.json` `ok:true failures:[]`, `cost_forecast_topic26.json` `ok:true` spend `2119176 VND` observed `2026-10-18T15:52:10+00:00` (`~68min old <24h`, trial ends `2026-10-25T00:00Z`).
- **Backend:** Reused, no rotation, no `.stale-*` created: `tmp/edai2-gcp/terraform-data/topic22-backend-initialized-proof.json` `ok:true phase:initialized` rev `e651a86…` match, observed `2026-10-18T16:57:13Z` (age `~210s <900s` at `17:00:43Z` check).
- **Lease:** Acquire `uv run python scripts/gke/manage_profile.py --kubeconfig 'C:\Users\hhoangdo\Documents\Personal Projects\FSDS\ecom-data-platform-submission\tmp\edai2-gcp\kubeconfig' --context edai2-gke rubric-evidence --ttl 6h --acquire-session-lease --owner topic26-registry --commit-sha e651a86dfb7d509c28c58fe0116cddd3cf6ea1a5 --lease-file tmp/edai2-gcp/topic26-lease.json` exit 0 (`lease_acquired:true`, acquired `2026-10-18T17:00:52Z`, TTL 6h). Release: same `--kubeconfig`/`--context edai2-gke` with `rubric-evidence --release-session-lease --owner topic26-registry --lease-file tmp/edai2-gcp/topic26-lease.json` exit 0 (`lease_released:true`, `Test-Path` False = file absent). Cluster left UP.
- **Units:** `uv run pytest tests/unit/llm/test_publish_agents_live.py tests/unit/llm/test_smoke_keda_chats.py -q` → 18 passed.
- **Live publish (fail-closed, no mutation):** `uv run python scripts/llm/publish_agents.py --kubeconfig '<abs-kubeconfig>' --context edai2-gke --templates infra/agentregistry/edai2 --commit-sha e651a86dfb7d509c28c58fe0116cddd3cf6ea1a5 --publish --read-back --output evidence/04_2_llm_design/agents/registry.json --strict` → nonzero exit, `ValueError: job commit mismatch for agent: retrieval` (`evidence/04_2_llm_design/cicd/jobs.json` commit `7233469eef8519aeb059da03a924bb6a180bed5b` vs HEAD `e651a86…`); `Test-Path evidence/04_2_llm_design/agents/registry.json` False (no file written). Parse-only: `resolve_bindings(templates, jobs.json, platform_install.json, e651a86…, strict=True, allow_ci_commit=7233469…)` → `PARSE_OK ['coordinator','drift','retrieval']` (in-process only; CLI `--allow-ci-commit` without `--publish` exits 2 `exactly one of --publish and --submit-gke-job is required` — NOT used to publish at wrong commit).
- **Live read-only state:** `kubectl --kubeconfig <abs> --context edai2-gke -n edai2 get endpoints` → `retrieval-agent`, `drift-agent`, `coordinator` all EMPTY address lists (plus empty `llmd-router`; deprecated `v1 Endpoints` warning); `get scaledobjects -n edai2` → 5/5 (`retrieval-agent,drift-agent,coordinator,feast-offline-writer,feast-online-writer`) `Ready True Active False`, min 1 max 2; `get sandboxagents -n kagent` → `No resources found`; `get deployments -n edai2` → `retrieval/drift/coordinator 0/1`, `llmd-primary 0/1`, `llmd-comparison 0/0`.
- **Rollbacks NOT executed (unsafe, fresh machine evidence):** `helm --kubeconfig <abs> --kube-context edai2-gke list --namespace default --short` → `edai2-{retrieval-agent,drift-agent,coordinator,rag-index,feast-offline-writer,feast-online-writer}` (workload releases in `default`), while Deployments/Services live in `edai2` and that ns holds only platform charts (`agentregistry,airflow,substrate,…`, no workload releases). Combined with `0/1` agent deploys, bare `helm upgrade` without `--atomic` would mutate with no restorable gate.
- **Screenshot QA / captures:** none attempted — machine evidence absent (`Missing`). No tunnel/browser launched. Nothing manufactured.
- **Cleanup:** No workload/route/pod/port-forward created; KEDA mins already 1; Helm/model/index/alias untouched.
- **Limitations:** (1) `jobs.json` pinned at `7233469…` vs HEAD `e651a86…` — fail-closed correct, needs owning-topic rebuild/repin policy. (2) Zero Ready endpoints + zero agent resources → registry/KEDA/chat wins unprovable (readiness is T28 unlock). (3) Release/deployment namespace split (`default` vs `edai2`) blocks rollback CLIs as written. Never patched under lease. One retry max: zero retries spent (foreknown-Partial churn).
- **Handoff:** T28 readiness unlock next. Next session: fresh lease + fresh gates per topic (backend `<900s`, spend `<24h`); do NOT resume from any suspend file (cluster UP).
