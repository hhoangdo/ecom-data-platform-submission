# L02 — Mini-coursework pipelines

[Roadmap and status board](../README.md) · [Rubric map](../rubric-map.md) · [Evidence guide](../evidence-guide.md)

## Purpose and examples

Prove the existing e-commerce data platform actually generates the intended problems, handles them, and produces trustworthy feature data for the assistant.

Examples: “Where did duplicated and late orders go?” and “Which table defines customer order frequency, and can I trace it back to generated sources?”

## Expected output

A reproducible staged mini-coursework run with original measurements, native Spark/Flink/Airflow/DataHub/DBeaver evidence, and a documented customer-frequency feature/label contract for L03/L04.

## Inspect before interviewing

All repository paths below are relative to `C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission`. Inspect the actual implementation, not only old plans.

- `deliverables/01_data_generator.md`, `02_schema_design.md`, `03_data_generator_improvement.md`, `05_spark_batch.md`, `06_flink_streaming.md`, `08_airflow_gx_orchestration.md`, `09_datahub_governance.md`, `12_novel_ideas.md`, `13_mini_coursework_rubric_evidence.md`.
- `docker-compose.yml`, `compose/`, `Makefile`, `scripts/generate/`, `scripts/spark/`, `scripts/flink/`, `scripts/orchestration/`, `scripts/datahub/`, `scripts/analytics/`.
- `data/`, `evidence/01_data_generator/`, `evidence/02_schema_design/`, `evidence/final_integration/`, and Section 03 outputs. Inspect exact output identities before reusing or regenerating them.

**Rubric ownership:** M03–M46 (90 points) and E32–E34 (4 points). L07 owns the 10-point M02 documentation requirement. Capture instructions must use each row's actual proof requirements, not only unit tests.

**Reference reading:** under `C:/Users/hhoangdo/Documents/Personal Projects/GitHub Repo/RecSys-MLops`: `docs/submission/rubic-(mini-coursework)/` and the main reference README's data-flow explanation.. Follow its evidence discipline and stated limitations; do not copy unrelated infrastructure.

## Dependencies and boundary

Requires L01's classification and baseline. Finish the feature/schema contract before L03/L04 depend on it. Run service groups in stages on approximately 32 GiB RAM; GCP is not a prerequisite. L02 can reuse trustworthy artifacts after revalidation instead of regenerating everything.

## Decisions for the grill-with-docs interview

- What is the smallest dataset that still visibly demonstrates skew, cardinality, schema evolution, duplicates, bursts, lateness, and genuine optimizations?
- Which existing Bronze/Silver/Gold stages are worth retaining? The rubric permits Bronze → Gold; explain any change before removing a working Silver consumer.
- What exact population, window, timestamps, ID and label meanings define customer order frequency and the later drift comparison?
- Which existing two novelty candidates can be proved without adding a new subsystem? How will before/after runs remain comparable?
- How will Airflow connections/variables, DataHub lineage/contracts, and actual feature outputs be observed using the existing local stack?

These are interview questions, not preselected implementation requirements. Present the actual alternatives and score consequences, recommend a feasible answer, and wait for the owner's decisions.

## Acceptance criteria

- [ ] Each M03–M46 row has a reproduced or explicitly revalidated result, linked native proof, or an agreed Not claimed decision.
- [ ] Original data/config/seed identities accompany generator characteristics and Spark/Flink/storage comparisons; correctness is checked alongside performance.
- [ ] DP1/DP2/DP3 run real ingest/validate stages in Airflow; actual table lineage, validation and contracts are visible in DataHub.
- [ ] DBeaver or agreed equivalent connects to actual tables; SCD2 and feature timestamp behavior are inspectable, not diagram-only.
- [ ] Drift generator configuration and actual two-column ID/label output join correctly to features. Document event_timestamp and created semantics.
- [ ] The feature contract and sample queries handed to L03/L04 are explicit. Offline/online writer expectations are identified for L06.
- [ ] Two mini novelty explanations include working outputs and honest limits. No additional novelty services are presumed.

## Simplifications and limitations to explain

Preserve real Spark/Flink/Airflow/DataHub execution where the rubric names them; DuckDB parity is useful but not a replacement for those proofs. Small study-sized workloads limit generalization of timing results. Explain differences in processing paths instead of inventing separate standards of correctness. Cloud replicas/model runtime are outside this topic.

## Copyable planning prompt

```text
Plan L02 — Mini-coursework pipelines only. This is an interview and planning session; do not implement code, delete artifacts, install tools, provision resources, or run a mutating workload. Writing agreed planning/glossary documents is permitted when the host mode allows it. Ask before expanding the topic.

Repository:
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission

Read:
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/README.md
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/rubric-map.md
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/evidence-guide.md
C:/Users/hhoangdo/Documents/Personal Projects/FSDS/ecom-data-platform-submission/tmp/edai2-plan/execution-v2/local/L02-mini-coursework-pipelines.md

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

