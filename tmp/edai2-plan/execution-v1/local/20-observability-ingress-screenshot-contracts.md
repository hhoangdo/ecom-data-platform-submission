# 20 — Observability, Temporary Ingress, and Screenshot Contracts

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement only Task 10's local/static instrumentation, alerts, Alloy pipelines, dashboards, temporary ingress, screenshot capture schema, and E2E contract.

**Architecture:** Stable redacted telemetry flows through Alloy into separate application/system log scopes, Prometheus/Grafana, Tempo and Langfuse. Evidence ingress is one replica and temporary. Screenshot capture writes a validated temporary PNG, fully decodes it at 1600x1000, atomically replaces the target, and requires original-resolution visual inspection later.

**Tech Stack:** OpenTelemetry, Prometheus, Grafana, Alloy, Loki, Tempo, Langfuse, ingress-nginx, cert-manager, Playwright, Pillow/PNG validation, pytest.

## Metadata

| Field | Locked value |
|---|---|
| Phase | Local/static observability Topic 20 |
| Source task | `tmp/edai2-plan/04.2_llm_design.md` Task 10 |
| Sheet3 support | `Sheet3!E41:E48`, `Sheet3!E50:E55`; `Sheet3!E49` is permanently `Out of Scope` with zero credit |
| Predecessor Completion Record | `tmp/edai2-plan/execution-v1/local/19-workload-charts-streaming-keda-experiments.md` must be `Complete` |
| Blocked successor | `tmp/edai2-plan/execution-v1/local/21-kind-lean-preflight.md` |
| Runtime ownership | Local config/E2E-contract test session |
| Class | Local/static; no live ingress/certificate/browser capture |

## Locked planning basis

Read `C:\Users\oou1hc\.codex\RTK.md`; verify `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`, `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`, and rubric `tmp/rubic-check/Coursework Tracking (Public).xlsx` `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.

## Global constraints

Current branch/serial session, `apply_patch`, `rtk uv run` developer recipes, and `rtk make` operator recipes. Topic 08 owns baseline dependencies; Topic 20 alone adds the literal runtime capture decoder with `rtk uv add pillow` and inspects both dependency-file diffs. No other dependency addition is authorized. No stage/commit, Helm/kubectl/GCP/certificate/browser live capture, generic docs/diagrams/rubric-manifest files, or automatic Docker prune/stop. One retry then `Partial`.

## Read-only current-state refresh

- [ ] Run `rtk git status --short --branch`. Expected: branch/changes recorded.
- [ ] Run `rtk proxy certutil -hashfile tmp/edai2-plan/03_data_generator_improvement.md SHA256`. Expected: output contains `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`.
- [ ] Run `rtk proxy certutil -hashfile tmp/edai2-plan/04.2_llm_design.md SHA256`. Expected: output contains `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`.
- [ ] Run `rtk proxy certutil -hashfile "tmp/rubic-check/Coursework Tracking (Public).xlsx" SHA256`. Expected: output contains `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- [ ] Run `rtk proxy powershell -NoProfile -Command "Select-String -Path tmp/edai2-plan/execution-v1/local/19-workload-charts-streaming-keda-experiments.md -Pattern '^Status: Complete|\| Status \| Complete \|'"`. Expected: completed predecessor.
- [ ] Run `rtk uv lock --check`. Expected: exit 0 before the one Topic 20-owned Pillow addition.
- [ ] Run `rtk git diff --check`. Expected: exit 0.

## Scope and non-goals

In scope: five alerts, Alloy log split, five dashboards, ingress/certificate resources, enable/disable CLI contract, screenshot capture schema/atomic validation, exact UI E2E contract and static tests.

Non-goals: Task 13 docs/diagrams/rubric verifier, live ingress/TLS/ACME, screenshot generation, GKE, dashboard import, alert firing, Jenkins evidence or final documentation.

## Exact file map

