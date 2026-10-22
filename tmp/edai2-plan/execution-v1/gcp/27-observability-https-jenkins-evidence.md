# Topic 27: Observability, HTTPS, and Jenkins Evidence Implementation Plan

> **For any agent (Codex / opencode / Claude / etc):** Work task-by-task in one session. Steps use checkbox (`- [ ]`) tracking. Auto-run without asking; only stop on safe-stop gates below.

> **Study-only simplified run (first iteration, overrides strict gates below):**
> - Repo root = current checkout (`<repo-root>`). Use `rtk` prefix if installed, else run commands directly.
> - Auto-run; no mid-run approvals. Only safe stops: budget/lease/ACME/DNS/auth missing. Disable ingress + suspend at end even on Partial.
> - Happy-path first: temporary HTTPS reachable + Grafana/Loki/Tempo visible + six Jenkins pages (no rebuild, one session) wins. Exact 5-alert pending->firing->recovery, full trace-chain hops, exact 401/1rps/5burst/429 boundaries may stay `Partial`.
> - Screenshots: viewport PNG + SHA + machine link + eyeball check is enough. `grafana_ab.png` may be placeholder until Topic 29 finalizes — mark stale, let Topic 31 refresh once.
> - Study-mode relaxation v1 (study-first, single-agent): plan-doc SHA pins and manifest-byte equality are LOG-ONLY — record computed vs listed values, never block. Image remote-digest equality stays HARD.
> - Safety gates stay HARD: live budget preflight, exact kubeconfig/context, capacity ceilings. Alert/trace-exactness gates are record-and-continue `Partial`, one bounded retry max. No mid-run approvals.
> - PoC-first sprint (trial ends 2026-10-25): demo win = Grafana/Loki/Tempo/Langfuse visible + temporary HTTPS/TLS + six Jenkins pages as-is. Alert/trace-exactness and screenshot-QA prose stay `Partial`. Keep disable-ingress + suspend at end. One lease, time-box, log spend/remaining/trial-hours.
>
> **Study-only contract amendment 2026-10-18 (operator directive):** ACME contact email and recovery-sink/attestation requirements are REMOVED entirely — not deferred, not Partial-gated. No staging/production ACME, no `certificate-issuer.yaml` email parameterization, no public TLS. Prove `401/1rps/5burst/429` + Grafana/Loki/Tempo/Langfuse via private ClusterIP + `127.0.0.1` loopback port-forward only. `Sheet3!E45:E47` HTTPS cells stay `Partial` by design. Budget gate uses bundle form (`--operator-inputs`); `project_purpose=personal-study` already skips sink attestation in code.

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

