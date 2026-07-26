# Topic 25: Jenkins Six-Workload Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build, scan, push, atomically deploy, smoke-test, and rollback-prove exactly six commit-SHA workloads through six distinct serialized Jenkins jobs.

**Architecture:** A zero-executor Jenkins controller schedules ephemeral rootless BuildKit agents under a capacity-one lock. One outer scheduler owns the sole evidence lease and runs three dependency waves, while each job executes `test -> build -> scan -> push_sha -> helm_atomic -> smoke_eval -> rollback_proof`. The same commit/base and immutable image digest bind CI, Helm, agents, machine evidence, and later screenshots.

**Tech Stack:** Jenkins, rootless BuildKit, Trivy, CycloneDX, Crane, Artifact Registry, Helm `--atomic`, GKE, Redpanda, Feast, Section 03 manifest, Python/`uv`.

## Metadata

| Field | Decision |
|---|---|
| Phase | Workload CI/CD deployment; execution topic 25 |
| Authoritative source tasks | `04.2_llm_design.md` Tasks 6 and 9 |
| Primary rubric cells | `Sheet3!E10:E12`, `Sheet3!E16:E18` |
| Prerequisites | Topics 22-24 complete; Section 03 verified manifest and Topic 21 local gates |
| Blocked successors | Topics 26-31 |
| Runtime owner | Outer CI owner until compare-and-swap handoff to `evidence-run`; `rubric-evidence`, maximum 6h |
| Execution class | `GCP-write/CI/deploy` |
| Branch rule | Same branch and commit across all six jobs; serial topic execution |

## Global Constraints

