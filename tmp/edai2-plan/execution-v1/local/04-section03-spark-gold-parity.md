# Section 03 Spark Gold and Parity Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Plan Task 6: render and test seven parameterized Spark Gold relations and prove keyed full-row parity against dbt and generator evidence.

**Architecture:** One parsed generator configuration creates `Section03SqlParameters` for Spark query rendering and exact keyed parity reports against generator/dbt outputs.

**Tech Stack:** Python 3.12, Spark SQL, DuckDB/Trino test doubles, pytest, `uv`, Make, `rtk`.

## Locked sources and acceptance procedure

- Read `C:\Users\oou1hc\.codex\RTK.md` before every operator session and prefix every shell command with `rtk`.
- Locked Section03 source: `tmp/edai2-plan/03_data_generator_improvement.md`, SHA256 `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`.
- Locked EDAI2 source: `tmp/edai2-plan/04.2_llm_design.md`, SHA256 `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`.
- Locked rubric source: `tmp/rubic-check/Coursework Tracking (Public).xlsx`, SHA256 `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- Preflight and final acceptance both run `rtk git status --short --branch`; record the output and reject a branch change during the serial session.
- Final acceptance also records SHA256s, evidence/screenshot QA, cleanup/runtime release, limitations, and successor handoff in the Completion Record.
- Keep one current branch and one serial session; any Kubernetes action sets `KUBECONFIG` and `--context` explicitly, never the corporate current context.
- Kind is local smoke only and never GKE/rubric evidence; do not run Docker prune or stop unrelated containers.

## Metadata

| Field | Decision |
|---|---|
| Phase | 4 — analytic parity |
| Source tasks | Section03 Task 6 |
| Rubric contribution | Supporting evidence for `Sheet3!E34` only; Topic 07 is sole primary owner |
| Prerequisites | Topic 03 Completion Record and candidate manifest identity |
| Blocked successors | Topic 05 only |
| Runtime ownership | Spark/parity operator; serial session |
| Local/GCP class | Local/mock Spark test; no GCP |

## Architecture and technology

The Spark stage accepts generator config/scale, calculates `Section03SqlParameters` once, and renders the same seven DP3 tables in dependency order. In strict Section 03 mode, `scripts/spark/run_batch.py` derives `start_ts`, `end_ts`, feature cutoff, label end, drift start, and baseline date from that parsed config and scale. Explicit `--start-ts`/`--end-ts` values are rejected unless they exactly match those derived values. Parity compares keyed full rows—generator versus dbt and generator versus Spark—not only aggregates. Float persistence is normalized at twelve decimal places with absolute tolerance `1e-9`; labels/keys/timestamps/strings are exact.

## Global constraints

The three locked hashes above remain authoritative. Work on the current branch in one serial session; do not create a worktree or branch and do not stage, commit, push, or open a PR. `REQUIRED_GOLD_TABLES` has no duplicates; core and DP3 sets are disjoint. No hard-coded cutoff/threshold/horizon. Operators use `rtk uv run`; Make recipes are `uv run`. Do not invoke GKE/GCP, prune Docker, or stop unrelated containers.

## Current-state refresh — read-only planning phase

```text
rtk git branch --show-current
rtk git status --short --branch
rtk uv run pytest tests/unit/test_spark_batch_runtime.py tests/unit/test_optional_duckdb_imports.py -q
rtk rg -n "GOLD_SERVING_TABLES|REQUIRED_GOLD_TABLES|ordered_core_gold_queries" src scripts tests
```

Expected: existing query order and test baseline are recorded without writing tables.

## Scope and non-goals

In scope: parameter propagation, SQL rendering, seven-table registration, full-row parity tests/reports. Out of scope: real cluster provisioning, running Airflow/DataHub, chart deployment, and modifying generator public APIs.

## Exact file map

| Action | Path |
|---|---|
| Modify | `src/vina_bim_shop/lakehouse/spark/sql.py`, `src/vina_bim_shop/lakehouse/spark/constants.py`, `src/vina_bim_shop/lakehouse/spark/job.py`, `src/vina_bim_shop/lakehouse/spark/runner.py`, `src/vina_bim_shop/lakehouse/spark/parity.py` |
| Modify | `scripts/spark/run_batch.py` |
| Modify | `tests/unit/test_spark_batch_runtime.py` |
| Modify | `tests/unit/test_optional_duckdb_imports.py` |

## Interfaces, data flow, and failure modes

Config/scale → derived batch/window timestamps and `Section03SqlParameters` → rendered Spark queries → seven persisted outputs → keyed comparison report. Fail on missing config/scale, an explicit batch timestamp that differs from the config-derived value, supplied cutoff not present in SQL, leakage predicates absent, inaccurate percentile shortcut, missing/extra key, nonexact label, nonfinite PSI, tolerance violation, or a candidate manifest/hash mismatch.

## Ordered test-first execution tasks

- [ ] Add failing query-order/leakage, strict config-derived batch-window, explicit mismatch, and four keyed full-row comparison tests, then run `rtk uv run pytest tests/unit/test_spark_batch_runtime.py -q`; expected FAIL because parameterized DP3 queries and strict batch semantics are absent.
- [ ] Thread `--generator-config` and `--generator-scale` through `job.py`, `runner.py`, `scripts/spark/run_batch.py`, and submit construction, then run `rtk uv run pytest tests/unit/test_spark_batch_runtime.py -q`; expected FAIL only on missing seven-query/table/parity contracts while config, scale, and derived start/end/cutoff metadata pass.
- [ ] Implement the seven exact Spark queries, type-7 PSI, ordered `DP3_GOLD_TABLES`, extended `GOLD_SERVING_TABLES`, and duplicate-free `REQUIRED_GOLD_TABLES`, then run `rtk uv run pytest tests/unit/test_spark_batch_runtime.py -q`; expected FAIL only on missing keyed parity report assertions.
- [ ] Implement generator-vs-dbt, generator-vs-Spark, and dbt-vs-Spark reports; production passes validated runtime values equivalent to `scripts/analytics/run_section03_dbt.py --project-dir infra/analytics/dbt --profiles-dir infra/analytics/dbt --config configs/generator/base.yaml --scale medium` as a direct argument array, then run `rtk uv run pytest tests/unit/test_spark_batch_runtime.py -q`; expected PASS with separate zero mismatch counts and bound manifest/config hashes.
- [ ] Run `rtk uv run pytest tests/unit/test_spark_batch_runtime.py tests/unit/test_optional_duckdb_imports.py -q`; expected PASS with cutoff-safe SQL, derived timestamps, ordered seven-table persistence, and no optional DuckDB import regression.
- [ ] Run `rtk git diff --check`, `rtk git status --short --branch`, and `rtk git ls-files --stage`; expected no whitespace errors, the original branch unchanged, only exact file-map paths changed, and the final index listing is byte-for-byte identical to the pre-topic listing. Pre-existing staged entries are user-owned; do not stage or unstage them.

## Evidence and screenshot ownership

The parity operator owns command logs and sanitized parity report containing candidate/config hashes and both comparison families. This is machine proof for finalization, not a GKE screenshot.

## Cleanup

Clean only session-owned local/mock tables and reports after hashes are retained; do not delete canonical bundles or unrelated Spark resources.

## Rubric table

| Cell | Parity contribution | Final scoring |
|---|---|---|
| Sheet3!E34 | Exact label key/values and training join | Section03 strict root required |

## Definition of Done

The seven outputs render in required order, all leakage/PSI parity tests pass, and a hash-bound no-mismatch report is available to runtime promotion.

## Completion Record

### Final execution update - 2026-08-04

The update below is authoritative for this execution. The older table rows that follow are retained as historical pre-remediation diagnostics and are superseded where they conflict with this update.

| Field | Final record |
|---|---|
| Status | **Partial.** The Bosch CA image, MinIO proxy contract, dbt contracts, complete 26-table Gold graph, Section 02 evidence, and generator/dbt rebaseline are repaired and locally verified. Both identical bounded strict Spark attempts ended with the executor killed (exit 143) before the `r2` evidence root was published. Generator-vs-dbt still has one semantic training-row mismatch. No three-way parity pass is claimed. |
| Assumptions verified | Branch stayed `feature/implement-edai2`; no branch/worktree/index mutation, commit, push, PR, Kubernetes, Kind, GCP, or cloud-runtime action occurred. The initial pre-existing Topic 04 Completion Record modification was preserved. The initial original Section 03 hash `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f` matched before the explicitly authorized Topic 03 serialization rebaseline; the final locked source hash is recorded below. |
| Affected files and interfaces | Topic 03 scope gate: `src/vina_bim_shop/generators/drift_evidence.py`, `tmp/edai2-plan/03_data_generator_improvement.md`, `tmp/edai2-plan/execution-v1/local/03-section03-dbt-gold-contracts.md`, the new Section 03 candidate pointer/bundle, and regenerated Section 01 evidence. Topic 04/runtime: `infra/lakehouse/minio/create-buckets.sh`, `infra/analytics/dbt/models/gold/feat_stream_60m.sql`, `infra/analytics/dbt/tests/assert_training_features_are_point_in_time.sql`, `src/vina_bim_shop/lakehouse/spark/sql.py`, `src/vina_bim_shop/lakehouse/spark/runner.py`, `scripts/analytics/run_section03_dbt.py`, and focused tests. Section 02 maintenance: `scripts/README.md`, `scripts/qa/generate_section02_evidence.py`, `scripts/qa/build_mini_coursework_rubric_manifest.py`, the three Gold diagrams, regenerated Section 02/final-integration evidence, and their tests. The CA Dockerfile/certificate were verified but not changed. Existing public Spark interfaces and the default DP3 selector were preserved; `--all-gold` is explicit internal strict-runtime mode. |
| Ordered execution and results | Generator command `rtk uv run python scripts/generate/run_generator.py --scale medium --mode full --seed 42` returned outer-shell exit `124` after the child continued and published the bundle; verifier `rtk uv run python scripts/generate/verify_section03_manifest.py --manifest evidence/03_data_generator_improvement/section03_candidate_manifest.json --allow-runtime-pending` returned `0` (`PASS`, runtime pending). The default dbt wrapper first returned `1` because the singular point-in-time test still lacked the lower 60-minute predicate (`8,991` rows); after the minimum correction it returned `0`, `PASS=88 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=88`. Explicit `--all-gold` returned `0`, `PASS=133 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=133`; a read-only DuckDB inventory returned exactly 26 required Gold base tables with no missing, unexpected, or duplicate names. The MinIO contract/runtime tests and focused Topic 04 suite returned `0` (`51 passed`). `rtk make up-batch` returned `0`; `minio-init` exited successfully and required services became healthy. Section 02 evidence generation returned `0`; the first manifest-builder diagnostic returned `1` because measured dbt test count was 90 rather than stale 66, then the corrected builder returned `0` with all 45 rubric checks satisfied; verification returned `0`; physical Gold PNG rendering returned `0`; Section 02 focused tests returned `0` (`30 passed`). CA revalidation build returned `0`; the in-image CA/Maven probe returned `0`; host `openssl.exe` returned `1` because OpenSSL is unavailable on Windows; image fingerprint verification returned `0`. The exact strict `run_batch.py` command with the prescribed window was run twice against `tmp/section03-runtime/topic04-spark-gold-20260804-r2`: attempt one returned `1` after about 294 seconds with executor exit 143; the one allowed identical retry returned `1` after about 324 seconds with executor exit 143. No `r2` evidence was published. `rtk make down-batch` returned `0`. Final focused regression returned `0` (`36 passed`); the first full suite returned `1` (`495 passed, 1 skipped, 1 intermittent Windows WinError 5 rename failure`); three fresh manifest-verifier module runs returned `0` (`9 passed` each); final full suite returned `0` (`496 passed, 1 skipped`). |
| Remaining measured issues | Generator-vs-dbt keyed comparison returned zero mismatches for `ml_customer_label`, `agg_feature_health_daily`, and `feature_drift_alerts`. `ml_customer_purchase_training` has one field-mismatched key: `CUS-NTR-00004611`; generator values are `f_stream_add_to_cart_60m=1` and `f_stream_cart_to_purchase_ratio_60m=1.000000000000`, while dbt values are `0` and `0.0`. The raw/staging event trace shows the add-to-cart at 22:59 and order at 23:11; the generator aggregates the lower-bounded 60-minute window across hour buckets, while dbt preserves latest-hour selection. Tolerance was not relaxed and this remains fail-closed. The Spark executor termination prevented generator-vs-Spark and dbt-vs-Spark measurement. |
| Evidence and hashes | Final locked sources: Section 03 `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`, EDAI2 `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`, rubric workbook `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`. Candidate manifest `evidence/03_data_generator_improvement/section03_candidate_manifest.json`: `4af7f8a84da020877bea580f6fc74a9011d371ac2a84a56f7053e83f76246ba1`; bundle ID `1b4123b312da3d1aca70c2dc4f44cf68db248f3b43aad830e8519ca7bbab7fd3`; config `configs/generator/base.yaml`: `5c5029fea77d93c3941d87d9a60f85cfe374f36899c3d3c1b028f3f5f3c3cd97`. Candidate retained hashes: `runs/1b4123.../section03_report.md` `ebdbba5708bbfc8c24006b67204e65a460644bf8539fc4f0ceaf2d90587bd487`; training CSV `603e21581668d9de0147ff1dd58c36fd0a1d0aefed24f237bf6398d816800841`; health CSV `0d9a304b49fdae14aca134a11b8e3420fd202bf093535f1d7904fae8d020963f`; alerts CSV `b656dccc0c86abdf5896e3db1788f04a0fb128e27f2218331f8cc49df188e76a`; labels CSV `526304d4e2d97a70ed6671993b2f5bc07e934dfbd72488cb98c32dcb924f0278`; config snapshot `7405c3e2a27d87be522bea9de7dcc559ad8baff5274a8bed98f002b2753a9196`. Section 02 run manifest `evidence/02_schema_design/run_manifest.json`: `a52cc5fda6e1c4c51af6cfc7ca15e9e2c3fc16337a34336b58b0eff7bbc7f41e`; final rubric manifest `evidence/final_integration/mini_coursework_rubric_manifest.json`: `b753917eafea2867ec6d7f637afd987403f407f9e012137824e268ccd410ca1f`; physical Gold ERD PNG: `7257e13240e9979e6921a5439dd2bc32da212ef7d7586b634aeff2ce6bc50dc4`; updated PlantUML: `7f63df11487dc3b78b9ee62ea79a36a5772aee23a57ede3a259f57b840a6f5a1`. The new Spark `r2` root has no retained files or hashes because the executor was killed before publication; the prior `topic04-spark-gold-20260804` diagnostics remain immutable. |
| Screenshot QA | No Topic 04 screenshot was created or required; machine evidence is authoritative. Section 02 regenerated diagram screenshots are maintenance artifacts, not Spark/GKE evidence. Successor topics own final UI captures. |
| Cleanup and runtime release | Session-created `vina-bim-shop` containers, network, and volumes were released by `rtk make down-batch` with exit `0`; no Docker prune was run. All five pre-existing Docupedia MCP containers remained running. The regenerated complete Gold DuckDB/dbt graph and Section 02 evidence were intentionally retained for the approved Section 02 maintenance scope; the previous candidate bundle remains recoverable. No Kubernetes, Kind, GCP, or cloud runtime state was accessed or mutated. |
| Limitations | No Spark/Iceberg table counts, Great Expectations, Trino, executive-mart, generator-vs-Spark, or dbt-vs-Spark evidence exists for this continuation because the local executor was killed twice before publication. Resolving the one generator-vs-dbt semantic mismatch requires an explicitly authorized decision to align hour-bucket/latest-hour semantics or to aggregate the full lower-bounded 60-minute window in both implementations. This local result is not GKE evidence, final UI evidence, or E34 promotion evidence. |
| Rubric disposition | Supporting local evidence only for `Sheet3!E34`; Topic 07 remains the sole primary owner. Topic 04 remains `Partial`; local dbt/Section 02/CA results do not establish strict runtime or promotion credit. |
| Stop conditions | The one bounded Spark retry was exhausted after executor exit 143, and the one-row generator/dbt mismatch remained. No further retry, speculative tuning, certificate import, insecure TLS flag, Docker prune, unrelated-container stop, Kubernetes command, or GCP mutation was performed. |
| Successor handoff | Topic 05 remains blocked on the strict runtime gate. Obtain explicit scope for the remaining stream-semantic choice, then run the exact medium-window command in a fresh evidence root using bundle `1b4123b312da3d1aca70c2dc4f44cf68db248f3b43aad830e8519ca7bbab7fd3` and config SHA `5c5029fea77d93c3941d87d9a60f85cfe374f36899c3d3c1b028f3f5f3c3cd97`, with sufficient supported Spark runtime capacity. Require all 26 Gold relations, all seven ordered DP3 outputs, zero mismatches in all three parity families, and successful validation/Trino/mart evidence before considering Complete; Topic 07 owns any later GKE evidence. |

| Field | Record |
|---|---|
| Status | **Partial — The Bosch CA image, MinIO proxy contract, dbt contracts, complete 26-table Gold graph, Section 02 evidence, and generator/dbt rebaseline are repaired and locally verified. Strict local Spark/Iceberg execution remains incomplete: both identical bounded Spark attempts ended with the executor killed (exit 143) before the `r2` evidence root was published. The direct generator-vs-dbt check still has one semantic training-row mismatch, so no three-way parity pass is claimed.** |
| Affected files | Modified only this Completion Record during this continuation. The existing Topic 04 source/test files and the pre-existing CA Dockerfile, certificate, and CA contract test were inspected but not changed; no dbt, generator, orchestration, Kubernetes, or GCP file changed. Session-owned diagnostic evidence is under `tmp/section03-runtime/topic04-spark-gold-20260804/`. |
| Commands / exit codes | `rtk git status --short --branch` → `0`, unchanged `feature/implement-edai2`; all three locked-source `rtk certutil.exe -hashfile ... SHA256` checks → `0` with exact matches; pre-edit `rtk git ls-files --stage > C:\Users\oou1hc\AppData\Local\Temp\edai2-topic04-index-before.txt` → `0`. Candidate/config hashes → `0`, exact expected values. `rtk uv run pytest tests/unit/test_spark_dockerfile_ca.py -q` → `0` (`2 passed`); `rtk uv run pytest tests/unit/test_spark_batch_runtime.py -q` → `0` (`33 passed`). `rtk docker build --progress=plain -f infra/spark/Dockerfile -t vina-bim-shop-spark:ca-fixed .` → `0`; exact in-image CA/Maven probe → `0`; host `rtk openssl.exe ...` → `1` because OpenSSL is unavailable on the Windows host, substituted image OpenSSL fingerprint check → `0` and matched `BE:FE:A4:B1:F8:75:4F:18:C4:49:A0:D5:50:FF:E7:6D:AB:A6:09:F4:10:B6:5F:ED:1B:B4:06:4A:A6:D9:A3:06`. Direct dbt wrapper → `0`, `PASS=88 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=88`. Read-only inventory/parity diagnostic → `0`: `13/26` required Gold relations present, `13` missing, all seven DP3 present, and `ml_customer_purchase_training` has `9,592` field mismatches while the other three keyed checks have zero mismatches. Initial `rtk make up-batch` → `1` at `minio-init` HTTP 502; proxy-disabled `rtk docker compose --profile lakehouse --profile batch run --rm --no-deps -e HTTP_PROXY= -e HTTPS_PROXY= -e http_proxy= -e https_proxy= -e ALL_PROXY= -e all_proxy= -e NO_PROXY=minio,localhost,127.0.0.1 -e no_proxy=minio,localhost,127.0.0.1 minio-init` → `0`; one bounded proxy-disabled `rtk make up-batch` retry → `1` with the same `minio-init` dependency failure. `rtk make down-batch` → `0`; post-cleanup Docker check → `0`, no `vina-bim-shop` volumes remained. Predecessor DuckDB/dbt artifacts were restored and their original hashes reverified. Final `rtk uv run pytest tests/unit/test_spark_batch_runtime.py tests/unit/test_optional_duckdb_imports.py -q` → `0` (`35 passed`); final `rtk git diff --check` → `0`; final `rtk git diff --name-only` → `0` with only this Completion Record; final `rtk git status --short --branch` → `0` with only this Completion Record modified; final `rtk git ls-files --stage > C:\Users\oou1hc\AppData\Local\Temp\edai2-topic04-index-after.txt` → `0`; `rtk fc.exe /b ...` → `0`, `FC: no differences encountered`. Full `rtk uv run pytest -q` → `1` after `882.66s` (`483 passed, 1 skipped, 6 failed`); the failures are unrelated baseline checks listed under Limitations. |
| Evidence + SHA256 | Locked sources: Section03 `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`, EDAI2 `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`, rubric workbook `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`. Candidate manifest `evidence/03_data_generator_improvement/section03_candidate_manifest.json`: `8c0ff22ef528f4170506734f03c055aeec742e62bd9e94d7d0f703e47653bed7`; bundle `c220ab9dc815fb6ccff187b661a0fa483f8c16bcda368dd214a0f78633d6c92f`; bound config `configs/generator/base.yaml`: `5c5029fea77d93c3941d87d9a60f85cfe374f36899c3d3c1b028f3f5f3c3cd97`. Current diagnostic `tmp/section03-runtime/topic04-spark-gold-20260804/dbt-inventory-and-generator-parity.txt`: `2b97246ebb15d0a7879b7e5e01c2997f17b183c85e8b443664290a64f690deaf`; initial Compose log `make-up-batch-initial.log`: `70e825dd518559cdcef481d9f0b3e1de615257a2053dd74350451436fc97e40d`; proxy-retry log `make-up-batch-proxy-retry.log`: `b636b543ddf0a1bc62242edcebebe7def84d2727e9665b84696a799adb9236bf`; `minio-init-retry.log`: `5b2822bfeb58c1ac351db774811339728e9ef67a4e47da44182fcd1f5a3d7b83`; Docker state capture: `5f90d34046ce220265fe384e3c6da48af3ac7fd6e726c7de502b53058683e042`. The Docupedia SHA256SUMS attachment reports the DER/certificate fingerprint `BEFE...`; the authoritative downloaded PEM raw hash was `46d26ce24971172304c94bd5d5308866dc394391edef3af55d20282e8a2f1aec`, while the repository PEM raw hash was `f84fff2fa94b68f4cf255db1720e03874f7e52b43078b52c817ea450e8cab3ff`; normalized PEM bytes were identical and DER hashes matched. |
| Screenshot QA | `No screenshot created or required; machine evidence only. Successor topics own final UI captures.` |
| Cleanup / runtime release | The session-created `vina-bim-shop` containers, network, and volumes were released by `rtk make down-batch` → `0`; no Docker prune was run. The six pre-existing Docupedia/Playwright containers were left running. The predecessor DuckDB and dbt artifacts were restored and reverified at DuckDB `52f70910d274b0c188713c2b6e1cd76c12b63102225e09652ffa0479c902d6ea`, manifest `0cef60444ab4c5208e3381df737b34975a4e480759e3f227f566b4d88048ecc7`, run results `aadfb7ebb1e2c7f35ed4be5ad62d746c5ce104b5b710c4b22c73578700c622ab`, and dbt log `77c316ec0c7729fae12ead1c3f1cea3976f2d49cdd27a6d148ab364cd897c49d`. No Kubernetes/GCP resource was accessed or mutated. |
| Limitations | The strict `run_batch.py` command was not executed because the only local Compose runtime slice could not satisfy its `minio-init` dependency after one bounded retry. Consequently, no Spark/Iceberg table counts, Trino smoke, Great Expectations result, generator-vs-Spark report, or dbt-vs-Spark report exists for this continuation. The current dbt output exposes only 13 of 26 required Gold relations and disagrees with the locked generator on 9,592 training rows; Topic 04 does not authorize upstream dbt/generator edits, so parity remains fail-closed. The full suite also retained six unrelated baseline failures: `test_scripts_readme_documents_every_tracked_script`, `test_all_zone_model_inventory_and_metadata_match_schema_design_source`, `test_physical_gold_model_puml_documents_all_layers_and_purposes`, `test_duckdb_gold_tables_have_physical_constraints_for_dbeaver_erd`, `test_promotion_sentinel_makes_fact_order_item_promotion_key_non_null`, and `test_schema_design_puml_shows_storage_and_serving_contracts`. The CA image is locally verified but this does not establish Spark output parity, GKE behavior, final UI evidence, or E34 runtime/promotion credit. |
| Rubric disposition | Supporting evidence only for `Sheet3!E34`; Topic 07 remains the sole primary owner. Local unit/dbt/CA results do not earn strict runtime or promotion credit, and no GKE claim is made. |
| Stop conditions | Triggered by the Compose `minio-init` proxy/502 failure and the persistent upstream required-inventory/training mismatch. One bounded proxy-disabled retry was exhausted; no further tuning, speculative certificate import, Docker prune, unrelated-container stop, Kubernetes command, or GCP mutation was performed. |
| Successor handoff | Topic 05 remains blocked on this gate. Before promotion, repair or explicitly authorize the Compose proxy/no-proxy runtime configuration and the upstream dbt/generator contract scope; rebuild the full 26-table Gold inventory from candidate `c220ab9dc815fb6ccff187b661a0fa483f8c16bcda368dd214a0f78633d6c92f` and config SHA `5c5029fea77d93c3941d87d9a60f85cfe374f36899c3d3c1b028f3f5f3c3cd97`; rerun the exact medium-window batch command, real Spark/Iceberg/Trino checks, and all three keyed comparison families; replace this diagnostic failure evidence only with a zero-mismatch report. |
