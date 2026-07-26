# Topic 27: Observability, HTTPS, and Jenkins Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove required telemetry, end-to-end trace continuity, temporary HTTPS/auth/rate limiting, and six existing Jenkins delivery records through contextual, fail-closed UI evidence.

**Architecture:** The handed-off `evidence-run` lease temporarily enables a one-replica ingress-nginx controller and production ACME routes. Grafana, Loki, Tempo, and Langfuse consume already-instrumented traffic. One Playwright browser session visits six distinct Jenkins job/build-stage pages bound to Topic 25 machine records without rebuilding.

**Tech Stack:** Prometheus, Grafana, Loki, Tempo, Grafana Alloy, Langfuse/ClickHouse, OpenTelemetry, ingress-nginx, cert-manager, `sslip.io`, Jenkins, Playwright.

## Metadata

| Field | Decision |
|---|---|
| Phase | Gateway/telemetry/CI UI evidence; topic 27 |
| Authoritative source tasks | `04.2_llm_design.md` Tasks 10-11 |
| Primary rubric cells | `Sheet3!E35:E43`, `Sheet3!E45:E47`, `Sheet3!E50:E55` |
| Prerequisites | Topics 25-26 successful; six job records; restored agent state; valid `evidence-run` lease |
| Blocked successors | Topic 28 starts only after Topic 27 suspends/releases |
| Runtime owner | Reused `evidence-run`, total lease <=6h |
| Execution class | `GCP-write/public-evidence` |
| Branch rule | Same branch/common CI commit; serial |

## Global Constraints

