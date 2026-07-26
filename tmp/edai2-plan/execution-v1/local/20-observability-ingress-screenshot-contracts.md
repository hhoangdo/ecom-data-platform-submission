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
| Sheet3 support | `Sheet3!E41:E55` |
| Predecessor Completion Record | `tmp/edai2-plan/execution-v1/local/19-workload-charts-streaming-keda-experiments.md` must be `Complete` |
| Blocked successor | `tmp/edai2-plan/execution-v1/local/21-kind-lean-preflight.md` |
| Runtime ownership | Local config/E2E-contract test session |
| Class | Local/static; no live ingress/certificate/browser capture |

## Locked planning basis

Read `C:\Users\oou1hc\.codex\RTK.md`; verify `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`, `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`, and rubric `tmp/rubic-check/Coursework Tracking (Public).xlsx` `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.

## Global constraints

Current branch/serial session, `apply_patch`, `rtk uv run` developer recipes, and `rtk make` operator recipes. Dependency changes are handed to Topic 15 for `rtk uv add` plus `rtk git diff -- pyproject.toml uv.lock` inspection. No stage/commit, Helm/kubectl/GCP/certificate/browser live capture, generic docs/diagrams/rubric-manifest files, or automatic Docker prune/stop. One retry then Partial.

## Read-only current-state refresh

- [ ] Run `rtk git status --short --branch`. Expected: branch/changes recorded.
- [ ] Run `rtk proxy certutil -hashfile tmp/edai2-plan/03_data_generator_improvement.md SHA256`. Expected: output contains `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`.
- [ ] Run `rtk proxy certutil -hashfile tmp/edai2-plan/04.2_llm_design.md SHA256`. Expected: output contains `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`.
- [ ] Run `rtk proxy certutil -hashfile "tmp/rubic-check/Coursework Tracking (Public).xlsx" SHA256`. Expected: output contains `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- [ ] Run `rtk proxy powershell -NoProfile -Command "Select-String -Path tmp/edai2-plan/execution-v1/local/19-workload-charts-streaming-keda-experiments.md -Pattern '^Status: Complete|\| Status \| Complete \|'"`. Expected: completed predecessor.
- [ ] Run `rtk git diff --check`. Expected: exit 0.

## Scope and non-goals

In scope: five alerts, Alloy log split, five dashboards, ingress/certificate resources, enable/disable CLI contract, screenshot capture schema/atomic validation, exact UI E2E contract and static tests.

Non-goals: Task 13 docs/diagrams/rubric verifier, live ingress/TLS/ACME, screenshot generation, GKE, dashboard import, alert firing, Jenkins evidence or final documentation.

## Exact file map

| Action | Exact path | Responsibility |
|---|---|---|
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
| Create | `scripts/qa/capture_edai2_evidence.py` | Screenshot temp/decode/atomic/schema capture |
| Create | `tests/e2e/llm/test_required_uis.py` | UI selectors, dimensions, source and rejection tests |
| Create | `tests/unit/llm/test_observability.py` | Labels, alerts, logs, traces, ingress static tests |

## Interfaces, data flow, and failure modes

Inputs are Topic 19's stable service/route/agent/tool/model/config/index/status/safety labels, rendered private services, controlled alert fixtures, and named UI capture requirements. Outputs are five alert rules, separate Alloy application/system pipelines, five dashboards, temporary TLS/auth/rate-limit ingress definitions, and an atomic screenshot manifest/capture validator. Topic 21 consumes static readiness only; GCP Topic 27 owns live ingress, alert and screenshot evidence.

Unknown/high-cardinality/PII label, merged log scope, broken W3C parent chain, missing alert transition, wrong threshold, second ingress controller, wrong 429 setting, absent auth/TLS context, stale/generic/terminal-only screenshot, PNG signature/decode/dimension/hash failure, non-atomic replacement, outside-root path, secret/PII detection, or live-case execution without a base URL fails closed and never creates a final evidence entry.

