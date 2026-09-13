# Topic 22: GCP Account, Budget, and Terraform Apply Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provision only the approved EDAI2 GCP foundation after proving account, billing, IAM, trial lifetime, live spend, forecast, and Terraform inputs are safe.

**Architecture:** Terraform owns a zonal Standard GKE cluster, two zero-capable node pools, Artifact Registry, one KMS-encrypted GCS bucket, KMS, Workload Identity/IAM, and a VND-denominated Billing Budget conservatively derived from the normalized USD 240 envelope. A private-bundle helper writes credentials only to `tmp/edai2-gcp/kubeconfig`, normalizes its context to fixed alias `edai2-gke`, and writes `tmp/edai2-gcp/kube-target.json`; every later Kubernetes call names those fixed values explicitly. No Kubernetes application is installed here.

**Tech Stack:** PowerShell, `rtk`, Python 3.12, `uv`, Terraform, Google Cloud CLI, GKE, Cloud Billing Budgets, Playwright, SHA-256.

## Metadata

| Field | Decision |
|---|---|
| Phase | GCP foundation; execution topic 22 of 32 |
| Authoritative source tasks | `04.2_llm_design.md` Task 7; GKE profile and trial-budget sections |
| Primary rubric cells | `Sheet3!E48` only; mandatory unscored `Sheet3!Row2` receives architecture facts but no ownership here |
| Prerequisites | Completed `tmp/edai2-plan/execution-v1/local/21-kind-lean-preflight.md` Completion Record and all topics 00-20 summarized there |
| Blocked successors | Topics 23-31; Topic 32 may run only as truthful partial finalization if this topic stops |
| Runtime owner | `topic22-terraform`; no evidence-session lease is acquired |
| Execution class | `GCP-write`; billable/persistent cloud resources |
| Branch rule | Same branch and checkout as Topic 21; serial execution only |

## Operator Project Selection

- The operator selected the existing project alias `FSDS-Ecom-Platform-Project` for reuse.
- The raw project identifier is stored only in the ignored ACL-restricted private selection and phase bundles; its SHA-256 is `280de6292ec9de40e955c9055f225e56462be31c96fc5047461bac1d420a7673`.
- Authenticated read-only verification confirmed the selected alias, ACTIVE lifecycle, the intended VND billing link, and the passing monetary gate at ₫0 observed spend.
- The first reuse bootstrap stopped before mutation because the project authority gate lacked `storage.buckets.get`, `storage.buckets.getIamPolicy`, and `storage.objects.list`. The operator then explicitly authorized `roles/storage.admin` for the active signed-in principal on this selected project; the narrowly scoped grant succeeded and all three permissions were verified without exposing the principal or project identifier.
- The single bounded bootstrap retry requested the fixed required API set. Its local long-running-operation poll exhausted before the remote operation settled, but a later read-only readback proved all 11 required APIs enabled. A private rollback-required `api_enable` handoff records that owned mutation and a USD 0 upper-bound cost; no backend bucket or Terraform-managed resource was created.
- The reuse verifier was corrected locally to enumerate Artifact Registry and KMS by documented exact locations, call Resource Manager `getIamPolicy` with POST, allow only the active principal plus Google-managed service identities, and scope the budget list to the selected project. Sanitized IAM inspection found no public, unrelated user/group/domain, project-managed, or external service-account membership.
- The operator authorized continuation after that stop. The minimum read-only `roles/billing.viewer` binding was added for the active principal on the linked billing account. Readback proved the binding, the live role's `billing.budgets.list` permission, the IAM grant, and the project-scoped Budget API call. The private REST client now supplies the selected project as its quota project, avoiding the prior `SERVICE_DISABLED` denial without selecting a global gcloud project.
- The corrected complete paginated reuse proof passes all 14 material resource categories. Compute inspection found only the Google-created default network, its 42 auto-mode default subnetworks, four default firewall rules, and Google-managed service identities; the gate permits those exact bootstrap defaults while continuing to reject custom networks, same-named subnets on custom networks, unrelated principals, public access, or any other resource.
- After preserving the original API-enable partial handoff under a phase-specific ignored private archive name, the authorized bootstrap completed with exit 0. It created and fully read back the sole private Terraform backend bucket and wrote the durable ignored bootstrap proof; no current partial handoff exists. Terraform remains prohibited until the full personal-study operator bundle supplies the real notification target and the dedicated backend-verification command writes its phase proof.
- An enabled email notification channel named `EDAI2 budget alerts` was created for the active signed-in principal and read back successfully. Its address and exact resource name remain only in the ignored ACL-restricted private record. Google reports verification status `UNSPECIFIED`; no delivery claim is made. On 2026-09-05 the operator approved a personal-study exception that makes encrypted recovery storage and two independent custodians not applicable; budget, notification, IAM, backend, DNS/HTTPS, sanitized-plan, and no-account-activation gates remain mandatory.
- Full-account activation remains prohibited. The trial credit ceiling is ₫7,889,850, the Terraform budget is ₫6,311,880, and the pre-deployment forecast ceiling is ₫4,733,910.

