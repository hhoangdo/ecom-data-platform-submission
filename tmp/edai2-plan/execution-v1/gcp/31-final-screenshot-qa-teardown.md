# Topic 31: Final Screenshot QA and Teardown Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fail-closed audit every required Section 03 and EDAI2 screenshot against its machine evidence, perform at most one bounded repair capture, generate the cross-cutting run manifest, and leave all GCP runtime suspended with no public forwarding rule.

**Architecture:** Topic 31 owns no rubric cell or primary screenshot. After the read-only audit it always acquires its own fresh <=2h QA lease; a rejected image is recaptured once using that manifest entry's original public, private-loopback, local-render, or browser-console reachability contract. The validator checks Section 03 images at `1600x900`, 32 named EDAI2 UI images plus `gcp_billing_spend.png` at `1600x1000`, original-resolution visual quality, cryptographic/manifests, provenance, machine links, and teardown.

**Tech Stack:** Python/`uv`, Playwright Chromium, PNG decoder, SHA-256, screenshot manifest validator, GKE profile manager, Google Cloud CLI.

## Metadata

| Field | Decision |
|---|---|
| Phase | Evidence lease 4 of 4; execution topic 31 |
| Authoritative source tasks | `04.2_llm_design.md` Tasks 10-12 and Evidence Contract |
| Primary rubric cells | None; cross-cutting prerequisite for every satisfied cell |
| Prerequisites | Topics 22-30 Completion Records and final suspended state |
| Blocked successors | Topic 32 |
| Runtime owner | `topic31-screenshot-qa`; always acquire a fresh lease <=2h after the read-only audit |
| Execution class | `GCP-read-mostly/conditional capture/teardown` |
| Branch rule | Same branch/common CI commit; serial |

## Global Constraints

