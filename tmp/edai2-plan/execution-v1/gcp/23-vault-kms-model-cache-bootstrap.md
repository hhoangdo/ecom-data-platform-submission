# Topic 23: Vault, KMS, and Model-Cache Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bootstrap KMS-auto-unsealed Vault and a generation/hash-pinned GCS model cache without exposing recovery material, credentials, or mutable model inputs.

**Architecture:** Terraform-provisioned KMS and GCS are consumed through Workload Identity. Vault uses integrated Raft, Kubernetes auth, narrow policies, and an operator-owned encrypted recovery sink outside the workspace. A one-time GKE Job packages three pinned model revisions into content-addressed `tar.zst` objects and a JCS manifest; consumers have no Hugging Face fallback.

**Tech Stack:** GKE, Vault, GCP KMS/GCS, Workload Identity, Kubernetes, Python/`uv`, Helm, Playwright, SHA-256.

## Metadata

| Field | Decision |
|---|---|
| Phase | Secure bootstrap; execution topic 23 |
| Authoritative source tasks | `04.2_llm_design.md` Tasks 7-8 |
| Primary rubric cells | None; supporting prerequisites for later owners only |
| Prerequisites | Topic 22 successful Completion Record, exact Terraform outputs, explicit kube context |
| Blocked successors | Topics 24-31 |
| Runtime owner | `topic23-bootstrap`, `core`, maximum 2h |
| Execution class | `GCP-write/security-sensitive` |
| Branch rule | Same branch/revision lineage; serial after Topic 22 |

## Global Constraints

