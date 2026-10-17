# Topic 25: Jenkins Six-Workload Deployment Implementation Plan

> **For any agent (Codex / opencode / Claude / etc):** Work task-by-task in one session. Steps use checkbox (`- [ ]`) tracking. Auto-run without asking; only stop on safe-stop gates below.

> **Study-only simplified run (first iteration, overrides strict gates below):**
> - Repo root = current checkout (`<repo-root>`), not `C:\Users\oou1hc\...`. Use `rtk` prefix if installed, else run commands directly.
> - Auto-run end-to-end; no mid-run approvals. Only safe stops: budget/spend/trial fail, missing bundle/inputs, wrong cluster context, or capacity over cap. Record blocker and suspend.
> - Check source hashes + `git status` once at start (not before every command). Reuse fresh (<24h) preflight/forecast if unchanged.
> - One lease per topic. Set `EDAI2_KUBECONFIG`/`EDAI2_CONTEXT` once, reuse. Run six jobs via single trigger-all; don't babysit per-job approvals.
> - Happy-path first: six SUCCESS + digests + smoke wins. BuildKit overlap-zero forensics, strict 7-stage audit may stay `Partial` — record measured value, hand off, don't rerun good jobs.
> - Study-mode relaxation v1 (study-first, single-agent): plan-doc SHA pins and manifest-byte equality are LOG-ONLY — record computed vs listed values, never block. `bundle_id` string match still enforced. Image remote-digest equality stays HARD.
> - Minimal CI: per-job `build -> push-SHA -> helm_atomic -> smoke` passes the job; `test`/`scan`/`rollback_proof` are best-effort and recorded. Trivy findings are logged; only a `CRITICAL` with a known exploit path blocks.
> - If Jenkins trigger/verify flags are absent from the checked-in scripts, deploy via direct `helm upgrade --install --atomic` with commit-SHA tags; record as study-debt in the Completion Record; do not claim `Sheet3!E35:E40`.
> - Safety gates stay HARD: live budget preflight, exact kubeconfig/context, capacity ceilings, lowercase 40-hex commit. No mid-run approvals; one lease per topic; reuse fresh (<24h) preflight/forecast.

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

