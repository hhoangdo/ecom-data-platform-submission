# Topic 24: Compact GKE Platform Installation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

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

- Read and obey `C:\Users\oou1hc\.codex\RTK.md`; prefix every shell command with `rtk`.
- Fixed source hashes: Section 03 `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`; EDAI2 `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`; rubric at `tmp/rubic-check/Coursework Tracking (Public).xlsx` `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- Prefix every shell command with `rtk`; no branch/worktree/stage/commit changes.
- Consume the completed local implementation. If a source/IaC/chart defect appears, capture it, release or suspend any owned runtime, mark this topic `Partial`, and return it to the owning local topic; do not patch implementation during a live cloud lease.
- Require explicit context `gke_${GOOGLE_CLOUD_PROJECT}_us-central1-a_edai2` before every live block.
- Require `EDAI2_GKE_KUBECONFIG=tmp/edai2-gcp/kubeconfig` and `EDAI2_GKE_CONTEXT=gke_${GOOGLE_CLOUD_PROJECT}_us-central1-a_edai2`. Every `kubectl` call includes `--kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT`; every Helm call includes `--kubeconfig $env:EDAI2_GKE_KUBECONFIG --kube-context $env:EDAI2_GKE_CONTEXT`; every script that queries or mutates Kubernetes receives both values. Never use or change the default kubeconfig/current context.
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

- [ ] Run `rtk uv run python scripts/gke/check_budget.py --project $env:GOOGLE_CLOUD_PROJECT --billing-account-env GOOGLE_BILLING_ACCOUNT --budget-notification-target-env EDAI2_BUDGET_NOTIFICATION_TARGET --recovery-sink-env EDAI2_VAULT_RECOVERY_SINK --recovery-sink-attestation $env:EDAI2_RECOVERY_SINK_ATTESTATION --required-permissions configs/gke/required_permissions.json --dns-probes acme-staging-v02.api.letsencrypt.org,huggingface.co,storage.googleapis.com --live-external-preflight --preflight-output evidence/04_2_llm_design/gke/gcp_preflight_topic24.json --trial-expires-at $env:EDAI2_TRIAL_EXPIRES_AT --current-spend-usd $env:EDAI2_CURRENT_SPEND_USD --spend-observed-at $env:EDAI2_SPEND_OBSERVED_AT --usage-ledger evidence/04_2_llm_design/gke/usage_ledger.json --envelope configs/gke/cost_envelope.yaml --requested-profile core --requested-ttl 2h --output evidence/04_2_llm_design/gke/cost_forecast_topic24.json`.
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

- **Status:** Not started; no platform readiness claimed.
- **Branch / revision:** Record exact `rtk git status --short --branch`; none recorded.
- **Affected files:** None at plan-authoring time.
- **Command / exit-code log:** No execution commands recorded.
- **Evidence / SHA-256 log:** No capacity/install evidence recorded.
- **Screenshot QA:** No named screenshot owned.
- **Cleanup / runtime release:** No lease held by this plan artifact.
- **Limitations:** Application workloads, public routes, scaling, and rubric evidence remain unproved.
- **Handoff:** Block Topic 25 until private readiness/exclusion inventories and suspended release are recorded.
