# 13 — Coordinator, Inference Routing, and Telemetry

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Task 5 chat facade, deterministic routing/experiments, observed inference adapter, strict token budgeting, safe timeout abstention, and correlated redacted telemetry.

**Architecture:** `POST /v1/chat` validates the locked chat contract, chooses the explicit/automatic route and one of three coordinator A2A destinations, and uses the facade's only outbound adapter through agentgateway. The dependency deadline is exactly 22 s, with one jittered retry only for an idempotent connection failure. Typed timeout results become recorded failed tool calls plus grounded abstention; they never cross-route or fabricate data.

**Tech Stack:** Python 3.12, uv, FastAPI, Pydantic v2, the pinned Qwen tokenizer, OpenTelemetry, Langfuse port, agentgateway A2A adapter, pytest.

## Metadata

| Field | Locked value |
|---|---|
| Phase | Local/static implementation Topic 13 |
| Source task | `tmp/edai2-plan/04.2_llm_design.md` Task 5 coordinator/inference portion |
| Sheet3 support | `Sheet3!E24:E26`, `Sheet3!E50`, `Sheet3!E54:E57` |
| Predecessor Completion Records | `tmp/edai2-plan/execution-v1/local/11-retrieval-api-mcp-safety.md`; `tmp/edai2-plan/execution-v1/local/12-section03-loader-drift-api-mcp.md`, both `Complete` |
| Blocked successor | `tmp/edai2-plan/execution-v1/local/14-agent-security-registry-notebooks.md` |
| Runtime ownership | Local uv test/API session only |
| Class | Local/static; no GCP mutation |

## Locked planning basis

Read `C:\Users\oou1hc\.codex\RTK.md`. Locked hashes: `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`, `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`, and rubric `tmp/rubic-check/Coursework Tracking (Public).xlsx` `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.

## Global constraints

Use current branch, serial execution, `apply_patch`, and `rtk` prefixes. No stage/commit/worktree/GCP/Docker auto-prune or stop. `rtk uv run` is developer mode; `rtk make` is operator mode. Topic 08 owns the baseline dependencies and lockfile: run `rtk uv lock --check`, and treat a missing prerequisite dependency as a `Partial` predecessor defect rather than editing `pyproject.toml` or `uv.lock`. One bounded repair retry, then `Partial`; this is separate from the one connection retry permitted by the runtime contract.

## Read-only current-state refresh

- [ ] Run `rtk git status --short --branch`. Expected: branch and unrelated changes captured.
- [ ] Run `rtk proxy certutil -hashfile tmp/edai2-plan/03_data_generator_improvement.md SHA256`. Expected: output contains `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`.
- [ ] Run `rtk proxy certutil -hashfile tmp/edai2-plan/04.2_llm_design.md SHA256`. Expected: output contains `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`.
- [ ] Run `rtk proxy certutil -hashfile "tmp/rubic-check/Coursework Tracking (Public).xlsx" SHA256`. Expected: output contains `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- [ ] Run `rtk proxy powershell -NoProfile -Command "Select-String -Path tmp/edai2-plan/execution-v1/local/11-retrieval-api-mcp-safety.md,tmp/edai2-plan/execution-v1/local/12-section03-loader-drift-api-mcp.md -Pattern '^Status: Complete|\| Status \| Complete \|'"`. Expected: two completed predecessor records.
- [ ] Run `rtk uv lock --check`. Expected: exit 0 with the Topic 08-owned baseline lockfile unchanged.
- [ ] Run `rtk git diff --check`. Expected: exit 0.

## Scope and non-goals

In scope: chat schemas/API, observed inference/A2A adapters, routing Strategy, independent deterministic experiments, 3968/128 budgets, whole-turn/chunk dropping, timeout tool-call recording, citations/tool calls/versions, telemetry/redaction, unit tests.

Non-goals: SandboxAgent/registry manifests and notebooks (Topic 14), evaluation execution (Topic 15), platform manifests, live agent/model calls, charts, GCP, and screenshots.

## Exact file map

