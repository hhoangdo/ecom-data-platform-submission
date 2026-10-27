# L03 — RAG knowledge lifecycle

[Roadmap and status board](../README.md) · [Rubric map](../rubric-map.md) · [Evidence guide](../evidence-guide.md)

## Purpose and examples

Make the assistant retrieve the actual definitions and operational knowledge needed to interpret the same data that the drift tool measures.

Examples: “What does customer order frequency count, and what time window does it use?” and “Which contract/runbook should I consult when this feature distribution changes?”

## Expected output

A small versioned metric/contract/runbook corpus; a real text → chunk → embedding → Feast pipeline; persisted queryable data and actual validation/lineage. The topic replaces the old unrelated policy-support story without rewriting the whole platform.

## Inspect before interviewing

All repository paths below are relative to `C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission`. Inspect the actual implementation, not only old plans.

- `src/vina_bim_shop/llm/indexing.py`, `retrieval.py`, `ports.py`, `adapters/`, `scripts/llm/build_index.py` and current document sources.
- `infra/feast/`, `infra/feast-registry/`, `infra/orchestration/airflow/`, `infra/governance/` and relevant RAG/index configuration.
- `evidence/04_2_llm_design/completion/28-rag-inference-benchmarks.md` and the actual 17-chunk historical smoke result. Recheck candidate persistence and the DataHub test-double/dry-run paths.
- L02's agreed customer-feature, ID and timestamp contracts.

**Rubric ownership:** E08–E09 (4 points). Contributes actual Feast user/chunk data to E10/E22/E23, but L04 owns API/agent behavior and G03 owns final cloud interaction proof.

**Reference reading:** under `C:/Users/hhoangdo/Documents/Personal Projects/GitHub Repo/RecSys-MLops`: `docs/submission/rubric-final-coursework-(final-llm)/rag.md`, `agent_pull_data.md`, and original `benchmark_proof/` retrieval results.. Follow its evidence discipline and stated limitations; do not copy unrelated infrastructure.

## Dependencies and boundary

Requires L01 and L02's data/feature contract. L04 consumes this topic's stable retrieval contract. A small real local integration must not require public HTTPS if loopback is an agreed local address. Deployment of the canonical index on GCP belongs to G02/G03.

## Decisions for the grill-with-docs interview

- Which metric definitions, data contracts, troubleshooting procedures and limitation notes belong in the smallest useful corpus? What replaces the old policy documents?
- How will document identity/version, chunk identity, embedding model and feature-store records remain traceable through re-indexing?
- How do user-feature lookup and chunk lookup use Feast and the actual backing stores? Which paths currently bypass them?
- What existing candidate persistence/validation/promotion mechanism is genuinely needed, and which ceremony can be removed?
- What should happen for missing/stale documents, empty retrieval and failed metadata emission? Choose observable behavior without inventing arbitrary quality thresholds.

These are interview questions, not preselected implementation requirements. Present the actual alternatives and score consequences, recommend a feasible answer, and wait for the owner's decisions.

## Acceptance criteria

- [ ] Corpus definitions agree with L02's data, including customer-frequency window/population/timestamps; example questions have source answers.
- [ ] Real Airflow tasks perform text ingestion, chunking, embedding and Feast persistence; the result survives the agreed process restart.
- [ ] Actual chunk/vector retrieval works through the agreed store; mocks or the old smoke index are not relabelled canonical.
- [ ] Real DataHub entities show the pipeline's lineage, validation and contract; an in-memory test adapter alone is insufficient.
- [ ] Repeat indexing has a meaningful agreed invariant and failure cases have original results. L05 owns formal property-test reporting.
- [ ] Hand L04 actual lookup IDs, schema, examples and failure semantics; hand G02 the reproducible corpus/index/configuration identities.
- [ ] Local proof and pending cloud execution are separately identified; unmeasured retrieval quality remains explicitly unclaimed.

## Simplifications and limitations to explain

Start with a small corpus tied to real implementation facts. Do not invent a large document approval workflow, unsupported “canonical 60-case” gate, or public-ingress requirement solely because v1 mentioned it. Any evaluation threshold must be justified and agreed in L05. Citations explain data definitions; they do not establish why a distribution changed.

## Copyable planning prompt

```text
Plan L03 — RAG knowledge lifecycle only. This is an interview and planning session; do not implement code, delete artifacts, install tools, provision resources, or run a mutating workload. Writing agreed planning/glossary documents is permitted when the host mode allows it. Ask before expanding the topic.

Repository:
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission

Read:
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/README.md
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/rubric-map.md
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/evidence-guide.md
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/local/L03-rag-knowledge-lifecycle.md

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

