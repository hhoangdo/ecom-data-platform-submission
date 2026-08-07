# 16 — Six Images and Jenkins CI Definitions

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Author and statically prove the Task 6 delivery system: six exact Jenkins jobs/Jenkinsfiles and six non-root Docker targets/build contexts, serialized rootless BuildKit, pinned scan/push tooling, exact stage order, robust change mapping, and sentinel Helm rendering without any build, push, or deploy.

**Architecture:** Jenkins controller executors are zero. A global `edai2-buildkit-slot` lock of capacity one serializes ephemeral rootless BuildKit pods. Each job creates one archive, scans that exact archive before push, computes distinct archive SHA and registry manifest digest, pushes only commit SHA, then performs atomic Helm/smoke/rollback stages later.

**Tech Stack:** Jenkins Groovy, Docker multi-stage builds, rootless BuildKit, Trivy 0.70.0, Crane 0.21.7, Helm rendering, pytest.

## Metadata

| Field | Locked value |
|---|---|
| Phase | Local/static CI Topic 16 |
| Source task | `tmp/edai2-plan/04.2_llm_design.md` Task 6 CI portion |
| Sheet3 support | `Sheet3!E35:E40` |
| Predecessor Completion Record | `tmp/edai2-plan/execution-v1/local/15-evaluation-test-quality-load.md` must be `Complete` |
| Blocked successor | `tmp/edai2-plan/execution-v1/local/17-terraform-vault-iac-static.md` |
| Runtime ownership | Local static test/render session |
| Class | Local/static; no build/push/deploy |

## Locked planning basis

Read `C:\Users\oou1hc\.codex\RTK.md`; verify hashes `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`, `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`, and `tmp/rubic-check/Coursework Tracking (Public).xlsx` `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.

## Global constraints

Use current branch, serial work, `apply_patch`, `rtk uv run` for developer recipes, and `rtk make` for operator recipes. CI scripts themselves must not invoke `rtk`. Topic 08 owns baseline dependencies; run `rtk uv lock --check` and treat a missing prerequisite as a `Partial` predecessor defect instead of editing dependencies. Topic 16 is the sole owner of the reusable `service-agent` and `worker` chart templates; Topics 18 and 19 may lint/render/consume them but never edit them. No staging/commit, Docker build/push, Jenkins trigger, Helm apply, GCP, auto-prune/stop. One retry then `Partial`.

## Read-only current-state refresh

- [ ] Run `rtk git status --short --branch`. Expected: branch and pre-existing changes recorded.
- [ ] Run `rtk proxy certutil -hashfile tmp/edai2-plan/03_data_generator_improvement.md SHA256`. Expected: output contains `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`.
- [ ] Run `rtk proxy certutil -hashfile tmp/edai2-plan/04.2_llm_design.md SHA256`. Expected: output contains `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`.
- [ ] Run `rtk proxy certutil -hashfile "tmp/rubic-check/Coursework Tracking (Public).xlsx" SHA256`. Expected: output contains `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- [ ] Run `rtk proxy powershell -NoProfile -Command "Select-String -Path tmp/edai2-plan/execution-v1/local/15-evaluation-test-quality-load.md -Pattern '^Status: Complete|\| Status \| Complete \|'"`. Expected: completed predecessor.
- [ ] Run `rtk uv lock --check`. Expected: exit 0 with the Topic 08-owned baseline lockfile unchanged.
- [ ] Run `rtk git diff --check`. Expected: exit 0.

## Scope and non-goals

In scope: Dockerfile/image catalog, six Jenkinsfiles/jobs, change map, rootless pod, shared pipeline/release script, static tests, sentinel chart render.

Non-goals: actual image build, archive scan, registry push, Jenkins run, Helm deploy, credentials, GCP, screenshots.

## Exact file map

