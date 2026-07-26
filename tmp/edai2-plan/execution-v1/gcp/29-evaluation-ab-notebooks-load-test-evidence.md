# Topic 29: Evaluation, A/B, Notebooks, Load-Test, and Test Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce reproducible evaluation, two isolated A/B experiments, executed agent notebooks, test-quality evidence, Locust performance evidence, agent-test UI proof, and two runtime-backed novel-idea proofs.

**Architecture:** A fresh <=6h evidence lease restores the verified index and releases. The primary evaluation runs exactly 60 fixed cases. Agent A/B compares coordinator v1/v2 on the same primary model; model A/B compares primary/comparison models on the same v1 agent configuration with one Ready model replica per arm. Notebooks, coverage, EP/BVA, mutation, Hypothesis/CrossHair, and Locust are executed rather than inferred from source.

**Tech Stack:** Python/pytest, Hypothesis, CrossHair, mutmut, Locust, Jupyter/nbconvert, kagent/MCP, Feast/pgvector, llm-d, Grafana, Playwright.

## Metadata

| Field | Decision |
|---|---|
| Phase | Evidence lease 2 of 4; execution topic 29 |
| Authoritative source tasks | `04.2_llm_design.md` Tasks 5-6, 9, 12 |
| Primary rubric cells | `Sheet3!E22`, `Sheet3!E23`, `Sheet3!E25`, `Sheet3!E27:E31`, `Sheet3!E44`, `Sheet3!E56`, `Sheet3!E57`, `Sheet3!E61`, `Sheet3!E62` |
| Prerequisites | Topic 28 suspended; Topics 25-27 registry/chat/gateway/telemetry records |
| Blocked successors | Topics 30-32 |
| Runtime owner | `topic29-eval`; fresh `rubric-evidence` lease <=6h |
| Execution class | `GCP-write/test-and-evaluation-evidence` |
| Branch rule | Same branch/common CI commit; serial |

## Global Constraints

