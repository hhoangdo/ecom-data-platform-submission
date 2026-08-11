# 18 — Compact Platform Helm and llm-d Kustomize

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement and statically render Task 8's pinned private platform: supporting Helm catalog/values, Topic 16-owned service-agent/worker chart consumption, agentgateway, kagent/Substrate, ModelConfigs, WorkerPool, Agent Registry, ExternalSecret consumption, and llm-d CPU Kustomize.

**Architecture:** Helm owns supporting services; Topic 16 exclusively owns reusable workload primitives; pinned Kustomize owns llm-d CPU. Platform services remain ClusterIP. ExternalSecrets are created by Topic 17 and consumed via existingSecret references. App-owned agent values from Topic 14 render through Topic 16 charts here but are deployed only in Task 9.

**Tech Stack:** Helm, Kustomize, Kubernetes/Gateway API, agentgateway 1.3.1, kagent 0.9.9, Substrate 0.0.6, Agent Registry 0.3.3, llm-d v0.7 CPU, pytest.

## Metadata

| Field | Locked value |
|---|---|
| Phase | Local/static platform Topic 18 |
| Source task | `tmp/edai2-plan/04.2_llm_design.md` Task 8 static portion |
| Sheet3 support | `Sheet3!E3:E7`, `Sheet3!E41:E47` |
| Predecessor Completion Record | `tmp/edai2-plan/execution-v1/local/17-terraform-vault-iac-static.md` must be `Complete` |
| Blocked successor | `tmp/edai2-plan/execution-v1/local/19-workload-charts-streaming-keda-experiments.md` |
| Runtime ownership | Local Helm/Kustomize rendering only |
| Class | Local/static; no cluster mutation or GKE credit |

## Locked planning basis

Read `C:\Users\oou1hc\.codex\RTK.md`; verify `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`, `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`, and `tmp/rubic-check/Coursework Tracking (Public).xlsx` `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.

## Global constraints

Current branch/serial session, `apply_patch`, `rtk uv run` developer recipes, and `rtk make` operator recipes. Topic 08 owns baseline dependencies; run `rtk uv lock --check` and treat a missing prerequisite as a `Partial` predecessor defect instead of editing dependencies. Do not stage/commit, apply Helm/Kustomize/kubectl, edit Topic 16 chart templates, pull models/images, invoke GCP, auto-prune/stop Docker, or create secrets. One retry then `Partial`.

## Read-only current-state refresh

- [ ] Run `rtk git status --short --branch`. Expected: branch/changes recorded.
- [ ] Run `rtk proxy certutil -hashfile tmp/edai2-plan/03_data_generator_improvement.md SHA256`. Expected: output contains `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`.
- [ ] Run `rtk proxy certutil -hashfile tmp/edai2-plan/04.2_llm_design.md SHA256`. Expected: output contains `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`.
- [ ] Run `rtk proxy certutil -hashfile "tmp/rubic-check/Coursework Tracking (Public).xlsx" SHA256`. Expected: output contains `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- [ ] Run `rtk proxy powershell -NoProfile -Command "Select-String -Path tmp/edai2-plan/execution-v1/local/17-terraform-vault-iac-static.md -Pattern '^Status: Complete|\| Status \| Complete \|'"`. Expected: completed predecessor.
- [ ] Run `rtk uv lock --check`. Expected: exit 0 with the Topic 08-owned baseline lockfile unchanged.
- [ ] Run `rtk git diff --check`. Expected: exit 0.

## Scope and non-goals

In scope: immutable release catalog, supporting values, consuming/linting Topic 16 reusable charts, gateway policies/routes, ModelConfigs/WorkerPool, CPU overlays, local template/render and static security/integration tests.

Non-goals: Helm/kubectl apply, CRD installation, model prefetch, GKE readiness, secret generation, app deployment, live ingress, screenshots.

## Exact file map