## Global Constraints

- Read and obey `C:\Users\oou1hc\.codex\RTK.md`; prefix every shell command with `rtk`.
- Authoritative source hashes must be exact before work starts:
  - Section 03: `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`
  - EDAI2: `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`
  - Rubric workbook: `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`
- Prefix every shell command with `rtk`. Do not nest `rtk` inside project scripts.
- Do not create/switch branches or worktrees, stage files, or commit.
- Consume the completed local implementation. If a source/IaC/chart defect appears, capture it, release or suspend any owned runtime, mark this topic `Partial`, and return it to the owning local topic; do not patch implementation during a live cloud lease.
- Execute topics serially. A later topic may not infer success from planned files or a prior dry run.
- Stop safely before Terraform plan/apply if the GCP project, active billing link, Billing Budget notification target, required project/billing IAM permissions, trial expiry, spend observation, DNS/HTTPS egress, Billing-console URL, or other named external input is missing, stale, inconsistent, or unauthorized.
- Raw project, billing, notification, URL, spend, and private-path values are supplied only through the ACL-restricted ignored file `tmp/edai2-gcp/operator-inputs.json`. They must never appear in shell arguments, logs, Git, or evidence. The personal-study bundle resolves the ignored tfvars, backend config, authenticated browser state, gcloud config/ADC, and `TF_DATA_DIR` under `tmp/edai2-gcp/`.
- The private backend config names the sole state bucket/prefix. On reuse, a pre-existing backend must have the independently observed SHA-256 proof, US-CENTRAL1 location, UBLA, versioning, non-public IAM, and an empty exact prefix; every other bucket is unsafe. For an operator-selected ACTIVE project with no backend, the authorized bootstrap first verifies the existing billing link and permissions, enables only the fixed required APIs, proves every paginated resource category empty, and only then creates and verifies that one backend bucket. Any nonempty or ambiguous readback after API enablement records a private rollback-required handoff and stops before bucket creation. A fresh project creates the same backend after its billing/API gates. The bucket remains outside Terraform state/destroy, and the workflow never deletes an existing bucket or uses local state.
- Every GCP topic uses `check_budget.py --live-external-preflight`. That mode uses Resource Manager and Cloud Billing `testIamPermissions`, verifies project lifecycle/billing linkage/notification target, probes the named DNS/HTTPS endpoints, and writes only booleans, timestamps, permission names/counts, and SHA-256 fingerprints. It must never emit an account ID, billing ID, principal, access token, notification URI, or credential.
- The active operator bundle declares `project_purpose=personal-study`; its strict schema omits recovery destination and custodian-attestation fields. The legacy production-shaped schema and its recovery validation remain supported but are not used for this personal project.
- The only authorized Kubernetes client target is fixed non-secret metadata: kubeconfig `tmp/edai2-gcp/kubeconfig`, context `edai2-gke`, and zone `us-central1-a`, recorded by `tmp/edai2-gcp/kube-target.json`. Every `kubectl` call must include `--kubeconfig tmp/edai2-gcp/kubeconfig --context edai2-gke`; every Helm call must include `--kubeconfig tmp/edai2-gcp/kubeconfig --kube-context edai2-gke`.
- Never call the kubectl context-switch operation, never rely on an implicit current-context query, and never write or inspect the user's default kubeconfig.
- The approved region/zone is `us-central1`/`us-central1-a`; the cluster is zonal Standard GKE with `COS_CONTAINERD`.
- Node pools are `e2-highmem-4` regular platform and `e2-standard-8` Spot workload, both minimum zero; Spot maximum two.
- Live execution is VND-only. The bundle records a timestamped account-credit-derived rate `trial_credit_vnd / official_USD_300`; the VND budget is conservatively rounded down from normalized USD 240, and the VND forecast ceiling corresponds to normalized USD 180. Node-hour/storage caps remain unchanged.
- A current VND Cloud Billing console spend observation must be no older than 24 hours. Stop if normalized forecast exceeds USD 180, console or ledger spend reaches 75% of normalized USD 240, the VND reconciliation difference exceeds the rate-equivalent of USD 5, or the trial expires before the requested runtime.
- At 90% or 100% budget, suspend immediately and prohibit resume. A budget notification is not an enforcement control; `check_budget.py` is.
- Never place credentials, service-account JSON, secret values, Terraform state, recovery shares, raw billing identifiers, principal identities, or unsanitized Terraform JSON in Git, terminal logs, screenshots, or evidence JSON.
- The sole GCP tfstate backend/configuration is the approved Terraform design. Do not add VMs, Ansible, Cloud Build, hosted LLMs, GPUs, or a persistent public load balancer.
- Use one bounded retry only after identifying and correcting a transient cause. If the retry fails, stop, preserve diagnostics, mark affected rubric cells `Partial` or `Missing`, and hand off a truthful result.
- `Sheet3!E49` remains `Out of Scope`, source points 1 and earned points 0. No GCP work may introduce a VM to chase that point.
- Screenshot capture is fail-closed: UI viewport `1600x1000`, non-element-cropped, fully visible stable selectors, temporary PNG, PNG signature check, decoder verification/full load, then atomic replacement. Record dimensions, URL, UTC, revision, selectors, SHA-256, linked machine evidence, what the image proves, and what it does not. Reject blank, clipped, loading, login-only, home-only, error, stale, secret-bearing, or PII-bearing images and inspect accepted files at original resolution.