- Read `C:\Users\oou1hc\.codex\RTK.md`; prefix shell commands with `rtk`.
- Fixed hashes: Section 03 `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`; EDAI2 `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`; `tmp/rubic-check/Coursework Tracking (Public).xlsx` `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- No branch/worktree/stage/commit changes.
- Start suspended; fresh project/billing/IAM/trial-expiry/spend/capacity/context/recovery-sink/external-input gate and lease <=6h.
- Require `EDAI2_GKE_KUBECONFIG=tmp/edai2-gcp/kubeconfig` and `EDAI2_GKE_CONTEXT=gke_${GOOGLE_CLOUD_PROJECT}_us-central1-a_edai2`. Every `kubectl` call includes `--kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT`; every Helm call includes `--kubeconfig $env:EDAI2_GKE_KUBECONFIG --kube-context $env:EDAI2_GKE_CONTEXT`; every script that queries or mutates Kubernetes receives both values. Never use or change the default kubeconfig/current context.
- `EDAI2_TFVARS_PATH=tmp/edai2-gcp/coursework.auto.tfvars` remains untracked.
- Primary evaluation is exactly 60 static cases and five authoritative gates.
- Agent A/B: 60 observed sessions per arm; v1-primary vs v2-primary; same primary model/index/traffic fixture.
- Model A/B: 60 observed sessions per arm; v1-primary vs v1-comparison; one Ready primary and one Ready comparison model. No factorial scaling in this topic.
- Stable UUID assignment, selected/discarded IDs, held-constant hashes, and prior-alias read-back are mandatory.
- Promotion occurs only after all configured gates; failed experiments preserve previous facade/registry alias.
- Changed-production-Python coverage >90%; changed-code mutation score >80%. Scope is derived by `verify_edai2_test_scope.py`, never hand-selected.
- Locust: 1 user, spawn 1/s, 2 minutes, zero unexpected failures, retrieval p95 <=750ms; HTML/CSV nonempty.
- Notebooks must execute and contain output but no credentials/raw PII.
- One bounded retry per failing live/capture operation after diagnosed transient cause; truthful partial otherwise.
- `Sheet3!E49` remains out of scope.
- Owned screenshots are the three kagent chats, four test-quality captures, and `locust_report.png`; all use `1600x1000`, viewport/non-element crop, full stable selectors, temp PNG/signature/decode/full-load/atomic replacement, manifest/machine/hash/proves-does-not fields, original-resolution inspection, and strict rejection states.

## Read-Only Planning Refresh

1. `rtk git status --short --branch`
   - Expected: same branch/common commit.
2. `rtk python -c "import hashlib; p=['tmp/edai2-plan/03_data_generator_improvement.md','tmp/edai2-plan/04.2_llm_design.md','tmp/rubic-check/Coursework Tracking (Public).xlsx']; print([hashlib.sha256(open(x,'rb').read()).hexdigest() for x in p])"`
   - Expected: fixed hashes.
3. `rtk rg -n "Status|suspended|benchmark.json|Handoff" tmp/edai2-plan/execution-v1/gcp/28-rag-inference-benchmarks.md`
   - Expected: Topic 28 truthful results and suspended state.
4. `rtk kubectl --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT cluster-info`
   - Expected: the dedicated kubeconfig resolves the approved GKE API; mismatch or failure is a safe stop.
5. `rtk uv run python scripts/qa/verify_edai2_test_scope.py --base $env:EDAI2_BASE_REF --head $env:EDAI2_COMMIT_SHA --config configs/llm/test_scope.yaml --check-only`
   - Expected: deterministic changed-production-Python scope and no generated/vendor files.

## Scope

- Run primary 60-case evaluation.
- Run isolated agent and model A/B experiments and capture real A/B dashboard.
- Execute both MCP/agent notebooks.
- Run/render coverage, EP/BVA, mutation, Hypothesis/CrossHair, and Locust evidence.
- Verify routed UI demonstrates all three agents.
- Prove effective-date boundaries and hash-bound citation rejection as two novel ideas.
- Suspend and release fresh lease.

## Non-Goals

- No factorial benchmark, CI rebuild, registry republish, backup/recovery, or final docs.
- No synthetic screenshot substituted for executed result.

## Exact File Map

| Role | Exact paths |
|---|---|
| Read | `tests/fixtures/llm/evaluation_cases.jsonl`, `configs/llm/evaluation.yaml` |
| Read/execute | `notebooks/edai2/drift_agent_mcp.ipynb`, `notebooks/edai2/retrieval_agent_mcp.ipynb` |
| Read/execute | `tests/load/llm/locustfile.py`, `tests/load/llm/test_locust_contract.py` |
| Read/execute | `tests/unit/llm/test_contracts.py`, `tests/unit/llm/test_indexing.py`, `tests/unit/llm/test_retrieval.py`, `tests/unit/llm/test_drift.py` |
| Read/execute | `tests/unit/llm/test_inference.py`, `tests/unit/llm/test_coordinator.py`, `tests/unit/llm/test_safety.py`, `tests/unit/llm/test_evaluation.py` |
| Read/execute | `tests/contract/llm/test_api_contracts.py`, `tests/contract/llm/test_mcp_contracts.py`, `tests/contract/llm/test_section03_contract.py` |
| Read/execute | `tests/property/llm/test_idempotency.py`, `tests/integration/llm/test_feast_pgvector.py`, `tests/integration/llm/test_section03_ingestion.py` |
| Read/execute | `tests/integration/llm/test_streaming_writers.py`, `tests/integration/llm/test_airflow_datahub.py`, `tests/integration/llm/test_gke_agents.py` |
| Execute | `scripts/llm/run_evaluation.py`, `scripts/qa/verify_edai2_test_scope.py`, `scripts/qa/capture_edai2_evidence.py` |
| Execute | `scripts/gke/manage_profile.py`, `scripts/gke/check_budget.py` |
| Read external/untracked | `tmp/edai2-gcp/kubeconfig` |
| Generate | `evidence/04_2_llm_design/evaluation/report.json` |
| Generate | `evidence/04_2_llm_design/evaluation/agent_ab.json`, `evidence/04_2_llm_design/evaluation/model_ab.json` |
| Generate | `evidence/04_2_llm_design/notebooks/drift_agent_mcp.ipynb`, `evidence/04_2_llm_design/notebooks/retrieval_agent_mcp.ipynb` |
| Generate | `evidence/04_2_llm_design/load/locust.html`, `evidence/04_2_llm_design/load/locust_stats.csv` |
| Generate | `evidence/04_2_llm_design/tests/coverage.json`, `evidence/04_2_llm_design/tests/ep_bva.json`, `evidence/04_2_llm_design/tests/mutation.json` |
| Generate | `evidence/04_2_llm_design/tests/properties_crosshair.json`, `evidence/04_2_llm_design/tests/novel_ideas.json` |
| Screenshot owner | `evidence/04_2_llm_design/screenshots/kagent_retrieval_chat.png`, `evidence/04_2_llm_design/screenshots/kagent_drift_chat.png`, `evidence/04_2_llm_design/screenshots/kagent_coordinator_chat.png` |
| Screenshot owner | `evidence/04_2_llm_design/screenshots/coverage_and_api_fixtures.png`, `evidence/04_2_llm_design/screenshots/ep_bva.png`, `evidence/04_2_llm_design/screenshots/mutation.png` |
| Screenshot owner | `evidence/04_2_llm_design/screenshots/properties_crosshair.png`, `evidence/04_2_llm_design/screenshots/locust_report.png` |
| Update through capture CLI | `evidence/04_2_llm_design/screenshots/ui_manifest.json` |

## Interfaces, Data Flow, and Failure Modes

Static cases -> coordinator/agent/MCP/model/data paths -> per-case observations -> five gates.

Stable UUIDs -> fixed experiment arm -> exact runtime/ModelConfig -> metrics -> decision -> CAS promotion or unchanged alias -> Grafana A/B dashboard.

Source notebooks -> nbconvert execution -> output evidence copies -> content/hash/PII scan.

Git diff scope -> coverage/mutation/property/test commands -> rendered reports -> contextual screenshots.

Failures: arm contamination, missing samples, inactive/extra replica, assignment drift, changed constant, failed gate incorrectly promoted, notebook stale output, mutation wrong scope, CrossHair timeout without bounded status, Locust failure/p95 miss, UI generic page. Each leaves specific cells unsatisfied.

## Ordered Test-First Execution Tasks

### Task 1: Acquire fresh evaluation lease

- [ ] Run `rtk uv run python scripts/gke/check_budget.py --project $env:GOOGLE_CLOUD_PROJECT --trial-expires-at $env:EDAI2_TRIAL_EXPIRES_AT --current-spend-usd $env:EDAI2_CURRENT_SPEND_USD --spend-observed-at $env:EDAI2_SPEND_OBSERVED_AT --usage-ledger evidence/04_2_llm_design/gke/usage_ledger.json --envelope configs/gke/cost_envelope.yaml --requested-profile rubric-evidence --requested-ttl 6h --output evidence/04_2_llm_design/gke/cost_forecast.json`.
  - Expected: exit 0.
- [ ] Run `rtk uv run python scripts/gke/manage_profile.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT rubric-evidence --ttl 6h --acquire-session-lease --owner topic29-eval --commit-sha $env:EDAI2_COMMIT_SHA`.
  - Expected: fresh sole lease and verified active index/releases.

### Task 2: Run primary and isolated A/B evaluations

- [ ] Run `rtk uv run python scripts/llm/run_evaluation.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --cases tests/fixtures/llm/evaluation_cases.jsonl --output evidence/04_2_llm_design/evaluation/report.json`.
  - Expected: exactly 60 results, all five gates, per-case revisions/citations/tool/safety/latency/cost.
- [ ] Run `rtk uv run python scripts/llm/run_evaluation.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --experiment agent_exp_v1 --sessions-per-arm 60 --select-stable-uuids --runtime-a v1-primary --runtime-b v2-primary --index-version $env:EDAI2_INDEX_VERSION --output evidence/04_2_llm_design/evaluation/agent_ab.json`.
  - Expected: 60 observed sessions per arm, held primary model, exact assignment/metrics/decision, failed gate preserves prior alias.
- [ ] Run `rtk uv run python scripts/llm/run_evaluation.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --experiment model_exp_v1 --sessions-per-arm 60 --select-stable-uuids --runtime-a v1-primary --runtime-b v1-comparison --model-replicas-per-arm 1 --index-version $env:EDAI2_INDEX_VERSION --output evidence/04_2_llm_design/evaluation/model_ab.json`.
  - Expected: one primary and one comparison replica, 60 observed sessions each, held v1 config, exact decision/read-back.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --verify-ab-dashboard-provenance evidence/04_2_llm_design/screenshots/grafana_ab.png --agent-evidence evidence/04_2_llm_design/evaluation/agent_ab.json --model-evidence evidence/04_2_llm_design/evaluation/model_ab.json --producer-topic 27 --strict-partial`.
  - Expected: Topic 27 retains sole screenshot ownership; if final A/B timestamps make it stale, mark it for Topic 31's one bounded refresh rather than creating a duplicate.

