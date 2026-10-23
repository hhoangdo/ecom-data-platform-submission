# Topic 24: Compact GKE Platform Installation Implementation Plan

> **Current execution contract — user-approved 2026-10-13:** The final “GCP execution, verified completion” plan supersedes the older simplified, two-hour and three-CPU instructions below. Use one serial six-hour `topic24-platform` lease, stop new work at 5½ hours, and require aggregate ≤5 CPU, ≤18 GiB memory and ≤80 GiB PVC. Keep existing machine types, one regular node and at most one Spot node. Run heavy builds/tests on GKE, with no local Docker/Kubernetes. Require all 20 named ExternalSecrets, real primary-model inference, strict live evidence and verified suspension before Complete. Historical dated Partial records remain unchanged as prior-run evidence. Stay on `feature/implement-edai2`; no staging, commits, pushes, branches or worktrees.

> **For any agent (Codex / opencode / Claude / etc):** Work task-by-task in one session. Steps use checkbox (`- [ ]`) tracking. Auto-run without asking; only stop on safe-stop gates below.

> **Study-only simplified run (first iteration, overrides strict gates below):**
> - Repo root = current checkout (`<repo-root>`), not `C:\Users\oou1hc\...`. Use `rtk` prefix if installed, else run commands directly.
> - Auto-run end-to-end; no mid-run approvals. Only safe stops: budget/spend/trial fail, missing bundle/inputs, wrong cluster context, or capacity over cap. Record blocker and suspend.
> - Check source hashes + `git status` once at start (not before every command). Reuse fresh (<24h) preflight/forecast if unchanged.
> - One lease per topic. Set `EDAI2_KUBECONFIG`/`EDAI2_CONTEXT` once, reuse. Always suspend/release at end even on Partial.
> - Screenshots (if any): viewport PNG + SHA + linked machine JSON + eyeball check is enough for first pass. Skip temp-PNG/signature/decode/atomic + proves/does-not prose.
> - Happy-path first: platform Ready + private services wins. Exact selector-SHA/EndpointSlice read-back, full gateway policy matrix may stay `Partial` — record measured value, hand off, don't loop retries.
> - Keep two-phase (plan then execute) + short Completion Record.

**Goal:** Install the private, capacity-bounded EDAI2 supporting platform and control planes on GKE without deploying the six application workloads or enabling public ingress.

**Architecture:** Helm owns compact supporting releases; pinned Kustomize owns llm-d v0.7 CPU; Gateway API/agentgateway governs all model, MCP, and A2A traffic; kagent 0.9.9 and Agent Substrate 0.0.6 provide declarative sandboxed agents and a gVisor worker pool. Vault/External Secrets and Workload Identity supply runtime credentials without payloads in manifests.

**Tech Stack:** GKE, Helm, Kustomize, Vault, External Secrets, PostgreSQL/pgvector, Valkey, Redpanda, Airflow, Feast, DataHub/OpenSearch, ClickHouse/Langfuse, Prometheus/Loki/Tempo/Grafana/Alloy, Gateway API, agentgateway, llm-d, kagent, Agent Substrate, Agent Registry, Jenkins.

## Metadata

| Field | Decision |
|---|---|
| Phase | Private platform; execution topic 24 |
| Authoritative source tasks | `04.2_llm_design.md` Task 8 |
| Primary rubric cells | `Sheet3!E3`, `Sheet3!E4`, `Sheet3!E6` |
| Prerequisites | Topic 23 successful, Topic 22 context/outputs, immutable model-cache and Vault bootstrap hashes |
| Blocked successors | Topics 25-31 |
| Runtime owner | `topic24-platform`, `core`, maximum 2h |
| Execution class | `GCP-write/private-runtime` |
| Branch rule | Same branch; serial after Topic 23 |

## Global Constraints

