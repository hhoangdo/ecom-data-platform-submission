# 14 — Agent Security, Registry, and Notebook Contracts

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete Task 5's agent-facing local/static work: exactly five SandboxAgent resources representing three logical identities, strict WorkerPool/snapshot/RemoteMCPServer and credential-reference bindings, late-bound registry metadata/read-back/rollback, and two cleared parameterized notebooks. Topic 18 owns the exhaustive gateway-policy enforcement matrix after those policies exist.

**Architecture:** Retrieval and drift each have one SandboxAgent; coordinator has `v1-primary`, `v2-primary`, and `v1-comparison` resources under one logical coordinator identity. The Kubernetes resource remains named `support`, but its labels, environment, snapshots, and registry identity are `retrieval`. All use the platform WorkerPool and versioned GCS snapshots, and all traffic goes through agentgateway. Registry identity is separate from runtime variants and is published only after generated ActorTemplate/image data is known.

**Tech Stack:** kagent 0.9.9 CRDs, Agent Substrate 0.0.6, agentgateway 1.3.1 policies, Agent Registry/arctl 0.3.3 metadata, Helm values, Jupyter, pytest.

## Metadata

| Field | Locked value |
|---|---|
| Phase | Local/static implementation Topic 14 |
| Source task | `tmp/edai2-plan/04.2_llm_design.md` Task 5 agent/registry/notebook portion |
| Sheet3 support | `Sheet3!E13:E25`; notebooks specifically `Sheet3!E22:E23` |
| Predecessor Completion Record | `tmp/edai2-plan/execution-v1/local/13-coordinator-inference-routing-telemetry.md` must be `Complete` |
| Blocked successor | `tmp/edai2-plan/execution-v1/local/15-evaluation-test-quality-load.md` |
| Runtime ownership | Local rendering/notebook-structure session only |
| Class | Local/static; no cluster, registry, or notebook execution |

## Locked planning basis

Read `C:\Users\oou1hc\.codex\RTK.md`. Verify Section 03 plan `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`, EDAI2 plan `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`, and `tmp/rubic-check/Coursework Tracking (Public).xlsx` `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.

## Global constraints

Use current branch, serial session, `apply_patch`, and `rtk`-prefixed shell commands. Developer recipes use `rtk uv run`; operator recipes use `rtk make`. Topic 08 owns the baseline dependencies and lockfile: run `rtk uv lock --check`, and treat a missing prerequisite dependency as a `Partial` predecessor defect rather than editing `pyproject.toml` or `uv.lock`. No staging/commit/worktree, GCP/cluster/registry mutation, notebook execution, secret material, or automatic Docker prune/stop. One bounded retry then `Partial`.

## Read-only current-state refresh

- [ ] Run `rtk git status --short --branch`. Expected: branch and unrelated changes recorded.
- [ ] Run `rtk proxy certutil -hashfile tmp/edai2-plan/03_data_generator_improvement.md SHA256`. Expected: output contains `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`.
- [ ] Run `rtk proxy certutil -hashfile tmp/edai2-plan/04.2_llm_design.md SHA256`. Expected: output contains `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`.
- [ ] Run `rtk proxy certutil -hashfile "tmp/rubic-check/Coursework Tracking (Public).xlsx" SHA256`. Expected: output contains `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- [ ] Run `rtk proxy powershell -NoProfile -Command "Select-String -Path tmp/edai2-plan/execution-v1/local/13-coordinator-inference-routing-telemetry.md -Pattern '^Status: Complete|\| Status \| Complete \|'"`. Expected: one completed predecessor.
- [ ] Run `rtk uv lock --check`. Expected: exit 0 with the Topic 08-owned baseline lockfile unchanged.
- [ ] Run `rtk git diff --check`. Expected: exit 0.

## Scope and non-goals

In scope: three app-agent Helm value files, five SandboxAgent definitions, two RemoteMCPServers, credential-reference/resource-binding tests, three registry identities and supplementary runtime metadata, publish/read-back/rollback CLI, two cleared source notebooks and structure tests.

Non-goals: platform WorkerPool/ModelConfig creation and exhaustive gateway-policy enforcement (Topic 18), reusable chart creation (Topic 16), workload deployment (Topic 19), live registry publication, notebook execution, GKE, secrets, screenshots, or observability.

## Exact file map