### Task 3: Execute notebooks and prove agent-test UI

- [ ] Run `rtk uv run jupyter nbconvert --to notebook --execute notebooks/edai2/drift_agent_mcp.ipynb --output-dir evidence/04_2_llm_design/notebooks --output drift_agent_mcp.ipynb`.
  - Expected: agent -> drift MCP -> Feast daily health and Section 03 feature/label context with versions, no PII/secret.
- [ ] Run `rtk uv run jupyter nbconvert --to notebook --execute notebooks/edai2/retrieval_agent_mcp.ipynb --output-dir evidence/04_2_llm_design/notebooks --output retrieval_agent_mcp.ipynb`.
  - Expected: agent -> retrieval MCP -> Feast/pgvector chunks with versions, no PII/secret.
- [ ] Run `rtk uv run pytest tests/e2e/llm/test_required_uis.py -q -k agent_chat_all_three`.
  - Expected: Topic 29's own three routed chat screenshots demonstrate retrieval, drift, and coordinator while consuming Topic 26 registry/KEDA/chat-smoke machine records and Topic 27 route evidence; `Sheet3!E44` machine gate passes without creating a duplicate screenshot owner.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --capture-agent-chats retrieval,drift,coordinator --viewport 1600x1000 --outputs evidence/04_2_llm_design/screenshots/kagent_retrieval_chat.png,evidence/04_2_llm_design/screenshots/kagent_drift_chat.png,evidence/04_2_llm_design/screenshots/kagent_coordinator_chat.png --manifest evidence/04_2_llm_design/screenshots/ui_manifest.json --registry-evidence evidence/04_2_llm_design/agents/registry.json --notebook-root evidence/04_2_llm_design/notebooks --strict`.
  - Expected: three contextual images show named agent/version, request, tool/routing result, grounded non-PII output, and linked notebook/registry machine evidence.