- Read `C:\Users\oou1hc\.codex\RTK.md`; prefix shell commands with `rtk`.
- Fixed hashes: Section 03 `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`; EDAI2 `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`; `tmp/rubic-check/Coursework Tracking (Public).xlsx` `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- No branch/worktree/stage/commit changes.
- Consume the completed local implementation. If a source/IaC/chart defect appears, capture it, release or suspend any owned runtime, mark this topic `Partial`, and return it to the owning local topic; do not patch implementation during a live cloud lease.
- Begin with read-only QA, then always run a redacted `check_budget.py --live-external-preflight` and acquire a fresh <=2h lease. The gate covers project lifecycle, billing linkage, exact IAM permissions, trial expiry, spend/forecast, notification target, approved recovery sink, DNS, context, and capacity. Missing external input stops mutation and results in truthful failed/pending QA, never an invented substitute.
- Require `EDAI2_GKE_KUBECONFIG=tmp/edai2-gcp/kubeconfig` and `EDAI2_GKE_CONTEXT=gke_${GOOGLE_CLOUD_PROJECT}_us-central1-a_edai2`. Every `kubectl` call includes `--kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT`; every Helm call includes `--kubeconfig $env:EDAI2_GKE_KUBECONFIG --kube-context $env:EDAI2_GKE_CONTEXT`; every script that queries or mutates Kubernetes receives both values. Never use or change the default kubeconfig/current context.
- `EDAI2_TFVARS_PATH` is absolute, resolves exactly to this repository's `tmp/edai2-gcp/coursework.auto.tfvars`, and remains untracked.
- `EDAI2_SECTION03_BUNDLE_ID` must be copied from the verified Section 03 manifest's top-level `bundle_id`, match its screenshot `canonical_path`, and contain no separator or traversal segment.
- Topic 31 never changes primary screenshot ownership; repaired manifest entries retain original `producer_topic`.
- Section 03 screenshot dimensions are exactly `1600x900`; EDAI2/billing UI screenshots exactly `1600x1000`.
- Every screenshot is viewport/non-element-cropped with full stable selectors. Capture to a temporary PNG; verify eight-byte PNG signature, decoder `verify`, full pixel load, exact dimensions, and selector visibility before atomic replacement.
- Each manifest entry contains canonical path, dimensions, URL or source artifact, UTC capture time, commit/config/data revision, visible selectors/text, SHA-256, linked machine-evidence paths/hashes, primary producer topic, what it proves, and what it does not prove.
- Reject blank/uniform, clipped, loading/skeleton, login-only, generic home, error/stack trace, stale revision/time, secret/token/account identifier, raw PII, missing selector, missing machine link, or hash mismatch.
- Inspect every accepted PNG at original resolution. Montage/thumbnail review is supplemental only.
- One bounded recapture per rejected image after the exact cause is fixed. If it fails, retain any prior valid file, mark the image/cells `Partial` or `Missing`, and continue truthful partial QA.
- No terminal/source-only substitute where UI proof is required.
- `Sheet3!E49` remains out of scope.
- Teardown means pools zero, ingress disabled, no EDAI2 `LoadBalancer`, no tagged project forwarding rule, no lease owner/refcount, and no temporary capture pod/browser secret.

## Read-Only Planning Refresh

1. `rtk git status --short --branch`
   - Expected: same branch/common CI revision.
2. `rtk python -c "import hashlib; p=['tmp/edai2-plan/03_data_generator_improvement.md','tmp/edai2-plan/04.2_llm_design.md','tmp/rubic-check/Coursework Tracking (Public).xlsx']; print([hashlib.sha256(open(x,'rb').read()).hexdigest() for x in p])"`
   - Expected: fixed hashes.
3. `rtk rg -n "Status|Screenshot QA|Cleanup / runtime release|Handoff" tmp/edai2-plan/execution-v1/gcp/22-gcp-account-budget-terraform-apply.md tmp/edai2-plan/execution-v1/gcp/23-vault-kms-model-cache-bootstrap.md tmp/edai2-plan/execution-v1/gcp/24-compact-platform-install.md tmp/edai2-plan/execution-v1/gcp/25-jenkins-six-workload-deploy.md tmp/edai2-plan/execution-v1/gcp/26-keda-agent-ha-registry-rollbacks.md tmp/edai2-plan/execution-v1/gcp/27-observability-https-jenkins-evidence.md tmp/edai2-plan/execution-v1/gcp/28-rag-inference-benchmarks.md tmp/edai2-plan/execution-v1/gcp/29-evaluation-ab-notebooks-load-test-evidence.md tmp/edai2-plan/execution-v1/gcp/30-persistence-vault-recovery-resume.md`
   - Expected: all preceding records are present; incomplete records become known partial limitations.
4. `rtk kubectl --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT cluster-info`
   - Expected: the dedicated kubeconfig resolves the approved GKE API; mismatch or failure is a safe stop.
5. `rtk uv run python scripts/qa/capture_edai2_evidence.py --verify-section03-screenshot-contract --manifest evidence/03_data_generator_improvement/section03_manifest.json --bundle-id $env:EDAI2_SECTION03_BUNDLE_ID --expected-path evidence/03_data_generator_improvement/runs/$env:EDAI2_SECTION03_BUNDLE_ID/section03_config_and_training_join.png --strict`.
   - Expected: manifest bundle/path equality passes without wildcard discovery; invalid, missing, or path-like bundle IDs fail.
6. `rtk uv run python scripts/qa/capture_edai2_evidence.py --verify-screenshots-only --root evidence/04_2_llm_design --section03-manifest evidence/03_data_generator_improvement/section03_manifest.json --strict`.
   - Expected: read-only report identifies exact pass/fail reasons without replacing a file.

## Scope

- Audit Section 03 screenshot paths/dimensions/hashes/machine links.
- Audit exactly 32 named EDAI2 screenshots and `gcp_billing_spend.png`.
- Inspect every image at original resolution.
- Perform at most one bounded recapture for each invalid image using original ownership.
- Generate/verify `ui_manifest.json` and `run_manifest.json`.
- Disable ingress, suspend/release, and write `teardown.json`.

## Non-Goals

- No new workload build, benchmark, experiment, notebook, rubric scoring, documentation, Terraform destroy, or ownership reassignment.
- No cosmetic recapture of an already valid image.

## Exact Screenshot Inventory

| Producer | Exact names |
|---|---|
| Topic 22 | `gcp_billing_spend.png`, `terraform_apply.png` |
| Topic 23 | no screenshot; machine bootstrap evidence only |
| Topic 26 | `agentregistry_agents.png`, `keda_scale.png` |
| Topic 27 | `grafana_http.png`, `grafana_compute.png`, `grafana_llm.png`, `grafana_agents.png`, `grafana_ab.png`, `loki_app_logs.png`, `tempo_trace.png`, `langfuse_trace.png`, `nginx_tls.png`, `chat_auth_rate_limit.png`, `jenkins_rag_index.png`, `jenkins_retrieval_agent.png`, `jenkins_drift_agent.png`, `jenkins_coordinator.png`, `jenkins_feast_offline.png`, `jenkins_feast_online.png` |
| Topic 28 | `airflow_rag_graph.png`, `datahub_rag_lineage.png` |
| Topic 29 | `kagent_retrieval_chat.png`, `kagent_drift_chat.png`, `kagent_coordinator_chat.png`, `coverage_and_api_fixtures.png`, `ep_bva.png`, `mutation.png`, `properties_crosshair.png`, `locust_report.png` |
| Topic 30 | `vault_status.png` |
| Topic 32 | `design_patterns.png`, `whole_course_diagram.png` |

The table contains exactly 32 EDAI2 names plus `gcp_billing_spend.png`. Topic 32 images may be source-rendered and captured during Topic 32; before then Topic 31 records them as pending, not missing final evidence. Topic 32 must run the same validator after creating them.

## Exact File Map

| Role | Exact path |
|---|---|
| Read | `evidence/03_data_generator_improvement/section03_manifest.json` |
| Read | `evidence/03_data_generator_improvement/runs/$env:EDAI2_SECTION03_BUNDLE_ID/section03_config_and_training_join.png` |
| Read/update through capture CLI | `evidence/04_2_llm_design/screenshots/ui_manifest.json` |
| Consume | `evidence/04_2_llm_design/gke/platform_install.json` |
| Read | `evidence/04_2_llm_design/screenshots/gcp_billing_spend.png`, `evidence/04_2_llm_design/screenshots/terraform_apply.png` |
| Read | `evidence/04_2_llm_design/screenshots/agentregistry_agents.png`, `evidence/04_2_llm_design/screenshots/keda_scale.png` |
| Read | `evidence/04_2_llm_design/screenshots/grafana_http.png`, `evidence/04_2_llm_design/screenshots/grafana_compute.png`, `evidence/04_2_llm_design/screenshots/grafana_llm.png` |
| Read | `evidence/04_2_llm_design/screenshots/grafana_agents.png`, `evidence/04_2_llm_design/screenshots/grafana_ab.png`, `evidence/04_2_llm_design/screenshots/loki_app_logs.png` |
| Read | `evidence/04_2_llm_design/screenshots/tempo_trace.png`, `evidence/04_2_llm_design/screenshots/langfuse_trace.png`, `evidence/04_2_llm_design/screenshots/nginx_tls.png` |
| Read | `evidence/04_2_llm_design/screenshots/chat_auth_rate_limit.png`, `evidence/04_2_llm_design/screenshots/jenkins_rag_index.png`, `evidence/04_2_llm_design/screenshots/jenkins_retrieval_agent.png` |
| Read | `evidence/04_2_llm_design/screenshots/jenkins_drift_agent.png`, `evidence/04_2_llm_design/screenshots/jenkins_coordinator.png`, `evidence/04_2_llm_design/screenshots/jenkins_feast_offline.png`, `evidence/04_2_llm_design/screenshots/jenkins_feast_online.png` |
| Read | `evidence/04_2_llm_design/screenshots/airflow_rag_graph.png`, `evidence/04_2_llm_design/screenshots/datahub_rag_lineage.png` |
| Read | `evidence/04_2_llm_design/screenshots/kagent_retrieval_chat.png`, `evidence/04_2_llm_design/screenshots/kagent_drift_chat.png`, `evidence/04_2_llm_design/screenshots/kagent_coordinator_chat.png` |
| Read | `evidence/04_2_llm_design/screenshots/coverage_and_api_fixtures.png`, `evidence/04_2_llm_design/screenshots/ep_bva.png`, `evidence/04_2_llm_design/screenshots/mutation.png` |
| Read | `evidence/04_2_llm_design/screenshots/properties_crosshair.png`, `evidence/04_2_llm_design/screenshots/locust_report.png`, `evidence/04_2_llm_design/screenshots/vault_status.png` |
| Read | `evidence/04_2_llm_design/screenshots/design_patterns.png`, `evidence/04_2_llm_design/screenshots/whole_course_diagram.png` |
| Generate | `evidence/04_2_llm_design/run_manifest.json` |
| Generate | `evidence/04_2_llm_design/gke/teardown.json` |
| Execute | `scripts/qa/capture_edai2_evidence.py`, `scripts/gke/check_budget.py`, `scripts/gke/manage_profile.py`, `scripts/gke/configure_evidence_ingress.py` |
| Read external/untracked | `tmp/edai2-gcp/kubeconfig` |
| Generate immutable gate evidence | `evidence/04_2_llm_design/gke/gcp_preflight_topic31.json`, `evidence/04_2_llm_design/gke/cost_forecast_topic31.json` |
| Update append-only | `evidence/04_2_llm_design/gke/usage_ledger.json` |

`EDAI2_SECTION03_BUNDLE_ID` is not free-form: load it from the top-level `bundle_id` in `section03_manifest.json`, require the manifest screenshot entry's `canonical_path` to equal the literal path shown above after expansion, and reject separators, traversal, or a mismatch. No wildcard discovery is permitted.

## Interfaces, Data Flow, and Failure Modes

Producer machine evidence + PNG + manifest row -> byte/decode/dimension check -> provenance/hash check -> selector/context/staleness/privacy check -> original-resolution human inspection -> accepted QA record.

Rejected image -> exact cause -> fresh gate/lease already held -> replay original reachability -> one capture to temp -> validation/full load -> atomic replace -> recheck -> pass or truthful failure. Public producer entries may recreate only their original temporary HTTPS route; `agentregistry_ui`, `grafana_ui`, `airflow_web`, `datahub_frontend`, and `vault_status` use inventory-verified loopback-only tunnels; billing uses its authenticated browser-console mode; Terraform/test-report/diagram entries use their original local-render source. A private entry is never exposed publicly, and every temporary route/tunnel is removed in `finally`.

All evidence -> truthful strict-partial `run_manifest.json` with Topic 32 as the only permitted pending producer -> disable ingress -> suspend -> GCP inventory -> `teardown.json`.

Failure modes include pending Topic 32 images, stale UI revision, Jenkins generic page, login state, selector clipping, PII/secret/account data, manifest/hash mismatch, unavailable external auth, lease/budget refusal, teardown residue. Every failure is explicit and blocks only dependent claims.

## Ordered Test-First Execution Tasks

### Task 1: Run machine screenshot audit

- [ ] Run `rtk uv run playwright install chromium`.
  - Expected: pinned browser available; no screenshot created yet.
- [ ] Run `rtk uv run pytest tests/e2e/llm/test_required_uis.py tests/unit/test_edai2_rubric_manifest.py -q`.
  - Expected: screenshot schema/privacy/provenance tests pass; live cases skip if no route.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --verify-screenshots-only --expected-edai2-count 32 --expected-extra gcp_billing_spend.png --ui-dimensions 1600x1000 --section03-dimensions 1600x900 --manifest evidence/04_2_llm_design/screenshots/ui_manifest.json --section03-manifest evidence/03_data_generator_improvement/section03_manifest.json --output tmp/edai2-gcp/topic31-screenshot-audit.json --strict-partial`.
  - Expected: exact per-file status; Topic 32's two future files may be `PendingProducer`, all other failures named.

