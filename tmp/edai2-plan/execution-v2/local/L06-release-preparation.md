# L06 — Release preparation

[Roadmap and status board](../README.md) · [Rubric map](../rubric-map.md) · [Evidence guide](../evidence-guide.md)

## Purpose and examples

Turn the agreed application into one reproducible deployable release so the later cloud window is spent running demonstrations rather than repairing packaging and operational policy.

Examples: “Which image and configuration will each agent actually run?” and “Can this pipeline test, build and deploy that exact revision without hand-editing a cluster?”

## Expected output

One chosen feasible inference/deployment baseline; reproducible images/charts/IaC/CI definitions; ordinary single-operator secret/auth workflow; real instrumentation and a precise G01–G03 handoff.

## Inspect before interviewing

All repository paths below are relative to `C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission`. Inspect the actual implementation, not only old plans.

- `infra/terraform/`, `infra/helm/`, `infra/kustomize/`, `infra/kind/`, `infra/kagent/`, `infra/agentgateway/`, `infra/agentregistry/`, `infra/substrate/`.
- `infra/security/`, `infra/ingress/`, `infra/observability/`, `containers/`, `ci/jenkins/`, `cloudbuild.yaml`, `cloudbuild-coordinator.yaml`.
- `configs/llm/models.yaml`, `routing.yaml`, `src/vina_bim_shop/llm/telemetry.py`, `observability.py`, `scripts/gke/`, `scripts/feast/`.
- Completion topics 22–27/30; locate Ansible roles or establish whether they are missing. Check stale project/registry/revision defaults, placeholder model digests, missing runtime probes, personal-study branches and Jenkins verification-only stages.

**Rubric ownership:** E03–E04, E06–E07, E12–E15, E18–E21, E24–E25, E35–E55, E58 (62 points). This is preparation ownership, not a claim that manifests earn runtime marks. E48 proof is G01; remaining deployed/live proof is G02/G03.

**Reference reading:** under `C:/Users/hhoangdo/Documents/Personal Projects/GitHub Repo/RecSys-MLops`: `docs/submission/rubric-final-coursework-(final-llm)/llm_inference_platform.md`, `global_model_config.md`, `agent_registry.md`, `ci_cd.md`, `routing_gateway.md`, `security.md`, `iac.md`, `observability.md`.. Follow its evidence discipline and stated limitations; do not copy unrelated infrastructure.

## Dependencies and boundary

Requires L01 and stable L03–L05 interfaces/experiment requirements. Deployment preparation can overlap after contracts are agreed. Choose versions and compatibility during this interview; do not assume GPU access, a public-IP pattern, a particular secret product, or complete local stack capacity.

## Decisions for the grill-with-docs interview

- Which compatible inference runtime/model, agent framework and sandbox/substrate configuration meet the rubric with the least operational burden? Compare the reference's CPU-small-model approach without assuming acceptance of every substitution.
- What components actually need replication/HA, what scales via KEDA, and how will rolling-update/fallback work for MCP tools and agents? Explain worker-pool warm-up separately from scaling.
- How will the six pipelines each perform test + build + automatic deployment, including paired MCP/agent versions and offline/online stream-feature writers?
- Which minimal central secret system, normal credential storage, username/password/rate limit and HTTPS/domain approach works for one owner? No extra mailbox/encrypted-folder ceremony.
- What telemetry must be emitted at source for token/RTT/TTFT/safety/agent/tool metrics, API/host metrics, logs and traces? How are request/run identities correlated?
- What actual VM service justifies Ansible's role-based deployment row without inventing a large new subsystem? How will Terraform remain the single owner of persistent cloud resources?

These are interview questions, not preselected implementation requirements. Present the actual alternatives and score consequences, recommend a feasible answer, and wait for the owner's decisions.

## Acceptance criteria

- [ ] One runtime/model/configuration path is documented with actual compatible versions and real artifact identities; no repeated-digit digests or stale cloud defaults remain in the agreed release configuration.
- [ ] Required images build and local checks render/validate charts, routing, health/readiness, registry publication, sandbox and autoscale/rollback configuration. These checks are labelled preparation, not live runtime proof.
- [ ] Six explicit CI/CD definitions cover RAG, retrieval MCP+agent, drift MCP+agent, coordinator, offline writer and online writer. Verification-only jobs are not the deployment path.
- [ ] Terraform and actual Ansible role inventory are prepared and locally checked; cloud inputs/state/bootstrap instructions are explicit and credential-free in public docs.
- [ ] The agreed single-operator secret/auth workflow removes competing study/production branches without relaxing unrelated data correctness. Configured local addresses do not force public ingress.
- [ ] Instrumentation has meaningful local checks, including failure accounting; dashboards query emitted metrics and can distinguish no samples from zero values.
- [ ] G01 receives exact cloud inputs/cost assumptions; G02 receives deploy/build/rollback steps; G03 receives route, workload, telemetry and proof recipes. Live outcomes remain pending there.

## Simplifications and limitations to explain

Keep working services unless a discussed replacement simplifies the project with an explicit score impact. Central secret management is required, but Vault Raft/KMS ceremonies are not independently demanded by E58. Keep authentication simple; a custom evidence login page is not a substitute for actual chat UI authentication. Templates passing locally do not establish autoscale, sandbox enforcement, HTTPS or CI/CD success. Model/GPU quotas and actual spending are verified in G01, not assumed here.

## Copyable planning prompt

```text
Plan L06 — Release preparation only. This is an interview and planning session; do not implement code, delete artifacts, install tools, provision resources, or run a mutating workload. Writing agreed planning/glossary documents is permitted when the host mode allows it. Ask before expanding the topic.

Repository:
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission

Read:
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/README.md
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/rubric-map.md
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/evidence-guide.md
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/local/L06-release-preparation.md

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

