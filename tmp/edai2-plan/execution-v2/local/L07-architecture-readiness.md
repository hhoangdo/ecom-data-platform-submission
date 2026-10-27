# L07 — Architecture and cloud readiness

[Roadmap and status board](../README.md) · [Rubric map](../rubric-map.md) · [Evidence guide](../evidence-guide.md)

## Purpose and examples

Let the owner and instructor follow the complete platform without decoding a wall of components or conflicting milestone descriptions.

Examples: “Trace one generated order into a feature and then a drift answer” and “Show how a question reaches retrieved definitions and the model, and where the answer returns.”

## Expected output

An agreed rough whole-platform layout, editable and rendered final diagrams, reconciled README/detailed docs and five-class explanation, plus a staged local rehearsal and explicit cloud handoff checklist.

## Inspect before interviewing

All repository paths below are relative to `C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission`. Inspect the actual implementation, not only old plans.

- `architecture/diagrams/detailed-architecture.excalidraw`, `architecture/diagrams/platform_deployment/platform-architecture.puml`, `detailed-platform-architecture.puml` in that same directory.
- `README.md`, `deliverables/04.2_llm_design.md`, `docs/`, actual L02–L06 outputs and `evidence/04_2_llm_design/screenshots/whole_course_diagram.png`.
- Existing diagram source/render workflows. Check data paths, runtime boundaries, proposed-versus-implemented labels and source/render drift before drawing.
- Actual central classes under `src/vina_bim_shop/llm/`; do not invent classes merely to fill a documentation template.

**Rubric ownership:** M02 (10 points), E60 (1 point), plus unscored Sheet3 A2 documentation/whole-course diagram requirements. Each other topic owns its detailed evidence; L07 assembles the explanation, G04 validates the final release narrative.

**Reference reading:** under `C:/Users/hhoangdo/Documents/Personal Projects/GitHub Repo/RecSys-MLops`: `docs/pngs/full_flow.png`, `final_llm_4k.png`, `overview.png`, the reference README and `docs/submission/rubric-final-coursework-(final-llm)/repository_design.md`. These are files, not directories. Prioritize readability over the giant overview export's dimensions.. Follow its evidence discipline and stated limitations; do not copy unrelated infrastructure.

## Dependencies and boundary

Rough layout can start after L03/L04's story/interfaces are agreed. Final local readiness requires L02–L06 acceptance or an explicit owner-approved scope/score change. G01 must not begin while unresolved local implementation problems are merely labelled cloud work.

## Decisions for the grill-with-docs interview

- Which 10–15 top-level blocks tell the whole story without hiding deployable units? Where do stores/SDKs/agents/controllers belong?
- Which two paths show preparation/indexing and analyst question → agent → tool/model → response? What data actually crosses each arrow?
- What belongs in the separate LLM deployment companion rather than cluttering the main overview? Preserve the existing mini-coursework view.
- Which editable source/export workflow passed L01's rehearsal? How do rough layout review and later icon polish avoid duplicated unsynchronized diagrams?
- Which five actual classes best explain the system, and which limitations must the owner be able to explain in the presentation?

These are interview questions, not preselected implementation requirements. Present the actual alternatives and score consequences, recommend a feasible answer, and wait for the owner's decisions.

## Acceptance criteria

- [ ] Rough whole-platform composition is reviewed before adding logos. It connects data/features to actual agents/RAG, shows the analyst and response, and keeps CI/evidence off the application path.
- [ ] Existing mini Excalidraw is preserved. The whole-platform overview and focused LLM deployment view have one editable source each and readable matching PNG/SVG exports.
- [ ] Main overview uses meaningful labelled data arrows and only line styles that actually appear; proposed components are explicitly distinguished from verified implementation.
- [ ] Root README truthfully explains both data and LLM work with TOC, structure and links to detailed annotated evidence under docs/. Obsolete out-of-scope LLM claims are reconciled.
- [ ] Five real classes have responsibilities/interfaces linked to source; relevant module/class/function docstrings are checked without an unrelated code-wide rewrite.
- [ ] Staged local commands reproduce the agreed outputs within machine resources. Record actual results and separate normal G03 runtime measurements from unresolved local implementation defects.
- [ ] G01 handoff lists exact source/image/config/data/index inputs, required quotas/resources, remaining cloud-only checks and human account/domain/login actions. No claim that the entire platform has run in the cloud.

## Simplifications and limitations to explain

Architecture diagrams are explanatory artifacts, not runtime screenshots. A Feast SDK is not a separately deployed service. Do not copy every reference component or reproduce its 14k-pixel canvas. Keep cluster pools/routes/benchmark sequences in focused views. L07's readiness checklist is a handoff result; the only topic-status board remains the root roadmap.

## Copyable planning prompt

```text
Plan L07 — Architecture and cloud readiness only. This is an interview and planning session; do not implement code, delete artifacts, install tools, provision resources, or run a mutating workload. Writing agreed planning/glossary documents is permitted when the host mode allows it. Ask before expanding the topic.

Repository:
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission

Read:
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/README.md
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/rubric-map.md
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/evidence-guide.md
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/local/L07-architecture-readiness.md

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

