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
- Fixed hashes: Section 03 `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`; EDAI2 `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`; `tmp/rubic-check/Coursework Tracking (Public).xlsx` `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- No branch/worktree/stage/commit changes.
- Consume the completed local implementation. If a source/IaC/chart defect appears, capture it, release or suspend any owned runtime, mark this topic `Partial`, and return it to the owning local topic; do not patch implementation during a live cloud lease.
- Start suspended; run a redacted `check_budget.py --live-external-preflight` for project lifecycle, billing linkage, exact IAM permissions, trial expiry, spend/forecast, notification target, approved recovery sink, DNS, capacity, context, and external inputs before acquiring a lease <=6h.
- Require `EDAI2_GKE_KUBECONFIG=tmp/edai2-gcp/kubeconfig` and `EDAI2_GKE_CONTEXT=gke_${GOOGLE_CLOUD_PROJECT}_us-central1-a_edai2`. Every `kubectl` call includes `--kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT`; every Helm call includes `--kubeconfig $env:EDAI2_GKE_KUBECONFIG --kube-context $env:EDAI2_GKE_CONTEXT`; every script that queries or mutates Kubernetes receives both values. Never use or change the default kubeconfig/current context.
- `EDAI2_TFVARS_PATH` is absolute, resolves exactly to this repository's `tmp/edai2-gcp/coursework.auto.tfvars`, and remains untracked.
- Public reachability starts disabled. After the lease, create only `retrieval` and `chat` routes through ACME staging then production; bind their expiry to the lease, record them in `gateway/topic29_routes.json`, pass that manifest to every routed test/capture, and disable them in `finally` before suspension. No private UI or other service is exposed.
- Primary evaluation is exactly 60 static cases. Its five authoritative gates are recall@4 >=0.85, citation precision >=0.90, safety pass rate >=0.95, retrieval p95 <=750 ms, and generation p95 <=20 s.
- Agent A/B: 60 observed sessions per arm; v1-primary vs v2-primary; same primary model/index/traffic fixture.
- Model A/B: 60 observed sessions per arm; v1-primary vs v1-comparison; one Ready primary and one Ready comparison model. No factorial scaling in this topic.
- Stable UUID assignment, selected/discarded IDs, held-constant hashes, and prior-alias read-back are mandatory.
- Agent A/B promotion requires at least a 2 percentage-point improvement in either groundedness or citation precision, no safety regression, no increase in tool-failure rate, and p95 latency regression <=5%.
- Model A/B promotion requires all five primary gates plus cost per 100 requests improvement >=20%; a failed experiment preserves the previous facade/registry alias and model route.
- Changed-production-Python coverage >90%; changed-code mutation score >80%. Scope is derived by `verify_edai2_test_scope.py`, never hand-selected.
- Locust: 1 user, spawn 1/s, 2 minutes, zero unexpected failures, retrieval p95 <=750ms; HTML/CSV nonempty.
- Notebooks must execute and contain output but no credentials/raw PII.
- After the initial empirical suite, permit exactly one session-wide bounded tuning retry. It may change only retrieval top-k, reranker cutoff, or the coordinator-v2 prompt/config hash; it must preserve cases, models, data/index, routes, replicas, assignments, sessions, seed, thresholds, and baseline evidence. A gate still missed after that retry remains `Partial` or `Missing`. A separate one-time capture retry is allowed only for a diagnosed rendering/transient cause.
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
| Execute | `scripts/gke/manage_profile.py`, `scripts/gke/check_budget.py`, `scripts/gke/configure_evidence_ingress.py` |
| Read external/untracked | `tmp/edai2-gcp/kubeconfig` |
| Generate immutable gate evidence | `evidence/04_2_llm_design/gke/gcp_preflight_topic29.json`, `evidence/04_2_llm_design/gke/cost_forecast_topic29.json` |
| Update append-only | `evidence/04_2_llm_design/gke/usage_ledger.json` |
| Generate | `evidence/04_2_llm_design/gateway/topic29_routes.json` |
| Generate | `evidence/04_2_llm_design/evaluation/report.json` |
| Generate | `evidence/04_2_llm_design/evaluation/agent_ab.json`, `evidence/04_2_llm_design/evaluation/model_ab.json` |
| Generate only for the one permitted empirical retry | `evidence/04_2_llm_design/evaluation/retry.json` |
| Generate | `evidence/04_2_llm_design/notebooks/drift_agent_mcp.ipynb`, `evidence/04_2_llm_design/notebooks/retrieval_agent_mcp.ipynb` |
| Generate | `evidence/04_2_llm_design/load/locust.html`, `evidence/04_2_llm_design/load/locust_stats.csv` |
| Generate | `evidence/04_2_llm_design/tests/test_scope.json`, `evidence/04_2_llm_design/tests/coverage.json`, `evidence/04_2_llm_design/tests/ep_bva.json`, `evidence/04_2_llm_design/tests/mutation.json` |
| Generate | `evidence/04_2_llm_design/tests/properties_crosshair.json`, `evidence/04_2_llm_design/tests/novel_effective_date.json`, `evidence/04_2_llm_design/tests/novel_citation_integrity.json`, `evidence/04_2_llm_design/tests/novel_ideas.json` |
| Screenshot owner | `evidence/04_2_llm_design/screenshots/kagent_retrieval_chat.png`, `evidence/04_2_llm_design/screenshots/kagent_drift_chat.png`, `evidence/04_2_llm_design/screenshots/kagent_coordinator_chat.png` |
| Screenshot owner | `evidence/04_2_llm_design/screenshots/coverage_and_api_fixtures.png`, `evidence/04_2_llm_design/screenshots/ep_bva.png`, `evidence/04_2_llm_design/screenshots/mutation.png` |
| Screenshot owner | `evidence/04_2_llm_design/screenshots/properties_crosshair.png`, `evidence/04_2_llm_design/screenshots/locust_report.png` |
| Update through capture CLI | `evidence/04_2_llm_design/screenshots/ui_manifest.json` |

## Interfaces, Data Flow, and Failure Modes

Lease -> ACME staging validation -> production-only retrieval/chat routes -> hash-bound route manifest -> routed evaluations/notebooks/chats/Locust -> route disable in `finally`.

Static cases -> coordinator/agent/MCP/model/data paths -> per-case observations -> recall@4/citation/safety/retrieval-p95/generation-p95 gates.

Stable UUIDs -> fixed experiment arm -> exact runtime/ModelConfig -> metrics -> decision -> CAS promotion or unchanged alias -> Grafana A/B dashboard.

Source notebooks -> nbconvert execution -> output evidence copies -> content/hash/PII scan.

Git diff scope -> coverage/mutation/property/test commands -> rendered reports -> contextual screenshots.

Failures: missing/extra/stale route, staging or production certificate failure, route expiry beyond lease, arm contamination, missing samples, inactive/extra replica, assignment drift, changed constant or threshold, failed gate incorrectly promoted, notebook stale output, mutation wrong scope, CrossHair timeout without bounded status, Locust failure/p95 miss, UI generic page, or leaked ingress. Each leaves specific cells `Partial`/`Missing`; cleanup still disables routes and suspends.

## Ordered Test-First Execution Tasks

### Task 1: Acquire fresh evaluation lease

- [ ] Run `rtk uv run python scripts/gke/check_budget.py --project $env:GOOGLE_CLOUD_PROJECT --billing-account-env GOOGLE_BILLING_ACCOUNT --budget-notification-target-env EDAI2_BUDGET_NOTIFICATION_TARGET --recovery-sink-env EDAI2_VAULT_RECOVERY_SINK --recovery-sink-attestation $env:EDAI2_RECOVERY_SINK_ATTESTATION --required-permissions configs/gke/required_permissions.json --dns-probes acme-staging-v02.api.letsencrypt.org,huggingface.co,storage.googleapis.com --live-external-preflight --preflight-output evidence/04_2_llm_design/gke/gcp_preflight_topic29.json --trial-expires-at $env:EDAI2_TRIAL_EXPIRES_AT --current-spend-usd $env:EDAI2_CURRENT_SPEND_USD --spend-observed-at $env:EDAI2_SPEND_OBSERVED_AT --usage-ledger evidence/04_2_llm_design/gke/usage_ledger.json --envelope configs/gke/cost_envelope.yaml --requested-profile rubric-evidence --requested-ttl 6h --output evidence/04_2_llm_design/gke/cost_forecast_topic29.json`.
  - Expected: all live external/IAM/budget/capacity gates pass and only redacted hashes, booleans, timestamps, and bounded numeric values are emitted.
- [ ] Run `rtk uv run python scripts/gke/manage_profile.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT rubric-evidence --ttl 6h --acquire-session-lease --owner topic29-eval --commit-sha $env:EDAI2_COMMIT_SHA`.
  - Expected: fresh sole lease and verified active index/releases.
- [ ] Run `rtk uv run python scripts/gke/configure_evidence_ingress.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --enable --route-set topic29-evaluation --routes retrieval,chat --issuer acme-staging --lease-owner topic29-eval --output evidence/04_2_llm_design/gateway/topic29_routes.json --strict`.
  - Expected: only the two named routes exist, staging HTTP-01 and certificate read-back pass, and the manifest records hashed hosts, nonsecret URLs, certificate state, lease expiry, revision, and cleanup selector.
- [ ] Run `rtk uv run python scripts/gke/configure_evidence_ingress.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --promote-route-manifest evidence/04_2_llm_design/gateway/topic29_routes.json --issuer acme-production --require-routes retrieval,chat --lease-owner topic29-eval --strict`.
  - Expected: production certificates and both routes are Ready, their expiry does not exceed the lease, staging history remains in the manifest, and no additional service is reachable.

### Task 2: Run primary and isolated A/B evaluations

- [ ] Run `rtk uv run python scripts/llm/run_evaluation.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --route-manifest evidence/04_2_llm_design/gateway/topic29_routes.json --cases tests/fixtures/llm/evaluation_cases.jsonl --gates "recall_at_4>=0.85,citation_precision>=0.90,safety_pass_rate>=0.95,retrieval_p95_ms<=750,generation_p95_ms<=20000" --output evidence/04_2_llm_design/evaluation/report.json`.
  - Expected: exactly 60 results, all five exact gates, per-case revisions/citations/tool/safety/latency/cost, and route-manifest hash.
- [ ] Run `rtk uv run python scripts/llm/run_evaluation.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --route-manifest evidence/04_2_llm_design/gateway/topic29_routes.json --experiment agent_exp_v1 --sessions-per-arm 60 --select-stable-uuids --runtime-a v1-primary --runtime-b v2-primary --index-version $env:EDAI2_INDEX_VERSION --min-groundedness-or-citation-gain-pp 2 --max-safety-regression 0 --max-tool-failure-rate-delta 0 --max-p95-regression-pct 5 --promote-if-all --output evidence/04_2_llm_design/evaluation/agent_ab.json`.
  - Expected: 60 observed sessions per arm, held primary model, exact assignment/metrics/decision; promotion occurs only when one quality metric improves >=2 points with no safety/tool-failure regression and p95 regression <=5%, otherwise the prior alias is read back unchanged.
- [ ] Run `rtk uv run python scripts/llm/run_evaluation.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --route-manifest evidence/04_2_llm_design/gateway/topic29_routes.json --experiment model_exp_v1 --sessions-per-arm 60 --select-stable-uuids --runtime-a v1-primary --runtime-b v1-comparison --model-replicas-per-arm 1 --index-version $env:EDAI2_INDEX_VERSION --gates "recall_at_4>=0.85,citation_precision>=0.90,safety_pass_rate>=0.95,retrieval_p95_ms<=750,generation_p95_ms<=20000" --min-cost-per-100-improvement-pct 20 --promote-if-all --output evidence/04_2_llm_design/evaluation/model_ab.json`.
  - Expected: one primary and one comparison replica, 60 observed sessions each, held v1 config, exact decision/read-back; all five quality/latency gates and >=20% cost-per-100 improvement are required, otherwise the previous model route remains active.
- [ ] Only if an empirical gate fails, run once: `rtk uv run python scripts/llm/run_evaluation.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --route-manifest evidence/04_2_llm_design/gateway/topic29_routes.json --bounded-tuning-retry-from evidence/04_2_llm_design/evaluation/report.json,evidence/04_2_llm_design/evaluation/agent_ab.json,evidence/04_2_llm_design/evaluation/model_ab.json --retry-number 1 --allowed-tuning retrieval_top_k,reranker_cutoff,coordinator_v2_prompt --preserve-baselines --unchanged-gates --output evidence/04_2_llm_design/evaluation/retry.json`.
  - Expected: any change outside the three allowed settings or any second retry fails; before/after hashes and results remain durable, and a remaining miss is marked `Partial`/`Missing`.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --verify-ab-dashboard-provenance evidence/04_2_llm_design/screenshots/grafana_ab.png --agent-evidence evidence/04_2_llm_design/evaluation/agent_ab.json --model-evidence evidence/04_2_llm_design/evaluation/model_ab.json --producer-topic 27 --strict-partial`.
  - Expected: Topic 27 retains sole screenshot ownership; if final A/B timestamps make it stale, mark it for Topic 31's one bounded refresh rather than creating a duplicate.

