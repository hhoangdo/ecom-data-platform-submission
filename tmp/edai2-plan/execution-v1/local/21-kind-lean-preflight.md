# 21 — Lean Kind Preflight and One-Slice Smoke

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run one fail-closed, resource-bounded local retrieval slice on a dedicated single-node Kind cluster after Topic 20. This is supplemental readiness only and earns no Sheet3 credit.

**Architecture:** A dedicated kubeconfig/context isolates `edai2-lean`. A preflight script inspects Docker concurrency and fully rendered resources before creation/deployment, writes fail-closed JSON totals, then one local retrieval image is built, loaded, deployed and probed. Broad Compose detection stops without altering any container.

**Tech Stack:** Kind, `kindest/node:v1.35.5` pinned digest, Docker, kubectl, Helm render, Python preflight, pytest.

## Metadata

| Field | Locked value |
|---|---|
| Phase | Supplemental local Kind Topic 21 |
| Source task | Lean preflight supplement after local Tasks 3–10 |
| Sheet3 support | Zero credit across `Sheet3!E3:E62`; local Kind never proves a GKE rubric cell |
| Predecessor Completion Record | `tmp/edai2-plan/execution-v1/local/20-observability-ingress-screenshot-contracts.md` must be `Complete` |
| Blocked successor | `tmp/edai2-plan/execution-v1/gcp/22-gcp-account-budget-terraform-apply.md` |
| Runtime ownership | One named local operator owns only cluster `edai2-lean` |
| Class | Local Kind; explicitly not GCP/GKE evidence |

## Locked planning basis

Read `C:\Users\oou1hc\.codex\RTK.md`; verify `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`, `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`, and rubric `tmp/rubic-check/Coursework Tracking (Public).xlsx` `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.

Cluster `edai2-lean`; context `kind-edai2-lean`; kubeconfig `tmp/edai2-kind/kubeconfig`; node image `kindest/node:v1.35.5@sha256:ce977ae6d65918d0b58a5f8b5e940429c2ce42fa3a5619ec2bbc60b949c0ac95`.

## Global constraints

Current branch/serial session, `apply_patch`, `rtk uv run` developer recipes, and `rtk make` operator recipes. Dependency changes are handed to Topic 15 for `rtk uv add` plus `rtk git diff -- pyproject.toml uv.lock` inspection. Do not commit/stage, invoke GCP, run broad Compose concurrently, auto-prune/stop Docker, deploy LoadBalancer, or run full llm-d/Jenkins/observability/Vault recovery. One image/slice at a time. One retry then Partial.

Limits: namespace requests <=6 CPU/16GiB; limits <=10 CPU/22GiB; <=30 pods; <=8 PVCs/20GiB; zero LoadBalancer; every KEDA maxReplicaCount <=1.

## Read-only current-state refresh

- [ ] Run `rtk git status --short --branch`. Expected: branch/changes recorded.
- [ ] Run `rtk proxy certutil -hashfile tmp/edai2-plan/03_data_generator_improvement.md SHA256`. Expected: output contains `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`.
- [ ] Run `rtk proxy certutil -hashfile tmp/edai2-plan/04.2_llm_design.md SHA256`. Expected: output contains `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`.
- [ ] Run `rtk proxy certutil -hashfile "tmp/rubic-check/Coursework Tracking (Public).xlsx" SHA256`. Expected: output contains `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- [ ] Run `rtk proxy powershell -NoProfile -Command "Select-String -Path tmp/edai2-plan/execution-v1/local/20-observability-ingress-screenshot-contracts.md -Pattern '^Status: Complete|\| Status \| Complete \|'"`. Expected: completed predecessor.
- [ ] Run `rtk docker ps --format "{{.Names}}"`. Expected: inventory only; if preflight identifies broad coursework Compose, stop without changing containers.
- [ ] Run `rtk proxy powershell -NoProfile -Command "if (Test-Path tmp/edai2-kind/kubeconfig) { Write-Error 'dedicated kubeconfig already exists'; exit 1 }; Write-Output 'False'"`. Expected: exit 0 and exactly `False`; an existing file stops the topic as `Partial` rather than being reused.
- [ ] Run `rtk git diff --check`. Expected: exit 0.

## Scope and non-goals

In scope: Kind config, namespace/quota/limits/default-deny policy, retrieval smoke values, fail-closed preflight JSON, static tests, exact build/load/deploy/probe/cleanup.

Non-goals: full platform, broad Compose, llm-d, Jenkins, observability, Vault/recovery, GKE, Terraform, public ingress, LoadBalancer, persistent evidence, or Sheet3 credit.

