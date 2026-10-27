# L05 — Tests and experiments

[Roadmap and status board](../README.md) · [Rubric map](../rubric-map.md) · [Evidence guide](../evidence-guide.md)

## Purpose and examples

Show that the system handles meaningful cases and that claimed improvements are measured, rather than presenting green reports with unclear scope.

Examples: “Do repeated feature writes create duplicates?” and “Did warm-up actually reduce first-response time on the same workload, and what did it cost?”

## Expected output

Runnable test and measurement recipes, native local test reports, original result capture, agreed experiment designs and bounded novelty candidates. Actual cluster measurements are explicitly reserved for G03.

## Inspect before interviewing

All repository paths below are relative to `C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission`. Inspect the actual implementation, not only old plans.

- `tests/unit/`, `tests/integration/`, `tests/contract/`, `tests/property/`, `tests/load/`, `tests/fixtures/`, `pyproject.toml`.
- `configs/llm/test_scope.yaml`, `coverage.ini`, `evaluation.yaml`, `benchmark_requests.json`, `warmup_prompts.json`.
- `scripts/llm/run_evaluation.py`, `benchmark_inference.py`, `live_runner.py`, `scripts/qa/verify_edai2_test_scope.py`, `verify_edai2_mutation_score.py`.
- `src/vina_bim_shop/llm/evaluation.py`, `inference.py`, `infra/substrate/`, historical completion topics 28/29 and claimed testing screenshots.

**Rubric ownership:** E05, E26–E31, E56–E57, E61–E62 (19 points). L02 owns generator/drift labels and mini novelty. Do not double-count a single unexamined feature as four novelty ideas.

**Reference reading:** under `C:/Users/hhoangdo/Documents/Personal Projects/GitHub Repo/RecSys-MLops`: `docs/submission/rubric-final-coursework-(final-llm)/validation_verification.md`, `llm_inference_platform.md`, `benchmark_ha.md`, `a_b.md`, `noval_ideas.md`, `benchmark_proof/`.. Follow its evidence discipline and stated limitations; do not copy unrelated infrastructure.

## Dependencies and boundary

Requires stable L02–L04 contracts. Formal test reporting is local; inference/warm-up/A/B/load harnesses can be prepared with labelled fixtures or a small available runtime. Do not claim live performance from those fixtures. L06 chooses the final deployment/runtime; G03 executes the agreed cloud treatments.

## Decisions for the grill-with-docs interview

- What is the honest changed-code/API coverage and mutation scope? Retain the rubric's strict >90% coverage and >80% mutation thresholds without gaming exclusions.
- Which concrete partitions/boundaries, repeat-write/replay invariants and failure cases test the actual contracts? How will mocks be distinguished from integration proof?
- What comparable inputs, versions, warm/cold state, repetitions and measurements are feasible for inference, warm-up and load tests?
- What differs in agent model configuration versus model version for the two A/B rows, and how will both arms receive actual traffic?
- Which two existing LLM novelty candidates have separate, demonstrable value? What results would honestly fail to support an improvement claim?

These are interview questions, not preselected implementation requirements. Present the actual alternatives and score consequences, recommend a feasible answer, and wait for the owner's decisions.

## Acceptance criteria

- [ ] Native API test output states the real tested scope and demonstrates coverage >90%, fixtures/mocks and explicit integration boundaries.
- [ ] Named equivalence partitions/boundaries and meaningful property-based idempotency assertions execute; mutation score >80% is measured on stated changed code.
- [ ] Locust can produce original HTML/CSV plus request/failure/latency data; invalid status codes cannot count as successful responses.
- [ ] Inference and startup comparisons specify the actual treatment, common workload, timing/resource/cost definitions and original result capture. Do not invent a promised speedup.
- [ ] Agent-config and model-version A/B are distinct experiments with version/arm identities and both traffic counts; quality evaluation is explained.
- [ ] Existing evaluation gates/sample sets are reviewed for relevance to the new corpus. Arbitrary inherited numeric gates are not silently imposed or removed.
- [ ] Two bounded novelty choices have agreed implementation/proof owners; new code is not secretly bundled into a testing topic.
- [ ] Local formal results are linked; the G03 experiment handoff specifies actual live checks and any non-statistical limitations.

## Simplifications and limitations to explain

A small number of runs can demonstrate method and observed behavior, not broad causal/statistical conclusions. Report failures and confounders. Do not rerun the whole repository's mutation suite on every edit when the rubric asks for changed code. No mocked timing, fabricated benchmark CSV or custom success card can replace native output. Failure to meet an agreed gate triggers investigation or an explicit unclaimed limitation, not a weakened score definition.

## Copyable planning prompt

```text
Plan L05 — Tests and experiments only. This is an interview and planning session; do not implement code, delete artifacts, install tools, provision resources, or run a mutating workload. Writing agreed planning/glossary documents is permitted when the host mode allows it. Ask before expanding the topic.

Repository:
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission

Read:
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/README.md
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/rubric-map.md
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/evidence-guide.md
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/local/L05-tests-experiments.md

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