- Use `rtk` prefix if installed, else run commands directly. Repo root = current checkout (`<repo-root>`).
- Fixed source hashes: Section 03 `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`; EDAI2 `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`; rubric at `tmp/rubic-check/Coursework Tracking (Public).xlsx` `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- Do not create/switch branches/worktrees, stage, or commit. Six jobs use one `EDAI2_COMMIT_SHA` and one verified `EDAI2_BASE_REF`.
- Consume the completed local implementation. If a source/IaC/chart defect appears, capture it, release or suspend any owned runtime, mark this topic `Partial`, and return it to the owning local topic; do not patch implementation during a live cloud lease.
- Require explicit context `gke_${GOOGLE_CLOUD_PROJECT}_us-central1-a_edai2`.
- Require `EDAI2_GKE_KUBECONFIG=tmp/edai2-gcp/kubeconfig` and `EDAI2_GKE_CONTEXT=gke_${GOOGLE_CLOUD_PROJECT}_us-central1-a_edai2`. Every `kubectl` call includes `--kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT`; every Helm call includes `--kubeconfig $env:EDAI2_GKE_KUBECONFIG --kube-context $env:EDAI2_GKE_CONTEXT`; every script that queries or mutates Kubernetes receives both values. Never use or change the default kubeconfig/current context.
- Run a fresh redacted `check_budget.py --live-external-preflight` gate before mutation. Safe-stop if project lifecycle, billing linkage, exact IAM permissions, trial expiry, spend, budget notification target, approved recovery-sink attestation, DNS, verified Section 03 inputs, registry permission, Jenkins auth, or another external input is absent/stale/inconsistent.
- `EDAI2_TFVARS_PATH` is absolute, resolves exactly to this repository's `tmp/edai2-gcp/coursework.auto.tfvars`, and remains untracked.
- Re-run live budget/capacity gates before `rubric-evidence`; lease TTL <=6h.
- Jenkins controller executors are zero; `edai2-buildkit-slot` capacity is one; peak BuildKit concurrency must be one with overlap count zero.
- Jenkins is the first and only image build/push/deploy path. No direct Helm bootstrap deploy.
- Images use commit-SHA tags and remote manifest digests; mutable tags fail.
- Each child must execute all seven ordered stages and release only its child reference in `post { always }`.
- Wave order is exactly `rag-index,feast-offline-writer,feast-online-writer | retrieval-agent,drift-agent | coordinator`.
- One bounded retry is allowed for one failed job only after documenting a transient cause; never rerun successful jobs to make UI evidence.
- Failed jobs leave only their rubric cells `Partial` or `Missing`, block dependent waves, preserve already-good atomic releases, persist diagnostics, and suspend if the lease cannot be handed off.
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
   - Expected: exact lowercase 40-hex value exported as `EDAI2_COMMIT_SHA`; any abbreviated, uppercase, non-hex, or different job revision is a safe stop.

## Scope

- Validate six Jenkins definitions/build contexts and rendered Helm bundles.
- Resume private platform in `rubric-evidence` under one outer lease.
- Strictly bootstrap/read back Redpanda topics/schema.
- Upload and fully verify the immutable Section 03 bundle through Workload Identity without activating it; the drift Jenkins/Helm release is the sole activation owner.
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
| Read/consume | `infra/kafka/topics.yaml`, `infra/kafka/schemas/customer_feature_updates-value.schema.json`, `src/vina_bim_shop/kafka/topics.py` |
| Read/consume | `src/vina_bim_shop/kafka/bootstrap.py`, `scripts/kafka/bootstrap_topics.py`, `infra/governance/recipes/kafka_topics.yml` |
| Execute | `scripts/gke/manage_profile.py`, `scripts/gke/check_budget.py`, `scripts/feast/load_section03.py` |
| Execute | `scripts/llm/smoke_release.py`, `scripts/qa/capture_edai2_evidence.py` |
| Read external/untracked | `tmp/edai2-gcp/kubeconfig` |
| Consume | `evidence/03_data_generator_improvement/section03_manifest.json` |
| Generate immutable gate evidence | `evidence/04_2_llm_design/gke/gcp_preflight_topic25.json`, `evidence/04_2_llm_design/gke/cost_forecast_topic25.json` |
| Update append-only | `evidence/04_2_llm_design/gke/usage_ledger.json` |
| Generate | `evidence/04_2_llm_design/streaming/bootstrap.json` |
| Generate | `evidence/04_2_llm_design/section03/upload.json` |
| Generate by drift Jenkins/Helm release only | `evidence/04_2_llm_design/section03/import.json` |
| Generate | `evidence/04_2_llm_design/streaming/writers.json` |
| Generate | `evidence/04_2_llm_design/cicd/jobs.json` |
| Generate | `evidence/04_2_llm_design/rollbacks/jenkins_helm_stage.json` |

## Interfaces, Data Flow, and Failure Modes

Verified commit/base + Jenkins job map -> serialized BuildKit archive -> Trivy/SBOM -> SHA push -> digest verification -> atomic Helm release -> smoke/evaluation -> controlled rollback/restore -> one machine record.

Section 03 manifest -> local hash verification -> immutable KMS GCS prefix create-only upload/read-back -> drift Jenkins/Helm release consumes verified upload -> its activation Job re-verifies -> PostgreSQL/Feast/Valkey activation -> deterministic feature event -> drift readiness. No pre-CI path creates an import Job, writes runtime stores, emits the feature event, or probes drift readiness; the drift release is the sole activation owner.

The rag-index Jenkins job may build a noncanonical `ci-bootstrap` index only to smoke its deployment. That index is versioned with the CI commit and cannot be promoted or cited for `Sheet3!E8:E9`; Topic 28 later creates the distinct `canonical-evidence` index and owns those rubric cells.

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

- [ ] Run `rtk uv run python scripts/gke/check_budget.py --project $env:GOOGLE_CLOUD_PROJECT --billing-account-env GOOGLE_BILLING_ACCOUNT --budget-notification-target-env EDAI2_BUDGET_NOTIFICATION_TARGET --recovery-sink-env EDAI2_VAULT_RECOVERY_SINK --recovery-sink-attestation $env:EDAI2_RECOVERY_SINK_ATTESTATION --required-permissions configs/gke/required_permissions.json --dns-probes acme-staging-v02.api.letsencrypt.org,huggingface.co,storage.googleapis.com --live-external-preflight --preflight-output evidence/04_2_llm_design/gke/gcp_preflight_topic25.json --trial-expires-at $env:EDAI2_TRIAL_EXPIRES_AT --current-spend-usd $env:EDAI2_CURRENT_SPEND_USD --spend-observed-at $env:EDAI2_SPEND_OBSERVED_AT --usage-ledger evidence/04_2_llm_design/gke/usage_ledger.json --envelope configs/gke/cost_envelope.yaml --requested-profile rubric-evidence --requested-ttl 6h --output evidence/04_2_llm_design/gke/cost_forecast_topic25.json`.
  - Expected: exit 0; live project/billing/IAM/notification/recovery-sink/DNS/trial/spend/capacity gates pass and output contains only redacted hashes, booleans, timestamps, and bounded numeric values.
- [ ] Run `rtk kubectl --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT cluster-info`.
  - Expected: the dedicated kubeconfig resolves the approved GKE API without reading or changing the default context.
- [ ] Run `rtk uv run python scripts/gke/manage_profile.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT rubric-evidence --ttl 6h --acquire-session-lease --owner topic25-ci --commit-sha $env:EDAI2_COMMIT_SHA`.
  - Expected: sole owner/refcount zero, bounded expiry, platform restored privately, ingress disabled.

### Task 3: Provision immutable streaming prerequisites

- [ ] Run `rtk uv run python scripts/kafka/bootstrap_topics.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --execution gke-rpk --namespace edai2 --statefulset edai2-redpanda --bootstrap-server localhost:9092 --topics-file infra/kafka/topics.yaml --schema-file infra/kafka/schemas/customer_feature_updates-value.schema.json --strict --evidence evidence/04_2_llm_design/streaming/bootstrap.json`.
  - Expected: two exact topics, one partition, replication one, delete policy, seven-day retention, closed-schema hash, and successful read-back.
- [ ] Run the identical bootstrap command once more.
  - Expected: proved no-op; any existing mismatch fails rather than mutating.
- [ ] Run `rtk uv run python scripts/feast/load_section03.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --manifest evidence/03_data_generator_improvement/section03_manifest.json --strict --gcs-prefix $env:EDAI2_SECTION03_GCS_URI --if-generation-match-zero --upload-only --verify-upload --defer-activation-to-release drift --evidence evidence/04_2_llm_design/section03/upload.json`.
  - Expected: local hashes/schema/fingerprint pass and the immutable bundle is create-only uploaded and read back. An existing identical bundle is reused only after full hash/schema/fingerprint verification; a same-ID content mismatch fails. No GKE import Job, PostgreSQL/Feast/Valkey write, feature event, or drift readiness probe occurs.

### Task 4: Run the six jobs once

- [ ] Run `rtk powershell -NoProfile -Command 'if ($env:EDAI2_COMMIT_SHA -cnotmatch "^[0-9a-f]{40}$") { exit 25 }; & rtk uv run python scripts/qa/capture_edai2_evidence.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --jenkins-trigger-all --commit-sha $env:EDAI2_COMMIT_SHA --verified-base $env:EDAI2_BASE_REF --reuse-session-lease --lease-owner topic25-ci --handoff-lease-to-evidence --evidence-owner evidence-run --resume-profile rubric-evidence --ttl 6h --waves "rag-index,feast-offline-writer,feast-online-writer|retrieval-agent,drift-agent|coordinator" --max-concurrent-buildkit 1 --section03-upload-evidence evidence/04_2_llm_design/section03/upload.json --drift-activation-owner jenkins-helm --rag-index-purpose ci-bootstrap --rag-index-version "ci-bootstrap-$($env:EDAI2_COMMIT_SHA)" --jenkins-rollback-output evidence/04_2_llm_design/rollbacks/jenkins_helm_stage.json --strict --root evidence/04_2_llm_design; exit $LASTEXITCODE'`.
  - Expected: six unique SUCCESS records and build IDs, same commit/base, all seven stages, peak BuildKit one, dependency waves, digest equality, atomic releases, smoke/evaluation and rollback/restore. The drift release alone activates Section 03 under Helm `--atomic`, writes `section03/import.json`, publishes the single deterministic event, and proves `/readyz`; no second import runs. The rag-index release records a commit-bound `ci-bootstrap` index that is not promoted as canonical evidence.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --verify-jenkins-evidence evidence/04_2_llm_design/cicd/jobs.json --expected-commit $env:EDAI2_COMMIT_SHA --expected-jobs 6 --require-buildkit-serialization --require-wave-order --require-single-section03-activation jenkins-helm --section03-upload evidence/04_2_llm_design/section03/upload.json --section03-import evidence/04_2_llm_design/section03/import.json --require-rag-index-purpose ci-bootstrap --require-rag-index-version "ci-bootstrap-$($env:EDAI2_COMMIT_SHA)" --require-lowercase-40hex-commit --forbid-rag-index-purpose canonical-evidence --strict`.
  - Expected: exit 0; upload precedes the sole drift-owned activation, no duplicate import/direct Helm bootstrap/child-ref leak exists, and lease handoff occurs only after all jobs are terminal with refcount zero.

