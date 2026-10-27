# Rubric map: mini coursework and LLM

Source: [Coursework Tracking (Public).xlsx](<../../rubic-check/Coursework Tracking (Public).xlsx>), inspected 2026-10-26. The labels below translate/summarize the requirements; the workbook remains authoritative. Read its merged headings and proof column together with each row. Tutorials/examples are not permission to silently substitute a different capability.

- **Mnn** = row nn of `rubic (mini-coursework)`, scored E2:E46; **45 rows, 100 points**.
- **Enn** = row nn of `Sheet3` (LLM), scored E3:E62; **60 rows, 100 points**.
- Excluded: `rubic final-coursework (final -` (classic ML final). Do not import its training-platform obligations into the LLM scope.
- `Sheet3!A2` adds README/domain/deployable-unit diagram/structure/docstring guidance but E2 is blank. Address it through L07 without inventing points.
- Novel ideas are inside the totals: M45–M46 = 10 points; E61–E62 = 4. Without them the ceilings are 90 and 96, respectively.
- The workbook has no separate mandatory/optional flags. M30 explicitly permits **bronze → gold only**. Preserve named required capabilities unless the owner agrees to the score consequence of a substitution or omission.

## How to use the columns

**Owner** is the topic responsible for preparing the behavior and evidence contract. **Proof environment** names where the actual result is accepted; G03 gathers live cloud proof and G04 checks final claims. This avoids interpreting an L06 manifest as completed live deployment.

**Pending** means not yet certified against the accepted v2 release. It does not deny useful historical work. Promote a row to **Demonstrated** only with its actual linked source/result and accepted screenshot/document. Use **Not claimed** only after an explicit decision, documenting the reason and lost points in that row. Do not assume a precise awarded score: the instructor grades the submission. A single screenshot can support multiple rows only where its content proves each requirement.

The only topic execution status board is in [README.md](README.md). Add proof paths/limitations to the row's claim cell as work progresses; do not create a duplicate topic tracker here. The topic briefs are linked from that board.

## Mini coursework — 100 points

