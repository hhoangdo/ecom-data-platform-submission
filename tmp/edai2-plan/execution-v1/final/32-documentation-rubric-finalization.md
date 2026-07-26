# Topic 32: Documentation and Rubric Finalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finalize mandatory Row 2 documentation, design evidence, five key classes, and a fail-closed one-owner `Sheet3!E3:E62` rubric manifest whose maximum is 99 and whose actual score may be lower when evidence is incomplete.

**Architecture:** Local tests drive README/docs/PlantUML and manifest generation. The builder consumes immutable source hashes, Topics 00-31 Completion Records, Section 03's verified prerequisite manifest, machine evidence, and strict screenshot QA. It assigns exactly one primary owner to each rubric cell, retains `Sheet3!E49` as one source point but always zero earned/Out of Scope, and never converts planned or failed evidence into a claim.

**Tech Stack:** Markdown, PlantUML/SVG, Python/`uv`, pytest, SHA-256, fail-closed JSON manifest validation, screenshot capture validator.

## Metadata

| Field | Decision |
|---|---|
| Phase | Local documentation/finalization; execution topic 32 |
| Authoritative source tasks | `04.2_llm_design.md` Task 13 and Evidence Contract; rubric audit |
| Primary rubric cells | Mandatory unscored `Sheet3!Row2`; `Sheet3!E49` status owner; `Sheet3!E59`; `Sheet3!E60` |
| Prerequisites | Topics 00-31 Completion Records; Section 03 manifest; Topic 31 run/teardown/screenshot QA |
| Blocked successors | None; this is final handoff |
| Runtime owner | None; local/read-only evidence consumption and repository documentation writes |
| Execution class | `Local-write/no-GCP-runtime` |
| Branch rule | Same branch; no worktree/branch switch/stage/commit |

## Global Constraints

