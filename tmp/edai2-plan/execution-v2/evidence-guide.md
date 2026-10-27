# Evidence guide: prove behavior, then capture it

Read alongside the [roadmap and status board](README.md) and [row-level rubric map](rubric-map.md). This document defines evidence quality, not a second completion tracker.

## What counts

The chain is **claim → real workload/configuration → original result → native screenshot → limited explanation**. A screenshot helps a reviewer see a result; original logs and measurements let them inspect it. A checksum proves file identity, not that the claimed behavior happened.

Accept native service UIs, genuine terminal output, and tool-generated reports such as coverage, mutation, and Locust HTML. A custom HTML/PIL status page is an explanatory projection and cannot replace the original result or live service screen. Source-rendered architecture diagrams are appropriate documentation; keep them outside the runtime screenshot collection.

Do not claim success from empty panels, a configured but unexecuted pipeline, synthetic status cards, or 4xx/5xx requests. A negative authentication test should fail; label it as the negative case. Successful authenticated chat requires the expected successful status **and a valid response**. Treat rate limiting separately.

Show useful zero values truthfully: zero failures or zero safety interceptions can be correct if queries return actual samples for the run. “No data” is not an observed zero. If claiming interception works, execute an approved synthetic safety case and show its actual outcome.

## One accepted release, several purposeful runs

Keep a small human-readable evidence index in the final `docs/` submission section. For each claim record: rubric ID; final document/image; original result path; run ID/time and timezone; source revision; relevant image/model/configuration/dataset/index identity; workload; expected and observed result; limitation. Reuse one artifact across rows only when it actually proves each claim. Avoid another elaborate sealing or approval framework.

Baseline and optimized runs, model versions, agent configurations, and rollback tests intentionally differ. Name those differences. Failed experiments may be summarized honestly where relevant; obsolete debugging artifacts do not belong in the final evidence path. Never remove a baseline required to support an improvement claim simply to show only successful runs.

Capture locally, download cloud results, and verify readability **before teardown**. G04 checks originals and screenshot links before deleting superseded files. Keep enough configuration to reproduce a run; never store passwords/tokens in screenshots, logs, or public evidence.

## L01 capture rehearsal

1. Inspect the available browser and desktop capture tools. Confirm the agent can inspect the intended browser session; a configured Playwright server alone is not proof of authenticated GCP access.
2. Select one existing local service UI and one real terminal or DBeaver view. Start only the profile needed for the rehearsal after the topic plan is approved.
3. Execute a real small workload and capture the native result. Reopen the saved image and check that the result, run context, and text are readable.
4. Test a view requiring login with the owner's help where needed. Do not capture credentials. A GCP login/verification problem triggers the manual route; do not manufacture a replacement UI.
5. Record which shots agents can capture, which need an owner login, and which need full human capture. Add a small MCP only if the rehearsal demonstrates a concrete benefit.

The exact local startup command depends on the chosen service and must be written into L01's approved plan after inspecting current commands. This outline does not pretend the services are already running.

## Required shot families

