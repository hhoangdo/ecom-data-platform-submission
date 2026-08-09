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
| Status | Complete - corrected local/static contracts implement five SandboxAgent resources under three logical identities, platform-only model credential references, late-bound provenance including per-runtime coordinator model hashes and five byte-identical held revisions, injected publish/read-back validation, CAS-safe rollback, and cleared tutorial notebooks with exact public request/response schema shapes. |
| Current branch/status | `## feature/implement-edai2...origin/feature/implement-edai2`; final status and staged-index identity were rechecked after this record update. No entry was staged or unstaged. |
| Affected files | Created: `infra/helm/edai2/values/retrieval-agent.yaml`, `infra/helm/edai2/values/drift-agent.yaml`, `infra/helm/edai2/values/coordinator-agent.yaml`, `infra/agentregistry/edai2/retrieval-agent.yaml`, `infra/agentregistry/edai2/drift-agent.yaml`, `infra/agentregistry/edai2/coordinator-agent.yaml`, `scripts/llm/publish_agents.py`, `notebooks/edai2/drift_agent_mcp.ipynb`, `notebooks/edai2/retrieval_agent_mcp.ipynb`, `tests/unit/llm/test_agent_manifests.py`, `tests/unit/llm/test_registry.py`, and `tests/unit/llm/test_notebooks.py`. Modified: this Completion Record only. No platform/chart, dependency, lockfile, Topic 13, secret, cluster, registry, or GCP path changed. |
| Commands and exit codes | Preflight `rtk git status --short --branch`, all three locked `rtk proxy certutil -hashfile ... SHA256` checks, predecessor completion lookup, `rtk uv lock --check`, and `rtk git diff --check` exited `0`. The locked source SHA-256 values were `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`, `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`, and `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`. Pre-edit `rtk git ls-files --stage` identity was 931 lines, SHA-256 `08ae60bb5c72e320e0a0d15e10be6f8a1c04dc70740c702915574736f35d847b`. Initial TDD red: manifest/registry command exited `1` with 8 expected missing-file failures; notebook command exited `1` with 2 expected missing-notebook failures. First correction TDD red: manifest/registry command exited `1` with 5 expected contract failures and 6 passes; green exited `0` (`11 passed`), and the prior final suite exited `0` (`19 passed`). Final provenance TDD red: `rtk uv run pytest tests/unit/llm/test_registry.py -q` exited `1` with 7 expected missing-provenance failures and 4 passes; green exited `0` (`12 passed`), and the prior final suite exited `0` (`24 passed`). Final notebook QA TDD red: `rtk uv run pytest tests/unit/llm/test_notebooks.py -q` exited `1` with 2 expected missing-interface/tutorial failures and 2 passes. `rtk uv run jupyter nbconvert --clear-output --inplace notebooks/edai2/drift_agent_mcp.ipynb notebooks/edai2/retrieval_agent_mcp.ipynb` exited `0` without executing cells; focused notebook tests then exited `0` (`4 passed`); final `rtk uv run pytest tests/unit/llm/test_agent_manifests.py tests/unit/llm/test_registry.py tests/unit/llm/test_notebooks.py tests/unit/llm/test_safety.py -q` exited `0` (`26 passed`). Post-record `rtk uv lock --check`, `rtk git diff --check`, and `rtk git status --short --branch` exited `0`; final `rtk git ls-files --stage` was byte-for-byte identical to pre-edit (931 lines, the same SHA-256). |
| Evidence hashes | Correction notebook clear-output log `tmp/edai2-local/topic14/notebooks-clear-correction.txt` SHA-256 `38f62e4898cbbb2c5e2614641f87c1ffa64492c0ab47705845a461cf164869c8`; first correction acceptance log `tmp/edai2-local/topic14/acceptance-tests-correction.txt` SHA-256 `701ee7b625ac543d49f8557721baba8e4f3f94fe4b8fb867d245f85c0137cb7b`; provenance acceptance log `tmp/edai2-local/topic14/acceptance-tests-provenance-correction.txt` SHA-256 `f35f5fc89f7d1a0c83397126d3dc4c91cf95c6b20605b2b1de50dcd9912cc81b`; final notebook clear-output log `tmp/edai2-local/topic14/notebooks-clear-qa-correction.txt` SHA-256 `6bd6a40a2677b791f6c07266f816a8f6ca63047993062faaa48c1ea7b73b24f1`; final notebook QA acceptance log `tmp/edai2-local/topic14/acceptance-tests-notebook-qa-correction.txt` SHA-256 `7f80978aecfb61e07888b9204f9cd907b9d8cd06e61e34a55fc019418de34df9`. These are local machine evidence only; late-binding tokens are not runtime evidence. |
| Screenshot QA | Not captured locally |
| Cleanup/runtime release | `nbconvert --clear-output` left both source notebooks valid and output-free; the injected-runner tests removed their owned `TemporaryDirectory` on success and read-back mismatch. No notebook kernel, cluster, registry, Docker resource, secret, lease, model, or cloud runtime was acquired. Local test logs remain under `tmp/edai2-local/topic14/` as machine evidence. |
| Limitations | This topic did not install or invoke `arctl`, publish a registry record, render/apply charts, contact Kubernetes/GKE/Kind, execute a notebook, or capture a UI. `substrate.bucketName` remains a declared empty render input that Topic 16 must fail closed until Terraform supplies it. The pre-existing `/notebooks/` ignore rule means the two verified source notebooks are intentionally absent from `git status`; it was not changed and no file was force-staged. Hash and image tokens require future caller-supplied immutable values and are not evidence. Topic 18 owns the exhaustive gateway-policy matrix; later runtime owners own registry read-back, deployed SandboxAgent/KEDA proof, and executed notebook evidence. |
| Handoff | `tmp/edai2-plan/execution-v1/local/15-evaluation-test-quality-load.md`; consume the Topic 14 static contracts without changing Topic 14 resources. |
