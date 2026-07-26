# 17 — Terraform, Cost, IAM, Vault, and ExternalSecret Static IaC

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement and locally validate Task 7's strict Terraform, profiles, cost envelope, GCS IAM/lifecycle, Vault policy, and ExternalSecret contracts without planning, applying, authenticating, or mutating GCP.

**Architecture:** The `infra/terraform/edai2` Terraform root composes zonal GKE, Artifact Registry, GCS, KMS, least-privilege IAM, and budget modules. Workload Identity and prefix-conditioned object permissions replace JSON keys. Vault paths/roles are disjoint; only chart/CRD consumers lacking file injection receive exact-key ExternalSecrets.

**Tech Stack:** Terraform/HCL, GKE Standard, GCS/KMS/IAM/Budget modules, Vault HCL, Kubernetes ExternalSecret YAML, Python static tests.

## Metadata

| Field | Locked value |
|---|---|
| Phase | Local/static IaC Topic 17 |
| Source task | `tmp/edai2-plan/04.2_llm_design.md` Task 7 static portion |
| Sheet3 support | `Sheet3!E46`, `Sheet3!E48`, `Sheet3!E58` |
| Predecessor Completion Record | `tmp/edai2-plan/execution-v1/local/16-images-jenkins-ci.md` must be `Complete` |
| Blocked successor | `tmp/edai2-plan/execution-v1/local/18-platform-helm-kustomize.md` |
| Runtime ownership | Local Terraform validation only; no backend/provider project session |
| Class | Local/static; never GCP proof |

## Locked planning basis

Read `C:\Users\oou1hc\.codex\RTK.md`; verify Section 03 hash `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`, EDAI2 hash `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`, and rubric `tmp/rubic-check/Coursework Tracking (Public).xlsx` hash `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.

## Global constraints

Stay on current branch and run serially. Use `apply_patch`, `rtk uv run` for developer recipes, and `rtk make` for operator recipes. Topic 08 owns baseline dependencies; run `rtk uv lock --check` and treat a missing prerequisite as a `Partial` predecessor defect rather than editing dependencies. Do not stage/commit, run `terraform plan/apply/refresh/import`, authenticate, call `gcloud`, create state, expose secret values, or auto-prune/stop Docker. `EDAI2_TFVARS_PATH` names an operator-owned external variable file; never copy it into the repository. One retry then `Partial`.

## Read-only current-state refresh

- [ ] Run `rtk git status --short --branch`. Expected: branch/unrelated changes recorded.
- [ ] Run `rtk proxy certutil -hashfile tmp/edai2-plan/03_data_generator_improvement.md SHA256`. Expected: output contains `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`.
- [ ] Run `rtk proxy certutil -hashfile tmp/edai2-plan/04.2_llm_design.md SHA256`. Expected: output contains `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`.
- [ ] Run `rtk proxy certutil -hashfile "tmp/rubic-check/Coursework Tracking (Public).xlsx" SHA256`. Expected: output contains `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- [ ] Run `rtk proxy powershell -NoProfile -Command "Select-String -Path tmp/edai2-plan/execution-v1/local/16-images-jenkins-ci.md -Pattern '^Status: Complete|\| Status \| Complete \|'"`. Expected: completed predecessor.
- [ ] Run `rtk uv lock --check`. Expected: exit 0 with the Topic 08-owned baseline lockfile unchanged.
- [ ] Run `rtk proxy powershell -NoProfile -Command 'if ($env:EDAI2_TFVARS_PATH) { Write-Error "EDAI2_TFVARS_PATH must remain unused in static Topic 17"; exit 1 }; Write-Output "EDAI2_TFVARS_PATH=unset"'`. Expected: exit 0 and exactly `EDAI2_TFVARS_PATH=unset`; the external file is not read.
- [ ] Run `rtk git diff --check`. Expected: exit 0.

## Scope and non-goals

In scope: environment/modules, profile/cost configs, non-mutating budget parser, GCS prefix IAM/lifecycle, Vault config/policies/auth, exact ExternalSecret definitions, Terraform format/init-backend-false/validate, security static tests.

Non-goals: Terraform plan/apply, provider authentication, GCP inventory, Vault init/unseal, secret creation, Helm install, live budget query, screenshots, and state files.

## Exact file map