| Action | Exact path | Responsibility |
|---|---|---|
| Create | `infra/helm/edai2/releases.yaml` | Immutable chart/image/version catalog |
| Create | `infra/helm/edai2/values/airflow.yaml`, `infra/helm/edai2/values/feast.yaml`, `infra/helm/edai2/values/postgres.yaml`, `infra/helm/edai2/values/valkey.yaml`, `infra/helm/edai2/values/redpanda.yaml`, `infra/helm/edai2/values/datahub.yaml`, `infra/helm/edai2/values/opensearch.yaml`, `infra/helm/edai2/values/substrate.yaml`, `infra/helm/edai2/values/kagent.yaml`, `infra/helm/edai2/values/agentgateway.yaml`, `infra/helm/edai2/values/agentregistry.yaml`, `infra/helm/edai2/values/jenkins.yaml`, `infra/helm/edai2/values/vault.yaml`, `infra/helm/edai2/values/external-secrets.yaml`, `infra/helm/edai2/values/ingress-nginx.yaml`, `infra/helm/edai2/values/cert-manager.yaml`, `infra/helm/edai2/values/keda.yaml`, `infra/helm/edai2/values/prometheus.yaml`, `infra/helm/edai2/values/loki.yaml`, `infra/helm/edai2/values/tempo.yaml`, `infra/helm/edai2/values/grafana.yaml`, `infra/helm/edai2/values/alloy.yaml`, `infra/helm/edai2/values/langfuse.yaml`, `infra/helm/edai2/values/clickhouse.yaml` | Private compact platform resources, retention and existingSecret refs |
| Consume | `infra/helm/edai2/service-agent/Chart.yaml`, `infra/helm/edai2/service-agent/values.yaml`, `infra/helm/edai2/service-agent/templates/deployment.yaml`, `infra/helm/edai2/service-agent/templates/service.yaml`, `infra/helm/edai2/service-agent/templates/scaledobject.yaml`, `infra/helm/edai2/service-agent/templates/networkpolicy.yaml`, `infra/helm/edai2/service-agent/templates/serviceaccount.yaml`, `infra/helm/edai2/service-agent/templates/sandboxagent.yaml`, `infra/helm/edai2/service-agent/templates/remotemcpserver.yaml`, `infra/helm/edai2/service-agent/templates/agentgateway-policy.yaml` | Topic 16-owned reusable app/service-agent primitive; lint/render here without edits |
| Consume | `infra/helm/edai2/worker/Chart.yaml`, `infra/helm/edai2/worker/values.yaml`, `infra/helm/edai2/worker/templates/deployment.yaml`, `infra/helm/edai2/worker/templates/scaledobject.yaml`, `infra/helm/edai2/worker/templates/networkpolicy.yaml`, `infra/helm/edai2/worker/templates/serviceaccount.yaml` | Topic 16-owned reusable writer primitive; lint/render here without edits |
| Create | `infra/agentgateway/edai2/gateway.yaml`, `infra/agentgateway/edai2/model-route.yaml`, `infra/agentgateway/edai2/mcp-routes.yaml`, `infra/agentgateway/edai2/a2a-routes.yaml`, `infra/agentgateway/edai2/policies.yaml` | Private Gateway API routes and five-key ACL matrix |
| Create | `infra/kagent/edai2/model-configs.yaml` | Primary/comparison OpenAI-compatible private ModelConfigs |
| Create | `infra/kagent/edai2/workerpool-scaledobject.yaml` | One `edai2-agents` WorkerPool/KEDA scale target |
| Create | `infra/kustomize/llmd/overlays/cpu/kustomization.yaml`, `infra/kustomize/llmd/overlays/cpu/patch-primary.yaml`, `infra/kustomize/llmd/overlays/cpu/patch-comparison.yaml`, `infra/kustomize/llmd/overlays/cpu/patch-router.yaml`, `infra/kustomize/llmd/overlays/cpu/patch-model-cache-init.yaml` | Pinned CPU serving/router/cache init |
| Create | `tests/integration/llm/conftest.py` | Fail-closed live-GKE kubeconfig/context CLI and fixture contract |
| Create | `tests/integration/llm/test_gke_agents.py` | Static manifest/resource/route/render contracts |
| Create | `tests/fixtures/kubernetes/render-only-kubeconfig.yaml` | Non-secret client-only context used solely so the local `kubectl kustomize` command names an explicit kubeconfig/context without contacting an API |
| Consume | `infra/security/external-secrets/cluster-secret-store.yaml`, `infra/security/external-secrets/chat-basic-auth.yaml`, `infra/security/external-secrets/jenkins-controller.yaml`, `infra/security/external-secrets/kagent-gateway-keys.yaml`, `infra/security/external-secrets/facade-gateway-key.yaml`, `infra/security/external-secrets/postgres.yaml`, `infra/security/external-secrets/clickhouse.yaml`, `infra/security/external-secrets/valkey.yaml`, `infra/security/external-secrets/redpanda.yaml`, `infra/security/external-secrets/airflow.yaml`, `infra/security/external-secrets/datahub.yaml`, `infra/security/external-secrets/langfuse.yaml`, `infra/security/external-secrets/agentregistry.yaml`, `infra/security/external-secrets/grafana.yaml` | Topic 17-owned projections; assert exact existingSecret references only |

