# Topic 22: GCP Account, Budget, and Terraform Apply Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provision only the approved EDAI2 GCP foundation after proving account, billing, IAM, trial lifetime, live spend, forecast, and Terraform inputs are safe.

**Architecture:** Terraform owns a zonal Standard GKE cluster, two zero-capable node pools, Artifact Registry, one KMS-encrypted GCS bucket, KMS, Workload Identity/IAM, and a USD 240 Billing Budget. Google Cloud CLI writes credentials only to the dedicated `tmp/edai2-gcp/kubeconfig`; every later Kubernetes client call names that file and the approved context explicitly, and the default kubeconfig/current context is never read or changed. No Kubernetes application is installed here. Python 3.12/`uv` budget and evidence CLIs provide fail-closed machine records.

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

## Global Constraints

- Read and obey `C:\Users\oou1hc\.codex\RTK.md`; prefix every shell command with `rtk`.
- Authoritative source hashes must be exact before work starts:
  - Section 03: `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`
  - EDAI2: `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`
  - Rubric workbook: `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`
- Prefix every shell command with `rtk`. Do not nest `rtk` inside project scripts.
- Do not create/switch branches or worktrees, stage files, or commit.
- Execute topics serially. A later topic may not infer success from planned files or a prior dry run.
- Stop safely before Terraform plan/apply if the GCP project, active billing link, Billing Budget notification target, required IAM, trial expiry, spend observation, DNS-capable egress, or other named external input is missing, stale, inconsistent, or unauthorized.
- The operator-provided tfvars file is exactly `tmp/edai2-gcp/coursework.auto.tfvars`, addressed through `EDAI2_TFVARS_PATH`; it must remain untracked and must not be copied into `infra/terraform`.
- The only authorized Kubernetes client target is `EDAI2_GKE_KUBECONFIG=tmp/edai2-gcp/kubeconfig` plus `EDAI2_GKE_CONTEXT=gke_${GOOGLE_CLOUD_PROJECT}_us-central1-a_edai2`. Every `kubectl` call must include `--kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT`; every Helm call must include `--kubeconfig $env:EDAI2_GKE_KUBECONFIG --kube-context $env:EDAI2_GKE_CONTEXT`; scripts that query or mutate Kubernetes must receive both explicit values.
- Never call the kubectl context-switch operation, never rely on an implicit current-context query, and never write or inspect the user's default kubeconfig.
- The approved region/zone is `us-central1`/`us-central1-a`; the cluster is zonal Standard GKE with `COS_CONTAINERD`.
- Node pools are `e2-highmem-4` regular platform and `e2-standard-8` Spot workload, both minimum zero; Spot maximum two.
- Fixed envelope: USD 300 trial, USD 240 Terraform budget, USD 180 forecast ceiling, regular node-hours <=96, aggregate Spot node-hours <=72, second-Spot hours <=16, public ingress hours <=24, evidence lease <=6h, PVC <=80Gi, GCS plus Artifact Registry <=15Gi.
- A current Cloud Billing console spend observation must be no older than 24 hours. Stop if projected total exceeds USD 180, console or ledger spend reaches 75% of USD 240, console/ledger differ by more than USD 5, or the trial expires before the requested runtime.
- At 90% or 100% budget, suspend immediately and prohibit resume. A budget notification is not an enforcement control; `check_budget.py` is.
- Never place credentials, service-account JSON, secret values, Terraform state, recovery shares, or raw billing identifiers in Git, logs, screenshots, or evidence JSON.
- The sole GCP tfstate backend/configuration is the approved Terraform design. Do not add VMs, Ansible, Cloud Build, hosted LLMs, GPUs, or a persistent public load balancer.
- Use one bounded retry only after identifying and correcting a transient cause. If the retry fails, stop, preserve diagnostics, mark affected rubric cells unsatisfied, and hand off a truthful partial result.
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
| Read | `scripts/gke/check_budget.py`, `scripts/qa/capture_edai2_evidence.py` |
| External/untracked input | `tmp/edai2-gcp/coursework.auto.tfvars` |
| Generate/untracked Kubernetes credentials | `tmp/edai2-gcp/kubeconfig` |
| Temporary/untracked | `tmp/edai2-gcp/edai2.tfplan`, `tmp/edai2-gcp/terraform-show.json` |
| Generate | `evidence/04_2_llm_design/gke/cost_forecast.json` |
| Generate | `evidence/04_2_llm_design/gke/terraform_apply.json` |
| Generate | `evidence/04_2_llm_design/gke/usage_ledger.json` |
| Screenshot owner | `evidence/04_2_llm_design/screenshots/gcp_billing_spend.png` |
| Screenshot owner | `evidence/04_2_llm_design/screenshots/terraform_apply.png` |
| Update through capture CLI | `evidence/04_2_llm_design/screenshots/ui_manifest.json` |
| Update during execution | This file's Completion Record only |