| Action | Exact path | Responsibility |
|---|---|---|
| Modify | `src/vina_bim_shop/llm/inference.py` | Complete the Topic 08 `ObservedInferenceClient` scaffold with budgets, deadline/retry, and typed timeout results |
| Modify | `src/vina_bim_shop/llm/routing.py` | Complete the Topic 08 scaffold with route handling and independent stable experiment assignment |
| Modify | `src/vina_bim_shop/llm/coordinator.py` | Complete the Topic 08 `CommerceAgentCoordinator` scaffold with grounding/tool calls/abstention |
| Modify | `src/vina_bim_shop/llm/telemetry.py` | Complete the Topic 08 scaffold with redacted OTel/Langfuse attributes and dropped-content counters |
| Modify | `src/vina_bim_shop/llm/adapters/llmd.py` | Complete the Topic 08 observed private inference port |
| Modify | `src/vina_bim_shop/llm/adapters/kagent.py` | Complete the Topic 08 facade-only A2A adapter for three destinations |
| Modify | `src/vina_bim_shop/llm/api/chat.py` | Complete the Topic 08 FastAPI scaffold with the exact chat schema, probes, and metrics |
| Modify | `src/vina_bim_shop/llm/safety.py` | Add Topic 13-owned prompt-injection, unsupported-claim, redaction, rejection, and abstention policy without weakening Topic 11 retrieval integrity |
| Modify | `configs/llm/models.yaml` | Pin model/tokenizer IDs, 4096 context, 3968 input, 128 output, concurrency 1 |
| Modify | `configs/llm/routing.yaml` | Set salts, 90:10 assignment, destinations, and promoted alias |
| Create | `tests/unit/llm/test_inference.py` | Budgets, timeout and telemetry tests |
| Create | `tests/unit/llm/test_coordinator.py` | Routes, citations/tool calls, experiments, negative dependency graph |
| Modify | `tests/unit/llm/test_safety.py` | Preserve Topic 11 retrieval cases and add Topic 13 prompt-injection/unsupported-claim/redaction/rejection/abstention cases |
| Modify | `tests/contract/llm/test_api_contracts.py` | Add byte-faithful chat request/response/error assertions to the Topic 08 shared contract scaffold |
| Create | `tests/fixtures/llm/chat_smoke_request.json` | Exact local curl request; no inline shell JSON |

## Interfaces, data flow, and failure modes

The public Pydantic contract is byte-faithful to locked source lines 302–425:

```python
class ChatRequest(BaseModel):
    session_id: UUID
    message: Annotated[str, Field(min_length=1, max_length=4000)]
    route: Literal["auto", "support", "drift"] = "auto"

class ChatResponse(BaseModel):
    request_id: UUID
    route: Literal["support", "drift", "abstain"]
    answer: str
    claims: list[GroundedClaim]
    agent_name: str
    agent_version: str
    model_version: str
    index_version: str | None
    tool_calls: list[ToolCallRecord]
    safety_action: Literal["allow", "redact", "reject", "abstain"]
```

There is no public messages array, route hint, experiment-eligibility flag, runtime-destination field, or separate public citation list. Experiment assignment remains internal and `GroundedClaim` carries grounding.

Destinations are exactly `coordinator-v1-primary`, `coordinator-v2-primary`, and `coordinator-v1-comparison`. No `v2-comparison`.

Input budget is exactly 3968 tokens and output budget 128 within context 4096. Count tokens with the tokenizer pinned for Qwen after rendering the complete chat template; a tiktoken approximation is forbidden. Reduction removes the oldest complete history groups atomically, then removes complete retrieval chunks ordered deterministically by `(score, chunk_id)`; it never slices content. If fixed system/current-user content alone exceeds 3968, return `422` with `ApiError.code=context_too_large`. Redacted telemetry records dropped group/chunk counts, token totals and hashes, never content.

Agent experiment uses locked salt `agent_exp_v1` and stable UUID hash with 90:10 `v1-primary|v2-primary`. Model experiment uses independent salt `model_exp_v1` and 90:10 `v1-primary|v1-comparison`. Ordinary sessions use the promoted alias. The facade allowlist contains only these three A2A destinations.

A typed A2A/tool/model timeout at exactly 22 s is recorded as a failed tool call with duration/status and yields grounded abstention. Only an idempotent connection failure may receive one jittered retry; timeout, validation, safety, and model-response failures are never retried. The coordinator never invokes another route, specialist, MCP, model, Feast, or database directly.