## Exact telemetry, alert, ingress, and capture contracts

Stable labels are exactly `service`, `route`, `agent`, `tool`, `model_version`, `agent_config`, `index_version`, `status`, `safety_action`, and `log_scope`. Customer IDs/messages, credentials and PII are forbidden labels.

Five alerts: API/tool failure >5%; retrieval p95 >750 ms; active-index freshness >24h; memory >90%; disk >80%. Each has controlled pending/firing test fixtures.

Alloy assigns `log_scope=application` to EDAI2 JSON app logs and `log_scope=system` to Kubernetes/node/controller logs; dashboard queries never merge them.

One W3C trace root continues NGINX/chat -> facade -> agentgateway -> coordinator. Model branch goes agentgateway -> llm-d. A2A branch goes agentgateway -> specialist -> agentgateway -> matching MCP -> retrieval/drift API -> Feast/PostgreSQL. A specialist model branch separately goes to agentgateway/llm-d. A new root at any hop fails.

Chat ingress annotations are exactly `limit-rps: "1"`, `limit-burst-multiplier: "5"`; controller ConfigMap has `limit-req-status-code: "429"`; evidence controller replicas exactly one; `limit-rate-after` absent.

Screenshots are exactly 1600x1000. Capture writes a sibling temporary file, verifies the eight-byte PNG signature, fully loads/decodes pixels, validates dimensions/content selector, then atomically replaces final. It rejects zero-byte, partial/truncated decode, wrong signature/format/dimensions, stale timestamp, generic home/login page, missing host/selector/context, terminal-only substitute, secret/PII, duplicate hash for distinct required views, outside-root path, or hash mismatch. Later QA uses `view_image` with `detail=original`.

## Ordered test-first execution

- [ ] Add red tests and run `rtk uv run pytest tests/unit/llm/test_observability.py tests/e2e/llm/test_required_uis.py -q`. Expected: nonzero until labels/alerts/ingress/capture contracts exist.
- [ ] Add alerts/Alloy/dashboards and run `rtk uv run pytest tests/unit/llm/test_observability.py -q -k "labels or alert or alloy or trace"`. Expected: exit 0 for exact labels, five thresholds, log split and trace continuity.
- [ ] Add ingress manifests and run `rtk helm template ingress-nginx ingress-nginx/ingress-nginx -f infra/helm/edai2/values/ingress-nginx.yaml --set controller.replicaCount=1`. Expected: exit 0; one controller and effective 429 ConfigMap.
- [ ] Run `rtk uv run pytest tests/unit/llm/test_observability.py -q -k "ingress"`. Expected: exit 0 for rate annotations, one-controller rule, no `limit-rate-after`, temporary-only hosts.
- [ ] Implement capture contract and run `rtk uv run pytest tests/e2e/llm/test_required_uis.py -q`. Expected: exit 0 locally with live URL cases explicitly skipped and all synthetic PNG rejection/atomic-replace cases passing.
- [ ] Run `rtk uv run pytest tests/unit/llm/test_inference.py tests/unit/llm/test_coordinator.py tests/unit/llm/test_observability.py tests/e2e/llm/test_required_uis.py -q`. Expected: exit 0; instrumentation labels align with source services and live cases do not fabricate screenshots.
- [ ] Run `rtk git diff --check`. Expected: exit 0.

## Evidence, screenshot ownership, cleanup, and rubric

Topic 20 owns capture schema and synthetic validation reports, not real screenshots. Later GCP evidence owner captures, uses original-resolution `view_image`, records visible selector/text/source/time/dimensions/hash, then deletes temporary ingress. Remove only synthetic temp PNGs; no live route/runtime.

| Sheet3 cell | Local proof | Deferred proof |
|---|---|---|
| `Sheet3!E41:E47` | ingress/auth/rate/TLS/UI capture contracts | contextual live views |
| `Sheet3!E48:E53` | dashboards/log split/trace continuity/alerts | runtime metrics/logs/traces |
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
