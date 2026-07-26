# Workstation, Toolchain, Context, and Safety Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a reproducible local planning and smoke-test workstation without mutating GCP or the current corporate Kubernetes context.

**Architecture:** A reserved dedicated kubeconfig/context convention isolates future Topic 21 Kind smoke checks from the corporate context; this topic performs no cluster operation.

**Tech Stack:** Windows Winget, Kind 0.32.0, `kindest/node:v1.35.5@sha256:ce977ae6d65918d0b58a5f8b5e940429c2ce42fa3a5619ec2bbc60b949c0ac95`, Helm 3.20.0, Terraform 1.15.8, gcloud 577.0.0, `uv`, Make, `rtk`.

## Locked sources and acceptance procedure

- Read `C:\Users\oou1hc\.codex\RTK.md` before every operator session and prefix every shell command with `rtk`.
- Locked Section03 source: `tmp/edai2-plan/03_data_generator_improvement.md`, SHA256 `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`.
- Locked EDAI2 source: `tmp/edai2-plan/04.2_llm_design.md`, SHA256 `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`.
- Locked rubric source: `tmp/rubic-check/Coursework Tracking (Public).xlsx`, SHA256 `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- Preflight and final acceptance both run `rtk git status --short --branch`; record the output and reject a branch change during the serial session.
- Final acceptance also records SHA256s, evidence/screenshot QA, cleanup/runtime release, limitations, and successor handoff in the Completion Record.

## Metadata

| Field | Decision |
|---|---|
| Phase | 0 — local prerequisite |
| Source tasks | Workstation/toolchain/context safety support only |
| Primary rubric cells | Supporting contributor only for `Sheet3!E3:E62`; no primary ownership |
| Prerequisites | None |
| Blocked successors | Topic 01 only |
| Runtime ownership | Named operator; one serial session |
| Local/GCP class | Local-only; no live GCP mutation |

## Architecture and technology

Use `uv` as the Python toolchain, Make recipes as `uv run ...`, and `rtk` only as the operator command proxy. Pin Windows tools to Kind `0.32.0`, Helm `3.20.0`, Terraform `1.15.8`, and gcloud `577.0.0`. Reserve `tmp/edai2-kind/kubeconfig`, cluster `edai2-lean`, context `kind-edai2-lean`, and image `kindest/node:v1.35.5@sha256:ce977ae6d65918d0b58a5f8b5e940429c2ce42fa3a5619ec2bbc60b949c0ac95` exclusively for Topic 21; Kind is never GKE evidence.

## Global constraints

- Source locks: Section03 `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`; EDAI2 `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`; workbook `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- Keep the same Git branch for every plan and implementation session; do not create a worktree or branch.
- Sessions are serial. Record the operator and start/end timestamps before acquiring any runtime.
- Explicitly set `KUBECONFIG` and use an explicit `--context`; never rely on kubectl’s current context.
- Guard the existing corporate context: it is read-only and is never renamed, deleted, switched, or used for apply/delete/port-forward.
- Local files contain no live GCP mutation commands. GCP commands belong only to later, explicitly authorized runtime plans.
- Topic 00 installs/verifies tools and reserves the dedicated path/context convention only; Topic 21 alone creates, smokes, or tears down `edai2-lean`.
- Never substitute Kind smoke output for GKE, Terraform-apply, Airflow, DataHub, or rubric evidence.
- Do not run Docker system prune, Docker prune, or stop/remove containers not named by this session.
- Truthful scoring only: missing verified evidence earns zero; `Sheet3!E32:E34` are prerequisite-owned and `Sheet3!E49` remains Out of Scope.

## Current-state refresh — read-only planning phase

Run before any install or mutation:

```text
rtk git branch --show-current
rtk git status --short --branch
rtk git rev-parse --show-toplevel
rtk kubectl config current-context
rtk kubectl config get-contexts
rtk kind version
rtk kubectl version --client --output=yaml
rtk helm version --short
rtk terraform version
rtk gcloud version
```

Expected: a single recorded branch, a visible corporate context marked read-only in the handoff, and version results that either meet the pins or identify the exact missing tool. This is observation only.

## Scope and non-goals

In scope: pin verification, context isolation, dedicated local Kind conventions, and evidence naming. Out of scope: Kind creation/smoke/teardown, installing a cluster into GCP, changing kubeconfig contents, Docker cleanup outside a named Kind cluster, credentials, and scoring any local smoke as production proof.

## Exact file map

| Action | Path | Purpose |
|---|---|---|
| Create | `tmp/edai2-plan/execution-v1/local/00-workstation-toolchain-context-safety.md` | This operator plan |
| Verify only | `Makefile`, `pyproject.toml`, `uv.lock` | Confirm Make uses `uv run` and project Python is locked |

## Interfaces, data flow, and failure modes

Operator → `rtk` → pinned local CLI → explicit temporary Kind kubeconfig/context. A smoke capture is labelled `local-kind-smoke` and cannot enter any GKE evidence manifest. Missing version pin, unknown current context, dirty unrelated changes, absent digest, or an attempt to target the corporate context stops the session before mutation.

## Ordered test-first execution tasks