- Read `C:\Users\oou1hc\.codex\RTK.md`; prefix every shell command with `rtk`.
- Fixed source hashes: Section 03 `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`; EDAI2 `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`; `tmp/rubic-check/Coursework Tracking (Public).xlsx` `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- Do not create/switch branches/worktrees, stage, or commit.
- Topic 32 makes no GCP mutation. Missing project/billing/IAM/trial/spend/recovery sink/external inputs or failed runtime topics are recorded as limitations/unsatisfied cells; local truthful partial finalization still proceeds.
- `EDAI2_TFVARS_PATH=tmp/edai2-gcp/coursework.auto.tfvars` remains untracked and must not be read into docs/manifest.
- Execute Topic 32 only after Topic 31 has released its lease, in the same serial session order and current checkout/branch; do not create a branch/worktree or stage, commit, push, or open a PR.
- Row 2 is mandatory but unscored. README must contain business domain, TOC, repository structure, docstring/file-description policy, whole-course deployment diagram, and links to detailed docs.
- Diagram nodes are deployable units only; arrows follow data/control direction, are numbered/labeled, distinguish user/developer flows by color, and use dashed lines only for clearly secondary flows.
- Detailed documents and contextual screenshots live under `docs/edai2`/evidence and are linked from README; README summarizes rather than becoming the detail dump.
- `Sheet3!E3:E62` appears exactly once each in numeric order with one primary owner. Duplicate/missing ownership fails.
- `Sheet3!E32:E34` may only be `Prerequisite` owned by Section 03 and require strict verified hashes. No other cell may use prerequisite status.
- `Sheet3!E49.points=1`, `earned_points=0`, status `Out of Scope`, owner Topic 32; no VM/Ansible may be introduced.
- Direct EDAI2 compatible subtotal is at most 95; verified Section 03 contributes at most 4; combined maximum 99. A lower truthful score is valid; score inflation is not.
- `Satisfied` requires implementation/config, executed command/exit 0, measured result, contextual screenshot/report, SHA-256, machine link, and compatible screenshot QA.
- Planned, missing, empty, stale, unhashed, outside-repository, tampered, incompatible, secret/PII-bearing, or failed evidence is `Unsatisfied`.
- Topic 32 owns `design_patterns.png` and `whole_course_diagram.png`; UI dimensions `1600x1000`, full screenshot contract and original-resolution inspection apply.
- Each owned capture writes a same-directory temporary PNG, verifies the eight-byte PNG signature, performs decoder verification and a full pixel load, checks exact `1600x1000` dimensions and stable contextual selectors, then atomically replaces the final path. Record UTC time, URL/source path, current revision, visible selectors, SHA-256, linked machine evidence, and what the image proves/does not prove. Reject clipped, blank/near-uniform, loading, login-only, generic-home, error, stale, secret-bearing, PII-bearing, corrupt, truncated, or over-cropped images, and inspect each accepted file at original resolution.
- One bounded repair per local render/capture after diagnosed cause; repeated failure remains truthful partial.

## Read-Only Planning Refresh

1. `rtk git status --short --branch`
   - Expected: same branch and request-scoped changes.
2. `rtk python -c "import hashlib; p=['tmp/edai2-plan/03_data_generator_improvement.md','tmp/edai2-plan/04.2_llm_design.md','tmp/rubic-check/Coursework Tracking (Public).xlsx']; print([hashlib.sha256(open(x,'rb').read()).hexdigest() for x in p])"`
   - Expected: fixed hashes.
3. `rtk rg -n "Status|Definition of Done|Screenshot QA|Cleanup / runtime release|Limitations|Handoff" tmp/edai2-plan/execution-v1`
   - Expected: every Topic 00-31 has a Completion Record; missing/incomplete entries are explicit limitations.
4. `rtk uv run python scripts/qa/capture_edai2_evidence.py --verify-teardown evidence/04_2_llm_design/gke/teardown.json --strict`
   - Expected: Topic 31 reports zero pools/no ingress/forwarding/lease. If absent, final docs must not claim teardown.
5. `rtk uv run pytest tests/unit/test_edai2_rubric_manifest.py -q`
   - Expected before final implementation: failing tests precisely identify missing final manifest/docs rather than silently passing an incomplete stub.

## Scope

- Test and write Row 2 README/domain/TOC/repository/diagram navigation.
- Render whole-course, GKE drill-down, and agent-sequence diagrams.
- Write detailed architecture, low-level design, runbook, benchmark, evaluation, CI/CD, observability, security, and rubric evidence docs.
- Prove clean boundaries/design patterns and document five exact key classes.
- Capture two owned documentation screenshots.
- Build/verify the one-owner fail-closed rubric manifest and truthful score.
- Run focused/full regression, link/docstring audits, screenshot all-image verification, and final branch status.

## Non-Goals

- No GCP resume, screenshot recreation owned by Topics 22-31, runtime remediation, Terraform destroy, new feature, or score-targeted claim.
- No copied secret, tfvars, raw PII, plan prose presented as implemented fact, or unverified “100/100” statement.

## Exact File Map

| Action | Exact paths |
|---|---|
| Modify | `README.md`, `architecture/masterplan.md`, `architecture/diagrams/README.md` |
| Modify | `deliverables/README.md`, `scripts/README.md`, `infra/README.md`, `src/vina_bim_shop/README.md`, `Makefile` |
| Modify | `deliverables/04.2_llm_design.md` |
| Create | `architecture/diagrams/coursework_end_to_end_deployment.puml` |
| Create | `architecture/diagrams/edai2_gke_deployment.puml` |
| Create | `architecture/diagrams/edai2_agent_sequence.puml` |
| Create | `docs/edai2/architecture.md`, `docs/edai2/low_level_design.md`, `docs/edai2/gke_runbook.md` |
| Create | `docs/edai2/inference_benchmark.md`, `docs/edai2/evaluation.md`, `docs/edai2/cicd.md` |
| Create | `docs/edai2/observability.md`, `docs/edai2/security.md`, `docs/edai2/rubric_evidence.md` |
| Read/modify | `tests/unit/test_edai2_repository_contract.py`, `tests/unit/test_edai2_documentation.py`, `tests/unit/test_edai2_diagrams.py` |
| Read/modify | `tests/unit/test_edai2_rubric_manifest.py`, `tests/unit/test_edai2_security_static.py` |
| Execute | `scripts/qa/audit_edai2_documentation.py`, `scripts/qa/build_edai2_rubric_manifest.py`, `scripts/qa/capture_edai2_evidence.py` |
| Generate | `evidence/04_2_llm_design/documentation_coverage.json` |
| Generate | `evidence/04_2_llm_design/rubric_manifest.json` |
| Screenshot owner | `evidence/04_2_llm_design/screenshots/design_patterns.png` |
| Screenshot owner | `evidence/04_2_llm_design/screenshots/whole_course_diagram.png` |
| Update through capture CLI | `evidence/04_2_llm_design/screenshots/ui_manifest.json` |

## One-Owner Rubric Matrix

| Primary owner | Exact cells |
|---|---|
| Topic 22 | `Sheet3!E48` |
| Topic 23 | none; supporting only |
| Topic 24 | `Sheet3!E3`, `Sheet3!E4`, `Sheet3!E6` |
| Topic 25 | `Sheet3!E10:E12`, `Sheet3!E16:E18` |
| Topic 26 | `Sheet3!E7`, `Sheet3!E13:E15`, `Sheet3!E19:E21`, `Sheet3!E24` |
| Topic 27 | `Sheet3!E35:E43`, `Sheet3!E45:E47`, `Sheet3!E50:E55` |
| Section 03 | `Sheet3!E32:E34` as verified prerequisites only |
| Topic 28 | `Sheet3!E5`, `Sheet3!E8`, `Sheet3!E9`, `Sheet3!E26` |
| Topic 29 | `Sheet3!E22`, `Sheet3!E23`, `Sheet3!E25`, `Sheet3!E27:E31`, `Sheet3!E44`, `Sheet3!E56`, `Sheet3!E57`, `Sheet3!E61`, `Sheet3!E62` |
| Topic 30 | `Sheet3!E58` |
| Topic 31 | none; cross-cutting QA only |
| Topic 32 | mandatory `Sheet3!Row2`, `Sheet3!E49` status, `Sheet3!E59`, `Sheet3!E60` |

This matrix covers every cell from `Sheet3!E3:E62` exactly once.

## Interfaces, Data Flow, and Failure Modes

Source plans/workbook hashes + Completion Records + Section 03 manifest + machine evidence + screenshot manifests/QA -> strict owner/cell reconciliation -> status/points/earned/evidence hashes -> subtotal/ceiling -> reviewer docs and rubric manifest.

Code/package structure -> five class signatures + ports/adapters/Strategy examples -> tests/docs -> `design_patterns.png`.

Deployment inventory/data flows -> PlantUML -> rendered SVG -> README embed -> `whole_course_diagram.png`.

Failure modes: duplicate/missing cell owner, source point mismatch, false Section 03 prerequisite, `Sheet3!E49` earned, score >99, unsupported doc claim, broken link, non-deployable diagram node, screenshot failure, hash tampering, missing docstring. Each fails verification; local finalization records lower truthful result.

## Ordered Test-First Execution Tasks

### Task 1: Write/run final documentation and rubric tests

- [ ] Ensure tests require README TOC/repo map/domain, local links, whole-course embedded SVG, deployable-only diagram nodes, numbered/labeled/directional colored arrows, limited dashed flows, five exact classes, public docstrings, screenshot context/limitations, and no claim without evidence.
- [ ] Ensure rubric tests require fixed source hash, exact owner matrix, `Sheet3!E3:E62` numeric order, missing/false/true Section 03 prerequisite behavior, unchanged `Sheet3!E49.points=1`/earned zero/OOS, duplicate rejection, tamper rejection, and <=99.
- [ ] Run `rtk uv run pytest tests/unit/test_edai2_documentation.py tests/unit/test_edai2_diagrams.py tests/unit/test_edai2_rubric_manifest.py -q`.
  - Expected: fail only for genuinely absent/incomplete final files; no incomplete stub can pass.

### Task 2: Render and document architecture

- [ ] Run `rtk uv run python scripts/qa/audit_edai2_documentation.py --render-diagrams architecture/diagrams/coursework_end_to_end_deployment.puml,architecture/diagrams/edai2_gke_deployment.puml,architecture/diagrams/edai2_agent_sequence.puml --strict`.
  - Expected: SVG renders, deployable-unit/arrow rules pass, no secret/PII.
- [ ] Write README/domain/TOC/repository navigation and the nine detailed `docs/edai2` files using only observed evidence and explicit limitations.
- [ ] Run `rtk uv run python scripts/qa/audit_edai2_documentation.py --output evidence/04_2_llm_design/documentation_coverage.json`.
  - Expected: 100% declared EDAI2 module/public-symbol docstrings, all local links/renders resolve.

### Task 3: Prove design patterns and five classes

- [ ] Run `rtk uv run pytest tests/unit/test_edai2_repository_contract.py tests/unit/test_edai2_documentation.py -q`.
  - Expected: clean boundaries, ports/adapters and Strategy proof, five exact typed class APIs, and docs pass.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --capture design-patterns --viewport 1600x1000 --output evidence/04_2_llm_design/screenshots/design_patterns.png --manifest evidence/04_2_llm_design/screenshots/ui_manifest.json --machine-evidence evidence/04_2_llm_design/documentation_coverage.json --strict`.
  - Expected: contextual rendered design/class view, not a raw source-only terminal.

