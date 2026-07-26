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
| Status | Not started |
| Affected files | Record only exact file-map paths and generated candidate paths actually changed |
| Commands / exit codes | Record every checkbox command and numeric exit code, ending with `rtk git status --short --branch` |
| Evidence + SHA-256 | Record candidate manifest/artifact paths and hashes, or `no candidate produced` |
| Screenshot QA | Record proves/does-not-prove, dimensions, visible context, redaction, and SHA-256 |
| Cleanup / runtime release | Record staging/candidate retention and `no runtime acquired` |
| Limitations | Pending candidate cannot satisfy `Sheet3!E32:E34` |
| Successor handoff | Provide candidate manifest SHA-256, config/scale/windows, artifact inventory, and test results to Topic 03 |
