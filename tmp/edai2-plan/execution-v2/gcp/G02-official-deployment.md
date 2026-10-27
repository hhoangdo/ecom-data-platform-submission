# G02 — Deploy the official platform

[Roadmap and status board](../README.md) · [Rubric map](../rubric-map.md) · [Evidence guide](../evidence-guide.md)

## Purpose and examples

Turn the prepared release into a real running platform and show that its deployment pipelines actually build and deploy the code being demonstrated.

Examples: “Can an analyst ask for a definition and a drift check through the actual chat UI?” and “Did the six CI/CD jobs deploy their own built images, rather than merely verify old tags?”

## Expected output

One identified release with persisted feature/RAG data, working model/agents/MCP/coordinator, registry/chat/gateway/security/telemetry and six successful test-build-deploy pipelines. Initial smoke results establish readiness for G03's experiments.

## Inspect before interviewing

All repository paths below are relative to `C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission`. Inspect the actual implementation, not only old plans.

- G01's resource/context outputs; L06's release definition and exact build/deploy/rollback commands; L03/L04's data/API contracts.
- `ci/jenkins/`, `infra/helm/`, `infra/kagent/`, `infra/agentgateway/`, `infra/agentregistry/`, `infra/security/`, `infra/observability/`, feature writer configurations.
- `scripts/llm/smoke_release.py`, `publish_agents.py`, actual notebook endpoints and runtime readiness checks.
- Historical completion topics 24–28: direct Helm parity and green verification jobs must not be mistaken for the six genuine CI/CD demonstrations.

**Rubric ownership:** Executes deployment proof for L06's E03–E04/E06–E07, specialist/coordinator deployment and registry rows, E35–E40 and relevant gateway/security rows. Completes E49 if assigned from G01. G03 owns measured scaling/fallback/experiments and final native proof.

**Reference reading:** under `C:/Users/hhoangdo/Documents/Personal Projects/GitHub Repo/RecSys-MLops`: `docs/submission/rubric-final-coursework-(final-llm)/ci_cd.md`, `global_model_config.md`, `agent_registry.md`, `agent_coordinator.md`, `routing_gateway.md`.. Follow its evidence discipline and stated limitations; do not copy unrelated infrastructure.

## Dependencies and boundary

Requires G01. Deploy only the locally approved runtime/version configuration. If a live incompatibility requires a new major choice, explain it and update L06's one baseline; do not create another study-only fallback architecture. Use the agreed stop/shutdown rules while fixing deployment problems.

## Decisions for the grill-with-docs interview

- Which actual source revision, images/model versions and data/index identities form the accepted release, and what sequence respects their real dependencies?
- How does each CI job prove tests, build output and automatic deployment into this release? Where is the original console/stage evidence preserved?
- What minimal smoke journey demonstrates actual Feast lookup, both MCP agents, coordinator response, citations and drift output through the final chat UI?
- Which real secret/auth/registry/gateway/telemetry checks must succeed before starting G03? How will missing data and bad responses be detected?
- What rollback/retry behavior applies to a failed install without leaving multiple competing deployments or unexplained patches?

These are interview questions, not preselected implementation requirements. Present the actual alternatives and score consequences, recommend a feasible answer, and wait for the owner's decisions.

## Acceptance criteria

- [ ] Selected model serves real requests through the applied global configuration/gateway; original model/runtime identities are captured.
- [ ] Canonical feature data and RAG corpus/index are persisted and queryable; actual Airflow work and DataHub lineage are present.
- [ ] Retrieval/feature and drift tools work through their agents and coordinator; registry entries match running revisions. The real chat UI supports both journeys.
- [ ] Required replicas, sandbox/scaling/warm-up configuration and health/readiness are installed; configuration alone is not marked measured scaling/HA proof.
- [ ] Six CI/CD jobs actually test, build and automatically deploy RAG, retrieval MCP+agent, drift MCP+agent, coordinator, offline writer and online writer; resulting outputs match built artifacts.
- [ ] Gateway routes, username/password/rate-limit setup, HTTPS retrieval API, central secret use, metric/log/trace collection and any assigned Ansible service pass initial real checks.
- [ ] Native installation/CI/smoke outputs are saved. G03 receives exact URLs, contexts, queries, run/data identities and proof workload commands.

## Simplifications and limitations to explain

A smoke test is not a full benchmark. “No data” telemetry means investigate instrumentation/queries before G03, not just capture the dashboard layout. Do not call five HTTP 405s five accepted chat requests. Preserve human-readable evidence and original output without restoring the old heavyweight sealing process.

## Copyable planning prompt

```text
Plan G02 — Deploy the official platform only. This is an interview and planning session; do not implement code, delete artifacts, install tools, provision resources, or run a mutating workload. Writing agreed planning/glossary documents is permitted when the host mode allows it. Ask before expanding the topic.

Repository:
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission

Read:
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/README.md
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/rubric-map.md
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/evidence-guide.md
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/gcp/G02-official-deployment.md

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

