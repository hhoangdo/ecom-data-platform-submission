# Section 03 Canonical Runtime Promotion Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete Task 10 by generating a medium/seed-42 candidate, importing verified Spark/Airflow/DataHub captures, and atomically promoting one immutable strict Section03 bundle.

**Architecture:** A pending generator candidate is identity-bound to analytic/runtime captures; the finalizer recursively verifies and atomically promotes one immutable strict bundle.

**Tech Stack:** Python 3.12, Pandas, dbt, Spark, Airflow, DataHub, SHA-256, pytest, `uv`, Make, `rtk`.

## Locked sources and acceptance procedure

- Read `C:\Users\oou1hc\.codex\RTK.md` before every operator session and prefix every shell command with `rtk`.
- Locked Section03 source: `tmp/edai2-plan/03_data_generator_improvement.md`, SHA256 `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`.
- Locked EDAI2 source: `tmp/edai2-plan/04.2_llm_design.md`, SHA256 `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`.
- Locked rubric source: `tmp/rubic-check/Coursework Tracking (Public).xlsx`, SHA256 `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- Preflight and final acceptance both run `rtk git status --short --branch`; record the output and reject a branch change during the serial session.
- Final acceptance also records SHA256s, evidence/screenshot QA, cleanup/runtime release, limitations, and successor handoff in the Completion Record.
- Keep one current branch and one serial session; any Kubernetes action sets `KUBECONFIG` and `--context` explicitly, never the corporate current context.
- Kind is local smoke only and never GKE/rubric evidence; do not run Docker prune or stop unrelated containers.

## Metadata

| Field | Decision |
|---|---|
| Phase | 7 — canonical Section03 completion |
| Source tasks | Section03 Task 10; reconciliation for Sheet3!E32:E34 |
| Primary rubric cells | Sheet3!E32, Sheet3!E33, Sheet3!E34 |
| Prerequisites | Topic 06 Completion Record, matching runtime captures, and same branch |
| Blocked successors | Topic 08 only |
| Runtime ownership | Single evidence operator; serial session/lock |
| Local/GCP class | Local generator plus separately authorized runtime imports; no GCP mutation in this file |

## Architecture and technology

The generator creates a pending candidate with immutable local artifacts. dbt/Spark/Airflow/DataHub evidence binds to its config, scale, config-derived windows, bundle, and hashes. The finalizer verifies all recursive inventories under a lock, writes a new immutable fourteen-artifact bundle, rewrites only references to that bundle, and atomically promotes `section03_manifest.json`; the candidate pointer is diagnostic and removed only when identity matches. If the derived immutable bundle ID already exists, the finalizer may reuse it only after byte/hash verification of the complete recursive inventory; the same ID with any content mismatch fails closed and is never overwritten.

## Global constraints

Plan 00 safety/hashes apply. The canonical run is `scale=medium`, `mode=full`, `seed=42`, with `12000` customers, `600` sellers, `6000` products, `45000` orders, and `80` promotions. Reuse an existing byte-identical verified bundle; never regenerate to inflate evidence. Drift deployment owns activation; an evidence plan must not silently activate it. Candidate/pending manifests earn zero. No Kind capture is GKE proof. Operator commands use `rtk`; Make recipes are `uv run`.

The deterministic image writer uses a same-directory temporary PNG, verifies the eight-byte PNG signature, runs decoder verification and a full pixel load, enforces exact 1600×900 dimensions, and only then atomically replaces `section03_config_and_training_join.png`. Its manifest/QA record includes UTC time, generator command and source path, current revision, visible config/training headings and columns, SHA-256, linked machine evidence, and explicit `proves`/`does_not_prove` fields. Reject corrupt, truncated, clipped, blank/near-uniform, stale, secret-bearing, or PII-bearing images and inspect the accepted image at original resolution.

## Current-state refresh — read-only planning phase

```text
rtk git branch --show-current
rtk git status --short --branch
rtk uv run python scripts/generate/verify_section03_manifest.py --manifest evidence/03_data_generator_improvement/section03_manifest.json --strict
rtk rg -n "runtime_evidence|bundle_id|consumer_contract|rubric_cells" evidence/03_data_generator_improvement
```

Expected: either one existing strict manifest verifies or its absence/failure is recorded. Do not delete/replace it during refresh.

## Scope and non-goals

In scope: generator candidate, independent verification, runtime-capture import, strict finalization, exact `Sheet3!E32:E34` reconciliation. Out of scope: rerunning unrelated builds, GCP provisioning, changing source contracts, manual evidence edits, and claims above verified facts.

## Exact file map

| Action | Path |
|---|---|
| Create | `scripts/generate/finalize_section03_evidence.py`, `tests/integration/test_section03_finalizer.py` |
| Regenerate | Finalizer-derived immutable directory below `evidence/03_data_generator_improvement/runs/` and `evidence/03_data_generator_improvement/section03_manifest.json` |
| Regenerate | `evidence/03_data_generator_improvement/runs/{derived-bundle-id}/section03_config_and_training_join.png` at exactly 1600×900 |
| Runtime input | `tmp/section03-runtime/spark`, `tmp/section03-runtime/airflow`, `tmp/section03-runtime/datahub` |
| Transient | `evidence/03_data_generator_improvement/section03_candidate_manifest.json`; absent after clean success unless safe cleanup cannot be proven |

`derived-bundle-id` means the lowercase SHA-256 calculated by the finalizer over the sorted complete fourteen-key artifact inventory, including the rewritten report and the three runtime top-manifest hashes. It is never operator-chosen.

## Interfaces, data flow, and failure modes

Config + seed → candidate manifest → pending verifier; config-faithful dbt/Spark and exact Airflow/DataHub captures must match candidate identity → finalizer → strict root → EDAI2 read-only consumer. Fail on any false check, configured-count/rate breach, missing warning/alert day, empty/nonunique labels/training, a Spark timestamp inconsistent with the parsed config, parity mismatch, stale/partial runtime inventory, capture hash mismatch, non-verified runtime status, path traversal/symlink input, or same-ID content mismatch. A pre-promotion failure preserves the prior strict root byte-for-byte. A post-promotion housekeeping error is warning-only and preserves every pointer or bundle whose safe removal is uncertain.

## Ordered test-first execution tasks

- [ ] Add synthetic candidate/Spark/Airflow/DataHub trees and first run `rtk uv run pytest tests/integration/test_section03_finalizer.py -q`; expected FAIL before the finalizer exists. Cover corrupt/missing/stale and recursively unlisted artifacts, config/run/scale/cutoff mismatches, traversal/symlink input, failure immediately before authoritative replace, candidate-pointer identity change, post-promotion cleanup failure, verified identical same-ID reuse, and same-ID content mismatch rejection.
- [ ] Implement the exact lock, recursive fourteen-artifact verification, staging, final-ID derivation, report rewrite, path rebinding, atomic replace, compare-and-delete candidate pointer, active-plus-previous retention, and `--clean` lifecycle. Run `rtk uv run pytest tests/integration/test_section03_finalizer.py -q`; expected PASS, with every pre-promotion fault leaving the active manifest and transitive hashes unchanged and post-promotion housekeeping faults returning success plus a warning.
- [ ] Run `rtk uv run python scripts/generate/verify_section03_manifest.py --manifest evidence/03_data_generator_improvement/section03_candidate_manifest.json --allow-runtime-pending` and `rtk uv run python -c "import hashlib,json; from pathlib import Path; p=Path('evidence/03_data_generator_improvement/section03_candidate_manifest.json'); m=json.loads(p.read_text(encoding='utf-8')); assert m['scale']=='medium'; assert m['random_seed']==42; assert m['source_config_path']=='configs/generator/base.yaml'; assert m['source_config_sha256']==hashlib.sha256(Path('configs/generator/base.yaml').read_bytes()).hexdigest(); assert m['runtime_evidence']=={'status':'pending','spark':None,'airflow':None,'datahub':None}; print(m['bundle_id'])"`; expected both commands exit 0 for a valid medium/seed-42/config-identical pending candidate, in which case reuse that byte-identical candidate and do not regenerate it. Missing/invalid/mismatched candidate exits nonzero and authorizes only the next lifecycle step.
- [ ] Only when the preceding candidate reuse gate exits nonzero, run `rtk uv run python scripts/generate/run_generator.py --config configs/generator/base.yaml --scale medium --mode full --clean --seed 42`; expected exit 0, configured counts `12000/600/6000/45000/80`, rate in inclusive `[1.35,1.65]`, all Section 03 checks true, one replacement pending immutable candidate, and no change to any prior strict root.
- [ ] Run `rtk uv run python scripts/generate/verify_section03_manifest.py --manifest evidence/03_data_generator_improvement/section03_candidate_manifest.json --allow-runtime-pending`; expected exact `section03 manifest: PASS (runtime pending)` and zero rubric credit at this stage.
- [ ] Run `rtk uv run python -c "import json; from pathlib import Path; from PIL import Image; m=json.loads(Path('evidence/03_data_generator_improvement/section03_candidate_manifest.json').read_text(encoding='utf-8')); p=Path(m['artifacts']['evidence_image']['path']); b=p.read_bytes(); assert b[:8]==bytes.fromhex('89504e470d0a1a0a'); im=Image.open(p); im.verify(); im=Image.open(p); im.load(); assert im.size==(1600,900); print(p)"`, then inspect the printed path at original resolution with `view_image`; expected exit 0, a fully decoded 1600×900 PNG with readable config/training headings and no clipping, blank region, stale value, secret, or PII.
- [ ] Run `rtk uv run python scripts/analytics/run_section03_dbt.py --config configs/generator/base.yaml --scale medium --project-dir infra/analytics/dbt --profiles-dir infra/analytics/dbt`; expected exit 0 with all seven DP3 models and generic/singular contracts passing.
- [ ] With only the existing batch dependencies required by this slice running, run `rtk uv run python scripts/spark/run_batch.py --mode backfill --generator-config configs/generator/base.yaml --generator-scale medium --section03-manifest evidence/03_data_generator_improvement/section03_candidate_manifest.json --evidence-root tmp/section03-runtime/spark`; expected exit 0. Start/end/cutoff values are derived from config/scale rather than hard-coded; the seven tables exist and generator-vs-dbt, generator-vs-Spark, and dbt-vs-Spark keyed mismatch counts are zero.
- [ ] Run `rtk uv run python scripts/ctl.py compose up governance` and `rtk uv run python scripts/ctl.py compose up orchestration`; expected the existing DataHub and Airflow services healthy with volumes retained. Do not use `down -v`, run a broad Compose stack, or stop unrelated containers.
- [ ] Run `rtk uv run python scripts/orchestration/run_section03_dp3.py --airflow-url http://localhost:8082 --dag-id mini_coursework_pipeline --run-id section03-medium-seed42 --config configs/generator/base.yaml --scale medium --section03-manifest evidence/03_data_generator_improvement/section03_candidate_manifest.json --output tmp/section03-runtime/airflow --strict`; expected all six task instances `success`, seven hash-bound outputs, exact config/scale/cutoff binding, no Variable fallback, and redacted credentials.
- [ ] Run `rtk uv run python scripts/datahub/capture_evidence.py --section03 --gms-url http://localhost:8087 --frontend-url http://localhost:9002 --airflow-capture tmp/section03-runtime/airflow --section03-manifest evidence/03_data_generator_improvement/section03_candidate_manifest.json --output tmp/section03-runtime/datahub --strict`; expected indexed search resolves the exact DataFlow/DataJob, seven outputs, schemas, direct parents, and five assertions; direct GMS-only resolution is insufficient.
- [ ] Run `rtk uv run python scripts/generate/finalize_section03_evidence.py --candidate-manifest evidence/03_data_generator_improvement/section03_candidate_manifest.json --active-manifest evidence/03_data_generator_improvement/section03_manifest.json --spark-root tmp/section03-runtime/spark --airflow-root tmp/section03-runtime/airflow --datahub-root tmp/section03-runtime/datahub --clean`; expected exit 0 only after strict recursive verification and atomic promotion. A missing/failed/stale capture retains the candidate and prior active root.
- [ ] Run `rtk uv run python scripts/generate/verify_section03_manifest.py --manifest evidence/03_data_generator_improvement/section03_manifest.json --strict`; expected exact `section03 manifest: PASS`, `runtime_evidence.status="verified"`, no pending marker after clean success, and `Sheet3!E32`/`Sheet3!E33`/`Sheet3!E34` point values `1/1/2`.
- [ ] Run `rtk uv run pytest tests/integration/test_section03_finalizer.py -q`; expected PASS for verified identical same-ID bundle reuse after complete recursive verification and for same-ID content mismatch rejection with no overwrite, duplicate bundle, or score change. Do not invoke the live finalizer again after `--clean` has safely removed the consumed candidate pointer.
- [ ] Run `rtk uv run pytest tests/unit/test_generator_config.py tests/unit/test_generator_module_split.py tests/unit/test_section03_drift.py tests/unit/test_section03_manifest_verifier.py tests/unit/test_section03_dbt_contract.py tests/integration/test_section03_finalizer.py tests/integration/test_section03_generator.py tests/integration/test_section01_generator.py tests/integration/test_generator_cli.py tests/unit/test_spark_batch_runtime.py tests/unit/test_orchestration_runtime.py tests/unit/test_airflow_coursework_metadata.py tests/unit/test_orchestration_dag_adapters.py tests/unit/test_datahub_coursework_lineage.py tests/unit/test_datahub_capture_evidence.py tests/unit/test_datahub_adr_boundaries.py tests/unit/test_section03_documentation.py tests/unit/test_section02_schema_design.py -q`; expected PASS with zero failures, skips, or xfails in the listed files.
- [ ] Run `rtk uv run pytest -q`; expected PASS. If an unrelated pre-existing failure remains, preserve it, hash its log, and record the limitation without changing adjacent code.
- [ ] Run `rtk git diff --check` and `rtk git status --short --branch`; expected `rtk git diff --check` prints nothing, the original branch remains active, only the Section 03 exact file map plus deterministic evidence changed, and nothing is staged.

