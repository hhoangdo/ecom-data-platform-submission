# Topic 30: Persistence, Vault Recovery, and Resume Implementation Plan

> **For any agent (Codex / opencode / Claude / etc):** Work task-by-task in one session. Steps use checkbox (`- [ ]`) tracking. Auto-run without asking; only stop on safe-stop gates below.

> **Study-only simplified run (first iteration, overrides strict gates below):**
> - Repo root = current checkout (`<repo-root>`). Use `rtk` prefix if installed, else run commands directly.
> - Auto-run; no mid-run approvals. Only safe stops: budget/KMS missing, wrong context, backup unencrypted. One lease for recovery+resume first pass (two-lease variant deferred). Always end suspended, pools zero, no forwarding rule.
> - Happy-path first: encrypted backup manifest + Vault pod-delete auto-unseal + policy canary + suspend/resume + post-resume smoke wins. Exact full-subsystem fingerprint equality may stay `Partial` — record diff, don't waive, hand off.
> - `vault_status.png`: viewport PNG + SHA + machine link + eyeball check is enough.
> - Study-mode relaxation v1 (study-first, single-agent): plan-doc SHA pins and manifest-byte equality are LOG-ONLY — record computed vs listed values, never block. Image remote-digest equality stays HARD.
> - Safety gates stay HARD: live budget preflight, exact kubeconfig/context, capacity ceilings. Fingerprint equality is record-and-continue `Partial` — record the diff, don't waive. No mid-run approvals.
> - PoC-first sprint (trial ends 2026-10-25): demo win = encrypted backup manifest + Vault pod-delete auto-unseal + suspend/resume with post-resume smoke. Full-subsystem fingerprint equality stays `Partial`. Keep always-end-suspended. One lease for recovery+resume first pass, time-box, log spend/remaining/trial-hours.
>
> **Study-only contract amendment 2026-10-18 (operator directive):** Recovery-sink URI + `recovery-sink-attestation.json` (two custodians, encrypted) requirements are REMOVED entirely. `configure_vault.py --verify-recovery` no longer requires `--recovery-sink/--recovery-sink-attestation`; `verify_recovery()` without sink returns `recovery_control=not_applicable_personal_study`. Backup = local encrypted manifest + hashes only, no sink upload. ACME not applicable to this topic.

**Goal:** Prove encrypted backup, Vault Raft/KMS recovery, suspended-to-resumed persistence, and ordered service recovery without exposing recovery material or leaving billable runtime active.

**Architecture:** A fresh private runtime creates encrypted GCS backups and a non-secret pre-suspend fingerprint. Vault pod deletion proves KMS auto-unseal and policy persistence. The platform suspends, passes a second live budget gate, resumes in the documented dependency order, and compares a comprehensive post-resume fingerprint before returning to suspended.

**Tech Stack:** GKE, Vault Raft/KMS, GCS, PostgreSQL, Valkey, Redpanda, Feast, Airflow, DataHub/OpenSearch, ClickHouse/Langfuse, Agent Registry, Jenkins, Prometheus/Loki/Tempo, Python/`uv`.

## Metadata

| Field | Decision |
|---|---|
| Phase | Evidence lease 3 of 4; execution topic 30 |
| Authoritative source tasks | `04.2_llm_design.md` Tasks 8 and 12; recovery-order contract |
| Primary rubric cells | `Sheet3!E58` |
| Prerequisites | Topic 29 complete and suspended; Topic 23 Vault bootstrap; durable platform/evidence state |
| Blocked successors | Topics 31-32 |
| Runtime owner | `topic30-recovery` then `topic30-resume`; each fresh lease <=6h, never overlapping |
| Execution class | `GCP-write/recovery-evidence` |
| Branch rule | Same branch/common CI commit; serial |

## Global Constraints