Generated evidence must be created by the named commands; never hand-author a successful result.

## Interfaces, Data Flow, and Failure Modes

### Inputs

- `GOOGLE_CLOUD_PROJECT`, `GOOGLE_BILLING_ACCOUNT`, `EDAI2_BUDGET_NOTIFICATION_TARGET`.
- `EDAI2_TRIAL_EXPIRES_AT`, `EDAI2_CURRENT_SPEND_USD`, `EDAI2_SPEND_OBSERVED_AT`.
- `EDAI2_TFVARS_PATH=tmp/edai2-gcp/coursework.auto.tfvars`.
- `EDAI2_GKE_KUBECONFIG=tmp/edai2-gcp/kubeconfig`.
- `EDAI2_GKE_CONTEXT=gke_${GOOGLE_CLOUD_PROJECT}_us-central1-a_edai2`.
- An authenticated principal with the least privileges required by the approved modules.

### Outputs

- Sanitized Terraform outputs: project, zone, cluster name, pool names, registry URI, bucket name/prefixes, KMS resource ID, Workload Identity bindings, and budget ID; never credentials.
- Dedicated kubeconfig `tmp/edai2-gcp/kubeconfig` containing explicit kube-context `gke_${GOOGLE_CLOUD_PROJECT}_us-central1-a_edai2`; the default kubeconfig remains untouched.
- Hash-bound cost/apply evidence and two screenshots.

### Data flow

External spend/account inputs -> fail-closed preflight -> live SKU/ledger forecast -> Terraform static validation -> plan sanitizer/operator review -> apply -> resource inventory -> kubeconfig/context verification -> evidence capture.

### Failure modes

- Missing billing link/IAM/notification target: stop before plan.
- Stale spend/trial-expiry or budget mismatch: emit failed forecast and stop.
- Planned resource outside approved list or secret-looking value: discard plan and stop.
- Partial apply: run read-only `rtk terraform -chdir=infra/terraform/edai2 show` and GCP inventory once, record actual resources, and do not retry apply until cause and rollback/recovery are reviewed.
- Dedicated kubeconfig is missing, contains an unexpected context, or resolves another project/cluster: stop; never fall back to the default kubeconfig and never run a `kubectl` mutation.
- Screenshot failure: one bounded recapture after the exact selector/render cause is fixed; retain no invalid replacement.

## Ordered Test-First Execution Tasks

### Task 1: Prove fail-closed preflight behavior

- [ ] Run `rtk uv run pytest tests/unit/test_edai2_security_static.py tests/unit/test_edai2_repository_contract.py -q`.
  - Expected: exit 0; exact zone, machine types, zero-capable pools, Workload Identity, budget thresholds, storage limits, and VM/Ansible/Cloud-Build/hosted-model exclusions pass.
- [ ] Run `rtk uv run pytest tests/unit/test_gke_budget.py -q`.
  - Expected: exit 0; missing/stale spend, short trial lifetime, 75/90/100% thresholds, USD 5 reconciliation, and USD 180 forecast ceiling all fail closed in tests.
- [ ] Run `rtk powershell.exe -NoProfile -Command "if (-not $env:GOOGLE_CLOUD_PROJECT -or -not $env:GOOGLE_BILLING_ACCOUNT -or -not $env:EDAI2_BUDGET_NOTIFICATION_TARGET -or -not $env:EDAI2_TRIAL_EXPIRES_AT -or -not $env:EDAI2_CURRENT_SPEND_USD -or -not $env:EDAI2_SPEND_OBSERVED_AT) { exit 17 }; if ($env:EDAI2_TFVARS_PATH -ne 'tmp/edai2-gcp/coursework.auto.tfvars') { exit 18 }; if ($env:EDAI2_GKE_KUBECONFIG -ne 'tmp/edai2-gcp/kubeconfig' -or $env:EDAI2_GKE_CONTEXT -ne ('gke_' + $env:GOOGLE_CLOUD_PROJECT + '_us-central1-a_edai2')) { exit 19 }"`.
  - Expected: exit 0. Exit 17/18 is a safe stop, not permission to invent values.
