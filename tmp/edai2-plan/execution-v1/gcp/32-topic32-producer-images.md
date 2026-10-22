# Topic 32 — Producer Images (design patterns + whole-course diagram)

## Scope

Produce the two final producer images owned by Topic 32 and validate them with the same
strict screenshot validator used by Topic 31. Topic 31 does not backfill these images.

- `evidence/04_2_llm_design/screenshots/design_patterns.png`
- `evidence/04_2_llm_design/screenshots/whole_course_diagram.png`

## Producer Contract

- Source-rendered from `scripts/qa/render_topic32_diagrams.py`.
- Reachability: `local-render`.
- Manifest rows written through `record_capture`; linked machine evidence:
  `evidence/04_2_llm_design/screenshots/topic32_source.json`.
- Dimensions: `1600x1000`.
- The Section 03 pass image `section03_config_and_training_join.png` is never overwritten.

## Completion Record

- **Status:** Completed (2026-10-19).
- **Branch / revision:** `feature/implement-edai2`, `a5c2111d46cf8805baee18ba98bfd2df9ec942c5`.
- **Producer:** `scripts/qa/render_topic32_diagrams.py`.
- **Images / SHA-256:**
  - `design_patterns.png` — `7ea0569a2be061621f3ae28d4e21e0f11b9994bc88aa20e2953a67e13a95b41c`
  - `whole_course_diagram.png` — `71732162be9f52006354bff91db69bc7a15dca36eb658034e615a3347f88c3b6`
- **Machine evidence:** `evidence/04_2_llm_design/screenshots/topic32_source.json`.
- **Manifest:** `evidence/04_2_llm_design/screenshots/ui_manifest.json` rows for both images.
- **Validation:** `run_manifest` screenshot audit includes both as `Pass`; `pending_producer: 0`.
- **Visual QA:** agent (operator-delegated) at original resolution; titles, pattern names,
  component relationships, boundaries, flows, and legends are legible.
- **Limitations:** The diagrams are source-rendered documentation, not live runtime captures.
- **Handoff:** Topic 31 reran the strict audit after T32 and recorded `pass: 8 / missing: 26 /
  pending: 0`.