| Action | Exact path | Responsibility |
|---|---|---|
| Create | `containers/edai2/Dockerfile` | One pinned base and six non-root targets |
| Create | `containers/edai2/.dockerignore` | Minimal build context exclusions |
| Create | `containers/edai2/images.yaml` | Target/context/command/repository/release mapping |
| Create | `ci/jenkins/jobs.yaml` | Six exact job names and Jenkinsfiles |
| Create | `ci/jenkins/change-map.yaml` | Single/shared/rename/delete/unknown/force-all selection |
| Create | `ci/jenkins/buildkit-pod.yaml` | Ephemeral rootless pod, serialization label |
| Create | `ci/jenkins/pipeline.groovy` | Shared ordered stage implementation |
| Create | `ci/jenkins/scripts/release.sh` | Scan/push/atomic Helm/smoke/rollback functions; no rtk |
| Create | `ci/jenkins/Jenkinsfile.rag-index` | `edai2-rag-index` |
| Create | `ci/jenkins/Jenkinsfile.retrieval-agent` | `edai2-retrieval-agent` |
| Create | `ci/jenkins/Jenkinsfile.drift-agent` | `edai2-drift-agent` |
| Create | `ci/jenkins/Jenkinsfile.coordinator` | `edai2-coordinator` |
| Create | `ci/jenkins/Jenkinsfile.feast-offline-writer` | `edai2-feast-offline-writer` |
| Create | `ci/jenkins/Jenkinsfile.feast-online-writer` | `edai2-feast-online-writer` |
| Create | `infra/helm/edai2/service-agent/Chart.yaml`, `infra/helm/edai2/service-agent/values.yaml`, `infra/helm/edai2/service-agent/templates/deployment.yaml`, `infra/helm/edai2/service-agent/templates/service.yaml`, `infra/helm/edai2/service-agent/templates/scaledobject.yaml`, `infra/helm/edai2/service-agent/templates/networkpolicy.yaml`, `infra/helm/edai2/service-agent/templates/serviceaccount.yaml`, `infra/helm/edai2/service-agent/templates/sandboxagent.yaml`, `infra/helm/edai2/service-agent/templates/remotemcpserver.yaml`, `infra/helm/edai2/service-agent/templates/agentgateway-policy.yaml` | Minimal reusable service/agent chart needed for sentinel CI rendering |
| Create | `infra/helm/edai2/worker/Chart.yaml`, `infra/helm/edai2/worker/values.yaml`, `infra/helm/edai2/worker/templates/deployment.yaml`, `infra/helm/edai2/worker/templates/scaledobject.yaml`, `infra/helm/edai2/worker/templates/networkpolicy.yaml`, `infra/helm/edai2/worker/templates/serviceaccount.yaml` | Minimal reusable writer chart needed for sentinel CI rendering |
| Modify | `tests/unit/test_edai2_repository_contract.py` | Add CI/image/map/stage/render assertions to the Topic 08 repository-contract scaffold |

## Interfaces, data flow, and failure modes

Inputs are Topic 15's verified test scope/dependency lock, a verified-base-to-commit git diff, six image definitions, Topic 14 agent values, and sentinel render tag `testsha`. The static output is six catalog entries/Jenkinsfiles, one serialized rootless builder contract, one archive-to-scan-to-push identity chain per target, the only reusable `service-agent` and `worker` chart templates, and deterministic path fan-out. Topic 17 consumes the security boundary; Topic 18 lints/renders and Topic 19 consumes these charts without editing templates; the later Jenkins runtime consumes all six definitions.

Unknown/unclassified runtime paths select all six jobs; invalid verified base, missing/duplicate job, target/context mismatch, concurrent BuildKit path, checksum mismatch, scan-after-push, remote/archive digest mismatch, mutable tag, recursive `rtk`, secret literal, stage-order drift, failed sentinel render, or unbuilt-tag deployment fails closed before any push/deploy.

## Exact image and CI contract

