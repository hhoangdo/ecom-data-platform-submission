# G04 — Final submission and teardown

[Roadmap and status board](../README.md) · [Rubric map](../rubric-map.md) · [Evidence guide](../evidence-guide.md)

## Purpose and examples

Leave one clear submission that an instructor can navigate and reproduce, then stop the cloud resources after proof has been preserved.

Examples: “Which evidence supports this claimed mark?” and “Does the README describe the release in these screenshots, including the limitations we chose?”

## Expected output

A curated instructor-facing docs/evidence set for one accepted release, reconciled row-level claims and architecture, removed superseded artifacts, and verified cloud teardown with its real historical status clearly stated.

## Inspect before interviewing

All repository paths below are relative to `C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission`. Inspect the actual implementation, not only old plans.

- The rubric map's evidence links, single roadmap board, L07 documentation/diagrams and G01–G03 original results.
- Root README, `docs/`, `deliverables/`, `evidence/`, `artifacts/`, relevant old planning/debug outputs and Git tracked/untracked inventory.
- Current release/source/data/config identities and intentional baseline/A/B differences. Inspect remaining old sealing requirements before removing or updating their consumers.
- G01's exact resource inventory, Terraform state, teardown commands and shutdown schedule.

**Rubric ownership:** Final consistency check for all M02–M46 and E03–E62, plus unscored LLM A2 guidance. Does not independently earn new runtime marks; reconciles the claims their owning topics proved.

**Reference reading:** under `C:/Users/hhoangdo/Documents/Personal Projects/GitHub Repo/RecSys-MLops`: Reference root README, `docs/submission/rubric-final-coursework-(final-llm)/`, `benchmark_proof/` and its explicit measurement/limitation disclosures.. Follow its evidence discipline and stated limitations; do not copy unrelated infrastructure.

## Dependencies and boundary

Requires G03 or an explicit decision to finish with identified unclaimed/pending rows. Evidence preservation and local validation precede teardown. Submission preparation does not authorize publishing, messaging the instructor or rewriting Git history.

## Decisions for the grill-with-docs interview

- Which exact release and evidence paths are final, which comparison runs intentionally remain, and what historical material is superseded?
- Which rows are truly demonstrated, pending, or deliberately unclaimed after inspecting the actual results? What is each sheet's evidence-supported potential score, without promising the instructor's award?
- Are simplified choices and future improvements understandable and consistent across diagrams, README, class descriptions and detailed docs?
- What exact resource deletion/retention actions satisfy the agreed shutdown and preserve irreplaceable results? What post-teardown facts must the README state?

These are interview questions, not preselected implementation requirements. Present the actual alternatives and score consequences, recommend a feasible answer, and wait for the owner's decisions.

## Acceptance criteria

- [ ] Every row has inspected proof or a precise pending/unclaimed reason; each sheet's point arithmetic is correct and no image-count completion claim remains.
- [ ] Final README links detailed documents under docs/; screenshots are embedded with explanations and original-result links rather than an unexplained image pile.
- [ ] Diagrams match the accepted implementation and retain editable sources; five-class/design-pattern explanations point to actual code.
- [ ] One accepted release is easy to identify. Baseline/optimized/A/B differences are intentional and named, not contradictory status narratives.
- [ ] Exact superseded artifact deletions and link updates are reviewed and applied; useful original data/results survive locally. No blanket untracked deletion or history rewrite.
- [ ] Original results and images reopen locally, required links resolve, secrets are absent, and the evidence chain survives cloud shutdown.
- [ ] Agreed resources are torn down and verified absent or intentionally retained with explained cost/owner. Final docs state the actual deployment/teardown dates and do not claim a live platform after shutdown.
- [ ] The roadmap board reflects actual topic outcomes; final handoff gives demonstrated potential points, limitations, reproduction entrypoint and any remaining next action.

## Simplifications and limitations to explain

A clean submission can truthfully contain limitations and unsuccessful comparison results. Do not fabricate missing evidence to make every row look complete. An accepted release can have several linked runs. Teardown is not evidence that the platform never worked, and historical screenshots are not evidence that it remains online. Publishing/submitting externally is a separate explicit user action.

## Copyable planning prompt

```text
Plan G04 — Final submission and teardown only. This is an interview and planning session; do not implement code, delete artifacts, install tools, provision resources, or run a mutating workload. Writing agreed planning/glossary documents is permitted when the host mode allows it. Ask before expanding the topic.

Repository:
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission

Read:
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/README.md
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/rubric-map.md
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/evidence-guide.md
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/gcp/G04-submission-teardown.md

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