### Task 5: Verify writer behavior against deployed releases

- [ ] Run `rtk uv run python scripts/llm/smoke_release.py --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT --streaming-writers --publish-valid-and-duplicate --publish-invalid --output evidence/04_2_llm_design/streaming/writers.json`.
  - Expected: one effective update in each destination, independent checkpoint-after-ack, duplicate no effect, and exactly two redacted DLQ records distinguished by consumer group.
- [ ] Run `rtk uv run pytest tests/integration/llm/test_streaming_writers.py -q --live-gke --kubeconfig $env:EDAI2_GKE_KUBECONFIG --context $env:EDAI2_GKE_CONTEXT`.
  - Expected: exit 0.
- [ ] Run `rtk git status --short --branch`.
  - Expected: same branch/revision lineage and only request-scoped generated evidence/implementation changes.

## Evidence and Screenshot Ownership

Topic 25 owns `cicd/jobs.json`, `streaming/bootstrap.json`, `streaming/writers.json`, `section03/upload.json`, the drift-release-produced `section03/import.json`, and job-stage rollback evidence at `rollbacks/jenkins_helm_stage.json`. It owns no screenshot. Topic 26 separately owns the injected live Helm rollback proof at `rollbacks/helm.json`; neither topic overwrites the other's record. Topic 25's `ci-bootstrap` RAG index is explicitly noncanonical; Topic 28 owns the later canonical evidence index. Topic 27 must capture six existing job pages in one browser session and must not rebuild any job.

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