| Action | Exact path | Responsibility |
|---|---|---|
| Modify | `pyproject.toml`, `uv.lock` | Add only literal `pillow` for full PNG decode validation and preserve all prior dependency/config ownership |
| Create | `infra/observability/prometheus/alerts.yaml` | Five exact alert rules |
| Create | `infra/observability/alloy/config.alloy` | Separate app/system logs and OTel routing |
| Create | `infra/observability/grafana/dashboards/http.json` | HTTP RPS/count/failure |
| Create | `infra/observability/grafana/dashboards/compute.json` | CPU/RAM/disk/network |
| Create | `infra/observability/grafana/dashboards/agents.json` | Agent/tool calls/failures |
| Create | `infra/observability/grafana/dashboards/llm.json` | Tokens/RTT/TTFT/safety/PII |
| Create | `infra/observability/grafana/dashboards/ab.json` | Agent/model experiment metrics |
| Create | `infra/ingress/edai2/ingresses.yaml` | Temporary sslip.io HTTPS/auth/rate routes |
| Create | `infra/ingress/edai2/certificate-issuer.yaml` | Staging then production ACME issuer contract |
| Create | `scripts/gke/configure_evidence_ingress.py` | Enable/disable/render/read-back contract |
| Create | `scripts/qa/capture_edai2_evidence.py` | Screenshot temp/decode/atomic/schema capture plus loopback-only private endpoint lifecycle |
| Create | `tests/e2e/llm/test_required_uis.py` | UI selectors, dimensions, source and rejection tests |
| Create | `tests/unit/llm/test_observability.py` | Labels, alerts, logs, traces, ingress static tests |

## Interfaces, data flow, and failure modes

Inputs are Topic 19's stable service/route/agent/tool/model/config/index/status/safety labels, rendered private services, controlled alert fixtures, named UI capture requirements, and the signed Topic 24 platform inventory. Outputs are five alert rules, separate Alloy application/system pipelines, five dashboards, temporary TLS/auth/rate-limit ingress definitions, and an atomic screenshot manifest/capture validator. For private UIs the capture CLI requires `--kubeconfig ABSOLUTE_KUBECONFIG_PATH --context EXACT_GKE_CONTEXT --platform-inventory SIGNED_PLATFORM_INVENTORY --private-endpoint-key APPROVED_ENDPOINT_KEY --loopback-only --tunnel-ttl BOUNDED_DURATION`. Each inventory entry must contain namespace, rendered ClusterIP Service name/UID, service port/target port, selector SHA-256, and nonempty Ready endpoint UID(s). Before capture, the helper reads the Service and EndpointSlices from the explicit context and rejects any absent, extra, stale, or mismatched field. It then opens `kubectl --kubeconfig ... --context ... port-forward --address 127.0.0.1` as a hidden child, writes its exact PID/stdout/stderr beneath `tmp/edai2-local/topic20/`, waits for a bounded loopback readiness probe, captures through that ephemeral tunnel, and uses a guaranteed `finally` path to terminate, wait for, and verify absence of that exact PID after success, timeout, browser failure, validation failure, or interruption. On Windows the child uses no-window process creation; it never opens a visible console. The evidence source records the stable endpoint key/service UID—not the ephemeral port—and the CLI never changes or reads the default context. Topic 21 consumes static readiness only; GCP Topic 27 owns live ingress, alert and screenshot evidence.

Unknown/high-cardinality/PII label, merged log scope, broken W3C parent chain, missing alert transition, wrong threshold, second ingress controller, wrong 429 setting, absent auth/TLS context, unknown/extra/stale private endpoint entry, namespace/service UID/port/selector/Ready-endpoint mismatch, non-loopback bind, missing/wrong kubeconfig or context, leaked port-forward process, stale/generic/terminal-only screenshot, PNG signature/decode/dimension/hash failure, non-atomic replacement, outside-root path, secret/PII detection, or live-case execution without an authorized route fails closed and never creates a final evidence entry.