- Use `rtk` prefix if installed, else run commands directly. Repo root = current checkout (`<repo-root>`).
- Fixed source hashes: Section 03 `2b70794867c5d70441cb6848df547e1fbf8e462d7af68a0b9527b6ee18cb7643`; EDAI2 `d8ca5b11c577c888b34a2518e3ce5bc424d27201f75a10c6d4d4ed79787b7dfa`; rubric at `tmp/rubic-check/Coursework Tracking (Public).xlsx` `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- Prefix every shell command with `rtk`; no branch/worktree/stage/commit changes.
- Consume the completed local implementation. If a source/IaC/chart defect appears, capture it, release or suspend any owned runtime, mark this topic `Partial`, and return it to the owning local topic; do not patch implementation during a live cloud lease.
- Require explicit context `edai2-gke` (live `tmp/edai2-gcp/kube-target.json` truth; the `gke_${GOOGLE_CLOUD_PROJECT}_us-central1-a_edai2` form is the pre-rename gcloud-native name rewritten by `prepare_private_kube_target`/`_bind_private_kube_document`) before every live block.
- Require `EDAI2_GKE_KUBECONFIG=tmp/edai2-gcp/kubeconfig` and `EDAI2_GKE_CONTEXT=edai2-gke`. Every `kubectl` call includes `--kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT`; every Helm call includes `--kubeconfig $env:EDAI2_GKE_KUBECONFIG --kube-context $env:EDAI2_GKE_CONTEXT`; every script that queries or mutates Kubernetes receives both values. Never use or change the default kubeconfig/current context.
- Re-run the redacted live project/billing/IAM/notification/recovery-sink/DNS/trial/spend/budget/capacity gate. Missing external input, model-cache URI/generation, or permission is a safe stop.
- `EDAI2_TFVARS_PATH` remains an absolute path resolving exactly to untracked `tmp/edai2-gcp/coursework.auto.tfvars`.
- `core` uses one regular platform node and at most one Spot node only during private model/API validation; no public `LoadBalancer`.
- Capacity fails above regular 3.4 CPU/24Gi, one-Spot 6.8 CPU/24Gi, platform aggregate 3.00 CPU/18Gi, or PVC 80Gi. Lower/serialize workloads; never enlarge approved machines silently.
- All releases/configs/images/models are immutable and pinned. Reject `latest`, mutable remote Kustomize bases, GPUs, hosted models, bundled duplicate data stores/tools/agents, and secret literals.
- GCS uses Workload Identity and fixed prefixes. Langfuse/Substrate/model cache must not use JSON credentials.
- ExternalSecret must be Ready before each consumer. Kagent PostgreSQL URL is a Vault Agent file, not an ExternalSecret.
- Core ingress is private ClusterIP only. ACME/public ingress belongs to Topics 27/31.
- One bounded retry after an identified transient error; repeated failure records truthful partial state and suspends.
- `Sheet3!E49` remains out of scope; no VM/Ansible.

## Read-Only Planning Refresh

1. `rtk git status --short --branch`
   - Expected: same branch as Topics 22-23 and no unexplained overlap in platform manifests/evidence.
2. `rtk python -c "import hashlib; p=['tmp/edai2-plan/03_data_generator_improvement.md','tmp/edai2-plan/04.2_llm_design.md','tmp/rubic-check/Coursework Tracking (Public).xlsx']; print([hashlib.sha256(open(x,'rb').read()).hexdigest() for x in p])"`
   - Expected: fixed hashes.
3. `rtk rg -n "Status|vault_bootstrap.json|model_cache.json|Handoff" tmp/edai2-plan/execution-v1/gcp/23-vault-kms-model-cache-bootstrap.md`
   - Expected: successful bootstrap/cache, zero-secret scan, suspended release.
4. `rtk kubectl --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT cluster-info`
   - Expected: the dedicated kubeconfig resolves the approved GKE API; mismatch or failure is a safe stop.

## Scope

- Validate pinned chart/Kustomize rendering and capacity.
- Enter `core` under a fresh <=2h lease.
- Restore Vault and install every private supporting release in one fail-fast order.
- Verify ExternalSecrets, storage/retention, Workload Identity, gateway policies, model cache, llm-d, Substrate, kagent, registry, and Jenkins controller.
- Render but do not apply app-owned agent/workload resources.
- Suspend after durable machine inventory.

## Non-Goals

- No application workload build/push/deploy, Section 03 import, agent publication, KEDA scaling proof, public route, Jenkins screenshot, benchmark, or final rubric claim.
- No direct Helm workaround for a failed release-order gate.

## Exact File Map

| Role | Exact path(s) |
|---|---|
| Read | `infra/helm/edai2/releases.yaml` |
| Read | `infra/helm/edai2/values/airflow.yaml`, `infra/helm/edai2/values/feast.yaml`, `infra/helm/edai2/values/postgres.yaml`, `infra/helm/edai2/values/valkey.yaml`, `infra/helm/edai2/values/redpanda.yaml` |
| Read | `infra/helm/edai2/values/datahub.yaml`, `infra/helm/edai2/values/opensearch.yaml`, `infra/helm/edai2/values/substrate.yaml`, `infra/helm/edai2/values/kagent.yaml` |
| Read | `infra/helm/edai2/values/agentgateway.yaml`, `infra/helm/edai2/values/agentregistry.yaml`, `infra/helm/edai2/values/jenkins.yaml`, `infra/helm/edai2/values/vault.yaml`, `infra/helm/edai2/values/external-secrets.yaml` |
| Read | `infra/helm/edai2/values/ingress-nginx.yaml`, `infra/helm/edai2/values/cert-manager.yaml`, `infra/helm/edai2/values/keda.yaml`, `infra/helm/edai2/values/prometheus.yaml` |
| Read | `infra/helm/edai2/values/loki.yaml`, `infra/helm/edai2/values/tempo.yaml`, `infra/helm/edai2/values/grafana.yaml`, `infra/helm/edai2/values/alloy.yaml` |
| Read | `infra/helm/edai2/values/langfuse.yaml`, `infra/helm/edai2/values/clickhouse.yaml` |
| Read | `infra/helm/edai2/service-agent/Chart.yaml`, `infra/helm/edai2/service-agent/values.yaml`, `infra/helm/edai2/service-agent/templates/deployment.yaml`, `infra/helm/edai2/service-agent/templates/service.yaml` |
| Read | `infra/helm/edai2/service-agent/templates/scaledobject.yaml`, `infra/helm/edai2/service-agent/templates/networkpolicy.yaml`, `infra/helm/edai2/service-agent/templates/serviceaccount.yaml` |
| Read | `infra/helm/edai2/service-agent/templates/sandboxagent.yaml`, `infra/helm/edai2/service-agent/templates/remotemcpserver.yaml`, `infra/helm/edai2/service-agent/templates/agentgateway-policy.yaml` |
| Read | `infra/helm/edai2/worker/Chart.yaml`, `infra/helm/edai2/worker/values.yaml`, `infra/helm/edai2/worker/templates/deployment.yaml`, `infra/helm/edai2/worker/templates/scaledobject.yaml` |
| Read | `infra/helm/edai2/worker/templates/networkpolicy.yaml`, `infra/helm/edai2/worker/templates/serviceaccount.yaml` |
| Read | `infra/kustomize/llmd/overlays/cpu/kustomization.yaml`, `infra/kustomize/llmd/overlays/cpu/patch-primary.yaml`, `infra/kustomize/llmd/overlays/cpu/patch-comparison.yaml` |
| Read | `infra/kustomize/llmd/overlays/cpu/patch-router.yaml`, `infra/kustomize/llmd/overlays/cpu/patch-model-cache-init.yaml` |
| Read | `infra/kagent/edai2/model-configs.yaml`, `infra/kagent/edai2/workerpool-scaledobject.yaml` |
| Read | `infra/agentgateway/edai2/gateway.yaml`, `infra/agentgateway/edai2/model-route.yaml`, `infra/agentgateway/edai2/mcp-routes.yaml`, `infra/agentgateway/edai2/a2a-routes.yaml`, `infra/agentgateway/edai2/policies.yaml` |
| Read | `infra/agentregistry/edai2/retrieval-agent.yaml`, `infra/agentregistry/edai2/drift-agent.yaml`, `infra/agentregistry/edai2/coordinator-agent.yaml` |
| Read | `infra/security/vault/config.hcl`, `infra/security/vault/kubernetes-auth.yaml`, `infra/security/vault/policies/retrieval.hcl`, `infra/security/vault/policies/drift.hcl`, `infra/security/vault/policies/coordinator.hcl` |
| Read | `infra/security/vault/policies/agentgateway.hcl`, `infra/security/vault/policies/jenkins.hcl` |
| Read | `infra/security/external-secrets/cluster-secret-store.yaml`, `infra/security/external-secrets/chat-basic-auth.yaml`, `infra/security/external-secrets/jenkins-controller.yaml`, `infra/security/external-secrets/kagent-gateway-keys.yaml` |
| Read | `infra/security/external-secrets/facade-gateway-key.yaml`, `infra/security/external-secrets/postgres.yaml`, `infra/security/external-secrets/clickhouse.yaml`, `infra/security/external-secrets/valkey.yaml` |
| Read | `infra/security/external-secrets/redpanda.yaml`, `infra/security/external-secrets/airflow.yaml`, `infra/security/external-secrets/datahub.yaml`, `infra/security/external-secrets/langfuse.yaml` |
| Read | `infra/security/external-secrets/agentregistry.yaml`, `infra/security/external-secrets/grafana.yaml` |
| Execute | `scripts/gke/manage_profile.py`, `scripts/gke/check_budget.py` |
| Read external/untracked | `tmp/edai2-gcp/kubeconfig` |
| Consume | `evidence/04_2_llm_design/security/vault_bootstrap.json`, `evidence/04_2_llm_design/gke/model_cache.json` |
| Generate immutable gate evidence | `evidence/04_2_llm_design/gke/gcp_preflight_topic24.json`, `evidence/04_2_llm_design/gke/cost_forecast_topic24.json` |
| Update append-only | `evidence/04_2_llm_design/gke/usage_ledger.json` |
| Generate | `evidence/04_2_llm_design/gke/platform_install.json` |
| Generate | `evidence/04_2_llm_design/gke/platform_capacity.json` |

## Interfaces, Data Flow, and Failure Modes

Terraform/KMS/GCS + Vault/cache prerequisites -> profile capacity render -> Vault restore -> External Secrets -> platform data services -> orchestration/governance -> observability -> gateway/model stack -> substrate/kagent/registry/Jenkins -> sanitized readiness inventory.

Platform outputs consumed by Topic 25:

- Private PostgreSQL/pgvector, Valkey, Redpanda, OpenSearch, ClickHouse.
- Airflow, Feast, DataHub, observability and Langfuse endpoints.
- Gateway API/agentgateway, two ModelConfigs, one `edai2-agents` WorkerPool.
- Private Agent Registry and Jenkins controller.
- No app-owned `RemoteMCPServer`/`SandboxAgent` applied.

`platform_install.json.private_endpoints` contains exactly five keys: `agentregistry_ui`, `grafana_ui`, `airflow_web`, `datahub_frontend`, and `vault_status`. Every entry contains its namespace, rendered ClusterIP Service name and UID, service port and target port, selector SHA-256, and the nonempty Ready endpoint UID list observed from the same explicit kubeconfig/context. The whole inventory is revision/time/hash-bound. Later capture helpers must read back the named Service and EndpointSlice objects and reject an absent, extra, stale, or mismatched key/UID/port/selector/Ready-endpoint entry before opening a tunnel.

Failure modes:

- Capacity/render failure: stop before node/profile transition.
- ExternalSecret not Ready: do not start consumer.
- GCS prefix access exceeds assigned prefix: stop and revoke binding.
- Model cache generation/hash mismatch: llm-d remains unready; no Hub fallback.
- Private endpoint key/service/port/selector/Ready-endpoint mismatch: reject the inventory and block every dependent UI capture.
- Built-in kagent tools/agents or bundled stores appear: reject render.
- Any public service in core: disable it, capture failure state, suspend.
- Partial install: preserve persistent state, record exact first failed release, do not skip ahead.

## Ordered Test-First Execution Tasks

### Task 1: Validate immutable manifests and capacity

- [ ] Run `rtk uv run pytest tests/integration/llm/test_gke_agents.py tests/unit/test_edai2_security_static.py tests/unit/test_edai2_repository_contract.py -q`.
  - Expected: exit 0; version pins, secret boundaries, retention, resources, ModelConfigs, WorkerPool, gateway policy matrices, and no-public-core rules pass.
- [ ] Run `rtk helm --kubeconfig $env:EDAI2_GKE_KUBECONFIG --kube-context $env:EDAI2_GKE_CONTEXT lint infra/helm/edai2/service-agent`.
  - Expected: exit 0.
- [ ] Run `rtk helm --kubeconfig $env:EDAI2_GKE_KUBECONFIG --kube-context $env:EDAI2_GKE_CONTEXT lint infra/helm/edai2/worker`.
  - Expected: exit 0.
- [ ] Run `rtk kubectl --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT kustomize infra/kustomize/llmd/overlays/cpu`.
  - Expected: valid pinned llm-d v0.7 CPU resources, primary/comparison exact IDs, context 4096, concurrency one, no GPU/`latest`/secret/public service.
- [ ] Run `rtk uv run python scripts/gke/manage_profile.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT core --ttl 2h --render-only --output evidence/04_2_llm_design/gke/platform_capacity.json`.
  - Expected: all regular/Spot/PVC/`emptyDir`/object ceilings pass with system headroom.

### Task 2: Acquire private core runtime

- [ ] Run `rtk uv run python scripts/gke/check_budget.py --operator-inputs tmp/edai2-gcp/operator-inputs.json --required-permissions configs/gke/required_permissions.json --live-external-preflight --preflight-output evidence/04_2_llm_design/gke/gcp_preflight_topic24.json --usage-ledger evidence/04_2_llm_design/gke/usage_ledger.json --envelope configs/gke/cost_envelope.yaml --requested-profile core --requested-ttl 2h --output evidence/04_2_llm_design/gke/cost_forecast_topic24.json`.
  - bundle inputs resolve without operator action: `project_id`, `billing_account_id`, `budget_notification_target`, `dns_probes`, `billing_console_url`, and `recovery_sink` come from `--operator-inputs`; recovery attestation is skipped when `project_purpose == "personal-study"`; trial/spend/budget come from the bundle's `trial_expires_at`, `current_spend_vnd`, `console_spend_vnd`, `forecast_vnd`, `trial_credit_vnd`, `conversion_observed_at`, `spend_observed_at` (staleness enforced in code at 86400s); `EDAI2_COMMIT_SHA` is `git rev-parse HEAD` (must be 40-hex); `EDAI2_GKE_KUBECONFIG`/`EDAI2_GKE_CONTEXT` are `tmp/edai2-gcp/kubeconfig` + the `context` field of `tmp/edai2-gcp/kube-target.json`; `EDAI2_TFVARS_PATH` is the absolute path of untracked `tmp/edai2-gcp/coursework.auto.tfvars`.
  - Expected: exit 0 with a fresh redacted external/IAM/budget/capacity gate.
- [ ] Run `rtk kubectl --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT cluster-info`.
  - Expected: the dedicated kubeconfig resolves the approved GKE API without reading or changing the default context.
- [ ] Run `rtk uv run python scripts/gke/manage_profile.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT core --ttl 2h --acquire-session-lease --owner topic24-platform --commit-sha $env:EDAI2_COMMIT_SHA --stage vault`.
  - Expected: Vault restores/unseals and its previous fingerprint matches Topic 23.

### Task 3: Install the platform in the fixed order

- [ ] Run `rtk uv run python scripts/gke/manage_profile.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT core --resume-existing-ttl --owner topic24-platform --stage platform --output evidence/04_2_llm_design/gke/platform_install.json`.
  - Expected: fail-fast order is External Secrets/store/targets -> cert-manager/ingress/KEDA -> PostgreSQL/pgvector/Valkey/Redpanda/OpenSearch/ClickHouse -> Airflow/Feast/DataHub -> Prometheus/Loki/Tempo/Grafana/Alloy -> Langfuse -> Gateway API -> agentgateway -> cache verification -> llm-d -> Substrate -> kagent -> Agent Registry -> Jenkins.
- [ ] Run `rtk kubectl --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT -n edai2 get externalsecret,pods,statefulset,deployment,service,pvc -o wide`.
  - Expected: required ExternalSecrets Ready before consumers; all services private; requests/storage match render.
- [ ] Run `rtk kubectl --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT -n kagent get modelconfig,workerpool,pods -o wide`.
  - Expected: `default-model-config`, `edai2-comparison`, and `edai2-agents` exist; platform controllers Ready.
- [ ] Run `rtk kubectl --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT get gateway,httproute,grpcroute -A`.
  - Expected: private agentgateway routes only; llm-d not directly exposed.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --platform-inventory --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --private-endpoint-keys agentregistry_ui,grafana_ui,airflow_web,datahub_frontend,vault_status --require-private-endpoint-fields namespace,service_name,service_uid,service_port,target_port,selector_sha256,ready_endpoint_uids --output evidence/04_2_llm_design/gke/platform_install.json --strict`.
  - Expected: sanitized inventory binds release/chart/image/model/cache generations, capacity, retention, services, and readiness without secret payload. `private_endpoints` has exactly the five requested keys; every field is read back from the same context, every Ready endpoint UID list is nonempty, and the inventory records revision/time/SHA-256.
  - Note: `configs/gke/platform_service_bindings.json` does not exist pre-execution (chart sources for the five external charts are unrecorded; pre-execution discovery STOPPED per fail-closed rule). After the fail-fast install above, create it from live state with `rtk kubectl --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT get service -n edai2` and `-n vault`, mapping the five keys to the rendered UI/server Services (release names equal chart short names; `vault_status` binds the Vault server Service in `vault`), then run the inventory build command. Until the contract exists the build fails clean (exit 2, no file written).
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --verify-private-endpoint-inventory evidence/04_2_llm_design/gke/platform_install.json --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --expected-keys agentregistry_ui,grafana_ui,airflow_web,datahub_frontend,vault_status --strict`.
  - Expected: exact live Service UID/name/namespace/ports/selector hash and Ready endpoint UID read-back matches; absent, extra, stale, or mismatched inventory fails.

### Task 4: Prove platform exclusions and app boundary

- [ ] Run `rtk uv run pytest tests/integration/llm/test_gke_agents.py -q --live-gke --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT`.
  - Expected: gateway credential positive/negative matrix, two ModelConfigs, WorkerPool scale surface, storage prefixes, and controllers pass.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --verify-platform-exclusions evidence/04_2_llm_design/gke/platform_install.json --forbid bundled-postgres,bundled-valkey,rustfs,builtin-agents,builtin-tools,public-loadbalancer,app-sandboxagents --strict`.
  - Expected: exit 0; the five app-owned SandboxAgent renders exist only in unapplied bundles for Topic 25.