## Read-Only Planning Refresh

Run these before any mutation:

1. `rtk git status --short --branch`
   - Expected: the same nonempty branch recorded by Topic 21 and only known work; no unexplained overlap in Terraform, GCP evidence, or execution-plan paths.
2. `rtk python -c "import hashlib; p=['tmp/edai2-plan/03_data_generator_improvement.md','tmp/edai2-plan/04.2_llm_design.md','tmp/rubic-check/Coursework Tracking (Public).xlsx']; print('\\n'.join(f'{x} {hashlib.sha256(open(x,\"rb\").read()).hexdigest()}' for x in p))"`
   - Expected: the three fixed hashes above.
3. `rtk rg -n "Status|Definition of Done|limitations|handoff" tmp/edai2-plan/execution-v1/local/21-kind-lean-preflight.md`
   - Expected: Topic 21 records completion, compatible local tests, the current commit/revision, and no unresolved blocker that invalidates GCP work.
4. `rtk git ls-files --error-unmatch tmp/edai2-gcp/coursework.auto.tfvars`
   - Expected: nonzero exit because the tfvars file is not tracked. A zero exit is a safety failure: stop and remove it from version control through an explicitly authorized remediation, not in this run.
5. Run the live preflight command in Task 3 against only `tmp/edai2-gcp/operator-inputs.json`.
   - Expected: its bundle validator resolves the exact ignored ACL-restricted tfvars/backend/browser/gcloud/ADC/TF_DATA_DIR paths without printing any path or raw value; missing or wrong paths stop before cloud access.

If a source hash, branch, predecessor state, or file ownership differs, stop without cloud mutation and update this plan before execution.

## Scope

- Verify external account/billing/IAM/trial/spend inputs.
- Run static Terraform/security tests, format, initialization without backend, and validation.
- Produce a live-price cost forecast and contextual Billing-console screenshot.
- Plan, sanitize, review, and apply only the approved resources.
- Establish and verify the explicit GKE kubeconfig/context.
- Produce sanitized Terraform machine evidence and contextual screenshot.

## Non-Goals

- No Helm/Kustomize application install, Vault initialization, model download, workload build, public ingress, benchmark, or screenshot beyond the two owned images.
- No Terraform destroy.
- No secret creation or recovery-material handling.
- No claim that a GKE workload or rubric UI is ready.

## Exact File Map

| Role | Exact path |
|---|---|
| Read | `infra/terraform/edai2/versions.tf`, `infra/terraform/edai2/providers.tf`, `infra/terraform/edai2/variables.tf` |
| Read | `infra/terraform/edai2/main.tf`, `infra/terraform/edai2/outputs.tf`, `infra/terraform/edai2/terraform.tfvars.example` |
| Read | `infra/terraform/modules/gke/main.tf`, `infra/terraform/modules/gke/variables.tf`, `infra/terraform/modules/gke/outputs.tf` |
| Read | `infra/terraform/modules/artifact_registry/main.tf`, `infra/terraform/modules/artifact_registry/variables.tf`, `infra/terraform/modules/artifact_registry/outputs.tf` |
| Read | `infra/terraform/modules/gcs/main.tf`, `infra/terraform/modules/gcs/variables.tf`, `infra/terraform/modules/gcs/outputs.tf` |
| Read | `infra/terraform/modules/kms/main.tf`, `infra/terraform/modules/kms/variables.tf`, `infra/terraform/modules/kms/outputs.tf` |
| Read | `infra/terraform/modules/iam/main.tf`, `infra/terraform/modules/iam/variables.tf`, `infra/terraform/modules/iam/outputs.tf` |
| Read | `infra/terraform/modules/budget/main.tf`, `infra/terraform/modules/budget/variables.tf`, `infra/terraform/modules/budget/outputs.tf` |
| Read | `configs/gke/cost_envelope.yaml` |
| Read | `configs/gke/required_permissions.json` |
| Read | `scripts/gke/check_budget.py`, `scripts/qa/capture_edai2_evidence.py` |
| External/untracked input | `tmp/edai2-gcp/coursework.auto.tfvars` |
| Generate/untracked Kubernetes credentials | `tmp/edai2-gcp/kubeconfig` |
| Temporary/untracked | Fixed private binary plan beneath bundle-bound `TF_DATA_DIR` |
| Generate | `evidence/04_2_llm_design/gke/cost_forecast_topic22.json` |
| Generate | `evidence/04_2_llm_design/gke/gcp_preflight_topic22.json` |
| Generate | `evidence/04_2_llm_design/gke/terraform_apply.json` |
| Generate | `evidence/04_2_llm_design/gke/usage_ledger.json` |
| Screenshot owner | `evidence/04_2_llm_design/screenshots/gcp_billing_spend.png` |
| Screenshot owner | `evidence/04_2_llm_design/screenshots/terraform_apply.png` |
| Update through capture CLI | `evidence/04_2_llm_design/screenshots/ui_manifest.json` |
| Update during execution | This file's Completion Record only |