- Read `C:\Users\oou1hc\.codex\RTK.md`; prefix every shell command with `rtk`.
- Fixed hashes: Section 03 `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`; EDAI2 `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`; `tmp/rubic-check/Coursework Tracking (Public).xlsx` `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- No branch/worktree/stage/commit changes.
- Consume the completed local implementation. If a source/IaC/chart defect appears, capture it, release or suspend any owned runtime, mark this topic `Partial`, and return it to the owning local topic; do not patch implementation during a live cloud lease.
- Require exact kube context, a fresh redacted `check_budget.py --live-external-preflight`, valid lease, project lifecycle, billing linkage, exact IAM permissions, trial/spend/notification/recovery-sink status, DNS egress, ACME capability, Vault-projected UI auth, and Jenkins machine records. Missing inputs cause safe stop.
- Require `EDAI2_GKE_KUBECONFIG=tmp/edai2-gcp/kubeconfig` and `EDAI2_GKE_CONTEXT=gke_${GOOGLE_CLOUD_PROJECT}_us-central1-a_edai2`. Every `kubectl` call includes `--kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT`; every Helm call includes `--kubeconfig $env:EDAI2_GKE_KUBECONFIG --kube-context $env:EDAI2_GKE_CONTEXT`; every script that queries or mutates Kubernetes receives both values. Never use or change the default kubeconfig/current context.
- `EDAI2_TFVARS_PATH` is absolute, resolves exactly to this repository's `tmp/edai2-gcp/coursework.auto.tfvars`, and remains untracked.
- Public ingress exists only during bounded evidence capture. Controller replicas exactly one; global `limit-req-status-code=429`; chat annotations exactly `limit-rps: "1"` and `limit-burst-multiplier: "5"`.
- Do not expose llm-d, internal MCP/A2A routes, secrets, PII, or raw customer/message labels.
- Application logs use `log_scope=application`; system/controller logs use `log_scope=system`; dashboards never merge them.
- The five alert thresholds are exact: API/tool failure rate >5%, retrieval p95 >750 ms, active-index freshness >24 h, memory utilization >90%, and disk utilization >80%. Each fixture must prove pending then firing and recovery with timestamps.
- Trace continuity must span ingress/chat -> facade -> agentgateway -> coordinator -> specialist -> MCP -> API -> Feast/PostgreSQL and the model branch to llm-d. A new root at any hop fails `Sheet3!E53`.
- Six Jenkins pages are captured in one browser session from existing build URLs/IDs. Do not trigger, rebuild, replay, or mutate a job.
- One bounded capture retry after fixing the named cause; repeated failure remains truthful partial.
- `Sheet3!E49` is out of scope.
- Every owned UI screenshot is `1600x1000`, viewport/non-element-cropped, stable selectors fully visible, temp PNG/signature/decode/full-load/atomic replacement, manifest URL/UTC/revision/selectors/dimensions/SHA/machine link/proves/does-not, original-resolution inspection. Reject blank/clipped/loading/login/home/error/stale/secret/PII.

## Read-Only Planning Refresh

1. `rtk git status --short --branch`
   - Expected: same branch/common commit.
2. `rtk python -c "import hashlib; p=['tmp/edai2-plan/03_data_generator_improvement.md','tmp/edai2-plan/04.2_llm_design.md','tmp/rubic-check/Coursework Tracking (Public).xlsx']; print([hashlib.sha256(open(x,'rb').read()).hexdigest() for x in p])"`
   - Expected: fixed hashes.
3. `rtk rg -n "Status|Screenshot QA|evidence-run|Handoff" tmp/edai2-plan/execution-v1/gcp/26-keda-agent-ha-registry-rollbacks.md`
   - Expected: current versions restored and lease valid.
4. `rtk uv run python scripts/qa/capture_edai2_evidence.py --verify-jenkins-evidence evidence/04_2_llm_design/cicd/jobs.json --expected-commit $env:EDAI2_COMMIT_SHA --expected-jobs 6 --require-buildkit-serialization --require-wave-order --strict`
   - Expected: six immutable existing records pass before opening browser.
5. `rtk kubectl --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT cluster-info`
   - Expected: the dedicated kubeconfig resolves the approved GKE API; mismatch or failure is a safe stop.

## Scope

- Validate telemetry dashboards, alerts, labels, trace propagation, and ingress render.
- Enable staging then production ACME route for final capture.
- Prove auth 401, accepted/burst boundary, and 429 beyond limit.
- Generate controlled traffic/failures and capture ten gateway/telemetry screenshots, including `grafana_ab.png` under Topic 27 ownership.
- Capture six distinct Jenkins pages in one browser session without rebuild.
- Verify capture manifest, disable ingress, release lease, and suspend.

## Non-Goals

- No final A/B decision; Topic 29 owns `Sheet3!E56:E57` machine results and Topic 31 must refresh the Topic-27-owned `grafana_ab.png` if Topic 29 makes it stale.
- No job build/deploy.
- No persistent public load balancer.

## Exact File Map

| Role | Exact paths |
|---|---|
| Read | `infra/observability/prometheus/alerts.yaml`, `infra/observability/alloy/config.alloy` |
| Read | `infra/observability/grafana/dashboards/http.json`, `infra/observability/grafana/dashboards/compute.json`, `infra/observability/grafana/dashboards/agents.json` |
| Read | `infra/observability/grafana/dashboards/llm.json`, `infra/observability/grafana/dashboards/ab.json` |
| Read | `infra/ingress/edai2/ingresses.yaml`, `infra/ingress/edai2/certificate-issuer.yaml` |
| Read | `tests/e2e/llm/test_required_uis.py` |
| Execute | `scripts/gke/configure_evidence_ingress.py`, `scripts/qa/capture_edai2_evidence.py` |
| Execute | `scripts/gke/manage_profile.py`, `scripts/gke/check_budget.py`, `scripts/llm/smoke_release.py` |
| Read external/untracked | `tmp/edai2-gcp/kubeconfig` |
| Consume | `evidence/04_2_llm_design/cicd/jobs.json`, `evidence/04_2_llm_design/agents/registry.json`, `evidence/04_2_llm_design/agents/chat_smoke.json` |
| Consume | `evidence/04_2_llm_design/gke/keda_ha.json`, `evidence/04_2_llm_design/rollbacks/helm.json`, `evidence/04_2_llm_design/rollbacks/model.json`, `evidence/04_2_llm_design/rollbacks/index.json` |
| Generate immutable gate evidence | `evidence/04_2_llm_design/gke/gcp_preflight_topic27.json`, `evidence/04_2_llm_design/gke/cost_forecast_topic27.json` |
| Update append-only | `evidence/04_2_llm_design/gke/usage_ledger.json` |
| Generate | `evidence/04_2_llm_design/gateway/topic27_routes.json` |
| Generate | `evidence/04_2_llm_design/observability/telemetry.json` |
| Generate | `evidence/04_2_llm_design/gateway/https_rate_limit.json` |
| Screenshot owner | `evidence/04_2_llm_design/screenshots/grafana_http.png`, `evidence/04_2_llm_design/screenshots/grafana_compute.png`, `evidence/04_2_llm_design/screenshots/grafana_llm.png` |
| Screenshot owner | `evidence/04_2_llm_design/screenshots/grafana_agents.png`, `evidence/04_2_llm_design/screenshots/grafana_ab.png`, `evidence/04_2_llm_design/screenshots/loki_app_logs.png` |
| Screenshot owner | `evidence/04_2_llm_design/screenshots/tempo_trace.png`, `evidence/04_2_llm_design/screenshots/langfuse_trace.png`, `evidence/04_2_llm_design/screenshots/nginx_tls.png` |
| Screenshot owner | `evidence/04_2_llm_design/screenshots/chat_auth_rate_limit.png`, `evidence/04_2_llm_design/screenshots/jenkins_rag_index.png`, `evidence/04_2_llm_design/screenshots/jenkins_retrieval_agent.png` |
| Screenshot owner | `evidence/04_2_llm_design/screenshots/jenkins_drift_agent.png`, `evidence/04_2_llm_design/screenshots/jenkins_coordinator.png`, `evidence/04_2_llm_design/screenshots/jenkins_feast_offline.png`, `evidence/04_2_llm_design/screenshots/jenkins_feast_online.png` |
| Update through capture CLI | `evidence/04_2_llm_design/screenshots/ui_manifest.json` |

## Interfaces, Data Flow, and Failure Modes

Controlled requests/failures -> OpenTelemetry/metrics/JSON logs -> Alloy -> Prometheus/Loki/Tempo/Langfuse -> contextual dashboards/traces -> machine evidence -> screenshots.

Private services -> temporary one-replica ingress -> ACME staging validation -> production certificate -> authenticated routes -> viewport captures -> ingress disable/suspend.

Topic 25 `jobs.json` -> six exact URLs/build IDs -> one authenticated browser context -> six distinct stage pages -> capture manifest. Browser navigation must not invoke Build Now/Replay/Rebuild.

Failures: selector instability, certificate challenge failure, second ingress replica, response code 503 instead of 429, merged log scopes, trace root break, missing telemetry labels, Jenkins build ID mismatch, login-only page, secret/PII. One corrected retry; otherwise preserve old valid files and mark cells `Partial` or `Missing`.

## Ordered Test-First Execution Tasks

### Task 1: Validate static telemetry and ingress contracts

- [ ] Run `rtk uv run pytest tests/unit/llm/test_inference.py tests/unit/llm/test_coordinator.py tests/e2e/llm/test_required_uis.py -q`.
  - Expected: config/unit tests pass; live UI tests skip only for absent base URLs and create no screenshot.
- [ ] Run `rtk uv run python scripts/gke/configure_evidence_ingress.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --render-only --strict`.
  - Expected: one controller replica, exact rate settings, no unrelated bandwidth annotation, required routes only.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --verify-observability-contract --strict`.
  - Expected: required HTTP/compute/LLM/agent metrics, stable labels, exact alert thresholds (API/tool failure >5%, retrieval p95 >750 ms, active-index freshness >24 h, memory >90%, disk >80%), separated log scopes, and trace hop contract pass.