## Interfaces, data flow, and failure modes

Inputs are Topic 17's validated capacity/identity/secret contracts, Topic 16 charts, Topic 14 app values, immutable release pins, model-cache generation/hash references, and three runtime profiles. Helm/Kustomize output is a private, capacity-bounded platform manifest inventory: supporting services, gateway routes, two ModelConfigs, one WorkerPool, registry, and CPU inference overlays. The custom pytest interface accepts `--live-gke --kubeconfig ABSOLUTE_KUBECONFIG_PATH --context EXACT_GKE_CONTEXT`; any live fixture fails before API access when either value is absent, the path is not absolute/readable, the context is not present in that file, or it is not the expected GKE context. Fixtures construct their Kubernetes client only from those exact arguments and never merge or read the default kubeconfig. Topic 19 consumes the rendered platform interfaces; GCP Topic 24 owns installation/readiness.

Missing pin/digest, mutable tag, public Service, secret literal, absent existingSecret, unsupported built-in data service/agent/tool, wrong selector/toleration, resource/retention/GCS breach, direct llm-d route, wrong credential matrix, comparison replica-state violation, GPU request, render error, missing live kubeconfig/context, default-context fallback, or a non-GKE live context fails closed. No partial install or alternative hosted model is authorized.

## Platform contracts

Pinned versions: Gateway API 1.5.0, agentgateway 1.3.1, Substrate 0.0.6, kagent 0.9.9, Agent Registry/arctl 0.3.3, llm-d v0.7, and ingress-nginx Helm chart 4.15.1. `infra/helm/edai2/releases.yaml` and `values/ingress-nginx.yaml` carry the literal `4.15.1`; no floating range or second ingress version is allowed. No `latest`, GPU, public Service, nested RuntimeClass, hosted model or secret literal.

Substrate: bundled Valkey/RustFS off, external `edai2-valkey-primary.edai2.svc.cluster.local:6379`, GCS storage prefix. kagent: external DB `urlFile`, all ten built-ins/kmcp/kagent-tools/grafana-mcp/querydoc disabled, `proxy.url=http://agentgateway-proxy.edai2.svc.cluster.local:15000`.

ModelConfigs use OpenAI provider, exact Qwen IDs, 4096 context, private gateway base URL, `kagent-model-route-key/api-key`. One WorkerPool `edai2-agents`.

The gateway allow matrix has exactly five disjoint credentials: model-route, retrieval-MCP, drift-MCP, coordinator-to-specialist A2A, and facade-to-coordinator A2A. Each credential has only its named allow attachment. Static tests enumerate every credential against every route class and require an explicit deny attachment yielding `401` or `403` for every non-allow pair; they also reject a wildcard selector, shared key reference, direct service bypass, missing policy attachment, or a policy that relies on default allow. This Topic 18 policy matrix is the exhaustive enforcement proof deferred by Topic 14.

Replica reconciliation: comparison replicas = 0 in core; comparison replicas = 1 only during model A/B; comparison replicas = 2 only during its own four factorial cells. Primary replicas = 2 only during its own factorial cells. The inactive model is zero during every other model's two-replica cell. After comparison factorial it returns to one for model A/B, then zero.

