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
| Prerequisites | Topic 22 Partial (Option-A) accepted, exact Terraform outputs, explicit `edai2-gke` context. Zero operator inputs: every value resolves from the bundle or live outputs. |
| Blocked successors | Topics 24-31 |
| Runtime owner | `topic23-bootstrap`, `core`, maximum 2h |
| Execution class | `GCP-write/security-sensitive` |
| Branch rule | Same branch/revision lineage; serial after Topic 22 |

## Global Constraints

- Read and obey `C:\Users\oou1hc\.codex\RTK.md`; prefix every shell command with `rtk`.
- Revalidate fixed hashes before execution: Section 03 `2b70794867c5d70441cb6848df547e1fbf8e462d7af68a0b9527b6ee18cb7643`; EDAI2 `d8ca5b11c577c888b34a2518e3ce5bc424d27201f75a10c6d4d4ed79787b7dfa`; rubric at `tmp/rubic-check/Coursework Tracking (Public).xlsx` `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- Prefix shell commands with `rtk`; do not create/switch branches/worktrees, stage, or commit.
- Consume the completed local implementation. If a source/IaC/chart defect appears, capture it, release or suspend any owned runtime, mark this topic `Partial`, and return it to the owning local topic; do not patch implementation during a live cloud lease.
- Require the exact Topic 22 project, zone `us-central1-a`, cluster `edai2`, and kube context `edai2-gke` (live `tmp/edai2-gcp/kube-target.json` truth; never the default context).
- Require kubeconfig `tmp/edai2-gcp/kubeconfig` and context `edai2-gke`. Every `kubectl` call includes `--kubeconfig tmp/edai2-gcp/kubeconfig --context edai2-gke`; every Helm call includes `--kubeconfig tmp/edai2-gcp/kubeconfig --kube-context edai2-gke`; every script that queries or mutates Kubernetes receives both values. Never use or change the default kubeconfig/current context.
- Run a fresh bundle-form `check_budget.py --live-external-preflight` gate (via `--operator-inputs tmp/edai2-gcp/operator-inputs.json`, VND-only, personal-study) before entering `core`. Missing project, billing linkage, required IAM permission, trial expiry, spend, DNS/HTTPS egress, or other external input is a safe stop. No operator-supplied values exist in this topic: the model-cache URI and KMS key id resolve live from Terraform outputs via `--print-model-cache-uri` / `--print-kms-key-id` (identifier-class only).
- `EDAI2_TFVARS_PATH` is absolute, resolves exactly to `tmp/edai2-gcp/coursework.auto.tfvars`, and remains untracked.
- Study-only recovery: a single recovery key (shares=1/threshold=1) is held in process memory during configuration, then stored as the Kubernetes Secret `vault/vault-recovery` (value never in stdout/logs/Git/evidence/temp). No sink path, no attestation file, no custodians; `recovery_control: not_applicable_personal_study`. Disaster recovery outside the cluster is impossible by design; evidence records `recovery_material: in-cluster-only` and `disaster_safe: false`. Never write a root token, recovery key, unseal value, secret payload, or Vault snapshot into Git/evidence/temp files, stdout, or the workspace.
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
- Option-A exception (E48 deferred): Topic 23 may start on Topic 22 `Partial` (WI 4/4 live, 0/0 nodes, kube `edai2-gke` verified). It must NOT assume `evidence/04_2_llm_design/gke/terraform_apply.json` exists; consume live `terraform output`/REST readbacks + recorded hashes instead, and carry "E48 pending operator PNG + machine link" as a limitation. Starting Topic 23 does not mark E48 `Satisfied`.
4. `rtk kubectl --kubeconfig tmp/edai2-gcp/kubeconfig --context edai2-gke cluster-info`
   - Expected: the dedicated kubeconfig resolves the approved GKE API; any mismatch stops execution without falling back to a default context.
5. `rtk terraform -chdir=infra/terraform/edai2 output -json`
   - Expected: sanitized resource IDs required here; no secret output.

## Scope

- Render/validate Vault, policies, Kubernetes auth, and ExternalSecret boundaries.
- Start only Vault, initialize it with an in-cluster recovery key, configure and negatively test policies, revoke initial root authority.
- Prefetch three immutable model revisions into the generation-pinned GCS model cache.
- Produce redacted machine evidence; Topic 30 owns the final contextual `vault_status.png` after recovery.
- Suspend safely after durable evidence.

## Non-Goals

- No supporting platform/application install beyond Vault and the prefetch Job.
- No model serving, agent, Jenkins workload, public ingress, benchmark, or rubric-finalization claim.
- No recovery exercise; Topic 30 owns recovery.

## Standing Authorization and the One Pending Approval

- Standing authorization (operator-approved, scope-locked to this file): Vault install + init/configure + prefetch Job + verifiers + suspend, profile `core` max 2h, spend stops (forecast >USD 180 or spend ≥75% aborts; suspend at 90/100%), stop-and-report on any failure, no autonomous retry beyond one transient-only retry, no destroy, no activation. No mid-run check-ins; gates stop the run instead of asking.
- One pending approval gate: the Vault KMS identity is a pre-existing IaC gap (no pod-usable KMS decrypter exists live; `04.2` Task 7/8 require KMS auto-unseal). The prepared addition is exactly 3 resources, $0: `google_service_account.vault` (`edai2-vault`), its `vault/vault` Workload Identity binding, and its `roles/cloudkms.cryptoKeyDecrypter` grant (all inside `infra/terraform/modules/iam`, `fmt`/`validate` green). Scope proof is a counts-only plan inspection (exactly 3 creates of those addresses, everything else no-op, no forbidden types/values); the Topic-22 sanitizer structurally accepts only all-create plans and is not used here. The cloud phase MUST stop before apply until that inspection passes and the operator approves the bound plan hash. The full plan additionally carries the pre-existing platform `node_count` 1→0 correction (zero-capacity design); Vault work re-scales to 1 node after apply and suspends to 0/0 at the end. No other cloud write is gated.

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
| Derive live (identifier-class, never persisted) | model-cache GCS URI via `--print-model-cache-uri`, KMS key id via `--print-kms-key-id` |

## Interfaces, Data Flow, and Failure Modes

Terraform KMS/Vault resources -> private Vault pod -> in-memory initialization (single recovery key to `vault/vault-recovery` Secret) -> Kubernetes auth/policies/KV key-name setup -> initial-root revocation -> redacted evidence.

Pinned model config -> Workload-Identity prefetch Job -> deterministic archives/internal inventory -> create-only GCS blobs -> create-only JCS manifest -> read-back by object generation -> `model_cache.json`.

Failure modes:

- An existing `vault/vault-recovery` Secret is found: refuse initialization; stop; never reinitialize.
- Vault already initialized with an unrecognized fingerprint: stop; never reinitialize.
- Policy cross-path read succeeds: revoke affected auth role, mark the supporting `Sheet3!E58` prerequisite failed, suspend.
- Model object exists with mismatched bytes/generation: stop; never overwrite.
- Cache exceeds cap or revision is mutable: fail before consumer readiness.
- Evidence sanitizer sees secret-like content: quarantine output outside evidence, revoke exposed credential through operator procedure, and stop.

## Ordered Test-First Execution Tasks

### Task 1: Prove static secret and cache invariants

- [ ] Run `rtk uv run pytest tests/unit/test_edai2_security_static.py tests/integration/llm/test_gke_agents.py -q`.
  - Expected: exit 0; Raft/KMS, no JSON keys, exact KV projections, cross-path denials, existingSecret use, cache generations, size cap, and no-Hub-fallback are enforced.
- [ ] Run `rtk helm --kubeconfig tmp/edai2-gcp/kubeconfig --kube-context edai2-gke lint infra/helm/edai2/service-agent`.
  - Expected: exit 0 with no secret literal.
- [ ] Run `rtk uv run python scripts/gke/manage_profile.py --kubeconfig tmp/edai2-gcp/kubeconfig --context edai2-gke core --ttl 2h --stage vault --dry-run`.
  - Expected: only Vault/KMS/required namespace resources render; capacity fits and no public service appears.

### Task 2: Re-run the live gate and acquire bounded runtime

- [ ] Run `rtk uv run python scripts/gke/check_budget.py --operator-inputs tmp/edai2-gcp/operator-inputs.json --required-permissions configs/gke/required_permissions.json --live-external-preflight --preflight-output evidence/04_2_llm_design/gke/gcp_preflight_topic23.json --usage-ledger evidence/04_2_llm_design/gke/usage_ledger.json --envelope configs/gke/cost_envelope.yaml --requested-profile core --requested-ttl 2h --output evidence/04_2_llm_design/gke/cost_forecast_topic23.json`.
  - Expected: exit 0; live project/billing/IAM/notification/DNS/trial/spend/cap checks pass (personal-study: recovery attestation not applicable) and only redacted hashes/booleans are emitted.
- [ ] Run `rtk uv run python scripts/gke/manage_profile.py --kubeconfig tmp/edai2-gcp/kubeconfig --context edai2-gke core --ttl 2h --stage vault --acquire-session-lease --owner topic23-bootstrap --commit-sha $env:EDAI2_COMMIT_SHA`.
  - Expected: sole lease recorded, one platform node at most, Vault Ready privately, ingress disabled.

### Task 3: Initialize/configure Vault with in-cluster recovery key

- [ ] Run `rtk uv run python scripts/gke/configure_vault.py --kubeconfig tmp/edai2-gcp/kubeconfig --context edai2-gke --namespace vault --kms-key-id "$(rtk uv run python scripts/gke/check_budget.py --operator-inputs tmp/edai2-gcp/operator-inputs.json --print-kms-key-id)" --kubernetes-auth --policies infra/security/vault/policies --redacted-output evidence/04_2_llm_design/security/vault_bootstrap.json`.
  - Expected: initialization uses a single recovery key (shares=1/threshold=1) held in memory then stored as Secret `vault/vault-recovery`; key names are populated, positive/negative policy probes pass, initial root token is revoked, in-memory buffers are cleared, and redacted evidence contains no payload and no custodian/attestation fields. An existing recovery Secret stops the run (exit 3).
- [ ] Run `rtk kubectl --kubeconfig tmp/edai2-gcp/kubeconfig --context edai2-gke -n vault exec vault-0 -- vault status -format=json`.
  - Expected: initialized, unsealed by KMS, active Raft node; sanitize output before persistence.
- [ ] Run `rtk uv run pytest tests/unit/test_edai2_security_static.py -q`.
  - Expected: exit 0 after generated evidence exists.

### Task 4: Verify redacted bootstrap evidence

- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --verify-vault-bootstrap evidence/04_2_llm_design/security/vault_bootstrap.json --strict`.
  - Expected: KMS/Raft/auth identifiers, key-name fingerprints, policy results, root revocation, and zero secret/recovery payload pass. No screenshot is created in this topic.

