# RAG Source, Chunking, and Embeddings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the source/version parsing, deterministic token chunking, and pinned embedding half of EDAI2 Task 2, producing candidate-only inputs for Topic 10.

**Architecture:** Eight canonical Markdown files parse into exactly nine immutable document-version records. Each version is NFC-normalized and tokenized independently into deterministic 400-token/80-overlap chunks, then embedded with the pinned BGE revision into normalized finite 384-vectors. No active alias or storage promotion occurs.

**Tech Stack:** Python 3.12, Pydantic v2 contracts, Hugging Face `sentence-transformers`/`AutoTokenizer`, BAAI/bge-small-en-v1.5, SHA-256, RFC 8785/JCS canonical JSON, pytest, `uv`, `rtk`.

## Locked sources and execution policy

- Read `C:\Users\oou1hc\.codex\RTK.md`; every shell command begins with `rtk`.
- Section 03 source is `tmp/edai2-plan/03_data_generator_improvement.md`, SHA-256 `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`.
- EDAI2 source is `tmp/edai2-plan/04.2_llm_design.md`, SHA-256 `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`.
- Rubric source is `tmp/rubic-check/Coursework Tracking (Public).xlsx`, SHA-256 `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`.
- Work on the current branch in one serial session. Do not create a worktree or branch and do not stage, commit, push, or open a PR.
- Do not mutate GCP/Kubernetes, active indexes, PostgreSQL, Feast, Airflow, or DataHub. Do not prune Docker or stop unrelated containers.

## Metadata

| Field | Decision |
|---|---|
| Phase | 9 — trusted sources, chunks, and embeddings |
| Source tasks | EDAI2 Task 2 source/version/chunk/embed portion |
| Rubric contribution | Supporting evidence for `Sheet3!E8:E9` and `Sheet3!E61` |
| Prerequisites | Topic 08 Completion Record |
| Blocked successors | Topic 10 |
| Runtime ownership | Local RAG data operator; one serial session |
| Local/GCP class | Local deterministic implementation/tests; no GCP mutation |

## Global constraints

- Exact files are `returns.md`, `shipping.md`, `cancellation.md`, `payments.md`, `promotions.md`, `warranties.md`, `privacy.md`, and `marketplace_support.md`.
- Every file is UTF-8 without BOM, LF-only, and final-newline terminated.
- Every record uses this literal grammar; unknown/missing keys or free text outside a record fail parsing:

```text
---
document_id: returns-policy
category: returns
version: 1.0.0
effective_from: 2025-01-01T00:00:00Z
effective_to: null
---
# Returns policy
```
- Seven files contain one record and 300–700 English words. `returns.md` contains exactly two 150–350-word records separated only by `<!-- version-separator -->`, the same document/category, distinct SemVer values, adjacent non-overlapping intervals, and null end on current; total is exactly eight files and nine versions.
- Eligibility is `effective_from <= effective_at < effective_to`, with null end treated as infinity.
- Chunking uses Unicode NFC, pinned tokenizer with `add_special_tokens=False`, starts `0,320,640`, maximum 400 tokens, exact 80-token overlap when a successor exists, and never crosses version boundaries.
- `chunk_id` hashes JCS JSON fields `document_id`, `version`, `ordinal`, `token_start`, `token_end`, `content_sha256`, `tokenizer_revision`.
- Embedding model is `BAAI/bge-small-en-v1.5` revision `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`; moving `main` fallback is forbidden.
- Passage embedding uses canonical chunk text with no prefix. Query embedding uses exact prefix `Represent this sentence for searching relevant passages: `.
- `normalize_embeddings=True`; every vector is finite and length 384.

## Current-state refresh — read-only planning phase

```text
rtk git status --short --branch
rtk git branch --show-current
rtk rg -n "KnowledgeCategory|IndexBuildReport|EmbeddingPort|BAAI/bge-small-en-v1.5|tokenizer_revision" src/vina_bim_shop/llm configs/llm tests/unit/llm
rtk uv run pytest tests/unit/llm/test_indexing.py -q
```

Expected: the same branch and Topic 08 contract baseline are recorded; no source, vector store, alias, or service is mutated.

## Scope and non-goals