| ID | Points | Plain-language goal | Owner | Planned proof | Proof environment | Claim |
|---|---:|---|---|---|---|---|
| M02 | 10 | Explain domain, deployment, repo structure/TOC and code documentation. | L07 | Truthful README linked to detailed docs; diagram with deployable units/data arrows; relevant module/class/function descriptions. | Local; final G04 review | Pending |
| M03 | 1 | Use Docker and Compose. | L02 | Real Compose startup and image-size before/after context required by shared proof heading. | Local | Pending |
| M04 | 1 | Optimize Dockerfile. | L02 | Applied Dockerfile method and native measured image sizes before/after. | Local | Pending |
| M05 | 2 | Generate offline skew. | L02 | Config, generated source and measured city/category distribution. | Local | Pending |
| M06 | 2 | Generate high-cardinality data. | L02 | Approximate distinct counts/ID distribution on generated data. | Local | Pending |
| M07 | 2 | Generate schema evolution. | L02 | Old/new source partitions and expected absent/null optional fields. | Local | Pending |
| M08 | 2 | Generate another offline problem. | L02 | Existing duplicate scenario/config and measured duplicate rates. | Local | Pending |
| M09 | 2 | Configure the offline generator. | L02 | Actual config and resulting volume/characteristics. | Local | Pending |
| M10 | 2 | Persist simulated sources before Bronze ingestion. | L02 | Source data location/format/count and later ingestion input. | Local | Pending |
| M11 | 2 | Generate streaming bursts. | L02 | Time-bucket event rates showing configured burst. | Local | Pending |
| M12 | 2 | Generate late-arriving events. | L02 | Event/arrival timestamps and measured lateness distribution. | Local | Pending |
| M13 | 2 | Generate another streaming problem. | L02 | Configured duplicates or existing alternative with measured rate. | Local | Pending |
| M14 | 2 | Configure the streaming generator. | L02 | Config and observed stream volume/burst/late/duplicate characteristics. | Local | Pending |
| M15 | 2 | Establish an unoptimized Spark baseline. | L02 | Original job results and Spark UI stages on the agreed dataset. | Local | Pending |
| M16 | 2 | Explain and handle skew in Spark. | L02 | UI problem observation, applied method and comparable before/after result. | Local | Pending |
| M17 | 2 | Explain and handle high cardinality in Spark. | L02 | Measured problem, implementation and comparison to baseline. | Local | Pending |
| M18 | 2 | Handle schema evolution in Spark. | L02 | Old/new schema processing, resulting fields and correctness checks. | Local | Pending |
| M19 | 2 | Handle the other offline problem in Spark. | L02 | Dedup or chosen handling code and original input/output counts. | Local | Pending |
| M20 | 2 | Integrate Spark into the data pipelines. | L02 | Successful Airflow task invoking actual Spark work and persisted output. | Local | Pending |
| M21 | 2 | Establish a Flink baseline. | L02 | Actual running job, workload and baseline outputs/UI. | Local | Pending |
| M22 | 2 | Explain and handle streaming bursts. | L02 | Flink UI/workload evidence and comparable processing result. | Local | Pending |
| M23 | 2 | Explain and handle late arrivals. | L02 | Event-time/watermark behavior and late-event result. | Local | Pending |
| M24 | 2 | Handle the other streaming problem. | L02 | Dedup or selected handling behavior with original counts/output. | Local | Pending |
| M25 | 2 | Process windows in Flink. | L02 | Relevant actual window-processing code plus matching window output. | Local | Pending |
| M26 | 2 | Optimize lakehouse storage. | L02 | Applied optimization code and before/after file/query measurements. | Local | Pending |
| M27 | 2 | Optimize warehouse storage/querying. | L02 | Applied indexing or existing method and comparable measurements. | Local | Pending |
| M28 | 2 | DP1 ingests raw sources to Bronze. | L02 | Airflow graph/grid with actual ingest task and output. | Local | Pending |
| M29 | 2 | DP1 validates data. | L02 | Airflow validation stage order, successful result and bad-input behavior. | Local | Pending |
| M30 | 2 | DP2 ingests Bronze into Silver/Gold or directly Gold. | L02 | Successful Airflow stages and actual target tables. | Local | Pending |
| M31 | 2 | DP2 validates transformed data. | L02 | Airflow task result and original validation output. | Local | Pending |
| M32 | 2 | DP3 computes the offline feature table. | L02 | Airflow feature stage and persisted customer-frequency feature output. | Local | Pending |
| M33 | 2 | DP3 validates the feature table. | L02 | Airflow stage order and real feature validation result. | Local | Pending |
| M34 | 2 | Link DP1 and tables in DataHub. | L02 | Native DataHub pipeline/table lineage for the actual run. | Local | Pending |
| M35 | 2 | Show DP1 validation and contract in DataHub. | L02 | Native entity assertions/contract matching ingested data. | Local | Pending |
| M36 | 2 | Link DP2 and tables in DataHub. | L02 | Native transformed-table/pipeline lineage. | Local | Pending |
| M37 | 2 | Show DP2 validation and contract in DataHub. | L02 | Native assertions/contract and corresponding validation output. | Local | Pending |
| M38 | 2 | Link DP3 and tables in DataHub. | L02 | Native feature-table/pipeline lineage. | Local | Pending |
| M39 | 2 | Show DP3 validation and contract in DataHub. | L02 | Native feature assertions/contract and validation output. | Local | Pending |
| M40 | 2 | Visualize tables across all zones. | L02 | DBeaver native schema/table views connected to actual stores. | Local | Pending |
| M41 | 1 | Implement SCD2 dimensions. | L02 | Actual valid_from_ts, valid_to_ts, is_current columns and historical/current records. | Local | Pending |
| M42 | 1 | Give feature tables event and creation timestamps. | L02 | Actual event_timestamp and created columns with sample records. | Local | Pending |
| M43 | 2 | Explain dimension/fact relationships. | L02 | Actual database relationships/queries and annotated DBeaver or equivalent export. | Local | Pending |
| M44 | 2 | Apply consistent layer/table names. | L02 | Native schema listing and documented dim_/fact_/feat_/raw_/stg_ or justified equivalents. | Local | Pending |
| M45 | 5 | Prove novel idea 1. | L02 | Reassess existing idea first; document additional technique, implementation and actual result. | Local | Pending |
| M46 | 5 | Prove novel idea 2. | L02 | Separate bounded idea and working result; distinguish its contribution from M45. | Local | Pending |

