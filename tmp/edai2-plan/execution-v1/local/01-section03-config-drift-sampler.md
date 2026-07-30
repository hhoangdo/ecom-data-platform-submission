# Section 03 Configuration and Drift Sampler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Section 03 Tasks 1–2: strict typed drift configuration and deterministic order-timestamp redistribution without changing entity counts, disabled output, shared-RNG state, or non-time stochastic choices.

**Architecture:** `configs/generator/base.yaml` is the single deployment contract. `GeneratorConfig` owns frozen `DriftConfig`; `resolve_drift_window()` derives every boundary; `generate_order_timestamps_with_drift()` uses a child RNG while advancing the shared RNG exactly as the legacy call did.

**Tech Stack:** Python 3.12, NumPy, Pandas, PyYAML, pytest, `uv`, Make, `rtk`.

## Locked sources and execution policy

- Read `C:\Users\oou1hc\.codex\RTK.md`; every shell command begins with `rtk`.
- Section 03 source is `tmp/edai2-plan/03_data_generator_improvement.md`, SHA-256 `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`.
- EDAI2 source is `tmp/edai2-plan/04.2_llm_design.md`, SHA-256 `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`.
- Rubric source is `tmp/rubic-check/Coursework Tracking (Public).xlsx`, SHA-256 `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- Work on the current branch in one serial session. Do not create a worktree or branch and do not stage, commit, push, or open a PR.
- Do not mutate GCP. Any Kubernetes command requires explicit `KUBECONFIG` and `--context`; this topic needs neither.
- Kind is local smoke only and never GKE evidence. Do not prune Docker or stop unrelated containers.

## Metadata

| Field | Decision |
|---|---|
| Phase | 1 — Section 03 generator contract |
| Source tasks | Section 03 Tasks 1–2 |
| Rubric contribution | Supporting evidence for `Sheet3!E32:E33`; Topic 07 is sole primary owner |
| Prerequisites | Topic 00 Completion Record |
| Blocked successors | Topic 02 |
| Runtime ownership | Local Python test operator; one serial session |
| Local/GCP class | Local-only; no GCP mutation |

## Global constraints

- The YAML mapping is exactly `enabled`, `scenario`, `mode`, `cutoff_fraction`, `post_rate_multiplier`, `psi_warning`, `psi_alert`, `label_horizon_days`.
- Fixed values are `customer_order_frequency`, `abrupt`, `0.65`, `1.5`, `0.10`, `0.15`, and `7`; only `enabled` may be false for legacy-equivalence tests.
- Smoke history is 14 days. No entity count changes.
- Disabled mode immediately returns `random_timestamps(rng, start_ts, end_ts, size, evening_bias=True)` and performs no random call, allocation, sort, or validation before delegating.
- Enabled mode canonicalizes and hashes the pre-call `rng.bit_generator.state` with namespace `section03-order-timestamps-v1` to seed an isolated child `np.random.Generator`, then calls the unchanged legacy sampler once and discards its values solely to advance the shared RNG by exactly the legacy amount. Only the child RNG may drive the drift sample.
- The child sampler builds one-minute candidate slots from `start_ts.floor("min")` through `end_ts.floor("min")` inclusive and retains the current 24 hourly weights. For slot `t`, it calculates `raw_weight[t] = hourly_weight[t.hour] * (drift.post_rate_multiplier if t >= drift_start_ts else 1.0)` without rounding the cutoff, then `probability = raw_weight / raw_weight.sum()`. It samples `size` slot indices with replacement, adds child-RNG seconds drawn from `[0, 59]` inclusive, clips to the current inclusive generator bounds, and returns a stable `pd.Series` in draw order.
- `summarize_drift_rates` uses exact elapsed seconds on each side of `drift_start_ts` and reports `(post_count / post_duration_days) / (pre_count / pre_duration_days)`.
- The canonical medium fixture has 45,000 orders and normalized post/pre rate in inclusive `[1.35,1.65]`.
- Make recipes use `uv run`; operator commands use `rtk uv run`.

## Current-state refresh — read-only planning phase

```text
rtk git status --short --branch
rtk git branch --show-current
rtk rg -n "GeneratorConfig|random_timestamps|_generate_orders|history_days" configs/generator/base.yaml src/vina_bim_shop/generators tests/unit
rtk uv run pytest tests/unit/test_generator_config.py tests/integration/test_section01_generator.py -q
```

Expected: the same branch is recorded, existing config/order APIs are visible, and the pre-change tests pass or a pre-existing failure is recorded before edits.

## Scope and non-goals

In scope: typed config, strict parsing, resolved Section 03 evidence root, 14-day smoke history, drift windows, normalized sampling, order integration, disabled equivalence, RNG-state equivalence, and keyed non-time stochastic projection. Non-goals: labels, PSI artifacts, dbt, Spark, Airflow, DataHub, Feast, model training, GCP, and adjacent config refactors.

## Exact file map

| Action | Exact path | Responsibility |
|---|---|---|
| Modify | `configs/generator/base.yaml` | Add the enabled drift mapping and `outputs.section03_evidence_root`; change only smoke history to 14 days. |
| Modify | `src/vina_bim_shop/generators/config.py` | Add frozen `DriftConfig`, strict parser, `GeneratorConfig.drift`, and resolved Section 03 root. |
| Create | `src/vina_bim_shop/generators/drift.py` | Define windows, deterministic sampler, realized-rate summary, and later PSI boundary. |
| Modify | `src/vina_bim_shop/generators/offline/orders.py` | Route only order timestamp assignment through the drift sampler. |
| Modify | `tests/unit/test_generator_config.py` | Test exact accepted values and every invalid mapping. |
| Create | `tests/unit/test_section03_drift.py` | Test windows, sampling, counts, rate, disabled equivalence, RNG state, and keyed projections. |
| Modify | `tests/unit/test_generator_module_split.py` | Permit `drift`, `labels`, and `drift_evidence` while preserving legacy import/re-export rules. |

## Interfaces and data flow

`load_generator_config(path, scale, overrides)` preserves its signature and returns `GeneratorConfig.drift: DriftConfig`. `resolve_drift_window(config) -> DriftWindow` derives `drift_start_ts`, `feature_cutoff_ts`, `label_end_ts`, and monitoring boundaries. The sampler and rate-summary interfaces are exactly:

```python
def generate_order_timestamps_with_drift(
    rng: np.random.Generator,
    *,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
    size: int,
    drift: DriftConfig,
) -> pd.Series: ...