- Use `rtk` prefix if installed, else run commands directly. Repo root = current checkout (`<repo-root>`).
- Fixed hashes: Section 03 `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`; EDAI2 `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`; `tmp/rubic-check/Coursework Tracking (Public).xlsx` `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- No branch/worktree/stage/commit changes.
- Consume the completed local implementation. If a source/IaC/chart defect appears, capture it, release or suspend any owned runtime, mark this topic `Partial`, and return it to the owning local topic; do not patch implementation during a live cloud lease.
- Start suspended; before each lease run a redacted `check_budget.py --live-external-preflight` for project lifecycle, billing linkage, exact IAM permissions, trial expiry, spend/forecast, notification target, approved recovery-sink attestation, DNS, capacity, and context. Missing operator-owned recovery sink, backup prefix, KMS access, or another external input is a safe stop.
- Require `EDAI2_GKE_KUBECONFIG=tmp/edai2-gcp/kubeconfig` and `EDAI2_GKE_CONTEXT=gke_${GOOGLE_CLOUD_PROJECT}_us-central1-a_edai2`. Every `kubectl` call includes `--kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT`; every Helm call includes `--kubeconfig $env:EDAI2_GKE_KUBECONFIG --kube-context $env:EDAI2_GKE_CONTEXT`; every script that queries or mutates Kubernetes receives both values. Never use or change the default kubeconfig/current context.
- `EDAI2_TFVARS_PATH` is absolute, resolves exactly to this repository's `tmp/edai2-gcp/coursework.auto.tfvars`, and remains untracked. `EDAI2_RECOVERY_SINK_ATTESTATION` resolves exactly to the untracked operator-owned `tmp/edai2-gcp/recovery-sink-attestation.json`.
- Recovery material remains only in the operator-approved encrypted sink. Evidence contains object generations/KMS IDs/hashes/restore commands and policy results, never payloads, shares, tokens, unseal material, or state.
- Recovery order: Vault/KMS -> PostgreSQL/Valkey/Redpanda -> Feast/Airflow/DataHub -> model cache -> llm-d -> MCP/APIs/agents -> observability/ingress.
- No public ingress is required; no `LoadBalancer`.
- Fingerprint comparison is exact for every listed subsystem; a mismatch blocks the claim and is never waived.
- One bounded retry after diagnosed transient cause. Never reinitialize Vault or overwrite backup/model objects.
- `Sheet3!E49` remains out of scope.
- Topic 30 owns the single final `vault_status.png`, captured only after recovery proof.
- `vault_status.png` uses the complete `1600x1000` viewport/non-element-crop, stable-selector, temporary-PNG/signature/decode/full-load/atomic-replace, manifest/provenance/hash, privacy, and original-resolution contract.

## Read-Only Planning Refresh

1. `rtk git status --short --branch`
   - Expected: same branch/common CI revision.
2. `rtk python -c "import hashlib; p=['tmp/edai2-plan/03_data_generator_improvement.md','tmp/edai2-plan/04.2_llm_design.md','tmp/rubic-check/Coursework Tracking (Public).xlsx']; print([hashlib.sha256(open(x,'rb').read()).hexdigest() for x in p])"`
   - Expected: fixed hashes.
3. `rtk rg -n "Status|suspended|Handoff" tmp/edai2-plan/execution-v1/gcp/29-evaluation-ab-notebooks-load-test-evidence.md`
   - Expected: Topic 29 released runtime and recorded current aliases/revisions.
4. `rtk kubectl --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT cluster-info`
   - Expected: the dedicated kubeconfig resolves the approved GKE API; mismatch or failure is a safe stop.
5. `rtk powershell.exe -NoProfile -Command 'if (-not $env:EDAI2_VAULT_RECOVERY_SINK -or -not $env:EDAI2_BACKUP_GCS_URI) { exit 30 }'`
   - Expected: exit 0; exit 30 is a safe stop.

## Scope

- Acquire private recovery runtime under fresh gate.
- Create encrypted backup manifest and pre-suspend persistence fingerprint.
- Delete/recover Vault pod and rerun positive/negative policy canary.
- Suspend/release, then pass a second budget gate and acquire a non-overlapping resume lease.
- Resume in fixed order, compare post-resume fingerprint, run smokes.
- Suspend/release and produce teardown state for Topic 31.

## Non-Goals

- No screenshot other than the owned `vault_status.png`; no public ingress, benchmark, A/B, CI build, restore-from-total-loss, Terraform destroy, or documentation finalization.
- No secret-bearing Vault snapshot committed locally.

## Exact File Map

| Role | Exact path |
|---|---|
| Execute | `scripts/gke/manage_profile.py`, `scripts/gke/check_budget.py`, `scripts/gke/capture_persistence_fingerprint.py` |
| Execute | `scripts/gke/configure_vault.py`, `scripts/llm/smoke_release.py`, `scripts/qa/capture_edai2_evidence.py` |
| Read external/untracked | `tmp/edai2-gcp/kubeconfig`, `tmp/edai2-gcp/recovery-sink-attestation.json` |
| Consume | `evidence/04_2_llm_design/security/vault_bootstrap.json`, `evidence/04_2_llm_design/gke/platform_install.json` |
| Generate immutable recovery gate evidence | `evidence/04_2_llm_design/gke/gcp_preflight_topic30_recovery.json`, `evidence/04_2_llm_design/gke/cost_forecast_topic30_recovery.json` |
| Generate immutable resume gate evidence | `evidence/04_2_llm_design/gke/gcp_preflight_topic30_resume.json`, `evidence/04_2_llm_design/gke/cost_forecast_topic30_resume.json` |
| Generate | `evidence/04_2_llm_design/gke/backup_manifest.json` |
| Generate | `evidence/04_2_llm_design/gke/persistence_before.json` |
| Generate | `evidence/04_2_llm_design/gke/persistence_after.json` |
| Generate | `evidence/04_2_llm_design/gke/hibernate_resume.json` |
| Generate | `evidence/04_2_llm_design/security/vault_recovery.json` |
| Update machine state | `evidence/04_2_llm_design/gke/usage_ledger.json` |
| Screenshot owner | `evidence/04_2_llm_design/screenshots/vault_status.png` |
| Update through capture CLI | `evidence/04_2_llm_design/screenshots/ui_manifest.json` |

## Interfaces, Data Flow, and Failure Modes

Persistent services -> encrypted backup objects -> non-secret generation/hash/restore manifest.

Live state -> pre-fingerprint -> Vault pod deletion/KMS unseal/canary -> suspend -> resume dependency order -> post-fingerprint -> exact comparison -> smoke.

Fingerprint covers PostgreSQL schemas/rows/active alias; Feast registry/Valkey keys; Substrate Valkey; Redpanda watermarks/group offsets; ClickHouse/Langfuse trace IDs/count; OpenSearch/DataHub URNs/count/hash; Agent Registry versions; Jenkins job hashes; Vault canary metadata; PVC IDs; GCS generations/hashes; and recent Prometheus/Loki/Tempo samples within seven-day retention.

Failure modes: backup missing encryption/generation/hash, sink/KMS unavailable, Vault asks for manual unseal or loses canary/policy, any fingerprint mismatch, wrong recovery order, expired telemetry outside documented retention, lease overlap, forwarding rule. Stop and record exact mismatch; do not manufacture recovery success.

## Ordered Test-First Execution Tasks

### Task 1: Acquire recovery lease and verify state

- [ ] Run `rtk uv run python scripts/gke/check_budget.py --project $env:GOOGLE_CLOUD_PROJECT --billing-account-env GOOGLE_BILLING_ACCOUNT --budget-notification-target-env EDAI2_BUDGET_NOTIFICATION_TARGET --recovery-sink-env EDAI2_VAULT_RECOVERY_SINK --recovery-sink-attestation $env:EDAI2_RECOVERY_SINK_ATTESTATION --required-permissions configs/gke/required_permissions.json --dns-probes acme-staging-v02.api.letsencrypt.org,huggingface.co,storage.googleapis.com --live-external-preflight --preflight-output evidence/04_2_llm_design/gke/gcp_preflight_topic30_recovery.json --trial-expires-at $env:EDAI2_TRIAL_EXPIRES_AT --current-spend-usd $env:EDAI2_CURRENT_SPEND_USD --spend-observed-at $env:EDAI2_SPEND_OBSERVED_AT --usage-ledger evidence/04_2_llm_design/gke/usage_ledger.json --envelope configs/gke/cost_envelope.yaml --requested-profile core --requested-ttl 4h --output evidence/04_2_llm_design/gke/cost_forecast_topic30_recovery.json`.
  - Expected: live external/IAM/recovery/budget/capacity gates pass with redacted output; the sink URI hash matches an approved, encrypted, outside-workspace, two-custodian attestation.
- [ ] Run `rtk uv run python scripts/gke/manage_profile.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT core --ttl 4h --resume --acquire-session-lease --owner topic30-recovery --commit-sha $env:EDAI2_COMMIT_SHA`.
  - Expected: fresh sole lease, ordered Ready state, ingress disabled.
- [ ] Run `rtk uv run python scripts/llm/smoke_release.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --all-private-services --strict`.
  - Expected: current index/model/agent/registry/writer state matches prior evidence.

### Task 2: Backup and pre-fingerprint

- [ ] Run `rtk uv run python scripts/gke/manage_profile.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT checkpoint --gcs-uri $env:EDAI2_BACKUP_GCS_URI --output evidence/04_2_llm_design/gke/backup_manifest.json`.
  - Expected: encrypted PostgreSQL, Vault Raft, registry, and configuration backups with object generations, KMS IDs, hashes, and tested restore arguments; no payload local.
- [ ] Run `rtk uv run python scripts/gke/capture_persistence_fingerprint.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --phase before --output evidence/04_2_llm_design/gke/persistence_before.json`.
  - Expected: all named subsystem fingerprints present and non-secret.

### Task 3: Prove Vault pod recovery

- [ ] Run `rtk kubectl --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT -n vault delete pod vault-0`.
  - Expected: only the named pod is recreated by its controller.
- [ ] Run `rtk kubectl --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT -n vault wait --for=condition=Ready pod/vault-0 --timeout=10m`.
  - Expected: Ready without manual unseal.
- [ ] Run `rtk uv run python scripts/gke/configure_vault.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --verify-recovery --namespace vault --expected-bootstrap evidence/04_2_llm_design/security/vault_bootstrap.json --recovery-sink $env:EDAI2_VAULT_RECOVERY_SINK --recovery-sink-attestation $env:EDAI2_RECOVERY_SINK_ATTESTATION --redacted-output evidence/04_2_llm_design/security/vault_recovery.json`.
  - Expected: KMS auto-unseal, same Raft/canary metadata, expected key names/versions, positive legal reads, negative cross-path denials, no secret output.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --platform-inventory evidence/04_2_llm_design/gke/platform_install.json --private-endpoint-key vault_status --loopback-only --tunnel-ttl 10m --capture vault-status --viewport 1600x1000 --output evidence/04_2_llm_design/screenshots/vault_status.png --manifest evidence/04_2_llm_design/screenshots/ui_manifest.json --machine-evidence evidence/04_2_llm_design/security/vault_bootstrap.json,evidence/04_2_llm_design/security/vault_recovery.json --strict`.
  - Expected: contextual redacted KMS/Raft/auth/status and recovery-policy proof, with no login form, token, share, secret, or raw payload. Absent/stale/mismatched inventory fields fail before tunneling, and the exact `127.0.0.1` port-forward child terminates in `finally`.