## Exact telemetry, alert, ingress, and capture contracts

Stable labels are exactly `service`, `route`, `agent`, `tool`, `model_version`, `agent_config`, `index_version`, `status`, `safety_action`, and `log_scope`. Customer IDs/messages, credentials and PII are forbidden labels.

Five alerts: API/tool failure >5%; retrieval p95 >750 ms; active-index freshness >24h; memory >90%; disk >80%. Each has controlled pending/firing test fixtures.

Alloy assigns `log_scope=application` to EDAI2 JSON app logs and `log_scope=system` to Kubernetes/node/controller logs; dashboard queries never merge them.

One W3C trace root continues NGINX/chat -> facade -> agentgateway -> coordinator. Model branch goes agentgateway -> llm-d. A2A branch goes agentgateway -> specialist -> agentgateway -> matching MCP -> retrieval/drift API -> Feast/PostgreSQL. A specialist model branch separately goes to agentgateway/llm-d. A new root at any hop fails.

The ingress-nginx Helm chart version is literally `4.15.1`, matching Topic 18's release catalog. Chat ingress annotations are exactly `limit-rps: "1"`, `limit-burst-multiplier: "5"`; controller ConfigMap has `limit-req-status-code: "429"`; evidence controller replicas exactly one; `limit-rate-after` absent.

Every primary screenshot uses a fixed 1600x1000 viewport and is a full contextual viewport capture, never an element crop. Capture writes a sibling temporary file, verifies the eight-byte PNG signature, fully loads/decodes pixels with Pillow, validates dimensions/content anchors, then atomically replaces the final path. Each `ui_manifest.json` entry contains exactly `path`, `width`, `height`, `captured_at_utc`, `url_or_source`, `commit_or_revision`, `visible_selectors`, `linked_machine_evidence`, `sha256`, `proves`, and `does_not_prove`; `visible_selectors` and `linked_machine_evidence` are non-empty lists and the final two fields are non-empty bounded claims. Reject zero-byte, blank/near-uniform, partial/truncated decode, wrong signature/format/dimensions, clipped target/context, loading/spinner state, stale timestamp or revision, generic home page, login-only page, error page, missing host/anchor/title/context, terminal-only substitute, secret/credential/raw PII, duplicate hash for distinct required views, outside-root path, non-atomic replacement, or hash mismatch. Later QA inspects every accepted PNG through `view_image` with `detail=original`.

The only private endpoint keys are `agentregistry_ui`, `grafana_ui`, `airflow_web`, `datahub_frontend`, and `vault_status`. Each resolves through Topic 24's signed `platform_install.json`. A capture may use public temporary HTTPS only where the owning GCP topic explicitly creates and later removes that route; otherwise it must use the loopback-only interface above.

## Locked screenshot inventory and visible anchors

Locked source line 250 enumerates exactly the following 32 PNGs; do not infer an extra filename, rename one, or accept a substitute. `visible_selectors` records the successful Playwright role/text/test-id locators for the required anchors below, with the page title and surrounding application context also visible.