## Ordered test-first execution

- [ ] Add red tests and run `rtk uv run pytest tests/unit/llm/test_inference.py tests/unit/llm/test_coordinator.py tests/unit/llm/test_safety.py tests/contract/llm/test_api_contracts.py -q`. Expected: nonzero for missing Task 5 implementation; cases cover byte-faithful schemas, routes, claims, safety actions, exact 22 s deadline, retry classification, destinations, salts, Qwen rendered-template token counts, 3968/128 boundaries, whole-group/chunk dropping, `ApiError.code=context_too_large`, and redaction.
- [ ] Implement budgets/inference/telemetry, then run `rtk uv run pytest tests/unit/llm/test_inference.py -q`. Expected: exit 0; the pinned Qwen tokenizer counts the fully rendered chat template, boundary 3968 is accepted, 3969 is reduced or returns `context_too_large`, output is capped at 128, and the exact 22 s timeout is typed.
- [ ] Implement routing/coordinator/chat API, then run `rtk uv run pytest tests/unit/llm/test_coordinator.py tests/unit/llm/test_safety.py -q`. Expected: exit 0; exact destinations/salts/90:10 assignments and no cross-route fallback.
- [ ] Run `rtk uv run crosshair check src/vina_bim_shop/llm/routing.py --analysis_kind=PEP316 --per_condition_timeout=5 --max_uninteresting_iterations=64`. Expected: exit 0 with stable deterministic assignment and no counterexample.
- [ ] Start the owned monitor hidden with `rtk powershell -NoProfile -Command '$d="tmp/edai2-local/topic13"; New-Item -ItemType Directory -Force -Path $d | Out-Null; $p=Start-Process -FilePath "rtk" -ArgumentList @("uv","run","uvicorn","vina_bim_shop.llm.api.chat:app","--host","127.0.0.1","--port","8083") -WindowStyle Hidden -PassThru -RedirectStandardOutput "$d/chat.stdout.log" -RedirectStandardError "$d/chat.stderr.log"; Set-Content -LiteralPath "$d/chat.pid" -Value $p.Id -NoNewline'`, then wait with `rtk powershell -NoProfile -Command '$ok=$false; 1..40 | ForEach-Object { & rtk curl.exe --fail-with-body -sS http://127.0.0.1:8083/healthz *> $null; if ($LASTEXITCODE -eq 0) { $ok=$true; break }; Start-Sleep -Milliseconds 250 }; if (-not $ok) { Write-Error "chat monitor did not become healthy"; exit 1 }'`, then run `rtk powershell -NoProfile -Command '$status=& rtk curl.exe --fail-with-body -sS -o tmp/edai2-local/topic13/chat-response.json -w "%{http_code}" -X POST http://127.0.0.1:8083/v1/chat -H "Content-Type: application/json" --data-binary "@tests/fixtures/llm/chat_smoke_request.json"; Set-Content -LiteralPath tmp/edai2-local/topic13/chat-status.txt -Value $status -NoNewline; if ($status -ne "200") { exit 1 }; $body=Get-Content -Raw -LiteralPath tmp/edai2-local/topic13/chat-response.json | ConvertFrom-Json; foreach ($field in "request_id","route","answer","claims","agent_name","agent_version","model_version","tool_calls","safety_action") { if ($null -eq $body.$field) { Write-Error "missing ChatResponse field $field"; exit 1 } }'`. Expected: HTTP 200 and the locked `ChatResponse` fields, with a typed grounded response if the A2A fake is configured or recorded dependency timeout plus abstention; never a fabricated answer or alternate route. If any command fails after the PID is written, run the following PID cleanup checkbox before returning from Topic 13.
- [ ] Stop and verify only the recorded monitor with `rtk powershell -NoProfile -Command '$monitorPid=[int](Get-Content -LiteralPath "tmp/edai2-local/topic13/chat.pid"); Stop-Process -Id $monitorPid; Wait-Process -Id $monitorPid -ErrorAction SilentlyContinue; if (Get-Process -Id $monitorPid -ErrorAction SilentlyContinue) { Write-Error "owned chat monitor still running"; exit 1 }'`, then run `rtk uv run pytest tests/unit/llm/test_inference.py tests/unit/llm/test_coordinator.py tests/unit/llm/test_safety.py tests/contract/llm/test_api_contracts.py -q` and `rtk git diff --check`. Expected: both checks exit 0 and the exact recorded PID is absent.

