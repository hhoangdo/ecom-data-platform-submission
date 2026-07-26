# 11 — Retrieval API, MCP, and Deterministic Grounding

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the local Task 3 retrieval domain, FastAPI endpoint, streamable-HTTP MCP tool, deterministic citation validation, probes, metrics, and focused tests.

**Architecture:** `POST /v1/retrieval/search` and MCP `search_ecommerce_knowledge` adapt the same async `FeastRetrievalService`. The service enforces a 700 ms dependency deadline, permits one jittered retry only for an idempotent connection failure, re-reads citation hashes, and never fabricates matches. Chat-level unsupported-claim and prompt-injection handling remains separate from route-level retrieval integrity.

**Tech Stack:** Python 3.12, uv, FastAPI, Pydantic v2, MCP streamable HTTP, Feast/pgvector port from Topic 10, OpenTelemetry, Prometheus, pytest, SHA-256.

## Metadata

| Field | Locked value |
|---|---|
| Phase | Local/static implementation Topic 11 |
| Source task | `tmp/edai2-plan/04.2_llm_design.md` Task 3 |
| Sheet3 support | `Sheet3!E10:E12`, `Sheet3!E62` |
| Predecessor Completion Record | `tmp/edai2-plan/execution-v1/local/10-rag-index-feast-airflow-datahub.md` must be `Complete` |
| Blocked successor | `tmp/edai2-plan/execution-v1/local/13-coordinator-inference-routing-telemetry.md` |
| Runtime ownership | One local uv/uvicorn session owned by the Topic 11 operator |
| Class | Local/static; no GCP mutation and no GKE rubric credit |

## Locked planning basis

- `C:\Users\oou1hc\.codex\RTK.md` must be read first; every shell command is prefixed with `rtk`.
- Section 03 plan SHA-256: `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`.
- EDAI2 master plan SHA-256: `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`.
- Rubric source `tmp/rubic-check/Coursework Tracking (Public).xlsx` SHA-256: `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- A hash mismatch stops execution and yields a truthful `Partial` Completion Record.

## Global constraints

- Stay on the current branch; use one serial implementation session.
- Use `apply_patch` for repository text edits.
- Do not stage, commit, create a branch/worktree, call GCP, or claim live deployment.
- Do not automatically prune or stop Docker resources.
- Developer recipes use `rtk uv run ...`; operator recipes use `rtk make ...`.
- Topic 08 owns the baseline dependencies and lockfile. Run `rtk uv lock --check`; if a required baseline dependency is absent, stop as `Partial` and report a Topic 08 predecessor defect instead of editing `pyproject.toml` or `uv.lock`.
- After one bounded retry, preserve the failure as `Partial`; do not broaden scope.

## Read-only current-state refresh

- [ ] Run `rtk git status --short --branch`. Expected: current branch and unrelated user changes are recorded before edits.
- [ ] Run `rtk proxy certutil -hashfile tmp/edai2-plan/03_data_generator_improvement.md SHA256`. Expected: output contains `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`.
- [ ] Run `rtk proxy certutil -hashfile tmp/edai2-plan/04.2_llm_design.md SHA256`. Expected: output contains `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`.
- [ ] Run `rtk proxy certutil -hashfile "tmp/rubic-check/Coursework Tracking (Public).xlsx" SHA256`. Expected: output contains `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- [ ] Run `rtk proxy powershell -NoProfile -Command "Select-String -Path tmp/edai2-plan/execution-v1/local/10-rag-index-feast-airflow-datahub.md -Pattern '^Status: Complete|\| Status \| Complete \|'"`. Expected: one Completion Record match.
- [ ] Run `rtk uv lock --check`. Expected: exit 0 with the Topic 08-owned baseline lockfile unchanged.
- [ ] Run `rtk git diff --check`. Expected: exit 0 before scoped edits; otherwise stop this topic as `Partial` without editing unrelated files.

## Scope and non-goals

In scope: typed retrieval contracts, async service, API/MCP adapters, route-local citation/hash validation, 700 ms timeout, stable errors, health/readiness/metrics, EP/BVA, unit and contract tests.

Non-goals: RAG ingestion/index construction, Section 03 ingestion, chat-level unsupported-claim/injection policy, Helm charts, SandboxAgents, live Feast/PostgreSQL, GKE, UI screenshots, and generic documentation.

## Exact file map