Generated evidence must be created by the named commands; never hand-author a successful result.

## Interfaces, Data Flow, and Failure Modes

### Inputs

- Sole raw-input interface: ACL-restricted, ignored `tmp/edai2-gcp/operator-inputs.json`; no raw value is accepted through environment variables or argv.
- Bundle fields cover the personal-study purpose, project, billing account, exact notification target, Billing Console URL, public DNS probes, trial/spend/conversion timestamps, current/console/forecast/trial-credit VND amounts, backend proof, and safe allowlisted billing DOM-marker/PII-selector lists.
- Bundle paths resolve the exact tfvars, backend config, authenticated browser state, gcloud config, ADC file, and private `TF_DATA_DIR` beneath `tmp/edai2-gcp/`.
- An authenticated principal with the least privileges required by the approved modules.

### Outputs

- Sanitized Terraform outputs: project, zone, cluster name, pool names, registry URI, bucket name/prefixes, KMS resource ID, Workload Identity bindings, and budget ID; never credentials.
- Dedicated kubeconfig `tmp/edai2-gcp/kubeconfig` containing fixed context `edai2-gke`, plus redacted helper `tmp/edai2-gcp/kube-target.json`; the default kubeconfig remains untouched.
- Hash-bound cost/apply evidence and two screenshots.

### Data flow

External spend/account inputs -> fail-closed preflight -> live SKU/ledger forecast -> Terraform static validation -> plan sanitizer/operator review -> apply -> resource inventory -> kubeconfig/context verification -> evidence capture.

### Failure modes

- Missing billing link/IAM/notification target/DNS or a redaction violation: stop before plan.
- Stale spend/trial-expiry or budget mismatch: emit failed forecast and stop.
- Planned resource outside approved list or secret-looking value: discard plan and stop.
- Partial apply: capture diagnostics through the private runtime-contract helper and the redacted inventory helper only; never run a state/show command that can print raw state. Do not retry until cause and rollback/recovery are reviewed.
- Dedicated kubeconfig is missing, contains an unexpected context, or resolves another project/cluster: stop; never fall back to the default kubeconfig and never run a `kubectl` mutation.
- Screenshot failure: one bounded recapture after the exact selector/render cause is fixed; retain no invalid replacement.

## Ordered Test-First Execution Tasks

### Task 1: Prove fail-closed preflight behavior

- [ ] Run `rtk uv run pytest tests/unit/test_edai2_security_static.py tests/unit/test_edai2_repository_contract.py -q`.
  - Expected: exit 0; exact zone, machine types, zero-capable pools, Workload Identity, budget thresholds, storage limits, and VM/Ansible/Cloud-Build/hosted-model exclusions pass.
- [ ] Run `rtk uv run pytest tests/unit/test_gke_budget.py -q`.
  - Expected: exit 0; missing/stale VND spend, short trial lifetime, 75/90/100% thresholds, rate-normalized USD 5 reconciliation, and normalized USD 180 forecast ceiling all fail closed in tests.
- [ ] Validate `tmp/edai2-gcp/operator-inputs.json` through the live preflight. It is the sole raw-input interface and validates all referenced private paths as resolved, ignored, ACL/mode restricted, and beneath `tmp/edai2-gcp/`; no raw identifier is echoed.
  - Expected: exit 0 and only `EXTERNAL_PATH_GATE=PASS`. Exit 17/18/19 is a safe stop, not permission to invent values.