## Evidence and Screenshot Ownership

Topic 24 owns `platform_install.json` and `platform_capacity.json`. It owns no named screenshot. Later screenshots must link these machine records when they rely on platform readiness; a screenshot cannot replace them.

## Cleanup and Runtime Release

- [ ] Run `rtk uv run python scripts/gke/manage_profile.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT suspended --release-session-lease --owner topic24-platform --require-evidence-manifest evidence/04_2_llm_design/gke/platform_install.json`.
  - Expected: both pools zero, ingress disabled, no public forwarding rule, persistent PVC/GCS state retained.
- Ensure no transient Helm hook/prefetch pod remains.
- Do not uninstall persistent platform releases or delete cache/backups.
- [ ] Run and record `rtk git status --short --branch` as the final acceptance command.

## Rubric Traceability

| Cells | Topic 24 contribution | Final owner |
|---|---|---|
| `Sheet3!E3`, `Sheet3!E4`, `Sheet3!E6` | direct platform/model/ModelConfig proof owned here | Topic 32 reconciliation |
| `Sheet3!E5`, `Sheet3!E7:E26` | supporting runtime only | Topics 25-29 |
| `Sheet3!E35:E47`, `Sheet3!E50:E58` | supporting platform foundations | Topics 27/30 |

## Definition of Done

- [ ] Fixed hashes, predecessor evidence, budget, capacity, and explicit context pass.
- [ ] Platform installs in the exact fail-fast order with every consumer gated by secret readiness.
- [ ] Pinned private gateway/model/Substrate/kagent/registry/Jenkins state passes live tests.
- [ ] No app workload/agent resource, public service, mutable tag, bundled duplicate, or secret payload exists.
- [ ] Machine inventories are hash-bound and sanitized.
- [ ] Runtime is suspended and Topic 25 receives exact release/model/cache/context hashes and limitations.
- [ ] Final `rtk git status --short --branch` is recorded.

## Completion Record