| Exact filename | Required visible anchors in the full 1600x1000 viewport |
|---|---|
| `airflow_rag_graph.png` | Airflow title, DAG ID `rag_index_pipeline`, Graph view, successful run state |
| `datahub_rag_lineage.png` | DataHub title, RAG dataset identity, Lineage view, upstream and downstream nodes |
| `kagent_retrieval_chat.png` | kagent title, resource `support`, logical identity `retrieval`, grounded answer and citation |
| `kagent_drift_chat.png` | kagent title, agent `drift`, population PSI/status, feature name `f_customer_order_frequency_7d` |
| `kagent_coordinator_chat.png` | kagent title, agent `coordinator`, selected specialist route, recorded tool call |
| `agentregistry_agents.png` | Agent Registry title and all three logical identities `retrieval`, `drift`, `coordinator` |
| `keda_scale.png` | KEDA/ScaledObject context, target name, Ready/Active conditions, observed replica transition |
| `grafana_http.png` | Grafana title, dashboard `EDAI2 HTTP`, RPS/count/failure panels and time range |
| `grafana_compute.png` | Grafana title, dashboard `EDAI2 Compute`, CPU/RAM/disk/network panels and time range |
| `grafana_llm.png` | Grafana title, dashboard `EDAI2 LLM`, token/RTT/TTFT/safety panels and time range |
| `grafana_agents.png` | Grafana title, dashboard `EDAI2 Agents`, agent/tool call and failure panels |
| `grafana_ab.png` | Grafana title, dashboard `EDAI2 A-B`, both arms, sample counts, quality/latency panels |
| `loki_app_logs.png` | Loki/Grafana Explore context, `log_scope=application`, service filter, redacted structured log rows |
| `tempo_trace.png` | Tempo trace context, trace ID, root chat span, gateway/coordinator/specialist/MCP dependency chain |
| `langfuse_trace.png` | Langfuse title, trace/session identity, model version, token/latency fields, redacted input/output state |
| `vault_status.png` | Vault title, initialized state, unsealed/healthy state, authentication context without secret values |
| `nginx_tls.png` | HTTPS origin, valid certificate/security indicator, ingress host, application title |
| `chat_auth_rate_limit.png` | Chat route context plus explicit authentication rejection `401` and rate-limit response `429` evidence |
| `coverage_and_api_fixtures.png` | Coverage report title, total at least 91%, API contract/fixture suite identity and passing state |
| `ep_bva.png` | EP/BVA report identity, boundary case labels, passing totals |
| `mutation.png` | Mutation report identity, classified status counts, strict score greater than 0.80 |
| `properties_crosshair.png` | Hypothesis and CrossHair report identities, bounded run details, no counterexample/passing state |
| `terraform_apply.png` | Terraform apply evidence title, successful terminal state, exact commit/revision and linked machine record; live proof is owned by the GCP Task 7 topic |
| `design_patterns.png` | Diagram title `EDAI2 Design Patterns`, pattern names, component relationships, readable legend |
| `whole_course_diagram.png` | Whole-course architecture title, Section 03/EDAI2 boundaries, data/control/evidence flows, readable legend |
| `locust_report.png` | Locust report title, host/scenario, request/failure totals, p95 and run duration |
| `jenkins_rag_index.png` | Jenkins job `edai2-rag-index`, build number, `SUCCESS`, common full commit SHA |
| `jenkins_retrieval_agent.png` | Jenkins job `edai2-retrieval-agent`, build number, `SUCCESS`, common full commit SHA |
| `jenkins_drift_agent.png` | Jenkins job `edai2-drift-agent`, build number, `SUCCESS`, common full commit SHA |
| `jenkins_coordinator.png` | Jenkins job `edai2-coordinator`, build number, `SUCCESS`, common full commit SHA |
| `jenkins_feast_offline.png` | Jenkins job `edai2-feast-offline-writer`, build number, `SUCCESS`, common full commit SHA |
| `jenkins_feast_online.png` | Jenkins job `edai2-feast-online-writer`, build number, `SUCCESS`, common full commit SHA |

Each filename maps one-to-one to a manifest entry and a non-empty machine-evidence link. `proves` is limited to what is visibly established by that capture and its linked record; `does_not_prove` names the deferred or non-visible claim, so a UI screenshot alone never proves Terraform mutation, deployment success, security enforcement, scaling, alert behavior, or benchmark validity.

## Ordered test-first execution