Resource/PVC/object/emptyDir totals fit locked capacity. Seven-day metrics/log/trace/Langfuse retention; one-shard/one-replica ClickHouse; GCS ambient identity; MinIO/JSON credentials absent.

## Ordered test-first execution

- [ ] Add red manifest and live-fixture tests and run `rtk uv run pytest tests/integration/llm/test_gke_agents.py tests/unit/test_edai2_security_static.py -q`. Expected: nonzero until catalog/charts/routes/models/overlays and the fail-closed live kubeconfig/context interface exist.
- [ ] Lint the Topic 16-owned reusable charts with `rtk helm lint infra/helm/edai2/service-agent` and `rtk helm lint infra/helm/edai2/worker`. Expected: both exit 0, `rtk git diff -- infra/helm/edai2/service-agent infra/helm/edai2/worker` is empty for Topic 18, and nothing is applied.
- [ ] Render all three app-agent values through the consumed chart: `rtk helm template retrieval infra/helm/edai2/service-agent -f infra/helm/edai2/values/retrieval-agent.yaml --set image.tag=testsha --set-string substrate.bucketName=edai2-sentinel-bucket`; `rtk helm template drift infra/helm/edai2/service-agent -f infra/helm/edai2/values/drift-agent.yaml --set image.tag=testsha --set-string substrate.bucketName=edai2-sentinel-bucket`; and `rtk helm template coordinator infra/helm/edai2/service-agent -f infra/helm/edai2/values/coordinator-agent.yaml --set image.tag=testsha --set-string substrate.bucketName=edai2-sentinel-bucket`. Expected: all exit 0; their aggregate is exactly five SandboxAgents representing logical identities `retrieval`, `drift`, and `coordinator`, `support` carries `EDAI2_LOGICAL_AGENT=retrieval`, snapshots contain the sentinel bucket and logical/variant keys, and no `${EDAI2_*}` placeholder remains.
- [ ] Render worker with `rtk helm template feast-offline-writer infra/helm/edai2/worker -f infra/helm/edai2/worker/values.yaml --set image.tag=testsha`. Expected: exit 0; bounded Deployment/ScaledObject/NetworkPolicy with no LoadBalancer.
- [ ] Render llm-d with `rtk kubectl --kubeconfig tests/fixtures/kubernetes/render-only-kubeconfig.yaml --context render-only kustomize infra/kustomize/llmd/overlays/cpu`. Expected: exit 0 without API contact; exact model IDs/context/CPU, immutable pins, private router, and inactive-zero profile logic.
- [ ] Run `rtk uv run pytest tests/integration/llm/test_gke_agents.py tests/unit/test_edai2_security_static.py -q`. Expected: exit 0 for resources, retention, GCS, ExternalSecrets, ingress-nginx chart `4.15.1`, all five keys against every wrong route with explicit 401/403 policy outcomes, replica state matrix, the aggregate five-resource render, and synthetic rejection of missing/wrong/default live kubeconfig contexts without cluster contact.
- [ ] Run `rtk uv run python scripts/gke/manage_profile.py core --ttl 2h --dry-run`. Expected: exit 0 with capacity report only and no cluster/GCP contact.
- [ ] Run `rtk git diff --check`. Expected: exit 0.

## Evidence, cleanup, rubric, and DoD

Topic 18 owns lint/template/Kustomize/static report hashes only. Delete only temporary render files. No Helm release, CRD, model, cluster or screenshot is claimed.

| Sheet3 cell | Local proof | Deferred proof |
|---|---|---|
| `Sheet3!E3:E7` | pinned CPU/model/registry static renders | live GKE/model/registry |
| `Sheet3!E41:E47` | private gateway/security/retention contracts | contextual runtime UIs |

## Definition of Done

All charts lint/render, Kustomize renders, platform/resource/security tests pass, exact replica states are encoded, and no live action occurred. Topic 19 consumes charts/platform references without editing them.

## Completion Record