| Action | Exact path | Responsibility |
|---|---|---|
| Modify | `src/vina_bim_shop/llm/retrieval.py` | Complete the Topic 08 scaffold with `FeastRetrievalService`, query/filter rules, deadline/retry, and citation verification |
| Modify | `src/vina_bim_shop/llm/api/retrieval.py` | Complete the Topic 08 FastAPI scaffold with the route, probes, metrics, and error mapping |
| Modify | `src/vina_bim_shop/llm/mcp/retrieval.py` | Complete the Topic 08 scaffold with the exact `search_ecommerce_knowledge` MCP schema and adapter |
| Modify | `src/vina_bim_shop/llm/safety.py` | Complete retrieval-result hash/support validation; chat policy is added by Topic 13 |
| Create | `tests/unit/llm/test_retrieval.py` | EP/BVA, timeouts, deterministic results, metrics/probes |
| Create | `tests/unit/llm/test_safety.py` | Citation discriminator/hash/support validation |
| Modify | `tests/contract/llm/test_api_contracts.py` | Add retrieval OpenAPI request/response/error assertions to the Topic 08 shared contract scaffold |
| Modify | `tests/contract/llm/test_mcp_contracts.py` | Add retrieval MCP schema parity assertions to the Topic 08 shared contract scaffold |
| Create | `tests/fixtures/llm/retrieval_smoke_request.json` | Exact local curl request without inline shell JSON |
| Consume | `src/vina_bim_shop/llm/contracts.py`, `src/vina_bim_shop/llm/ports.py` | Topic 08-owned shared contracts and retrieval port; no edits here |

## Interfaces, data flow, and failure modes

The public Pydantic contract is byte-faithful to locked source lines 302–425:

```python
class SearchRequest(BaseModel):
    query: Annotated[str, Field(min_length=1, max_length=2000)]
    top_k: Annotated[int, Field(ge=1, le=8)] = 4
    category: KnowledgeCategory | None = None
    effective_at: UtcDateTime | None = None

class SearchMatch(BaseModel):
    content: str
    score: float
    citation: KnowledgeCitation

class SearchResponse(BaseModel):
    request_id: UUID
    index_version: str
    embedding_model: Literal["BAAI/bge-small-en-v1.5"]
    matches: list[SearchMatch]
    retrieval_ms: float
    abstained: bool
    reason: str | None
```

There are no public rank, direct document metadata, or request-effective-time fields; immutable document/version/chunk hashes remain inside `KnowledgeCitation`.

Flow: HTTP or MCP request -> validation -> async retrieval port -> 700 ms deadline -> at most one jittered retry for an idempotent connection failure -> effective-date/category filtering -> citation SHA re-read/support validation -> schema response -> metrics/trace. Timeouts, validation failures, and non-connection failures are never retried.

Error mapping is exact:

| Condition | HTTP/status contract |
|---|---|
| Invalid query, `top_k`, category, or timestamp | `422` validation error |
| Empty/no active index or hash-invalid active alias | `409 index_unavailable` |
| Feast/pgvector call exceeds 700 ms, or its one permitted connection retry fails | `503 dependency_timeout` |
| No matching policy row | 200 typed abstention with no fabricated match |
| Citation discriminator/hash mismatch | deterministic rejection before response |

Chat-level unsupported generated claims and injection handling are tested in Topic 13; Topic 11 validates retrieval artifacts, not model prose.

## Ordered test-first execution