- [ ] Run `rtk uv run python scripts/gke/check_budget.py --operator-inputs tmp/edai2-gcp/operator-inputs.json --redacted-account-summary --output evidence/04_2_llm_design/gke/gcp_account_summary_topic22.json`.
  - Expected: the helper loads identifiers only from the private bundle, performs supported read-only REST through the private authenticated gcloud configuration, captures raw responses in memory, and atomically emits only active/linked booleans plus project-number/project-alias/billing-account SHA-256 values. Any incomplete readback emits a redacted failure and stops.

### Task 2: Validate Terraform without cloud mutation

- [ ] Run `rtk terraform -chdir=infra/terraform/edai2 fmt -check -recursive`.
  - Expected: exit 0 and no rewrite.
- [ ] For local validation only, set `TF_DATA_DIR` to a disposable ignored ACL-restricted directory under `tmp/edai2-gcp/`, then run `rtk terraform -chdir=infra/terraform/edai2 init -backend=false`.
  - Expected: exit 0; providers resolve from pinned constraints and no remote state is changed.
- [ ] Run `rtk terraform -chdir=infra/terraform/edai2 validate`.
  - Expected: exit 0.
- [ ] Run `rtk uv run pytest tests/unit/test_edai2_security_static.py tests/unit/test_edai2_repository_contract.py -q`.
  - Expected: exit 0 after initialization and no generated provider/state file is staged.

### Task 3: Gate live cost and capture billing authority

- [ ] Before any bootstrap mutation, dispatch `rtk uv run python scripts/gke/check_budget.py --operator-inputs tmp/edai2-gcp/monetary-inputs.json --private-monetary-forecast --usage-ledger evidence/04_2_llm_design/gke/usage_ledger.json --envelope configs/gke/cost_envelope.yaml --requested-ttl 0h --output evidence/04_2_llm_design/gke/bootstrap_forecast_topic22.json`. `monetary-inputs.json` is a separate ignored ACL-restricted private bundle containing only billing-account identity, gcloud config/ADC paths, and VND spend/forecast/trial values/timestamps. It makes only the exact private authenticated Cloud Billing account GET and writes immutable redacted VND monetary evidence plus billing-account open/currency/name-match booleans and a fingerprint. It does not contain or read a project, notification channel, recovery input, browser/DNS value, backend proof/config, tfvars, TF_DATA_DIR, Terraform contract, or state, and performs no mutation.
  - Expected: exit 0 only when the VND/open account and normalized USD 180 forecast gate pass. The forecast contains no raw account/project/token/path value and is the sole durable forecast artifact for bootstrap authorization.
- [ ] The operator then writes the fixed ignored private bootstrap authorization record referenced by the bundle. It must set `operator_approved: true` and bind exactly the fresh forecast SHA-256 and current immutable revision; an absent, stale, or mismatched record stops before project creation.
- [ ] Dispatch `rtk uv run python scripts/gke/check_budget.py --operator-inputs tmp/edai2-gcp/bootstrap-inputs.json --private-bootstrap`, then `rtk uv run python scripts/gke/check_budget.py --operator-inputs tmp/edai2-gcp/operator-inputs.json --verify-private-backend bootstrap`. `bootstrap-inputs.json` is a separate ignored ACL-restricted private bundle limited to the project and billing identities, forecast-bound monetary values/timestamps, backend proof/config, bootstrap authorization, and gcloud/ADC/TF_DATA_DIR private paths. It must not contain a notification, recovery, browser/DNS, tfvars, or Billing-console input; no placeholder notification is permitted. The bootstrap authorization record must be current for the immutable revision and durable forecast evidence. Its optional parent is either `folders/<number>`/`organizations/<number>` or the explicit `none` mode for a personal trial; `none` omits the v3 parent field and skips any parent IAM assertion, leaving project-create API enforcement definitive. The helper uses a private token environment and in-memory fixed REST calls, exact scoped `testIamPermissions` gates (billing association, project billing assignment, Resource Manager-tested Service Usage read/enable/LRO, and every Service Management bind), then creates-or-reads the project, polls each owning-API LRO, and only then links billing/enables services.
  - Expected: a reused ACTIVE project with a pre-existing backend first proves that exact bucket's metadata/IAM/empty prefix and then passes the complete paginated empty-resource gate across Compute, GKE, Artifact Registry, GCS, KMS, IAM, budgets, and project IAM. For the operator-selected empty project with no backend, the helper confirms the existing billing link and authorities, enables only the fixed missing APIs, performs the same complete paginated proof, and creates the private-config backend only after emptiness succeeds. A disabled/ambiguous API is never treated as empty; any post-enable ambiguity or nonempty result records the owned API mutation privately and stops. Fresh and verified-empty reuse paths read the created backend back at US-CENTRAL1 with UBLA/versioning/non-public IAM and an empty exact prefix, then record a durable redacted proof before init. After any owned bootstrap mutation, a later failure writes exactly one private redacted handoff with requested/completed phase booleans, owned rollback guidance, do-not-delete-existing, a zero upper-bound cost, and operator-review resume condition; it is never auto-deleted. Project creation/billing linkage is not claimed by a project-scoped permission check before that project exists.