## Evidence, cleanup, rubric, and DoD

Hash local test/CrossHair reports plus the exact fixture response and retain `tmp/edai2-local/topic13/chat.pid`, `chat.stdout.log`, `chat.stderr.log`, and `chat-response.json`. No screenshots or model-performance claims are owned. Stop and verify only the recorded Topic 13 uvicorn PID; release no cloud runtime.

| Sheet3 cell | Local proof | Deferred proof |
|---|---|---|
| `Sheet3!E24:E26` | routing/budget/timeout/telemetry tests | deployed agent/model scaling |
| `Sheet3!E50` | facade-only A2A dependency graph | gateway negative matrix |
| `Sheet3!E54:E57` | trace attributes and independent experiment assignments | live traces/A-B results |

## Definition of Done

Exact schemas, budgets, assignments, destinations, timeout abstention, citations/tool calls, facade-only adapter, telemetry and focused tests pass; no live claims; Topic 14 can bind resources to the three destinations.

## Completion Record

| Field | Execution value |
|---|---|
| Status | Partial — execution stopped before scoped implementation because the locked Qwen tokenizer is absent from the local cache and local-only resolution is forbidden from downloading it. |
| Current branch/status | Started clean on `## feature/implement-edai2...origin/feature/implement-edai2`; final status is `## feature/implement-edai2...origin/feature/implement-edai2` plus ` M tmp/edai2-plan/execution-v1/local/13-coordinator-inference-routing-telemetry.md`. No index entries were staged or unstaged. |
| Affected files | Modified only this Completion Record. No Topic 13 production/config/test/fixture file was changed. |
| Commands and exit codes | `rtk git status --short --branch`, all three locked-input `certutil` SHA-256 checks, predecessor Completion Record check, `rtk uv lock --check`, and `rtk git diff --check` exited `0` before edits. The combined preflight's final PowerShell `Get-FileHash` call exited `1` because that cmdlet is unavailable in this host, after it had already written the index listing; the prescribed `rtk proxy certutil -hashfile tmp/edai2-local/topic13/git-ls-files-before.txt SHA256` retry exited `0`. The one permitted remaining tokenizer gate, `rtk uv run python -X utf8 -c "from transformers import AutoTokenizer; t=AutoTokenizer.from_pretrained('Qwen/Qwen2.5-1.5B-Instruct',revision='989aa7980e4cf806f80c7fef2b1adb7bc71aa306',local_files_only=True); print(type(t).__name__, t.name_or_path)"`, exited `1`: `LocalEntryNotFoundError`/`OSError` reports no cached files and disabled outgoing traffic. Final `fc /b` index comparison, `rtk uv lock --check`, `rtk git diff --check`, and `rtk git diff --cached --exit-code` exited `0`. No red/green tests, CrossHair, or local smoke were run because the exact-Qwen-tokenizer prerequisite failed before test creation. |
| Evidence hashes | Locked inputs: Section 03 `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`; master plan `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`; workbook `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`. Pre/post index listings `tmp/edai2-local/topic13/git-ls-files-before.txt` and `git-ls-files-after.txt` are byte-for-byte identical (`fc /b` exit `0`) and both SHA-256 `60244bd7409ea7d4f72c126b9422a34f853bc235e5defa0946939f35033ea775`. |
| Screenshot QA | Not captured; no screenshot was manufactured. |
| Cleanup/runtime release | No Uvicorn monitor, model, A2A endpoint, GCP, GKE, Kind, Docker, database, token, or lease was started or acquired. |
| Limitations | The exact 3968-token rendered-Qwen-template requirement cannot be implemented or tested without the locked local tokenizer assets. A tiktoken approximation, network download, dependency/lockfile change, live model call, and fabricated evidence are prohibited. Consequently routing, telemetry, A2A adapter, API, safety, and test changes are intentionally absent. |
| Handoff | Restore the exact pinned Qwen tokenizer revision to the approved local cache, then restart Topic 13 from its preflight and test-first steps. Topic 14 remains blocked; do not bind resources to the three destinations from this Partial record. |