- [ ] Add the sole runtime decoder dependency with `rtk uv add pillow`, then run `rtk git diff -- pyproject.toml uv.lock` and `rtk uv lock --check`. Expected: only the literal Pillow requirement and its necessary lock resolution differ; any unrelated dependency/config churn is reverted before continuing.
- [ ] Add red tests and run `rtk uv run pytest tests/unit/llm/test_observability.py tests/e2e/llm/test_required_uis.py -q`. Expected: nonzero until labels/alerts/ingress/capture contracts, the exact 32-file inventory, manifest fields, anchors, and rejection cases exist.
- [ ] Add alerts/Alloy/dashboards and run `rtk uv run pytest tests/unit/llm/test_observability.py -q -k "labels or alert or alloy or trace"`. Expected: exit 0 for exact labels, five thresholds, log split and trace continuity.
- [ ] Add ingress manifests and run `rtk helm template ingress-nginx ingress-nginx/ingress-nginx --version 4.15.1 -f infra/helm/edai2/values/ingress-nginx.yaml --set controller.replicaCount=1`. Expected: exit 0; the command version equals Topic 18's literal release-catalog version `4.15.1`, with one controller and effective 429 ConfigMap.
- [ ] Run `rtk uv run pytest tests/unit/llm/test_observability.py -q -k "ingress"`. Expected: exit 0 for catalog/render version equality, rate annotations, one-controller rule, no `limit-rate-after`, and temporary-only hosts.
- [ ] Implement capture and private-endpoint lifecycle contracts and run `rtk uv run pytest tests/e2e/llm/test_required_uis.py -q`. Expected: exit 0 locally with live cases explicitly skipped; all 32 exact filenames and their required anchors are enumerated one-to-one, every manifest entry has exactly the eleven locked fields, full contextual 1600x1000 viewport capture is enforced, all synthetic rejection/atomic-replace cases pass, and missing flags, unknown endpoint/service UID, wrong context, non-loopback bind, and tunnel-leak simulations fail with exact-child cleanup asserted.
- [ ] Run `rtk uv run pytest tests/unit/llm/test_inference.py tests/unit/llm/test_coordinator.py tests/unit/llm/test_observability.py tests/e2e/llm/test_required_uis.py -q`. Expected: exit 0; instrumentation labels align with source services and live cases do not fabricate screenshots.
- [ ] Run `rtk git diff --check`. Expected: exit 0.

## Evidence, screenshot ownership, cleanup, and rubric

Topic 20 owns capture schema and synthetic validation reports, not real screenshots. Later GCP evidence owner captures, uses original-resolution `view_image`, records visible selector/text/source/time/dimensions/hash, then deletes temporary ingress. Remove only synthetic temp PNGs; no live route/runtime.

| Sheet3 cell | Local proof | Deferred proof |
|---|---|---|
| `Sheet3!E41:E47` | ingress/auth/rate/TLS/UI capture contracts | contextual live views |
| `Sheet3!E48` | Terraform screenshot filename/schema/anchor contract only | live Terraform apply proof is owned by GCP Topic 22 |
| `Sheet3!E49` | `Out of Scope`; zero credit and no artifact claim | none; it remains permanently out of scope |
| `Sheet3!E50:E53` | dashboards/log split/trace continuity/alerts | runtime metrics/logs/traces |
| `Sheet3!E54:E55` | Langfuse/experiment telemetry labels | live Langfuse/A-B dashboards |

## Definition of Done

Exact labels/alerts/log split/trace/ingress/capture rejection tests pass; screenshot contract is atomic and 1600x1000; no docs/rubric files or live resource is touched.

## Completion Record

| Field | Execution value |
|---|---|
| Status | Not started |
| Current branch/status | Record final `rtk git status --short --branch` |
| Affected files | Record Topic 20 exact paths |
| Commands and exit codes | Record static/unit/E2E/render checks |
| Evidence hashes | Record synthetic test/report SHA-256 |
| Screenshot QA | No live screenshots; later owner must use original-resolution view_image |
| Cleanup/runtime release | Record synthetic temp cleanup; no live ingress/runtime |
| Limitations | Record all deferred UI/TLS/alert/trace proof |
| Handoff | `tmp/edai2-plan/execution-v1/local/21-kind-lean-preflight.md` |