- **Status:** Partial — STOPPED fail-fast at Step 1b (External Secrets store auth). First failure: `ClusterSecretStore/edai2-vault` Ready=False `InvalidProviderConfig` (Vault 400 on `PUT /v1/auth/kubernetes/login`: role `external-secrets` does not exist). Steps 2-14 never attempted. No platform readiness claimed. E3/E4/E6 unsatisfied.
- **Execution run 2026-10-07 ~18:36-19:15 UTC (Option A, muse concerto subagents, HEAD `1643f8d224f66e7ed078fce7cc1c7414780a0cd7` unmoved):** Wave 0 all green (42/42 static tests; 2/2 helm lints; kustomize pinned v0.7.0, no GPU/latest/secret/public; capacity render `13eb4149…` profile-shape PASS, per-node ceilings met by machine-type construction e2-highmem-4→3.4/24Gi + e2-standard-8→6.8/24Gi exactly at ceiling, aggregate/PVC deferred to live read-back; bundle FRESH spend ₫741000 age ~7h). Wave 1: backend `initialized` proof rotated (stale 11:46Z/b86297e → fresh 18:42:59Z/1643f8d) + stale runtime-binding rotated; gate exit 0 (`ok:true`, 43+7 perms, spend $28.18, forecast $0; preflight `9c46b2a5…`, forecast `6825a65a…`); lease `topic24-platform` acquired 18:46:06Z TTL 2h; Vault scaled 0→1, verified initialized + unsealed by gcpckms + raft + t=1/n=1, matching Topic 23. Wave 2: pools→core (platform 1, spot 1); ESO chart 0.20.2 rev 1 deployed 3/3 Running; store + 14 ExternalSecrets applied → store Ready=False (role missing), all 14 ES SecretSyncedError (consequence, not separate failures). Live read-back: no LoadBalancer, workload requests ≈ baseline (≤3.00 CPU/18Gi PASS), PVC 10Gi ≤80Gi PASS. Inventory BLOCKED (no live edai2 Services → bindings file cannot be truthfully built; capture refused clean, nothing fabricated). Live pytest 7 passed (conftest `gke_` defect did NOT reproduce — no test consumes the fixture). Suspend: vault sts→0 (PVC `data-vault-0` Bound + `vault-recovery` Secret kept), platform pool→0/0, spot resize→0 accepted but autoscaler-held 1/1; lease release refused (manifest absent) → lease file KEPT/HELD to 20:46Z.
- **Root cause (owning-local-topic defect, verified at source):** `infra/security/vault/kubernetes-auth.yaml` defines only 5 roles (retrieval/drift/coordinator/agentgateway/jenkins) — no `external-secrets` role; `infra/security/vault/policies/` has 5 policies, no external-secrets policy; `configure_vault.py` never writes the role. Secondary gap for after unblock: `infra/security/external-secrets/kagent-gateway-keys.yaml` never syncs `coordinator-to-specialist` (bound by `values/coordinator-agent.yaml`). Not patched under lease per live-lease rule.
- **Branch / revision:** `feature/implement-edai2` at `1643f8d` (unmoved). Tree: `M usage_ledger.json` (append-only obs #14-15, chain valid) + `?? gcp_preflight_topic24.json / cost_forecast_topic24.json / platform_capacity.json`. Nothing staged/committed/pushed.
- **Command / exit-code log:** static 42 passed exit 0; lints 0/0; render 0; backend-refresh 0; gate 0 (after 2 diagnosed rotations: stale proof FileExistsError, stale runtime-binding); cluster-info 0; lease acquire 0; vault scale+status 0; ESO helm 0; store/ES apply 0 (objects created, Ready=False live); capture exit≠0 missing-bindings (expected); pytest --live-gke 7 passed; suspend scales done; lease release exit≠0 manifest-missing (lease kept).
- **Evidence / SHA-256 log:** preflight `9c46b2a5…` ok:true; forecast `6825a65a…` $0; capacity `13eb4149…`; vault_bootstrap `9186fbac…` untouched; model_cache `67609f90…` untouched. `platform_install.json` NOT created. No secret payload printed or persisted at any point.
- **Screenshot QA:** No named screenshot owned, produced, or claimed.
- **Cleanup / runtime release:** vault 0/0, platform 0/0, spot 1/1 autoscaler-held (resize→0 accepted ×2, node replaced server-side); no Running hook/prefetch pods (pre-existing Failed prefetch Job retained, untouched); ESO rev-1 + 14 NotReady ES left as failure state for forensics (no delete); GCS/KMS/PVC/Terraform/proofs untouched.
- **Limitations:** (1) Store-auth defect blocks E3-E6; resume = owning topic adds least-privilege external-secrets policy + k8s role → `kubectl wait Ready clustersecretstore/edai2-vault` → continue steps 2-14 in order under same lease file (resume-existing-ttl) or rotated lease. (2) Lease `tmp/edai2-gcp/topic24-lease.json` HELD past close (TTL to 20:46Z); next session must resume-or-rotate, never run parallel. (3) Spot pool cannot reach 0/0 while ESO+system pods scheduled. (4) Proofs 900s/revision-bound; spend observation 24h-bound — refresh before next burst.
- **Handoff:** Topic 25 BLOCKED until store Ready + steps 2-14 + inventories recorded. Resume point: Step 1b. State: ESO 0.20.2 rev 1, vault sts rev-scale 0, platform 0/spot 1, lease held.

- **Status (run 2, 2026-10-08 ~02:10-02:45 UTC):** Partial — STOPPED at Step 1b activation. Phase-0 fix implemented locally + green (external-secrets.hcl 13 read-only paths, ConfigMap role entry, configure_vault.py idempotent role support; 9/9 new tests, 40/40 scoped suite) but CANNOT be activated live: no Vault admin path exists. Initial root revoked (Topic 23); sole recovery key cannot mint admin on unsealed Vault 2.0.4 (`generate-root`/`rekey` 403 unauthenticated; recovery-key submit no-op progress 0; only 5 least-privilege k8s roles). Re-bootstrap would destroy KV material + violate standing orders. Requires owning-topic decision (re-bootstrap authorization, 2.0.4-specific recovery, or surfaced admin token) — cargo-cult retries change nothing. "Scoped admin available" premise falsified by redacted live probe (names/status only, no secret material; temp helpers deleted).
- **Run-2 facts:** spend bundle refreshed to operator console ₫871000/₫871000/₫0 observed 02:10:43Z (trial to 10-25); proofs rotated (backend-initialized fresh, runtime-binding on forecast-SHA mismatch); gate exit 0 (preflight `b5a44a57…` ok:true 43+7 perms, forecast `2362dd1f…` spend ₫871000/$33.12 forecast $0); stale lease released + fresh lease acquired 02:17:57Z TTL 2h; vault 0→1 verified (gcpckms/raft/t=1/n=1, ClusterID `59a721b0-…`) then →0; pools→core then →0/0 (spot autoscaler-held 1, recorded); static 9+22 pass, 2/2 lints; store still `InvalidProviderConfig Ready=False`, 14 ES SecretSyncedError (unchanged); `platform_install.json` NOT created; lease release refused (manifest absent) → lease HELD to 04:17:57Z. Tree: `M usage_ledger.json` (append-only) + Phase-0 fix files (`M kubernetes-auth.yaml`, `M configure_vault.py`, `?? external-secrets.hcl`, `?? test_topic24_vault_role.py`) + `??` gate/capacity evidence. Nothing staged/committed/pushed; no deletions of persistent state.
- **Handoff (run 2):** Topic 25 BLOCKED. Resume point unchanged: Step 1b after owning-topic Vault-admin decision. Proofs 900s-bound, spend 24h-bound — refresh next burst.

- **Status (runs 3-8, finalize push 2026-10-08/09, HEAD `1643f8d` unmoved):** Partial — platform installed through observability; 4/5 seal Services live. Operator authorized Vault re-bootstrap with minimal study-only admin design (gitignored token at `tmp/edai2-gcp/edai2-study-admin-token.json`, edai2-admin policy with generate-root/rekey/seal denies, root revoked; accepted risk: token loss recoverable only by re-bootstrap). Re-bootstrap SUCCEEDED (fresh Raft, KMS auto-unseal, 7 policies incl external-secrets, 6 k8s roles incl external-secrets, auth/kubernetes/config host+CA+reviewer-JWT written, strict verify passed; old `vault_bootstrap.json` superseded, new SHA `453c8810…`). Local TDD fixes, all green: admin-token support + verifier allowlist (85/85), cert-manager values, full 19-chart pin catalog + per-chart values alignment (postgres/valkey/redpanda/opensearch/clickhouse/datahub/prometheus/loki/tempo/grafana/alloy/langfuse/jenkins), request tuning (CPU 6.76→2.66, mem 20.70→9.65Gi, machine-checked ceiling test), persistence tuning (PVC math 79Gi ≤80Gi), feast registry delivery (PATH-A secrets-mount + bundled no-auth redis + transformation disabled via real key), opensearch→2.38.0 re-pin (DataHub 1.1.6 expects 2.x; compat flag proven removed in 3.0), datahub ES http+auth, redpanda kafka-plaintext toggle, opensearch open-tier fallback (installer-Quit proven: any plugins.security.* key triggers it; Topics 27/31 re-harden TLS+auth).
- **Live state:** RUNNING — ESO, cert-manager, ingress-nginx, keda, postgres, valkey, redpanda (plaintext kafka), opensearch 2.19.6 (open tier), clickhouse (bitnamilegacy images), airflow (platform-DB wired), feast (feature-server + bundled redis), datahub (SQL bootstrapped via in-pod psql, system-update Completed, GMS/frontend/actions Running), prometheus, loki (emptyDir fix), tempo, grafana, alloy. BLOCKED at langfuse 2.1.4: chart needs `langfuse` role+DB in platform postgres (never provisioned) — same in-pod SQL-bootstrap pattern as datahub, NO values change needed. Tail unattempted: Gateway CRDs → agentgateway → cache proof → llm-d → substrate/kagent/registry → jenkins → seal. Bindings 4/5 live (`agentregistry_ui` absent — registry not installed); `platform_install.json` NOT created; live pytest 7/7 throughout. Suspended: vault 0/0 (PVC+recovery+token kept), pools 0/0-accepted with autoscaler remainder, no public LB.
- **Security disclosures (recorded, post-Complete hardening required):** (1) postgres secret `.data` map printed into transient tool output (base64 password; NOT in repo/evidence — verified by grep; owning topic to rotate post-Complete); (2) `application_default_credentials.json` OAuth refresh token printed into tool output (same scope; operator to revoke/refresh post-Complete). Keys-only/hashes-only discipline held everywhere else; no secret payload in repo or evidence.
- **Spend/gate:** bundle at ₫1000000/₫1000000/₫0 observed 2026-10-08T18:54Z — STALE after 2026-10-09T18:54Z; next burst needs fresh operator console values first. Proofs 900s/revision-bound (rotate at burst start). Lease file HELD past last suspend (release refused, manifest absent) — resume-or-rotate, never parallel.
- **Handoff:** Topic 25 BLOCKED. Resume point: langfuse SQL bootstrap (`CREATE USER/DB langfuse` via in-pod file-sourced passwords, datahub pattern) → `helm upgrade langfuse` → gateway stack → seal. State: all above Running; langfuse pending; vault 0/0; pools remainder; lease held.

- **Status (plan-authoring time):** Not started; no platform readiness claimed.
- **Branch / revision (plan-authoring time):** Record exact `rtk git status --short --branch`; none recorded.
- **Affected files (plan-authoring time):** None at plan-authoring time.
- **Command / exit-code log (plan-authoring time):** No execution commands recorded.
- **Evidence / SHA-256 log (plan-authoring time):** No capacity/install evidence recorded.
- **Screenshot QA (plan-authoring time):** No named screenshot owned.
- **Cleanup / runtime release (plan-authoring time):** No lease held by this plan artifact.
- **Limitations (plan-authoring time):** Application workloads, public routes, scaling, and rubric evidence remain unproved.
- **Handoff (plan-authoring time):** Block Topic 25 until private readiness/exclusion inventories and suspended release are recorded.


### FINALIZE strict run 2026-10-12: pre-lease compatibility safe stop

- **Status:** Partial. First failure is the approved local-preparation gate: pinned Substrate 0.0.6 cannot inject a Secret-backed password into the API server's external Valkey connection using its supported chart values. Live `valkey-cli PING` without credentials returns `NOAUTH Authentication required.` The API server render has no Redis password environment input or Secret envFrom; the chart exposes address/IAM/TLS controls only. No password was printed or decoded; no authentication downgrade, bundled store, chart substitution, or speculative workaround was applied.
- **Revision / pinned inputs:** HEAD `1643f8d224f66e7ed078fce7cc1c7414780a0cd7` on `feature/implement-edai2`; the two source hashes, rubric hash, model-cache file hash `67609f90...`, and current Vault bootstrap hash `453c8810...` match the FINALIZE brief. Existing unrelated work preserved; no stage/commit/push/branch/worktree action.
- **Local work / verification:** Read and rendered the exact downloaded chart packages, recording five OCI artifact digests in sanitized preparation evidence. `prepare_probe.py` exits 0 only when the incompatible rendered connection and live NOAUTH premise are reproduced. Baseline `tests/integration/llm/test_gke_agents.py`, `tests/unit/test_edai2_security_static.py`, `tests/unit/test_edai2_repository_contract.py`: 22 passed, exit 0. `git diff --check`: exit 0. No production chart/configuration or evidence-helper fix is claimed. The full six-suite static gate, Helm lints, complete capacity renders, budget refresh, fresh gate pair, lease acquisition, Langfuse SQL bootstrap, remaining installs, and sealing were not reached.
- **Evidence / SHA-256:** `platform_prepare_topic24.json` `cd8847ce257758a4e16e4d56639d574f3cbbcb68777318af8198e23dfade5be6`; `platform_cleanup_topic24.json` `e34c586b9911e05e508c02db072b61e8e51eba778168b1f52cb58294b3c13102`; replica restore record `0e84086746cc836ea0b51d0d339a53965d3022228820b53259a11c91ee93157e`. `platform_install.json` remains ABSENT; the old gate/capacity evidence, model cache, current/superseded Vault evidence, and bindings were not rewritten. No screenshot owned or created.
- **Cleanup ruling:** Requesting zero nodes exposed zero-disruption PDBs on the last node. To carry out the authorized runtime suspension without deleting PDBs/PVCs, 30 previously enumerated supporting Deployments/StatefulSets in `edai2` were scaled to zero; exact prior replica counts/UIDs are preserved in the gitignored restore record and sanitized cleanup proof. StatefulSet claim-retention read-back is Retain; all 10 PVCs remain Bound, totaling 71Gi. Vault remains 0/0; recovery Secret and gitignored study-admin token remain present. This costs runtime availability and the already accepted ephemeral telemetry loss; a resume MUST restore the saved supporting replicas before consumer checks.
- **Node-pool cleanup:** Explicit zero-node requests/read-backs and operation statuses are recorded in cleanup evidence. Kubernetes node count at read-back: 0. Autoscaling settings/remainders are recorded as measured, not described as zero without proof. Earlier scratch cleanup attempts used a deprecated zonal URL with an incompatible colon method and were rejected with HTTP 404; the corrected attempt uses the documented locations `:setSize` endpoint. Only sanitized errors/statuses were emitted.
- **Lease / spend:** No fresh lease acquired. The owner-matching expired Topic 24 lease is retained because no install manifest exists. Monetary observations remain stale; no timestamp was fabricated from the screenshot and no budget or permission pass is claimed. Before any new burst, obtain a current console/conversion observation, run the fresh exact six-hour gate, and rotate the expired lease as specified.
- **Handoff / resume:** Topic 25 stays BLOCKED; E3/E4/E6 are not claimed satisfied. Owning local Topic 18 must provide a reviewed secret-safe authenticated external-Valkey connection for pinned Substrate 0.0.6. Then finish the remaining local chart/schema/credential/capacity/evidence-helper repairs, pass all local gates, refresh budget/proofs, restore saved workloads and Vault under the sole Topic 24 lease, and resume at Langfuse SQL bootstrap. Existing residuals and the two transcript-only credential exposures remain queued for post-Complete hardening/rotation.
- **Final git status:**

```text
## feature/implement-edai2...origin/feature/implement-edai2
 M evidence/04_2_llm_design/gke/usage_ledger.json
 M evidence/04_2_llm_design/security/vault_bootstrap.json
 M infra/helm/edai2/releases.yaml
 M infra/helm/edai2/values/airflow.yaml
 M infra/helm/edai2/values/cert-manager.yaml
 M infra/helm/edai2/values/clickhouse.yaml
 M infra/helm/edai2/values/datahub.yaml
 M infra/helm/edai2/values/feast.yaml
 M infra/helm/edai2/values/grafana.yaml
 M infra/helm/edai2/values/jenkins.yaml
 M infra/helm/edai2/values/langfuse.yaml
 M infra/helm/edai2/values/loki.yaml
 M infra/helm/edai2/values/opensearch.yaml
 M infra/helm/edai2/values/postgres.yaml
 M infra/helm/edai2/values/prometheus.yaml
 M infra/helm/edai2/values/redpanda.yaml
 M infra/helm/edai2/values/tempo.yaml
 M infra/helm/edai2/values/valkey.yaml
 M infra/kustomize/llmd/overlays/cpu/patch-primary.yaml
 M infra/security/vault/kubernetes-auth.yaml
 M scripts/gke/configure_vault.py
 M scripts/qa/capture_edai2_evidence.py
 M tmp/edai2-plan/execution-v1/gcp/24-compact-platform-install.md
?? configs/gke/platform_service_bindings.json
?? evidence/04_2_llm_design/gke/cost_forecast_topic24.json
?? evidence/04_2_llm_design/gke/gcp_preflight_topic24.json
?? evidence/04_2_llm_design/gke/platform_capacity.json
?? evidence/04_2_llm_design/gke/platform_cleanup_topic24.json
?? evidence/04_2_llm_design/gke/platform_prepare_topic24.json
?? evidence/04_2_llm_design/security/vault_bootstrap.superseded-2026-10-07.json
?? infra/feast-registry/
?? infra/security/external-secrets/opensearch.yaml
?? infra/security/vault/policies/edai2-admin.hcl
?? infra/security/vault/policies/external-secrets.hcl
?? tests/unit/test_topic24_airflow_local.py
?? tests/unit/test_topic24_capacity_ceilings.py
?? tests/unit/test_topic24_cert_manager_values.py
?? tests/unit/test_topic24_datahub_opensearch_local_auth.py
?? tests/unit/test_topic24_feast_datahub_local.py
?? tests/unit/test_topic24_feast_local_registry_fix.py
?? tests/unit/test_topic24_helm_images.py
?? tests/unit/test_topic24_loki_writable_storage.py
?? tests/unit/test_topic24_opensearch_password.py
?? tests/unit/test_topic24_redpanda_kafka_plaintext_local.py
?? tests/unit/test_topic24_releases_catalog.py
?? tests/unit/test_topic24_vault_role.py
```


### FINALIZE remote-build preparation 2026-10-12T17:07:14.195157+00:00: capacity safe stop

- **Status:** Partial; Topic 25 remains BLOCKED. User-adopted six-hour heavy-work-on-GCP plan supersedes older two-hour/simplified directions. No cloud lease was acquired and no installation/build/publish was attempted.
- **Revision/branch:** `1643f8d224f66e7ed078fce7cc1c7414780a0cd7` / `feature/implement-edai2`; unchanged. All five pinned source/rubric/cache/Vault hashes matched at entry. No stage, commit, push, branch/worktree creation, local Docker, Cloud Build, new VM/repository, or persistent-state deletion.
- **First blocking gate:** corrected pinned-chart renders request **3.210 CPU > 3.000 CPU**. This is a lower bound: five Substrate workloads (seven containers) omit CPU/memory requests, and generated gateway/WorkerPool workloads and installation phases still need accounting. Do not claim complete capacity, readiness, or increase caps. Actual PVC baseline is 10 Bound claims / 71 GiB; Jenkins adds 8 GiB, yielding 79/80 GiB without any orphan subtraction/deletion.
- **Local changes:** catalog records seven verified OCI chart artifacts including matching CRD charts; kagent uses supported external-database/bundled-component controls and the pinned worker image; ModelConfigs remain `edai2` without unsupported `contextTokens` (4096 stays in llm-d); WorkerPool remains `kagent` with actual `ateomImage`. Registry disables bundled PostgreSQL, explicitly pins the chart's server image 0.2.1, maps its JWT key, and prepares a Secret-backed external URL using Registry's existing app credential rather than copying PostgreSQL admin credentials. Registry Helm MUST use `scripts/gke/topic24_postrender.py`; its nonsecret validation marker is not a deployable connection string.
- **Commands/exits:** prescribed six static suites plus new regression files: **55 passed / 2 failed / 0 errors**, exit 1; failures are CPU ceiling and missing remaining resource bounds. Focused latest preparation/post-render tests: **10 passed**, exit 0. Explicit-context image-hook regression: **1 passed**, exit 0. Both Helm lints exit 0 (default invocation warns that image.tag needs workload values); CPU Kustomize render exit 0; git diff --check exit 0. Earlier renderer namespace defect was reproduced and repaired before the final run.
- **Fresh review:** Registry role/database/ownership/password bootstrap is still REQUIRED before installation; this is the pending runtime SQL step, not a fulfilled readiness claim. Use the existing Registry app credential only inside the PostgreSQL Pod through a Secret-backed input; do not read/decode it on the PC. The stock kagent chart's hosted `kagent/default-model-config` still requires private replacement/filtering. Consumer installation remains blocked by the failed preparation gate.
- **Evidence:** `evidence/04_2_llm_design/gke/platform_prepare_topic24_remote_build.json` SHA-256 `07e27f9f1414774f9931fe396ddc30aa3581894c4c8c9faa182352b9ae88c256`; sanitized source/proof hashes, OCI artifacts, and checks recorded there. Static JUnit SHA `24603e6173fef56c97494f849bd9ce5034600933976a54c17e7cd0dcd4a6aec4`; fresh cleanup read-back SHA `efad1cf58a9a2e9464405a6cb1fac769b93134f22b7cb6755e7a3ac9f3fe88da`. Existing budget, preparation, cleanup, model-cache, and Vault proof files were not replaced; `platform_install.json` remains absent. Monetary bundles were not refreshed because the budget stage was not reached; no observation/conversion timestamp was fabricated.
- **Cleanup:** fresh read-back `2026-10-12T17:00:06.191010+00:00`: both managed-group targets 0, Kubernetes nodes 0, Vault desired replicas 0; all 10 PVCs Bound (71 GiB), recovery Secret and gitignored admin-token file retained. No owned hook/build/test runtime or temporary IAM binding was created. Existing expired Topic 24 lease is retained unchanged because no sealing manifest exists. Ruling: read-back-only cleanup is sufficient here because the run created no cloud runtime and suspension was already achieved; no unnecessary pre-gate cloud mutation.
- **Resume:** first fit complete, nonzero resource accounting inside unchanged 3 CPU/18 GiB/80 GiB caps. Then finish the listed Substrate, Vault Agent/provider, gateway, database/bootstrap, and strict collector repairs; require all local gates before refreshing budget/permissions and acquiring the one six-hour lease. Restore supporting replicas from the saved 30-workload UID/replica record only after build/test cleanup. Accepted residuals and both prior credential exposures remain pending post-Complete hardening. Topic 25 stays BLOCKED.
- **Final Git status:** `## feature/implement-edai2...origin/feature/implement-edai2`; full status recorded at ignored `tmp/edai2-gcp/topic24-finalize/final-git-status.txt` SHA `c4ed08ccfc755b3251edb8da6c2a19e41b9880f047caa6caab9f1c3be731819b`. Existing dirty work preserved; nothing staged/committed/pushed.


### Completion Record — 2026-10-14 first GCP finalization attempt

- **Status:** Partial; Topic 25 remains blocked. Required source, live installation, model inference and strict sealing proof are not yet complete.
- **Revision/branch:** `1643f8d224f66e7ed078fce7cc1c7414780a0cd7` / `feature/implement-edai2`; no staging, commit, push, branch or worktree changes. Heavy work ran on GKE without local Docker.
- **Approved change:** cumulative regular and Spot node-hour ceilings are now 130 each, explicitly approved by the user. Monetary caps remain $240 / $180; machine types, at most one node per pool and six-hour lease are unchanged.
- **Preparation/gates:** six prescribed suites 48 passed; focused regressions 110 passed; budget helper regression run 113 passed. Both Helm lints, CPU Kustomize render and Terraform IAM formatting passed. Projected steady 4.610 CPU / 14.764 GiB; install peak 4.795 CPU / 17.139 GiB; projected PVC 79 GiB. Fresh human gross-spend confirmation is rounded ₫2.04M. Exact budget command exits zero with `ok:true`; separate measured node-hour/storage gate passes the approved ceilings.
- **GCP results/first failure:** both Go package suites passed in the one-CPU/four-GiB build Job. `ko` then exited 1 because the prepared wrapper combined `GOOS=linux` with `--platform=linux/amd64`. No image was published. A separate internal-kernel diagnostic used an unavailable private entrypoint; it does not prove unsupported hardware. The real-cache model feasibility Pod was stopped before inference proof. No remaining platform component was installed or declared Ready.
- **Cleanup:** actual nodes and both MIG targets are zero; Vault is zero; all 10 PVCs remain Bound (71 GiB). Owned build/probe runtime and its repository writer grant were removed. Existing PVCs, GCS, KMS, model cache, Terraform state and historical proofs were preserved. The lease acquired `2026-10-13T17:01:48.042641+00:00` is retained because `platform_install.json` is legitimately absent.
- **Evidence:** `evidence/04_2_llm_design/gke/platform_execution_topic24_20261014.json` SHA-256 `2ebba816223eaf359316252f46976148d6996f7734b00456d37c4996ec6d8d1b`; sanitized commands/results and artifact hashes are linked there. Cleanup SHA-256 `9370724525393142bf475539b8391b8c12c69d836804e96487ac0086a233567e`. Final attempt Git status is saved under the ignored execution directory; SHA-256 `54500acbf107c24f2f969b596290a97d9eced77968ee007ec550976f98d15ffd`.
- **Resume:** reviewed command correction removes GOOS/GOARCH only before ko. Await the explicit user exception before applying it or retrying within the unchanged original lease deadline. If not approved, remain suspended and Partial. Accepted residuals and both prior credential exposures remain in the post-Complete rotation handoff.


### Completion Record — corrected build and cache probe, 2026-10-14

- **Status:** Partial for this attempt; Topic25 remains blocked pending resume.
- **Build:** Both Go packages passed and the pinned API image was published as `sha256:92d849837483d6ebe0f9bbfe74b0a068edacbc6714e63c014cad69926cce1a4b`; remote outputs, SBOM and completed Job provenance retained.
- **First failure:** CPU cache initializer exited1 because the ConfigMap filename was `model-cache-manifest.json` while it reads `model_cache.json`. Missing generated ConfigMap namespace also reproduced; misplaced default-namespace copies removed. This is not evidence of an unsupported CPU.
- **Cleanup:** zero nodes and managed-group targets, Vault0, all10 PVCs Bound (71Gi), temporary builder IAM grant removed. See `evidence/04_2_llm_design/gke/platform_cache_attempt_topic24_20261014.json` for artifact hashes. Lease retained and later expired; inventory absent.
- **Resume authorization:** user approved the two-line namespace/key correction and one model-probe/resume, then explicitly requested continuing with a fresh billing screenshot after the prior lease expired. The successful API image will be reused.
- **Historical metadata limitation:** regenerating builder preparation metadata changed its preparation timestamp; the earlier preparation hash remains historical. Source bundle bytes/hash, first failed Job evidence and successful build outputs are retained; no old timestamp is reconstructed.


### Completion Record — Langfuse manifest type correction, 2026-10-14

- **Attempt status:** Partial pending approved resume. CPU model feasibility passed real 8-token completion plus model-list and missing-auth rejection; cache initialization exited0. PostgreSQL roles/databases, Vault store and20 fresh ExternalSecrets verified.
- **First installation failure:** Langfuse2.1.4 rejected numeric environment value `LANGFUSE_S3_MEDIA_UPLOAD_MAX_CONTENT_LENGTH`; same setting explicitly as string passes server-side dry-run for both Deployments. Helm4 requires named post-renderer plugin; reviewed renderer packaged locally and verified through Registry Secret-ref render.
- **Corrections:** User explicitly approved bounded CLI/YAML compatibility corrections and resume with versions/credentials/resources/budget unchanged. Langfuse supported string value and Vault CLI role-key list parsing regressions reproduced3 failures, then47 focused tests passed. Capacity recomputed4.795CPU/17.138672Gi peak,79Gi projectedPVC.
- **Cleanup:** Verified2026-10-14T06:02:19.581172+00:00;0 nodes, both MIG targets0,Vault0,10 PVCs Bound, temporary builder repo grant absent. SHA256 cleanup `23ee5434a0b82761e9da918c74a8705f842376af7ab05851b0e6d94ad2641041`. Lease remains original05:21:57UTC acquisition; stopnewwork10:51:57UTC,expiry11:21:57UTC. Topic25 remains blocked until final installation/seal/cleanup.


### Completion Record — Langfuse credential gate, 2026-10-14

- **Status:** Partial; Topic 25 blocked. Bounded CLI/YAML fixes approved; separate single-key repair approval pending. No key repair executed.
- **Verified progress:** Substrate build and real CPU model feasibility passed; 42 restored workload identities, Vault rotating reviewer, 20 fresh ExternalSecrets and three PostgreSQL Service credentials verified. Langfuse PostgreSQL migrations passed. String environment value and single-node ClickHouse setting passed 48 focused tests and Deployment server dry-runs. Helm revision 3 deployed after desired replicas became zero, so it is not live readiness proof.
- **Blocker:** Langfuse encryption key is 48 hex characters; required format is 64. Exact counts found 73 non-seed tables empty. Prepared in-pod repair changes only this key and verifies historical version and other fields preserved.
- **Cleanup:** Verified 2026-10-14T06:33:52.715551+00:00; zero Kubernetes nodes and MIG targets, Vault zero, all 10 PVCs Bound (71 GiB), temporary builder Writer grant absent. Persistent state preserved. Lease retained; stop-new-work 10:51:57 UTC / expiry 11:21:57 UTC unchanged.
- **Evidence:** `evidence/04_2_llm_design/gke/platform_langfuse_gate_topic24_20261014.json` contains sanitized hashes, cleanup and final Git status. No staging/commits/push/branches/worktrees. Accepted residuals and both prior exposures remain in post-Complete rotation handoff.


### Completion Record — user-requested pause at ClickHouse compatibility blocker, 2026-10-14

- **Status:** Partial; Topic 25 blocked. User requested a planning handoff and temporary stop. No further installation/research after handoff preparation; in-progress suspension completed.
- **Passed:** approved Langfuse key repair (Vault version 1 retained, version 2 valid32-byte key; salt/nextauth unchanged), 20 fresh ESO targets, restored controller/application UIDs, PostgreSQL/Valkey/ClickHouse readiness. Six static suites48PASS and final focused/security83PASS; lints2/render/diffcheckPASS.
- **First failure:** Langfuse chart2.1.4 installs app4.50.0, which requires ClickHouse>=25.12; retained server25.7.5 lacks enable_full_text_index. Migration39dirty, events_full absent. No marker forced, schema deleted or server version changed. Earlier image-only official ClickHouse swap was incompatible; a proper adapter/probe/backup requires a concrete plan and version exception.
- **Readiness limitation:** Helm revision4 eventually reported deployed after suspension reduced desired replicas0; this does not establish Langfuse readiness. Remaining gateway/model/agent/Jenkins installation and strict inventory are incomplete.
- **Cleanup:** verified 2026-10-14T11:51:47.066974+00:00;0nodes,bothMIGtargets0,Vault0,10BoundPVCs71Gi retained,temporarybuildergrantabsent. Persistent state preserved. Lease11:22:26UTC retained, stopnewwork16:52:26UTC/expiry17:22:26UTC, not extended by pause.
- **Evidence:** `evidence/04_2_llm_design/gke/platform_langfuse_clickhouse_blocker_topic24_20261014.json` SHA256 `03d74ceca868e9c085bc0d36179450074d47a96a34128dd1beda13216ad6048f`; contains sanitized proof hashes and final Git status. No staging/commits/push/branches/worktrees. Handoff: `tmp/edai2-gcp/topic24-finalize/NEXT_SESSION_HANDOFF.md`. Accepted residuals and both prior credential exposures remain pending post-Complete rotation.


### Completion Record — approved finalization run, 2026-10-14 (lease EXPIRED 17:22:26Z; seal incomplete)

- **Status:** Partial; Topic 25 blocked. All remaining installs completed; strict inventory verified; single seal gate incomplete — authenticated primary-model completion through the gateway.
- **Revision/branch:** `1643f8d224f66e7ed078fce7cc1c7414780a0cd7` / `feature/implement-edai2` unmoved; no staging, commit, push, branch or worktree actions. Heavy work on GKE only; no local Docker.
- **Live results:** Substrate 0.0.6 rev2 deployed in edai2 (pinned digest verified; root cause of rev1 failure: node service account had no IAM roles -> 403 AR pull; fixed with repo-scoped artifactregistry.reader + applying the missing substrate-api-env ConfigMap). Kagent 0.9.9 + CRDs + model-configs + WorkerPool/ScaledObject deployed (exactly two ModelConfigs in edai2; WorkerPool 1/1, ScaledObject 1-2). Agent Registry 0.3.3 rev2 (server 0.2.1, Recreate, Secret-backed envs, marker absent) after: stale ExternalSecret re-applied with -n edai2; Vault registry session-seed repaired from 24 to 32 bytes (Ed25519) via append-only kv patch (v1->v2, other fields preserved, no value printed); non-trusted `vector` extension pre-created by the PostgreSQL superuser inside the agentregistry database. Jenkins 5.9.68 deployed (+8Gi PVC, 79Gi total <=80Gi). The missing `AgentgatewayParameters edai2/edai2-private-gateway` was applied (prior session skipped it; controller had errored since ~14:07Z), creating the private proxy Service. Airflow webserver crash loop (64 restarts) repaired with a bounded startupProbe threshold patch 6->18.
- **Seal evidence:** `evidence/04_2_llm_design/gke/platform_install.json` built strict (exit 0) and verified — inventory (`--verify-private-endpoint-inventory`) and exclusions (`--verify-platform-exclusions`) both PASS, five bindings/seven fields, ready endpoints nonempty, sanitized. 7/7 live contract tests PASS. Six-suite static gate 48/48 PASS (JUnit `seal-six-suite-20261014T1750Z.xml`). Probe namespace `edai2-clickhouse-probe` deleted. Closed node-hours after suspension: platform 130.742 / spot 128.965 <=131 (`envelope-usage-recompute-20261014T1800Z.json`).
- **First failure (seal gate):** auth matrix = 20/20 foreign-key denials 401 + 10/10 missing/invalid 401 PASS, but only 4/5 allowed: the model route's own correct key returns 401 at the backend. Verified empirically: the gateway accepts and proxies to llm-d, the route key is byte-identical to VLLM_API_KEY, a DIRECT llm-d call returns HTTP 200 with a real completion ("OK"), but agentgateway consumes the client Authorization header and `backend.auth.passthrough: {}` does not forward it upstream in 1.3.1. Fix deferred to next lease: static backend credential on auth-model-route (bounded policies.yaml change) + re-run matrix. Sanitized proof `tmp/edai2-gcp/topic24-finalize/seal-auth-matrix.json` (no key values).
- **Cleanup:** verified suspension 2026-10-14 ~17:50Z: Kubernetes nodes 0; both MIG targets 0; Vault desired replicas 0; all 11 PVCs Bound (79Gi) retained; no public LoadBalancer; restart record for 54 owned workloads in `key-repair-resume-20261014/cleanup-progress.json` (11:51Z proof preserved separately). Lease expired 17:22:26Z and was not extended; no new work ran after expiry except the mandated suspension and read-only evidence.
- **Local changes:** `scripts/qa/capture_edai2_evidence.py` (named-targetPort resolution from backing Pods, fail-closed; `_require_topic24_target` clean exit-2 instead of Path(None) crash — repairs a pre-existing failing CLI test), `configs/gke/platform_service_bindings.json` (5th binding agentregistry_ui), `tmp/edai2-gcp/topic24-finalize/remote-build-output/remote-tool-versions.txt` (ko version line normalized to the canonical command-labeled shape), plus new tmp evidence files. `uv run python -m pytest` is REQUIRED for the suites (plain `uv run pytest` cannot import scripts.gke — no `__init__.py`).
- **Evidence:** JUnit/summary files under `tmp/edai2-gcp/topic24-finalize/`: `seal-live-gke-agents.xml`, `seal-live-tests-summary.json`, `seal-auth-matrix.json`, `seal-six-suite-20261014T1750Z.xml`, `registry-jwt-seed-repair-result.json`, `envelope-usage-recompute-20261014T1800Z.json`. Full handoff with rulings and resume steps: `tmp/edai2-gcp/topic24-finalize/session-handoff-20261014T1800Z.md`.
- **Handoff:** Topic 25 BLOCKED until: new lease + refreshed gates; model-route backend credential fix; auth matrix 5/5; fresh inventory capture + both verifiers (no pod churn between capture and verify — the cache-provenance check execs the stored pod name); capacity re-measure; then lease release with the manifest. Accepted residuals (stock kagent/default-model-config in ns kagent; llm-d pod churn ~16:37Z unexplained; both prior credential exposures) remain for post-Complete handling.

### Completion Record — Topic 24 Complete, 2026-10-15 (fresh lease 18:26:30Z, released after seal)

- **Status:** Complete; Topic 25 unblocks. All installs, live verification, strict sealing, and cleanup pass. No staging, commits, pushes, branches, or worktrees. Heavy work on GKE only.
- **Revision/branch:** `1643f8d224f66e7ed078fce7cc1c7414780a0cd7` / `feature/implement-edai2` unmoved.
- **Approved changes:** cumulative ceilings 150/150 (`configs/gke/cost_envelope.yaml` + `tests/unit/test_edai2_repository_contract.py` 131→150, monetary caps $240/$180 unchanged, 1+1 nodes unchanged); fresh serial `topic24-platform` lease 2026-10-14T18:26:30Z TTL 6h (old expired 17:22:26Z released via manifest, no overlap); bounded manifest fixes preserving versions/credentials/resources/budget.
- **Gates:** envelope 150/150 with ledger entries (counts 33→34, monetary_gate_ok true, chain valid); preflight/forecast reports ok:true reused fresh (<24h, observed 11:03:59Z); suspension pre-run verified 0 nodes / MIG 0/0 / Vault 0 / 11 PVCs Bound 79Gi; closed hours recomputed 130.742/128.965 ≤150 (`envelope-usage-recompute-20261015T0130Z.json`, 254 events, within-envelope true).
- **Restore (Phase 1):** 54/54 workloads scaled to saved replicas with 0 UID mismatches (Vault 77ff0077… verified, 0→1, unsealed Raft t=1/n=1); platform pool 0→1 (Ready), spot 0→1 (Ready); 20/20 ESO SecretSynced True; Langfuse web+worker 1/1.
- **Fix (Phase 2):** `infra/agentgateway/edai2/policies.yaml` `auth-model-route` backend `passthrough: {}` → `secretRef: {name: kagent-model-route-key}`; `infra/security/external-secrets/kagent-gateway-keys.yaml` added `Authorization` key mapping same Vault `model-api-key` (bounded, same credential); `tests/integration/llm/test_gke_agents.py` updated to assert secretRef. Red-test pre-fix 401 reproduced; post-fix policy ACCEPTED Valid / ATTACHED (PartiallyValid message `missing Authorization value` resolved after ESO sync).
- **Live proof (Phase 3):** port-forward 127.0.0.1:18080; 25-pair matrix 5 allowed (1×200 + 4×500 mcp/a2a Topic 25 backends acceptable) / 20 denied 401; missing 5/5 401; invalid 5/5 401; anomalies 0; real primary-model completion 200 `OK` through gateway (`seal-auth-matrix-20261015.json`, no key values).
- **Seal (Phase 4):** fresh strict `platform_install.json` built exit 0 (5 bindings, 7 fields); `--verify-private-endpoint-inventory` exit 0 + `--verify-platform-exclusions` exit 0 same shot, zero pod churn; 7/7 live contract tests pass; six-suite 48/48 pass via `uv run python -m pytest` (362s).
- **Close (Phase 5):** owned capacity 4.360 CPU ≤5 / 14.389Gi ≤18 / 79Gi ≤80; suspended 54/54 to 0 (`suspend-20261015.json`), MIG 0/0, nodes 0, Vault 0/0, 11 PVCs Bound 79Gi; lease released with manifest; closed hours recomputed platform 131.369 / spot 129.538 ≤150 (`envelope-usage-recompute-20261015Tclose.json`, 258 events, within-envelope true); ledger count 34.
- **Evidence:** `evidence/04_2_llm_design/gke/platform_install.json` (fresh), `tmp/edai2-gcp/topic24-finalize/seal-auth-matrix-20261015.json`, `envelope-usage-recompute-20261015T0130Z.json`, `envelope-usage-recompute-20261015Tclose.json`, `suspend-20261015.json`, `usage_ledger.json` (34 obs).
- **Rulings:** same-checkout no-worktree/no-commit override per user plan; pools-before-workloads restore order (nodes needed to schedule); test ceiling 131→150 as bounded fix; exclusions verifier needs explicit kubeconfig/context (plan omits, script requires); platform_install.json delete-then-capture for fresh seal (untracked evidence); Authorization key mapping as bounded credential-preserving fix for CRD `Authorization`-key requirement.
- **Residuals carried (not fixed):** stock `kagent/default-model-config` in ns kagent; `substrate-crds` in substrate-system; two historical transcript credential exposures queued for post-Complete rotation.