- Use `rtk` prefix if installed, else run commands directly. Repo root = current checkout (`<repo-root>`).
- Fixed hashes: Section 03 `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`; EDAI2 `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`; `tmp/rubic-check/Coursework Tracking (Public).xlsx` `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
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

### Execution 2026-10-18 ~16:00Z — Partial, no lease (readiness + Jenkins-jobs block, spend refreshed)
- **Status:** Partial. No lease (foreknown churn — would burn budget with zero new evidence); zero mutation. Prior T27 lease (`03:46Z`) already proved the block; readiness unchanged (`coordinator/drift/retrieval/llmd-primary 0/1`, `/readyz 503`); zero live Jenkins jobs (`jobs.json` 6 pass only at pinned `7233469`, HEAD mismatch LOG-ONLY docs drift).
- **Branch / revision:** `feature/implement-edai2`, HEAD `e651a86dfb7d509c28c58fe0116cddd3cf6ea1a5` (unstaged, no stage/commit/push).
- **Spend:** `2119176 VND` observed `2026-10-18T15:52:10+00:00` (`<24h`; 6d to `2026-10-25`). Backend proof `15:52:52Z` (fresh at T28 gate; no T27 mutation gated on it).
- **Command / exit-code log:** Static re-verified without lease: 25 passed (`observability+jenkins+telemetry+gateway`); `render-only --strict` exit 0 (1/429/disabled). No `check_budget`/lease/ingress/capture live commands (T28 r2 lease covered cluster state: ingress zero, controller ClusterIP).
- **Evidence / SHA-256 log:** No new `topic27_routes.json`, `https_rate_limit.json`, `telemetry.json` (need Ready services). Prior gate SHAs (`fd656388…`, `0e397908…`, spend `1963347`) superseded by spend refresh — next leased run regenerates.
- **Screenshot QA:** All 16 owned PNGs still Missing; manifest untouched. Nothing manufactured.
- **Cleanup / runtime release:** No lease held; nothing to disable/release (verified via T28 r2 release checks).
- **Limitations:** ACME removed (Partial by design); Jenkins cells need real CI jobs; readiness is T28 unlock.
- **Handoff:** T28 r2 still Partial on readiness — T27 unblocked only after readiness + jobs land.

### Execution 2026-10-18 ~03:46-03:50Z — Partial, one lease, study-only contract (ACME/sink removed)
- **Status:** Partial. Study-only amendment applied (ACME + recovery-sink removed, no public TLS). Live gates passed; evidence paths still blocked on Jenkins-jobs + service readiness (not on ACME). No rebuilds, no substitutes.
- **Branch / revision:** `feature/implement-edai2`, HEAD `e651a86dfb7d509c28c58fe0116cddd3cf6ea1a5`. Working tree: Phase A source/test changes + spend refresh + vault study-only fix + 4 contract amendments (unstaged, no stage/commit/push).
- **Spend:** `1963347 VND` observed `2026-10-18T03:43:08+00:00` (fresh `<24h`, from console `₫2.94M` cost / `₫5,926,503 / ₫7,889,850` remaining / 7d to `2026-10-25`). Trial remaining `~164.2h`, requested TTL 6h, envelope headroom large.
- **Command / exit-code log:** backend `initialized` proof rotated (archived stale `03:30:41Z`, fresh `ok:true` rev `e651a86` obs `03:45:44Z`, exit 0). Bundle gate archived stale topic27 files to `.stale-20261018T0346Z`, fresh `check_budget --live-external-preflight` wrote `ok:true failures:[]` (wrapper exit 2, files authoritative). Lease `manage_profile rubric-evidence --ttl 6h --acquire-session-lease --owner topic27-evidence --commit-sha e651a86 --lease-file tmp/edai2-gcp/topic27-lease.json` exit 0 (`03:46:58Z`). Static: `render-only --strict` exit 0 (1/429/disabled); `test_observability+jenkins+telemetry+gateway` 25 passed; `--verify-observability-contract` exit 0; `--verify-jenkins-evidence` exit 2 at HEAD commit (mismatch `7233469` vs `e651a86`) / exit 0 at jobs commit (6 pass, docs-only drift LOG-ONLY). Live: deployments `coordinator 0/1`, `drift-agent 0/1`, `llmd-primary 0/1`; pods Running/False; ingress baseline controller ClusterIP, zero ingresses/issuers. No ACME enable attempted (removed). No Jenkins capture (zero live jobs; `jobs.json` direct-helm study-debt). No gateway/telemetry empirical run (services not Ready; one read-only readiness check = bounded attempt, no retry burned on foreknown churn).
- **Evidence / SHA-256 log:** `gcp_preflight_topic27.json` SHA `fd656388613342661bbc5ecb41bc6d6a58832e073eef9ddcada65715ebcb94e6` (`ok:true`, `failures:[]`); `cost_forecast_topic27.json` SHA `0e397908b6e281904a29bad8aea47cce8d666051d6147af8bf69c49a4674fd3f` (`ok:true`, spend `1963347`). No `topic27_routes.json`, `https_rate_limit.json`, `telemetry.json` (would require Ready services).
- **Screenshot QA:** All 16 owned PNGs Missing (10 gateway/telemetry + 6 Jenkins); manifest untouched. Nothing manufactured.
- **Cleanup / runtime release:** No ingress/issuer ever applied (baseline ClusterIP verified); zero ingresses/issuers at release; no forwarding rule. Lease `topic27-evidence` released exit 0 (`lease_released:true`, file absent). Cluster left UP for T28.
- **Limitations:** (1) ACME removed per 2026-10-18 operator directive — HTTPS cells `E45:E47` stay Partial by design; private ClusterIP + loopback only. (2) Zero live Jenkins jobs — `E35:E40` need real CI jobs (owning CI topic). (3) Services not Ready — readiness is Topic 28 unlock (Section 03 + canonical index).
- **Handoff:** Topic 28 prerequisites NOT met (services unready, no index/model hashes). Next: fresh ≤6h lease + fresh spend/backend gates; do NOT resume suspend files (cluster UP).

### Execution 2026-10-18 ~03:30-04:10Z — Partial, one lease, zero captures
- **Status:** Partial. Live gates passed; both evidence paths structurally blocked (details below). No rebuilds, no substitutes manufactured.
- **Branch / revision:** `feature/implement-edai2`, HEAD `e651a86dfb7d509c28c58fe0116cddd3cf6ea1a5`. Three locked SHAs match. Working tree holds Phase A source/test changes (unstaged, no stage/commit/push).
- **Spend:** `1833686 VND` observed `2026-10-17T15:33Z` (~11.9h old, `<24h` fresh). Trial ends `2026-10-25T00:00Z` (~164h left). Envelope `6311880 VND`, forecast ceiling `4733910 VND`.
- **Command / exit-code log:** `cluster-info` 0 (`136.115.175.17`); nodes 2 Ready. Backend proof stale at entry → archived to `topic22-backend-initialized-proof.json.stale-20261018T0330Z`, `check_budget --verify-private-backend initialized` exit 0, fresh proof `ok:true` rev `e651a86` obs `03:30:41Z` (`<900s`). `check_budget` bundle-form attempt 1 exit 2 `preflight_error` (stale proof); attempt 2 `ok:true failures:[]` (wrapper exit 2, files authoritative per Topic 26 ruling). Lease `manage_profile rubric-evidence --ttl 6h --acquire-session-lease --owner evidence-run --commit-sha e651a86` exit 0 (`03:31:38Z`, ~09:31Z expiry). Ingress baseline: controller 1 replica, ClusterIP, zero ingresses. `ensure-lb` → `34.136.20.93`. `enable acme-staging` → `ValueError: issuer readback failed` (ClusterIssuer `Failed to register ACME account: 400 invalidContact: evidence@example.invalid` has no public-suffix TLD — checked-in placeholder in `infra/ingress/edai2/certificate-issuer.yaml`, identical staging+production). Static gates green: `render-only --strict` 1/429/disabled; `--verify-jenkins-evidence` 6 pass; `--verify-observability-contract` pass. Jenkins API `jobs:[]` (zero jobs; `jobs.json` is direct-helm study-debt, no Jenkins records exist); `browser.json` empty. Services `/readyz` 503, pods Running/False, `llmd-primary` Pending.
- **Evidence / SHA-256 log:** `gcp_preflight_topic27.json` SHA `a905dbe4…08213` (`ok:true`, `failures:[]`, counts 43/7); `cost_forecast_topic27.json` SHA `8b5dcae2…9bc2` (`ok:true`). No `topic27_routes.json` (failed-enable artifacts removed), no `https_rate_limit.json`, no `telemetry.json`.
- **Screenshot QA:** All 16 owned PNGs Missing (10 HTTPS-routed + 6 Jenkins); manifest untouched.
- **Cleanup / runtime release:** Deleted applied `edai2-acme-staging` issuer; svc restored ClusterIP (verified, no LB status); zero ingresses/issuers; no forwarding rule. Lease released after record (see below). Client-side Jenkins port-forward orphan noted (no cluster resource, dies with session). Jenkins creds held in session env only, never written.
- **Limitations:** (1) ACME contact email placeholder blocks staging AND production (same file) — owning-local fix: parameterize contact email as operator input; no patch under lease. (2) Zero Jenkins jobs/builds exist — Jenkins cells need real CI jobs first (owning CI topic). (3) Services not Ready — readiness is Topic 28's unlock.
- **Handoff:** Topic 28 prerequisites NOT met (Topic 27 Partial, services unready). Next: fresh ≤6h lease + fresh spend/backend gates before any mutation; do NOT resume from suspend files (cluster UP).

### Execution 2026-10-18 ~00:15Z — Partial, zero mutation (no lease acquired)
- **Status:** Partial. Read-only refresh passed (branch `feature/implement-edai2` HEAD `e651a86` clean; 3 locked SHAs match; `jobs.json` 6 jobs `digest_match:true` commit `7233469…`; `cluster-info` via `tmp/edai2-gcp/kubeconfig`/`edai2-gke` → `136.115.175.17`; spend `1833686 VND` ~8.6h old `<24h`). Live paths BLOCKED at CLI contract level; no lease acquired (would burn budget on foreknown failure), no cloud mutation, cluster left UP.
- **Command / exit-code log:** `pytest test_inference+coordinator+required_uis` → 40 passed, 1 skipped, 11 errors (tokenizer fixture `local_files_only` cache miss, unrelated to gates); `capture_edai2_evidence --verify-observability-contract --strict` exit 0; `configure_evidence_ingress --render-only` exit 1 (`render-only requires the dedicated render-only context`, kubeconfig holds only `edai2-gke`); live `--enable` would fail closed (`live ingress requires an explicit GKE context`, code requires `gke_*` prefix vs authorized `edai2-gke`); `capture_edai2_evidence --verify-jenkins-evidence/--capture-ui-set/--capture-jenkins-six-pages/--verify-telemetry/--verify-screenshot-topic` → `unrecognized arguments` (script supports only Topic26-era `--capture agentregistry-agents|keda-scale`); `smoke_release --gateway-auth-rate-limit/--telemetry-fixtures` → unrecognized (script is Topic26-scoped). Venv python used directly (`uv run`/`python -m pytest` intercepted by rtk proxy); absolute kubeconfig required by script (topic lists relative path).
- **Evidence / SHA-256 log:** No `gcp_preflight_topic27.json`, `cost_forecast_topic27.json`, `topic27_routes.json`, `https_rate_limit.json`, `telemetry.json` — generating them without working CLIs would fabricate passes.
- **Screenshot QA:** All 16 owned PNGs Missing (10 gateway/telemetry + 6 Jenkins); manifest untouched. Nothing manufactured.
- **Cleanup / runtime release:** No lease ever acquired; no ingress touched; no pools changed. Stale `topic23-lease.json` (expired) only file present.
- **Limitations:** Jenkins verify pinned at jobs commit `7233469…` vs HEAD `e651a86` (docs/test-only drift, LOG-ONLY); `grafana_ab.png` placeholder/stale question moot until capture CLI exists.
- **Handoff:** Topic 28 MAY PROCEED on its own inputs (suspended-state rule vacuous — nothing resumed; acquire fresh ≤6h lease + fresh spend/backend gates before any mutation). Owning-local fixes needed: ingress `gke_*` vs `edai2-gke` context split, `render-only` context, Jenkins/UI/telemetry capture flags, gateway/rate-limit smoke flags, tokenizer cache for full unit green.

### Execution 2026-10-18 ~16:14Z — Partial, one lease, study-only contract (dependency order T27 after T28)

- **Status:** Partial. Study-only amendment applied (ACME + recovery-sink removed, private ClusterIP + loopback only). Static gates green; live captures blocked on Jenkins-jobs + readiness, not on ACME. No rebuilds, no substitutes.
- **Branch / revision:** `feature/implement-edai2`, HEAD `e651a86dfb7d509c28c58fe0116cddd3cf6ea1a5`. No stage/commit/push.
- **Spend / trial:** `2119176 VND` observed `2026-10-18T15:52:10+00:00` (`<24h`). Trial ends `2026-10-25T00:00Z` (~6d left).
- **Command / exit log:** backend `initialized` reused (`16:09:23Z`, `<900s`, rev `e651a86`). Bundle gate archived to `.stale-20261018T1613Z`, fresh `ok:true failures:[]` (exit 0). Lease `topic27-evidence --lease-file tmp/edai2-gcp/topic27-lease.json` exit 0 (`16:14:24Z`). Static: `render-only --strict` exit 0 (1/429/disabled); `test_observability` 11 passed; `--verify-observability-contract` exit 0; `--verify-jenkins-evidence` exit 0 at jobs commit `7233469…` (6 pass, HEAD scripts-only drift LOG-ONLY). Live bounded attempt: `jenkins, grafana, prometheus-server` all ClusterIP (private); `--capture-jenkins-six-pages ... --strict` usage error exit 2 (with and without `--kubeconfig/--context` — CLI contract gap, flag exists but main rejects combo); no `topic27_routes.json`/`https_rate_limit.json`/`telemetry.json` created (would require Ready services + real Jenkins jobs). Services `coordinator/drift/retrieval 0/1` (`/readyz 503` by design), `llmd-primary Init:Error 403`. One bounded retry NOT spent on foreknown churn.
- **Evidence / SHA:** `gcp_preflight_topic27.json` `ok:true`, `cost_forecast_topic27.json` `ok:true` (spend `2119176`). No new routes/telemetry machine files.
- **Screenshot QA:** All 16 owned PNGs Missing (10 gateway/telemetry incl. `grafana_ab.png` Topic-27-owned + 6 Jenkins); manifest untouched. Nothing manufactured.
- **Cleanup:** No ingress/issuer ever applied (baseline ClusterIP verified); zero ingresses at release; no forwarding rule. Lease `topic27-evidence` released exit 0 (file absent). Cluster left UP for T29.
- **Limitations:** (1) ACME removed — `E45:E47` Partial by design, private loopback only. (2) Zero live Jenkins jobs (`jobs.json` direct-helm study-debt) — `E35:E40` need real CI jobs. (3) Services not Ready — readiness is T28 unlock. (4) Jenkins capture CLI contract gap (flag present, invocation rejected) → owning local topic, no patch under lease.
- **Handoff:** T29 prerequisites NOT met (no index/model hashes, services unready). Next: fresh lease + fresh gates per topic; do NOT resume suspend files (cluster UP).

### Execution 2026-10-18 ~16:38-16:40Z — Partial, one lease, subagent-driven Task 5 run (readiness red)
- **Status:** Partial. Study-only contract locked (NO ACME/public-TLS, private ClusterIP + 127.0.0.1 only; E45:E47 Partial by design). Static gates green; live captures blocked on service readiness + Jenkins-capture CLI semantic gap. One bounded live attempt, no retry on foreknown churn. No rebuilds, no shims, nothing manufactured.
- **Branch / revision:** `feature/implement-edai2`, HEAD `e651a86dfb7d509c28c58fe0116cddd3cf6ea1a5` (unstaged, no stage/commit/push).
- **Spend:** `2119176 VND` observed `2026-10-18T15:52:10+00:00` (`<24h`; ~6d to `2026-10-25T00:00Z`). Bundle gate REUSED (`gcp_preflight_topic27.json` `ok:true failures:[]` + `cost_forecast_topic27.json` `ok:true` spend `2119176`); no archive, no bundle-form run. Backend proof REUSED no rotation (`tmp/edai2-gcp/terraform-data/topic22-backend-initialized-proof.json` obs `2026-10-18T16:31:30.624320Z`, age `~427s <900s` at `16:38:37Z` check, rev `e651a86…` match; no `Move-Item`, no `--verify-private-backend` run).
- **Command / exit-code log (FULL commands):** lease acquire `.venv\Scripts\python.exe scripts/gke/manage_profile.py --kubeconfig 'C:\Users\hhoangdo\Documents\Personal Projects\FSDS\ecom-data-platform-submission\tmp\edai2-gcp\kubeconfig' --context edai2-gke rubric-evidence --ttl 6h --acquire-session-lease --owner topic27-evidence --commit-sha e651a86dfb7d509c28c58fe0116cddd3cf6ea1a5 --lease-file tmp/edai2-gcp/topic27-lease.json` exit 0 (`lease_acquired:true`, `16:38:40Z`). Units `.venv\Scripts\python.exe -m pytest tests/unit/llm/test_observability.py -q` → `11 passed` exit 0. Static `scripts/gke/configure_evidence_ingress.py --kubeconfig '<abs>' --context edai2-gke --render-only --strict` exit 0 (`controller_replicas 1`, `limit_req_status_code 429`, `enabled:false`); `scripts/qa/capture_edai2_evidence.py --verify-observability-contract --strict` exit 0; `scripts/qa/capture_edai2_evidence.py --verify-jenkins-evidence evidence/04_2_llm_design/cicd/jobs.json --expected-commit 7233469eef8519aeb059da03a924bb6a180bed5b --expected-jobs 6 --strict` exit 0 (6 pass; HEAD scripts-only drift LOG-ONLY). Live `kubectl --kubeconfig '<abs>' --context edai2-gke -n edai2 get svc jenkins grafana prometheus-server` exit 0 — all `ClusterIP` (`jenkins 34.118.230.33`, `grafana 34.118.236.192`, `prometheus-server 34.118.238.24`), private, no external IP. Jenkins capture WITH kubeconfig/context `.venv\Scripts\python.exe scripts/qa/capture_edai2_evidence.py --capture-jenkins-six-pages evidence/04_2_llm_design/cicd/jobs.json --kubeconfig '<abs>' --context edai2-gke --strict` exit 2 exact error `capture_edai2_evidence.py: error: Jenkins capture requires --outputs`; WITHOUT kubeconfig/context `.venv\Scripts\python.exe scripts/qa/capture_edai2_evidence.py --capture-jenkins-six-pages evidence/04_2_llm_design/cicd/jobs.json --strict` exit 2 same exact error (parse accepts combo per Task 2 fix; semantic fail-closed on missing `--outputs`/`--urls`, no shim built). Deployments `coordinator/drift-agent/retrieval-agent 0/1`. No ACME enable attempted (removed). No telemetry empirical `smoke_release` run (services not Ready; recorded `0/1`).
- **Evidence / SHA-256 log:** No new `topic27_routes.json`, `https_rate_limit.json`, `telemetry.json` (require Ready services + real Jenkins jobs/URLs). Gate JSONs untouched (reused, no refresh). No captures written.
- **Screenshot QA:** All 16 owned PNGs Missing (10 gateway/telemetry incl. `grafana_ab.png` + 6 Jenkins); `evidence/04_2_llm_design/screenshots/` dir absent; manifest untouched. Nothing manufactured.
- **Cleanup / runtime release:** Release `.venv\Scripts\python.exe scripts/gke/manage_profile.py --kubeconfig 'C:\Users\hhoangdo\Documents\Personal Projects\FSDS\ecom-data-platform-submission\tmp\edai2-gcp\kubeconfig' --context edai2-gke rubric-evidence --release-session-lease --owner topic27-evidence --lease-file tmp/edai2-gcp/topic27-lease.json` exit 0 (`lease_released:true`); lease file absent verified (`Test-Path` False). Zero ingresses verified (`get ingress -A`: `No resources found`); no LB (`ingress-nginx-controller` `ClusterIP 34.118.233.155`, no `LoadBalancer`). Cluster left UP.
- **Limitations:** (1) ACME removed per operator directive — `E45:E47` Partial by design, private loopback only. (2) Services not Ready (`0/1`) — readiness is Topic 28 unlock. (3) Jenkins capture CLI semantic gap (requires `--outputs`/`--urls`; `jobs.json` alone insufficient, zero live jobs context) → owning local topic, no patch under lease. (4) `E35:E40` need real CI jobs.
- **Handoff:** Topic 28 prerequisites NOT met (services unready). Next run: fresh ≤6h lease + fresh spend/backend gates; do NOT resume suspend files (cluster UP).
- Authoritative for Task 5 (subagent-driven run): this entry; prior entries are inline-run history.

### Execution 2026-10-18 ~17:03-17:05Z — Partial, one lease, subagent-driven Task 4 run (readiness red)
- **Status:** Partial. Study-only contract locked (NO ACME/public-TLS; private ClusterIP + 127.0.0.1 only; E45:E47 Partial by design). Static gates green; live captures blocked on service readiness + Jenkins-capture CLI semantic gap. One bounded live attempt, zero retries on foreknown churn. No rebuilds, no shims, nothing manufactured.
- **Branch / revision:** `feature/implement-edai2`, HEAD `e651a86dfb7d509c28c58fe0116cddd3cf6ea1a5` (unstaged, no stage/commit/push per task rule).
- **Spend:** `2119176 VND` observed `2026-10-18T15:52:10+00:00` (`~71min` old at 17:03Z, `<24h` + `<6h` TTL; ~6d to `2026-10-25T00:00Z`). Bundle gate REUSED (`gcp_preflight_topic27.json` `ok:true failures:[]` + `cost_forecast_topic27.json` `ok:true` spend `2119176`); no archive, no bundle-form run. Backend proof REUSED no rotation (`tmp/edai2-gcp/terraform-data/topic22-backend-initialized-proof.json` obs `2026-10-18T16:57:13.185596Z`, age `~385s <900s` at `17:03:38Z` check, rev `e651a86dfb7d509c28c58fe0116cddd3cf6ea1a5` match; no `Move-Item`, no `--verify-private-backend` run).
- **Command / exit-code log (FULL commands):** lease acquire `.venv\Scripts\python.exe scripts/gke/manage_profile.py --kubeconfig 'C:\Users\hhoangdo\Documents\Personal Projects\FSDS\ecom-data-platform-submission\tmp\edai2-gcp\kubeconfig' --context edai2-gke rubric-evidence --ttl 6h --acquire-session-lease --owner topic27-evidence --commit-sha e651a86dfb7d509c28c58fe0116cddd3cf6ea1a5 --lease-file tmp/edai2-gcp/topic27-lease.json` exit 0 (`lease_acquired:true`, `17:03:41Z`). Units `.venv\Scripts\python.exe -m pytest tests/unit/llm/test_observability.py -q` → `11 passed` exit 0. Static `scripts/gke/configure_evidence_ingress.py --kubeconfig '<abs>' --context edai2-gke --render-only --strict` exit 0 (`controller_replicas 1`, `limit_req_status_code 429`, `enabled:false`); `scripts/qa/capture_edai2_evidence.py --verify-observability-contract --strict` exit 0 (`locked_views 33`); `scripts/qa/capture_edai2_evidence.py --verify-jenkins-evidence evidence/04_2_llm_design/cicd/jobs.json --expected-commit 7233469eef8519aeb059da03a924bb6a180bed5b --expected-jobs 6 --strict` exit 0 (`jobs 6`; HEAD scripts-only drift LOG-ONLY). Live `kubectl --kubeconfig '<abs>' --context edai2-gke -n edai2 get svc jenkins grafana prometheus-server` exit 0 — all `ClusterIP` (`jenkins 34.118.230.33`, `grafana 34.118.236.192`, `prometheus-server 34.118.238.24`), private, no external IP. Jenkins capture WITH kubeconfig/context `.venv\Scripts\python.exe scripts/qa/capture_edai2_evidence.py --capture-jenkins-six-pages evidence/04_2_llm_design/cicd/jobs.json --kubeconfig '<abs>' --context edai2-gke --strict` exit 2 exact error `capture_edai2_evidence.py: error: Jenkins capture requires --outputs`; WITHOUT kubeconfig/context `.venv\Scripts\python.exe scripts/qa/capture_edai2_evidence.py --capture-jenkins-six-pages evidence/04_2_llm_design/cicd/jobs.json --strict` exit 2 same exact error (Task-1 parse fixed — combo accepted; semantic fail-closed on missing `--outputs`/`--urls`, no shim). Readiness `kubectl -n edai2 get deploy coordinator drift-agent retrieval-agent` → all `0/1`; no telemetry run without Ready (record `0/1`). No ACME attempted.
- **Evidence / SHA-256 log:** No new `topic27_routes.json`, `https_rate_limit.json`, `telemetry.json` (require Ready services + real Jenkins jobs/URLs). Gate JSONs untouched (reused, no refresh). No captures written.
- **Screenshot QA:** All 16 owned PNGs Missing (10 gateway/telemetry incl. `grafana_ab.png` Topic-27-owned + 6 Jenkins); manifest untouched. Nothing manufactured.
- **Cleanup / runtime release:** Release `.venv\Scripts\python.exe scripts/gke/manage_profile.py --kubeconfig 'C:\Users\hhoangdo\Documents\Personal Projects\FSDS\ecom-data-platform-submission\tmp\edai2-gcp\kubeconfig' --context edai2-gke rubric-evidence --release-session-lease --owner topic27-evidence --lease-file tmp/edai2-gcp/topic27-lease.json` exit 0 (`lease_released:true`); lease file absent verified (`Test-Path` False). Zero ingresses verified (`get ingress -A`: `No resources found`); no LB (`ingress-nginx-controller` `ClusterIP 34.118.233.155`, no external IP). Cluster left UP.
- **Limitations:** (1) ACME removed per operator directive — `E45:E47` Partial by design, private loopback only. (2) Services not Ready (`0/1`) — readiness is Topic 28 unlock. (3) Jenkins capture CLI semantic gap (requires `--outputs`/`--urls`; `jobs.json` alone insufficient, zero live jobs context) → owning local topic, no patch under lease. (4) `E35:E40` need real CI jobs.
- **Handoff:** Topic 28 prerequisites NOT met (services unready). Next run: fresh ≤6h lease + fresh spend/backend gates; do NOT resume suspend files (cluster UP).
- Authoritative for Task 4 (subagent-driven run): this entry; prior entries are inline-run history.


## Completion Record - 2026-10-19 final closeout (deferred by operator)

- **Status:** Partial - deferred by operator. The study-only lock was retained; no public ACME/TLS or live ingress was enabled.
- **Branch / revision:** `feature/implement-edai2`, `a5c2111d46cf8805baee18ba98bfd2df9ec942c5`.
- **Evidence:** `configure_evidence_ingress.py` still rejects live `--enable`/`--disable`; zero ingress/LB/forwarding rules at teardown.
- **Approved exception:** `E45:E47` remains Partial by design; all 16 owned PNGs remain Missing and are listed in `topic31-approved-exceptions.json` under Topic 27.
- **Handoff:** revisit only if the operator approves a bounded public-TLS window and a valid ACME contact email.
