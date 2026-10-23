# Topic 22 Handoff — Corp PC → Personal PC

## 1. Objective and non-goals

Resume and complete **Topic 22 only** (GCP account, budget, Terraform plan/apply) on a personal machine with direct network egress. Do not start Topic 23 or any later topic. Never activate the Google Cloud full account. Budgets are alerts, not spending caps — independent preflight, forecast, and zero-capacity safeguards remain mandatory.

## 2. Starting state (corp PC, verified)

- Branch: `feature/implement-edai2...origin/feature/implement-edai2`
- HEAD: `741e7843bf452ad765bc98810341c52c51a4ce29` (no new commits from this work yet)
- Modified (this commit): `configs/gke/required_permissions.json`, `scripts/gke/check_budget.py`, `scripts/qa/capture_edai2_evidence.py`, `src/vina_bim_shop/topic22_private.py`, `tests/unit/test_topic22_fourth_repair.py`, `tmp/edai2-plan/execution-v1/gcp/22-gcp-account-budget-terraform-apply.md`
- Stale tracked evidence restored from HEAD (not refreshed here): `evidence/04_2_llm_design/gke/cost_forecast_topic22.json`, `evidence/04_2_llm_design/gke/gcp_preflight_topic22.json`
- Untracked, intentionally left out of this commit: `evidence/04_2_llm_design/gke/usage_ledger.json` (append-only ledger regenerates/extends on the personal PC)
- Old stale hashes (do NOT apply on these): sanitized outer `c554b4b7c15f4ae1cad5fded347b18a9d339b0db514278ef4ed2f933367b181d`, inner private plan `fa352c80e1c0fbc064231d66c73bf1236b3eb5964a7c9c3a084fe05665742300`, forecast `9b97bfaf19ea878761d678ad884cb2e23e44abd4997b23f2583c5f4deae195e7`, revision `741e7843bf452ad765bc98810341c52c51a4ce29`
- Tests: `tests/unit/test_topic22_fourth_repair.py` 111 passed; security/contract/budget/third/second/precloud suites 78 passed; `terraform fmt -check` clean; redaction scans clean (no `@`, `serviceAccount:`, private paths in sanitized output).

## 3. What the corp session proved

- Permission-map fix: `TOPIC22_OPERATION_PERMISSIONS` reconciled to the testIamPermissions-safe manifest (`container.clusters.update`, no `container.nodePools.*`, no `storage.services.get`).
- Sanitizer fix (TDD, 4 new regression tests): legitimate Terraform `after_unknown` values accepted — WI `service_account_id` derived from deterministic `google_service_account` email via `for_each` address keys; Google-managed storage service agent and budget project-number filter deferred as unknown-at-plan with redaction intact; fabricated unknowns still rejected.
- Live gates via corp proxy `127.0.0.1:3128`: token, project ACTIVE, permissions, notification channel, DNS, billing URL all pass; alias hash matches the intended `FSDS-Ecom-Platform-Project` reuse target. GCS `storage.googleapis.com` reads time out through the corp proxy, so backend-proof refresh, live preflight, and re-sanitize could not complete here.
- Private state left intact: runtime contract + binding restored; durable bootstrap proof, private plan, tfvars/backend/ADC/gcloud config untouched; 15-minute backend phase proof expired unrecreated (refresh on personal PC); no approval file remains; no apply ran.

## 4. Do-NOT-copy list (stays on corp PC)

Never copy, paste, print, or commit: entire `tmp/edai2-gcp/` (operator-inputs, tfvars, backend.hcl, gcloud-config/ADC, tf-data including `topic22.tfplan`, proofs, kubeconfig), `C:\Users\oou1hc\AppData\Local\Temp\opencode\` scratch, raw project/billing IDs, principal emails, tokens, OAuth data, or private paths. The personal machine must re-authenticate and establish its own private bundle via the Topic 22 local-only entry procedure. Never paste private values into chat or tracked docs — hashes and booleans only.

## 5. Next-session planning prompt (verbatim — use as-is on the personal PC)

```text
Act as the Topic 22 continuation session (personal PC, direct network, no corp proxy).

Workspace: <personal-pc path to ecom-data-platform-submission>
Branch: feature/implement-edai2 (same checkout, serial, no new branches/worktrees)

First read: AGENTS.md + all referenced files including RTK.md (rtk prefix on every shell command),
tmp/edai2-plan/execution-v1/gcp/22-gcp-account-budget-terraform-apply.md,
tmp/edai2-plan/execution-v1/gcp/22-handoff-to-personal-pc.md,
and the recent diff for scripts/qa/capture_edai2_evidence.py,
scripts/gke/check_budget.py, tests/unit/test_topic22_fourth_repair.py.
Inspect rtk git status/diff. Use skills: executing-plans,
systematic-debugging, test-driven-development,
verification-before-completion.

Safety (hard stops): never Activate the full account; spend must stay
below ₫7,889,850; Terraform budget ₫6,311,880 (USD 240); forecast ceiling
₫4,733,910 (USD 180); stale/missing/failing trial, spend, forecast, billing
link, budget, or preflight → do not apply; node pools stay zero-capacity;
budgets are alerts, not caps. Personal-study recovery exception
(not_applicable_personal_study) is NOT apply approval. Apply needs a new
explicit approval bound to the exact new inner plan + forecast + revision
hashes. Preserve work: no reset/clean/stage/commit/push/PR unless explicitly
asked. Redact everything: never print or commit raw project/billing IDs,
principal emails, tokens, OAuth data, or private paths under tmp/edai2-gcp.
Private bundle must be established locally via the Topic 22 entry procedure;
never paste private values into chat.

Known state from corp PC: sanitizer repair green (WI/KMS/budget
after_unknown handling, permission-map fix); old hashes outer c554b4b7…,
inner fa352c80…, forecast 9b97bfaf…, rev 741e7843… are STALE — do not apply
on them. Corp proxy passed CRM/IAM/Billing but GCS storage timed out, so
backend-proof refresh + live preflight + re-sanitize must be redone here on
direct egress. Re-auth privately first (no passwords/OTPs to agent).

Execute: fresh backend proof → live preflight/forecast/ledger →
re-sanitize → present new inner plan + forecast + revision hashes and STOP
for exact hash approval. Only after that approval: bind private approval,
apply exactly that plan, verify inventory/IAM/KMS/budget/zero capacity,
capture both screenshots with manifests, re-run tests + secret scans, update
the Topic 22 Completion Record truthfully. Do not declare complete until every
DoD check passes. Do not start Topic 23.
```

## 6. Personal-machine prerequisites and resume

- Terraform 1.15.8, gcloud 577.0.0, kubectl 1.34.1, `uv`/Python 3.12, direct egress to `*.googleapis.com`, `rtk` available, same branch checkout.
- Re-authenticate privately (browser login, no codes to the agent), establish the private bundle locally, then: fresh backend proof → live preflight/forecast/ledger → re-sanitize → present new hashes → exact hash approval → bound approval → apply that exact plan → inventory/IAM/KMS/budget/zero-capacity verification → both screenshots with manifests → tests + secret scans → truthful Completion Record.
- Billing screenshots mandatory: `gcp_billing_spend.png` + `terraform_apply.png` at 1600x1000 with manifests and PII redaction; user performs login, agent never handles passwords/OTPs/Activate.

## 7. Topic 23 gate

Topic 23 stays blocked until Topic 22's Completion Record is `Complete` with every Definition-of-Done check passing, exact output names/hashes/revision/context recorded, and truthful limitations noted.