## Evidence and screenshot ownership

The evidence operator owns the strict manifest, all direct/transitive SHA-256 values, measured rate, `section03_config_and_training_join.png`, its QA metadata sidecar/manifest fields, and the three runtime imports. The accepted image is exactly 1600×900, fully decoded, viewed at original resolution, contextual, unclipped, nonblank, current, and free of secrets/PII. Screenshot metadata records `proves`: parsed drift configuration, visible `id,label`/training rows, and linkage to the matching machine-evidence hashes; it records `does_not_prove`: Feast runtime, GKE, model training, or any cell outside `Sheet3!E32:E34`. No absent observation is synthesized.

## Cleanup

After successful promotion, delete only the consumed candidate pointer if its identity still matches; retain active and previous immutable bundles. Release session lock/runtime ownership. Never run broad Docker cleanup.

## Rubric table

| Cell | Strict requirement | Scoring |
|---|---|---|
| Sheet3!E32 | Verified drift/config/training, PNG, rate, runtime bindings | 1 only if strict root verifies |
| Sheet3!E33 | Verified typed config snapshot and config-derived windows | 1 only if strict root verifies |
| Sheet3!E34 | Verified unique exact `id,label` and named training join | 2 only if strict root verifies |

## Definition of Done

One strict immutable bundle validates recursively, runtime status is verified, `Sheet3!E32:E34` mapping is exact and subtotal is four, active/previous retention is safe, and the EDAI2 consumer can read it without modification.

## Completion Record

| Field | Record |
|---|---|
| Status | Not started |
| Affected files | Exact file map above |
| Commands / exit codes | Record all generator/verifier/finalizer/runtime commands and exits, ending with `rtk git status --short --branch` |
| Evidence + SHA256 | Record strict manifest, bundle, capture paths, and SHA256s |
| Screenshot QA | Record temp-write/signature/decode/load checks, 1600×900 dimensions, original-resolution inspection, UTC time, source, revision, visible headings/columns, redaction, linked machine evidence, SHA-256, `proves`, and `does_not_prove` |
| Cleanup / runtime release | Record pointer retention/deletion, bundle retention, and lock release |
| Limitations | Evidence states measured outcomes only; no Feast/GKE claim |
| Successor handoff | Strict manifest path/SHA256 and consumer contract to plan 08 |
