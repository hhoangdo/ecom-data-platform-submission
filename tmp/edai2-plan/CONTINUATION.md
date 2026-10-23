# EDAI2 Continuation Plan — New GCP Trial

**Status:** local cleanup complete; no GCP resources running.
**Pre-cleanup baseline:** `4aef2aeebd0be7f70023652aea52ac74e5a26fe6`
(`feature/implement-edai2`, already on origin before cleanup).
**Cleanup branch:** `chore/edai2-final-cleanup` (local only, not pushed).
**Official artifact:** `evidence/04_2_llm_design/` — one `run_manifest.json`.

## 1. Current state

| Item | Value |
|---|---|
| Overall audit | **24 pass / 10 missing / 0 pending / 0 fail / 34 total** |
| T27 | Completed, 16/16 screenshots |
| T31 teardown | `ok: true`; nodes 0, ingress 0, load balancers 0, forwarding rules 0, pools zero, lease absent |
| Manifest SHA-256 | `4DCC3A285E75A8ECFB782795904DD43879A9906B29D7DCE804DE407BB1A546C6` |
| Bundle SHA-256 | `3b923dbf9ef4f02e71beb2d9caf314825320b43fbd1220e24af12b258d5a740f` |
| Bundle files / bytes | 111 / 4,277,959 |
| Current trial | expires 2026-10-25; cluster torn down; do not start it for this cleanup |
| Operator-reported credit | 5,214,351 VND remaining (2026-10-23); manifest cost snapshot is 2,503,095 VND spent as of 2026-10-22 |

The old trial project, registry, bucket, kubeconfig, browser state, model archives,
and credentials were purged locally. Do **not** reuse them. Historical IDs in the
completion records are transcripts, not configuration.

## 2. Remaining work for 34/34

| Topic | Missing images | Dependency |
|---|---|---|
| T22 | `gcp_billing_spend.png`, `terraform_apply.png` | New project/billing, Terraform plan/apply window |
| T26 | `agentregistry_agents.png`, `keda_scale.png` | Agent registry deployed; KEDA scale event |
| T28 | `airflow_rag_graph.png`, `datahub_rag_lineage.png` | RAG index + Airflow DAG + DataHub lineage |
| T29 | `kagent_coordinator_chat.png`, `kagent_drift_chat.png`, `kagent_retrieval_chat.png`, `locust_report.png` | kagent chats + Locust run |

Non-screenshot exceptions remain documented, not blocking 34/34:

- T25: Jenkins provenance waived; six verification jobs check the deployed tag.
- T30: platform/Vault recovery complete; spot/backup/accessors deferred.

Do not fabricate any missing image. If a precondition cannot be met, record a
truthful exception and stop that topic.

## 3. New-trial bootstrap

1. Create a **new** GCP trial account/project. Do not reuse the old project, billing
   account, bucket, registry, service accounts, or credentials.
2. Authenticate fresh:
   ```powershell
   gcloud auth login
   gcloud config set project <NEW_PROJECT_ID>
   ```
3. Set the new environment (names are examples; keep them out of git):
   ```powershell
   $env:EDAI2_PROJECT_ID = "<NEW_PROJECT_ID>"
   $env:EDAI2_REGION = "us-central1"
   $env:EDAI2_BUCKET = "<NEW_GLOBALLY_UNIQUE_BUCKET>"
   $env:EDAI2_REGISTRY = "us-central1-docker.pkg.dev/<NEW_PROJECT_ID>"
   ```
4. Create `infra/terraform/edai2/terraform.tfvars` from
   `terraform.tfvars.example`; fill the new project, billing account, bucket,
   notification target, and trial credit. Never commit it.
5. Preflight, then apply:
   ```powershell
   .venv\Scripts\python.exe scripts/gke/check_budget.py --help
   terraform -chdir=infra/terraform/edai2 init
   terraform -chdir=infra/terraform/edai2 plan -out=trial.tfplan
   terraform -chdir=infra/terraform/edai2 apply trial.tfplan
   ```
   Run `--help` and use the flags the current revision actually supports; do not
   copy commands blindly from historical records.