- [ ] For a fresh project, stop after the backend proof until the operator has supplied and verified the exact project notification-channel input in the private bundle. Then run the deferred Task 1 redacted account-summary command and `rtk uv run python scripts/gke/check_budget.py --operator-inputs tmp/edai2-gcp/operator-inputs.json --required-permissions configs/gke/required_permissions.json --live-external-preflight --preflight-output evidence/04_2_llm_design/gke/gcp_preflight_topic22.json --usage-ledger evidence/04_2_llm_design/gke/usage_ledger.json --envelope configs/gke/cost_envelope.yaml --requested-profile suspended --requested-ttl 0h --output evidence/04_2_llm_design/gke/cost_forecast_topic22.json`.
  - Expected: exit 0; every account and external gate passes; VND spend/forecast values normalize through the locked timestamped rate to the USD 240 budget/USD 180 forecast ceilings. Evidence contains only redacted booleans/counts/names/timestamps/hashes plus VND and normalized USD amounts and is immutable.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --capture billing --operator-inputs tmp/edai2-gcp/operator-inputs.json --viewport 1600x1000 --output evidence/04_2_llm_design/screenshots/gcp_billing_spend.png --manifest evidence/04_2_llm_design/screenshots/ui_manifest.json --machine-evidence evidence/04_2_llm_design/gke/cost_forecast_topic22.json --strict`.
  - Expected: contextual spend/budget page, observation time and project alias visible, account numbers and PII redacted, final PNG decoded and atomically installed, manifest hash/dimensions/selectors recorded.
- [ ] Inspect `gcp_billing_spend.png` with the image viewer at original resolution.
  - Expected: no login/home/error state, clipping, loading overlay, secret, account number, or stale timestamp.

### Task 4: Produce and review the immutable plan

- [ ] Confirm the redacted preflight includes `serviceusage.services.enable`; the Terraform root enables the exact Topic 22 APIs before every foundation module and sets `disable_on_destroy = false` so a reused project is never deconfigured during cleanup. The durable private GCS backend proof remains a hard stop before `init`.
  - Expected: fresh projects can create the declared foundation after the plan, reused projects retain their enabled services, and no API is disabled by Topic 22 cleanup.
- [ ] Dispatch `rtk uv run python scripts/gke/check_budget.py --operator-inputs tmp/edai2-gcp/operator-inputs.json --verify-private-backend bootstrap` before init. The helper uses only private gcloud/ADC configuration and writes a redacted proof for the exact bootstrap-created or reuse-validated GCS bucket/prefix, selected project, US-CENTRAL1, UBLA, versioning, non-public IAM, and an empty state prefix. Stop if it fails.
- [ ] Dispatch `rtk uv run python scripts/gke/check_budget.py --operator-inputs tmp/edai2-gcp/operator-inputs.json --private-terraform-action init`, then the same fixed command with `plan`. The helper reads its ignored private runtime contract, credential paths, and TF_DATA_DIR only from the bundle; it captures process output in memory and emits only fixed status.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --private-plan-sanitize --operator-inputs tmp/edai2-gcp/operator-inputs.json --output evidence/04_2_llm_design/gke/terraform-show.json --strict`.
  - Expected: the bundle-only sanitizer reads the fixed private plan in process, binds its SHA-256 with the forecast evidence and current revision, and atomically writes only sanitized authorization evidence. It rejects secret-bearing output, forbidden resources, and replay.

### Task 5: Apply once and bind the kube context