In scope: eight source files, exact parser grammar/word/version validation, canonical hashes, effective windows, token chunks, chunk IDs, pinned passage/query embedding behavior, candidate dry-run report, and unit tests. Non-goals: PostgreSQL/pgvector writes, Feast, Airflow, DataHub, active alias, ANN, retrieval API, 60-case Task 6/12 evaluation, or canonical evidence.

## Exact file map

| Action | Exact path | Responsibility |
|---|---|---|
| Create | `data/knowledge/ecommerce/returns.md` | Two adjacent effective-dated returns records separated by exact marker. |
| Create | `data/knowledge/ecommerce/shipping.md` | One canonical shipping record. |
| Create | `data/knowledge/ecommerce/cancellation.md` | One canonical cancellation record. |
| Create | `data/knowledge/ecommerce/payments.md` | One canonical payments record. |
| Create | `data/knowledge/ecommerce/promotions.md` | One canonical promotions record. |
| Create | `data/knowledge/ecommerce/warranties.md` | One canonical warranties record. |
| Create | `data/knowledge/ecommerce/privacy.md` | One canonical privacy record. |
| Create | `data/knowledge/ecommerce/marketplace_support.md` | One canonical marketplace-support record. |
| Modify | `configs/llm/models.yaml` | Pin model/tokenizer/revision, dimension, prefixes, and normalization. |
| Modify | `src/vina_bim_shop/llm/contracts.py` | Define source/version/chunk/build-report fields and exact counts. |
| Modify | `src/vina_bim_shop/llm/ports.py` | Define `EmbeddingPort` returning 384-vectors. |
| Modify | `src/vina_bim_shop/llm/indexing.py` | Implement parser, canonical hashes, version checks, chunking, embedding validation, and dry-run report. |
| Create | `scripts/llm/build_index.py` | Thin candidate/dry-run CLI over indexing code. |
| Create | `tests/unit/llm/test_indexing.py` | Test grammar, counts, hashes, windows, chunks, prefixes, revision, and vectors. |

## Interfaces and data flow

Canonical bytes → source SHA-256 → version records/body SHA-256 → per-version token windows → JCS `chunk_id` → passage embeddings → `IndexBuildReport(document_count=8, document_version_count=9, embedding_dimension=384)`. Query embedding is a separate adapter call and never reuses the passage text form.

## Failure modes

Fail on wrong inventory/category/filename, BOM/CRLF/missing final newline, malformed delimiter/front matter, unknown/missing key, invalid SemVer/RFC3339 UTC, duplicate `(document_id,version)`, returns gap/overlap, word-bound violation, cross-version chunk, non-400/80 window, unstable hash/ID/order, unpinned model/revision, passage prefix, missing query prefix, non-normalized/nonfinite/non-384 vector, network fallback to `main`, or alias/storage mutation.

## Ordered test-first execution tasks

- [ ] Add exact eight-file/nine-version grammar, encoding, word-bound, adjacency, and effective-boundary tests, then run `rtk uv run pytest tests/unit/llm/test_indexing.py -q`; expected FAIL because trusted sources and parser behavior are absent.
- [ ] Create the eight exact Markdown files and implement strict parsing/hashing/version validation, then run `rtk uv run pytest tests/unit/llm/test_indexing.py -q`; expected FAIL only on missing deterministic chunk/embedding behavior while inventory/version tests pass.
- [ ] Add 400/80/NFC/token-boundary/JCS-ID tests, then run `rtk uv run pytest tests/unit/llm/test_indexing.py -q`; expected FAIL until token windows start at `0,320,640`, stay inside each version, and retain the final nonempty window.
- [ ] Implement deterministic chunking, then run `rtk uv run pytest tests/unit/llm/test_indexing.py -q`; expected FAIL only on missing pinned embedding/prefix/vector validation.
- [ ] Add pinned revision, no-prefix passage, exact-prefix query, normalization, finite, and 384-d tests; implement the embedding adapter contract, then run `rtk uv run pytest tests/unit/llm/test_indexing.py -q`; expected PASS with deterministic ordered chunks/vectors and no storage/alias action.
- [ ] Run `rtk uv run python scripts/llm/build_index.py --mode candidate --index-version test_idx_001 --source-root data/knowledge/ecommerce --dry-run`; expected exit 0, exactly 8 documents and 9 versions, chunks at most 400 tokens with exact 80 overlap where a successor exists, finite normalized 384-vectors, candidate label `ci-bootstrap`, and no storage write or promotion.
- [ ] Run `rtk uv run pytest tests/unit/llm/test_indexing.py -q`; expected PASS with effective-date boundaries immediately before/at/after the returns transition and deterministic same-input report hashes.
- [ ] Run `rtk git diff --check`, `rtk git status --short --branch`, and `rtk git ls-files --stage`; expected no whitespace errors, the original branch unchanged, only exact file-map paths changed, and the final index listing is byte-for-byte identical to the pre-topic listing. Pre-existing staged entries are user-owned; do not stage or unstage them.

