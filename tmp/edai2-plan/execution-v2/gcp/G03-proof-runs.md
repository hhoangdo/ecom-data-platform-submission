# G03 — Run and capture proof

[Roadmap and status board](../README.md) · [Rubric map](../rubric-map.md) · [Evidence guide](../evidence-guide.md)

## Purpose and examples

Collect the actual behavioral and measurement evidence the instructor needs while the deployed platform is accessible.

Examples: “Did replicas increase because of our load?” and “Can I trace this chat request through the coordinator, tool, retrieval/model spans and token metrics?”

## Expected output

Original results for the agreed live journeys/experiments, populated dashboards, executed notebooks and native screenshots with complete human fallback recipes. Each result links to the accepted release and explains its limits.

## Inspect before interviewing

All repository paths below are relative to `C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission`. Inspect the actual implementation, not only old plans.

- G02's smoke/deployment/CI outputs, L05's exact experiment designs, L06's telemetry definitions and the shared evidence guide.
- `scripts/llm/`, `tests/load/`, `notebooks/edai2/`, actual KEDA/sandbox/substrate/rollout probes and dashboard queries.
- Prior auth/benchmark/visual-review artifacts to ensure known 405/No-data/verification-only failure modes are not repeated.
- The owner-approved spending/time window and local download destination before beginning long-running work.

**Rubric ownership:** Gathers actual cloud behavior for E05, E08–E26, E31, E35–E47, E50–E58 and any cloud-dependent E61/E62 proof. Reuses E48/E49 applied evidence from G01/G02 and local test proof from L05 rather than rerunning unrelated work for screenshots.

**Reference reading:** under `C:/Users/hhoangdo/Documents/Personal Projects/GitHub Repo/RecSys-MLops`: `docs/submission/rubric-final-coursework-(final-llm)/benchmark_proof/`, `llm_inference_platform.md`, `benchmark_ha.md`, `a_b.md`, `observability.md`, and native `docs/pngs/ai-observability-command-center-overview.png`.. Follow its evidence discipline and stated limitations; do not copy unrelated infrastructure.

## Dependencies and boundary

Requires G02's actual working platform and L05's agreed comparable treatments. Do not begin workload capture with uninstrumented paths or placeholder data. If agent access fails but the behavior works, use the exact manual recipe; if behavior fails, repair it or mark the row pending.

## Decisions for the grill-with-docs interview

- What workload/run order fits the approved cost window while keeping baselines, warm state and A/B traffic comparable?
- Which native views and original results prove each row, and which screenshots can be shared without hiding important differences?
- How will sandbox restrictions, tool failures, rolling update/fallback, scaling transitions and worker warm-up be observed without an oversized destructive chaos program?
- Which requests create real LLM/agent/safety/tool telemetry, what time ranges/queries identify them, and how are zero observations distinguished from no samples?
- Who captures each inaccessible authenticated/desktop view, using which exact workload/navigation recipe, before teardown?

These are interview questions, not preselected implementation requirements. Present the actual alternatives and score consequences, recommend a feasible answer, and wait for the owner's decisions.

## Acceptance criteria

- [ ] Both actual specialist/coordinator chat journeys and executed notebooks demonstrate agent → MCP → Feast/drift behavior with original outputs.
- [ ] Replica transitions, real sandbox restrictions, rolling update/fallback and warm-up comparisons are observed against explicit expected results.
- [ ] Inference optimization, Locust HTML/CSV, agent-config A/B and model-version A/B have original workload/config/results, both arms where required, failures and honest limitations.
- [ ] Native API/host/LLM/agent/tool dashboards contain real samples for the run; logs and traces correlate with actual requests and tool behavior.
- [ ] Actual Airflow/DataHub/registry/CI/gateway/auth/HTTPS/central-secret views support their claims. Invalid positive auth classifications and generated runtime cards are rejected.
- [ ] Every accepted screenshot is inspected for readability/result/context; every failed capture has a precise human fallback, not a fabricated substitute.
- [ ] Original logs, reports, applied configs and screenshots are downloaded and checked locally before G04 permits teardown. Pending or Not claimed rows identify exact missing behavior/points.

## Simplifications and limitations to explain

Small experiments support measured observations under stated conditions, not universal performance or causal guarantees. Do not hide counterexamples by rerunning until a preferred screenshot appears. Avoid extending the cloud window to chase decorative evidence; prioritize actual missing rubric behavior and the agreed score/simplicity tradeoff.

## Copyable planning prompt

```text
Plan G03 — Run and capture proof only. This is an interview and planning session; do not implement code, delete artifacts, install tools, provision resources, or run a mutating workload. Writing agreed planning/glossary documents is permitted when the host mode allows it. Ask before expanding the topic.

Repository:
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission

Read:
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/README.md
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/rubric-map.md
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/evidence-guide.md
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/gcp/G03-proof-runs.md

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

