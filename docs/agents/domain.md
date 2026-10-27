# Domain docs

## Glossary

`CONTEXT.md` at the repository root is the authoritative domain
glossary for this single-context repository.

For engineering skills, interpret references to `GLOSSARY.md`
as references to `CONTEXT.md`. Read it before domain exploration
and use its canonical vocabulary in proposals, tickets, and tests.

When terminology is resolved and writing is authorized, update
`CONTEXT.md` using its existing format. Keep implementation plans
and status in their existing documents.

Do not create a duplicate `GLOSSARY.md` or `GLOSSARY-MAP.md`.

## Architecture decisions

Read relevant decisions in `docs/adr/` when present. If the
directory is absent, proceed silently.

Create ADRs lazily, only for consequential tradeoffs that are
hard to reverse and surprising without context. Surface conflicts
with existing ADRs explicitly.