### Task 4: Run test-quality gates and render evidence

- [ ] Run `rtk uv run pytest tests/unit/llm tests/contract/llm tests/integration/llm --cov=src/vina_bim_shop/llm --cov-config=configs/llm/coverage.ini --cov-report=json:evidence/04_2_llm_design/tests/coverage.json -q`.
  - Expected: changed EDAI2 package coverage >90%, fixtures/mocks/API tests present.
- [ ] Run `rtk uv run pytest tests/unit/llm tests/contract/llm -q -k "boundary or partition or bva or effective_date"`.
  - Expected: parametrized boundary partitions cover required input/status/date/PSI cases and write `ep_bva.json`.
- [ ] Run `rtk uv run mutmut run --paths-to-mutate src/vina_bim_shop/llm`.
  - Expected: verified changed-code scope and score >80%, recorded in `mutation.json`.
- [ ] Run `rtk uv run pytest tests/property/llm/test_idempotency.py -q`.
  - Expected: Hypothesis passes with recorded examples/seed.
- [ ] Run `rtk uv run crosshair check src/vina_bim_shop/llm/contracts.py src/vina_bim_shop/llm/indexing.py --per_condition_timeout 10 --per_path_timeout 3`.
  - Expected: bounded analysis has no counterexample; exact status recorded.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --capture-test-evidence --viewport 1600x1000 --strict --root evidence/04_2_llm_design`.
  - Expected: `coverage_and_api_fixtures.png`, `ep_bva.png`, `mutation.png`, and `properties_crosshair.png` are contextual executed-result captures.

### Task 5: Run Locust and capture report

- [ ] Run `rtk uv run locust -f tests/load/llm/locustfile.py --headless -u 1 -r 1 -t 2m --host $env:EDAI2_RETRIEVAL_BASE_URL --html evidence/04_2_llm_design/load/locust.html --csv evidence/04_2_llm_design/load/locust_stats`.
  - Expected: nonempty HTML/CSV, zero unexpected failures, measured throughput, retrieval p95 <=750ms, sanitized resolved host.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --capture locust-report --viewport 1600x1000 --output evidence/04_2_llm_design/screenshots/locust_report.png --manifest evidence/04_2_llm_design/screenshots/ui_manifest.json --machine-evidence evidence/04_2_llm_design/load/locust_stats.csv --strict`.
  - Expected: contextual Locust results table/time/load/p95 visible.