### Task 3: Execute notebooks and prove agent-test UI

- [ ] Run `rtk powershell -NoProfile -Command '$env:EDAI2_ROUTE_MANIFEST="evidence/04_2_llm_design/gateway/topic29_routes.json"; & rtk uv run jupyter nbconvert --to notebook --execute notebooks/edai2/drift_agent_mcp.ipynb --output-dir evidence/04_2_llm_design/notebooks --output drift_agent_mcp.ipynb; exit $LASTEXITCODE'`.
  - Expected: agent -> drift MCP -> Feast daily health and Section 03 feature/label context with versions, no PII/secret.
- [ ] Run `rtk powershell -NoProfile -Command '$env:EDAI2_ROUTE_MANIFEST="evidence/04_2_llm_design/gateway/topic29_routes.json"; & rtk uv run jupyter nbconvert --to notebook --execute notebooks/edai2/retrieval_agent_mcp.ipynb --output-dir evidence/04_2_llm_design/notebooks --output retrieval_agent_mcp.ipynb; exit $LASTEXITCODE'`.
  - Expected: agent -> retrieval MCP -> Feast/pgvector chunks with versions, no PII/secret.
- [ ] Run `rtk uv run pytest tests/e2e/llm/test_required_uis.py -q -k agent_chat_all_three --live-gke --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --route-manifest evidence/04_2_llm_design/gateway/topic29_routes.json`.
  - Expected: Topic 29's own three routed chat screenshots demonstrate retrieval, drift, and coordinator while consuming Topic 26 registry/KEDA/chat-smoke machine records and Topic 27 route evidence; `Sheet3!E44` machine gate passes without creating a duplicate screenshot owner.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --route-manifest evidence/04_2_llm_design/gateway/topic29_routes.json --capture-agent-chats retrieval,drift,coordinator --viewport 1600x1000 --outputs evidence/04_2_llm_design/screenshots/kagent_retrieval_chat.png,evidence/04_2_llm_design/screenshots/kagent_drift_chat.png,evidence/04_2_llm_design/screenshots/kagent_coordinator_chat.png --manifest evidence/04_2_llm_design/screenshots/ui_manifest.json --registry-evidence evidence/04_2_llm_design/agents/registry.json --chat-machine-evidence evidence/04_2_llm_design/agents/chat_smoke.json --https-machine-evidence evidence/04_2_llm_design/gateway/https_rate_limit.json --notebook-root evidence/04_2_llm_design/notebooks --strict`.
  - Expected: three contextual images show named agent/version, request, tool/routing result, grounded non-PII output, and linked notebook/registry machine evidence.