- [ ] Preflight, Section 03 create-only upload/read-back, budget, capacity, context, and immutable topic/schema gates pass.
- [ ] Drift Jenkins/Helm is the sole Section 03 activation owner; no duplicate import exists, and CI-bootstrap RAG is distinct from the later canonical evidence index.
- [ ] Six jobs use one branch/base/commit, unique IDs, exact stages, one BuildKit pod, and correct waves.
- [ ] Six digests/releases/smokes/rollbacks and writer semantics are hash-bound.
- [ ] No successful job is rerun for future screenshots.
- [ ] Lease is safely handed to `evidence-run` or failure path suspends.
- [ ] `rtk git status --short --branch` is recorded in final acceptance and Completion Record.

## Completion Record

- **Status:** Partial (2026-10-15 ~19:05Z). Accepted Partials carried: Section 03 chain
  (upload.json partial, import.json deferred), Jenkins-automation study-debt (direct-Helm
  path never exercised, Sheet3!E35:E40 unclaimed). New: builder systematic failure, 0/6
  verified images, 0/6 deploys. No green-job reruns; no secrets in evidence/logs.
- **Branch / revision:** `feature/implement-edai2`, HEAD
  `714abc7f96b4f10125c2dfa68d1d336f48570b39` (6 ahead of origin, no stage/commit/push;
  only pre-existing untracked `infra/feast-registry/data/`,
  `infra/feast-registry/feast-registry-secret.yaml`).
- **Builder (pilot rag-index, bounded retry consumed):** run_pilot.py (sleep 5400,
  100x60s poll, req 2m/1Gi lim 4CPU/16Gi, kaniko v1.23.2-debug, platform-node pin,
  4-segment `HOST/edai2-rag-index/edai2-rag-index:714abc7...`, ctx-rag-index.tar).
  Pod `edai2-kaniko-study` 18:21:42Z Running, executor RUNNING, build.log 61.4K (pip-install
  phase done); pod Succeeded ~18:38Z, study-builds.json `partial/poll_end=pod-phase-Succeeded/
  terminated=Completed/pushed=null/remote=null/digest_verified=false/log_tail=null`,
  no `build-*.log` preserved. Identical signature to attempt #4 (sleep 2400) → sleep-independent,
  systematic, not proven transient; coincident 18:16-18:24Z capacity storm (llmd-primary landing,
  feast-redis/gateway preempted, FailedScheduling Insufficient cpu, cross-workload liveness
  timeouts). 16Gi OOM question UNANSWERED (build died in pip phase). No further retries:
  one-bounded-retry consumed, cause unproven, 6-serialized-builds infeasible in remaining TTL,
  retry churn risks healthy workloads.
- **AR observation (unverified, owning-topic decision):**
  `edai2-rag-index/edai2-rag-index:714abc7f96b4f10125c2dfa68d1d336f48570b39` EXISTS,
  remote digest `sha256:96766d9ca6c60c4dcb476cbba2e46779f1e30b3de97f1c32c2ccc980d4114b2c`
  — pushed by a dying build, NO local digest to compare, digest_verified=false, NOT deployed.
  Other 5 workload repos EMPTY. `edai2-coordinator/substrate-api-topic24` (topic24-c1f70d0e3d215712
  + .sbom) KEPT. Probe `edai2-rag-index/kaniko-probe:2` RETAINED: repo has tag immutability,
  tag+digest delete both FAILED_PRECONDITION (45MB, 2026-10-15T05:35:43Z).
- **Deploys:** 0/6 — blocked (deploy_all.py gates on digest_verified; none verified).
  No workload Helm releases exist; platform releases untouched.
- **Smoke/writers:** not run (nothing deployed). `writers.json`/`jobs.json` absent (recorded
  honestly, may stay partial). `upload.json` partial stands (792B); `import.json` deferred
  (drift activation owner never deployed).
- **Suspend (verified):** 54/54 workloads (incl. llmd-primary) scaled to 0; pools platform+spot
  setSize 0, MIG targets [0],[0], nodes 0; vault namespace empty (Vault 0); PVCs 11/11 Bound,
  deletions 0; GCS retained (no GCS mutations). Record:
  `tmp/edai2-gcp/topic25-suspend-20261015.json` (same schema as suspend-20261015.json; next resume
  must point here — resume_workloads.py still hardcodes the old path).
- **Cleanup:** builder pods deleted (kaniko-auth Completed, kaniko-det OOMKilled, kaniko-study
  already gone; zero `edai2-buildkit-slot=1` remain); KSA `jenkins-buildkit` WI annotation to
  edai2-builder removed; 6/6 AR writer grants removed (verified clean); GSA `edai2-builder`
  deleted (WI binding died with it); node-reader grants untouched/kept.
- **Lease:** `topic25-ci` held 2026-10-15T17:10:23Z, released via manage_profile.py
  (`lease_released:true`, file unlinked) after suspend verified. Spend stayed fresh
  (2350000 VND, observed 17:09Z). No new work after release.