| Action | Exact path | Responsibility |
|---|---|---|
| Create | `infra/helm/edai2/values/retrieval-agent.yaml` | `support` resource with logical retrieval identity and retrieval RemoteMCPServer bindings |
| Create | `infra/helm/edai2/values/drift-agent.yaml` | Drift SandboxAgent and drift RemoteMCPServer bindings |
| Create | `infra/helm/edai2/values/coordinator-agent.yaml` | Three coordinator runtime resources under one identity |
| Create | `infra/agentregistry/edai2/retrieval-agent.yaml` | Late-bound retrieval registry identity template |
| Create | `infra/agentregistry/edai2/drift-agent.yaml` | Late-bound drift registry identity template |
| Create | `infra/agentregistry/edai2/coordinator-agent.yaml` | One coordinator identity plus three supplementary runtime entries |
| Create | `scripts/llm/publish_agents.py` | Late-bind ActorTemplate digest, publish, read back, rollback |
| Create | `notebooks/edai2/drift_agent_mcp.ipynb` | Parameterized drift live notebook with cleared output |
| Create | `notebooks/edai2/retrieval_agent_mcp.ipynb` | Parameterized retrieval live notebook with cleared output |
| Create | `tests/unit/llm/test_agent_manifests.py` | Resource counts, identity fields, route references, snapshots, and disjoint credential references |
| Create | `tests/unit/llm/test_registry.py` | Late-binding/read-back/rollback contracts |
| Create | `tests/unit/llm/test_notebooks.py` | Parameter-cell, output-clear, secret/PII structure tests |
| Reference contract | `infra/kagent/edai2/model-configs.yaml`, `infra/kagent/edai2/workerpool-scaledobject.yaml` | Future Topic 18-owned platform paths; validate only their agreed names and never require the files to exist or edit them here |

## Interfaces, data flow, and failure modes

Inputs are Topic 13's three destination names, primary/comparison ModelConfig names, gateway credential references, the required non-empty Helm value `substrate.bucketName` populated later from Terraform output `substrate_bucket_name`, and exact MCP endpoints. Values define five SandboxAgents, two RemoteMCPServers, three logical registry identities, supplementary variant hashes, and two cleared notebooks. Topic 16 is the sole reusable-chart owner and consumes these app-agent values for sentinel renders; Topics 18–19 consume the resources and registry templates without editing chart templates; later GCP evidence consumes read-back records and executed notebooks.

Rendering fails closed for an unset bucket/logical-agent/runtime-variant, wrong WorkerPool, unversioned snapshot, fourth logical identity, sixth SandboxAgent, direct service address, wrong credential-route pairing, Python image in registry `image`, non-identical held constant, failed read-back, rollback CAS mismatch, notebook output, secret, or raw PII. No partial registry record or alternate route is emitted.

## Exact resource and security contract

Five SandboxAgent resources equal three logical identities:

| Resource | Logical identity | ModelConfig | Allowed tool path |
|---|---|---|---|
| `support` | retrieval | primary | retrieval MCP only |
| `drift` | drift | primary | drift MCP only |
| `coordinator-v1-primary` | coordinator | primary | support/drift A2A |
| `coordinator-v2-primary` | coordinator | primary | support/drift A2A |
| `coordinator-v1-comparison` | coordinator | comparison | support/drift A2A |

Every resource has `spec.platform: substrate`, `spec.type: Declarative`, `spec.declarative.runtime: go`, `spec.substrate.workerPoolRef.name: edai2-agents`, and a versioned `spec.substrate.snapshotsConfig.location`. `substrate.bucketName` is required and non-empty; chart templates concatenate that value with `/agent-substrate/`, the exact logical identity, the exact runtime variant, and a trailing slash. A valid sentinel rendering is `gs://edai2-sentinel-bucket/agent-substrate/retrieval/v1-primary/`; the drift and coordinator renderings substitute only their locked logical identity and permitted runtime variant. The `support` resource sets `EDAI2_LOGICAL_AGENT=retrieval`; the others use `drift` or `coordinator`, and `EDAI2_RUNTIME_VARIANT` is `v1-primary`, `v2-primary`, or `v1-comparison` as applicable. Values YAML contains no `${EDAI2_*}` or other shell-substitution placeholder, and rendering fails if the bucket, logical identity, or runtime variant is unset.

Every resource's `spec.sandbox.network.allowedDomains` permits only DNS, the pinned Substrate control-plane endpoints, and `agentgateway-proxy.edai2.svc.cluster.local`; direct llm-d, MCP, specialist API, Feast, PostgreSQL, and Valkey addresses are absent and denied.