### Task 4: Run test-quality gates and render evidence

- [ ] Run `rtk uv run python scripts/qa/verify_edai2_test_scope.py --base $env:EDAI2_BASE_REF --head $env:EDAI2_COMMIT_SHA --config configs/llm/test_scope.yaml --output evidence/04_2_llm_design/tests/test_scope.json --strict`.
  - Expected: exact changed production Python files and denominator hashes are machine-recorded; generated/vendor/test files cannot enter the scope.
- [ ] Run `rtk uv run python scripts/qa/verify_edai2_test_scope.py --scope evidence/04_2_llm_design/tests/test_scope.json --run-coverage --pytest-targets tests/unit/llm,tests/contract/llm,tests/integration/llm --coverage-config configs/llm/coverage.ini --coverage-output evidence/04_2_llm_design/tests/coverage.json --fail-under 91`.
  - Expected: the verified changed-production scope exceeds 90%; the JSON report is nonempty and records fixtures/mocks/API tests.
- [ ] Run `rtk uv run pytest tests/unit/llm tests/contract/llm -q -k "boundary or partition or bva or effective_date" --json-report --json-report-file=evidence/04_2_llm_design/tests/ep_bva.json`.
  - Expected: parametrized boundary partitions cover required input/status/date/PSI cases and the nonempty report records every selected test.