| Family / rubric IDs | Real action and screen | Required visible result / reject when |
|---|---|---|
| Mini M03–M14 | Build images; run configured generators; show native image listing and data queries/report | Image-size comparison, configuration, skew/distinct/schema/duplicate and burst/lateness measurements; reject a static assertion without run output. |
| Mini M15–M20 | Run matched Spark baseline/optimized jobs; open Spark UI/history and Airflow | Job/stage identity, observed problem and measured change, completed orchestration; reject unrelated stages or unexplained different datasets. |
| Mini M21–M25 | Run Flink workload; inspect job, records/windows, burst/late/dedup behavior | Matching job/data and output comparison; include actual window-processing source; reject merely healthy TaskManagers. |
| Mini M26–M27 | Execute storage/query optimization and original comparison | Applied code/config plus file/query measurement before and after; reject “optimized” without a baseline. |
| Mini M28–M33; LLM E08 | Execute DP1/DP2/DP3 and RAG; open Airflow grid/graph and task logs | Successful real tasks, order and relevant parameters/output; reject stub/no-op DAGs. |
| Mini M34–M39; LLM E09 | Emit metadata from real runs; inspect DataHub entities and lineage | Actual upstream/downstream tables/pipeline, validation and contracts; reject only an ingestion-success message. |
| Mini M40–M44; LLM E32–E34 | Open real databases in DBeaver; run schema and feature/label queries | Zones, relationships, SCD2 fields, feature timestamps and ID/label join; reject an ERD drawing alone as database proof. |
| LLM E03–E07 | Inspect model service, applied model config, registry and original benchmark output | Running selected model/config, registry UI, endpoints and measured results; reject tutorial screenshots or manifest-only deployment claims. |
| LLM E10–E25 | Use both tools through agents/coordinator and run the two notebooks | Actual Feast user/chunk retrieval, drift result, UI response, registry entries, replicas, sandbox restriction test; reject direct HTTP alone as agent/MCP proof. |
| LLM E12–E26 | Apply rollout/load/startup experiments; inspect revisions, replicas, KEDA/substrate and results | Desired and ready counts, change over time, failure/fallback behavior and measured timing; reject a replica count as proof of autoscale or HA. |
| LLM E27–E31 | Run real API tests and Locust; open native output/reports | Coverage >90%, mutation >80% on changed code with stated scope, boundary partitions, property/idempotency results, Locust HTML; reject a custom success card. |
| LLM E35–E40 | Run each of six CI/CD pipelines; inspect stages and console | Tests, image build, immutable output, automatic deployment and resulting workload for that pipeline; reject tag-parity verification alone. |
| LLM E41–E47 | Visit metrics/logs/traces/chat/registry via gateway; test auth/rate limit and HTTPS retrieval API | Actual routed UI, valid positive/negative auth cases and rate limit, domain/certificate; reject an auth demonstration page as a working chat UI. |
| LLM E48–E49 | Run Terraform and role-based Ansible; inspect output and real target | Applied resources/configuration and successful target check; reject `plan`, `validate`, or `--check` as an executed deployment. |
| LLM E50–E55 | Generate known traffic; query metrics, logs and correlated traces; open native dashboards | Time range covering the run, sampled host/API/token/RTT/TTFT/safety/agent/tool values, trace/tool error examples; reject “No data.” |
| LLM E56–E57 | Execute both agent-config and model-version comparisons | Named arms, request counts, failures, quality/latency results and limitations; reject one arm or a static dashboard. |
| LLM E58 | Store/retrieve a secret through the agreed central system and demonstrate workload use | Native system/config and sanitized successful access; reject drawn “unsealed” status as a Vault UI. |
| Mini M02/M45–M46; LLM E59–E62 | Show actual code/classes/design pattern and measured novelty outputs | Explanation linked to implemented code and original output, diagrams labelled as documentation; reject decorative patterns or untested novelty claims. |

## Manual fallback: recipe required before each workload

The owning topic's detailed plan must replace these fields with exact values before execution; an unresolved recipe means **capture not ready**, not permission to invent a picture.

1. **Claim:** rubric IDs and the one behavior this image proves.
2. **Prerequisites:** services, account/login action, dataset/index/configuration and expected readiness.
3. **Run:** copyable PowerShell commands from the current repo, with explicit project/context where relevant. State expected output and how to stop after failure. Never include secret literals.
4. **Navigate:** precise service URL or desktop app, page/menu/tab, selected run/job/entity, query and time range.
5. **Check:** literal fields/results that must be visible; include the run/revision identity where useful. Do not equate visible panels with valid data.
6. **Capture:** exact image filename, image destination and whether a companion view is needed. Keep native original; inspect before accepting. Crop/redact only to remove irrelevant areas or secrets without changing results, and disclose any redaction.
7. **Preserve:** original logs/results and explanatory Markdown paragraph linked to this shot.
8. **Fallback:** if the agent cannot access/capture it, give these same steps to the owner and state exactly what is missing. If the underlying behavior fails, repair it or mark the row pending; a human screenshot cannot fix it.

When a human captures on Windows, run the prepared workload, navigate to the specified view, wait for the required result, use the normal screenshot tool (for example Win+Shift+S), save to the stated path, and reopen it at normal reading size. Avoid enormous whole-page exports with illegible text. Multiple focused native shots are preferable where one image cannot show the claim clearly.

## Reference reading

Reference root: `C:/Users/hhoangdo/Documents/Personal Projects/GitHub Repo/RecSys-MLops`.

- `docs/submission/rubric-final-coursework-(final-llm)/benchmark_proof/`: original workload/results and run metadata; normalized/reconstructed results are explicitly labelled.
- `docs/submission/rubric-final-coursework-(final-llm)/benchmark_ha.md`: honest limits of a small experiment.
- `docs/submission/rubric-final-coursework-(final-llm)/llm_inference_platform.md`: exact endpoints, workload, versions, comparisons and limitations.
- `docs/pngs/ai-observability-command-center-overview.png` and `llm_load_aware_benchmark_metrics.png`: native dashboard and terminal readability.

Adopt the evidence discipline rather than copying the reference's breadth or claiming its results as ours.