### Task 5: Build and read back immutable model cache

- [ ] Run `rtk uv run python scripts/gke/prefetch_models.py --kubeconfig tmp/edai2-gcp/kubeconfig --context edai2-gke --config configs/llm/models.yaml --gcs-uri "$(rtk uv run python scripts/gke/check_budget.py --operator-inputs tmp/edai2-gcp/operator-inputs.json --print-model-cache-uri)" --if-generation-match-zero --submit-gke-job --output evidence/04_2_llm_design/gke/model_cache.json`.
  - Expected: exactly three pinned revisions, three content-addressed blobs, one canonical manifest, per-object generations and internal hashes, <=5Gi, Workload Identity only, and successful generation-specific read-back.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --verify-model-cache evidence/04_2_llm_design/gke/model_cache.json --strict`.
  - Expected: exit 0; URI/generation/hash inventory is internally consistent and contains no credential.

## Evidence and Screenshot Ownership

| Artifact | Owner | Proves | Does not prove |
|---|---|---|---|
| `security/vault_bootstrap.json` | Topic 23 | KMS/Raft/auth/policies/key-name setup/root revocation | later recovery |
| `gke/model_cache.json` | Topic 23 | immutable model objects and generations | llm-d serving |
Topic 30 owns recovery evidence and the single final `vault_status.png`; Topic 23 owns no screenshot.

## Cleanup and Runtime Release

- [ ] Run `rtk uv run python scripts/gke/manage_profile.py --kubeconfig tmp/edai2-gcp/kubeconfig --context edai2-gke suspended --release-session-lease --owner topic23-bootstrap --require-evidence-manifest evidence/04_2_llm_design/security/vault_bootstrap.json`.
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

- [ ] Source hashes, predecessor, budget, explicit context passed; every remaining input auto-resolved (no operator values).
- [ ] Static tests and dry-run passed before live mutation.
- [ ] Vault is initialized once, KMS-unsealed, policy-separated, and initial root authority revoked.
- [ ] Redacted evidence contains no secret/recovery material.
- [ ] Three immutable model revisions and JCS manifest pass generation/hash read-back and size caps.
- [ ] Runtime is suspended, lease released, no public forwarding rule exists, and Topic 24 receives exact hashes/limitations.
- [ ] Final `rtk git status --short --branch` is recorded.

## Completion Record

- **Status:** Complete — mint-from-live, model_cache.json minted+verified, no Job/lease/scale.
- **Finalize run 2026-10-07 ~16:2x-17:0x UTC (all via `rtk`, HEAD `b86297e2234d1f66e14212521f99f535e21e0da1` unmoved):** Vault DONE untouched (no configure_vault.py); no Job submitted, no scale, no lease acquired; model_cache.json minted from live GCS truth then strict-verified. Spend ₫741000 `spend_observed_at 2026-10-07T11:45:39.523781Z` fresh (age ~4.7h). Pins primary `989aa7980e4cf806f80c7fef2b1adb7bc71aa306` / comparison `7ae557604adf67be50417f59c2c2f167def9a775` / embedding `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`; generations 1791335619032151/1791335643570911/1791335653109106; sizes 2419850347/773408269/234759753 total 3428018369; sha256 `bb3fd27e…`/`ea1b73fe…`/`bf09707a…`; manifest_sha256 `9876ddc5…` (`9876ddc56b98e1df20888e29986ea7eabbbc3a81764421283b461883f8a77d57`); file SHA `67609f908cf96cfb28d0910411a55dc8cb0670766dd17feb2405cb951ebf2dba`; `--verify-model-cache --strict` exit 0 `{"verified":"model_cache.json"}`; `pytest tests/unit/test_topic23_scripts.py -q` 33 passed.
- **Evidence / SHA-256 log:** `gke/model_cache.json` (`67609f90…`, verified strict exit 0), manifest `9876ddc5…`. GCS live truth unchanged: primary 2419850347B gen1791335619032151 sha `bb3fd27eedd21aa689191b721df4b443bdfac40b0e50c667319b6173f8ac0afa`, comparison 773408269B gen1791335643570911 sha `ea1b73feff5bbef7fc6f9e750b218818a876e165bc91686e58002ae693ff83d3`, embedding 234759753B gen1791335653109106 sha `bf09707aaa2acf416dec6542334ac047ed0a51a6846cb4509539fa90d6c0a6c8`. Failed Job retained for forensics.
- **Cleanup / runtime release:** vault sts `0` (0 replicas), no lease (`tmp/edai2-gcp/topic23-lease.json` absent `lease=False`), blobs+Failed Job retained (no delete), temp `Temp\opencode\*.tar.zst` clean `[]`, 1 spot node `gke-edai2-spot-fdbbeaa5-fsmc Ready` recorded, no stage/commit/push.
- **Limitations:** (1) Failed Job retained for forensics. (2) 1 spot node Ready at handoff (`gke-edai2-spot-fdbbeaa5-fsmc Ready 3h36m v1.35.8-gke.1380001`). (3) Proofs 900s expiry, spend ₫741000 observed 11:45:39Z. (4) Uncommitted helper+test+evidence (model_cache.json untracked + plan file M).
- **Handoff:** Topic 24 receives exact hashes `bb3fd27e…`/`ea1b73fe…`/`bf09707a…` + generations 1791335619032151/1791335643570911/1791335653109106 + manifest `9876ddc5…` + file SHA `67609f90…`; zero-secret scan passed; vault 0, no lease.
- **Branch / revision:** `feature/implement-edai2` at `b86297e` (HEAD unmoved). Working tree M+?? only, nothing staged/committed/pushed.

- **Status:** Partial — STOP on 412 + bytes-mismatch per stop rules. Cache blobs preserved, Failed Job retained, nothing deleted, nothing fabricated.
- **Continue run 2026-10-07 ~11:45-12:1x UTC (all via `rtk`, HEAD `b86297e2234d1f66e14212521f99f535e21e0da1` unmoved):** operator fresh screenshot Cost ₫741K-Savings ₫741K=Total ₫0 Oct1-7, remaining ₫7,392,978 of ₫7,889,850, 18 days to 2026-10-25. Both ignored bundles refreshed to console/current ₫741000 `spend_observed_at 2026-10-07T11:45:39.523781Z`; backend `initialized` proof refreshed `ok:true` observed 11:46:07Z SHA `88d78aa7…`; Task-2 preflight+forecast regenerated `ok:true` spend $28.18 forecast $0 SHAs `9c46b2a5…`/`a24aea27…`. Lease acquired/released cleanly. Platform 1+spot 1 + vault-0 1/1 Running restored. Phase-A local TDD fix (no lease): added `_adoption_identical` top-dir-strip helper + `test_worker_adopts_identical_trees_after_topdir_strip`, 32 passed, static 11 passed, helm lint 0 failed, dry-run core/vault fits. Old Failed Job (11:23:44Z) recorded then deleted (logs to `Temp\opencode\edai2-model-prefetch-failed.log`). Single rerun 11:58:32Z hit `412 PreconditionFailed` on `primary` then `RuntimeError existing object bytes mismatch` → STOPPED: no delete, no relaunch, no mint. `model_cache.json` NOT created; `--verify-model-cache` correctly errors exit 2 file absent. Forensic log `Temp\opencode\edai2-model-prefetch-412-second.log` 11283B retained with 412 + mismatch lines.
- **Evidence / SHA-256 log:** `vault_bootstrap.json` untouched, fresh preflight `9c46b2a5…`, forecast `a24aea27…`. `model_cache.json` NOT created. GCS live truth: 3 blobs unchanged primary 2419850347B gen1791335619032151, comparison 773408269B gen1791335643570911, embedding 234759753B gen1791335653109106; Failed Job `edai2-model-prefetch-pvdsc` Failed 0/1 retained.
- **Cleanup / runtime release:** vault sts→0 0/0, platform resize-to-0 op in-flight + spot resize-to-0 accepted (spot Ready SchedulingDisabled draining at handoff, converges server-side), lease released vs `vault_bootstrap.json`, blobs+Job retained per 412 rule, no stage/commit/push.
- **Limitations:** (1) Adoption still mismatches despite top-dir fix — fresh snapshot bytes differ from existing blobs, needs owning-topic content diff (compare unpacked file lists/hashes, check snapshot_download determinism); E3-E5 unsatisfied, E58 Partial till Topic30. (2) 1 spot node draining at handoff. (3) Proofs 900s expiry, spend now ₫741000 observed 11:45:39Z — next burst needs fresh if >24h. (4) Local changes uncommitted: `prefetch_models.py` (`_adoption_identical`), `test_topic23_scripts.py` (+1 test) — owning topic must review/keep.
- **Handoff:** Do NOT purge blobs; do NOT delete Failed Job until logs archived. To finish: diff fresh vs existing payloads to find divergent files, fix adoption or re-pin, then single rerun → verify → suspend → Topic24.
- **Branch / revision:** `feature/implement-edai2...origin/feature/implement-edai2 [ahead 1]` at `b86297e`, working tree M+?? only, nothing staged/committed/pushed.

- **Status:** Partial — STOP on 412 + bytes-mismatch per stop rules. Cache blobs preserved, Failed Job retained, nothing deleted, nothing fabricated.
- **Continue run 2026-10-07 ~11:13–11:2x UTC (all via `rtk`, HEAD `b86297e2234d1f66e14212521f99f535e21e0da1` unmoved):** operator supplied fresh billing screenshot (Cost ₫739K − Savings ₫739K = Total ₫0; remaining ₫7,393,089 of ₫7,889,850; 18 days to 2026-10-25). Both ignored bundles refreshed to `console/current ₫739000`, `spend_observed_at 2026-10-07T11:13:23Z`; backend `initialized` proof refreshed `ok:true`; Task-2 preflight+forecast regenerated `ok:true` (spend $28.10, forecast $0, new SHAs `f67c45c2…`/`27e4f8cf…`). Lease acquired/released cleanly. Prefix held the 3 good blobs (no purge). Platform 1 node + vault-0 1/1 Running restored. Phase-A local fix (no lease held): `prefetch_models._run` now resolves binaries via `shutil.which` (2 new TDD tests; `31 passed`); real `kubectl.EXE`/`gcloud.CMD` resolve. Retained Complete Job recorded then deleted (single launch, never concurrent). Rerun hit `412 PreconditionFailed` on `primary` (expected — blobs exist) then worker raised `RuntimeError: existing object bytes mismatch for primary` → per stop rules STOPPED: no delete, no relaunch, no evidence minting. Forensic note: the adoption comparator (`dir_manifest(refit) != dir_manifest(work)`) compares an extracted nested `<old-random-dir>/…` tree against a flat fresh tree, so it can never match — the adoption path as coded always stops here; owning local topic must redesign the comparison (e.g. compare archive payload roots, strip top-level dir, or compare per-file content keyed by relative path inside the snapshot). `model_cache.json` NOT created; `--verify-model-cache` correctly errors (file absent).
- **Evidence / SHA-256 log:** `security/vault_bootstrap.json` (`9186fbac…`, untouched), fresh `gke/gcp_preflight_topic23.json` (`f67c45c2…`, ok:true), fresh `gke/cost_forecast_topic23.json` (`27e4f8cf…`, ok:true). `gke/model_cache.json` NOT created. GCS live truth (not evidence): the 3 prior blobs unchanged; Failed Job `edai2-model-prefetch` (`Failed 0/1`, `primary` 412+mismatch) retained with pod logs.
- **Cleanup / runtime release:** vault sts→0 (PVC `data-vault-0` Bound + `vault-recovery` Secret persist); both pools async resize-to-0 accepted (`rc:0` each; nodes `SchedulingDisabled`/draining at handoff, converging server-side); lease released against `vault_bootstrap.json`; blobs + Failed Job retained per 412 rule; `./gcloud/` SDK debris removed earlier; no stage/commit/push.
- **Limitations:** (1) Adoption-path defect above blocks E3-E5; E58 stays `Partial` until Topic 30. (2) 1 spot node was still `Ready` plus draining nodes at handoff — server-side async drain converges after lease release; next burst must verify 0 nodes at gates. (3) Proofs expire every 900s; spend now ₫739000 observed 11:13:23Z — next burst needs fresh observation if >24h. (4) Local source changes this session (uncommitted, same branch): `prefetch_models.py` (`shutil`+`_resolve_binary`+`_run`), `test_topic23_scripts.py` (+2 tests) — owning local topic must review/keep them.
- **Handoff:** Do NOT purge blobs; do NOT delete the Failed Job until its logs are archived. To finish: owning topic fixes the adoption comparator + adds a test proving adopt-identical-trees passes (e.g. build two archives from the same snapshot dir and assert adopt), then single rerun (adoption should then succeed) → verify → suspend → Topic 24.

- **Status:** Partial — Vault DONE (untouched this run); model cache GOOD in GCS but `model_cache.json` NOT minted due to a Windows source defect. No 412, no mismatch, no fabrication.
- **Resume run 2026-10-07 (all via `rtk`, HEAD `b86297e2234d1f66e14212521f99f535e21e0da1` unmoved):** gates green (3 locked hashes exact; `cluster-info` ok; backend `initialized` proof refreshed `ok:true`; Task-2 preflight+forecast `ok:true`, spend $21.60, forecast $0); lease `topic23-bootstrap` acquired/released cleanly; prefix confirmed empty (`One or more URLs matched no objects`); platform pool resized 0→1 (`rc:0`), `vault-0` 0→1/1 Running; stale failed Job from 2026-10-06 deleted after recording status (0/1 Failed) to allow single fresh launch (never concurrent); fresh `prefetch_models.py --ksa edai2-retrieval-agent` Job `Complete 1/1 in 115s`, worker manifest 3/3 fresh (`adopted:false`, no 412): primary `2419850347B gen 1791335619032151`, comparison `773408269B gen 1791335643570911`, embedding `234759753B gen 1791335653109106`, total `3428018369B` (≈3.19GiB ≤5Gi); live `gcloud storage objects describe` confirms all 3 generations+sizes match; `gcloud storage ls` lists exactly the 3 `.tar.zst` blobs. Script then crashed at `prefetch_models.py:234 _run("gcloud",...)` with `FileNotFoundError: [WinError 2]` (Windows resolves `gcloud.cmd`, not `gcloud`; `rtk gcloud` works, plain `subprocess gcloud` does not). Per live-lease rule the source was NOT patched. `--verify-model-cache` correctly errors (file absent); verifier NOT bypassed.
- **Evidence / SHA-256 log (unchanged files):** `security/vault_bootstrap.json` (`9186fbac…`, verified, untouched), `gke/gcp_preflight_topic23.json` (`41c6a9f0…`, ok:true), `gke/cost_forecast_topic23.json` (`8d591db5…`, ok:true). `gke/model_cache.json` NOT created. GCS live truth (not evidence): 3 blobs above with matching generations; Complete Job `edai2-model-prefetch` retained for forensics with logs manifest.
- **Cleanup / runtime release:** vault sts→0 (pod Terminating→gone; PVC `data-vault-0` Bound 10Gi + Secret `vault-recovery` persist); both pools async resize-to-0 accepted (`rc:0` each; 1 spot node `SchedulingDisabled` draining at handoff, server-side converges to 0/0); lease released against `vault_bootstrap.json`; GCS cache objects + Complete Job retained (no delete on non-412 path); no stage/commit/push.
- **Limitations:** (1) Prior "concurrent writer" theory CLOSED: operator confirms NO foreign writer; prior objects were own crashed-run debris (purged; prefix was empty at start). (2) NEW BLOCKER — owning-local-topic defect: `scripts/gke/prefetch_models.py:173-177,234` invokes bare `gcloud` (and `kubectl`) via `subprocess` without Windows `.cmd` resolution; on Windows the post-Job `describe` step crashes after a successful upload, so evidence is never minted. Fix belongs locally (e.g. `shutil.which`/`gcloud.cmd` shim or PATH handling + test), NOT during a lease. (3) E3-E5 still unsatisfied (no `model_cache.json`); E58 stays `Partial` until Topic 30; lease is a local file (serial only); proofs expire every 900s.
- **Handoff:** Cache blobs are GOOD — do NOT purge. To finish: apply owning-topic Windows fix, then EITHER (a) manually mint `model_cache.json` from retained Job logs + live describes using `manifest_entry`/`canonical` helpers (same values as above) only if the owning topic authorizes out-of-band minting, OR (b) delete the retained Complete Job and rerun `prefetch_models.py` once (adoption path will adopt the 3 existing blobs after byte-compare, then mint + verify + suspend). Then `--verify-model-cache --strict`, suspend (vault→0, pools 0/0), hand Topic 24 redacted hashes + zero-secret scan.
- **Branch / revision:** `feature/implement-edai2...origin/feature/implement-edai2 [ahead 1]` at `b86297e` (HEAD unmoved). Working tree holds only intended unstaged edits + new files. Nothing staged, committed, pushed, or PR'd.
- **Branch / revision:** `feature/implement-edai2...origin/feature/implement-edai2 [ahead 1]` at `b86297e` (HEAD unmoved). Working tree holds only intended unstaged edits. Nothing staged, committed, pushed, or PR'd.
- **Affected files:** This plan file; `scripts/gke/configure_vault.py` (new); `scripts/gke/prefetch_models.py` (new); `scripts/gke/manage_profile.py` (stage/lease/kube flags); `scripts/gke/check_budget.py` (URI/KMS print modes, quota env, principal fallback, post-apply proof branch); `scripts/qa/capture_edai2_evidence.py` (Topic-23 verifiers); `infra/terraform/{edai2/main.tf,modules/iam/*}` (vault GSA + WI + KMS grants, applied live); `tests/unit/test_topic23_scripts.py` (29 TDD tests); gate evidence `gke/{gcp_preflight_topic23,cost_forecast_topic23}.json`, `security/vault_bootstrap.json`; refreshed `bootstrap_forecast_topic22.json` + `usage_ledger.json`. GCS backend state mutated only by approved applies (vault IAM live, node corrections).
- **Command / exit-code log (cloud run 2026-10-06/07, all via `rtk`):** console observation bound into ignored bundles; fresh live preflight `ok:true` (43+7 perms, spend $21.60); lease acquired twice; backend proofs refreshed; plan→approval→apply executed vault IAM live; role upgraded after live denial proved decrypter insufficient; stale GCS lock from a killed apply recovered via `force-unlock`; Vault chart 0.34.1 installed (seal under `server.ha.raft.config`); `configure_vault.py` green after 3 TDD-fixed defects across 3 clean pre-configuration wipe cycles; `vault_bootstrap.json` verified, 5/5 probes, 27 keys, root revoked; pod deletion proved KMS auto-unseal. Full regression 195 passed repeatedly; stage listing byte-identical; HEAD unmoved.
- **Evidence / SHA-256 log:** `security/vault_bootstrap.json` (`9186fbac…`, verified), `gke/gcp_preflight_topic23.json` (`41c6a9f0…`, ok:true), `gke/cost_forecast_topic23.json` (`8d591db5…`, ok:true). `gke/model_cache.json` NOT created. Machine evidence authoritative.
- **Screenshot QA:** No screenshot owned, produced, or claimed; Topic 30 will capture final recovery-aware `vault_status.png`.
- **Cleanup / runtime release:** Lease released against `vault_bootstrap.json`; Vault scaled to 0 replicas (Raft PVC + `vault-recovery` Secret persist); both pools resize-to-0 accepted (async drain); failed prefetch Job retained for forensics; 3 orphaned model-cache objects removed in 2 documented purges; smoke temp files removed. Pre-existing broken-venv warning incidental to `uv run`.
- **Limitations:** (1) MODEL CACHE STOPPED: `model-cache/*.tar.zst` objects appear and disappear on a minutes timescale with no known actor — possible concurrent operator/session activity. Guard + file-level adoption check behaved correctly (no overwrite, truthful stop). E3-E5 cache prerequisite unsatisfied. (2) Custodians/sink removed (operator-approved): single in-cluster key, `disaster_safe:false`; E58 stays `Partial` until Topic 30. (3) Lease is a local file — serial topics only. (4) Proof files expire every 900s by design; every gated burst must re-verify first.
- **Handoff:** Vault complete (hashes above). To resume model cache: confirm no other writer is active, ensure prefix empty, rerun `prefetch_models.py` (adoption handles benign races; fresh 412 + mismatch stops again). Then verify, suspend (vault→0, pools 0/0, lease released), hand Topic 24 redacted hashes + zero-secret scan.