- [ ] Run `rtk uv run python scripts/qa/verify_edai2_test_scope.py --scope evidence/04_2_llm_design/tests/test_scope.json --run-mutation --mutation-output evidence/04_2_llm_design/tests/mutation.json --min-exclusive 0.80 --fail-on-unknown-status`.
  - Expected: mutmut runs only the verified changed-code scope; `killed/(killed+survived+timeout+suspicious+untested)` is strictly greater than `0.80` (so `0.805` passes), and the report records every status count, denominator, exact score, commands, and scope hashes. A zero denominator or unknown status fails closed.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --collect-property-crosshair --hypothesis-target tests/property/llm/test_idempotency.py --crosshair-targets src/vina_bim_shop/llm/contracts.py,src/vina_bim_shop/llm/indexing.py --per-condition-timeout 10 --per-path-timeout 3 --output evidence/04_2_llm_design/tests/properties_crosshair.json --strict`.
  - Expected: Hypothesis examples/seed and bounded CrossHair status/counterexamples are explicitly generated in one nonempty JSON artifact; any timeout is recorded, never inferred as a pass.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --capture-test-evidence --viewport 1600x1000 --strict --root evidence/04_2_llm_design`.
  - Expected: `coverage_and_api_fixtures.png`, `ep_bva.png`, `mutation.png`, and `properties_crosshair.png` are contextual executed-result captures.