- [ ] Run `rtk gcloud projects describe $env:GOOGLE_CLOUD_PROJECT --format=json`.
  - Expected: project lifecycle is ACTIVE and project number matches the approved tfvars.
- [ ] Run `rtk gcloud billing projects describe $env:GOOGLE_CLOUD_PROJECT --format=json`.
  - Expected: billing is enabled and the billing account matches the approved external input; redact account identifiers from committed evidence.

### Task 2: Validate Terraform without cloud mutation

- [ ] Run `rtk terraform -chdir=infra/terraform/edai2 fmt -check -recursive`.
  - Expected: exit 0 and no rewrite.
- [ ] Run `rtk terraform -chdir=infra/terraform/edai2 init -backend=false`.
  - Expected: exit 0; providers resolve from pinned constraints and no remote state is changed.
- [ ] Run `rtk terraform -chdir=infra/terraform/edai2 validate`.
  - Expected: exit 0.
- [ ] Run `rtk uv run pytest tests/unit/test_edai2_security_static.py tests/unit/test_edai2_repository_contract.py -q`.
  - Expected: exit 0 after initialization and no generated provider/state file is staged.

### Task 3: Gate live cost and capture billing authority

- [ ] Run `rtk uv run python scripts/gke/check_budget.py --project $env:GOOGLE_CLOUD_PROJECT --trial-expires-at $env:EDAI2_TRIAL_EXPIRES_AT --current-spend-usd $env:EDAI2_CURRENT_SPEND_USD --spend-observed-at $env:EDAI2_SPEND_OBSERVED_AT --usage-ledger evidence/04_2_llm_design/gke/usage_ledger.json --envelope configs/gke/cost_envelope.yaml --requested-profile suspended --requested-ttl 0h --output evidence/04_2_llm_design/gke/cost_forecast.json`.
  - Expected: exit 0, spend age <=24h, forecast <=USD 180, trial lifetime positive, ledger/console delta <=USD 5, and every cap reported.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --capture billing --url $env:EDAI2_BILLING_CONSOLE_URL --viewport 1600x1000 --output evidence/04_2_llm_design/screenshots/gcp_billing_spend.png --manifest evidence/04_2_llm_design/screenshots/ui_manifest.json --machine-evidence evidence/04_2_llm_design/gke/cost_forecast.json --strict`.
  - Expected: contextual spend/budget page, observation time and project alias visible, account numbers and PII redacted, final PNG decoded and atomically installed, manifest hash/dimensions/selectors recorded.
- [ ] Inspect `gcp_billing_spend.png` with the image viewer at original resolution.
  - Expected: no login/home/error state, clipping, loading overlay, secret, account number, or stale timestamp.

### Task 4: Produce and review the immutable plan

- [ ] Run `rtk terraform -chdir=infra/terraform/edai2 plan -var-file=$env:EDAI2_TFVARS_PATH -out=../../../tmp/edai2-gcp/edai2.tfplan`.
  - Expected: exit 0; approved resources only.
- [ ] Run `rtk terraform -chdir=infra/terraform/edai2 show -json ../../../tmp/edai2-gcp/edai2.tfplan`.
  - Expected: JSON is supplied to the evidence sanitizer; no secret value is printed or committed.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --sanitize-terraform-show tmp/edai2-gcp/edai2.tfplan --output tmp/edai2-gcp/terraform-show.json --require-resources gke,node-pools,artifact-registry,gcs,kms,iam,budget --forbid-resources vm,cloud-build,load-balancer --strict`.
  - Expected: exit 0; budget USD 240 with 0.50/0.75/0.90/1.00 thresholds, correct zone/pools, zero minima, lifecycle/prefix IAM, and no secret-bearing outputs.

### Task 5: Apply once and bind the kube context

- [ ] Obtain explicit operator authorization for the sanitized plan hash recorded in the Completion Record.
  - Expected: authorization references the exact plan SHA-256, project alias, forecast hash, and current branch revision. Absence means stop.