- [ ] After reviewing only the redacted authorization evidence, the operator writes the ignored fixed private approval record with `operator_approved: true` and its plan, forecast, and revision hashes. Do not modify any public evidence record at this point.
- [ ] Dispatch `rtk uv run python scripts/gke/check_budget.py --operator-inputs tmp/edai2-gcp/operator-inputs.json --private-terraform-action apply`.
  - Expected: the helper rederives its private contract, verifies the fresh bootstrap proof and fixed approval record, runs once with private credentials, captures output in memory, then requires and persists the initialized backend proof. It rejects a changed or unapproved plan.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --terraform-inventory --operator-inputs tmp/edai2-gcp/operator-inputs.json --authorization-evidence evidence/04_2_llm_design/gke/terraform-show.json --output evidence/04_2_llm_design/gke/terraform_apply.json --strict`.
  - Expected: sanitized inventory contains the cluster, zero-capable pools, registry, bucket/prefix policies, KMS, Workload Identity/IAM, and budget; no application/Vault claim.
- [ ] Dispatch `rtk uv run python scripts/gke/check_budget.py --operator-inputs tmp/edai2-gcp/operator-inputs.json --write-private-wi-values`; it runs the fixed private `terraform output -json workload_identity_bindings` command under the bundle-bound private environment, validates the four bindings only in memory, atomically writes the one fixed ignored private Helm-values record, then internally materializes ephemeral ignored per-workload values to lint and render retrieval, drift, coordinator, and workers. It validates every rendered KSA/GSA annotation, captures outputs in memory, deletes the temporary values, and emits only fixed status. Checked-in empty annotations alone are not sufficient evidence.
- [ ] Run `rtk uv run python scripts/gke/check_budget.py --operator-inputs tmp/edai2-gcp/operator-inputs.json --prepare-kube-target`.
  - Expected: the helper supplies project and credential paths only through its private child environment, invokes fixed identifier-free argv internally with stdout/stderr captured, writes only `tmp/edai2-gcp/kubeconfig`, normalizes its context to `edai2-gke`, and atomically writes redacted `tmp/edai2-gcp/kube-target.json`. The default kubeconfig is untouched.
- [ ] Run `rtk kubectl --kubeconfig tmp/edai2-gcp/kubeconfig --context edai2-gke config view --minify --output name`.
  - Expected: the dedicated file selects only the fixed alias; this does not change either kubeconfig.
- [ ] Run `rtk kubectl --kubeconfig tmp/edai2-gcp/kubeconfig --context edai2-gke cluster-info`.
  - Expected: API server responds; this is connectivity only, not application readiness.

### Task 6: Capture Terraform proof

- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --render-sanitized-terraform evidence/04_2_llm_design/gke/terraform_apply.json --capture terraform-apply --viewport 1600x1000 --output evidence/04_2_llm_design/screenshots/terraform_apply.png --manifest evidence/04_2_llm_design/screenshots/ui_manifest.json --machine-evidence evidence/04_2_llm_design/gke/terraform_apply.json --strict`.
  - Expected: contextual sanitized resource/apply view with project alias, zone, revision, successful result, and no tfvars/state/secrets.