### Task 2: Inspect every present image at original resolution

- [ ] Use the image viewer with detail `original` once per present Section 03 screenshot, each present EDAI2 screenshot, and `gcp_billing_spend.png`; record reviewer/pass/reason in the audit.
  - Expected: no decision is made from a thumbnail or montage.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --merge-original-resolution-review tmp/edai2-gcp/topic31-screenshot-audit.json --manifest evidence/04_2_llm_design/screenshots/ui_manifest.json --strict-partial`.
  - Expected: machine and visual results agree; disagreement rejects the file.

### Task 3: Acquire the topic lease, then conditionally repair

- [ ] Run `rtk uv run python scripts/gke/check_budget.py --project $env:GOOGLE_CLOUD_PROJECT --billing-account-env GOOGLE_BILLING_ACCOUNT --budget-notification-target-env EDAI2_BUDGET_NOTIFICATION_TARGET --recovery-sink-env EDAI2_VAULT_RECOVERY_SINK --recovery-sink-attestation $env:EDAI2_RECOVERY_SINK_ATTESTATION --required-permissions configs/gke/required_permissions.json --dns-probes acme-staging-v02.api.letsencrypt.org,huggingface.co,storage.googleapis.com --live-external-preflight --preflight-output evidence/04_2_llm_design/gke/gcp_preflight_topic31.json --trial-expires-at $env:EDAI2_TRIAL_EXPIRES_AT --current-spend-usd $env:EDAI2_CURRENT_SPEND_USD --spend-observed-at $env:EDAI2_SPEND_OBSERVED_AT --usage-ledger evidence/04_2_llm_design/gke/usage_ledger.json --envelope configs/gke/cost_envelope.yaml --requested-profile rubric-evidence --requested-ttl 2h --output evidence/04_2_llm_design/gke/cost_forecast_topic31.json`.
  - Expected: fresh live external/IAM/recovery/budget/capacity gate passes with redacted output; otherwise no mutation or recapture occurs.
- [ ] Run `rtk uv run python scripts/gke/manage_profile.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT rubric-evidence --ttl 2h --acquire-session-lease --owner topic31-screenshot-qa --commit-sha $env:EDAI2_COMMIT_SHA`.
  - Expected: fresh sole lease.
- [ ] If a non-Topic-32 image is rejected, run `rtk uv run python scripts/qa/capture_edai2_evidence.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --platform-inventory evidence/04_2_llm_design/gke/platform_install.json --recapture-rejected tmp/edai2-gcp/topic31-screenshot-audit.json --replay-original-reachability --public-route-controller scripts/gke/configure_evidence_ingress.py --private-loopback-only --max-attempts-per-image 1 --preserve-producer-topic --viewport 1600x1000 --manifest evidence/04_2_llm_design/screenshots/ui_manifest.json --strict-partial`.
  - Expected: only rejected non-Topic-32 files are attempted once. Public entries temporarily recreate only their original route; private endpoint keys use `127.0.0.1` tunnels and never ingress; billing/local-render entries use their original source mode. Every route/tunnel closes in `finally`, and an invalid replacement never overwrites a valid file.

### Task 4: Verify cross-cutting run evidence

- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --strict-partial --allow-pending-producer-topic 32 --root evidence/04_2_llm_design --output evidence/04_2_llm_design/run_manifest.json`.
  - Expected: `run_manifest.json` links cost/TTL/capacity, Terraform, Kubernetes, Airflow/DataHub, registry/chat/KEDA/Jenkins, Vault/recovery, persistence, observability, benchmark/evaluation/load/notebooks/rollbacks and screenshot QA. Topic 32's two not-yet-produced images are explicit `PendingProducer`; every other missing/failed item remains truthful `Partial`/`Missing`.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --verify-screenshots-only --expected-edai2-count 32 --expected-extra gcp_billing_spend.png --manifest evidence/04_2_llm_design/screenshots/ui_manifest.json --strict-partial`.
  - Expected: every existing producer file passes; Topic 32 images remain explicit pending until Topic 32.

