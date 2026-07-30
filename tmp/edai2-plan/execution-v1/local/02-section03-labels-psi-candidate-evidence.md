# Section 03 Labels, PSI, and Candidate Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Section 03 Tasks 3–4: leakage-safe labels, point-in-time features, daily PSI/alerts, deterministic candidate artifacts, and an independent fail-closed candidate verifier while preserving Section 01.

**Architecture:** Pure in-memory builders consume generator frames plus `DriftWindow`; a staged writer renders deterministic CSV/config/report/PNG artifacts, hashes them, verifies a temporary root, and atomically advances only `section03_candidate_manifest.json`. Candidate runtime status remains pending.

**Tech Stack:** Python 3.12, Pandas, NumPy, PyArrow, Pillow, PyYAML, pytest, SHA-256, `uv`, Make, `rtk`.

## Locked sources and execution policy

- Read `C:\Users\oou1hc\.codex\RTK.md`; every shell command begins with `rtk`.
- Section 03 source is `tmp/edai2-plan/03_data_generator_improvement.md`, SHA-256 `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`.
- EDAI2 source is `tmp/edai2-plan/04.2_llm_design.md`, SHA-256 `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`.
- Rubric source is `tmp/rubic-check/Coursework Tracking (Public).xlsx`, SHA-256 `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- Work on the current branch in one serial session. Do not create a worktree or branch and do not stage, commit, push, or open a PR.
- Do not mutate GCP or Kubernetes. Kind is never GKE evidence. Do not prune Docker or stop unrelated containers.

## Metadata

| Field | Decision |
|---|---|
| Phase | 2 — pure contracts and pending candidate |
| Source tasks | Section 03 Tasks 3–4 |
| Rubric contribution | Supporting evidence for `Sheet3!E32:E34`; Topic 07 is sole primary owner |
| Prerequisites | Topic 01 Completion Record |
| Blocked successors | Topic 03 |
| Runtime ownership | Generator/evidence operator; one serial session |
| Local/GCP class | Local-only; no GCP mutation |

## Global constraints

- Eligible identity cohort is every unique non-null customer with `created_ts <= feature_cutoff_ts`.
- Positive label requires successful payment with `feature_cutoff_ts < payment_timestamp <= label_end_ts`; output is exactly ordered `id,label`.
- `ml_customer_purchase_training` is the separate richer join and never changes the exact label schema.
- Feature event and created timestamps must be cutoff-safe; inactive eligible customers remain with zero-valued numeric features.
- PSI uses the fixed baseline-known cohort, seven complete UTC-day windows, baseline-derived quantile bins, epsilon normalization, and thresholds stable `<0.10`, warning `[0.10,0.15)`, alert `>=0.15`.
- Generator evidence is staged, immutable, deterministic, recursively hash-bound, and pending until Topic 07 imports runtime proof.
- Candidate or pending evidence earns zero.

## Current-state refresh — read-only planning phase

```text
rtk git status --short --branch
rtk git branch --show-current
rtk rg -n "run_generation|write_evidence|commerce_events|section01" src/vina_bim_shop/generators scripts/generate tests
rtk uv run pytest tests/unit/test_section03_drift.py tests/integration/test_section01_generator.py -q
```

Expected: the same branch and Topic 01 baseline are recorded; no canonical evidence is written during refresh.

## Scope and non-goals

In scope: pure labels/features/training/PSI/health/alerts, normalized commerce-event inheritance, deterministic writing, candidate manifest, independent verification, runner/CLI integration, clean semantics, and Section 01 regressions. Non-goals: dbt, Spark, live Airflow/DataHub, strict finalization, Feast runtime, GCP, or hand-editing generated evidence.

## Exact file map

| Action | Exact path | Responsibility |
|---|---|---|
| Modify | `src/vina_bim_shop/generators/drift.py` | Add PSI and shared window helpers. |
| Create | `src/vina_bim_shop/generators/labels.py` | Build exact label and point-in-time feature/training outputs. |
| Create | `src/vina_bim_shop/generators/drift_evidence.py` | Build health/alerts and write all staged candidate artifacts, report, image, hashes, and manifest. |
| Modify | `src/vina_bim_shop/generators/runner.py` | Invoke Section 03 evidence after full offline frames exist while preserving `run_generation()`. |
| Modify | `src/vina_bim_shop/generators/writer.py` | Lock cleanup and retain authoritative/current/previous bundles safely. |
| Modify | `scripts/generate/run_generator.py` | Print the Section 03 candidate manifest path while preserving CLI compatibility. |
| Create | `scripts/generate/verify_section03_manifest.py` | Independently verify containment, exact schemas/counts, bindings, hashes, checks, and four-point ceiling. |
| Modify | `tests/unit/test_section03_drift.py` | Add label, leakage, feature, PSI, event-inheritance, and threshold tests. |
| Create | `tests/unit/test_section03_manifest_verifier.py` | Exercise every fail-closed candidate mutation. |
| Create | `tests/integration/test_section03_generator.py` | Verify canonical artifact schemas, samples, hashes, report, image, and candidate manifest. |
| Modify | `tests/integration/test_generator_cli.py` | Verify completion text and resolved candidate path. |
| Modify | `tests/integration/test_section01_generator.py` | Reassert every Section 01 artifact and disabled behavior. |

## Interfaces and data flow

Generator frames + `DriftWindow` flow into `build_purchase_labels`, `normalize_commerce_events_for_features`, `build_point_in_time_customer_features`, `build_customer_purchase_training`, `calculate_psi`, daily health, and alert builders. `DriftEvidenceResult` returns paths merged into `GenerationResult.evidence_paths` without changing `run_generation()` parameters/defaults/result type. The independent verifier does not import the writer.

## Failure modes

Fail on future identities, post-cutoff event/created leakage, duplicate/null IDs, nonbinary labels, wrong column order/types, invalid timestamps, incomplete baseline windows, nonfinite PSI, bad threshold inclusivity, altered order-event lead/lag, missing medium stream evidence, path traversal, drive paths, symlinks, missing/extra manifest keys, schema/count drift, consumer-contract rebinding, hash mismatch, false checks, rubric keys outside `Sheet3!E32:E34`, or a satisfied subtotal other than four.

## Ordered test-first execution tasks

- [ ] Add exact horizon/cohort/leakage/PSI fixtures, then run `rtk uv run pytest tests/unit/test_section03_drift.py -q`; expected FAIL because label, feature, PSI, health, and alert builders are absent.
- [ ] Implement the pure builders, then run `rtk uv run pytest tests/unit/test_section03_drift.py -q`; expected PASS for cutoff/horizon edges, inactive eligible customers, zero/repeated PSI bins, finite epsilon, and inclusive 0.10/0.15 thresholds.
- [ ] Add enabled-vs-legacy keyed non-time projection assertions, exact event lead/lag inheritance, allowed boundary crossings inside the maximum lead/lag buffer, same-side inheritance outside that buffer, and canonical medium requirements of at least 100 order-derived events on each side with `abs(stream_normalized_post_pre_ratio - order_normalized_post_pre_ratio) <= 0.20`; run `rtk uv run pytest tests/unit/test_section03_drift.py -q`; expected FAIL until normalized commerce-event evidence is complete.
- [ ] Implement normalized commerce-event feature/evidence inheritance, then run `rtk uv run pytest tests/unit/test_section03_drift.py -q`; expected PASS with unchanged offsets, exact keyed non-time choices, legitimate buffered crossings, and the medium stream-rate comparison.
- [ ] Add verifier and generator/CLI artifact tests, then run `rtk uv run pytest tests/unit/test_section03_manifest_verifier.py tests/integration/test_section03_generator.py tests/integration/test_generator_cli.py -q`; expected FAIL because staged writing, atomic candidate promotion, and independent validation are absent.
- [ ] Implement staged writing and exhaustive verifier rejection for traversal, absolute/drive paths, symlinks, bundle/path mismatch, missing/extra artifact or check keys, ordered-schema/count drift, consumer-contract path/hash rebinding, byte/hash mutation, false checks, wrong rubric keys, and score inflation; run `rtk uv run pytest tests/unit/test_section03_manifest_verifier.py tests/integration/test_section03_generator.py tests/integration/test_generator_cli.py -q`; expected PASS with failures leaving the prior pointer/root unchanged.
- [ ] Run `rtk uv run pytest tests/integration/test_section01_generator.py tests/integration/test_generator_cli.py tests/integration/test_section03_generator.py -q`; expected PASS with every Section 01 key/artifact preserved and temporary runs leaving canonical strict evidence untouched.
- [ ] Run `rtk uv run python scripts/generate/run_generator.py --config configs/generator/base.yaml --scale medium --mode full --clean --seed 42`; expected exit 0, configured counts `12000/600/6000/45000/80`, normalized rate in `[1.35,1.65]`, exact nonempty labels/training, deterministic 1600×900 PNG, and a pending candidate without changing a prior strict root.
- [ ] Run `rtk uv run python scripts/generate/verify_section03_manifest.py --manifest evidence/03_data_generator_improvement/section03_candidate_manifest.json --allow-runtime-pending`; expected exact output `section03 manifest: PASS (runtime pending)` and zero rubric credit.
- [ ] Run `rtk git diff --check`, `rtk git status --short --branch`, and `rtk git ls-files --stage`; expected no whitespace errors, the original branch unchanged, only exact file-map paths plus generated pending candidate artifacts changed, and the final index listing is byte-for-byte identical to the pre-topic listing. Pre-existing staged entries are user-owned; do not stage or unstage them.

## Evidence and screenshot ownership

Topic 02 owns the pending `config_snapshot.yaml`, exact label/training/health/alerts CSVs, deterministic samples, report, candidate manifest, and 1600×900 `section03_config_and_training_join.png`. Screenshot QA records dimensions, visible config/training context, no secrets/PII, and that the image proves local configuration-to-training linkage but does not prove Spark, Airflow, DataHub, GKE, or final rubric satisfaction.

## Cleanup

`--clean` removes only abandoned staging and unreferenced candidates after a replacement candidate verifies. It never pre-deletes the strict root or retained verified bundles. Do not remove a pointer whose identity changed. No runtime is acquired.

## Rubric table

| Workbook cell | Supporting proof | Ownership rule |
|---|---|---|
| `Sheet3!E32` | Drift configuration/result, training sample, deterministic contextual image | Candidate only; Topic 07 promotes |
| `Sheet3!E33` | Parsed config snapshot, resolved windows, source-config hash | Candidate only; Topic 07 promotes |
| `Sheet3!E34` | Exact unique `id,label` and distinct point-in-time training join | Candidate only; Topic 07 promotes |

## Definition of Done

Pure and integration contracts pass; event inheritance and medium stream comparison pass; the exhaustive verifier fails closed; Section 01 remains intact; a valid pending candidate is reusable by Topic 07; no runtime or score claim is made.

## Completion Record

| Field | Record |
|---|---|
| Status | **Complete after the customer-frequency timestamp-assignment repair.** The canonical medium candidate now contains a truthful warning observation: peak daily PSI `0.120526925411 >= 0.10` on `2026-04-30`, with 15 warning rows, 7 stable rows, and 0 alert rows across the fixed 11,966-customer cohort. All pure, fail-closed writer/verifier, CLI, Section 01 regression, configured-count, rate-ratio, cutoff/leakage, schema/hash, image, cleanup, and index-preservation gates pass. Runtime remains pending and no rubric score is claimed. |
| Affected files | Modified only `src/vina_bim_shop/generators/drift.py`, `src/vina_bim_shop/generators/offline/orders.py`, `src/vina_bim_shop/generators/drift_evidence.py`, `scripts/generate/verify_section03_manifest.py`, `tests/unit/test_section03_drift.py`, `tests/unit/test_section03_manifest_verifier.py`, `tests/integration/test_section03_generator.py`, and this Completion Record. Replaced the tracked pending candidate pointer and old bundle `evidence/03_data_generator_improvement/runs/08c3ed4561bf17c0359ed8741d7d2bbd3fe8e52ab5aa088ea75e8532670b6e49/` with verified bundle `evidence/03_data_generator_improvement/runs/c220ab9dc815fb6ccff187b661a0fa483f8c16bcda368dd214a0f78633d6c92f/`, containing only the eleven declared artifacts. Canonical Section 01 tracked evidence was restored byte-for-byte after generation. No configuration, dependency, Topic 03, branch, worktree, index, or runtime file remains changed. |
| Commands / exit codes | Pre-edit: `rtk git status --short --branch` and `rtk git branch --show-current` → `0` on clean `feature/implement-edai2`; `rtk git ls-files --stage` → `0`, 792 lines, normalized SHA-256 `6304cc06aad6a16b8e0a630a68c1e04beb8e8c1be7becbe307f8d8d3f4f650a9`. The attempted GNU `rtk sha256sum ...` preflight → `1` because that binary is unavailable; the read-only .NET SHA-256 fallback → `0` and all three locked hashes matched.<br>Assignment TDD: `rtk uv run pytest tests/unit/test_section03_drift.py -q` → `1` at the expected missing-helper import, then `0` (`44 passed`, warning-free). Fail-closed TDD: `rtk uv run pytest tests/unit/test_section03_manifest_verifier.py tests/integration/test_section03_generator.py tests/integration/test_generator_cli.py -q` → `1` (`4 failed, 9 passed`) at the four expected missing semantic gates, then `0` (`13 passed`). Regression: `rtk uv run pytest tests/integration/test_section01_generator.py tests/integration/test_generator_cli.py tests/integration/test_section03_generator.py -q` → `0` (`8 passed`).<br>Canonical/evidence: `rtk uv run python scripts/generate/run_generator.py --config configs/generator/base.yaml --scale medium --mode full --clean --seed 42` → `0` in 1,162.8 seconds with configured counts `12000/600/6000/45000/80`; `rtk uv run python scripts/generate/verify_section03_manifest.py --manifest evidence/03_data_generator_improvement/section03_candidate_manifest.json --allow-runtime-pending` → `0`, exact output `section03 manifest: PASS (runtime pending)`; manifest-bound empirical measurement → `0`, `max_psi=0.120526925411 warning_rows=15 alert_rows=0`; Section 01 byte-diff gate → `0`. Post-record final acceptance: `rtk uv run pytest tests/unit/test_section03_drift.py -q` → `0` (`44 passed`); `rtk uv run pytest tests/unit/test_section03_manifest_verifier.py tests/integration/test_section03_generator.py tests/integration/test_generator_cli.py -q` → `0` (`13 passed`); `rtk uv run pytest tests/integration/test_section01_generator.py tests/integration/test_generator_cli.py tests/integration/test_section03_generator.py -q` → `0` (`8 passed`).<br>Final gates: candidate verifier → `0` with exact pending output; `rtk git diff --check` → `0`; Section 01 byte-diff gate → `0`; locked hashes and candidate-manifest hash → `0` with exact matches; final `rtk git ls-files --stage` → `0`, 792 lines and unchanged normalized SHA-256 `6304cc06aad6a16b8e0a630a68c1e04beb8e8c1be7becbe307f8d8d3f4f650a9`; final `rtk git status --short --branch` → `0` on unchanged `feature/implement-edai2`, with only the declared code/tests/Completion Record and old-to-new Topic 02 candidate replacement present. |
| Evidence + SHA-256 | Candidate manifest `evidence/03_data_generator_improvement/section03_candidate_manifest.json` → `8c0ff22ef528f4170506734f03c055aeec742e62bd9e94d7d0f703e47653bed7`; bundle ID `c220ab9dc815fb6ccff187b661a0fa483f8c16bcda368dd214a0f78633d6c92f`; source config SHA-256 `5c5029fea77d93c3941d87d9a60f85cfe374f36899c3d3c1b028f3f5f3c3cd97`.<br>Artifact hashes: `config_snapshot.yaml` `7405c3e2a27d87be522bea9de7dcc559ad8baff5274a8bed98f002b2753a9196`; `ml_customer_label.csv` `526304d4e2d97a70ed6671993b2f5bc07e934dfbd72488cb98c32dcb924f0278` (11,996 rows; 4,395 positives); `agg_feature_health_daily.csv` `0d9a304b49fdae14aca134a11b8e3420fd202bf093535f1d7904fae8d020963f` (22 rows); `feature_drift_alerts.csv` `b656dccc0c86abdf5896e3db1788f04a0fb128e27f2218331f8cc49df188e76a` (0 rows, exact header); `ml_customer_purchase_training.csv` `76607ad6d92ffee2558568a37735c17a6c3e4f4fe32e0204b62f22e9afadc05b` (11,996 rows); samples `11802e34c683730445db0a2690a1d62c3059e2093e4f348bba318bdd89289e0b`, `8f181026aa6cb5f1ee890dee1a63b76ed9e0b6ba7ea20cefc268009aa40306f9`, `b656dccc0c86abdf5896e3db1788f04a0fb128e27f2218331f8cc49df188e76a`, `c43378e8fc869ea6b344ebfa3ccf383575cb3fa0f9545f4f68ca0a028f88a7db`; image `ba02e5341f6af700530b97dca707f5e4e25f7cbaf44b6df8d50d7fd9821003ad`; report `ebdbba5708bbfc8c24006b67204e65a460644bf8539fc4f0ceaf2d90587bd487`. Measured order ratio `1.518934890754`; stream ratio `1.521767411480`; absolute difference `0.002832520726`; stream pre/post counts `52,490/43,011`; all nine manifest checks are true. |
| Screenshot QA | Original-resolution decoder and visual inspection passed for `section03_config_and_training_join.png`: exactly `1600×900`, RGB, SHA-256 `ba02e5341f6af700530b97dca707f5e4e25f7cbaf44b6df8d50d7fd9821003ad`, nonblank, legible, and unclipped. It visibly contains the eight locked drift values, resolved drift/cutoff/label/baseline windows, exact `id`, `label`, event timestamp, and 90-day order feature for the first ten synthetic IDs, plus both source CSV names and the local-candidate limitation. No secret, real PII, or successor-owned UI screenshot was created. It proves only local configuration-to-training linkage. |
| Cleanup / runtime release | `--clean` advanced the pending pointer only after the repaired candidate verified, removed superseded bundle `08c3ed4561bf17c0359ed8741d7d2bbd3fe8e52ab5aa088ea75e8532670b6e49`, retained bundle `c220ab9dc815fb6ccff187b661a0fa483f8c16bcda368dd214a0f78633d6c92f`, and left `staging_count=0`. The one-byte transient `section03.lock` was removed after the writer exited. Required canonical raw outputs remain generator-managed local data. All Section 01 tracked files equal `HEAD`. No service, container, Kind/GKE context, kubeconfig, Docker resource, cloud resource, or GCP runtime was acquired or mutated. |
| Resource / budget gates | Exactly one canonical medium runtime slice ran, completing in 1,162.8 seconds under the 1,800-second ceiling. No bounded tuning retry, dependency installation, live GCP mutation, Kubernetes command, Docker pruning, or unrelated process termination occurred. |
| Rollback / recovery | The medium stable-only integration test proves failure leaves the prior candidate pointer/root unchanged and removes owned staging. The independent verifier rejects hash-consistent stable-only medium evidence and incorrect inclusive `0.10`/`0.15` status mappings. If this candidate is later invalidated, restore the prior tracked pointer/bundle from Git without touching the index or unrelated files; do not reinterpret thresholds or manufacture alerts. |
| Limitations | The verified candidate remains local and runtime-pending. Spark/dbt parity, Airflow, DataHub, Feast, strict finalization, GKE/GCP, and final UI/runtime captures remain successor-owned. Zero points are claimed for `Sheet3!E32:E34`; Topic 07 remains the sole promotion and primary rubric owner. The alert artifact is truthfully empty because the measured peak is warning-level and below `0.15`. |
| Rubric disposition | Complete supporting implementation/candidate evidence for Topic 02, contributing only to `Sheet3!E32:E34`; runtime status is pending and the satisfied subtotal remains zero until Topic 07 performs strict promotion with successor runtime proof. |
| Successor handoff | **Topic 03 may proceed** using candidate manifest SHA-256 `8c0ff22ef528f4170506734f03c055aeec742e62bd9e94d7d0f703e47653bed7` and bundle `c220ab9dc815fb6ccff187b661a0fa483f8c16bcda368dd214a0f78633d6c92f`. Identity: `scale=medium`, seed `42`, history `60`; windows `2026-03-03T23:59:00Z`→`2026-05-01T23:59:00Z`, drift `2026-04-11T08:23:00Z`, cutoff `2026-04-24T23:59:00Z`, label end `2026-05-01T23:59:00Z`, baseline `2026-04-10`; fixed PSI cohort `11,966`; peak PSI `0.120526925411` on `2026-04-30`. Topic 03 may consume the exact candidate contract but must retain pending/zero-credit semantics. |
