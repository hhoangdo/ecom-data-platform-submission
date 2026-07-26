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
| Status | Not started |
| Affected files | Record only exact file-map paths actually changed |
| Commands / exit codes | Record every checkbox command and numeric exit code, ending with `rtk git status --short --branch` |
| Evidence + SHA-256 | Record test-log/rate-report paths and hashes, or `no artifact produced` |
| Screenshot QA | No screenshot required for Topic 01 |
| Cleanup / runtime release | Record fixture cleanup and `no runtime acquired` |
| Limitations | Record measured local-only limitations; no Spark/Airflow/DataHub claim |
| Successor handoff | Provide config hash, resolved windows, sampler API, and test results to Topic 02 |
