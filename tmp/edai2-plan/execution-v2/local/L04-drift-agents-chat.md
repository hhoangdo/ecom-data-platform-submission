# L04 — Drift tools, agents, and chat

[Roadmap and status board](../README.md) · [Rubric map](../rubric-map.md) · [Evidence guide](../evidence-guide.md)

## Purpose and examples

Give the analyst one understandable entry point that can consult definitions and measure customer-feature drift, rather than two unrelated demonstrations.

Examples: “Define the order-frequency feature and check whether it changed between these two periods” and “Which user features and contract should I inspect before acting on this alert?” A measured change is evidence to investigate, not a causal diagnosis.

## Expected output

An agreed set of analyst questions, validated async feature/chunk and drift APIs, two actual MCP tool contracts, coordinator routing, an honest local interaction rehearsal, and two runnable notebook demonstrations.

## Inspect before interviewing

All repository paths below are relative to `C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission`. Inspect the actual implementation, not only old plans.

- `src/vina_bim_shop/llm/api/`, `mcp/`, `coordinator.py`, `drift.py`, `routing.py`, `contracts.py`, `safety.py`, and `adapters/direct.py`.
- `infra/kagent/`, `infra/agentgateway/`, `infra/agentregistry/`, `configs/llm/routing.yaml`, `notebooks/edai2/`.
- `evidence/04_2_llm_design/completion/26-keda-agent-ha-registry-rollbacks.md`, `29-evaluation-ab-notebooks-load-test-evidence.md` and current API/UI routes.
- L02/L03's actual Feast lookup, drift dataset and corpus contracts. Check the historical direct adapter's support-only path and its experiment-variant behavior.

**Rubric ownership:** E10–E11, E16–E17, E22–E23 (8 points). Supplies behavior for the replicated/sandboxed/registered specialist and coordinator rows owned by L06. G03 supplies the final live agent/UI proof demanded by the shared workbook headings.

**Reference reading:** under `C:/Users/hhoangdo/Documents/Personal Projects/GitHub Repo/RecSys-MLops`: `docs/submission/rubric-final-coursework-(final-llm)/agent_pull_data.md`, `agent_recommendation_servicce.md`, `agent_coordinator.md`, `agent_notebooks.md`.. Follow its evidence discipline and stated limitations; do not copy unrelated infrastructure.

## Dependencies and boundary

Requires L02/L03's agreed data and retrieval contracts. Define logical behavior and local tests before L06 packages it. Real cloud model serving, registry, sandbox replicas and autoscale are verified by G02/G03; do not require those to accept a clearly labelled local contract check.

## Decisions for the grill-with-docs interview

- What exact questions route to retrieval, drift, or both, and what response makes the measured facts and cited definitions clear?
- Which API/MCP interfaces already work, what genuinely needs changing, and how are feature ID and chunk ID lookup both demonstrated?
- How should unknown IDs, missing baselines, invalid periods, unsupported questions and tool failure appear to the analyst?
- Which single agent/coordinator path is official? What happens to the support-only direct fallback without maintaining a second architecture?
- Which UI and two notebook journeys demonstrate actual agent → MCP → Feast/drift interaction rather than just calling helper functions?

These are interview questions, not preselected implementation requirements. Present the actual alternatives and score consequences, recommend a feasible answer, and wait for the owner's decisions.

## Acceptance criteria

- [ ] Two concrete analyst journeys connect retrieval definitions and measured drift; no output implies causation without evidence.
- [ ] FastAPI/Pydantic validation, health/readiness and real async handling are verified with meaningful invalid-input/failure cases.
- [ ] Both user-feature and chunk lookup operate through the agreed Feast-backed path; drift uses the agreed baseline/current data.
- [ ] MCP protocol/capabilities and coordinator routing are exercised. A direct HTTP retrieval call alone is not called agent/MCP proof.
- [ ] The official chat flow supports both agreed specialist behaviors. Any local inference fixture is explicitly labelled and leaves live generation proof to G03.
- [ ] Two notebooks are runnable against explicit endpoints, preserve actual output when run, and separate offline fixtures from real integration runs.
- [ ] Interfaces, sample requests/answers and runtime dependencies are handed to L05/L06. G03 repeats the actual live journeys through the final chat UI.

## Simplifications and limitations to explain

Keep the assistant read-only: no marketplace order mutations or invented operational autonomy. Prefer ordinary clear routing over extra agents. Do not make provider-specific tooling an unexplained learning prerequisite. Stochastic wording is not a sensible idempotency assertion; preserve deterministic data/tool invariants separately.

## Copyable planning prompt

```text
Plan L04 — Drift tools, agents, and chat only. This is an interview and planning session; do not implement code, delete artifacts, install tools, provision resources, or run a mutating workload. Writing agreed planning/glossary documents is permitted when the host mode allows it. Ask before expanding the topic.

Repository:
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission

Read:
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/README.md
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/rubric-map.md
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/evidence-guide.md
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/local/L04-drift-agents-chat.md

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