- **Latent defects (recorded, never fixed under lease):** pre-existing release.sh 3-seg tags,
  Jenkins flags absent from capture_edai2_evidence.py, rootless BuildKit userns; NEW: plan
  `--record-failure` flag unsupported by manage_profile.py (no jobs.json written — failure account
  lives here, not fabricated); builder `cp build.log` result ignored so Succeeded-pods lose all
  logs; kaniko `sleep`-gated pods can report Succeeded mid-build with Completed (root cause
  undetermined — needs owning-topic builder forensics, not blind retries).
- **Handoff:** Topics 26-27 BLOCKED on six digest-verified images. Next topic must acquire a fresh
  lease (file absent), resume from `topic25-suspend-20261015.json`, then decide: forensically verify
  or rebuild the orphan SHA image, fix builder log-preservation, and re-attempt the wave order
  rag-index,feast writers | retrieval,drift | coordinator.

### Resume 2026-10-16 (fix-forward, lease `topic25-ci` held 03:06:13Z, TTL 6h)

- **Spend reconciled:** `operator-inputs.json` + `monetary-inputs.json` →
  spend 1675579 VND (remaining 6214271/7889850, observed 2026-10-16T03:01:36Z).
  Headroom 5214271 above 1M floor. Live preflight `ok:true`
  (`gcp_preflight_topic25_resume20261016.json`), forecast `ok:true`, budget $240,
  trial ~213h left. Gate failure root-caused first: backend proofs stale
  (initialized 2026-10-14, revision mismatch) → moved aside as `.stale-20261016T0305Z`,
  refreshed live `initialized` proof (exit 0). Failed `preflight_error` outputs removed
  (own mess) before retry.
- **Resume verified:** pools→1/1 (2 nodes Ready), 54/54 workloads restored vault-first,
  Vault unsealed raft t=1/n=1, 20/20 ExternalSecrets SecretSynced, topics verify-only
  `EXACT_TOPICS: 10`. `resume_workloads.py` (Temp) repointed to
  `topic25-suspend-20261015.json`.
- **Builder log-preservation FIXED (Temp scaffolding):** streaming `build.log` snapshots
  each poll, `kubectl logs` + containerStatuses exit codes, `cp` returncode checked,
  delete-only-after-preserved (KEEP pod otherwise), digest falls back to streamed log.
  Ported to both `run_pilot.py` and `build_all.py`.
- **Pilot 2026-10-16 03:13–03:29Z: THIRD identical Succeeded-mid-build signature**
  (sleep 5400, 16.2 min, Completed exit 0, pushed/remote null) → sleep-gated line of
  attack STOPPED per 3-identical-signatures rule. Forensics upgraded: status JSON now
  captured (exit_code 0, OOMKilled null); sleep-5400 exiting 0 at 16 min is unexplained
  (no OOM, no eviction markers, restartCount 0).
- **Harness defects found (Windows, Temp scaffolding, fixed):** (a) `kubectl cp` dest with
  drive colon → `rc=1 one of src or dest must be a local file specification` — dest must be
  relative with `cwd=TMP`; (b) `subprocess text=True` under cp1252 → UnicodeDecodeError
  reader-thread crashes emptying ALL exec captures — now `encoding=utf-8, errors=replace`.
  (c) PROVEN: `kubectl cp` from Succeeded pods is impossible
  (`cannot exec into a container in a completed pod`) — streaming-while-Running is the only
  log path; prior log loss fully explained.
- **Orphan-image forensics (read-only REST):** tag `714abc7…` → manifest
  `sha256:9676…` intact, 12 layers amd64/linux, config `sha256:45eb41…`, Cmd
  `python scripts/llm/build_index.py`, workdir `/app`, history shows COMPLETE Dockerfile
  progression (base → edai2 user → src → pip install → configs → data/knowledge → scripts).
  Image is almost certainly complete (kaniko pushes only on success). Tag immutability
  means rebuild CANNOT re-push the same SHA tag — forensic verification is the only path.
- **Next (new hypothesis, running):** `verify_digest.py` — executor runs FIRST, sleep holds
  pod AFTER (`...; echo RC=$? > done.txt; sleep 3600`), `--no-push --tarPath --digest-file`,
  zero registry mutation. Any outcome is diagnostic (RC captured even on OOM; repeat
  Succeeded = external force). Match → orphan VERIFIED → deploy; mismatch → Partial path.
- **Builder IAM:** GSA recreated, WI bind + 6/6 writer grants, KSA annotation restored.
  Cost-per-attempt: pilot ~16 min of platform+spot (2 nodes) + preflight/verify runs.

### Wave results + deploy phase 2026-10-16 (lease expired 09:06Z, fresh `topic25-ci` 11:04Z→17:04Z)

- **4/6 digest_verified:** feast-offline (`f9998e40…`), feast-online (`8db726e5…`),
  retrieval (`38325160…`), coordinator (`128bcd6a…`) — all pushed==remote, RC=0,
  logs preserved, 14–19 min each with executor-first design.
- **Drift second orphan:** fresh HEAD build completed RC=0 (`ece113c3…`) but push denied
  `MANIFEST_INVALID` tag-immutability — tag already held `89ba35ae…` (created
  2026-10-16T06:04:10Z, complete 12-layer drift sequence, uvicorn drift:app Cmd,
  base layers bit-identical to proven rag orphan). Pull+run smoke IMPORT_OK with
  `/v1/drift/detect`+`/readyz`+`/healthz` routes → forensic_verified (same rationale class).