- [ ] Run `rtk terraform -chdir=infra/terraform/edai2 apply ../../../tmp/edai2-gcp/edai2.tfplan`.
  - Expected: exit 0 on the first attempt. One retry is allowed only for a documented transient provider/API error after confirming no conflicting partial resource.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --terraform-inventory --project $env:GOOGLE_CLOUD_PROJECT --zone us-central1-a --output evidence/04_2_llm_design/gke/terraform_apply.json --strict`.
  - Expected: sanitized inventory contains the cluster, zero-capable pools, registry, bucket/prefix policies, KMS, Workload Identity/IAM, and budget; no application/Vault claim.
- [ ] Run `rtk powershell.exe -NoProfile -Command "$env:KUBECONFIG=$env:EDAI2_GKE_KUBECONFIG; & gcloud container clusters get-credentials edai2 --zone us-central1-a --project $env:GOOGLE_CLOUD_PROJECT; exit $LASTEXITCODE"`.
  - Expected: credentials are written only to `tmp/edai2-gcp/kubeconfig` for the approved cluster; the default kubeconfig is untouched.
- [ ] Run `rtk kubectl --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT config view --minify --output jsonpath='{.current-context}{\"`n\"}{.clusters[0].name}{\"`n\"}'`.
  - Expected: the dedicated file's selected view is exactly the approved context and cluster; this does not change either kubeconfig.
- [ ] Run `rtk kubectl --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT cluster-info`.
  - Expected: API server responds; this is connectivity only, not application readiness.

### Task 6: Capture Terraform proof

- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --capture terraform-apply --url $env:EDAI2_TERRAFORM_EVIDENCE_URL --viewport 1600x1000 --output evidence/04_2_llm_design/screenshots/terraform_apply.png --manifest evidence/04_2_llm_design/screenshots/ui_manifest.json --machine-evidence evidence/04_2_llm_design/gke/terraform_apply.json --strict`.
  - Expected: contextual sanitized resource/apply view with project alias, zone, revision, successful result, and no tfvars/state/secrets.
- [ ] Inspect `terraform_apply.png` at original resolution.
  - Expected: stable selectors fully visible; image proves successful approved Terraform apply but does not prove Kubernetes workloads.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --verify-screenshots gcp_billing_spend.png,terraform_apply.png --manifest evidence/04_2_llm_design/screenshots/ui_manifest.json --strict`.
  - Expected: exit 0 and both SHA-256 values match decoded files and linked machine evidence.

## Evidence and Screenshot Ownership

| Artifact | Primary owner | Proves | Does not prove |
|---|---|---|---|
| `gke/cost_forecast.json` | Topic 22 | live-price/spend/trial/cap gate | future runtime stayed within cap |
| `gke/terraform_apply.json` | Topic 22 | approved GCP resources exist | platform/application readiness |
| `gcp_billing_spend.png` | Topic 22 | contextual fresh billing observation | exact authoritative spend parsing |
| `terraform_apply.png` | Topic 22 | contextual successful sanitized apply | Vault, models, agents, or rubric UI |

Topic 31 audits these files but does not become their primary owner.

## Cleanup and Runtime Release

- Delete only the untracked temporary plan/show files after their hashes and sanitized evidence are durable: `tmp/edai2-gcp/edai2.tfplan` and `tmp/edai2-gcp/terraform-show.json`.
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

Initial state is factual and must be replaced/extended only with observed execution results.

- **Status:** Not started; no GCP mutation or rubric point is claimed.
- **Branch / revision:** Record exact `rtk git status --short --branch` and `rtk git rev-parse HEAD`; none recorded.
- **Operator authorization:** No apply authorization recorded.
- **Affected files:** None at plan-authoring time.
- **Command / exit-code log:** No execution commands recorded.
- **Evidence / SHA-256 log:** No generated evidence recorded.
- **Screenshot QA:** `gcp_billing_spend.png` and `terraform_apply.png` not captured.
- **Cleanup / runtime release:** No lease held; cloud state not inspected by this plan artifact.
- **Limitations:** Workspace dependency and external account state must be revalidated at execution.
- **Handoff:** Block Topics 23-31 until this record contains successful apply/context evidence; Topic 32 may only report a truthful partial result if Topic 22 stops.
