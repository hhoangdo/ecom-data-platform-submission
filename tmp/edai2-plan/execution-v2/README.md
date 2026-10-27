# V2 execution roadmap

Agreed 2026-10-26. This pack is the starting outline for finalizing Vina Bim Shop against the **mini-coursework** and **LLM** rubrics. It is not approval to execute all topics automatically.

## Start here

1. Read the agreed direction below and the [rubric map](rubric-map.md).
2. Open **L01** in the status board and copy its planning prompt into a new chat.
3. Complete that topic's `grill-with-docs` interview. Understand the purpose, concrete output, dependencies, alternatives, limitations, and marks at stake before approving a detailed plan.
4. Explicitly request execution when ready. A planning prompt alone does not authorize implementation, deletion, installation, or provisioning.
5. Update the board here after each session. Continue to the next topic whose prerequisites are met.

The [evidence guide](evidence-guide.md) defines what counts as proof. The old execution-v1 plans and completion records are historical inputs, not competing implementation instructions. Until L01 inventories and removes superseded material, do not follow their extra approval, encryption, or study-mode requirements as v2 policy.

## Agreed direction

- **Optimize score within simplicity.** Review costly or complicated requirements with the owner. Record the exact points and limitations of a deliberate omission; never silently lower a requirement.
- **One story:** a data operations assistant helps an internal analyst understand metric definitions, data contracts, and runbooks, then measure changes in customer-order-frequency data. Drift means a change in data distribution, not proof of a cause or a failing predictive model.
- **Reuse working components.** Simplify operating procedures and duplicate code paths first. Remove a service only after explaining its consumers, replacement, and rubric impact.
- **One official baseline.** Local and GCP may use different addresses, resource sizes, and credentials. They must not become different study/production definitions of correctness. Test doubles remain normal test tools, labelled as such; they are not live integration evidence.
- **Single operator.** Central secret management remains in scope. No second mailbox, two-custodian ceremony, or special encrypted recovery folder is imposed. Do not commit secrets; choose ordinary credential storage and the smallest adequate central-secret workflow in L06.
- **One accepted release, linked runs.** Local checks, the cloud demonstration, baseline/optimized measurements, and A/B arms can have separate run IDs. Their revisions, datasets, configurations, and intended differences must be explained.
- **Fresh working tree.** Remove superseded plans/debug outputs with ordinary tracked deletions after extracting useful facts. Do not rewrite Git history. Inventory untracked artifacts and arrange recovery before deleting anything irreplaceable.
- **Readiness first.** No fixed deadline or cloud spending amount has been agreed. Do the feasible local work first; agree funding, quotas, spending limits, and teardown timing in G01 before provisioning.
- **Learn before implementing.** Topic interviews are part of the work. Avoid unexplained jargon and unexplained “partial” results.

## Sources and present facts