## Exact file map

| Action | Exact path | Responsibility |
|---|---|---|
| Create | `infra/kind/edai2-lean/kind-config.yaml` | Single-node pinned Kind cluster configuration |
| Create | `infra/kind/edai2-lean/namespace.yaml` | `edai2-lean` namespace |
| Create | `infra/kind/edai2-lean/resource-quota.yaml` | CPU/memory/pod/PVC/storage/LoadBalancer limits |
| Create | `infra/kind/edai2-lean/limit-range.yaml` | Per-container defaults/caps |
| Create | `infra/kind/edai2-lean/network-policy.yaml` | Default deny plus DNS/probe allowance |
| Create | `infra/kind/edai2-lean/retrieval-values.yaml` | One retrieval API slice with fake index; SandboxAgent/RemoteMCPServer/KEDA CRs disabled locally and declared KEDA maximum fixed at 1 |
| Create | `scripts/kind/preflight_edai2_lean.py` | Docker guard, render totals, fail-closed JSON |
| Create | `tests/unit/test_edai2_kind_preflight.py` | Pins, names, totals, LoadBalancer/KEDA/Compose rejection |
| Generated | `tmp/edai2-kind/preflight.json` | Sanitized local totals/result only |
| Generated | `tmp/edai2-kind/kubeconfig` | Dedicated ephemeral kubeconfig |

## Interfaces, data flow, and failure modes

Preflight JSON includes status, cluster/context/kubeconfig/node-image, manifest hashes, request/limit totals, pod/PVC/storage counts, Service type inventory, KEDA maxima and broad-Compose detection. Missing/unparseable quantity or manifest fails closed.

Flow: static tests -> preflight render/inventory -> create one cluster -> verify context -> build one retrieval image -> load by cluster name -> apply namespace/quota/policy -> Helm install one API slice with `sandboxAgent.enabled=false`, `remoteMcpServer.enabled=false`, and `autoscaling.enabled=false` -> rollout/HTTP probes -> capture local inventory -> uninstall/delete owned cluster. The values file still fixes any future KEDA maximum at 1, and the preflight rejects a rendered or declared value above 1.

If broad Compose is detected, preflight exits nonzero before `kind create` and does not stop/remove/restart any container. Any wrong context/kubeconfig, limit breach, LoadBalancer, KEDA max >1, unpinned node image, or extra slice blocks execution.

## Ordered test-first execution