- Read and obey `C:\Users\oou1hc\.codex\RTK.md`; prefix every shell command with `rtk`.
- Revalidate fixed hashes before execution: Section 03 `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`; EDAI2 `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`; rubric at `tmp/rubic-check/Coursework Tracking (Public).xlsx` `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- Prefix shell commands with `rtk`; do not create/switch branches/worktrees, stage, or commit.
- Consume the completed local implementation. If a source/IaC/chart defect appears, capture it, release or suspend any owned runtime, mark this topic `Partial`, and return it to the owning local topic; do not patch implementation during a live cloud lease.
- Require the exact Topic 22 project, zone `us-central1-a`, cluster `edai2`, and context `gke_${GOOGLE_CLOUD_PROJECT}_us-central1-a_edai2`.
- Require `EDAI2_GKE_KUBECONFIG=tmp/edai2-gcp/kubeconfig` and `EDAI2_GKE_CONTEXT=gke_${GOOGLE_CLOUD_PROJECT}_us-central1-a_edai2`. Every `kubectl` call includes `--kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT`; every Helm call includes `--kubeconfig $env:EDAI2_GKE_KUBECONFIG --kube-context $env:EDAI2_GKE_CONTEXT`; every script that queries or mutates Kubernetes receives both values. Never use or change the default kubeconfig/current context.
- Run a fresh redacted `check_budget.py --live-external-preflight` gate before entering `core`. Missing project, billing linkage, required IAM permission, trial expiry, spend, valid encrypted recovery-sink attestation, model-cache URI, DNS/HTTPS egress, or other external input is a safe stop.
- `EDAI2_TFVARS_PATH` is absolute, resolves exactly to `tmp/edai2-gcp/coursework.auto.tfvars`, and remains untracked.
- Recovery material must stream directly to `EDAI2_VAULT_RECOVERY_SINK`, an operator-approved encrypted sink outside the workspace and stdout. Never write a root token, recovery share, unseal value, secret payload, or Vault snapshot into Git/evidence/temp files.
- `EDAI2_RECOVERY_SINK_ATTESTATION` is exactly `tmp/edai2-gcp/recovery-sink-attestation.json`; it is non-secret/untracked and binds the sink URI only by SHA-256, with approval, encryption, out-of-workspace, and at least two-custodian assertions.
- Secret evidence contains identifiers, key names/fingerprints, policy results, thresholds/counts, and revocation proof only.
- GCS access uses ambient Workload Identity. JSON service-account keys are forbidden.
- Model IDs/revisions are exactly the pinned values in `configs/llm/models.yaml`. Uploads use `ifGenerationMatch=0`; each object records its own generation. No mutable alias or Hub fallback is accepted.
- Model cache <=5Gi and combined GCS/Artifact Registry <=15Gi.
- One bounded retry is allowed only after correcting a transient cause. A repeated failure produces truthful partial evidence and suspends.
- `Sheet3!E49` is permanently out of scope and must not cause a VM/Ansible path.

## Read-Only Planning Refresh

1. `rtk git status --short --branch`
   - Expected: same branch as Topic 22 and only completed-plan changes; no unexplained Vault/KMS/model-cache overlap.
2. `rtk python -c "import hashlib; p=['tmp/edai2-plan/03_data_generator_improvement.md','tmp/edai2-plan/04.2_llm_design.md','tmp/rubic-check/Coursework Tracking (Public).xlsx']; print([hashlib.sha256(open(x,'rb').read()).hexdigest() for x in p])"`
   - Expected: the three fixed hashes.
3. `rtk rg -n "Status|terraform_apply.json|EDAI2_GKE_KUBECONFIG|Handoff" tmp/edai2-plan/execution-v1/gcp/22-gcp-account-budget-terraform-apply.md`
   - Expected: Topic 22 completion names exact evidence hashes/context and no unresolved apply limitation.
4. `rtk kubectl --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT cluster-info`
   - Expected: the dedicated kubeconfig resolves the approved GKE API; any mismatch stops execution without falling back to a default context.
5. `rtk terraform -chdir=infra/terraform/edai2 output -json`
   - Expected: sanitized resource IDs required here; no secret output.

## Scope

- Render/validate Vault, policies, Kubernetes auth, and ExternalSecret boundaries.
- Start only Vault, initialize it through the external recovery sink, configure and negatively test policies, revoke initial root authority.
- Prefetch three immutable model revisions into the generation-pinned GCS model cache.
- Produce redacted machine evidence; Topic 30 owns the final contextual `vault_status.png` after recovery.
- Suspend safely after durable evidence.

## Non-Goals

- No supporting platform/application install beyond Vault and the prefetch Job.
- No model serving, agent, Jenkins workload, public ingress, benchmark, or rubric-finalization claim.
- No recovery exercise; Topic 30 owns recovery.

## Exact File Map

| Role | Exact path |
|---|---|
| Read | `infra/security/vault/config.hcl` |
| Read | `infra/security/vault/policies/retrieval.hcl`, `infra/security/vault/policies/drift.hcl`, `infra/security/vault/policies/coordinator.hcl` |
| Read | `infra/security/vault/policies/agentgateway.hcl`, `infra/security/vault/policies/jenkins.hcl` |
| Read | `infra/security/vault/kubernetes-auth.yaml` |
| Read | `infra/security/external-secrets/cluster-secret-store.yaml`, `infra/security/external-secrets/chat-basic-auth.yaml`, `infra/security/external-secrets/jenkins-controller.yaml` |
| Read | `infra/security/external-secrets/kagent-gateway-keys.yaml`, `infra/security/external-secrets/facade-gateway-key.yaml`, `infra/security/external-secrets/postgres.yaml` |
| Read | `infra/security/external-secrets/clickhouse.yaml`, `infra/security/external-secrets/valkey.yaml`, `infra/security/external-secrets/redpanda.yaml` |
| Read | `infra/security/external-secrets/airflow.yaml`, `infra/security/external-secrets/datahub.yaml`, `infra/security/external-secrets/langfuse.yaml` |
| Read | `infra/security/external-secrets/agentregistry.yaml`, `infra/security/external-secrets/grafana.yaml` |
| Read | `infra/helm/edai2/values/vault.yaml`, `infra/helm/edai2/values/external-secrets.yaml` |
| Read | `configs/llm/models.yaml`, `configs/gke/profiles.yaml`, `configs/gke/cost_envelope.yaml` |
| Execute | `scripts/gke/manage_profile.py`, `scripts/gke/check_budget.py`, `scripts/gke/configure_vault.py`, `scripts/gke/prefetch_models.py` |
| Read external/untracked | `tmp/edai2-gcp/kubeconfig` |
| Generate immutable gate evidence | `evidence/04_2_llm_design/gke/gcp_preflight_topic23.json`, `evidence/04_2_llm_design/gke/cost_forecast_topic23.json` |
| Update append-only | `evidence/04_2_llm_design/gke/usage_ledger.json` |
| Generate | `evidence/04_2_llm_design/security/vault_bootstrap.json` |
| Generate | `evidence/04_2_llm_design/gke/model_cache.json` |
| External only | `EDAI2_VAULT_RECOVERY_SINK`, `EDAI2_MODEL_CACHE_GCS_URI` |
| External/non-secret attestation | `tmp/edai2-gcp/recovery-sink-attestation.json` |

## Interfaces, Data Flow, and Failure Modes

External encrypted sink + Terraform KMS/Vault resources -> private Vault pod -> initialization stream -> Kubernetes auth/policies/KV key-name setup -> initial-root revocation -> redacted evidence.

Pinned model config -> Workload-Identity prefetch Job -> deterministic archives/internal inventory -> create-only GCS blobs -> create-only JCS manifest -> read-back by object generation -> `model_cache.json`.

Failure modes:

- Recovery sink resolves to stdout, workspace, local temp, or unencrypted target: refuse initialization.
- Vault already initialized with an unrecognized fingerprint: stop; never reinitialize.
- Policy cross-path read succeeds: revoke affected auth role, mark the supporting `Sheet3!E58` prerequisite failed, suspend.
- Model object exists with mismatched bytes/generation: stop; never overwrite.
- Cache exceeds cap or revision is mutable: fail before consumer readiness.
- Evidence sanitizer sees secret-like content: quarantine output outside evidence, revoke exposed credential through operator procedure, and stop.

## Ordered Test-First Execution Tasks

### Task 1: Prove static secret and cache invariants

- [ ] Run `rtk uv run pytest tests/unit/test_edai2_security_static.py tests/integration/llm/test_gke_agents.py -q`.
  - Expected: exit 0; Raft/KMS, no JSON keys, exact KV projections, cross-path denials, existingSecret use, cache generations, size cap, and no-Hub-fallback are enforced.
- [ ] Run `rtk helm --kubeconfig $env:EDAI2_GKE_KUBECONFIG --kube-context $env:EDAI2_GKE_CONTEXT lint infra/helm/edai2/service-agent`.
  - Expected: exit 0 with no secret literal.
- [ ] Run `rtk uv run python scripts/gke/manage_profile.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT core --ttl 2h --stage vault --dry-run`.
  - Expected: only Vault/KMS/required namespace resources render; capacity fits and no public service appears.

### Task 2: Re-run the live gate and acquire bounded runtime

- [ ] Run `rtk uv run python scripts/gke/check_budget.py --project $env:GOOGLE_CLOUD_PROJECT --billing-account-env GOOGLE_BILLING_ACCOUNT --budget-notification-target-env EDAI2_BUDGET_NOTIFICATION_TARGET --recovery-sink-env EDAI2_VAULT_RECOVERY_SINK --recovery-sink-attestation $env:EDAI2_RECOVERY_SINK_ATTESTATION --required-permissions configs/gke/required_permissions.json --dns-probes acme-staging-v02.api.letsencrypt.org,huggingface.co,storage.googleapis.com --live-external-preflight --preflight-output evidence/04_2_llm_design/gke/gcp_preflight_topic23.json --trial-expires-at $env:EDAI2_TRIAL_EXPIRES_AT --current-spend-usd $env:EDAI2_CURRENT_SPEND_USD --spend-observed-at $env:EDAI2_SPEND_OBSERVED_AT --usage-ledger evidence/04_2_llm_design/gke/usage_ledger.json --envelope configs/gke/cost_envelope.yaml --requested-profile core --requested-ttl 2h --output evidence/04_2_llm_design/gke/cost_forecast_topic23.json`.
  - Expected: exit 0; live project/billing/IAM/notification/recovery-sink/DNS/trial/spend/cap checks pass and only redacted hashes/booleans are emitted.
- [ ] Run `rtk uv run python scripts/gke/manage_profile.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT core --ttl 2h --stage vault --acquire-session-lease --owner topic23-bootstrap --commit-sha $env:EDAI2_COMMIT_SHA`.
  - Expected: sole lease recorded, one platform node at most, Vault Ready privately, ingress disabled.

### Task 3: Initialize/configure Vault without local recovery material

- [ ] Run `rtk powershell.exe -NoProfile -Command '$a=Get-Content -Raw -LiteralPath $env:EDAI2_RECOVERY_SINK_ATTESTATION | ConvertFrom-Json; $sinkHash=[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($env:EDAI2_VAULT_RECOVERY_SINK))).ToLowerInvariant(); if (-not $a.approved -or -not $a.encrypted -or -not $a.outside_workspace -or [int]$a.custodian_count -lt 2 -or $a.sink_uri_sha256 -ne $sinkHash) { exit 24 }; "RECOVERY_SINK_GATE=PASS"'`.
  - Expected: exit 0 and only `RECOVERY_SINK_GATE=PASS`; no sink URI, token, share, principal, or billing identifier is emitted. Missing/malformed/mismatched attestation is a hard safe stop.
- [ ] Run `rtk uv run python scripts/gke/configure_vault.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --namespace vault --kms-key-from-terraform --recovery-sink $env:EDAI2_VAULT_RECOVERY_SINK --kubernetes-auth --policies infra/security/vault/policies --redacted-output evidence/04_2_llm_design/security/vault_bootstrap.json`.
  - Expected: initialization material streams only to the external sink; key names are populated, positive/negative policy probes pass, initial root token is revoked, in-memory buffers are cleared, and redacted evidence contains no payload.
- [ ] Run `rtk kubectl --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT -n vault exec vault-0 -- vault status -format=json`.
  - Expected: initialized, unsealed by KMS, active Raft node; sanitize output before persistence.
- [ ] Run `rtk uv run pytest tests/unit/test_edai2_security_static.py -q`.
  - Expected: exit 0 after generated evidence exists.

### Task 4: Verify redacted bootstrap evidence

- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --verify-vault-bootstrap evidence/04_2_llm_design/security/vault_bootstrap.json --strict`.
  - Expected: KMS/Raft/auth identifiers, key-name fingerprints, policy results, root revocation, and zero secret/recovery payload pass. No screenshot is created in this topic.