### Task 6: Prove the two novel ideas

- [ ] Run `rtk uv run pytest tests/unit/llm/test_indexing.py -q -k effective_date`.
  - Expected: immediately-before/at/after boundaries pass and runtime query evidence is linked for `Sheet3!E61`.
- [ ] Run `rtk uv run pytest tests/unit/llm/test_retrieval.py tests/unit/llm/test_safety.py -q -k "hash or unsupported or citation"`.
  - Expected: tampered hash/unsupported claim rejection passes and runtime proof is linked for `Sheet3!E62`.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --novel-ideas-report --output evidence/04_2_llm_design/tests/novel_ideas.json --strict`.
  - Expected: commands, results, runtime artifact hashes, and explicit value beyond taught baseline.

### Task 7: QA captures and suspend

- [ ] Inspect all eight owned screenshots at original resolution.
  - Expected: exact results/selectors visible, no rejected state.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --verify-screenshot-topic 29 --expected-count 8 --manifest evidence/04_2_llm_design/screenshots/ui_manifest.json --strict`.
  - Expected: exact names/count/hashes/machine links.
- [ ] Run `rtk uv run python scripts/gke/manage_profile.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT suspended --release-session-lease --owner topic29-eval --require-evidence-manifest evidence/04_2_llm_design/evaluation/report.json`.
  - Expected: pools zero, ingress disabled, no forwarding rule.
- [ ] Run `rtk git status --short --branch`.
  - Expected: same branch/revision lineage recorded.

## Evidence and Screenshot Ownership

Topic 29 owns exactly eight screenshots: three kagent chats, four test-quality captures, and `locust_report.png`. Topic 27 solely owns `grafana_ab.png`. Topic 29 is the sole primary rubric owner for the cells listed in Metadata.

## Cleanup and Runtime Release

- Restore prior facade/registry alias after any failed A/B; retain promotion only after passing gate/read-back.
- Restore normal one primary model replica and comparison zero before suspend.
- Remove load/evaluation Jobs and temporary route; preserve reports/notebooks.
- Release `topic29-eval`; verify pools zero/no forwarding rule.

## Rubric Traceability

| Cells | Points | Gate |
|---|---:|---|
| `Sheet3!E22:E23` | 4 | two executed agent/MCP notebooks |
| `Sheet3!E25` | 2 | coordinator registry/chat UI consumption |
| `Sheet3!E27:E31` | 9 | coverage, EP/BVA, mutation, properties/CrossHair, Locust |
| `Sheet3!E44` | 2 | routed UI demonstrates all three agents |
| `Sheet3!E56:E57` | 2 | isolated agent/model A/B plus dashboard |
| `Sheet3!E61:E62` | 4 | effective-date and citation-integrity novel ideas |

## Definition of Done

- [ ] Fresh gate/lease/context and fixed hashes pass.
- [ ] Primary evaluation, both isolated A/B experiments, and decisions are complete and honest.
- [ ] Both notebooks execute with safe outputs.
- [ ] All five test/load gates and two novel-idea gates pass or are truthfully failed.
- [ ] Eight screenshots pass strict/original QA.
- [ ] Normal model/alias state is restored; runtime suspended/released.
- [ ] Final `rtk git status --short --branch` is recorded.

## Completion Record

- **Status:** Not started; no evaluation/test/A-B cell claim.
- **Branch / revision:** Record exact `rtk git status --short --branch`; none recorded.
- **Affected files:** None at plan-authoring time.
- **Command / exit-code log:** No execution commands recorded.
- **Evidence / SHA-256 log:** No evaluation/notebook/test/load evidence recorded.
- **Screenshot QA:** Eight owned screenshots not captured.
- **Cleanup / runtime release:** No lease held by this plan artifact.
- **Limitations:** Any missed numeric/gate result lowers the truthful final score.
- **Handoff:** Topic 30 starts only after suspended state and receives experiment/alias/model/index hashes and limitations.