| Action | Exact path | Responsibility |
|---|---|---|
| Create | `infra/terraform/edai2/versions.tf` | Terraform/provider version constraints |
| Create | `infra/terraform/edai2/providers.tf` | Provider configuration without credentials |
| Create | `infra/terraform/edai2/variables.tf` | External inputs including safe limits |
| Create | `infra/terraform/edai2/main.tf` | Compose six approved modules |
| Create | `infra/terraform/edai2/outputs.tf` | Non-secret resource IDs only |
| Create | `infra/terraform/edai2/terraform.tfvars.example` | Typed example shape with safe non-secret values and no project identity |
| Generated | `infra/terraform/edai2/.terraform.lock.hcl` | Provider selections generated by backend-disabled init and reviewed/hash-bound |
| Create | `infra/terraform/modules/gke/main.tf`, `infra/terraform/modules/gke/variables.tf`, `infra/terraform/modules/gke/outputs.tf` | Zonal Standard cluster and zero-capable pools |
| Create | `infra/terraform/modules/artifact_registry/main.tf`, `infra/terraform/modules/artifact_registry/variables.tf`, `infra/terraform/modules/artifact_registry/outputs.tf` | Six repositories/immutable access |
| Create | `infra/terraform/modules/gcs/main.tf`, `infra/terraform/modules/gcs/variables.tf`, `infra/terraform/modules/gcs/outputs.tf` | Prefixes, lifecycle and storage caps |
| Create | `infra/terraform/modules/kms/main.tf`, `infra/terraform/modules/kms/variables.tf`, `infra/terraform/modules/kms/outputs.tf` | KMS resource IDs/least privilege |
| Create | `infra/terraform/modules/iam/main.tf`, `infra/terraform/modules/iam/variables.tf`, `infra/terraform/modules/iam/outputs.tf` | Workload Identity and prefix-conditioned IAM |
| Create | `infra/terraform/modules/budget/main.tf`, `infra/terraform/modules/budget/variables.tf`, `infra/terraform/modules/budget/outputs.tf` | USD 240 and 50/75/90/100% alerts |
| Modify | `configs/gke/profiles.yaml` | Complete the Topic 08 scaffold with suspended/core/rubric-evidence and TTL transitions |
| Modify | `configs/gke/cost_envelope.yaml` | Complete the Topic 08 scaffold with $180 forecast and PVC/object/capacity caps |
| Create | `configs/gke/required_permissions.json` | Exact Resource Manager/Cloud Billing permissions required by every live-GCP gate |
| Create | `scripts/gke/check_budget.py` | Non-mutating local validation plus redacted live external-input preflight |
| Create | `scripts/gke/manage_profile.py` | Render/dry-run profile state machine; live use deferred |
| Create | `infra/security/vault/config.hcl` | Raft/KMS/Kubernetes-auth configuration |
| Create | `infra/security/vault/policies/retrieval.hcl`, `infra/security/vault/policies/drift.hcl`, `infra/security/vault/policies/coordinator.hcl`, `infra/security/vault/policies/agentgateway.hcl`, `infra/security/vault/policies/jenkins.hcl` | Narrow consumer policies |
| Create | `infra/security/vault/kubernetes-auth.yaml` | Role/service-account bindings |
| Create | `infra/security/external-secrets/cluster-secret-store.yaml` | Reference-only store |
| Create | `infra/security/external-secrets/chat-basic-auth.yaml`, `infra/security/external-secrets/jenkins-controller.yaml`, `infra/security/external-secrets/kagent-gateway-keys.yaml`, `infra/security/external-secrets/facade-gateway-key.yaml`, `infra/security/external-secrets/postgres.yaml`, `infra/security/external-secrets/clickhouse.yaml`, `infra/security/external-secrets/valkey.yaml`, `infra/security/external-secrets/redpanda.yaml`, `infra/security/external-secrets/airflow.yaml`, `infra/security/external-secrets/datahub.yaml`, `infra/security/external-secrets/langfuse.yaml`, `infra/security/external-secrets/agentregistry.yaml`, `infra/security/external-secrets/grafana.yaml` | Exact-key projections and 1h refresh |
| Modify | `tests/unit/test_edai2_security_static.py` | Add IaC, secret, GCP exclusion, and policy assertions to the Topic 08 security scaffold |
| Modify | `tests/unit/test_edai2_repository_contract.py` | Extend the Topic 08/16 scaffold with Task 7 Terraform-root, resource-boundary, no-VM/Ansible/Cloud-Build, and secret-reference assertions |
| Create | `tests/unit/test_gke_budget.py` | Fake-adapter tests for the redacted live external-input gate |

## Interfaces, data flow, and failure modes

Inputs are typed non-secret Terraform variables, external `EDAI2_TFVARS_PATH` shape, cost/profile limits, prefix requirements, and Vault consumer matrix. Backend-disabled validation produces a provider lock and validated non-secret output schema; policy rendering produces narrow Vault roles and exact-key ExternalSecret references. `check_budget.py --live-external-preflight` is a non-mutating gate used later by every GCP topic: through injectable adapters it verifies active project lifecycle, billing linkage, `testIamPermissions` results against `configs/gke/required_permissions.json`, trial expiry, current spend/forecast, budget notification target, approved recovery-sink attestation, required DNS probes, and any topic-declared URL inputs. Its machine output contains booleans, bounded numeric values and hashes only—never raw project, billing-account, principal, notification-target, sink URI, credential or URL values. Topic 17 tests that mode only with fake adapters and never contacts GCP. Topic 18 consumes these static contracts; GCP Topic 22 alone may later use an operator-approved tfvars path and apply.

An unset required type, secret-looking value/output, broad IAM, cross-prefix permission, cross-Vault-path read, wrong ExternalSecret key, unsupported resource, capacity/cost breach, non-zero-disabled pool, backend/state access, provider authentication, missing/false live external gate, raw identifier/URI emission, or any plan/apply command fails closed. Topic 17 never falls back to default project credentials or a repository tfvars file.