Targets/build contexts are exactly `rag_index`, `retrieval_agent`, `drift_agent`, `coordinator`, `feast_offline_writer`, and `feast_online_writer`, each mapped to its own command, Artifact Registry repository and Helm release.

| Jenkinsfile | Docker target | Build context |
|---|---|---|
| `ci/jenkins/Jenkinsfile.rag-index` | `rag_index` | repository root `.` |
| `ci/jenkins/Jenkinsfile.retrieval-agent` | `retrieval_agent` | repository root `.` |
| `ci/jenkins/Jenkinsfile.drift-agent` | `drift_agent` | repository root `.` |
| `ci/jenkins/Jenkinsfile.coordinator` | `coordinator` | repository root `.` |
| `ci/jenkins/Jenkinsfile.feast-offline-writer` | `feast_offline_writer` | repository root `.` |
| `ci/jenkins/Jenkinsfile.feast-online-writer` | `feast_online_writer` | repository root `.` |

Controller executors = 0; BuildKit max concurrency = 1. Trivy 0.70.0 checksum is `8b4376d5d6befe5c24d503f10ff136d9e0c49f9127a4279fd110b727929a5aa9`; Crane 0.21.7 checksum is `1a57bc98207fa1c0d04bf760699099e26f8383499bfd55b99c1b919a928a7230`.

The Dockerfile base is literally `python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c`; the ephemeral rootless builder is literally `moby/buildkit:v0.20.2-rootless@sha256:cb5bb371545222c430528556acfdf424144b69897f5deaad391bd227187e90df`. These are real OCI index digests verified before this plan correction; tests reject an unpinned tag, all-zero/example digest, variable placeholder, or a differing literal.

Stage order is exactly `test -> build -> scan -> push_sha -> helm_atomic -> smoke_eval -> rollback_proof`. Scan-before-push operates on the same archive identity. Archive file SHA-256 and registry manifest digest are distinct typed fields. Zero CRITICAL and no unreviewed GPL-3.0/AGPL-3.0 are required.

Each target produces one Docker archive and file SHA-256. Trivy runs vulnerability, secret, and license scans against that exact archive, rejects a vulnerability database older than 24 hours, requires zero `CRITICAL` vulnerabilities and no unreviewed GPL-3.0/AGPL-3.0 package, and emits both JSON and CycloneDX reports. Pinned Crane computes the archive manifest digest. Workload Identity is the only permitted registry authentication/push path; the exact same archive is pushed only as the full lowercase 40-hex checkout commit tag, and the archived manifest digest must equal the remote registry digest before Helm can run.

The change map is exact: knowledge/indexing/Airflow-RAG/Feast-knowledge paths select RAG; retrieval API/MCP/safety/workload paths select retrieval; Section 03 ingestion/drift API/MCP/workload paths select drift; inference/routing/coordinator/kagent/agentregistry paths select coordinator; each writer schema/workload selects only its matching writer. Shared contracts/config, Docker/image map, chart/pipeline, gateway/security/observability, and unknown EDAI2 runtime paths fan out to all six; `EDAI2_FORCE_ALL=true` also selects all six. Tests cover single path, shared path, deletion, rename old+new paths, unknown runtime path, force-all, and each writer's own schema/workload. CI scripts reject recursive `rtk`, mutable tags, Cloud Build, static registry credentials, and unbuilt tags.

## Ordered test-first execution

