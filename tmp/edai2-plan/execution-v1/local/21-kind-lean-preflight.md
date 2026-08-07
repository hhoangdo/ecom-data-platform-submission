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

Read `C:\Users\oou1hc\.codex\RTK.md`; verify `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`, `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`, and rubric `tmp/rubic-check/Coursework Tracking (Public).xlsx` `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.

Cluster `edai2-lean`; context `kind-edai2-lean`; kubeconfig `tmp/edai2-kind/kubeconfig`; node image `kindest/node:v1.35.5@sha256:ce977ae6d65918d0b58a5f8b5e940429c2ce42fa3a5619ec2bbc60b949c0ac95`.

## Global constraints

Current branch/serial session, `apply_patch`, `rtk uv run` developer recipes, and `rtk make` operator recipes. Topic 08 owns baseline dependencies; run `rtk uv lock --check` and treat a missing prerequisite as a `Partial` predecessor defect instead of editing dependencies. Do not commit/stage, invoke GCP, run broad Compose concurrently, auto-prune/stop Docker, deploy LoadBalancer, or run full llm-d/Jenkins/observability/Vault recovery. One image/slice at a time. One retry then `Partial`.

Limits: namespace requests <=6 CPU/16GiB; limits <=10 CPU/22GiB; <=30 pods; <=8 PVCs/20GiB; zero LoadBalancer; every KEDA maxReplicaCount <=1.

## Read-only current-state refresh

- [ ] Run `rtk git status --short --branch`. Expected: branch/changes recorded.
- [ ] Run `rtk proxy certutil -hashfile tmp/edai2-plan/03_data_generator_improvement.md SHA256`. Expected: output contains `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`.
- [ ] Run `rtk proxy certutil -hashfile tmp/edai2-plan/04.2_llm_design.md SHA256`. Expected: output contains `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`.
- [ ] Run `rtk proxy certutil -hashfile "tmp/rubic-check/Coursework Tracking (Public).xlsx" SHA256`. Expected: output contains `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- [ ] Run `rtk proxy powershell -NoProfile -Command "Select-String -Path tmp/edai2-plan/execution-v1/local/20-observability-ingress-screenshot-contracts.md -Pattern '^Status: Complete|\| Status \| Complete \|'"`. Expected: completed predecessor.
- [ ] Run `rtk uv lock --check`. Expected: exit 0 with the Topic 08-owned baseline lockfile unchanged.
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
| Create | `infra/kind/edai2-lean/retrieval-values.yaml` | One retrieval API slice with `fullnameOverride: edai2-retrieval-kind` and fake index; SandboxAgent/RemoteMCPServer/KEDA CRs disabled locally and declared KEDA maximum fixed at 1 |
| Create | `scripts/kind/preflight_edai2_lean.py` | Docker guard, render totals, fail-closed JSON |
| Create | `scripts/kind/run_edai2_lean.ps1` | Exact post-preflight create/build/load/apply/deploy/probe/inventory lifecycle with hidden PID ownership and unconditional release/cluster/kubeconfig cleanup |
| Create | `tests/unit/test_edai2_kind_preflight.py` | Pins, names, totals, LoadBalancer/KEDA/Compose rejection |
| Generated | `tmp/edai2-kind/preflight.json` | Sanitized local totals/result only |
| Generated | `tmp/edai2-kind/kubeconfig` | Dedicated ephemeral kubeconfig |
| Generated | `tmp/edai2-kind/port-forward.pid`, `tmp/edai2-kind/port-forward.stdout.log`, `tmp/edai2-kind/port-forward.stderr.log` | Exact hidden probe-monitor ownership and logs |
| Generated | `tmp/edai2-kind/health.json`, `tmp/edai2-kind/health.status`, `tmp/edai2-kind/readiness.json`, `tmp/edai2-kind/readiness.status`, `tmp/edai2-kind/inventory.json` | Captured probe bodies/status codes, schema-validation inputs, and final bounded inventory |

## Interfaces, data flow, and failure modes

Preflight JSON includes status, cluster/context/kubeconfig/node-image, manifest hashes, request/limit totals, pod/PVC/storage counts, Service type inventory, KEDA maxima and broad-Compose detection. Missing/unparseable quantity or manifest fails closed.

Flow: static tests -> preflight render/inventory -> create one cluster -> verify context -> build one retrieval image -> load by cluster name -> apply namespace/quota/policy -> Helm install one API slice with `sandboxAgent.enabled=false`, `remoteMcpServer.enabled=false`, and `autoscaling.enabled=false` -> rollout/HTTP probes -> capture local inventory -> uninstall/delete owned cluster. The values file still fixes any future KEDA maximum at 1, and the preflight rejects a rendered or declared value above 1.

If broad Compose is detected, preflight exits nonzero before `kind create` and does not stop/remove/restart any container. Any wrong context/kubeconfig, limit breach, LoadBalancer, KEDA max >1, unpinned node image, or extra slice blocks execution.

## Locked script command sequence

`scripts/kind/run_edai2_lean.ps1` must execute this sequence with checked exit codes and stop on the first failure; the Helm uninstall, owned-cluster delete, port-forward termination, and owned-kubeconfig removal remain in nested `finally` blocks:

