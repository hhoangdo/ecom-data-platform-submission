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
| Status | **Partial.** All pure, integration, candidate-writing, independent-verifier, Section 01 regression, configured-count, rate-ratio, cutoff/leakage, schema/hash, and image checks pass. The locked empirical warning criterion did not: the measured peak daily PSI is `0.068131800343 < 0.10`, so all 22 health rows are `stable` and the exact-header alert CSV has zero rows. The single bounded diagnostic retry reproduced the same PSI; no threshold, score, alert, or measurement was altered. |
| Affected files | Modified only `src/vina_bim_shop/generators/drift.py`, `src/vina_bim_shop/generators/runner.py`, `src/vina_bim_shop/generators/writer.py`, `scripts/generate/run_generator.py`, `tests/unit/test_section03_drift.py`, `tests/integration/test_generator_cli.py`, `tests/integration/test_section01_generator.py`, and this Completion Record. Created only `src/vina_bim_shop/generators/labels.py`, `src/vina_bim_shop/generators/drift_evidence.py`, `scripts/generate/verify_section03_manifest.py`, `tests/unit/test_section03_manifest_verifier.py`, and `tests/integration/test_section03_generator.py`. Generated candidate pointer `evidence/03_data_generator_improvement/section03_candidate_manifest.json` and bundle `evidence/03_data_generator_improvement/runs/08c3ed4561bf17c0359ed8741d7d2bbd3fe8e52ab5aa088ea75e8532670b6e49/` containing only the eleven declared artifacts. Canonical Section 01 tracked evidence was restored byte-for-byte after the required medium run. |
| Commands / exit codes | Pre-edit: `rtk git status --short --branch` → `0` on unchanged `feature/implement-edai2`; three locked SHA-256 recomputations → `0`, all matched; `rtk git ls-files --stage` → `0`, 775 lines, normalized listing SHA-256 `5e0dddac56d215dc3910779a12c0fe268152b74e7052b590838a2448fd8db978`.<br>Red/green: `rtk uv run pytest tests/unit/test_section03_drift.py -q` → `1` (expected missing-builder collection failure), then `0` (`33 passed`); the first full normalized-medium fixture attempt and its bounded retry → `124`/`124` at 304/904 seconds, with owned pytest processes stopped; the scoped smoke inheritance replacement and full pure gate → `0` (`35 passed`). `rtk uv run pytest tests/unit/test_section03_manifest_verifier.py tests/integration/test_section03_generator.py tests/integration/test_generator_cli.py -q` → `1` at the expected missing-writer/verifier gate, then `0` (`9 passed`).<br>Regression/candidate: `rtk uv run pytest tests/integration/test_section01_generator.py tests/integration/test_generator_cli.py tests/integration/test_section03_generator.py -q` → `0` (`7 passed`). `rtk uv run python scripts/generate/run_generator.py --config configs/generator/base.yaml --scale medium --mode full --clean --seed 42` → `0` in 1,152.9 seconds with configured counts `12000/600/6000/45000/80`. `rtk uv run python scripts/generate/verify_section03_manifest.py --manifest evidence/03_data_generator_improvement/section03_candidate_manifest.json --allow-runtime-pending` → `0`, exact output `section03 manifest: PASS (runtime pending)`.<br>Final acceptance re-runs: pure gate → `0` (`35 passed`); focused writer/verifier/CLI gate → `0` (`9 passed`); Section 01 regression gate → `0` (`7 passed`); candidate verifier → `0` with the exact pending output. Bounded empirical recomputation over the fixed 11,966-customer cohort → `0`, baseline counts `{0:8236,1:2998,2:643,3:74,4:12,5:2,6:1}`, current counts `{0:6897,1:3657,2:1123,3:229,4:49,5:9,6:2}`, PSI `0.068131800343`, status `stable`. Final `rtk git diff --check` → `0`; Section 01 tracked diff gate → `0` (no differences); locked hashes → `0` (all matched); candidate verifier → `0`; final `rtk git ls-files --stage` → `0`, unchanged 775-line SHA-256 `5e0dddac56d215dc3910779a12c0fe268152b74e7052b590838a2448fd8db978`; final `rtk git status --short --branch` → `0` on the original branch with only the declared Topic 02 code/tests/Completion Record and candidate evidence paths modified or untracked. |
| Evidence + SHA-256 | Candidate manifest: `evidence/03_data_generator_improvement/section03_candidate_manifest.json` → `ba9fc1e83291d27a61c9558d720d6db411ec2bc5d05bc8b10852d8bec266e7a6`; bundle ID `08c3ed4561bf17c0359ed8741d7d2bbd3fe8e52ab5aa088ea75e8532670b6e49`; source config SHA-256 `5c5029fea77d93c3941d87d9a60f85cfe374f36899c3d3c1b028f3f5f3c3cd97`.<br>Artifact hashes: `config_snapshot.yaml` `7405c3e2a27d87be522bea9de7dcc559ad8baff5274a8bed98f002b2753a9196`; `ml_customer_label.csv` `1a62321bc4fd5b1373579ed86ed842fa5127150fb442ed05321ebc107620820e` (11,996 rows); `agg_feature_health_daily.csv` `19f27a44f3d40a4c73970f62af72702081798cacf6c53c42dfeddae7fcc309fc` (22 rows); `feature_drift_alerts.csv` `b656dccc0c86abdf5896e3db1788f04a0fb128e27f2218331f8cc49df188e76a` (0 rows, exact header); `ml_customer_purchase_training.csv` `cd72fafdc4b0950b2db7b892f5f451aa60f993b4e6c796c08ebc8fb9769ff981` (11,996 rows); samples `b9c62f8102bb6d85bb450998c5b0bbc596cec20f95e424accdd2bf671a1b60c9`, `30655f514b58b42449438f5bb320ebd75caa4a4dd70fa514af02d56f42ce2ae9`, `b656dccc0c86abdf5896e3db1788f04a0fb128e27f2218331f8cc49df188e76a`, `8b43ae492f321986c2344e44c340283d6f219b452311092223624d21b64242f7`; image `bb46d4994623454dc7a32598e5badb887cb3b40b77f8604702b49075d32bbb49`; report `d523862ff9db7acdb037af83df739201a67d2273053292a95379fdf80327bed1`. Measured order ratio `1.518934890754`; normalized stream ratio `1.521767411480`; absolute difference `0.002832520726`; stream pre/post counts `52,490/43,011`; all nine manifest checks are true. |
| Screenshot QA | Original-resolution decoder and visual QA passed for `section03_config_and_training_join.png`: exactly `1600×900`, SHA-256 `bb46d4994623454dc7a32598e5badb887cb3b40b77f8604702b49075d32bbb49`, nonblank and unclipped. Visible context includes the eight locked drift values, resolved drift/cutoff/label/baseline windows, exact `id`, `label`, event timestamp, and 90-day order feature for the first ten synthetic IDs, plus both source CSV names. No secrets or real PII are present; no redaction was required. It proves local parsed-configuration-to-training linkage only and explicitly does **not** prove Spark/dbt, Airflow, DataHub, Feast, GKE/GCP, final promotion, or rubric satisfaction. |
| Cleanup / runtime release | `--clean` retained exactly the verified pending candidate bundle above, left `staging_count=0`, and did not create or change `section03_manifest.json`; `previous_bundle_id=null`. Required canonical raw outputs remain generator-managed local data. All pytest processes left by bounded timeouts were identified by exact command line and stopped; no service, container, Kind/GKE context, kubeconfig, Docker resource, cloud resource, or GCP runtime was acquired or mutated. Final Section 01 tracked content hashes equal `HEAD`; no runtime remains to release. |
| Limitations | The valid pending candidate remains diagnostic and earns zero points for `Sheet3!E32:E34`. Empirical drift monitoring is Partial because peak PSI `0.068131800343` is below warning `0.10`; therefore neither a warning nor alert observation exists, and the empty alert artifact is truthful. Spark/dbt parity, Airflow, DataHub, Feast, strict finalization, GKE/GCP, and UI/runtime captures remain successor-owned. |
| Successor handoff | Topic 03 may consume candidate manifest SHA-256 `ba9fc1e83291d27a61c9558d720d6db411ec2bc5d05bc8b10852d8bec266e7a6` and bundle `08c3ed4561bf17c0359ed8741d7d2bbd3fe8e52ab5aa088ea75e8532670b6e49` for contract development, but it must carry the empirical-PSI Partial disposition and must not treat the candidate as a satisfied predecessor or rubric proof. Identity: `scale=medium`, seed `42`, history `60`; windows `2026-03-03T23:59:00Z`→`2026-05-01T23:59:00Z`, drift `2026-04-11T08:23:00Z`, cutoff `2026-04-24T23:59:00Z`, label end `2026-05-01T23:59:00Z`, baseline `2026-04-10`; fixed PSI cohort `11,966`. Topic 07 must not promote until the locked empirical warning requirement is resolved without changing thresholds or manufacturing evidence. |