- [ ] Add red EP/BVA cases and run `rtk uv run pytest tests/unit/llm/test_retrieval.py tests/unit/llm/test_safety.py tests/contract/llm/test_api_contracts.py tests/contract/llm/test_mcp_contracts.py -q`. Expected: nonzero because Task 3 implementation is absent, with failures covering `top_k` values 0, 1, 4, 8, and 9; query lengths 0, 1, 2000, and 2001; filters, timeout, citations, and empty index.
- [ ] Implement the four owned modules with `apply_patch`, then run `rtk uv run pytest tests/unit/llm/test_retrieval.py tests/unit/llm/test_safety.py -q`. Expected: exit 0; deadline is exactly 700 ms, only an idempotent connection failure receives one jittered retry, and tampered citations fail deterministically.
- [ ] Validate API/MCP parity with `rtk uv run pytest tests/contract/llm/test_api_contracts.py tests/contract/llm/test_mcp_contracts.py -q`. Expected: exit 0; both expose the same SearchRequest/SearchResponse/SearchMatch shapes and only the named MCP tool.
- [ ] Start the owned monitor hidden and persist ownership with `rtk powershell -NoProfile -Command '$d="tmp/edai2-local/topic11"; New-Item -ItemType Directory -Force -Path $d | Out-Null; $p=Start-Process -FilePath "rtk" -ArgumentList @("uv","run","uvicorn","vina_bim_shop.llm.api.retrieval:app","--host","127.0.0.1","--port","8081") -WindowStyle Hidden -PassThru -RedirectStandardOutput "$d/retrieval.stdout.log" -RedirectStandardError "$d/retrieval.stderr.log"; Set-Content -LiteralPath "$d/retrieval.pid" -Value $p.Id -NoNewline'`. Expected: the PID file names the live uvicorn process and no unrelated process is touched.
- [ ] Wait for the process health endpoint with `rtk powershell -NoProfile -Command '$ok=$false; 1..30 | ForEach-Object { & rtk curl.exe --fail-with-body -sS http://127.0.0.1:8081/healthz *> $null; if ($LASTEXITCODE -eq 0) { $ok=$true; break }; Start-Sleep -Milliseconds 250 }; if (-not $ok) { Write-Error "retrieval monitor did not become healthy"; exit 1 }'`, then run `rtk powershell -NoProfile -Command '$status=& rtk curl.exe -sS -o tmp/edai2-local/topic11/retrieval-response.json -w "%{http_code}" -X POST http://127.0.0.1:8081/v1/retrieval/search -H "Content-Type: application/json" --data-binary "@tests/fixtures/llm/retrieval_smoke_request.json"; Set-Content -LiteralPath tmp/edai2-local/topic11/retrieval-status.txt -Value $status -NoNewline; if (@("200","409") -notcontains $status) { exit 1 }'`. Expected: schema-valid `200` or exact `409 index_unavailable`; never fabricated matches.
- [ ] Probe with `rtk curl.exe --fail-with-body -sS http://127.0.0.1:8081/healthz`, then run `rtk powershell -NoProfile -Command '$status=& rtk curl.exe -sS -o tmp/edai2-local/topic11/ready-response.json -w "%{http_code}" http://127.0.0.1:8081/readyz; Set-Content -LiteralPath tmp/edai2-local/topic11/ready-status.txt -Value $status -NoNewline; if (@("200","503") -notcontains $status) { exit 1 }; $body=Get-Content -Raw -LiteralPath tmp/edai2-local/topic11/ready-response.json | ConvertFrom-Json; if ($status -eq "200" -and $body.status -ne "ready") { exit 2 }; if ($status -eq "503" -and $body.status -ne "not_ready") { exit 3 }'`, and `rtk curl.exe --fail-with-body -sS http://127.0.0.1:8081/metrics`. Expected: process health is independent of dependency readiness; readiness is schema-valid HTTP `200 ready` or `503 not_ready`; metrics include stable service/route/status labels. If any command after the PID file is written fails, execute the recorded-PID cleanup step before reporting `Partial`.
- [ ] Stop and verify only the recorded monitor with `rtk powershell -NoProfile -Command '$monitorPid=[int](Get-Content -LiteralPath "tmp/edai2-local/topic11/retrieval.pid"); Stop-Process -Id $monitorPid; Wait-Process -Id $monitorPid -ErrorAction SilentlyContinue; if (Get-Process -Id $monitorPid -ErrorAction SilentlyContinue) { Write-Error "owned retrieval monitor still running"; exit 1 }'`, then run `rtk uv run pytest tests/unit/llm/test_retrieval.py tests/unit/llm/test_safety.py tests/contract/llm/test_api_contracts.py tests/contract/llm/test_mcp_contracts.py -q` and `rtk git diff --check`. Expected: both checks exit 0 and the exact recorded PID is absent.

## Evidence, screenshot ownership, and cleanup

Topic 11 owns command transcripts and SHA-256 hashes for focused test reports plus `tmp/edai2-local/topic11/retrieval.pid`, `retrieval.stdout.log`, `retrieval.stderr.log`, `retrieval-response.json`, and `retrieval-status.txt`. It owns no screenshot. The later GCP evidence topic captures deployed API/MCP proof. Stop and verify only the recorded Topic 11 uvicorn PID; retain no temporary token, server, database, or cloud lease.

## Rubric traceability

| Sheet3 cell | Local proof | Deferred proof |
|---|---|---|
| `Sheet3!E10` | Pydantic/OpenAPI/probe tests | Deployed FastAPI capture |
| `Sheet3!E11` | Async 700 ms timeout and nonblocking tests | Runtime trace |
| `Sheet3!E12` | MCP schema parity and deterministic errors | Helm/RemoteMCPServer proof |
| `Sheet3!E62` | Route-level citation integrity tests | Evaluation evidence |

## Definition of Done

All owned tests pass; local smoke returns only valid data or exact errors; no chart/shared dependency file was edited; the branch is unchanged; `rtk git diff --check` is clean; successor 13 receives exact paths and hashes.

## Completion Record

| Field | Execution value |
|---|---|
| Status | Not started |
| Current branch/status | Record final `rtk git status --short --branch` output |
| Affected files | Record only Topic 11-owned exact paths |
| Commands and exit codes | Record every red test, green test, smoke, probe, and diff check |
| Evidence hashes | Record SHA-256 of non-secret local reports |
| Screenshot QA | Not captured locally; no screenshot claim |
| Cleanup/runtime release | Record owned uvicorn PID stop; no cloud runtime acquired |
| Limitations | Record missing live Feast/GKE evidence or bounded-retry failure |
| Handoff | `tmp/edai2-plan/execution-v1/local/13-coordinator-inference-routing-telemetry.md` |