- [ ] Add red preflight tests and run `rtk uv run pytest tests/unit/test_edai2_kind_preflight.py -q`. Expected: nonzero until package, pin, limits and guard exist.
- [ ] Implement package/preflight and run `rtk uv run pytest tests/unit/test_edai2_kind_preflight.py -q`. Expected: exit 0 for exact names/digest/limits and all rejection fixtures.
- [ ] Run `rtk uv run python scripts/kind/preflight_edai2_lean.py --cluster-name edai2-lean --context kind-edai2-lean --kubeconfig tmp/edai2-kind/kubeconfig --manifest-root infra/kind/edai2-lean --output tmp/edai2-kind/preflight.json`. Expected: exit 0 and fail-closed JSON totals within all caps; otherwise stop with containers unchanged.
- [ ] Create with `rtk proxy kind create cluster --name edai2-lean --image kindest/node:v1.35.5@sha256:ce977ae6d65918d0b58a5f8b5e940429c2ce42fa3a5619ec2bbc60b949c0ac95 --config infra/kind/edai2-lean/kind-config.yaml --kubeconfig tmp/edai2-kind/kubeconfig`. Expected: exit 0 and only cluster `edai2-lean`.
- [ ] Verify with `rtk kubectl --kubeconfig tmp/edai2-kind/kubeconfig --context kind-edai2-lean config current-context`. Expected: exactly `kind-edai2-lean`.
- [ ] Build with `rtk docker build --target retrieval_agent -t edai2-retrieval:kind-smoke -f containers/edai2/Dockerfile .`. Expected: exit 0; exactly one local image target built.
- [ ] Load with `rtk proxy kind load docker-image edai2-retrieval:kind-smoke --name edai2-lean`. Expected: exit 0 and image present only in the named cluster.
- [ ] Apply namespace with `rtk kubectl --kubeconfig tmp/edai2-kind/kubeconfig --context kind-edai2-lean apply -f infra/kind/edai2-lean/namespace.yaml`. Expected: exit 0.
- [ ] Apply limits with `rtk kubectl --kubeconfig tmp/edai2-kind/kubeconfig --context kind-edai2-lean apply -f infra/kind/edai2-lean/resource-quota.yaml -f infra/kind/edai2-lean/limit-range.yaml -f infra/kind/edai2-lean/network-policy.yaml`. Expected: exit 0 before workload admission.
- [ ] Deploy with `rtk helm upgrade --install edai2-retrieval-kind infra/helm/edai2/service-agent --namespace edai2-lean --kubeconfig tmp/edai2-kind/kubeconfig --kube-context kind-edai2-lean -f infra/kind/edai2-lean/retrieval-values.yaml --set image.repository=edai2-retrieval --set image.tag=kind-smoke --set sandboxAgent.enabled=false --set remoteMcpServer.enabled=false --set autoscaling.enabled=false --wait --timeout 5m`. Expected: exit 0; one API slice, ClusterIP only, no absent platform CRD dependency, and declared KEDA maximum remains 1.
- [ ] Probe rollout with `rtk kubectl --kubeconfig tmp/edai2-kind/kubeconfig --context kind-edai2-lean -n edai2-lean rollout status deployment/edai2-retrieval-kind --timeout=120s`. Expected: exit 0.
- [ ] Start the owned probe monitor with `rtk kubectl --kubeconfig tmp/edai2-kind/kubeconfig --context kind-edai2-lean -n edai2-lean port-forward service/edai2-retrieval-kind 18081:8080`. Expected: the local monitor binds only port 18081 to the named ClusterIP service.
- [ ] Probe process health with `rtk curl.exe -sS http://127.0.0.1:18081/healthz`. Expected: HTTP 200 and the schema-valid process-health body.
- [ ] Probe dependency readiness with `rtk curl.exe -sS http://127.0.0.1:18081/readyz`. Expected: HTTP 200 for the configured fake index adapter; no external dependency or fabricated match.
- [ ] Run focused smoke with `rtk uv run pytest tests/unit/llm/test_retrieval.py tests/contract/llm/test_api_contracts.py tests/contract/llm/test_mcp_contracts.py -q`. Expected: exit 0.
- [ ] Stop only the owned port-forward monitor, then inventory with `rtk kubectl --kubeconfig tmp/edai2-kind/kubeconfig --context kind-edai2-lean -n edai2-lean get resourcequota,limitrange,pods,svc,pvc -o wide`. Expected: caps respected, <=30 pods, <=8 PVC/20Gi, zero LoadBalancer; preflight JSON separately proves the declared KEDA maximum is 1.
- [ ] Uninstall with `rtk helm uninstall edai2-retrieval-kind --namespace edai2-lean --kubeconfig tmp/edai2-kind/kubeconfig --kube-context kind-edai2-lean`. Expected: exit 0 and only owned release removed.
- [ ] Delete with `rtk proxy kind delete cluster --name edai2-lean --kubeconfig tmp/edai2-kind/kubeconfig`. Expected: exit 0 and only owned cluster removed.
- [ ] Run `rtk git diff --check` and `rtk git status --short --branch`. Expected: exit 0 and only request-scoped files; no local runtime remains.

## Evidence, cleanup, rubric, and DoD

Topic 21 owns `preflight.json`, command results and local inventory hashes only. No screenshot and no Sheet3/GKE claim. Never delete Docker images/containers/volumes or clusters other than the explicitly owned release/cluster; automatic pruning is forbidden.

| Boundary | Result |
|---|---|
| Local readiness | One retrieval slice plus exact resource/context proof |
| `Sheet3!E3:E62` / GKE | Zero credit; all live GKE evidence remains Topic 22+ |
| Skipped | full llm-d, Jenkins, observability, Vault recovery, GKE |

## Definition of Done

Preflight JSON passes, exact pinned Kind cluster and context are used, one image/slice builds/loads/deploys/probes, caps hold, owned release/cluster are removed, and containers remain otherwise untouched. A Partial record is truthful after one bounded retry.

## Completion Record

| Field | Execution value |
|---|---|
| Status | Not started |
| Current branch/status | Record final `rtk git status --short --branch` |
| Affected files | Record Topic 21 exact paths |
| Commands and exit codes | Record every split preflight/create/verify/build/load/apply/deploy/probe/inventory/delete command |
| Evidence hashes | Record `preflight.json` and local inventory SHA-256 |
| Screenshot QA | None; Kind is not GKE evidence |
| Cleanup/runtime release | Record Helm uninstall and exact Kind delete result |
| Limitations | State no GKE/llm-d/Jenkins/observability/Vault proof |
| Handoff | `tmp/edai2-plan/execution-v1/gcp/22-gcp-account-budget-terraform-apply.md` |