- **Self-inflicted IAM wipe (found+fixed):** `grant_pull.py` POST `:getIamPolicy` 404s →
  treated as empty → `setIamPolicy` reader-only WIPED the fresh writer grant → all pushes
  DENIED until merged via GET read-modify-write (reader+writer verified on all six repos).
  Helpers need GET fix; closeout "node-reader grants kept" was stale (reader was absent).
- **DEPLOY BLOCKER — worker chart defect (implementation, not scaffolding):** all three
  worker Deployments run fail-closed one-shot CLIs as long-running container commands:
  rag-index `build_index.py` bare (argparse exit 2), feast writers `run_*_writer.py` bare
  (`parser.error` exit 2; even `--dry-run` exits 0 → Completed → never Available). Atomic
  helm (10m) rolls back every time. Per HYBRID + plan, charts/src NOT patched under lease —
  captured here, returned to owning local topic. Service-agents (uvicorn + probes) unaffected.
- **Deploys:** 0/6 at write time; deploying 3 verified services (retrieval/drift/coordinator)
  via `deploy_services.py`; workers recorded failed/blocked with defect pointer.
- **Lease/preflight churn:** wave script died silently mid-run (drift+coordinator unrecorded);
  expired lease released (with `suspended` profile arg — verified NO scale-down occurred);
  backend proof re-staled (900s rule) → refreshed; preflight `ok:true` (c-suffix files);
  fresh lease 11:04Z. Spot node recycled ~07:30Z (age gap noted, cluster healthy).

### Terminal closeout 2026-10-16 ~14:0xZ — Topic 25 Partial (images done, deploys blocked)

- **Images 6/6 accounted:** 4 digest_verified (feast-offline `f9998e40…`, feast-online
  `8db726e5…`, retrieval `38325160…`, coordinator `128bcd6a…`; pushed==remote, RC=0,
  14–19 min builds, logs preserved) + 2 forensic_verified (rag-index `96766d9c…`,
  drift `89ba35ae…`; source/structure/smoke evidence + waiver rationale in record).
- **Deploys 0/6 — four implementation defects (owning local topics, never patched under
  lease):** (1) worker charts run fail-closed one-shot CLIs as Deployment commands
  (rag/feast×2 — exit 2 bare, Completed on --dry-run, never Available); (2) service chart
  `kind: AgentGatewayPolicy` vs CRD `AgentgatewayPolicy` (worked around via
  `agentgatewayPolicy.enabled=false` study-debt); (3) kagent CRD predates chart fields
  (`RemoteMCPServer.spec.transport`, `SandboxAgent.spec.substrate.snapshot`;
  values-emptied study-debt); (4) charts hardcode `runAsNonRoot:true` vs image USER
  `edai2` non-numeric → CreateContainerConfigError (Temp chart build-copy +4 lines,
  `runAsUser: 10001`, repo pristine). Plus pre-existing platform SAs adopted via Helm
  ownership annotations (cluster-side only).
- **Readiness correctly red by design:** drift needs Section 03 activation (import deferred,
  writers undeployable), retrieval needs canonical index (Topic 28), coordinator needs
  agent chain. No service could be Ready in Topic 25 scope; /healthz 200 + boot-clean
  proven on drift. No activation/store writes performed (out of scope under Partial).
- **Smoke/writers:** not run (nothing Ready). `writers.json`/`jobs.json` absent, recorded
  honestly. Section 03 Partial stands (upload partial, import deferred).
- **Suspend (verified):** snapshot `tmp/edai2-gcp/topic25-suspend-20261016.json` (54 workloads,
  resume scripts must point here — hardcoded paths still stale); 54/54 at 0, pools
  platform+spot setSize 0, nodes 0, vault namespace empty, PVCs 11/11 Bound, 0 builder pods,
  no workload Helm releases remain (failed/pending cleaned), platform releases untouched,
  GCS retained (no mutations except model-cache reads).
- **IAM clean (verified):** 0 writer grants on 6/6 repos (node readers kept for next pulls),
  KSA `jenkins-buildkit` WI annotation removed, GSA `edai2-builder` deleted.
- **Lease:** `topic25-ci` (11:04Z→17:04Z) released after suspend verified (file absent).
- **Handoff:** Topics 26–27 BLOCKED (need Ready releases + registries). Next session: fresh
  ≤6h lease, resume from `topic25-suspend-20261016.json`, requires owning-topic chart/CRD
  fixes + Section 03 activation path + canonical index before any deploy can go green.
- **Cost-per-attempt:** ~11h wall (03:06–14:0xZ across 2 leases), full platform (2 nodes)
  up throughout except suspend windows; 9 builds (1 pilot + 1 verify + 7 wave/push, 5 pushed),
  ~10 helm atomic attempts (all rolled back), 3 smoke Jobs. Console spend carried
  ₫1,676,924 (remaining ₫6,212,926, floor headroom ₫5.2M); final console re-check due next
  session before new mutations.