| Field | Execution value |
|---|---|
| Status | Complete |
| Current branch/status | `feature/implement-edai2...origin/feature/implement-edai2`; final `rtk git status --short --branch` records only Topic 18 paths plus this Completion Record. |
| Affected files | `.gitignore` (unignores only the non-secret render fixture); `infra/helm/edai2/releases.yaml`; `infra/helm/edai2/values/{agentgateway,agentregistry,airflow,alloy,cert-manager,clickhouse,datahub,external-secrets,feast,grafana,ingress-nginx,jenkins,kagent,keda,langfuse,loki,opensearch,postgres,prometheus,redpanda,substrate,tempo,valkey,vault}.yaml`; `infra/agentgateway/edai2/*.yaml`; `infra/kagent/edai2/*.yaml`; `infra/kustomize/llmd/overlays/cpu/*.yaml`; `tests/integration/llm/conftest.py`; `tests/integration/llm/test_gke_agents.py`; `tests/fixtures/kubernetes/render-only-kubeconfig.yaml`. Topic 16-owned `service-agent` and `worker` charts and Topic 14-owned agent values were consumed only, with no Topic 18 edit. |
| Commands and exit codes | `rtk uv lock --check` 0; `rtk helm lint infra/helm/edai2/service-agent` 0; `rtk helm lint infra/helm/edai2/worker` 0; the retrieval/drift/coordinator service-agent and feast-offline-writer Helm templates 0; explicit-kubeconfig/context llm-d Kustomize render 0; `rtk uv run pytest tests/integration/llm/test_gke_agents.py tests/unit/test_edai2_security_static.py -q` 0 (11 passed); `rtk uv run python scripts/gke/manage_profile.py core --ttl 2h --dry-run` 0; `rtk git diff --check` 0. |
| Evidence hashes | Fresh transient UTF-8 stdout SHA-256: retrieval service-agent render `35538846a2e34f4d179bce9d8d85fa0a7b7b8f9a7b5fa9db6b5c857de8a3ddb5`; worker render `6a1a3a6f25bc8a08400836760e180ee4f6cb6611ed7562745173c4533980493f`; llm-d Kustomize render `6b7fb49582fc5a26e5c62da5d71050b0cd17531e0ec49e1626e675ab1896a5de`; static pytest report `10451cf472a048760cedde8c99bb5ac550eae84b228e24f6cdb24451efbc21fe`; profile dry-run report `f5ec2bc780a98db43fc715c422862c42ea70c4e9a7eb3d4e3629258ff9a28eaa`. No report files were retained. |
| Screenshot QA | Not captured locally |
| Cleanup/runtime release | No temporary render file or runtime was created; all render/test output was transient, and no Helm/Kustomize/kubectl apply, GCP, Docker, model, or secret action occurred. |
| Limitations | Installation/readiness, model-cache generation proof, GKE/model/registry behavior, public ingress, screenshots, and runtime rubric evidence remain deferred to successor live topics. |
| Handoff | `tmp/edai2-plan/execution-v1/local/19-workload-charts-streaming-keda-experiments.md` |

## Correction Addendum — Topic 19 WorkerPool KEDA contract

This addendum preserves the `Complete` status above. The Topic 19-authored WorkerPool contract already had bounds, polling interval, and cooldown period; this narrow Topic 18 correction adds its required Prometheus pending-chat trigger.

| Field | Correction evidence |
|---|---|
| Scope | `infra/kagent/edai2/workerpool-scaledobject.yaml` adds one Prometheus trigger with server `http://prometheus-server.edai2.svc.cluster.local`, metric `edai2_pending_chat_requests`, threshold `1`, and query `sum(edai2_pending_chat_requests)`. |
| Fresh commands and exit codes | The focused red gate above exited 1 because `triggers` was absent; its green rerun exited 0 (`4 passed`). The full predecessor regression `rtk uv run pytest tests/unit/test_edai2_repository_contract.py tests/integration/llm/test_gke_agents.py tests/unit/test_edai2_security_static.py -q` exited 0 (`22 passed`). |
| Limitations | Static manifest proof only; no WorkerPool, KEDA object, Prometheus query, Kubernetes API action, or scaling event was created or claimed. |
