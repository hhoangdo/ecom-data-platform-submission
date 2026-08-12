# Topic 30: Persistence, Vault Recovery, and Resume Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

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

- Read `C:\Users\oou1hc\.codex\RTK.md`; prefix every shell command with `rtk`.
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

- **Status:** Not started; no recovery or `Sheet3!E58` claim.
- **Branch / revision:** Record exact `rtk git status --short --branch`; none recorded.
- **Affected files:** None at plan-authoring time.
- **Command / exit-code log:** No execution commands recorded.
- **Evidence / SHA-256 log:** No backup/recovery/fingerprint evidence recorded.
- **Screenshot QA:** `vault_status.png` not captured.
- **Cleanup / runtime release:** No lease held by this plan artifact.
- **Limitations:** This proves pod/suspend recovery, not total regional disaster recovery.
- **Handoff:** Topic 31 requires exact recovery hashes and final suspended/no-forwarding proof.