## Exact IaC/security contract

Cluster: `us-central1-a`, Standard zonal, `COS_CONTAINERD`; regular `e2-highmem-4`, Spot `e2-standard-8`, Spot min 0/max 2, both manually zero-capable. Budget USD 240 with `0.50/0.75/0.90/1.00`; forecast gate <=$180. PVC cap 80Gi and object cap 15Gi. GCS IAM is prefix-conditioned and lifecycle-specific.

Reject VM, Ansible, Cloud Build, hosted model, SandboxAgent `runtimeClassName`, JSON service-account key, public permanent LB, broad IAM and secret-looking output/value.

Vault four-key path `kv/edai2/kagent/gateway-keys` contains exactly model/support/drift/coordinator keys; facade path `kv/edai2/facade/gateway-entry` contains only `authorization`. Cross-path reads fail. Other ExternalSecrets project only master-plan key names and use `refreshInterval: 1h`. First-party app credentials remain Vault-rendered files; GCS consumers use ambient identity.

Exact remaining projections are chat `auth`; Jenkins `admin-user,admin-password`; PostgreSQL `username,password,database`; ClickHouse `username,password`; Valkey `password`; Redpanda `sasl-user,sasl-password`; Airflow `fernet-key,webserver-secret,admin-password`; DataHub `system-update-password`; Langfuse `nextauth-secret,salt,encryption-key`; Agent Registry `api-token,session-secret`; and Grafana `admin-user,admin-password`. GCS prefix conditions separately cover `model-cache/`, `agent-substrate/`, `langfuse-events/`, `airflow-logs/`, and `backups/`; a role for one prefix cannot access another.

## Ordered test-first execution

- [ ] Add red IaC/security tests and run `rtk uv run pytest tests/unit/test_edai2_security_static.py tests/unit/test_edai2_repository_contract.py -q`. Expected: nonzero until environment/modules/policies/projections exist.
- [ ] Implement Terraform/config files and run `rtk terraform -chdir=infra/terraform/edai2 fmt -check -recursive`. Expected: exit 0; no file changed by check.
- [ ] Run `rtk terraform -chdir=infra/terraform/edai2 init -backend=false`. Expected: exit 0 without backend, state, project authentication or mutation.
- [ ] Run `rtk terraform -chdir=infra/terraform/edai2 validate`. Expected: exit 0 with configuration valid and no plan/apply.
- [ ] Implement Vault/ExternalSecret contracts and run `rtk uv run pytest tests/unit/test_edai2_security_static.py -q`. Expected: exit 0; exact paths/keys, cross-denials, existingSecret references and no literal secrets.
- [ ] Implement the budget preflight adapters and run `rtk uv run pytest tests/unit/test_gke_budget.py -q`. Expected: exit 0 using fake adapters only; every live project/billing/IAM/trial/spend/notification/recovery-sink/DNS/URL failure closes the gate, and captured output contains no raw IDs, principals, tokens, URIs or URLs.
- [ ] Run `rtk uv run python scripts/gke/check_budget.py --help` and `rtk uv run python scripts/gke/manage_profile.py --help`. Expected: exit 0; the former exposes `--live-external-preflight`, billing/IAM/recovery/DNS/URL inputs and redacted output, while neither command contacts GCP.
- [ ] Run `rtk uv run pytest tests/unit/test_edai2_security_static.py tests/unit/test_edai2_repository_contract.py tests/unit/test_gke_budget.py -q` and `rtk git diff --check`. Expected: both exit 0; no tfstate/tfplan/secret file exists.

## Evidence, cleanup, rubric, and DoD

Topic 17 owns fmt/init-backend-false/validate and static security reports only. Remove only local `.terraform` plugin cache created by this topic after recording provider lock/hash; do not delete state because none may exist. No runtime/cloud lease.

| Sheet3 cell | Local proof | Deferred proof |
|---|---|---|
| `Sheet3!E46` | ingress/secret prerequisite static contract | live TLS/auth |
| `Sheet3!E48` | Terraform validation and exclusion tests | apply screenshot |
| `Sheet3!E58` | strict GKE/Vault/IAM architecture contract | live capacity/security proof |

## Definition of Done

Exact environment/modules/profiles/cost/lifecycle/IAM/Vault/ExternalSecret contracts pass fmt/init-backend-false/validate/static tests; no plan/apply/auth/state/secret was produced.

## Completion Record

| Field | Execution value |
|---|---|
| Status | Not started |
| Current branch/status | Record final `rtk git status --short --branch` |
| Affected files | Record Topic 17 exact paths |
| Commands and exit codes | Record fmt/init/validate/static commands |
| Evidence hashes | Record sanitized reports/provider lock hash |
| Screenshot QA | Not captured locally |
| Cleanup/runtime release | Record owned .terraform cache cleanup; no cloud runtime |
| Limitations | Record deferred plan/apply/live Vault proof |
| Handoff | `tmp/edai2-plan/execution-v1/local/18-platform-helm-kustomize.md` |