### Task 5: Teardown regardless of QA result

- [ ] Run `rtk uv run python scripts/gke/configure_evidence_ingress.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --disable`.
  - Expected: routes/controller exposure disabled; safe if already disabled.
- [ ] Run `rtk uv run python scripts/gke/manage_profile.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT suspended --release-session-lease --owner topic31-screenshot-qa --allow-no-lease --output evidence/04_2_llm_design/gke/teardown.json`.
  - Expected: pools zero, no lease/refcount, ingress disabled.
- [ ] Run `rtk gcloud compute forwarding-rules list --project $env:GOOGLE_CLOUD_PROJECT --filter="labels.edai2=true" --format=json`.
  - Expected: empty list.
- [ ] Run `rtk kubectl --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT get service -A --field-selector spec.type=LoadBalancer`.
  - Expected: no EDAI2 LoadBalancer.
- [ ] Run `rtk git status --short --branch`.
  - Expected: same branch/revision lineage and request-scoped files.

## Evidence and Screenshot Ownership

Topic 31 owns `run_manifest.json`, `teardown.json`, and QA decisions only. It owns no primary rubric cell and no primary screenshot. All 33 screenshot producer assignments remain as listed. Topic 32 must add its two images and rerun strict all-image verification.

## Cleanup and Runtime Release