### Task 2: Revalidate budget/lease and enable temporary HTTPS

- [ ] Run `rtk uv run python scripts/gke/check_budget.py --project $env:GOOGLE_CLOUD_PROJECT --billing-account-env GOOGLE_BILLING_ACCOUNT --budget-notification-target-env EDAI2_BUDGET_NOTIFICATION_TARGET --recovery-sink-env EDAI2_VAULT_RECOVERY_SINK --recovery-sink-attestation $env:EDAI2_RECOVERY_SINK_ATTESTATION --required-permissions configs/gke/required_permissions.json --dns-probes acme-staging-v02.api.letsencrypt.org,huggingface.co,storage.googleapis.com --live-external-preflight --preflight-output evidence/04_2_llm_design/gke/gcp_preflight_topic27.json --trial-expires-at $env:EDAI2_TRIAL_EXPIRES_AT --current-spend-usd $env:EDAI2_CURRENT_SPEND_USD --spend-observed-at $env:EDAI2_SPEND_OBSERVED_AT --usage-ledger evidence/04_2_llm_design/gke/usage_ledger.json --envelope configs/gke/cost_envelope.yaml --requested-profile rubric-evidence --requested-ttl 6h --output evidence/04_2_llm_design/gke/cost_forecast_topic27.json`.
  - Expected: residual lease plus live project/billing/IAM/notification/recovery-sink/DNS/trial/spend/ingress-budget gates pass with redacted output only.