- [ ] Run `rtk git status --short --branch`, `rtk git branch --show-current`, `rtk git rev-parse --show-toplevel`, `rtk kubectl config current-context`, and `rtk kubectl config get-contexts`; expected outcome is one recorded current branch/root plus a corporate context inventory that remains read-only.
- [ ] Run `rtk winget install --id Kubernetes.kubectl --version 1.34.1 --exact --source winget --accept-package-agreements --accept-source-agreements`; expected outcome is exit 0 and kubectl client `v1.34.1` installed or already present.
- [ ] Run `rtk winget install --id Kubernetes.kind --version 0.32.0 --exact --source winget --accept-package-agreements --accept-source-agreements`; expected outcome is exit 0 and Kind `0.32.0` installed or already present.
- [ ] Run `rtk winget install --id Helm.Helm --version 3.20.0 --exact --source winget --accept-package-agreements --accept-source-agreements`; expected outcome is exit 0 and Helm `3.20.0` installed or already present.
- [ ] Run `rtk winget install --id Hashicorp.Terraform --version 1.15.8 --exact --source winget --accept-package-agreements --accept-source-agreements`; expected outcome is exit 0 and Terraform `1.15.8` installed or already present.
- [ ] Run `rtk winget install --id Google.CloudSDK --version 577.0.0 --exact --source winget --accept-package-agreements --accept-source-agreements`; expected outcome is exit 0 and gcloud `577.0.0` installed or already present.
- [ ] Run `rtk winget upgrade --id Kubernetes.kind --version 0.32.0 --exact --source winget --accept-package-agreements --accept-source-agreements`; expected outcome is exit 0 or Winget’s explicit already-at-version result, never an unpinned upgrade.
- [ ] Run `rtk winget upgrade --id Helm.Helm --version 3.20.0 --exact --source winget --accept-package-agreements --accept-source-agreements`; expected outcome is exit 0 or Winget’s explicit already-at-version result, never an unpinned upgrade.
- [ ] Run `rtk winget upgrade --id Hashicorp.Terraform --version 1.15.8 --exact --source winget --accept-package-agreements --accept-source-agreements`; expected outcome is exit 0 or Winget’s explicit already-at-version result, never an unpinned upgrade.
- [ ] Run `rtk winget upgrade --id Google.CloudSDK --version 577.0.0 --exact --source winget --accept-package-agreements --accept-source-agreements`; expected outcome is exit 0 or Winget’s explicit already-at-version result, never an unpinned upgrade.
- [ ] Run `rtk kind version`, `rtk kubectl version --client --output=yaml`, `rtk helm version --short`, `rtk terraform version`, and `rtk gcloud version`; expected outcome is Kind `0.32.0`, kubectl client `v1.34.1`, Helm `v3.20.0`, Terraform `1.15.8`, and gcloud `577.0.0`.
- [ ] Run `rtk powershell -NoProfile -Command "New-Item -ItemType Directory -Force -Path 'tmp/edai2-kind' | Out-Null; Test-Path 'tmp/edai2-kind/kubeconfig'"`; expected outcome is `False` or a pre-existing dedicated file, never the corporate kubeconfig. Record reserved path `tmp/edai2-kind/kubeconfig`, cluster `edai2-lean`, context `kind-edai2-lean`, and image `kindest/node:v1.35.5@sha256:ce977ae6d65918d0b58a5f8b5e940429c2ce42fa3a5619ec2bbc60b949c0ac95` for Topic 21.
- [ ] Run `rtk powershell -NoProfile -Command '$env:KUBECONFIG="tmp/edai2-kind/kubeconfig"; Write-Output $env:KUBECONFIG'`; expected output is exactly `tmp/edai2-kind/kubeconfig`, proving the parent PowerShell did not expand the nested environment reference. Topic 00 does not invoke Kind, kubectl, Helm, or Docker against that path.
- [ ] Run `rtk git diff --check` and `rtk git status --short --branch`; expected no whitespace errors, the original branch unchanged, only Topic 00 planning/tool-install effects recorded, and nothing staged.

Makefile policy: recipes are written as `uv run python ...` or `uv run pytest ...`; operators run them as `rtk make generate-section03`, `rtk make build-section03-dbt`, or `rtk make test-section03`.

## Evidence and screenshot ownership

The workstation operator owns terminal captures of versions, explicit corporate context, and the reserved future image/context convention. Store them outside rubric evidence unless a later approved plan imports them as clearly labelled local smoke. No screenshot may claim GKE.

## Cleanup

Topic 00 acquires no Kind runtime and performs no teardown. Preserve the dedicated path convention for Topic 21; do not prune images, volumes, networks, or unrelated containers.

## Rubric table

| Cell | Planned proof | Scoring rule |
|---|---|---|
| `Sheet3!Row2` | Mandatory/unscored reproducible local toolchain and safe boundaries | Zero direct points |
| `Sheet3!E3:E62` | Cross-cutting supporting prerequisite | Zero direct points from this plan |
| `Sheet3!E32:E34` | Section 03 prerequisite evidence only | Zero here; earned only from strict Section 03 manifest |
| `Sheet3!E49` | Ansible VM is prohibited | Out of Scope; zero earned while workbook value remains 1 |
| `Sheet3!E48` | None from Kind | Requires later real Terraform/GCP proof |
| `Sheet3!E59:E62` | Context-safe architecture and test contracts | Requires later hash-bound implementation/evidence |

## Definition of Done

Pinned versions are verified or clearly recorded as unavailable; the corporate context is identified and untouched; the exact dedicated kubeconfig/cluster/context/image convention is recorded for Topic 21; no Kind runtime is created.

## Completion Record

| Field | Record |
|---|---|
| Status | Not started |
| Affected files | `tmp/edai2-plan/execution-v1/local/00-workstation-toolchain-context-safety.md` |
| Commands / exit codes | Record each command and numeric exit code, ending with `rtk git status --short --branch` |
| Evidence + SHA256 | Record each capture path and SHA256, or `no capture produced` |
| Screenshot QA | Record visibility of version, explicit context, and local-only label |
| Cleanup / runtime release | Record no runtime acquired and preserve the dedicated path convention for Topic 21 |
| Limitations | Local smoke is not GKE evidence |
| Successor handoff | Provide branch, tool inventory, and safe context name to plan 01 |