### Task 5: Run Locust and capture report

- [ ] Run `rtk uv run locust -f tests/load/llm/locustfile.py --headless -u 1 -r 1 -t 2m --route-manifest evidence/04_2_llm_design/gateway/topic29_routes.json --route-key retrieval --html evidence/04_2_llm_design/load/locust.html --csv evidence/04_2_llm_design/load/locust`.
  - Expected: nonempty HTML/CSV, zero unexpected failures, measured throughput, retrieval p95 <=750ms, sanitized resolved host.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --capture locust-report --viewport 1600x1000 --output evidence/04_2_llm_design/screenshots/locust_report.png --manifest evidence/04_2_llm_design/screenshots/ui_manifest.json --machine-evidence evidence/04_2_llm_design/load/locust_stats.csv --strict`.
  - Expected: contextual Locust results table/time/load/p95 visible.

### Task 6: Prove the two novel ideas

- [ ] Run `rtk uv run pytest tests/unit/llm/test_indexing.py -q -k effective_date`.
  - Expected: local immediately-before/at/after boundary tests pass but do not alone satisfy `Sheet3!E61`.
- [ ] Run `rtk uv run python scripts/llm/run_evaluation.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --route-manifest evidence/04_2_llm_design/gateway/topic29_routes.json --novel-idea effective-dated-boundary --boundary-cases immediately-before,at,immediately-after --output evidence/04_2_llm_design/tests/novel_effective_date.json`.
  - Expected: live routed queries prove the three effective-date boundaries against the canonical index and hash-bind the runtime result for `Sheet3!E61`.
- [ ] Run `rtk uv run pytest tests/unit/llm/test_retrieval.py tests/unit/llm/test_safety.py -q -k "hash or unsupported or citation"`.
  - Expected: local tampered-hash/unsupported-claim rejection passes but does not alone satisfy `Sheet3!E62`.
- [ ] Run `rtk uv run python scripts/llm/run_evaluation.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --route-manifest evidence/04_2_llm_design/gateway/topic29_routes.json --novel-idea citation-integrity --cases tampered-hash,unsupported-claim --output evidence/04_2_llm_design/tests/novel_citation_integrity.json`.
  - Expected: live routed retrieval rejects both cases, records source/content hashes and safety action, and hash-binds runtime proof for `Sheet3!E62`.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --novel-ideas-report --runtime-evidence evidence/04_2_llm_design/tests/novel_effective_date.json,evidence/04_2_llm_design/tests/novel_citation_integrity.json --output evidence/04_2_llm_design/tests/novel_ideas.json --strict`.
  - Expected: commands, results, runtime artifact hashes, and explicit value beyond taught baseline.

### Task 7: QA captures and suspend

- [ ] Inspect all eight owned screenshots at original resolution.
  - Expected: exact results/selectors visible, no rejected state.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --verify-screenshot-topic 29 --expected-count 8 --manifest evidence/04_2_llm_design/screenshots/ui_manifest.json --strict`.
  - Expected: exact names/count/hashes/machine links.
- [ ] Run `rtk uv run python scripts/gke/configure_evidence_ingress.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --disable --route-manifest evidence/04_2_llm_design/gateway/topic29_routes.json --require-routes retrieval,chat --strict`.
  - Expected: both routes, certificates, and their temporary exposure are removed; no public forwarding rule remains.
- [ ] Run `rtk uv run python scripts/gke/manage_profile.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT suspended --release-session-lease --owner topic29-eval --require-evidence-manifest evidence/04_2_llm_design/evaluation/report.json`.
  - Expected: pools zero, ingress disabled, no forwarding rule.
- [ ] Run `rtk git status --short --branch`.
  - Expected: same branch/revision lineage recorded.

## Evidence and Screenshot Ownership

Topic 29 owns exactly eight screenshots: three kagent chats, four test-quality captures, and `locust_report.png`. Topic 27 solely owns `grafana_ab.png`. Topic 29 is the sole primary rubric owner for the cells listed in Metadata.

## Cleanup and Runtime Release

- Restore prior facade/registry alias after any failed A/B; retain promotion only after passing gate/read-back.
- Restore normal one primary model replica and comparison zero before suspend.
- In success and every failure path, disable the exact routes named by `gateway/topic29_routes.json` before releasing the lease; then remove load/evaluation Jobs and preserve reports/notebooks.
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