- [ ] Run `rtk uv run python scripts/gke/configure_evidence_ingress.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --enable --route-set topic27-observability --routes retrieval,chat,grafana,langfuse,jenkins --sslip-from-service ingress-nginx-controller --issuer acme-staging --lease-owner evidence-run --output evidence/04_2_llm_design/gateway/topic27_routes.json --strict`.
  - Expected: staging HTTP-01 Ready on all required hosts.
- [ ] Run `rtk uv run python scripts/gke/configure_evidence_ingress.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --promote-route-manifest evidence/04_2_llm_design/gateway/topic27_routes.json --issuer acme-production --require-routes retrieval,chat,grafana,langfuse,jenkins --lease-owner evidence-run --strict`.
  - Expected: production certificates Ready; retrieval/chat/Grafana/Langfuse/Jenkins hosts resolve and exactly match the signed route manifest.
- [ ] Run `rtk uv run python scripts/llm/smoke_release.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --route-manifest evidence/04_2_llm_design/gateway/topic27_routes.json --gateway-auth-rate-limit --expected-unauthenticated 401 --accepted-rps 1 --burst 5 --expected-over-limit 429 --output evidence/04_2_llm_design/gateway/https_rate_limit.json`.
  - Expected: exact EP/BVA results and no 503.

### Task 3: Generate and verify telemetry

- [ ] Run `rtk uv run python scripts/llm/smoke_release.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --telemetry-fixtures http,compute,llm,agents,logs,traces,alerts --output evidence/04_2_llm_design/observability/telemetry.json`.
  - Expected: required metrics/labels, application/system log separation, complete branched trace, controlled five-alert transitions, no PII/secret.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --verify-telemetry evidence/04_2_llm_design/observability/telemetry.json --strict`.
  - Expected: exit 0 and timestamps fall inside active lease/retention.

### Task 4: Capture gateway and telemetry views

- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --route-manifest evidence/04_2_llm_design/gateway/topic27_routes.json --capture-ui-set gateway-observability --viewport 1600x1000 --names grafana_http,grafana_compute,grafana_llm,grafana_agents,grafana_ab,loki_app_logs,tempo_trace,langfuse_trace,nginx_tls,chat_auth_rate_limit --manifest evidence/04_2_llm_design/screenshots/ui_manifest.json --machine-root evidence/04_2_llm_design --strict`.
  - Expected: ten contextual PNGs atomically installed with host/time/revision/selectors and exact machine links. `grafana_ab.png` shows the configured assignment/arm dashboard and is recaptured by Topic 31 under producer Topic 27 if Topic 29's final run makes it stale.

### Task 5: Capture six Jenkins pages in one session without rebuilding

- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --capture-jenkins-six-pages evidence/04_2_llm_design/cicd/jobs.json --single-browser-session --no-build --viewport 1600x1000 --outputs jenkins_rag_index.png,jenkins_retrieval_agent.png,jenkins_drift_agent.png,jenkins_coordinator.png,jenkins_feast_offline.png,jenkins_feast_online.png --manifest evidence/04_2_llm_design/screenshots/ui_manifest.json --strict`.
  - Expected: one authenticated browser session, six distinct job/build-stage URLs/IDs, same commit, SUCCESS, seven ordered stages, no rebuild/replay request and no credential exposure.
- [ ] Re-run `rtk uv run python scripts/qa/capture_edai2_evidence.py --verify-jenkins-evidence evidence/04_2_llm_design/cicd/jobs.json --expected-commit $env:EDAI2_COMMIT_SHA --expected-jobs 6 --strict`.
  - Expected: job records unchanged before/after capture.

### Task 6: Original-resolution QA and durable manifest

- [ ] Inspect all 16 owned PNGs at original resolution.
  - Expected: no rejection state; selectors/context are fully legible.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --verify-screenshot-topic 27 --expected-count 16 --manifest evidence/04_2_llm_design/screenshots/ui_manifest.json --strict`.
  - Expected: exact names/count, dimensions, SHA-256, URLs, UTC, revision, selectors, machine links, proves/does-not fields.
- [ ] Run `rtk git status --short --branch`.
  - Expected: same branch/revision lineage and request-scoped changes only.

## Evidence and Screenshot Ownership

Topic 27 owns exactly 16 named screenshots: ten gateway/telemetry (including `grafana_ab.png`) and six Jenkins. Topic 29 owns the final A/B machine results, while Topic 31 may refresh the same Topic-27-owned file once if stale. Topic 31 is QA/teardown authority, not primary capture owner.

## Cleanup and Runtime Release

- [ ] Run `rtk uv run python scripts/gke/configure_evidence_ingress.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --disable --route-manifest evidence/04_2_llm_design/gateway/topic27_routes.json --require-routes retrieval,chat,grafana,langfuse,jenkins --strict`.
  - Expected: ingress routes/controller exposure disabled.
- [ ] Run `rtk uv run python scripts/gke/manage_profile.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT suspended --release-session-lease --owner evidence-run --require-evidence-manifest evidence/04_2_llm_design/screenshots/ui_manifest.json`.
  - Expected: lease absent, both pools zero, no public forwarding rule.
- Remove traffic/alert fixture Jobs; preserve telemetry within seven-day retention and evidence hashes.

## Rubric Traceability

| Cells | Points | Topic 27 primary evidence |
|---|---:|---|
| `Sheet3!E35:E40` | 12 | six machine records plus six distinct Jenkins screenshots |
| `Sheet3!E41:E43` | 6 | HTTPS-routed Grafana/Loki/Tempo contextual views |
| `Sheet3!E45:E47` | 5 | registry UI, Vault-backed auth/rate limit, temporary valid HTTPS |
| `Sheet3!E50:E55` | 8 | HTTP/compute/log/trace/LLM/agent telemetry captures |

Topic 29 solely owns `Sheet3!E44`, `Sheet3!E56`, and `Sheet3!E57`; Topic 27 owns the route/dashboard screenshots that Topic 29 consumes.

## Definition of Done

- [ ] Static telemetry/ingress contracts, budget, lease, and explicit context pass.
- [ ] Production HTTPS and exact 401/accepted/burst/429 behavior are proved.
- [ ] Required telemetry/log scopes/trace continuity and all five exact alert thresholds/transitions are machine verified.
- [ ] Ten contextual gateway/telemetry images pass QA.
- [ ] Six distinct Jenkins pages are captured in one browser session with zero rebuilds.
- [ ] All 16 images pass original-resolution and manifest checks.
- [ ] Ingress is disabled, `evidence-run` released, pools zero, forwarding rules absent.
- [ ] Final `rtk git status --short --branch` is recorded.

## Completion Record

- **Status:** Not started; no gateway/observability/Jenkins screenshot claim.
- **Branch / revision:** Record exact `rtk git status --short --branch`; none recorded.
- **Affected files:** None at plan-authoring time.
- **Command / exit-code log:** No execution commands recorded.
- **Evidence / SHA-256 log:** No gateway/telemetry evidence recorded.
- **Screenshot QA:** Sixteen owned screenshots not captured.
- **Cleanup / runtime release:** No observed lease/ingress state.
- **Limitations:** A/B dashboard awaits Topic 29; persistence/recovery awaits Topic 30.
- **Handoff:** Topic 28 requires a fully suspended profile and must acquire a fresh <=6h budgeted lease.