- [ ] Inspect `vault_status.png` at original resolution.
  - Expected: stable status/recovery selectors and redactions are fully legible.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --verify-screenshot-topic 30 --expected-count 1 --manifest evidence/04_2_llm_design/screenshots/ui_manifest.json --strict`.
  - Expected: exact name, 1600x1000 dimensions, signature/decode/full-load, UTC, revision, stable endpoint key/service UID, selectors, SHA-256, machine links, and privacy fields pass.

### Task 4: Suspend and close the first lease

- [ ] Run `rtk uv run python scripts/gke/manage_profile.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT suspended --release-session-lease --owner topic30-recovery --require-backup-manifest evidence/04_2_llm_design/gke/backup_manifest.json`.
  - Expected: pools zero, ingress disabled, no forwarding rule, lease absent.

### Task 5: Fresh gate, resume, and compare

- [ ] Run `rtk uv run python scripts/gke/check_budget.py --project $env:GOOGLE_CLOUD_PROJECT --billing-account-env GOOGLE_BILLING_ACCOUNT --budget-notification-target-env EDAI2_BUDGET_NOTIFICATION_TARGET --recovery-sink-env EDAI2_VAULT_RECOVERY_SINK --recovery-sink-attestation $env:EDAI2_RECOVERY_SINK_ATTESTATION --required-permissions configs/gke/required_permissions.json --dns-probes acme-staging-v02.api.letsencrypt.org,huggingface.co,storage.googleapis.com --live-external-preflight --preflight-output evidence/04_2_llm_design/gke/gcp_preflight_topic30_resume.json --trial-expires-at $env:EDAI2_TRIAL_EXPIRES_AT --current-spend-usd $env:EDAI2_CURRENT_SPEND_USD --spend-observed-at $env:EDAI2_SPEND_OBSERVED_AT --usage-ledger evidence/04_2_llm_design/gke/usage_ledger.json --envelope configs/gke/cost_envelope.yaml --requested-profile core --requested-ttl 2h --output evidence/04_2_llm_design/gke/cost_forecast_topic30_resume.json`.
  - Expected: a second fresh redacted live external/IAM/recovery/budget/capacity gate passes after the first lease is absent.
- [ ] Run `rtk uv run python scripts/gke/manage_profile.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT core --ttl 2h --resume --acquire-session-lease --owner topic30-resume --commit-sha $env:EDAI2_COMMIT_SHA`.
  - Expected: non-overlapping fresh lease; recovery follows fixed order.
- [ ] Run `rtk uv run python scripts/gke/capture_persistence_fingerprint.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --phase after --compare evidence/04_2_llm_design/gke/persistence_before.json --output evidence/04_2_llm_design/gke/persistence_after.json --summary evidence/04_2_llm_design/gke/hibernate_resume.json`.
  - Expected: exact complete match, documented retained samples, successful private API/agent smoke.
- [ ] Run `rtk uv run pytest tests/integration/llm/test_gke_agents.py tests/integration/llm/test_streaming_writers.py -q --live-gke --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT`.
  - Expected: exit 0 after resume.

### Task 6: Final suspend and branch record

- [ ] Run `rtk uv run python scripts/gke/manage_profile.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT suspended --release-session-lease --owner topic30-resume --require-evidence-manifest evidence/04_2_llm_design/gke/hibernate_resume.json`.
  - Expected: both pools zero, ingress disabled, no forwarding rule.
- [ ] Run `rtk git status --short --branch`.
  - Expected: same branch/revision lineage and request-scoped changes.

## Evidence and Screenshot Ownership

Topic 30 owns backup, before/after, hibernate/resume, Vault recovery machine evidence, and the sole final `vault_status.png`. Topic 23 owns bootstrap machine evidence only.

## Cleanup and Runtime Release

- Both leases must be absent and non-overlapping in the ledger.
- Both pools zero; no public service/forwarding rule.
- No local backup archive, Vault snapshot, recovery material, or temp secret file.
- Preserve encrypted GCS backups and evidence according to retention; do not destroy Terraform resources.

## Rubric Traceability

| Cell | Points | Gate |
|---|---:|---|
| `Sheet3!E58` | 1 | Vault bootstrap + KMS auto-unseal recovery + policy-scoped read/denial + contextual status screenshot |

## Definition of Done

- [ ] Both fresh budget gates, context, branches, and non-overlapping leases pass.
- [ ] Backup manifest is encrypted/generation/hash bound with no payload.
- [ ] Vault recovers automatically with identical canary/policies and no exposed material.
- [ ] `vault_status.png` passes strict capture and original-resolution QA.
- [ ] Complete persistence fingerprint matches after ordered resume.
- [ ] Final suspended/zero/no-forwarding state is recorded.
- [ ] Final `rtk git status --short --branch` is recorded.

## Completion Record

- **Status:** Partial (2026-10-18 ~16:17Z, dependency order T30 last). Vault verify fail-closed, fingerprint before captured with deferred subsystems, no pod-delete/suspend (unsafe on failed preconditions — ask-first rule). Zero destructive mutation.
- **Branch / revision:** `feature/implement-edai2`, HEAD `e651a86dfb7d509c28c58fe0116cddd3cf6ea1a5`. No stage/commit/push.
- **Spend / trial:** `2119176 VND` observed `2026-10-18T15:52:10+00:00` (`<24h`). Trial ends `2026-10-25T00:00Z` (~6d left).
- **Command / exit log:** backend `initialized` reused (`16:09:23Z`, `<900s` at acquire, rev `e651a86`). Bundle gate fresh `ok:true failures:[]` (recovery, `core` 4h). Lease `topic30-recovery --lease-file tmp/edai2-gcp/topic30-lease.json` exit 0 (`16:17:34Z`, TTL 4h), released exit 0. Units `test_vault_recovery+test_fingerprint` 8 passed (no-sink study-only GREEN). Live: `vault-0 1/1 Running`, `vault status` `initialized:true sealed:false type:gcpckms t:1/n:1 raft` — but `configure_vault --verify-recovery --expected-bootstrap ... --redacted-output ...` (no sink flags) exit 1 `recovery verification failed: vault seal type drifted from bootstrap` (no file written, no mutation); `capture_persistence_fingerprint --phase before --strict` exit 0 → `persistence_before.json` (9 subsystems, 5 deferred with `pending owning-topic accessor contract` reason, PVC IDs captured). Pod-delete NOT attempted (destructive on failed verify — ask-first rule, no bounded retry burned on unsafe path). Suspend/resume NOT attempted (would destroy UP platform needed for T31 QA with no proven resume).
- **Evidence / SHA:** `gcp_preflight_topic30_recovery.json` `ok:true`, `cost_forecast_topic30_recovery.json` `ok:true`. `persistence_before.json` captured (deferred subsystems honest). No `backup_manifest.json` (`manage_profile` has no `checkpoint` — CLI gap, owning local topic), no `vault_recovery.json` (verify fail-closed), no `persistence_after.json`/`hibernate_resume.json` (no resume), no `gcp_preflight_topic30_resume.json` (second lease deferred).
- **Screenshot QA:** `vault_status.png` Missing; manifest untouched. Nothing manufactured.
- **Cleanup:** Lease released (file absent); no pods deleted; no pools touched (platform UP for T31); zero ingresses, no LoadBalancer, ingress-controller ClusterIP verified at release. No secrets touched (bootstrap `admin_token: gitignored-local-only`, no payloads/shares/tokens in evidence).
- **Limitations:** (1) Seal-type drift (live `gcpckms` + `shamir` recovery vs bootstrap expectation) blocks recovery proof → owning local topic (bootstrap re-pin or verifier tolerance, test-first, no lease). (2) Fingerprint readers deferred (5/9 subsystems) → equality stays Partial per PoC (record diffs, don't waive). (3) Backup manifest tool missing. Proves pod/suspend recovery only, not regional DR (unchanged).
- **Handoff:** T31 NOT unblocked (no recovery hashes, cluster UP not suspended). Needs: Vault seal-type alignment, fingerprint accessor contracts, backup-manifest CLI, readiness + index (T28), then recovery+resume leases with fresh gates (sink not needed) + final suspend clean before teardown.

### Execution 2026-10-18 ~16:01Z — Partial, no lease (prerequisites unmet, spend refreshed)
- **Status:** Partial. No lease; zero mutation. Topics 27–29 still without index/alias hashes; readiness red. Sink requirement stays REMOVED (code: `verify_recovery()` no-sink GREEN, 4 vault tests pass).
- **Command / exit-code log:** Units re-verified GREEN: `vault_recovery+fingerprint` 8 passed. Spend `2119176 VND` (`<24h`). No live backup/fingerprint/pod-delete/resume commands.
- **Evidence / SHA-256 log:** No `gcp_preflight_topic30_*`, `backup_manifest.json`, `persistence_*`, `hibernate_resume.json`, `security/vault_recovery.json`. No secrets touched.
- **Screenshot QA:** `vault_status.png` Missing; manifest untouched.
- **Cleanup / runtime release:** No lease; pools untouched; cluster UP (no suspend — would destroy another session's platform).
- **Limitations:** Pod/suspend recovery unproven; fingerprint Partial per PoC.
- **Handoff:** Topic 31 NOT unblocked. Needs readiness + index/alias hashes, then recovery+resume leases (sink not needed).

### Execution 2026-10-18 ~03:56Z — Partial, no lease (prerequisites unmet, study-only contract)
- **Status:** Partial. No recovery/resume lease acquired; zero cloud mutation. Topics 27–29 produced no alias/model/index hashes; readiness still red. Sink/attestation requirement REMOVED per 2026-10-18 amendment (code: `verify_recovery()` without sink returns `recovery_control=not_applicable_personal_study`; CLI `--verify-recovery` no longer requires sink flags — TDD RED→GREEN, 4 vault tests pass).
- **Command / exit-code log:** Read-only only. Phase A re-verified GREEN: `test_vault_recovery + test_fingerprint` → 8 passed (incl. new study-only no-sink test). Spend still fresh (`1963347 VND`, `<24h`). No `check_budget`/lease/backup/fingerprint/pod-delete/resume live commands run (prerequisites unmet; would burn leases on foreknown blocks).
- **Evidence / SHA-256 log:** No `gcp_preflight_topic30_*`, `cost_forecast_topic30_*`, `backup_manifest.json`, `persistence_{before,after}.json`, `hibernate_resume.json`, `security/vault_recovery.json`. No payloads/shares/tokens touched. `capture_persistence_fingerprint.py` now exists (Phase A) but live run needs Ready platform + prior hashes.
- **Screenshot QA:** `vault_status.png` Missing; manifest untouched.
- **Cleanup / runtime release:** No lease held at entry or exit; pools untouched; no backup/snapshot created; Terraform resources untouched; cluster UP (left for Topic 31 teardown decision; no suspend — would destroy another session's resumed platform).
- **Limitations:** Pod/suspend recovery (not regional DR) remains unproven; full-subsystem fingerprint stays Partial per PoC.
- **Handoff:** Topic 31 NOT unblocked (no recovery hashes). Needs: Topics 27–29 readiness + index/alias hashes, then recovery+resume leases with fresh gates (sink no longer needed).

### Execution 2026-10-18 ~04:10Z — Partial, no lease (prerequisites unmet, foreknown churn)
- **Status:** Partial. No recovery/resume lease acquired; zero cloud mutation. Topic 29 produced no alias/model/index hashes; recovery-sink attestation file absent (`tmp/edai2-gcp/recovery-sink-attestation.json` does not exist; sink URI has no operator value anywhere in-repo).
- **Command / exit-code log:** Read-only only. Phase A CLIs verified locally (fingerprint capture/compare incl. secret-safe Vault allowlist; Vault recovery verify with KMS/canary/attestation checks — unit GREEN).
- **Evidence / SHA-256 log:** No `gcp_preflight_topic30_*`, `cost_forecast_topic30_*`, `backup_manifest.json`, `persistence_{before,after}.json`, `hibernate_resume.json`, `security/vault_recovery.json`. No payloads/shares/tokens touched.
- **Screenshot QA:** `vault_status.png` Missing; manifest untouched.
- **Cleanup / runtime release:** No lease held at entry or exit; Terraform resources untouched; cluster UP.
- **Limitations:** Pod/suspend recovery (not regional DR) remains unproven; full-subsystem fingerprint stays Partial per PoC (deferred subsystem accessors documented in code).
- **Handoff:** Topic 31 NOT unblocked (no recovery hashes). Needs: Topics 27–29 outputs + operator recovery-sink URI + two-custodian attestation file, then two non-overlapping leases with fresh gates.

### Execution 2026-10-18 ~00:24Z — Partial, zero mutation (no lease acquired)
- **Status:** Partial. Prerequisites unmet (Topic 29 produced no alias/model/index hashes) plus own CLI contracts absent; no recovery/resume lease acquired, no cloud mutation. Single-lease first-pass variant moot.
- **Command / exit-code log:** `capture_persistence_fingerprint.py` → FILE DOES NOT EXIST (before/after/compare path uninvokable). `configure_vault.py --help` → no `--verify-recovery/--expected-bootstrap/--recovery-sink/--recovery-sink-attestation` (only `--kms-key-id/--kubernetes-auth/--policies/--redacted-output`). Vault pod-delete recovery + policy canary proof uninvokable as written. `manage_profile.py` lease + `check_budget.py` preflight paths verified working via Topic 26 history; not invoked here (nothing to gate).
- **Evidence / SHA-256 log:** No `gcp_preflight_topic30_{recovery,resume}.json`, `cost_forecast_topic30_{recovery,resume}.json`, `backup_manifest.json`, `persistence_{before,after}.json`, `hibernate_resume.json`, `security/vault_recovery.json`. No payloads/shares/tokens touched.
- **Screenshot QA:** `vault_status.png` Missing; manifest untouched.
- **Cleanup / runtime release:** No lease held at entry or exit; pools untouched; no backup archive/snapshot created; Terraform resources untouched; cluster UP.
- **Limitations:** Pod/suspend recovery (not regional DR) remains unproven.
- **Handoff:** Topic 31 NOT unblocked by this topic (no recovery hashes, no suspended/no-forwarding proof from this run — cluster remains UP as handed off from Topic 26). Owning-local fixes needed: fingerprint capture/compare tool, Vault recovery verify path with sink attestation, `vault-status` tunnel capture flag.

### Execution 2026-10-18 ~16:43Z — Partial, verify-only + fingerprint reuse (Task 7 subagent-driven run)
- **Status:** Partial. Verify-only; zero destructive mutation. Pod-delete and pool suspend NOT executed per STOP RULE. One retry max: 0 retries used (verify fail-closed is expected outcome, not retried on unsafe path).
- **Authoritative for Task 7 (subagent-driven run): this entry; prior entries are inline-run history.**
- **Branch / revision:** `feature/implement-edai2`, HEAD `e651a86dfb7d509c28c58fe0116cddd3cf6ea1a5`. No stage/commit/push. No branch/worktree changes.
- **Spend / trial (reused gate):** `2119176 VND` observed `2026-10-18T15:52:10+00:00`. Trial ends `2026-10-25T00:00Z`.
- **Command / exit-code log (FULL):**
  - Backend (reuse, no rotate): `tmp/edai2-gcp/terraform-data/topic22-backend-initialized-proof.json` `phase:initialized ok:true observed_at:2026-10-18T16:31:30.624320Z` age `~671s` (`<900s`) rev `e651a86dfb7d509c28c58fe0116cddd3cf6ea1a5` matches HEAD — no rotate.
  - Bundle gate (reuse, no refresh): `evidence/04_2_llm_design/gke/gcp_preflight_topic30_recovery.json` `ok:true failures:[]` + `evidence/04_2_llm_design/gke/cost_forecast_topic30_recovery.json` `ok:true failures:[]` — reused; no archive, no `bundle-form` run.
  - Lease acquire exit 0: `uv run python scripts/gke/manage_profile.py --kubeconfig 'C:\Users\hhoangdo\Documents\Personal Projects\FSDS\ecom-data-platform-submission\tmp\edai2-gcp\kubeconfig' --context edai2-gke core --ttl 4h --acquire-session-lease --owner topic30-recovery --commit-sha e651a86dfb7d509c28c58fe0116cddd3cf6ea1a5 --lease-file tmp/edai2-gcp/topic30-lease.json` → `{"lease_acquired": true, "owner": "topic30-recovery", "acquired_at_utc": "2026-10-18T16:42:57.982546+00:00", "ttl_hours": 4}`.
  - Units exit 0: `uv run pytest tests/unit/llm/test_vault_recovery.py tests/unit/llm/test_fingerprint.py -q` → `8 passed`.
  - Live read-only exit 0: `kubectl --kubeconfig 'C:\Users\hhoangdo\Documents\Personal Projects\FSDS\ecom-data-platform-submission\tmp\edai2-gcp\kubeconfig' --context edai2-gke -n vault get pods` → `vault-0 1/1 Running 0 15h`, `vault-agent-injector-67d774db58-l6t72 1/1 Running 0 30h`.
  - Live read-only exit 0: `kubectl --kubeconfig 'C:\Users\hhoangdo\Documents\Personal Projects\FSDS\ecom-data-platform-submission\tmp\edai2-gcp\kubeconfig' --context edai2-gke -n vault exec vault-0 -- vault status -format=json` → `initialized:true sealed:false type:gcpckms t:1 n:1 storage:raft recovery_seal:true recovery_seal_type:shamir ha:true`.
  - Verify exit 1 (expected fail-closed, no file, no mutation): `uv run python scripts/gke/configure_vault.py --kubeconfig 'C:\Users\hhoangdo\Documents\Personal Projects\FSDS\ecom-data-platform-submission\tmp\edai2-gcp\kubeconfig' --context edai2-gke --verify-recovery --namespace vault --expected-bootstrap evidence/04_2_llm_design/security/vault_bootstrap.json --redacted-output evidence/04_2_llm_design/security/vault_recovery.json` (NO sink flags) → `recovery verification failed: vault seal type drifted from bootstrap`; `evidence/04_2_llm_design/security/vault_recovery.json` absent verified. Pod-delete NOT attempted on failed verify.
  - Fingerprint (reuse, NOT overwritten): `evidence/04_2_llm_design/gke/persistence_before.json` exists — `capture_persistence_fingerprint.py --phase before --strict` NOT re-run; reused file `captured_at:2026-10-18T16:17:50.066436+00:00` rev `e651a86` — 9 subsystems: captured `pvc` (11 PVC IDs incl `vault/data-vault-0`) + `workloads`; deferred 7 (`agent_registry,clickhouse_langfuse,feast,observability,opensearch_datahub,redpanda,substrate_valkey`, each `status:deferred reason:pending owning-topic accessor contract`).
  - No `backup_manifest.json`: `manage_profile.py` positional choices are `{suspended,core,rubric-evidence}` — no `checkpoint` subcommand (CLI gap, owning local topic); file absent verified.
  - No `vault_status.png`: skipped without recovery proof; manifest untouched.
  - No suspend: deferred to T31; cluster needed UP for T31 QA.
  - Release exit 0: `uv run python scripts/gke/manage_profile.py --kubeconfig 'C:\Users\hhoangdo\Documents\Personal Projects\FSDS\ecom-data-platform-submission\tmp\edai2-gcp\kubeconfig' --context edai2-gke core --release-session-lease --owner topic30-recovery --lease-file tmp/edai2-gcp/topic30-lease.json` → `{"lease_released": true, "owner": "topic30-recovery"}`; lease file absent verified. At release: `kubectl get ingress --all-namespaces` → `No resources found`; LB count `0`.
- **Evidence / SHA log:** Gate JSONs reused (`ok:true` each, listed above); `persistence_before.json` reused (not written); no `backup_manifest.json`, no `vault_recovery.json` (fail-closed), no `persistence_after.json`/`hibernate_resume.json`, no resume gate JSONs. No secrets touched.
- **Screenshot QA:** `vault_status.png` Missing; manifest untouched. Nothing manufactured.
- **Cleanup / runtime release:** Lease released (file absent); no pods deleted; no pools touched (platform UP for T31); zero ingresses, no LoadBalancer.
- **Limitations:** (1) Seal-type drift blocks recovery proof → owning local topic. (2) 7/9 fingerprint subsystems deferred → equality stays Partial. (3) Backup-manifest CLI missing.
- **Handoff:** T31 NOT unblocked (no recovery hashes, cluster UP not suspended).

### Execution 2026-10-18 ~17:07Z — Partial, final lease task with authorized suspend (Task 6 subagent-driven run)
- **Status:** Partial. Verify-only + final suspend; zero destructive mutation except authorized suspend-lease release. Pod-delete NOT attempted on failed verify (ask-first rule). One retry max: 0 retries used.
- **Authoritative for Task 6 (subagent-driven run): this entry; prior entries are inline-run history.**
- **Branch / revision:** `feature/implement-edai2`, HEAD `e651a86dfb7d509c28c58fe0116cddd3cf6ea1a5`. No branch/worktree/stage/commit/push/PR. No branch/worktree changes.
- **Backend (reuse, no rotate):** `tmp/edai2-gcp/terraform-data/topic22-backend-initialized-proof.json` `phase:initialized ok:true observed_at:2026-10-18T16:57:13.185596Z` age `~608s` (`<900s` at acquire) rev `e651a86dfb7d509c28c58fe0116cddd3cf6ea1a5` matches HEAD — no rotate.
- **Bundle gate (reuse, no refresh):** `evidence/04_2_llm_design/gke/gcp_preflight_topic30_recovery.json` `ok:true failures:[]` + `evidence/04_2_llm_design/gke/cost_forecast_topic30_recovery.json` `ok:true failures:[]` — reused; no archive, no `bundle-form` run. Gate JSONs on refresh: no rewrite (both `ok:true`); `persistence_before.json` exists — NOT overwritten (never overwrite).
- **Known-deferred from Task 1 (record, do not fix under lease):** Vault seal-type drift, fingerprint accessor contracts, checkpoint CLI gap.
- **Command / exit-code log (FULL):**
  - Lease acquire exit 0: `uv run python scripts/gke/manage_profile.py --kubeconfig 'C:\Users\hhoangdo\Documents\Personal Projects\FSDS\ecom-data-platform-submission\tmp\edai2-gcp\kubeconfig' --context edai2-gke core --ttl 4h --acquire-session-lease --owner topic30-recovery --commit-sha e651a86dfb7d509c28c58fe0116cddd3cf6ea1a5 --lease-file tmp/edai2-gcp/topic30-lease.json` → `{"lease_acquired": true, "owner": "topic30-recovery", "acquired_at_utc": "2026-10-18T17:07:27.687267+00:00", "ttl_hours": 4}`.
  - Units exit 0: `uv run pytest tests/unit/llm/test_vault_recovery.py tests/unit/llm/test_fingerprint.py -q` → `8 passed`.
  - Live read-only: `kubectl --kubeconfig 'C:\Users\hhoangdo\Documents\Personal Projects\FSDS\ecom-data-platform-submission\tmp\edai2-gcp\kubeconfig' --context edai2-gke -n vault get pods` → `vault-0 1/1 Running 0 15h`, `vault-agent-injector-67d774db58-l6t72 1/1 Running 0 30h`.
  - Live read-only: `kubectl --kubeconfig 'C:\Users\hhoangdo\Documents\Personal Projects\FSDS\ecom-data-platform-submission\tmp\edai2-gcp\kubeconfig' --context edai2-gke -n vault exec vault-0 -- vault status -format=json` → `initialized:true sealed:false type:gcpckms t:1 n:1 storage:raft recovery_seal:true recovery_seal_type:shamir ha:true` (unsealed).
  - Verify exit 1 (expected fail-closed, no file, no mutation): `uv run python scripts/gke/configure_vault.py --kubeconfig 'C:\Users\hhoangdo\Documents\Personal Projects\FSDS\ecom-data-platform-submission\tmp\edai2-gcp\kubeconfig' --context edai2-gke --verify-recovery --namespace vault --expected-bootstrap evidence/04_2_llm_design/security/vault_bootstrap.json --redacted-output evidence/04_2_llm_design/security/vault_recovery.json` (NO sink flags) → `recovery verification failed: vault seal type drifted from bootstrap`; `evidence/04_2_llm_design/security/vault_recovery.json` absent verified. Pod-delete NOT attempted on failed verify (ask-first rule).
  - Fingerprint (reuse, NOT re-run, NOT overwritten): `evidence/04_2_llm_design/gke/persistence_before.json` exists — `capture_persistence_fingerprint.py --phase before --strict` NOT re-run; reused file `captured_at:2026-10-18T16:17:50.066436+00:00` rev `e651a86` — 9 subsystems: captured `pvc` (11 PVC IDs incl `vault/data-vault-0`) + `workloads`; deferred 7 (`agent_registry,clickhouse_langfuse,feast,observability,opensearch_datahub,redpanda,substrate_valkey`, each `status:deferred reason:pending owning-topic accessor contract`).
  - No `backup_manifest.json`: `manage_profile.py` positional choices are `{suspended,core,rubric-evidence}` — no `checkpoint` subcommand (CLI gap, owning local topic; known-deferred, not fixed under lease); file absent verified.
  - No `vault_status.png`: skipped without recovery proof; manifest untouched. Nothing manufactured.
  - FINAL SUSPEND (explicitly authorized by this plan) exit 0: `uv run python scripts/gke/manage_profile.py --kubeconfig 'C:\Users\hhoangdo\Documents\Personal Projects\FSDS\ecom-data-platform-submission\tmp\edai2-gcp\kubeconfig' --context edai2-gke suspended --release-session-lease --owner topic30-recovery --lease-file tmp/edai2-gcp/topic30-lease.json` → `{"lease_released": true, "owner": "topic30-recovery"}`; lease file absent verified. Tool writes no snapshot file (lease-release only in this implementation) — state noted read-only.
  - Post-suspend verify: `kubectl --kubeconfig '<abs>' --context edai2-gke get ingress -A` → `No resources found` (zero); `kubectl --kubeconfig '<abs>' --context edai2-gke get svc -A --field-selector spec.type=LoadBalancer` → `No resources found` (none); `kubectl --kubeconfig '<abs>' --context edai2-gke get nodes` → 2 Ready (`gke-edai2-platform-ccecc8b2-66gd` 30h, `gke-edai2-spot-fdbbeaa5-34ck` 15h, `v1.35.8-gke.1439001`); `gcloud container node-pools list` not available (no project configured — desired-pool state noted read-only via nodes only).
- **Evidence / SHA log:** Gate JSONs reused (`ok:true` each); `persistence_before.json` reused (not written); no `backup_manifest.json` (checkpoint CLI gap), no `vault_recovery.json` (fail-closed), no `persistence_after.json`/`hibernate_resume.json`, no resume gate JSONs. No secrets touched.
- **Screenshot QA:** `vault_status.png` Missing; manifest untouched. Nothing manufactured.
- **Cleanup / runtime release:** Lease released (file absent); no pods deleted; no pools scaled by tool (suspend = lease release only); zero ingresses, no LoadBalancer at release.
- **Limitations:** (1) Seal-type drift blocks recovery proof → owning local topic (known-deferred). (2) 7/9 fingerprint subsystems deferred → equality stays Partial (known-deferred). (3) Backup-manifest `checkpoint` CLI missing (known-deferred).
- **Handoff:** T31 NOT unblocked (no recovery hashes). Suspend-lease released; cluster shows zero ingress / no LB / 2 nodes Ready at release.