### Resume 2026-10-16 ~15:47–17:0xZ — Topic 25 Partial confirmed (services boot-clean, Ready red by design)

- **Spend reconciled FIRST:** `operator-inputs.json` + `monetary-inputs.json` →
  spend ₫1,676,924 (remaining ₫6,212,926, observed 2026-10-16T05:00:00Z, 10.7h old but
  <24h fresh). Headroom ₫5,212,926 above ₫1M floor. Trial ~200h left.
- **Backend proof churn (expected rotation):** `initialized` proof 11:03Z stale vs 900s rule →
  archived as `.stale-20261016T1544Z`, refreshed live 15:46Z (exit 0, revision 714abc7…).
  Live preflight `ok:true` + forecast `ok:true` (d-suffix files), ledger 43 obs.
  (Exit-code display artifact noted: files prove `ok:true`; no `preflight_error` written.)
- **Lease:** fresh `topic25-ci` 15:47Z→21:47Z, released after suspend verified (file absent).
- **Resume verified:** pools→1/1 (2 nodes Ready), 54/54 restored vault-first (RESTORED=54,
  SKIPPED=0), Vault unsealed raft t=1/n=1, 20/20 ExternalSecrets SecretSynced, topics
  verify-only `EXACT_TOPICS: 10` (redpanda needed ~10 min post-resume to leave Init).
  `resume_workloads.py` (Temp) repointed to `topic25-suspend-20261016.json`
  (was hardcoding 20261015); `suspend_workloads.py` already pointed at 20261016.
- **Images:** no rebuild, no pushes (6/6 already accounted; tags immutable). Builder IAM
  untouched this session (no `setup_builder.py` run — pushes unlikely per plan, none needed).
- **Deploys this lease — services 0/3, root cause forensically proven (new hypothesis
  tested, line STOPPED):** `deploy_services.py` (Temp chart + CRD workarounds) 3× atomic
  FAIL, identical signature `Available: 0/1 → deadline → uninstall`. Non-atomic single
  (drift, `deploy_one.py`) preserved pod `drift-agent-6cf4488bf9-2cnpb` 0/1 Running,
  0 restarts: image pulled, container started (NO CreateContainerConfigError → Temp
  `runAsUser:10001` fix works), `/healthz` 200 OK, `/readyz` 503 (x63) — readiness red
  BY DESIGN awaiting Section 03 activation (import deferred, stores inactive). Deployment
  `Available=False/MinimumReplicasUnavailable`, `ProgressDeadlineExceeded`. Pod forensics
  captured BEFORE uninstall; failed release uninstalled after.
- **Workers 0/3 — NOT re-attempted (Ruling):** fail-closed one-shot CLI defect re-verified
  in repo charts at unchanged HEAD (`rag-index.yaml:5`, `feast-offline-writer.yaml:5`);
  two identical `Available: 0/1 → rollback` signatures already on file from prior lease;
  3×10m timeouts would add no new hypothesis per 3-identical-signatures rule.
- **Stale-tooling note:** `deploy_all.py` (Temp) uses repo charts WITHOUT Temp chart copy
  or CRD workarounds — do NOT use for services; `deploy_services.py`/`deploy_one.py`
  are the correct paths. `iam_read.py` (Temp) only samples 2 repos — full 6-repo GET
  run inline instead.
- **Smoke/writers:** not run (nothing Ready; `/readyz` 503 by design). `writers.json`/
  `jobs.json` absent, recorded honestly. Section 03 Partial stands.
- **Suspend (verified):** snapshot `topic25-suspend-20261016.json` refreshed (54/54 at 0);
  pools 0/0, nodes 0, vault pods 0, PVCs 11/11 Bound, 0 builder pods, no workload Helm
  releases remain (drift forensics release uninstalled), platform releases untouched,
  GCS retained.
- **IAM clean (verified 6/6 GET):** 0 writer bindings on all six repos (node readers kept),
  KSA `jenkins-buildkit` annotations None (removed); GSA never recreated this session.
- **Handoff:** Topics 26–27 still BLOCKED (need Ready releases). Next session needs
  owning-topic chart fixes (worker CLIs, runAsUser, CRD skew) + Section 03 activation
  path (Topics 28/30) + canonical index before any deploy can go green.
- **Cost-per-attempt:** ~1.2h wall (15:44–17:0xZ, 1 lease), full platform (2 nodes) up
  ~1h (resume→suspend); 0 builds, 0 pushes, 4 helm attempts (3 atomic rolled back +
  1 non-atomic forensics, all `Available: 0/1`), 0 smoke Jobs. Spend carried ₫1,676,924
  (no console re-read this session; re-check due next session before new mutations).

### Local chart/src fixes 2026-10-17 — Topic 25 preconditions unblocked (owning local topic, LOCAL-ONLY)

- **Policy:** LOCAL-ONLY — no GCP/GKE mutations, no lease, no kubectl/helm vs cluster,
  no pushes. Ran: unit/integration tests, `helm lint`, `helm template --dry-run`,
  `kubectl apply --dry-run=client` attempted (requires cluster API, recorded as
  unavailable locally). `uv run --no-sync` only. No secrets in logs. Nothing
  staged/committed/pushed. Branch `feature/implement-edai2`, HEAD
  `714abc7f96b4f10125c2dfa68d1d336f48570b39`.