6. Build and push the images with explicit registry and revision substitutions.
   Both `cloudbuild.yaml` and `cloudbuild-coordinator.yaml` still carry historical
   defaults, so pass both values:
   ```powershell
   $sha = git rev-parse HEAD
   gcloud builds submit --config cloudbuild.yaml --substitutions "_REGISTRY=$env:EDAI2_REGISTRY,_SHA=$sha"
   gcloud builds submit --config cloudbuild-coordinator.yaml --substitutions "_REGISTRY=$env:EDAI2_REGISTRY,_SHA=$sha"
   ```
   Do not rely on the checked-in `_SHA` or `_REGISTRY` defaults.
   `ci/jenkins/scripts/release.sh` already passes
   `--set-string image.repository=${AR_LOCATION}-docker.pkg.dev/${GCP_PROJECT_ID}/...`.
   Do not rely on the hardcoded Helm defaults.
7. Acquire one bounded lease per window (maximum 6h):
   ```powershell
   .venv\Scripts\python.exe scripts/gke/manage_profile.py --help
   ```
   Use the `core` or `rubric-evidence` profile; stop-new-work at 4h, teardown at 5h.
8. Capture only the missing images with the current capture CLI:
   ```powershell
   .venv\Scripts\python.exe scripts/qa/capture_edai2_evidence.py --help
   ```
9. Reseal and verify after every evidence change:
   ```powershell
   .venv\Scripts\python.exe scripts/qa/seal_evidence_bundle.py
   .venv\Scripts\python.exe scripts/qa/verify_evidence_bundle.py
   ```
10. Tear down through the in-repo mechanism:
    ```powershell
    .venv\Scripts\python.exe scripts/gke/teardown.py --help
    ```
    Verify nodes 0, ingress 0, LBs 0, forwarding rules 0, pools zero, lease absent.

## 4. Proposed execution windows

| Window | Scope | Exit criteria |
|---|---|---|
| 1 (6h) | T22 billing/terraform apply; T26 registry/KEDA | 4 images captured, audit updated, teardown proof |
| 2 (6h) | T28 Airflow/DataHub; T29 kagent/Locust | 6 images captured, T31 QA rerun, teardown proof |
| Optional 3 | T25 Jenkins provenance; T30 spot/backup/accessors | machine evidence or truthful exception |

## 5. Cost and time

- Two 6h windows = 12 cluster-hours. Estimate **1.5–2.5M VND** for the remaining
  four topics, based on the prior 2.5M VND total and the smaller scope.
- Hard stop at **4.7M VND** (the prior forecast ceiling); keep at least 3M VND
  buffer in the new trial.
- One lease per window, maximum 6h. No public load balancer outside the capture
  window; no reserved IPs; teardown after each window.

## 6. Verification commands

```powershell
.venv\Scripts\python.exe scripts/qa/verify_evidence_bundle.py
.venv\Scripts\python.exe scripts/qa/check_ui_manifest_links.py
.venv\Scripts\python.exe scripts/qa/check_ui_manifest_secrets.py
.venv\Scripts\python.exe -m pytest tests/unit/llm -q
git status --short --branch
```

Confirm the audit remains `24/10/0/0/34` (or improves), every manifest reference
exists and matches, and no `.stale-*`, `.superseded-*`, or duplicate manifests remain.

## 7. Safe stops

- Do not upgrade the trial to a full account.
- Budget alerts are not spending caps; keep the independent preflight/forecast gates.
- Stop new work at 4h into a lease; teardown at 5h.
- No push, PR, history rewrite, or force-push without explicit approval.
- If a screenshot precondition fails, record an approved exception; never synthesize.
- Never copy a real kubeconfig, browser storage state, password, token, or model
  archive into the repository.
