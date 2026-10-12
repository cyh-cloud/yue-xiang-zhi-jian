# Domain docs

How engineering skills should consume this repo's domain documentation while exploring the codebase.

## Before exploring, read these

- `GLOSSARY.md` at the repo root, or
- `GLOSSARY-MAP.md` at the repo root if it exists, which points to one `GLOSSARY.md` per context. Read each one relevant to the topic.
- `docs/adr/`: read ADRs that touch the area you are about to enter.

If none of these files exist, move on silently. Do not flag missing glossary or ADRs; `/domain-modeling` creates them only when terms or decisions are actually resolved.

## File layout

Single-context (this repo):

```
/
├── GLOSSARY.md
├── docs/adr/
│   └── 0001-first-decision.md
└── src/...
```

## Vocabulary

When output names a domain concept (issue title, refactor proposal, test name), use the vocabulary in `GLOSSARY.md`. Avoid synonyms the glossary avoids; if a term is missing, note it for `/domain-modeling`.

## ADR conflicts

If a decision conflicts with an existing ADR, surface it explicitly, e.g. "Contradicts ADR-0001; worth reopening because..." and reconcile before changing direction.