```powershell
rtk kind create cluster --name edai2-lean --image kindest/node:v1.35.5@sha256:ce977ae6d65918d0b58a5f8b5e940429c2ce42fa3a5619ec2bbc60b949c0ac95 --config infra/kind/edai2-lean/kind-config.yaml --kubeconfig tmp/edai2-kind/kubeconfig
rtk kubectl --kubeconfig tmp/edai2-kind/kubeconfig --context kind-edai2-lean config current-context
rtk docker build --file containers/edai2/Dockerfile --target retrieval_agent --tag edai2/retrieval-agent:kind-local .
rtk kind load docker-image edai2/retrieval-agent:kind-local --name edai2-lean
rtk kubectl --kubeconfig tmp/edai2-kind/kubeconfig --context kind-edai2-lean apply -f infra/kind/edai2-lean/namespace.yaml
rtk kubectl --kubeconfig tmp/edai2-kind/kubeconfig --context kind-edai2-lean apply -f infra/kind/edai2-lean/resource-quota.yaml -f infra/kind/edai2-lean/limit-range.yaml -f infra/kind/edai2-lean/network-policy.yaml
rtk helm --kubeconfig tmp/edai2-kind/kubeconfig --kube-context kind-edai2-lean upgrade --install edai2-retrieval-kind infra/helm/edai2/service-agent --namespace edai2-lean -f infra/kind/edai2-lean/retrieval-values.yaml --set-string image.repository=edai2/retrieval-agent --set-string image.tag=kind-local --set image.pullPolicy=IfNotPresent --wait --timeout 5m
rtk kubectl --kubeconfig tmp/edai2-kind/kubeconfig --context kind-edai2-lean -n edai2-lean rollout status deployment/edai2-retrieval-kind --timeout=180s
rtk kubectl --kubeconfig tmp/edai2-kind/kubeconfig --context kind-edai2-lean -n edai2-lean get pods,pvc,services -o json
rtk helm --kubeconfig tmp/edai2-kind/kubeconfig --kube-context kind-edai2-lean uninstall edai2-retrieval-kind --namespace edai2-lean --wait --timeout 2m
rtk kind delete cluster --name edai2-lean
```

The inventory command's stdout is atomically written to `tmp/edai2-kind/inventory.json` and validated before cleanup. The script may parameterize only the exact values exposed by its invocation; tests must compare the resulting argument arrays to this sequence and must prove no call falls back to the default kubeconfig/context.

## Ordered test-first execution

- [ ] Add red preflight tests and run `rtk uv run pytest tests/unit/test_edai2_kind_preflight.py -q`. Expected: nonzero until package, pin, limits and guard exist.
- [ ] Implement package/preflight and run `rtk uv run pytest tests/unit/test_edai2_kind_preflight.py -q`. Expected: exit 0 for exact names/digest/limits and all rejection fixtures.
- [ ] Run `rtk uv run python scripts/kind/preflight_edai2_lean.py --cluster-name edai2-lean --context kind-edai2-lean --kubeconfig tmp/edai2-kind/kubeconfig --manifest-root infra/kind/edai2-lean --output tmp/edai2-kind/preflight.json`. Expected: exit 0 and fail-closed JSON totals within all caps; otherwise stop with containers unchanged.
- [ ] Implement `scripts/kind/run_edai2_lean.ps1` so it invokes the locked command sequence above with exact argument arrays. Its probe block must start `rtk kubectl --kubeconfig tmp/edai2-kind/kubeconfig --context kind-edai2-lean -n edai2-lean port-forward service/edai2-retrieval-kind 18081:8080 --address 127.0.0.1` through hidden `Start-Process -PassThru`, persist the PID and separate logs, use bounded retries plus `rtk curl.exe --fail-with-body` to require HTTP 200 bodies for `/healthz` and `/readyz`, parse both bodies against the locked probe schemas, and terminate and verify that PID in `finally`. Expected: static tests prove every command names only `edai2-lean`/`kind-edai2-lean`, the probe cannot accept a non-200 or invalid body, and every success/failure path reaches exact-owner cleanup.
- [ ] Run `rtk powershell -NoProfile -File scripts/kind/run_edai2_lean.ps1 -ClusterName edai2-lean -Context kind-edai2-lean -Kubeconfig tmp/edai2-kind/kubeconfig -NodeImage kindest/node:v1.35.5@sha256:ce977ae6d65918d0b58a5f8b5e940429c2ce42fa3a5619ec2bbc60b949c0ac95 -Namespace edai2-lean -LocalPort 18081 -Preflight tmp/edai2-kind/preflight.json -Inventory tmp/edai2-kind/inventory.json`. Expected: exit 0 after one retrieval slice becomes Ready, both schema-valid probes return HTTP 200, inventory proves <=30 pods, <=8 PVC/20Gi and zero LoadBalancer, the Helm release and cluster are removed, the exact port-forward PID is absent, and the owned ephemeral kubeconfig is deleted in the script's outer `finally`; unrelated images, containers, volumes, and clusters remain untouched.
- [ ] Run focused smoke with `rtk uv run pytest tests/unit/llm/test_retrieval.py tests/contract/llm/test_api_contracts.py tests/contract/llm/test_mcp_contracts.py tests/unit/test_edai2_kind_preflight.py -q`. Expected: exit 0 with the Kind lifecycle/probe schema and API/MCP contracts passing.
- [ ] Verify cleanup with `rtk powershell -NoProfile -Command '$clusterNames=& rtk proxy kind get clusters; if ($clusterNames -contains "edai2-lean") { Write-Error "owned Kind cluster still exists"; exit 1 }; if (Test-Path -LiteralPath "tmp/edai2-kind/kubeconfig") { Write-Error "owned kubeconfig still exists"; exit 1 }; $pidPath="tmp/edai2-kind/port-forward.pid"; if (Test-Path -LiteralPath $pidPath) { $monitorPid=[int](Get-Content -LiteralPath $pidPath); if (Get-Process -Id $monitorPid -ErrorAction SilentlyContinue) { Write-Error "owned port-forward still runs"; exit 1 } }; "KIND_CLEANUP=PASS"'`. Expected: exactly `KIND_CLEANUP=PASS`; only logs, `preflight.json`, and sanitized `inventory.json` remain.
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