def summarize_drift_rates(
    timestamps: pd.Series,
    *,
    window: DriftWindow,
) -> DriftRateSummary: ...
```

`_generate_orders` keeps its public and internal signatures.

## Failure modes

Reject non-mappings, missing or unknown keys, non-boolean `enabled`, booleans/nonfinite numeric values, unsupported scenario/mode, any legal-looking but unapproved value, insufficient baseline history, empty pre/post partitions, count drift, rate outside acceptance, altered shared RNG state, altered non-time customer/product/order-item/payment/shipment/quality/event decisions, or disabled output differences.

## Ordered test-first execution tasks

- [ ] Run `rtk uv run pytest tests/unit/test_generator_config.py tests/integration/test_section01_generator.py -q`; expected PASS as the recorded pre-change baseline, otherwise stop and record the exact pre-existing failure.
- [ ] Add the Task 1 failing assertions, then run `rtk uv run pytest tests/unit/test_generator_config.py -q`; expected FAIL because `DriftConfig`, the exact YAML mapping, validation errors, and isolated Section 03 root do not exist.
- [ ] Implement only `configs/generator/base.yaml` and `src/vina_bim_shop/generators/config.py`, then run `rtk uv run pytest tests/unit/test_generator_config.py -q`; expected PASS with all eight values, 14-day smoke history, unchanged entity counts, and exact dotted-key errors.
- [ ] Add tests for the exact keyword-only sampler/rate interfaces; immediate disabled delegation and byte/frame equivalence; canonical child seed and shared-RNG-state equality; inclusive one-minute slots; retained hourly weights; post-cutoff multiplier and normalized probabilities; with-replacement indices; child seconds `0..59`; inclusive clipping; stable draw order; the exact elapsed-time rate formula; the 45,000-order acceptance interval; and enabled-vs-legacy keyed non-time projections. Run `rtk uv run pytest tests/unit/test_section03_drift.py -q`; expected FAIL because the drift module and order hook are absent.
- [ ] Implement `src/vina_bim_shop/generators/drift.py` and the narrow order hook, then run `rtk uv run pytest tests/unit/test_section03_drift.py tests/unit/test_generator_module_split.py -q`; expected PASS with the exact sampler algorithm, the shared RNG equal to one direct legacy call, and keyed non-time choices exactly equal.
- [ ] Run `rtk uv run pytest tests/unit/test_generator_config.py tests/unit/test_section03_drift.py tests/unit/test_generator_module_split.py tests/integration/test_section01_generator.py -q`; expected PASS with zero failures, skips, or xfails in the listed files.
- [ ] Run `rtk git diff --check`, `rtk git status --short --branch`, and `rtk git ls-files --stage`; expected no whitespace errors, the original branch unchanged, only the exact file map changed, and the final index listing is byte-for-byte identical to the pre-topic listing. Pre-existing staged entries are user-owned; do not stage or unstage them.

## Evidence and screenshot ownership

The Topic 01 operator owns test logs and the measured local rate summary. No screenshot is required or scoreable here. Topic 07 alone binds these implementation results into the strict Section 03 evidence bundle.

## Cleanup

Tests write only fixture-managed temporary roots. Do not clean canonical evidence, stop containers, prune Docker, alter kubeconfig, or delete user files. Record that no runtime was acquired.

## Rubric table

| Workbook cell | Supporting proof | Ownership rule |
|---|---|---|
| `Sheet3!E32` | Fixed-count deterministic timestamp redistribution and measured rate | Supporting only; Topic 07 promotes evidence |
| `Sheet3!E33` | Strict typed YAML and configuration-derived timestamps | Supporting only; Topic 07 promotes evidence |

## Definition of Done

Configuration and sampler tests pass; disabled output and shared-RNG state match legacy behavior; enabled output changes only timestamp-derived fields; counts are fixed; rate acceptance passes; exact interfaces remain compatible; scoped diff checks pass.

## Completion Record

| Field | Record |
|---|---|
| Status | **Complete after the post-topic streaming determinism repair.** Typed configuration, deterministic timestamp redistribution, disabled/frame/RNG equivalence, fixed counts, exact sampler/rate interfaces, keyed streaming quality/synthetic choices, private-lineage containment, and the medium rate criterion all pass. The original Partial result and measured failure are retained in the initial execution log and repair diagnosis below. |
| Affected files | Original implementation: `configs/generator/base.yaml`; `src/vina_bim_shop/generators/config.py`; `src/vina_bim_shop/generators/drift.py`; `src/vina_bim_shop/generators/offline/orders.py`; `tests/unit/test_generator_config.py`; `tests/unit/test_section03_drift.py`; `tests/unit/test_generator_module_split.py`. Authorized repair: `src/vina_bim_shop/generators/streaming/session_events.py`; `src/vina_bim_shop/generators/streaming/generator.py`; `src/vina_bim_shop/generators/streaming/topic_commerce.py`; `tests/unit/test_section03_drift.py`; this Completion Record. No dependency files changed. |
| Commands / exit codes | Initial checkbox commands remain in the original execution log. The repair log below records its complete red/green and acceptance sequence. Latest acceptance: Topic 01 gate `0` (`68 passed`); streaming/CLI regressions `0` (`2 passed`); Topic 02 predecessor refresh `0` (`20 passed`); medium rate command `0`; `rtk git diff --check` `0`; `rtk git ls-files --stage` `0`; normalized index-listing hash command `0`; `rtk git status --short --branch` `0`. |
| Evidence + SHA-256 | Machine evidence is the authoritative terminal output; **no artifact produced**. `configs/generator/base.yaml` SHA-256 `5c5029fea77d93c3941d87d9a60f85cfe374f36899c3d3c1b028f3f5f3c3cd97`; `src/vina_bim_shop/generators/drift.py` SHA-256 `4de704f2a987e2e76ab933ad2226f8a3dc1674bdfd56992199ce569aea6fee5a`. Medium result: `pre_count=24717`, `post_count=20283`, `pre_duration_days=38.35`, `post_duration_days=20.65`, `pre_rate_per_day=644.5110821382008`, `post_rate_per_day=982.227602905569`, normalized ratio `1.5239886948832209` (inside inclusive `[1.35, 1.65]`). |
| Screenshot QA | No screenshot required, captured, or manufactured for Topic 01. Successor topics retain final UI-capture ownership. |
| Cleanup / runtime release | Pytest used fixture-managed temporary directories. No service, container, Kind cluster, Kubernetes context, cloud runtime, or GCP resource was acquired; no runtime cleanup was required. Docker data and unrelated containers were untouched. |
| Resource / budget gates | Local Python only. No live GCP mutation, billable resource, Kubernetes command, kubeconfig change, or local Kind/GKE evidence claim occurred. |
| Limitations | Local-only supporting evidence; no Spark, Airflow, DataHub, GKE, runtime, screenshot, or rubric-score claim. The prior streaming keyed non-time limitation is resolved by private source lineage that is verified not to appear in public topic outputs. |
| Rollback / recovery | The original Topic 01 implementation is present at the pre-repair HEAD. Recovery for this repair is limited to the three streaming modules, `tests/unit/test_section03_drift.py`, and this Completion Record; do not alter the index or unrelated files. |
| Rubric disposition | Supporting implementation evidence only for `Sheet3!E32:E33`; no score is claimed. Topic 07 remains the sole primary evidence owner. |
| Successor handoff | **Topic 02 is unblocked.** Its exact predecessor refresh `rtk uv run pytest tests/unit/test_section03_drift.py tests/integration/test_section01_generator.py -q` exits `0` with `20 passed`. Config hash is `5c5029fea77d93c3941d87d9a60f85cfe374f36899c3d3c1b028f3f5f3c3cd97`; sampler hash is `4de704f2a987e2e76ab933ad2226f8a3dc1674bdfd56992199ce569aea6fee5a`. Smoke window: start `2026-04-18T23:59:00`, drift `2026-04-27T10:47:00`, feature cutoff `2026-04-24T23:59:00`, label end/end `2026-05-01T23:59:00`, baseline date `2026-04-26`. Medium window: start `2026-03-03T23:59:00`, drift `2026-04-11T08:23:00`, feature cutoff `2026-04-24T23:59:00`, label end/end `2026-05-01T23:59:00`, baseline date `2026-04-10`. Interfaces remain unchanged. Latest Topic 01 full gate: `68 passed`; medium normalized ratio `1.5239886948832209`. |

### Execution command log

| Command | Exit | Result |
|---|---:|---|
| `rtk git status --short --branch` | 0 | Began clean on `feature/implement-edai2...origin/feature/implement-edai2`. |
| `rtk git ls-files --stage` | 0 | Pre-edit index listing captured: 773 lines; normalized SHA-256 `2526340f5b479315777b5310dfbd996ce095aaf1121c163bbd5eb474fac1b84e`. |
| `rtk certutil -hashfile tmp/edai2-plan/03_data_generator_improvement.md SHA256` | 0 | Locked hash matched `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`. |
| `rtk certutil -hashfile tmp/edai2-plan/04.2_llm_design.md SHA256` | 0 | Locked hash matched `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`. |
| `rtk certutil -hashfile "tmp/rubic-check/Coursework Tracking (Public).xlsx" SHA256` | 0 | Locked hash matched `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`. |
| `rtk uv run pytest tests/unit/test_generator_config.py tests/integration/test_section01_generator.py -q` | 0 | Pre-change baseline: `4 passed`. |
| `rtk uv run pytest tests/unit/test_generator_config.py -q` | 1 | Task 1 red: `DriftConfig` was absent. |
| `rtk uv run pytest tests/unit/test_generator_config.py -q` | 0 | Task 1 green after minimum implementation: `41 passed`. |
| `rtk uv run pytest tests/unit/test_section03_drift.py -q` | 1 | Task 2 red: drift module was absent. |
| `rtk uv run pytest tests/unit/test_section03_drift.py tests/unit/test_generator_module_split.py -q` | 1 | First implementation run: three failures exposed two test-harness ordering errors and the streaming event-type invariant. |
| `rtk uv run pytest tests/unit/test_section03_drift.py tests/unit/test_generator_module_split.py -q` | 1 | One bounded retry after correcting only the test harness: `1 failed, 18 passed`; streaming event-type invariant remained. |
| `rtk uv run pytest tests/unit/test_generator_config.py -q` | 1 | Review red: mixed-type unknown drift keys leaked `TypeError` (`1 failed, 42 passed`). |
| `rtk uv run pytest tests/unit/test_generator_config.py -q` | 0 | Review green after insertion-order unknown-key validation: `43 passed`. |
| `rtk uv run python -c "from dataclasses import asdict; from pathlib import Path; import json; import numpy as np; from vina_bim_shop.generators.config import load_generator_config; from vina_bim_shop.generators.drift import generate_order_timestamps_with_drift, resolve_drift_window, summarize_drift_rates; c=load_generator_config(Path('configs/generator/base.yaml'), scale='medium'); w=resolve_drift_window(c); t=generate_order_timestamps_with_drift(np.random.default_rng(c.random_seed), start_ts=w.start_ts, end_ts=w.end_ts, size=c.entities['orders'], drift=c.drift); print(json.dumps(asdict(summarize_drift_rates(t, window=w)), sort_keys=True))"` | 0 | Medium normalized ratio `1.5239886948832209`. |
| `rtk uv run pytest tests/unit/test_generator_config.py tests/unit/test_section03_drift.py tests/unit/test_generator_module_split.py tests/integration/test_section01_generator.py -q` | 1 | Final pre-record acceptance: `1 failed, 64 passed`; exact streaming count differences are recorded above. |
| `rtk git diff --check` | 0 | No whitespace errors. |
| `rtk git ls-files --stage` | 0 | Final pre-record listing remained 773 lines. |
| `rtk powershell -NoProfile -Command '$lines = & rtk git ls-files --stage; $text = [string]::Join("`n", $lines) + "`n"; $bytes = [Text.Encoding]::UTF8.GetBytes($text); $sha = [Security.Cryptography.SHA256]::Create(); ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace("-", "").ToLowerInvariant()'` | 0 | Final pre-record index SHA-256 `2526340f5b479315777b5310dfbd996ce095aaf1121c163bbd5eb474fac1b84e`, byte-for-byte equal to pre-edit. |
| `rtk git status --short --branch` | 0 | Branch unchanged; only the seven Topic 01 implementation/test paths were modified or added before this Completion Record update; no staged entries. |

### Post-topic streaming determinism repair

The original failure was preserved and reproduced on pre-repair HEAD `6c2c7c0`. Both streams had identical pre-duplicate counts: `add_to_cart=2025`, `checkout_started=1890`, `order_placed=1800`, `payment_failed=50`, `view=6626`. Chronological sorting changed the row sequence before index-based duplication. The legacy-hook duplicate distribution was `add_to_cart=37`, `checkout_started=33`, `order_placed=30`, `payment_failed=1`, `view=84`; drift produced `29/24/27/1/104`. Private source event/session ordinals now bind quality decisions and synthetic session cohorts before timestamp sorting. After repair, both runs produce the same duplicate distribution: `add_to_cart=27`, `checkout_started=26`, `order_placed=22`, `view=110`; the total remains 185 and private lineage is absent from all public topics.

| Command | Exit | Result |
|---|---:|---|
| `rtk git status --short --branch` | 0 | Repair began clean on `feature/implement-edai2...origin/feature/implement-edai2`. |
| `rtk git branch --show-current` | 0 | `feature/implement-edai2`. |
| `rtk git ls-files --stage` | 0 | Pre-repair listing captured: 775 lines. |
| Normalized `rtk git ls-files --stage` SHA-256 command | 0 | Pre-repair index digest `6ada08b5fd9d6d3077d09f03ed1f7f4aa90032e7a83f227faac0447850b31715`. |
| Three locked `rtk certutil -hashfile ... SHA256` commands | 0 each | All authoritative hashes matched their locked values. |
| `rtk uv run pytest tests/unit/test_section03_drift.py -q` | 1 | Repair RED: `3 failed, 14 passed`; failures were the original event counts, absent stable lineage, and timestamp-ranked synthetic cohorts. |
| `rtk uv run pytest tests/unit/test_section03_drift.py::test_enabled_generation_changes_only_timestamp_derived_offline_fields tests/unit/test_section03_drift.py::test_enabled_stream_quality_choices_follow_source_lineage tests/unit/test_section03_drift.py::test_disabled_streaming_skips_stable_lineage_helper -q` | 0 | First GREEN: `3 passed`; keyed quality/counts fixed and disabled path retained. |
| `rtk uv run pytest tests/unit/test_section03_drift.py::test_enabled_synthetic_commerce_choices_follow_source_lineage_without_leaks -q` | 1 | Second RED: synthetic order-session choices still differed. |
| `rtk uv run pytest tests/unit/test_section03_drift.py::test_enabled_synthetic_commerce_choices_follow_source_lineage_without_leaks -q` | 0 | Second GREEN: `1 passed`; stable synthetic cohorts and no private-field leakage. |
| `rtk uv run pytest tests/unit/test_section03_drift.py -q` | 0 | Focused repair suite: `17 passed`. |
| `rtk uv run pytest tests/unit/test_generator_config.py tests/unit/test_section03_drift.py tests/unit/test_generator_module_split.py tests/integration/test_section01_generator.py -q` | 0 | Complete Topic 01 gate: `68 passed`. |
| `rtk uv run pytest tests/integration/test_kafka_topic_outputs.py tests/integration/test_generator_cli.py -q` | 0 | Streaming/CLI regressions: `2 passed`. |
| `rtk uv run pytest tests/unit/test_section03_drift.py tests/integration/test_section01_generator.py -q` | 0 | Topic 02 predecessor refresh: `20 passed`. |
| Existing medium rate command | 0 | `45,000` orders; normalized ratio unchanged at `1.5239886948832209`. |
| Repaired duplicate-distribution diagnostic | 0 | Legacy-hook and drift distributions both `27/26/22/110` for add/cart, checkout, order, and view; 185 duplicates total. |
| `rtk git diff --check` | 0 | No whitespace errors before Completion Record update. |
| `rtk git ls-files --stage` | 0 | Pre-record final listing remained 775 lines. |
| Normalized `rtk git ls-files --stage` SHA-256 command | 0 | Pre-record final digest remained `6ada08b5fd9d6d3077d09f03ed1f7f4aa90032e7a83f227faac0447850b31715`, byte-for-byte equal to pre-repair. |
| `rtk git status --short --branch` | 0 | Before this record update, only the three authorized streaming modules and `tests/unit/test_section03_drift.py` were modified; no staged entries. |
