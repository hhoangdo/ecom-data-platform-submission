# Issue tracker: Local Markdown

Issues live in this repository as Markdown files. Use this local
workflow when a skill says to publish to the issue tracker.

## Conventions

- Keep tickets under `.scratch/<feature-slug>/issues/`.
- Use one file per ticket: `01-<slug>.md`, numbered from `01`.
- For v2 topics, use the topic ID as the directory name,
  for example `.scratch/L01/issues/01-<slug>.md`.
- Reuse an existing topic brief as the specification and current
  plan. Link to it from tickets rather than copying it.
- For work without an existing brief or specification, create
  `.scratch/<feature-slug>/spec.md` when needed.
- Record the triage role as a `Status:` line near the top of
  each issue; use `triage-labels.md`.
- Record the category as `Category: bug` or
  `Category: enhancement`.
- Append comments under `## Comments`.
- Fetch a ticket by reading its referenced file. Resolve a bare
  number within the named feature; ask if ambiguous.

## Topic status

`tmp/edai2-plan/execution-v2/README.md` remains the sole v2
topic-level status board. Ticket status describes individual
work items and does not establish topic completion.

Create directories and tickets only when needed. Setup itself
creates no tickets or duplicate specifications.

## Wayfinding

When wayfinder is invoked, use `.scratch/<effort>/map.md` and
numbered child tickets under `issues/`. Record `Type:` and
`Blocked by:` as described by the skill. For these children,
`Status:` tracks claim/resolution (`claimed` or `resolved`).
Claim before working; on resolution, append `## Answer` and
link the result from the map's Decisions-so-far.
