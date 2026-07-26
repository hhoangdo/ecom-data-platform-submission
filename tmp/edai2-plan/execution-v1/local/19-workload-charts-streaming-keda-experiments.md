# 19 — Workload Releases, Streaming, KEDA, and Experiment Contracts

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Statically implement Task 9's six workload values, Section 03 activation ordering, streaming schema/outbox/DLQ, bounded KEDA, inference factorial, independent experiments, warmup and rollback/smoke CLIs without building, pushing, deploying, bootstrapping live topics, or running live experiments.

**Architecture:** Topic 19 values consume the Topic 16-owned charts to render six commit-SHA releases; it never edits chart templates. Final service renders merge Topic 14 app-agent values with Topic 19 workload values. Kafka bootstrap precedes writers. The drift Jenkins/Helm release alone invokes the Topic 12 loader after verified upload; no duplicate importer exists. CI bootstrap retrieval index is explicitly temporary and distinct from the canonical Airflow evidence index. Experiment configurations hold all non-tested factors constant and fail closed on promotion.

**Tech Stack:** Helm values, Kubernetes/KEDA YAML, Redpanda/Kafka JSON Schema, PostgreSQL outbox, Python 3.12/uv, pytest, YAML/JSON static validators.

## Metadata

| Field | Locked value |
|---|---|
| Phase | Local/static workload Topic 19 |
| Source task | `tmp/edai2-plan/04.2_llm_design.md` Task 9 static portion |
| Sheet3 support | `Sheet3!E12:E26`, `Sheet3!E35:E40`, `Sheet3!E56:E57` |
| Predecessor Completion Record | `tmp/edai2-plan/execution-v1/local/18-platform-helm-kustomize.md` must be `Complete` |
| Blocked successor | `tmp/edai2-plan/execution-v1/local/20-observability-ingress-screenshot-contracts.md` |
| Runtime ownership | Local lint/render/schema session only |
| Class | Local/static; no workload/Kafka/GCP mutation |

## Locked planning basis

Read `C:\Users\oou1hc\.codex\RTK.md`; verify hashes `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`, `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`, and rubric `tmp/rubic-check/Coursework Tracking (Public).xlsx` `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.

## Global constraints

Use current branch/serial session, `apply_patch`, `rtk uv run` developer recipes, and `rtk make` operator recipes. Topic 08 owns baseline dependencies; run `rtk uv lock --check` and treat a missing prerequisite as a `Partial` predecessor defect instead of editing dependencies. Do not edit the Topic 16-owned chart templates. No stage/commit, build/push/deploy, live Kafka/Feast/KEDA/experiment, GCP, broad Compose, or automatic Docker stop/prune. One bounded retry then `Partial`.

## Read-only current-state refresh

- [ ] Run `rtk git status --short --branch`. Expected: branch and unrelated changes recorded.
- [ ] Run `rtk proxy certutil -hashfile tmp/edai2-plan/03_data_generator_improvement.md SHA256`. Expected: output contains `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`.
- [ ] Run `rtk proxy certutil -hashfile tmp/edai2-plan/04.2_llm_design.md SHA256`. Expected: output contains `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`.
- [ ] Run `rtk proxy certutil -hashfile "tmp/rubic-check/Coursework Tracking (Public).xlsx" SHA256`. Expected: output contains `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- [ ] Run `rtk proxy powershell -NoProfile -Command "Select-String -Path tmp/edai2-plan/execution-v1/local/18-platform-helm-kustomize.md -Pattern '^Status: Complete|\| Status \| Complete \|'"`. Expected: completed predecessor.
- [ ] Run `rtk uv lock --check`. Expected: exit 0 with the Topic 08-owned baseline lockfile unchanged.
- [ ] Run `rtk git diff --check`. Expected: exit 0.

## Scope and non-goals

In scope: six workload values, exact Kafka topics/schema/groups/outbox/DLQ, writers, KEDA values, import ordering, CI/bootstrap versus canonical index distinction, warmup/factorial/experiment configs, static smoke/benchmark/rollback CLIs, lint/render/schema/integration tests.

Non-goals: topic creation, Section 03 upload/import, image build, Jenkins trigger, Helm apply, live KEDA, warmup, benchmark, experiment, registry publish, rollback or GCP.

## Exact file map

