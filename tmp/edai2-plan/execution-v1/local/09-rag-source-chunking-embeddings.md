# RAG Source, Chunking, and Embeddings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the source/version parsing, deterministic token chunking, and pinned embedding half of EDAI2 Task 2, producing candidate-only inputs for Topic 10.

**Architecture:** Eight canonical Markdown files parse into exactly nine immutable document-version records. Each version is NFC-normalized and tokenized independently into deterministic 400-token/80-overlap chunks, then embedded with the pinned BGE revision into normalized finite 384-vectors. No active alias or storage promotion occurs.

**Tech Stack:** Python 3.12, Pydantic v2 contracts, Hugging Face `sentence-transformers`/`AutoTokenizer`, BAAI/bge-small-en-v1.5, SHA-256, RFC 8785/JCS canonical JSON, pytest, `uv`, `rtk`.

## Locked sources and execution policy

- Read `C:\Users\oou1hc\.codex\RTK.md`; every shell command begins with `rtk`.
- Section 03 source is `tmp/edai2-plan/03_data_generator_improvement.md`, SHA-256 `ece171c3d400c3b16fc668cd28e3587faebe1f596dd6c0c4498ff055e3fc027f`.
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
- Every file is UTF-8 without BOM, LF-only, and final-newline terminated; unknown/missing keys or free text outside records fails.
- Record grammar is exact front matter keys `document_id`, `category`, `version`, `effective_from`, `effective_to`, followed by canonical Markdown body.
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
- [ ] Run `rtk git diff --check` and `rtk git status --short --branch`; expected no whitespace errors, the original branch unchanged, only exact file-map paths changed, and nothing staged.

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
| Status | Not started |
| Affected files | Record only exact file-map paths actually changed |
| Commands / exit codes | Record every checkbox command and numeric exit code, ending with `rtk git status --short --branch` |
| Evidence + SHA-256 | Record source/model/dry-run/test-log paths and hashes |
| Screenshot QA | No screenshot required for Topic 09 |
| Cleanup / runtime release | Record dry-run cache disposition and `no runtime acquired` |
| Limitations | `test_idx_001` is bootstrap-only and not a stored/active/canonical index |
| Successor handoff | Provide exact source inventory, nine-version report, chunk/vector hashes, model revision, and dry-run output to Topic 10 |