### Task 4: Capture mandatory whole-course diagram

- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --capture whole-course-diagram --viewport 1600x1000 --output evidence/04_2_llm_design/screenshots/whole_course_diagram.png --manifest evidence/04_2_llm_design/screenshots/ui_manifest.json --machine-evidence architecture/diagrams/coursework_end_to_end_deployment.svg --strict`.
  - Expected: complete non-clipped diagram, title/legend/numbered flows/deployable units visible.
- [ ] Inspect both owned screenshots at original resolution.
  - Expected: no blank/clipped/loading/error/stale/secret/PII and all selectors/text legible.
- [ ] Run `rtk uv run python scripts/qa/capture_edai2_evidence.py --verify-screenshots-only --expected-edai2-count 32 --expected-extra gcp_billing_spend.png --ui-dimensions 1600x1000 --section03-dimensions 1600x900 --manifest evidence/04_2_llm_design/screenshots/ui_manifest.json --section03-manifest evidence/03_data_generator_improvement/section03_manifest.json --strict`.
  - Expected: all 32 named EDAI2 images plus billing and all Section 03 images pass; no pending producer remains.

### Task 5: Build and verify fail-closed rubric manifest

- [ ] Run `rtk uv run python scripts/qa/build_edai2_rubric_manifest.py --source-workbook "tmp/rubic-check/Coursework Tracking (Public).xlsx" --source-workbook-sha256 71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657 --section03-manifest evidence/03_data_generator_improvement/section03_manifest.json --run-manifest evidence/04_2_llm_design/run_manifest.json --output evidence/04_2_llm_design/rubric_manifest.json`.
  - Expected: Row 2 and every `Sheet3!E3:E62` cell exactly once, one owner, exact source points, honest statuses/earned points/hashes.
- [ ] Run `rtk uv run python scripts/qa/build_edai2_rubric_manifest.py --verify --manifest evidence/04_2_llm_design/rubric_manifest.json`.
  - Expected: verified `Sheet3!E32:E34` hashes or zero prerequisite credit; `Sheet3!E49` OOS/zero; score <=99; lower truthful score allowed; no missing proof synthesized.

### Task 6: Final regression and acceptance

- [ ] Run `rtk uv run pytest tests/unit/llm tests/contract/llm tests/property/llm tests/integration/llm tests/unit/test_edai2_repository_contract.py tests/unit/test_edai2_documentation.py tests/unit/test_edai2_diagrams.py tests/unit/test_edai2_rubric_manifest.py tests/unit/test_edai2_security_static.py -q`.
  - Expected: focused suite passes or exact truthful limitations recorded.
- [ ] Run `rtk uv run pytest -q`.
  - Expected: full regression passes.
- [ ] Run `rtk git diff --check`.
  - Expected: no whitespace errors.
- [ ] Run `rtk git status --short --branch`.
  - Expected: same branch; only scoped implementation/docs/generated evidence; no tfvars, secret, state, branch, stage, or commit action.

## Evidence and Screenshot Ownership

Topic 32 owns only `design_patterns.png` and `whole_course_diagram.png`, documentation coverage, and final rubric manifest. All other primary screenshot producers remain Topics 22 and 26-30. Topic 31 owns cross-cutting QA/teardown, not screenshots.

## Cleanup and Runtime Release

- No GCP runtime is acquired.
- Remove only failed temporary render/PNG files after durable diagnostics; accepted files are atomically installed.
- Confirm Topic 31 teardown remains valid through machine evidence; do not resume merely for docs.
- Ensure `tmp/edai2-gcp/coursework.auto.tfvars`, state, credentials, secrets, recovery material, and PII are absent from tracked/delivered files.

## Rubric Traceability

| Cell | Points | Topic 32 gate |
|---|---:|---|
| `Sheet3!Row2` | mandatory/unscored | README/domain/TOC/repo map/whole-course diagram/docs |
| `Sheet3!E49` | 1 source / 0 earned | always Out of Scope, no VM/Ansible |
| `Sheet3!E59` | 2 | clean repository/design-pattern proof |
| `Sheet3!E60` | 1 | five exact key classes and typed methods |
| `Sheet3!E3:E62` | max 99 compatible | one-owner fail-closed reconciliation; lower truthful result permitted |

## Definition of Done

- [ ] Fixed hashes, all Completion Records, screenshot QA, and teardown inputs are reconciled.
- [ ] Mandatory Row 2 documentation/diagram/navigation passes tests.
- [ ] Design-pattern and five-class documentation passes and two owned screenshots pass original QA.
- [ ] All 32 EDAI2 screenshots plus billing and Section 03 images pass strict final verification or affected cells are unsatisfied.
- [ ] Manifest maps every `Sheet3!E3:E62` cell once, Section 03 prerequisites strictly, `Sheet3!E49` zero/OOS, score <=99 and truthful.
- [ ] Documentation audit, focused tests, full tests, diff check, and final `rtk git status --short --branch` are recorded.
- [ ] No GCP runtime, secret, tfvars, state, recovery material, unsupported claim, staging, or commit is introduced.

## Completion Record

- **Status:** Not started; no final score/documentation claim.
- **Branch / revision:** Record exact `rtk git status --short --branch`; none recorded.
- **Affected files:** None at plan-authoring time.
- **Command / exit-code log:** No execution commands recorded.
- **Evidence / SHA-256 log:** No documentation/final manifest evidence recorded.
- **Screenshot QA:** Two owned images not captured; all-image strict check not run.
- **Cleanup / runtime release:** No runtime acquired; Topic 31 teardown not yet revalidated.
- **Limitations:** Final score may be below 99 whenever any prerequisite, command, measurement, screenshot, hash, or cleanup gate is incomplete.
- **Handoff:** Deliver final reviewer navigation, exact truthful score/status summary, limitations, evidence hashes, and confirmation that no work remains except explicitly unsatisfied external/runtime items.