Mini points total: **100**. Airflow connections/variables should be reusable in Airflow, as required by A28. Detailed explanations and annotated screenshots belong under `docs/`, linked from the summary README (A40).

## LLM — 100 points

| ID | Points | Plain-language goal | Owner | Planned proof | Proof environment | Claim |
|---|---:|---|---|---|---|---|
| E03 | 2 | Deploy the LLM inference platform. | L06 | Running selected runtime and native deployment/health evidence, not YAML alone. | GCP G02/G03 | Pending |
| E04 | 2 | Configure a custom model server/model. | L06 | Actual selected model identity/config and successful generation. | GCP G02/G03 | Pending |
| E05 | 2 | Benchmark and optimize model serving. | L05 | Original matched baseline/optimized workload and measured change with limitations. | Local harness; GCP G03 result | Pending |
| E06 | 2 | Apply a global model config via the agent gateway. | L06 | Applied configuration plus actual agent request reaching the configured runtime. | GCP G02/G03 | Pending |
| E07 | 2 | Deploy the agent registry. | L06 | Native deployed registry UI and actual entries. | GCP G02/G03 | Pending |
| E08 | 2 | Run text → chunks → embeddings → Feast in Airflow. | L03 | Real successful RAG DAG, persisted/retrievable chunks/vectors and DataHub lineage. | Local integration; GCP G03 canonical run | Pending |
| E09 | 2 | Govern the RAG pipeline. | L03 | Actual DataHub lineage, validation and contracts for pipeline/entities. | Local integration; GCP G03 | Pending |
| E10 | 1 | Validate the feature/chunk API and provide health checks. | L04 | FastAPI/Pydantic tests and actual Feast user/chunk lookup; shared deployed agent/UI proof. | Local tests; GCP G03 | Pending |
| E11 | 1 | Use async in the feature/chunk API. | L04 | Actual async path and relevant concurrency/error behavior verification. | Local; shared GCP G03 agent proof | Pending |
| E12 | 2 | Deploy its MCP with Helm, rolling update and fallback. | L06 | Real MCP tool use, observed rollout and automatic fallback under an agreed failure. | GCP G03 | Pending |
| E13 | 2 | Replicate and autoscale the retrieval/feature agent. | L06 | Actual multiple ready replicas and observed KEDA response under measured load. | GCP G03 | Pending |
| E14 | 1 | Restrict the agent in a sandbox. | L06 | Applied policy and actual allowed/denied behavior, not namespace alone. | GCP G03 | Pending |
| E15 | 2 | Publish the retrieval/feature agent in the registry. | L06 | Registry entry tied to the running agent/tool revision and successful UI use. | GCP G02/G03 | Pending |
| E16 | 1 | Validate the real-time drift API and health checks. | L04 | FastAPI/Pydantic tests and actual baseline/current drift result. | Local tests; GCP G03 | Pending |
| E17 | 1 | Use async in the drift API. | L04 | Actual async path and relevant concurrency/error behavior verification. | Local; shared GCP G03 agent proof | Pending |
| E18 | 2 | Deploy drift MCP with Helm, rolling update and fallback. | L06 | Real drift MCP calls, observed rollout and agreed automatic fallback test. | GCP G03 | Pending |
| E19 | 2 | Replicate and autoscale the drift agent. | L06 | Multiple ready replicas and observed scaling under load. | GCP G03 | Pending |
| E20 | 1 | Restrict the drift agent in a sandbox. | L06 | Applied restrictions and actual allowed/denied behavior. | GCP G03 | Pending |
| E21 | 2 | Publish the drift agent in the registry. | L06 | Running agent entry plus actual chat/tool use. | GCP G02/G03 | Pending |
| E22 | 2 | Demonstrate feature lookup and drift through agents/MCP in a notebook. | L04 | Executed notebook with actual Feast feature lookup and drift interaction output. | Local where feasible; GCP G03 | Pending |
| E23 | 2 | Demonstrate Feast RAG through agents/MCP in a notebook. | L04 | Executed notebook using actual retrieved chunks and agent/MCP interaction. | Local where feasible; GCP G03 | Pending |
| E24 | 2 | Deploy a replicated/autoscaled coordinator for both agents. | L06 | Correct routing to both specialists, actual replicas and scaling behavior. | GCP G03 | Pending |
| E25 | 2 | Publish the coordinator in the registry. | L06 | Native registry entry, replicas and working coordinator chat UI. | GCP G02/G03 | Pending |
| E26 | 2 | Demonstrate warm-up/startup optimization and explain worker HA. | L05 | Original cold/warm startup and resource/cost comparison, worker-pool configuration and bounded HA explanation. | Local harness; GCP G03 | Pending |
| E27 | 1 | Test the Web API with coverage >90%. | L05 | Native API test/fixture/mock output and coverage with explicit real scope. | Local | Pending |
| E28 | 2 | Use equivalence partitions and boundary values. | L05 | Named parametrized partitions/boundaries and actual execution output. | Local | Pending |
| E29 | 2 | Achieve mutation score >80% on changed code. | L05 | Native mutation report, exact changed-code scope and excluded/surviving mutants. | Local | Pending |
| E30 | 2 | Use property-based idempotency testing. | L05 | Meaningful repeated-write/replay invariant and native Hypothesis execution. | Local | Pending |
| E31 | 2 | Load test the retrieval Web API using Locust HTML. | L05 | Original Locust HTML/CSV, throughput/latency/failures and workload/configuration. | Local rehearsal; GCP G03 final | Pending |
| E32 | 1 | Simulate data drift. | L02 | Actual baseline/current customer-frequency distributions and drift scenario. | Local | Pending |
| E33 | 1 | Configure the drift generator. | L02 | Generator configuration tied to generated data and measured drift. | Local | Pending |
| E34 | 2 | Produce a two-column ID/label table for feature joins. | L02 | Actual ID/label table and inspected feature join output. | Local | Pending |
| E35 | 2 | CI/CD the RAG pipeline. | L06 | Successful tests, image build and automatic deployment with downstream verification. | GCP G02/G03 | Pending |
| E36 | 2 | CI/CD the feature/chunk MCP and agent. | L06 | Pipeline stages and matching built/deployed MCP+agent identity. | GCP G02/G03 | Pending |
| E37 | 2 | CI/CD the drift MCP and agent. | L06 | Pipeline stages and matching built/deployed MCP+agent identity. | GCP G02/G03 | Pending |
| E38 | 2 | CI/CD the coordinator agent. | L06 | Test/build/automatic deploy output tied to running coordinator. | GCP G02/G03 | Pending |
| E39 | 2 | CI/CD the stream job writing offline features. | L06 | Full pipeline plus actual offline feature write result. | GCP G02/G03 | Pending |
| E40 | 2 | CI/CD the stream job writing online features. | L06 | Full pipeline plus actual online feature write/read result. | GCP G02/G03 | Pending |
| E41 | 2 | Route the metrics UI behind the gateway. | L06 | Actual metrics UI through the configured ingress/gateway route. | GCP G03 | Pending |
| E42 | 2 | Route the logs UI behind the gateway. | L06 | Actual logs UI through its route. | GCP G03 | Pending |
| E43 | 2 | Route the tracing UI behind the gateway. | L06 | Actual trace UI through its route and an observed trace. | GCP G03 | Pending |
| E44 | 2 | Route the agent chat UI behind the gateway. | L06 | Working agent chat through the route, not an evidence-only auth page. | GCP G03 | Pending |
| E45 | 2 | Route the registry UI behind the gateway. | L06 | Actual registry listing through its route. | GCP G03 | Pending |
| E46 | 2 | Authenticate and rate-limit the agent chat UI. | L06 | Username/password positive/negative cases, valid chat and separate rate-limit result. | Local contract; GCP G03 | Pending |
| E47 | 1 | Give the retrieval Web API a domain and HTTPS. | L06 | Real domain/certificate and successful API request over HTTPS. | GCP G03 | Pending |
| E48 | 1 | Provision GKE/cloud resources with Terraform. | L06 | Real apply, outputs, selected state and matching cloud resources. | GCP G01 | Pending |
| E49 | 1 | Configure/deploy a VM service with role-based Ansible. | L06 | Actual role execution and resulting VM service check; dry-run alone insufficient. | GCP G01/G02 | Pending |
| E50 | 1 | Observe API throughput, request counts and failures. | L06 | Sampled request metrics from known real traffic on native dashboard. | GCP G03 | Pending |
| E51 | 1 | Observe CPU, RAM, disk and network. | L06 | Actual host/container telemetry in Prometheus/Grafana or equivalent. | GCP G03 | Pending |
| E52 | 1 | Collect and display logs. | L06 | Actual relevant service log records linked to the workload. | GCP G03 | Pending |
| E53 | 1 | Collect and display traces. | L06 | Actual request/agent/tool trace and relevant spans. | GCP G03 | Pending |
| E54 | 2 | Observe required LLM telemetry. | L06 | Input/output/total tokens, generation RTT, TTFT and safety/PII frequency with actual samples. | GCP G03 | Pending |
| E55 | 2 | Observe agent/tool calls and failures. | L06 | Per-agent/per-tool counters and real failure accounting for the workload. | GCP G03 | Pending |
| E56 | 1 | Compare agents with different model configurations. | L05 | Two named agent arms, actual samples and evaluation dashboard. | GCP G03 | Pending |
| E57 | 1 | Compare different model versions on the inference platform. | L05 | Two named model versions, actual samples and comparison dashboard. | GCP G03 | Pending |
| E58 | 1 | Centralize secrets using Vault or a similar tool. | L06 | Actual centrally stored secret consumed by a workload and sanitized native proof. | Local integration; GCP G03 | Pending |
| E59 | 2 | Keep a clean repo and demonstrate a real design pattern. | L01 | Reviewed artifact/navigation cleanup plus explanation of an existing useful pattern in actual code. | Local; final G04 review | Pending |
| E60 | 1 | Explain five main classes. | L07 | Five actual central classes, responsibilities, interfaces and linked source. | Local; final G04 review | Pending |
| E61 | 2 | Prove novel idea 1. | L05 | Existing candidate assessed first; bounded additional technique and measured working result. | Local or GCP G03, decided in L05 | Pending |
| E62 | 2 | Prove novel idea 2. | L05 | Separate idea, implementation, original output and limitation. | Local or GCP G03, decided in L05 | Pending |