- [Rubric workbook](<../../rubic-check/Coursework Tracking (Public).xlsx>): `rubic (mini-coursework)` E2:E46 = 100; `Sheet3` E3:E62 = 100. The separate classic ML final sheet is excluded. LLM A2 is an unscored README/diagram instruction and still needs attention.
- Reference: [RecSys-MLops](https://github.com/itsmekhoathekid/RecSys-MLops), checked locally at `C:/Users/hhoangdo/Documents/Personal Projects/GitHub Repo/RecSys-MLops`. Learn from its measured workloads, native proof, explicit limitations, and diagrams; its entire stack is not a minimum requirement.
- Historical inputs: [execution-v1](../execution-v1/) and [LLM completion records](../../../evidence/04_2_llm_design/completion/). The trial was torn down on 2026-10-22. Historical evidence is not a currently live platform.
- The root README mixes older milestone/target claims. [The current LLM deliverable](../../../deliverables/04.2_llm_design.md) says the LLM application is out of scope, despite code and historical cloud work. L01 inventories these contradictions; L07 reconciles final documentation.
- Existing evidence includes empty Grafana panels, a generated Vault status card, auth results counting HTTP 405 responses as accepted, and green Jenkins verification runs without full build/deploy provenance. These are remediation inputs, not accepted proof of the corresponding behavior.
- Historical direct retrieval-to-generation used a 17-chunk smoke index. Canonical indexing, live lineage, both chat routes, registry/scaling, and several experiments need implementation or revalidation, not just new screenshots.
- The workstation has approximately 32 GiB RAM and 16 logical processors. Use staged local profiles; do not make simultaneous full-stack parity a prerequisite for local completion.

Recheck these facts against current files when starting a topic. A historical note is not authority over changed code.

## Single authoritative status board

All v2 topic execution status lives in this table. The briefs describe acceptance criteria; the rubric map records evidence claims. Neither is a second topic-status tracker.

| Topic and planning prompt | Prerequisites | State | Next action / dependency |
|---|---|---|---|
| [L01 — Baseline, cleanup, and tool rehearsal](local/L01-baseline-cleanup-tools.md) | None | Not started | Start the interview; classify current claims and artifacts. |
| [L02 — Mini-coursework pipelines](local/L02-mini-coursework-pipelines.md) | L01 | Not started | Revalidate existing mini work against actual rows. |
| [L03 — RAG knowledge lifecycle](local/L03-rag-knowledge-lifecycle.md) | L01; L02 feature/data contract | Not started | Agree the analyst corpus and persisted retrieval journey. |
| [L04 — Drift tools, agents, and chat](local/L04-drift-agents-chat.md) | L02, L03 | Not started | Agree example questions and trace both tools through the coordinator. |
| [L05 — Tests and experiments](local/L05-tests-experiments.md) | L02–L04 contracts | Not started | Design meaningful tests, comparisons, and original result capture. |
| [L06 — Release preparation](local/L06-release-preparation.md) | L01; L03–L05 contracts | Not started | Choose one feasible deployment/inference baseline and prepare it locally. |
| [L07 — Architecture and cloud readiness](local/L07-architecture-readiness.md) | L02–L06 for final readiness | Not started | Begin rough diagrams once L03/L04's story is agreed; close the readiness checklist last. |
| [G01 — Cloud foundation](gcp/G01-cloud-foundation.md) | L07; operator funding decision | Not started | Verify account, quotas, spending and shutdown limits before apply. |
| [G02 — Deploy the official platform](gcp/G02-official-deployment.md) | G01 | Not started | Deploy the prepared release and execute real CI/CD jobs. |
| [G03 — Run and capture proof](gcp/G03-proof-runs.md) | G02 | Not started | Run agreed workloads/experiments and capture native results. |
| [G04 — Final submission and teardown](gcp/G04-submission-teardown.md) | G03 | Not started | Reconcile claims, curate the submission, and verify teardown. |

Allowed states: **Not started**, **In progress**, **Blocked**, **Done**. “Done” means the topic's own acceptance criteria passed. L06 can be done with explicitly identified live checks owned by G02/G03. That is a normal dependency, not a local failure. “Blocked” must name a failed behavior, its consequence, and the exact next action or user decision; do not write only “cloud unavailable” or “partial.”

Default order is L01 → L02 → L03 → L04 → L05 → L06 → L07 → G01 → G02 → G03 → G04. Once their input contracts are agreed, diagram drafts and independent test/deployment preparation may overlap. Do not expand into another 30-topic program without discussing why a split is necessary.

## Contract for every topic session

Read the brief, relevant rubric rows, and actual code before questioning the owner. Use `C:/Users/hhoangdo/.agents/skills/grill-with-docs/SKILL.md`, which invokes `grilling` and `domain-modeling`; if the harness has no Skill tool, read the named skill files and follow them. Ask decisions, not discoverable file-location questions. Ask the ready decision frontier in understandable rounds, recommending an answer and explaining its cost. Do not invent an entire implementation before interviewing.

Agree the topic design, then replace the final section of that same brief with its detailed plan. Keep one current plan per topic. State exact inputs/outputs, affected files/interfaces, verification commands and expected results, screenshot recipes, and genuinely deferred cloud checks. Resolve project-specific terms in the root [CONTEXT.md](../../../CONTEXT.md) when writing is permitted; it is a glossary, not a status log. Create an ADR only for a consequential, surprising tradeoff, not every routine choice.

At the end of execution, report: what now works; command/result evidence; the board state; limitations/marks not claimed; and one exact next action. Update the board once. Never interpret unit-test mocks, configured YAML, or a rendered diagram as proof of a live integration.

## Tooling and cloud defaults

Use existing `gcloud`, Terraform, kubectl, Helm, Docker, and Playwright first. L01 rehearses native browser/desktop capture and editable Excalidraw export; only add a small integration when it removes a demonstrated difficulty. The [Google gcloud MCP](https://github.com/googleapis/gcloud-mcp) is a candidate CLI interface, not a replacement for credentials, quotas, or reproducible Terraform. It is preview software. The [official Excalidraw MCP](https://github.com/excalidraw/excalidraw-mcp) is a candidate for drafts, subject to an existing-file edit/export rehearsal. Codex [supports configured MCP servers](https://learn.chatgpt.com/docs/extend/mcp). None is installed by this pack.

[Spacelift MCP](https://docs.spacelift.io/concepts/intelligence/spacelift-mcp) is technically suitable for managing infrastructure, but deferred: another account/workflow must justify its complexity. Do not let ad hoc MCP provisioning and Terraform separately own the same resources.

G01 requires an operator-selected, eligible funded project. [Google's trial terms](https://docs.cloud.google.com/free/docs/free-cloud-features) exclude previous trial signups and restrict GPU/quota access on non-billable trials. Do not assume a new email grants another trial or plan an unverified GPU deployment. Spending alerts are not a hard spending cap; agree the operating window and shutdown action.

## Pack acceptance

- Exactly three shared documents and eleven linked briefs; each brief includes its own copyable planning prompt and observable outcomes.
- Every scored row appears once in the rubric map with its real workbook weight, owner, proof, environment, and claim state. Each rubric totals 100; no invented scores for LLM row 2.
- Initial pending claims mean **not certified for the v2 release**, not “the historical project achieved nothing.” No runtime marks are asserted by writing these plans.
- Relative navigation resolves, topic prerequisites have no cycle, and old plans remain historical inputs until the planned cleanup occurs.
- No implementation, service installation, screenshot fabrication, cloud mutation, or historical artifact deletion is part of creating this pack.