| Action | Exact path | Responsibility |
|---|---|---|
| Create | `infra/helm/edai2/workloads/retrieval.yaml` | Retrieval service/MCP workload settings merged with Topic 14 retrieval-agent values |
| Create | `infra/helm/edai2/workloads/drift.yaml` | Drift service/MCP/agent plus single Section 03 activation hook |
| Create | `infra/helm/edai2/workloads/coordinator.yaml` | Facade and three internal coordinator destinations |
| Create | `infra/helm/edai2/workloads/rag-index.yaml` | Temporary CI bootstrap/canonical index job modes |
| Create | `infra/helm/edai2/workloads/feast-offline-writer.yaml` | Offline writer/group/KEDA values |
| Create | `infra/helm/edai2/workloads/feast-online-writer.yaml` | Online writer/group/KEDA values |
| Modify | `infra/kafka/topics.yaml` | Exact update and DLQ topic specifications |
| Modify | `src/vina_bim_shop/kafka/topics.py` | Typed topic/group names |
| Modify | `src/vina_bim_shop/kafka/bootstrap.py` | Idempotent local/GKE-rpk verification modes |
| Modify | `scripts/kafka/bootstrap_topics.py` | Strict schema/topic read-back CLI |
| Modify | `infra/governance/recipes/kafka_topics.yml` | DataHub topic/schema lineage |
| Create | `infra/kafka/schemas/customer_feature_updates-value.schema.json` | Closed Draft 2020-12 event/DLQ schema |
| Create | `infra/postgres/edai2/004_streaming_features.sql` | Outbox, dedup and consumer checkpoints |
| Modify | `src/vina_bim_shop/llm/streaming/offline_writer.py` | Complete the Topic 08 scaffold with offline destination/idempotency/group/DLQ behavior |
| Modify | `src/vina_bim_shop/llm/streaming/online_writer.py` | Complete the Topic 08 scaffold with online destination/idempotency/group/DLQ behavior |
| Create | `scripts/feast/run_offline_writer.py`, `scripts/feast/run_online_writer.py` | Thin worker CLIs |
| Modify | `configs/llm/warmup_prompts.json` | Complete the Topic 08 scaffold with three fixed shared-prefix warmups |
| Modify | `configs/llm/benchmark_requests.json` | Complete the Topic 08 scaffold with the fixed ordered 40-request mixed-prefix fixture |
| Create | `scripts/llm/benchmark_inference.py` | Factorial/startup/experiment evidence schema CLI |
| Create | `scripts/llm/smoke_release.py` | Release, writer and rollback smoke modes |
| Create | `tests/integration/llm/test_streaming_writers.py` | Topic/schema/dedup/checkpoint/DLQ contracts |
| Create | `tests/unit/llm/test_workload_contracts.py` | Six releases, ordering, KEDA, experiments, renders |
| Consume | `scripts/feast/load_section03.py` | Topic 12-owned only loader; drift release invokes exactly once |
| Consume | `configs/llm/routing.yaml` | Topic 13-owned salts/destinations/promoted alias |
| Consume | `infra/helm/edai2/service-agent`, `infra/helm/edai2/worker` | Topic 16-owned reusable charts; lint/render only and never edit templates |

## Interfaces, data flow, and failure modes

Inputs are the verified Section 03 manifest/hash, full `GIT_COMMIT`, Topic 16 charts, Topic 18 platform interfaces, Topic 14 app-agent values, Topic 13 routing salts, topic/schema contract, and fixed warmup/benchmark fixtures. Outputs are six renderable commit-SHA release values, one import-activation owner, deterministic event/outbox/DLQ semantics, bounded KEDA values, four factorial cells, two isolated experiment definitions, and rollback/smoke CLIs. Topic 20 consumes stable telemetry/routing labels; GCP Topics 25–29 own live delivery and measurement.

Verification/upload ordering mismatch, duplicate importer, same-hash mutation, bootstrap/canonical index conflation, topic read-back mismatch, open schema, unacknowledged checkpoint, duplicate destination effect, raw DLQ payload, KEDA bound breach, inactive-model replica, changed held constant, missing sample, failed promotion gate, alias CAS/read-back mismatch, lint/render error, or live local mutation fails closed.

## Exact workload and data contracts

Before drift deployment: local strict verification uploads only the hash-bound Section 03 bundle; the drift Helm/Jenkins release is the single activation owner and invokes `load_section03.py`. No init container, second Job or writer duplicates import. Same hash no-ops; failure restores prior active version and leaves drift unready.