LLM points total: **100**. A35 defines CI/CD as **test + build + automatic deployment**. E46's basic username/password/rate-limit requirement does not impose a second mailbox. E58 allows Vault **or similar tools**; it does not itself require Raft/KMS, two operators or a special recovery folder. A60 requires detailed documents with explained screenshots under `docs/`, linked from the summary README.

## Prioritization and interpretation

Revalidate existing mini work before redesigning it. The LLM specialist agent groups alone cover 18 points (E10–E21); six CI/CD rows cover 12; gateway/auth/HTTPS cover 13. Terraform and Ansible cover one point each. Use these weights when discussing effort; do not automatically drop an easy one-point requirement or assume every two-point requirement has equal cost.

The inference and sandbox/substrate tutorials linked in the workbook should be inspected during L06/L05. A CPU-compatible runtime in the reference suggests an option, not guaranteed acceptance of every substitution. If a named requirement cannot be met, state the exact difference, seek instructor clarification where needed, or mark it Not claimed. A description of future improvements does not earn a demonstrated row.

At G04 report: demonstrated potential points by sheet; pending points with reasons; explicitly unclaimed points; evidence links. All rows start Pending in this pack because an accepted v2 release has not yet been produced. Do not publish a “0 coursework score” or “200 achieved” claim from this initialization.
