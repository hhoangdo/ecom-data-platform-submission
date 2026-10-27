# G01 — Cloud foundation

[Roadmap and status board](../README.md) · [Rubric map](../rubric-map.md) · [Evidence guide](../evidence-guide.md)

## Purpose and examples

Start the cloud window only when account access, cost and resource availability are known, and create the foundation from the locally prepared configuration.

Examples: “Can the selected funded project run our chosen model and node layout?” and “Which Terraform state owns these resources, and when will we shut them down?”

## Expected output

An operator-approved funded project/region/resource envelope, verified quotas and contexts, actual Terraform foundation and applicable Ansible configuration, and a recorded shutdown plan.

## Inspect before interviewing

All repository paths below are relative to `C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission`. Inspect the actual implementation, not only old plans.

- L07's cloud handoff and L06's exact Terraform/Ansible definitions and cost/resource assumptions.
- `infra/terraform/`, `scripts/gke/check_budget.py`, `teardown.py`, account/budget scripts and actual Ansible roles located/prepared by L06.
- `evidence/04_2_llm_design/completion/22-gcp-account-budget-terraform-apply.md`, `22-handoff-to-personal-pc.md`, `23-vault-kms-model-cache-bootstrap.md`; historical project IDs and waivers are not new-account inputs.
- Current official funding/trial/quotas documentation and live read-only account/project checks, without printing credentials.

**Rubric ownership:** Executes E48 (1 point); E49 (1 point) is executed here or in G02 depending on the agreed VM service. L06 owns their preparation. No foundation credit is claimed from validate/plan/check alone.

**Reference reading:** under `C:/Users/hhoangdo/Documents/Personal Projects/GitHub Repo/RecSys-MLops`: `docs/submission/rubric-final-coursework-(final-llm)/iac.md`, `security.md`, and the actual reference Terraform/Ansible organization.. Follow its evidence discipline and stated limitations; do not copy unrelated infrastructure.

## Dependencies and boundary

Requires L07 local readiness and the operator's funding decision. Planning can occur before funding; provisioning cannot. If the intended account lacks eligible credits/GPU/quota, discuss the actual supported alternatives and spending consequences rather than evading eligibility or silently changing the model.

## Decisions for the grill-with-docs interview

- What eligible funded project/account will be used, and what total spending ceiling and operating window does the owner approve? No amount is currently assumed.
- Which region/resources/quotas support the L06 runtime, including CPU/GPU where applicable, external addresses/disks and any domain requirement?
- How will project ID, account, kubectl context, Terraform backend/state and registry destinations be explicitly selected so an agent cannot act on the expired project by accident?
- Which minimal cloud permissions and one-time human login/account actions are necessary? Can ordinary CLI authentication avoid long-lived key files?
- What is the precise shutdown schedule, resource inventory and evidence-download location? Budgets alert; they do not enforce a hard spending cap.

These are interview questions, not preselected implementation requirements. Present the actual alternatives and score consequences, recommend a feasible answer, and wait for the owner's decisions.

## Acceptance criteria

- [ ] Operator funding, spending ceiling and shutdown window are recorded before apply. Trial eligibility and actual quotas are verified, not inferred from a new email.
- [ ] Read-only preflight confirms active account/project/region, enabled necessary APIs and capacity for the already agreed baseline.
- [ ] Terraform plan is reviewed for intended resources and applied in the correct state. Native output and matching cloud resources support E48.
- [ ] If Ansible runs here, actual roles configure/deploy the agreed VM service with a resulting service check; otherwise G02 explicitly owns this proof.
- [ ] Node/storage/registry/network foundation is ready for G02. Human/domain/access prerequisites are concrete, without second-email or encrypted-folder rituals.
- [ ] Resource inventory, result-download path and exact teardown verification steps are recorded while resources are known.

## Simplifications and limitations to explain

Do not recreate every historical optional cloud service. Quota/funding failure is a real external prerequisite, not permission to label a substitute deployment equivalent. Use one IaC resource owner; CLI/MCP can inspect or operate the agreed environment without inventing separately managed persistent resources. No workloads should run indefinitely while waiting for a documentation decision.

## Copyable planning prompt

```text
Plan G01 — Cloud foundation only. This is an interview and planning session; do not implement code, delete artifacts, install tools, provision resources, or run a mutating workload. Writing agreed planning/glossary documents is permitted when the host mode allows it. Ask before expanding the topic.

Repository:
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission

Read:
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/README.md
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/rubric-map.md
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/evidence-guide.md
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/gcp/G01-cloud-foundation.md

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

