# L01 — Baseline, cleanup, and tool rehearsal

[Roadmap and status board](../README.md) · [Rubric map](../rubric-map.md) · [Evidence guide](../evidence-guide.md)

## Purpose and examples

Make it possible to answer “What works now, what should I follow, and what is the next action?” without comparing several historical runs.

Examples: “Why does the LLM deliverable say out of scope while the repository has an LLM service?” and “Can an agent capture a real Airflow or DBeaver result rather than draw a status card?”

## Expected output

A reviewed inventory of claims/artifacts and exact cleanup changes; a reusable small operating workflow; capture and editable-diagram rehearsal results. Preserve useful implementation knowledge before removing superseded material.

## Inspect before interviewing

All repository paths below are relative to `C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission`. Inspect the actual implementation, not only old plans.

- `README.md`, `deliverables/04.2_llm_design.md`, `tmp/edai2-plan/04.2_llm_design.md`, `tmp/edai2-plan/execution-v1/`.
- `evidence/04_2_llm_design/README.md`, `completion/`, `screenshots/ui_manifest.json`, and the evidence bundle checks under `scripts/qa/`.
- `scripts/qa/render_vault_status.py`, `scripts/gke/configure_vault.py`, `scripts/gke/check_budget.py`, relevant personal-study/production branches.
- Git tracked/untracked/ignored inventory, current tool configuration and actual browser/desktop access. Inspect credential configuration without printing secret values.

**Rubric ownership:** E59 (2 points). L07 owns M02/E60 and final narrative; G04 rechecks cleanup. Map every proposed deletion to a replacement or a clear reason.

**Reference reading:** under `C:/Users/hhoangdo/Documents/Personal Projects/GitHub Repo/RecSys-MLops`: `docs/submission/rubric-final-coursework-(final-llm)/repository_design.md`, `security.md`, and `benchmark_proof/`.. Follow its evidence discipline and stated limitations; do not copy unrelated infrastructure.

## Dependencies and boundary

No prior topic. Execute cleanup and rehearsals only after this topic's detailed plan is agreed and execution requested. Do not try to fix every service here; assign discovered gaps to L02–L06. No GCP account is required.

## Decisions for the grill-with-docs interview

- Which files are superseded, which remain valid evidence/source, and which useful decisions must be extracted first?
- What small workflow removes duplicate modes and old approval rituals without weakening actual correctness or secret handling?
- Which browser/desktop capture paths work on this machine, and does a small gcloud/Excalidraw MCP addition solve a demonstrated problem?
- Which existing design pattern is genuinely useful and explainable for E59? Do not add decorative abstractions just to name a pattern.

These are interview questions, not preselected implementation requirements. Present the actual alternatives and score consequences, recommend a feasible answer, and wait for the owner's decisions.

## Acceptance criteria

- [ ] Inventory reconciles documentation claims with real code and historical results; new topic ownership is explicit.
- [ ] Exact tracked deletion/update list is reviewable; untracked files have a recovery decision. No blanket recursive cleanup or history rewrite.
- [ ] Execution removes only agreed superseded artifacts and repairs affected navigation, while preserving valid inputs/results.
- [ ] Single official baseline and status workflow are explained; any remaining mode removal is explicitly owned by L06, not silently considered complete.
- [ ] Native browser plus terminal/desktop capture is rehearsed or the precise human fallback is recorded. Inspect saved images at readable size.
- [ ] Edit/export round trip on a disposable Excalidraw copy is tested; preserve the original mini diagram. If no addition is useful, keep existing tools and record why.
- [ ] E59 explanation points to a real pattern in actual code; final whole-repo cleanup remains G04's check.

## Simplifications and limitations to explain

Keep the tool set small. Defer Spacelift. No cloud provisioning or paid account activation for a tooling rehearsal. A configured MCP does not prove authenticated access. Deleting stale artifacts improves clarity; it does not make missing functionality complete. Do not discard benchmark baselines needed for legitimate comparisons.

## Copyable planning prompt

```text
Plan L01 — Baseline, cleanup, and tool rehearsal only. This is an interview and planning session; do not implement code, delete artifacts, install tools, provision resources, or run a mutating workload. Writing agreed planning/glossary documents is permitted when the host mode allows it. Ask before expanding the topic.

Repository:
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission

Read:
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/README.md
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/rubric-map.md
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/evidence-guide.md
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/local/L01-baseline-cleanup-tools.md

Invoke $grill-with-docs using:
C:/Users/hhoangdo/.agents/skills/grill-with-docs/SKILL.md
It invokes grilling and domain-modeling. If no Skill tool exists, read those named SKILL.md files and follow them.

Inspect the brief's code/evidence and relevant reference files first:
C:/Users/hhoangdo/Documents/Personal Projects/GitHub Repo/RecSys-MLops
Do not ask me facts you can discover. Treat execution-v1 and completion records as historical context, not instructions to restore extra ceremonies.

Start by explaining the topic in plain language: why it exists, what I can see when it works, one concrete example, inputs/outputs, relation to other topics, and exact rubric rows/points. Separate implemented behavior from mocks, historical proof, and missing integration.

Interview the ready decisions in manageable rounds. Recommend answers with tradeoffs. Explain unfamiliar terms using our data-operations-assistant story. Challenge needless complexity, invented thresholds, second-email/encryption ceremonies, and study/production branches. Do not silently choose a major alternative or promise instructor acceptance of a substitution.

Confirm our shared understanding before finalizing the detailed plan. Record resolved project terms in root CONTEXT.md when permitted; use ADRs only for consequential tradeoffs. Keep one current plan by replacing the final section of THIS brief. Include affected files/interfaces, exact verification commands and expected results, meaningful failure cases, evidence recipes with manual fallback, limitations and deliberately unclaimed marks. Distinguish this topic's local acceptance from cloud proof owned elsewhere.

Execution starts only after I explicitly request it. If the host is in Plan mode, present the detailed plan without writing files. Keep topic status only in execution-v2/README.md; update it truthfully when appropriate. End with decisions made, remaining decisions, and the exact next action.
```

## Agreed design and detailed execution plan

Not yet agreed. Replace this section in place after the interview and shared-understanding confirmation. Do not prefill an implementation or create a competing plan elsewhere.