### Task 5: Build and read back immutable model cache

- [ ] Run `rtk powershell.exe -NoProfile -Command 'if (-not $env:EDAI2_MODEL_CACHE_GCS_URI) { exit 25 }'`.
  - Expected: exit 0.
- [ ] Run `rtk uv run python scripts/gke/prefetch_models.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --config configs/llm/models.yaml --gcs-uri $env:EDAI2_MODEL_CACHE_GCS_URI --if-generation-match-zero --submit-gke-job --output evidence/04_2_llm_design/gke/model_cache.json`.
  - Expected: exactly three pinned revisions, three content-addressed blobs, one JCS manifest, per-object generations and internal hashes, <=5Gi, Workload Identity only, and successful generation-specific read-back.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --verify-model-cache evidence/04_2_llm_design/gke/model_cache.json --strict`.
  - Expected: exit 0; URI/generation/hash inventory is internally consistent and contains no credential.

## Evidence and Screenshot Ownership

| Artifact | Owner | Proves | Does not prove |
|---|---|---|---|
| `security/vault_bootstrap.json` | Topic 23 | KMS/Raft/auth/policies/key-name setup/root revocation | later recovery |
| `gke/model_cache.json` | Topic 23 | immutable model objects and generations | llm-d serving |
Topic 30 owns recovery evidence and the single final `vault_status.png`; Topic 23 owns no screenshot.

## Cleanup and Runtime Release

- [ ] Run `rtk uv run python scripts/gke/manage_profile.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT suspended --release-session-lease --owner topic23-bootstrap --require-evidence-manifest evidence/04_2_llm_design/security/vault_bootstrap.json`.
  - Expected: lease released, node pools zero, ingress disabled; Vault/model-cache persistent state remains.
- Confirm no prefetch Job/pod remains and no local archive/model/recovery material exists.
- Do not delete GCS objects, KMS resources, Raft PVC, or Terraform state.
- [ ] Run and record `rtk git status --short --branch` as the final acceptance command.

## Rubric Traceability

| Cell | Points | Topic 23 contribution | Satisfaction owner |
|---|---:|---|---|
| `Sheet3!E3:E5` | 6 | immutable cache and secure platform prerequisites | Topics 24/28 |
| `Sheet3!E58` | 1 | centralized Vault implementation prerequisite | Topic 30 |
| `Sheet3!E49` | 1 source / 0 earned | VM/Ansible prohibited | Topic 32 |

## Definition of Done

- [ ] Source hashes, predecessor, budget, explicit context, and external sink/URI passed.
- [ ] Static tests and dry-run passed before live mutation.
- [ ] Vault is initialized once, KMS-unsealed, policy-separated, and initial root authority revoked.
- [ ] Redacted evidence contains no secret/recovery material.
- [ ] Three immutable model revisions and JCS manifest pass generation/hash read-back and size caps.
- [ ] Runtime is suspended, lease released, no public forwarding rule exists, and Topic 24 receives exact hashes/limitations.
- [ ] Final `rtk git status --short --branch` is recorded.

## Completion Record

- **Status:** Not started; no Vault/model-cache success claimed.
- **Branch / revision:** Record exact `rtk git status --short --branch`; none recorded.
- **Affected files:** None at plan-authoring time.
- **Command / exit-code log:** No execution commands recorded.
- **Evidence / SHA-256 log:** No bootstrap/cache evidence recorded.
- **Screenshot QA:** No screenshot owned; Topic 30 will capture final recovery-aware `vault_status.png`.
- **Cleanup / runtime release:** No lease held by this plan artifact.
- **Limitations:** Recovery is intentionally untested until Topic 30.
- **Handoff:** Topic 24 remains blocked until redacted bootstrap/cache hashes, explicit context, suspended state, and zero-secret scan are recorded.