`customer_feature_updates.v1` and `customer_feature_updates.v1.dlq`: one partition, replication one, delete cleanup, seven-day retention. Consumer groups are exactly `edai2-feast-offline-writer-v1` and `edai2-feast-online-writer-v1`. Valid event goes through PostgreSQL outbox and deterministic event ID; destination acknowledgement precedes checkpoint. Invalid input yields one redacted deterministic DLQ record per group. Duplicate has no effect.

The closed update event fields are `event_id`, `manifest_sha256`, `id`, `event_timestamp`, `feature_name`, `feature_value`, and `source_version`. The closed DLQ envelope fields are `dlq_id`, `consumer_group`, `source_topic`, `source_partition`, `source_offset`, `payload_sha256`, `error_code`, and `observed_at`; it never embeds the rejected raw payload. SQL names are exactly `edai2_feature_outbox`, `edai2_feature_dedup`, and `edai2_consumer_checkpoints`.

CI bootstrap index is exactly `ci-bootstrap-${GIT_COMMIT}`, temporary and sufficient only for release smoke. `GIT_COMMIT` is the full lowercase 40-hex value from `rtk git rev-parse --verify HEAD`; every runtime/deploy image tag must be the same full lowercase 40-hex value as the Jenkins checkout revision. Literal `testsha` is accepted only as an explicit command-line override in the local `helm template` render-only steps below, is forbidden in checked-in values and every apply/deploy path, and never authorizes a build, push, or release. Canonical evidence index is created/promoted later by the Airflow RAG pipeline with its own version/hash/evaluation lineage; it is never relabeled from CI bootstrap and requires no image rebuild.

API KEDA: Prometheus RPS threshold 1, min 1, max 2, polling 15 s, cooldown 60 s. WorkerPool uses `ate.dev/v1alpha1`, `edai2-agents`, pending-chat query, same bounds. Static manifests never claim scale occurred.

Inference factorial cells and order are exactly `cache_off+load_aware` (baseline), `cache_on+load_aware`, `cache_off+prefix_aware`, and `cache_on+prefix_aware` (optimized). Every cell has two healthy endpoints for the active model, global concurrency 1, context 4096, `max_new_tokens=128`, `temperature=0`, `top_p=1`, seed `20260715`, fixed 40-request fixture/order, and the same image, weights, and Spot SKU. The inactive model is zero during another model's two-replica cells. Comparison is one only for model A/B and two only for its own factorial.

Agent startup: same nodes/primary/index/agents/prompts/policies, 20 deterministic sessions per agent/arm; cold min 0 KEDA active, candidate min 1 snapshot restore. Gates: startup p95 >=20% improvement, cost/100 >=5%, no quality/safety regression.

Agent experiment salt `agent_exp_v1`, 60 observed sessions/arm, held constants exact, promotion requires groundedness or citation +2pp, safety non-regression, tool failures not rise, and chat p95 regression no more than 5%. Model salt `model_exp_v1`, 60/arm, only ModelConfig/digest differs; all five gates and cost/100 improvement of at least 20% are required. A failed gate preserves the prior alias.

## Ordered test-first execution