## Evidence and screenshot ownership

Topic 09 owns source inventory, dry-run report, model revision/file hashes, and unit-test logs. The `test_idx_001` dry run is labelled `ci-bootstrap`, has no active alias, and cannot satisfy canonical runtime evidence. No screenshot is required.

## Cleanup

Remove only dry-run temporary caches/output if their report/hash is retained. Keep the eight source files and locked config/code/tests. No runtime, alias, database, or cloud resource is acquired.

## Rubric table

| Workbook cell | Supporting proof | Ownership rule |
|---|---|---|
| `Sheet3!E8:E9` | Exact source/version/chunk/embedding lineage inputs | Supporting only; Topic 10 completes storage/lineage |
| `Sheet3!E61` | Adjacent effective versions and before/at/after boundary tests | Supporting only; later runtime evidence owns satisfaction |

## Definition of Done

Exactly eight files/nine versions pass grammar/word/window tests; deterministic 400/80 chunks and pinned normalized finite 384-vectors pass; exact candidate dry-run succeeds without storage/promotion; scoped diff checks pass.

## Completion Record

| Field | Record |
|---|---|
| Status | Complete - the eight canonical UTF-8/LF source files parse into exactly nine immutable versions; the local candidate path emits deterministic 400/80 token chunks and finite normalized 384-vectors for the exact pinned BGE revision, with no storage or promotion. |
| Affected files | Created: `data/knowledge/ecommerce/returns.md`, `shipping.md`, `cancellation.md`, `payments.md`, `promotions.md`, `warranties.md`, `privacy.md`, `marketplace_support.md`; `scripts/llm/build_index.py`; `tests/unit/llm/test_indexing.py`. Modified: `configs/llm/models.yaml`, `src/vina_bim_shop/llm/contracts.py`, `src/vina_bim_shop/llm/ports.py`, `src/vina_bim_shop/llm/indexing.py`, and this Completion Record. No dependency lock, Section 03 evidence, cloud, or unrelated tracked file was edited. |
| Commands / exit codes | Before edits: `rtk git status --short --branch` 0 on `feature/implement-edai2...origin/feature/implement-edai2`; `rtk git ls-files --stage` 0 (901 entries); three locked-source SHA recomputations 0; `rtk uv run python scripts/generate/verify_section03_manifest.py --manifest evidence/03_data_generator_improvement/section03_manifest.json --strict` 0 (`section03 manifest: PASS`). Test-first checks intentionally red: parser import 1; chunk interface import 1; embedding interface import 1; candidate-pipeline constructor 1; dry-run CLI absence 1; report-digest attribute 1. Green focused sequence: `rtk uv run pytest tests/unit/llm/test_indexing.py -q` 0, 14 passed. Real local candidate command `rtk uv run python scripts/llm/build_index.py --mode candidate --index-version test_idx_001 --source-root data/knowledge/ecommerce --dry-run` 0 twice (same report digest); it produced 8 documents, 9 versions, 17 chunks, dimension 384, `candidate_label=ci-bootstrap`, `storage_written=false`, and `promotion=false`. Regression gate `rtk uv run pytest tests/unit/llm/test_indexing.py tests/contract/llm/test_section03_contract.py tests/unit/llm/test_contracts.py tests/contract/llm/test_api_contracts.py tests/contract/llm/test_mcp_contracts.py tests/unit/test_edai2_repository_contract.py tests/unit/test_edai2_security_static.py -q` 0, 33 passed, 2 third-party warnings. Post-record acceptance reran that same gate 0, followed by `rtk git diff --check` 0, `rtk git diff --cached --quiet` 0, `rtk git ls-files --stage` 0 (901 entries, byte-for-byte identical to the pre-topic listing), and `rtk git status --short --branch` 0. |
| Evidence + SHA-256 | Locked inputs remained exact: `tmp/edai2-plan/03_data_generator_improvement.md` `3c906ae30ac0fee606e96608a7b5759cd7439ae048c4c12a84511fce5cc33ae6`; `tmp/edai2-plan/04.2_llm_design.md` `b8be3ef5c84fe4d6fe52e8894c3c5dc1c3babc898e2a87684b2b8ff720d6d079`; `tmp/rubic-check/Coursework Tracking (Public).xlsx` `71b2403e068081b00245bea5e15c5754f3762ad354e0a3a6576d69e4963c8657`. Canonical source SHA-256s: `returns.md` `91cfcd43f23ed867ddb0780c88bfb68cc47b3484c57d1b28fb38ccba6c206191`; `shipping.md` `8ef2a95859de3d2da9c2978c8a285a8925ca3018ce11c094005e219ef3e83d47`; `cancellation.md` `1c0af7f77078a5690b97231efe16c32325823ec3d8adebd6e989045958d4cd0a`; `payments.md` `94760d2923a0af098139c4a203ddec26c52885c82ff79f4e3bb5d5934cba98af`; `promotions.md` `3671c89e258ccdf0e3ad08905210231593af70b29a0c25d4e3febb7659ca57c0`; `warranties.md` `d8521367cedbf2c73296e4430f50a8e15ee8a15152781ed2a9af560b14a64d51`; `privacy.md` `0707b28c5075243b6cc269af679b24d4326fb43d6160454c0e36ce1dea2ae514`; `marketplace_support.md` `bc1f5d938bb0042d6e1b192f19011c331f5c520f9ef25d2c4129a29c30a088b6`. Candidate machine evidence is stdout from the exact dry-run command, with canonical self-digest `fb856b3e0fb4d32bc9fd727dcb905ec57040b15c74c2a97c18cecbc247b52065` on both runs; it includes all version/chunk/vector and model-file hash maps. Pinned model: `BAAI/bge-small-en-v1.5@5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`; snapshot `model.safetensors` `3c9f31665447c8911517620762200d2245a2518d6e7208acc78cd9db317e21ad`, `tokenizer.json` `d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66`, `config.json` `094f8e891b932f2000c92cfc663bac4c62069f5d8af5b5278c4306aef3084750`. Implementation/test evidence: `configs/llm/models.yaml` `e6e2e7ac46d568f6c9139c55628bf661b06e1e9d03806e547d09c1cdc297d1bc`; `src/vina_bim_shop/llm/indexing.py` `95f347544ec27d5216a37a08c732fb2860dc12af8ad7114d62617388451895cf`; `scripts/llm/build_index.py` `a6f334dd6adb9fe0d6328a0cbcb336874749d2ecd26f3366dae1622304ced9ba`; `tests/unit/llm/test_indexing.py` `a8a83fe021fc4076a04a58a39da86762b060df9308c4e1a8d289b40082a5928c`. Machine test evidence is terminal stdout; no separate test-log artifact was retained. |
| Screenshot QA | No screenshot was required, manufactured, or created. This topic owns machine source/dry-run evidence only. |
| Cleanup / runtime release | No Kubernetes, Kind, GCP, PostgreSQL/pgvector, Feast, Airflow, DataHub, Docker, index, alias, or deployment resource was acquired or changed. No temporary output file was created. The exact Hugging Face snapshot remains in the shared local user cache for repeatability; Windows warned that cache symlinks are unavailable, but the pinned file hashes were recorded and no cache cleanup was needed. |
| Rubric disposition | Supports `Sheet3!E8:E9` only with trusted source/version/chunk/embedding lineage inputs; Topic 10 owns storage and lineage completion. Supports `Sheet3!E61` only with adjacent effective-version boundary handling. No score, GKE evidence, runtime retrieval claim, or canonical evidence is claimed here. |
| Limitations | `test_idx_001` is a local `ci-bootstrap` candidate only: it is neither stored nor active/canonical, has no alias, ANN/retrieval API, evaluation, UI capture, GKE/Kind claim, or cloud deployment. |
| Successor handoff | Topic 10 must consume the exact eight-file inventory, nine-version report, `fb856b3e0fb4d32bc9fd727dcb905ec57040b15c74c2a97c18cecbc247b52065` candidate report (including all chunk/vector hashes), and `BAAI/bge-small-en-v1.5@5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`; it alone may implement storage/alias/lineage. Retain `test_idx_001` as bootstrap-only and do not represent this local result as GKE evidence. |