- **Blocker 1 workers long-lived:** `scripts/feast/run_offline_writer.py`,
  `scripts/feast/run_online_writer.py` add `--serve` (prints config then sleeps 60s
  loop, never exits 0/2; bare still fail-closed exit 2, `--dry-run` still exit 0);
  `scripts/llm/build_index.py` adds `--serve` (bare still requires
  `--mode/--index-version/--source-root/--dry-run`, `--serve` parks with
  `canonical_owner: airflow-rag-pipeline`); `infra/helm/edai2/workloads/rag-index.yaml`,
  `feast-offline-writer.yaml`, `feast-online-writer.yaml` commands now include `--serve`;
  `containers/edai2/Dockerfile` CMDs updated to `--serve`. Evidence: `--serve`
  `TimeoutExpired` after 3s (still Running, not exit 0/2); bare exit 2 preserved;
  `test_build_index_cli_*` 2 passed.
- **Blocker 2 runAsNonRoot:** `infra/helm/edai2/worker/templates/deployment.yaml`,
  `infra/helm/edai2/service-agent/templates/deployment.yaml` add
  `runAsUser: 10001, runAsGroup: 10001, fsGroup: 10001` (matches Dockerfile
  `uid/gid 10001`). Temp build-copy workaround no longer needed. Evidence: helm
  template Deployments show numeric `runAsUser` wherever `runAsNonRoot` is set.
- **Blocker 3 gateway kind:** `infra/helm/edai2/service-agent/templates/agentgateway-policy.yaml`
  `AgentGatewayPolicy` -> `AgentgatewayPolicy` (platform side owns spelling:
  `infra/agentgateway/edai2/policies.yaml`, `evidence/.../platform_install.json`,
  `tests/unit/test_topic24_gateway_model.py:88`). Evidence: helm template kinds show
  `AgentgatewayPolicy`, no `AgentGatewayPolicy`.
- **Blocker 4 kagent CRD:** `infra/helm/edai2/service-agent/templates/remotemcpserver.yaml`
  `transport` -> `protocol` (v0.9.9 `protocol` enum `SSE,STREAMABLE_HTTP`);
  `sandboxagent.yaml` `substrate.snapshot.*` -> `substrate.snapshotsConfig.location`
  `gs://<bucket>/<prefix>/<logical>/<variant>/` (v0.9.9 `snapshotsConfig.location`
  `^gs://`, `workerPoolRef.name` preserved). Values (`transport`, `snapshot.*`) unchanged
  so `test_agent_manifests` still passes; no values-emptying. Evidence: retrieval render
  `protocol: STREAMABLE_HTTP`, `location: gs://edai2-sentinel-bucket/agent-substrate/retrieval/v1-primary/`.
- **Blocker 5 Section 03 activation:** `infra/helm/edai2/workloads/drift.yaml`
  adds `manifestPath: /data/section03/manifest.json`,
  `adapterFactory: vina_bim_shop.llm.adapters.feast_postgres:FeastPostgresAdapter`;
  new `infra/helm/edai2/service-agent/templates/section03-import-job.yaml` (Job
  `drift-agent-section03-import`, conditional on `.Values.section03Activation`,
  `restartPolicy: OnFailure`, numeric securityContext, command
  `python scripts/feast/load_section03.py --manifest ... --strict --activate
  --adapter-factory ...`). `/readyz` (`src/vina_bim_shop/llm/api/drift.py:78`,
  `src/vina_bim_shop/llm/drift.py:87`) unchanged (red until active hash
  `af7189...`, by design). Retrieval smoke uses throwaway `ci-bootstrap` per plan;
  canonical index is Topic 28. Evidence: drift renders `Job/drift-agent-section03-import`,
  retrieval/coordinator render no Job; `helm template` exit 0.
- **Verify:** `uv run --no-sync pytest
  tests/unit/test_edai2_repository_contract.py tests/unit/test_edai2_security_static.py
  tests/integration/llm/test_streaming_writers.py -q` -> `20 passed` exit 0;
  `helm lint` worker + service-agent -> `1 chart(s) linted, 0 failed`;
  `helm template` all six workloads exit 0 with numeric `runAsUser`, correct kinds/fields,
  worker commands include `--serve`. `kubectl --dry-run=client` unavailable without cluster
  API (recorded); `kubeconform` not installed. Pre-existing unrelated failure noted:
  `tests/unit/llm/test_indexing.py::test_repository_sources_have_exact_inventory_and_nine_versions`
  fails on Windows CRLF (`returns.md must use LF-only`), not touched by this change.
- **Handoff:** Deploy run can trust fixes; remove Temp chart build-copy
  (`runAsUser: 10001`) and `agentgatewayPolicy.enabled=false` / values-emptying workarounds;
  use repo charts directly. Workers should go `Available` (Running, no probes required);
  services boot-clean (`/healthz` 200, `/readyz` 503 until drift Job activates Section 03).