- Read and obey `C:\Users\oou1hc\.codex\RTK.md`; prefix every shell command with `rtk`.
- Fixed source hashes: Section 03 `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`; EDAI2 `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`; rubric at `tmp/rubic-check/Coursework Tracking (Public).xlsx` `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- Do not create/switch branches/worktrees, stage, or commit. Six jobs use one `EDAI2_COMMIT_SHA` and one verified `EDAI2_BASE_REF`.
- Require explicit context `gke_${GOOGLE_CLOUD_PROJECT}_us-central1-a_edai2`.
- Require `EDAI2_GKE_KUBECONFIG=tmp/edai2-gcp/kubeconfig` and `EDAI2_GKE_CONTEXT=gke_${GOOGLE_CLOUD_PROJECT}_us-central1-a_edai2`. Every `kubectl` call includes `--kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT`; every Helm call includes `--kubeconfig $env:EDAI2_GKE_KUBECONFIG --kube-context $env:EDAI2_GKE_CONTEXT`; every script that queries or mutates Kubernetes receives both values. Never use or change the default kubeconfig/current context.
- Safe-stop if project, billing, IAM, trial expiry, spend, recovery-sink status, verified Section 03 inputs, registry permission, Jenkins auth, or other external input is absent/stale/inconsistent.
- `EDAI2_TFVARS_PATH=tmp/edai2-gcp/coursework.auto.tfvars` remains untracked.
- Re-run live budget/capacity gates before `rubric-evidence`; lease TTL <=6h.
- Jenkins controller executors are zero; `edai2-buildkit-slot` capacity is one; peak BuildKit concurrency must be one with overlap count zero.
- Jenkins is the first and only image build/push/deploy path. No direct Helm bootstrap deploy.
- Images use commit-SHA tags and remote manifest digests; mutable tags fail.
- Each child must execute all seven ordered stages and release only its child reference in `post { always }`.
- Wave order is exactly `rag-index,feast-offline-writer,feast-online-writer | retrieval-agent,drift-agent | coordinator`.
- One bounded retry is allowed for one failed job only after documenting a transient cause; never rerun successful jobs to make UI evidence.
- Failed jobs leave only their rubric cells unsatisfied, block dependent waves, preserve already-good atomic releases, persist diagnostics, and suspend if the lease cannot be handed off.
- `Sheet3!E49` remains out of scope; no VM/Ansible/Cloud Build/hosted model.

## Read-Only Planning Refresh

1. `rtk git status --short --branch`
   - Expected: same branch lineage; no unexplained CI/chart/evidence overlap.
2. `rtk python -c "import hashlib; p=['tmp/edai2-plan/03_data_generator_improvement.md','tmp/edai2-plan/04.2_llm_design.md','tmp/rubic-check/Coursework Tracking (Public).xlsx']; print([hashlib.sha256(open(x,'rb').read()).hexdigest() for x in p])"`
   - Expected: fixed hashes.
3. `rtk rg -n "Status|platform_install.json|Handoff" tmp/edai2-plan/execution-v1/gcp/24-compact-platform-install.md`
   - Expected: private platform passed and suspended.
4. `rtk kubectl --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT cluster-info`
   - Expected: the dedicated kubeconfig resolves the approved GKE API; mismatch or failure is a safe stop.
5. `rtk uv run pytest tests/contract/llm/test_section03_contract.py -q`
   - Expected: verified Section 03 manifest/artifacts/hashes and exact `Sheet3!E32:E34` ownership pass.
6. `rtk git rev-parse HEAD`
   - Expected: exact value exported as `EDAI2_COMMIT_SHA`; no job may use another revision.

## Scope

- Validate six Jenkins definitions/build contexts and rendered Helm bundles.
- Resume private platform in `rubric-evidence` under one outer lease.
- Strictly bootstrap/read back Redpanda topics/schema.
- Import the verified Section 03 bundle through Workload Identity.
- Run six serialized CI jobs in three waves.
- Verify streaming-writer semantics and produce six machine records.
- Hand off the zero-refcount lease to `evidence-run` for Topics 26-27.

## Non-Goals

- No KEDA/HA/chat/registry/rollback live proof beyond each job's controlled stage; Topic 26 owns that.
- No Jenkins or UI screenshots; Topic 27 owns all six in one browser session.
- No public ingress.

## Exact File Map

| Role | Exact paths |
|---|---|
| Read | `containers/edai2/Dockerfile`, `containers/edai2/.dockerignore`, `containers/edai2/images.yaml` |
| Read | `ci/jenkins/jobs.yaml`, `ci/jenkins/change-map.yaml`, `ci/jenkins/buildkit-pod.yaml`, `ci/jenkins/pipeline.groovy` |
| Read | `ci/jenkins/Jenkinsfile.rag-index`, `ci/jenkins/Jenkinsfile.retrieval-agent`, `ci/jenkins/Jenkinsfile.drift-agent` |
| Read | `ci/jenkins/Jenkinsfile.coordinator`, `ci/jenkins/Jenkinsfile.feast-offline-writer`, `ci/jenkins/Jenkinsfile.feast-online-writer` |
| Read | `ci/jenkins/scripts/release.sh` |
| Read | `infra/helm/edai2/workloads/rag-index.yaml`, `infra/helm/edai2/workloads/retrieval.yaml`, `infra/helm/edai2/workloads/drift.yaml` |
| Read | `infra/helm/edai2/workloads/coordinator.yaml`, `infra/helm/edai2/workloads/feast-offline-writer.yaml`, `infra/helm/edai2/workloads/feast-online-writer.yaml` |
| Read/modify at implementation | `infra/kafka/topics.yaml`, `infra/kafka/schemas/customer_feature_updates-value.schema.json`, `src/vina_bim_shop/kafka/topics.py` |
| Read/modify at implementation | `src/vina_bim_shop/kafka/bootstrap.py`, `scripts/kafka/bootstrap_topics.py`, `infra/governance/recipes/kafka_topics.yml` |
| Execute | `scripts/gke/manage_profile.py`, `scripts/gke/check_budget.py`, `scripts/feast/load_section03.py` |
| Execute | `scripts/llm/smoke_release.py`, `scripts/qa/capture_edai2_evidence.py` |
| Read external/untracked | `tmp/edai2-gcp/kubeconfig` |
| Consume | `evidence/03_data_generator_improvement/section03_manifest.json` |
| Generate | `evidence/04_2_llm_design/streaming/bootstrap.json` |
| Generate | `evidence/04_2_llm_design/section03/import.json` |
| Generate | `evidence/04_2_llm_design/streaming/writers.json` |
| Generate | `evidence/04_2_llm_design/cicd/jobs.json` |
| Generate | `evidence/04_2_llm_design/rollbacks/helm.json` |

## Interfaces, Data Flow, and Failure Modes

Verified commit/base + Jenkins job map -> serialized BuildKit archive -> Trivy/SBOM -> SHA push -> digest verification -> atomic Helm release -> smoke/evaluation -> controlled rollback/restore -> one machine record.

Section 03 manifest -> local hash verification -> immutable KMS GCS prefix -> GKE Job re-verification -> PostgreSQL/Feast/Valkey activation -> deterministic feature event -> drift readiness.

Redpanda bootstrap -> exact topics/schema -> two independent consumer groups -> offline PostgreSQL and online Feast/Valkey -> separate checkpoints and DLQ records.

Failure modes include commit/base drift, lock overlap, stage omission/reordering, topic mismatch, Section 03 hash failure, digest mismatch, scan failure, Helm atomic rollback, smoke failure, child-ref leak, or wave-order violation. Any one invalidates the affected job record; no screenshot can repair it.

## Ordered Test-First Execution Tasks

### Task 1: Validate CI contracts before runtime

- [ ] Run `rtk uv run pytest tests/unit/test_edai2_repository_contract.py tests/unit/test_edai2_security_static.py tests/integration/llm/test_streaming_writers.py -q`.
  - Expected: exit 0; six jobs/images, seven stages, immutable pins, zero controller executors, capacity-one lock, wave map, no secret/direct-deploy path.
- [ ] Run `rtk uv run python scripts/gke/manage_profile.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT rubric-evidence --ttl 6h --render-only --image-tag testsha`.
  - Expected: six valid releases, RollingUpdate/probes/security/NetworkPolicy/KEDA, no `LoadBalancer`, capacity passes.
- [ ] Run `rtk kubectl --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT apply --dry-run=server -f tmp/edai2-gke/rendered/rubric-evidence.yaml`.
  - Expected: server-side schema validation passes without mutation.

### Task 2: Acquire the sole CI/evidence lease

- [ ] Run `rtk uv run python scripts/gke/check_budget.py --project $env:GOOGLE_CLOUD_PROJECT --trial-expires-at $env:EDAI2_TRIAL_EXPIRES_AT --current-spend-usd $env:EDAI2_CURRENT_SPEND_USD --spend-observed-at $env:EDAI2_SPEND_OBSERVED_AT --usage-ledger evidence/04_2_llm_design/gke/usage_ledger.json --envelope configs/gke/cost_envelope.yaml --requested-profile rubric-evidence --requested-ttl 6h --output evidence/04_2_llm_design/gke/cost_forecast.json`.
  - Expected: exit 0.
- [ ] Run `rtk kubectl --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT cluster-info`.
  - Expected: the dedicated kubeconfig resolves the approved GKE API without reading or changing the default context.
- [ ] Run `rtk uv run python scripts/gke/manage_profile.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT rubric-evidence --ttl 6h --acquire-session-lease --owner topic25-ci --commit-sha $env:EDAI2_COMMIT_SHA`.
  - Expected: sole owner/refcount zero, bounded expiry, platform restored privately, ingress disabled.

### Task 3: Provision immutable streaming prerequisites

- [ ] Run `rtk uv run python scripts/kafka/bootstrap_topics.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --execution gke-rpk --namespace edai2 --statefulset edai2-redpanda --bootstrap-server localhost:9092 --topics-file infra/kafka/topics.yaml --schema-file infra/kafka/schemas/customer_feature_updates-value.schema.json --strict --evidence evidence/04_2_llm_design/streaming/bootstrap.json`.
  - Expected: two exact topics, one partition, replication one, delete policy, seven-day retention, closed-schema hash, and successful read-back.
- [ ] Run the identical bootstrap command once more.
  - Expected: proved no-op; any existing mismatch fails rather than mutating.
- [ ] Run `rtk uv run python scripts/feast/load_section03.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --manifest evidence/03_data_generator_improvement/section03_manifest.json --strict --gcs-prefix $env:EDAI2_SECTION03_GCS_URI --if-generation-match-zero --submit-gke-job --publish-feature-events --wait --evidence evidence/04_2_llm_design/section03/import.json`.
  - Expected: local and in-cluster hashes pass, exact data activates atomically, one deterministic event publishes, drift `/readyz` passes, same-hash rerun is a no-op.

### Task 4: Run the six jobs once

- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --jenkins-trigger-all --commit-sha $env:EDAI2_COMMIT_SHA --verified-base $env:EDAI2_BASE_REF --reuse-session-lease --lease-owner topic25-ci --handoff-lease-to-evidence --evidence-owner evidence-run --resume-profile rubric-evidence --ttl 6h --waves "rag-index,feast-offline-writer,feast-online-writer|retrieval-agent,drift-agent|coordinator" --max-concurrent-buildkit 1 --strict --root evidence/04_2_llm_design`.
  - Expected: six unique SUCCESS records and build IDs, same commit/base, all seven stages, peak BuildKit one, dependency waves, digest equality, atomic releases, smoke/evaluation and rollback/restore.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --verify-jenkins-evidence evidence/04_2_llm_design/cicd/jobs.json --expected-commit $env:EDAI2_COMMIT_SHA --expected-jobs 6 --require-buildkit-serialization --require-wave-order --strict`.
  - Expected: exit 0; no direct Helm bootstrap or child-ref leak; lease handoff occurs only after all jobs terminal and refcount zero.

### Task 5: Verify writer behavior against deployed releases

- [ ] Run `rtk uv run python scripts/llm/smoke_release.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --streaming-writers --publish-valid-and-duplicate --publish-invalid --output evidence/04_2_llm_design/streaming/writers.json`.
  - Expected: one effective update in each destination, independent checkpoint-after-ack, duplicate no effect, and exactly two redacted DLQ records distinguished by consumer group.
- [ ] Run `rtk uv run pytest tests/integration/llm/test_streaming_writers.py -q --live-gke`.
  - Expected: exit 0.
- [ ] Run `rtk git status --short --branch`.
  - Expected: same branch/revision lineage and only request-scoped generated evidence/implementation changes.

## Evidence and Screenshot Ownership

Topic 25 owns `cicd/jobs.json`, `streaming/bootstrap.json`, `streaming/writers.json`, `section03/import.json`, and Helm rollback machine evidence. It owns no screenshot. Topic 27 must capture six existing job pages in one browser session and must not rebuild any job.

## Cleanup and Runtime Release

- On success, verify CAS lease ownership is `evidence-run`, expiry/commit unchanged, refcount zero; do not suspend because Topics 26-27 consume the handoff.
- On failure without handoff, run `rtk uv run python scripts/gke/manage_profile.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT suspended --release-session-lease --owner topic25-ci --record-failure evidence/04_2_llm_design/cicd/jobs.json`.
  - Expected: ingress disabled, both pools zero, good atomic releases preserved.
- Delete transient BuildKit pods and local archives; keep immutable registry images/evidence.

## Rubric Traceability

| Cell | Points | Topic 25 primary gate |
|---|---:|---|
| `Sheet3!E10` | 1 | retrieval FastAPI/Pydantic/probes pass in release smoke |
| `Sheet3!E11` | 1 | retrieval async contract passes in deployed smoke |
| `Sheet3!E12` | 2 | retrieval streamable-HTTP MCP Helm RollingUpdate/atomic fallback |
| `Sheet3!E16` | 1 | drift FastAPI/Pydantic/probes pass in release smoke |
| `Sheet3!E17` | 1 | drift async feature-read contract passes |
| `Sheet3!E18` | 2 | drift streamable-HTTP MCP Helm RollingUpdate/atomic fallback |

The six job records are supporting inputs for Topic 27's sole ownership of `Sheet3!E35:E40`; Topic 25 does not claim those cells.

## Definition of Done

- [ ] Preflight, Section 03, budget, capacity, context, and immutable topic/schema gates pass.
- [ ] Six jobs use one branch/base/commit, unique IDs, exact stages, one BuildKit pod, and correct waves.
- [ ] Six digests/releases/smokes/rollbacks and writer semantics are hash-bound.
- [ ] No successful job is rerun for future screenshots.
- [ ] Lease is safely handed to `evidence-run` or failure path suspends.
- [ ] `rtk git status --short --branch` is recorded in final acceptance and Completion Record.

## Completion Record

- **Status:** Not started; no CI/CD cell is claimed.
- **Branch / revision:** Record via `rtk git status --short --branch` and `rtk git rev-parse HEAD`; none recorded yet.
- **Affected files:** None at plan-authoring time.
- **Command / exit-code log:** No execution commands recorded.
- **Evidence / SHA-256 log:** No CI/import/writer evidence recorded.
- **Screenshot QA:** No screenshot owned; six future captures must use existing job IDs.
- **Cleanup / runtime release:** No lease held by this plan artifact.
- **Limitations:** Live KEDA/registry/chat/rollback contextual proof remains Topic 26.
- **Handoff:** Topics 26-27 require successful `evidence-run` lease handoff, six machine records, common commit, and remaining TTL.