- [ ] Add red CI contracts and run `rtk uv run pytest tests/unit/test_edai2_repository_contract.py -q`. Expected: nonzero until six jobs/targets, lock, pins, stages and map exist.
- [ ] Add Docker/image catalog and run `rtk uv run pytest tests/unit/test_edai2_repository_contract.py -q -k "docker or image"`. Expected: exit 0; six non-root targets/contexts, the two exact real digest pins, vulnerability/secret/license scans, <=24-hour database freshness, JSON/CycloneDX output, Workload Identity-only push, and archive/remote manifest-digest equality.
- [ ] Add Jenkins catalog/pod/pipeline/Jenkinsfiles and run `rtk uv run pytest tests/unit/test_edai2_repository_contract.py -q -k "jenkins or buildkit or stage"`. Expected: exit 0; controller 0, concurrency 1, six exact pages and ordered stages.
- [ ] Add change-map cases and run `rtk uv run pytest tests/unit/test_edai2_repository_contract.py -q -k "change_map"`. Expected: exit 0 for single/shared/deletion/rename/unknown/force-all.
- [ ] Run all six sentinel renders: `rtk helm template retrieval infra/helm/edai2/service-agent -f infra/helm/edai2/values/retrieval-agent.yaml --set image.tag=testsha --set-string substrate.bucketName=edai2-sentinel-bucket`; `rtk helm template drift infra/helm/edai2/service-agent -f infra/helm/edai2/values/drift-agent.yaml --set image.tag=testsha --set-string substrate.bucketName=edai2-sentinel-bucket`; `rtk helm template coordinator infra/helm/edai2/service-agent -f infra/helm/edai2/values/coordinator-agent.yaml --set image.tag=testsha --set-string substrate.bucketName=edai2-sentinel-bucket`; `rtk helm template rag-index infra/helm/edai2/worker --set image.tag=testsha --set-string image.repository=example.invalid/edai2/rag-index --set-string workload.name=rag-index`; `rtk helm template feast-offline-writer infra/helm/edai2/worker --set image.tag=testsha --set-string image.repository=example.invalid/edai2/feast-offline-writer --set-string workload.name=feast-offline-writer`; and `rtk helm template feast-online-writer infra/helm/edai2/worker --set image.tag=testsha --set-string image.repository=example.invalid/edai2/feast-online-writer --set-string workload.name=feast-online-writer`. Expected: all six exit 0, service snapshots contain the sentinel bucket plus `retrieval|drift|coordinator` logical keys, each render is distinct, no chart outside Topic 16 is created or modified, and nothing is applied. Literal `testsha` and `example.invalid` are permitted only in this render-only step.
- [ ] Run `rtk uv run pytest tests/unit/test_edai2_repository_contract.py -q` and `rtk git diff --check`. Expected: both exit 0; no image, registry artifact or Helm release exists.

## Evidence, cleanup, rubric, and DoD

Topic 16 owns static test and six sentinel-render hashes. It owns no Jenkins screenshot or build. The later evidence owner captures the six distinct existing Jenkins job/build pages in one browser session, binds their distinct build IDs to the common commit, and never rebuilds merely to obtain screenshots. Remove only render temp files; no Docker/Jenkins runtime is started.

| Sheet3 cell | Local proof | Deferred proof |
|---|---|---|
| `Sheet3!E35:E40` | six definitions, scan/push/stage/map assertions | six successful Jenkins page/build records |

## Definition of Done

Six exact jobs/targets, controller zero, serialization one, exact digest-pinned Python/BuildKit images, pinned checksum tools, all three scan classes with fresh databases and JSON/CycloneDX outputs, Workload Identity-only push, archive/remote digest equality, stage order, exact change-map fan-out, no-rtk CI, and all six sentinel renders are statically valid; no build/push/deploy occurred.

## Completion Record

| Field | Execution value |
|---|---|
| Status | Not started |
| Current branch/status | Record final `rtk git status --short --branch` |
| Affected files | Record Topic 16 exact paths |
| Commands and exit codes | Record focused/full CI tests and sentinel renders |
| Evidence hashes | Record test/render SHA-256 |
| Screenshot QA | Not captured; six pages deferred |
| Cleanup/runtime release | Record render temp cleanup; no runtime |
| Limitations | Record future build/push/deploy evidence |
| Handoff | `tmp/edai2-plan/execution-v1/local/17-terraform-vault-iac-static.md` |