- [ ] Add red workload/streaming tests and run `rtk uv run pytest tests/unit/llm/test_workload_contracts.py tests/integration/llm/test_streaming_writers.py -q`. Expected: nonzero until exact values/schema/order/experiments exist.
- [ ] Resolve the immutable CI revision with `rtk git rev-parse --verify HEAD`. Expected: one lowercase 40-hex SHA that becomes `GIT_COMMIT` and therefore the exact temporary index ID `ci-bootstrap-${GIT_COMMIT}`.
- [ ] Verify the local prerequisite with `rtk uv run python scripts/feast/load_section03.py --manifest evidence/03_data_generator_improvement/section03_manifest.json --strict --verify-only`. Expected: exit 0 with the complete canonical hash-bound bundle and no upload, PostgreSQL, Feast, Valkey, Helm, or GCP mutation.
- [ ] Prove activation ownership/order with `rtk uv run pytest tests/unit/llm/test_workload_contracts.py -q -k "section03_upload_verify_before_drift or single_activation_owner or no_duplicate_import"`. Expected: exit 0; the future live sequence is verify -> immutable upload -> drift Jenkins/Helm activation, with no second importer.
- [ ] Validate schema with `rtk uv run python -m json.tool infra/kafka/schemas/customer_feature_updates-value.schema.json`. Expected: exit 0 and closed Draft 2020-12 JSON.
- [ ] Run `rtk uv run pytest tests/integration/llm/test_streaming_writers.py -q`. Expected: exit 0 using fakes; exact topics/groups/outbox/dedup/checkpoint/two-DLQ behavior.
- [ ] Lint reused charts with `rtk helm lint infra/helm/edai2/service-agent` and `rtk helm lint infra/helm/edai2/worker`. Expected: both exit 0.
- [ ] Render retrieval with `rtk helm template retrieval infra/helm/edai2/service-agent -f infra/helm/edai2/values/retrieval-agent.yaml -f infra/helm/edai2/workloads/retrieval.yaml --set image.tag=testsha --set-string substrate.bucketName=edai2-sentinel-bucket`. Expected: exit 0; the final release merges agent and workload values, contains one `support` SandboxAgent with logical identity `retrieval`, has no LoadBalancer, and has bounded KEDA.
- [ ] Render drift with `rtk helm template drift infra/helm/edai2/service-agent -f infra/helm/edai2/values/drift-agent.yaml -f infra/helm/edai2/workloads/drift.yaml --set image.tag=testsha --set-string substrate.bucketName=edai2-sentinel-bucket`. Expected: exit 0; the final release merges both value layers and contains exactly one activation owner referencing the verified loader.
- [ ] Render coordinator with `rtk helm template coordinator infra/helm/edai2/service-agent -f infra/helm/edai2/values/coordinator-agent.yaml -f infra/helm/edai2/workloads/coordinator.yaml --set image.tag=testsha --set-string substrate.bucketName=edai2-sentinel-bucket`. Expected: exit 0; the final release merges both value layers and contains exactly three internal destinations plus one facade.
- [ ] Render the RAG index and both writers with `rtk helm template rag-index infra/helm/edai2/worker -f infra/helm/edai2/workloads/rag-index.yaml --set image.tag=testsha`, `rtk helm template feast-offline-writer infra/helm/edai2/worker -f infra/helm/edai2/workloads/feast-offline-writer.yaml --set image.tag=testsha`, and `rtk helm template feast-online-writer infra/helm/edai2/worker -f infra/helm/edai2/workloads/feast-online-writer.yaml --set image.tag=testsha`. Expected: all three exit 0, RAG bootstrap/canonical modes remain distinct, writer groups are distinct, and no import/bootstrap duplication exists.
- [ ] Assert the sentinel boundary with `rtk uv run pytest tests/unit/llm/test_workload_contracts.py -q -k "six_renders or sentinel_tag or commit_sha"`. Expected: exactly six render-only outputs; `testsha` is absent from checked-in values and accepted only by local template commands, while every runtime/deploy value requires full lowercase 40-hex and equality with the Jenkins checkout.
- [ ] Run `rtk uv run pytest tests/unit/llm/test_workload_contracts.py -q`. Expected: exit 0 for index distinction, KEDA values, factorial/inactive-zero constants, salts, held constants, samples and gates.
- [ ] Run `rtk git diff --check`. Expected: exit 0 and no live resource changed.

## Evidence, cleanup, rubric, and DoD

Topic 19 owns lint/render/schema/test hashes only. No Section 03 upload, topic bootstrap, release, scale, benchmark, experiment or rollback is claimed. Delete only render temp files.

| Sheet3 cell | Local proof | Deferred proof |
|---|---|---|
| `Sheet3!E12:E26` | six release/agent/KEDA/factorial contracts | live services/agents/scaling |
| `Sheet3!E35:E40` | Jenkins-owned release ordering contracts | six CI records |
| `Sheet3!E56:E57` | independent experiment schemas/gates | observed A/B reports |

## Definition of Done

All six values render; strict import ownership/order, streaming semantics, KEDA limits, CI/canonical index distinction, factorial inactive-zero, independent experiments and gates pass; no live execution occurs.

## Completion Record

| Field | Execution value |
|---|---|
| Status | Not started |
| Current branch/status | Record final `rtk git status --short --branch` |
| Affected files | Record Topic 19 exact paths |
| Commands and exit codes | Record schema, lint, render and tests |
| Evidence hashes | Record local artifacts SHA-256 |
| Screenshot QA | Not captured locally |
| Cleanup/runtime release | Record render cleanup; no runtime |
| Limitations | Record all deferred live upload/deploy/KEDA/benchmark/A-B proof |
| Handoff | `tmp/edai2-plan/execution-v1/local/20-observability-ingress-screenshot-contracts.md` |