- Delete `tmp/edai2-gcp/topic31-screenshot-audit.json` only after its substantive results/hashes are in the durable manifest.
- Close browser contexts; remove temp PNGs/capture pods.
- Disable ingress and release `topic31-screenshot-qa` even when QA fails.
- Verify both pools zero, no EDAI2 LoadBalancer/forwarding rule, no lease owner/refcount.
- Do not Terraform-destroy persistent resources without separate authorization.

## Rubric Traceability

Topic 31 has no primary rubric cell. Its QA gate is required before any cell may be `Satisfied`; failed images/machine links flow into Topic 32 as truthful `Partial`/`Missing` results.

## Definition of Done

- [ ] Fixed hashes, branch, predecessor records, and explicit context pass.
- [ ] Every present image receives machine and original-resolution review.
- [ ] Exactly 32 EDAI2 names plus billing are accounted for; two Topic 32 images are explicit pending until produced.
- [ ] A fresh <=2h gate/lease was acquired after the read-only audit; any live repair used one bounded attempt and replayed its original reachability.
- [ ] Run manifest is fail-closed and contains no synthesized proof.
- [ ] Teardown proves zero pools, disabled ingress, no forwarding rule/LoadBalancer/lease.
- [ ] Final `rtk git status --short --branch` is recorded.

## Completion Record

- **Status:** Not started; no cross-cutting QA or teardown claim.
- **Branch / revision:** Record exact `rtk git status --short --branch`; none recorded.
- **Affected files:** None at plan-authoring time.
- **Command / exit-code log:** No execution commands recorded.
- **Evidence / SHA-256 log:** No run/teardown/QA evidence recorded.
- **Screenshot QA:** 32 EDAI2 names plus billing and Section 03 set not audited.
- **Cleanup / runtime release:** No lease held by this plan artifact.
- **Limitations:** `design_patterns.png` and `whole_course_diagram.png` are intentionally produced/strictly revalidated in Topic 32.
- **Handoff:** Topic 32 receives per-image pass/fail, pending producer states, run manifest, teardown hash, and truthful limitations.
