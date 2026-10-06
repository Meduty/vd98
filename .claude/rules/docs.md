---
paths:
  - "SPEC.md"
  - "FORMAT.md"
  - "ARCHITECTURE.md"
  - "docs/**"
---
# Docs rules

- First line of every doc in `docs/` is a status header: LIVING (with "must match" + Reconciled date) or FROZEN.
- LIVING docs change in the same commit as the code they describe; bump **Reconciled**.
- FROZEN docs are never edited after the fact; write a new journal entry instead.
- SPEC edits follow `FORMAT.md` and go through the `repo-spec` skill: IDs only go up, strike through retired entries, one rule per entry, every §V names its guard or says `unguarded`.
- Cite `path:line` plus the symbol; after reformatting, re-verify cites.
- No secrets, tokens or personal data in any doc.