- [ ] Inspect `terraform_apply.png` at original resolution.
  - Expected: stable selectors fully visible; image proves successful approved Terraform apply but does not prove Kubernetes workloads.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --verify-screenshots gcp_billing_spend.png,terraform_apply.png --manifest evidence/04_2_llm_design/screenshots/ui_manifest.json --strict`.
  - Expected: exit 0 and both SHA-256 values match decoded files and linked machine evidence.

## Evidence and Screenshot Ownership

| Artifact | Primary owner | Proves | Does not prove |
|---|---|---|---|
| `gke/cost_forecast_topic22.json` | Topic 22 | live-price/spend/trial/cap gate | future runtime stayed within cap |
| `gke/terraform_apply.json` | Topic 22 | approved GCP resources exist | platform/application readiness |
| `gcp_billing_spend.png` | Topic 22 | contextual fresh billing observation | exact authoritative spend parsing |
| `terraform_apply.png` | Topic 22 | contextual successful sanitized apply | Vault, models, agents, or rubric UI |

Topic 31 audits these files but does not become their primary owner.

## Cleanup and Runtime Release

- Delete only the fixed private binary plan beneath bundle-bound `TF_DATA_DIR` after its hash and sanitized evidence are durable; never print its path or contents.
- Keep `tmp/edai2-gcp/coursework.auto.tfvars` untracked and access-controlled for later Terraform operations.
- Do not destroy persistent Terraform resources.
- Verify both node pools remain at zero immediately after apply and no forwarding rule/load balancer exists.
- Record that no session lease is held.
- [ ] Run and record `rtk git status --short --branch` as the final acceptance command.

## Rubric Traceability

| Cell | Points | Topic 22 gate | Evidence |
|---|---:|---|---|
| `Sheet3!E48` | 1 | Terraform plan/apply and approved GCP inventory succeed | `terraform_apply.json`, `terraform_apply.png` |
| `Sheet3!E49` | 1 source / 0 earned | Permanently out of scope; no VM/Ansible | static exclusion tests |
| `Sheet3!Row2` | mandatory/unscored | resource names/ownership may feed later diagram | no Row 2 satisfaction claim here |

## Definition of Done

- [ ] Predecessor, branch, and three source hashes are exact.
- [ ] External project/billing/IAM/trial/spend/notification/tfvars inputs passed fail-closed checks.
- [ ] Static tests, Terraform format/init/validate, budget gate, plan sanitizer, and apply exited 0.
- [ ] Explicit kubeconfig/context points to the approved project, zone, and `edai2` cluster.
- [ ] Only approved GCP resources exist; both pools are zero and no public forwarding rule exists.
- [ ] Both owned screenshots pass the full screenshot contract and original-resolution review.
- [ ] Temporary plan/show files are removed, tfvars remains untracked, and no secret/state is in Git/evidence.
- [ ] Topic 23 receives exact output names, hashes, revision, context, and truthful limitations.
- [ ] Final `rtk git status --short --branch` is recorded.

## Completion Record

Observed execution state is factual and limited to the completed bootstrap and pre-provisioning gates below.

- **Status:** Partial — the monetary gate and selected-project reuse bootstrap are complete, including the durable private backend proof and an enabled notification channel. The operator approved the personal-study recovery exception; the full operator bundle, dedicated backend phase proof, external preflight, Terraform plan/apply, Kubernetes target, and screenshots remain to be completed. No rubric point is claimed.
- **Branch / revision:** `feature/implement-edai2...origin/feature/implement-edai2`, initially clean and synchronized at `741e7843bf452ad765bc98810341c52c51a4ce29`. The working-tree delta is limited to Topic 22 repairs, tests, successful monetary evidence, usage ledger, and this record; nothing is staged.
- **Operator authorization:** The operator selected the existing ACTIVE project alias recorded above, authorized its reuse bootstrap, explicitly authorized `roles/storage.admin` on the project, and authorized continuation that added the minimum read-only `roles/billing.viewer` binding on the linked billing account. The forecast-bound private bootstrap authorization was consumed. No Terraform plan or apply authorization exists.
- **Cloud bootstrap:** The linked VND trial account remains unactivated with ₫0 observed spend. All 11 fixed APIs are enabled. The complete 14-category reuse inventory passes after allowing only documented Google-created defaults. The sole private state bucket was created with US-CENTRAL1, UBLA, versioning, non-public IAM, and empty-prefix readback, and its durable bootstrap proof exists. An enabled email channel named `EDAI2 budget alerts` was created for the active principal. No Terraform-managed foundation resource, GKE cluster, load balancer, or Kubernetes credential exists.
- **Affected files:** Modified `scripts/gke/check_budget.py` for typed private-path failures, Windows gcloud resolution, safe reuse bootstrap, documented regional inventory, project IAM filtering, project-scoped budget reads, quota-project routing, paced LRO polling, durable request-accepted partial state, and the personal-study recovery exception; modified `src/vina_bim_shop/topic22_private.py` for typed bundle/path/access validation errors and the strict personal-study schema; expanded `tests/unit/test_topic22_fourth_repair.py`; and updated this record. The ignored private phase files, backend proof, notification record, and archived API partial remain outside Git.
- **Command / exit-code log:** Locked source hashes and the initial Git index snapshot matched their recorded values. The latest relevant suite exited 0 with 179 passed. `rtk terraform -chdir=infra/terraform/edai2 fmt -check -recursive`, isolated backend-free `init`, and `validate` exited 0. The private monetary forecast exited 0. The first bootstrap stopped before mutation on missing Storage permissions; the bounded retry enabled the fixed APIs but its old hot-loop LRO poll stopped locally, after which readback proved all APIs enabled and an ignored rollback handoff was preserved. After the documented request-shape, IAM, quota-project, and default-resource repairs, the complete read-only reuse proof passed 14 categories and the authorized bootstrap exited 0.
- **Evidence / SHA-256 log:** The successful sanitized bootstrap forecast and usage ledger exist as untracked Topic 22 evidence. The two tracked redacted missing-input failure artifacts remain preserved by commit `741e784` and have not yet been replaced; replacement is permitted only after the full external preflight succeeds. No plan authorization or apply inventory exists.
- **Screenshot QA:** `gcp_billing_spend.png` and `terraform_apply.png` have not been captured; no screenshot claim is made.
- **Cleanup / runtime release:** No session lease is held. The historical API-enable partial is preserved under a phase-specific ignored private name; no current partial exists. The required APIs, minimum IAM bindings, notification channel, and private backend bucket persist for continuation. The backend-free local Terraform validation directory is ignored and contains no remote state. No destroy action has been run.
- **Limitations:** This is a personal study project with no production secrets or customer data, so external recovery custody is intentionally not claimed. Google Cloud budgets are alerts rather than guaranteed real-time caps; the workflow therefore retains conservative forecast rejection, zero-capacity defaults, trial-status checks, and the hard prohibition on activating the full billing account.
- **Handoff:** Complete the strict personal-study operator bundle without recovery fields, write the dedicated backend phase proof, and run the live preflight. Continue only to a sanitized Terraform plan that remains below the VND trial and normalized USD forecast limits; require the fixed plan-hash approval before any apply. Block Topics 23-31.