Retrieval RemoteMCPServer is `STREAMABLE_HTTP` to `http://retrieval-mcp.edai2.svc.cluster.local:8080/mcp`; drift mirrors it at `http://drift-mcp.edai2.svc.cluster.local:8080/mcp`. Both discovery and invocation use global `proxy.url`.

Five credentials are disjoint: model, retrieval, drift, coordinator-to-specialist, facade-to-coordinator. Topic 14 proves unique secret references, intended resource bindings, and absence of direct specialist/MCP/llm-d/database addresses. Topic 18, after creating the actual gateway policies, owns the exhaustive five-key-by-wrong-route static matrix and exact 401/403 policy assertions.

Registry publication late-binds the generated ActorTemplate's digest-pinned shared Go runtime; a Python service image is rejected in registry `image`. Read-back must preserve semantic version+short commit, route, prompt, ModelConfig, snapshot and hashes. Rollback deletes an injected bad runtime and compare-and-swap points the facade alias to a still-published prior destination.

Both notebooks begin with deterministic parameter cells for base URL, fixture ID, model/index/feature version inputs; contain no outputs, secrets or raw PII.

## Ordered test-first execution

- [ ] Add red manifest/security tests and run `rtk uv run pytest tests/unit/llm/test_agent_manifests.py tests/unit/llm/test_registry.py -q`. Expected: nonzero until exact five-resource/three-identity fields, retrieval logical identity, required bucket-derived snapshots, disjoint credential references, late binding, and rollback exist.
- [ ] Add agent value files and run `rtk uv run pytest tests/unit/llm/test_agent_manifests.py -q`. Expected: exit 0; exactly five resources, exact WorkerPool/snapshot/RemoteMCPServer fields, three identities, `support` maps to `retrieval`, no `${EDAI2_*}` placeholder exists, and all credential references bind only to intended resources.
- [ ] Add registry templates/CLI and run `rtk uv run pytest tests/unit/llm/test_registry.py -q`. Expected: exit 0; generated ActorTemplate digest is late-bound, read-back is exact, Python image rejected, rollback preserves prior alias.
- [ ] Add source notebooks and run `rtk uv run jupyter nbconvert --clear-output --inplace notebooks/edai2/drift_agent_mcp.ipynb notebooks/edai2/retrieval_agent_mcp.ipynb`. Expected: exit 0; both notebooks remain valid and output-free.
- [ ] Run `rtk uv run pytest tests/unit/llm/test_notebooks.py -q`. Expected: exit 0; deterministic parameter cells exist and no output/credential/raw PII is present.
- [ ] Run `rtk uv run pytest tests/unit/llm/test_agent_manifests.py tests/unit/llm/test_registry.py tests/unit/llm/test_notebooks.py tests/unit/llm/test_safety.py -q` and `rtk git diff --check`. Expected: both exit 0.

## Evidence, cleanup, rubric, and DoD

Topic 14 owns rendered inventories, test reports and hashes only. It never publishes agents or executes notebooks. Later runtime owners capture registry and notebook evidence. Remove only nbconvert temporary files; no runtime acquired.

| Sheet3 cell | Local proof | Deferred proof |
|---|---|---|
| `Sheet3!E13:E21` | resource bindings, credential references, and registry contracts | Topic 18 gateway-policy matrix plus SandboxAgent/KEDA/registry runtime |
| `Sheet3!E22:E23` | cleared parameterized notebook structure | executed notebook copies |
| `Sheet3!E24:E25` | three runtime bindings and registry metadata | live routes/read-back |

## Definition of Done

Exactly five resources/three identities, retrieval logical identity, required bucket-derived snapshots, field-level bindings, disjoint credential references, registry late binding/read-back/rollback, and notebook clear/structure tests pass with no platform/chart-file collision. Exhaustive policy enforcement remains explicitly owned by Topic 18.

## Completion Record

| Field | Execution value |
|---|---|
| Status | Not started |
| Current branch/status | Record final `rtk git status --short --branch` |
| Affected files | Record only Topic 14 paths |
| Commands and exit codes | Record tests, nbconvert clear, final checks |
| Evidence hashes | Record rendered/test report SHA-256 |
| Screenshot QA | Not captured locally |
| Cleanup/runtime release | Record notebook temp cleanup; no runtime |
| Limitations | Record deferred publication/execution/GKE evidence |
| Handoff | `tmp/edai2-plan/execution-v1/local/15-evaluation-test-quality-load.md` |
