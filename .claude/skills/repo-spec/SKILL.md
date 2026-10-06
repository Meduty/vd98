---
name: repo-spec
description: Sole editor of SPEC.md for this repo. Modes new, distil, amend, backprop. Use when asked to change SPEC, add/retire an invariant, record a bug, resolve a §D question, or flip a §T status.
---
# repo-spec

Writes **only** `SPEC.md`. Follow `FORMAT.md` exactly.

Modes:
- **amend** — change §G/§C/§I/§V/§T/§D entries the user approved.
- **backprop** — add §B row (date · symptom · cause with path+symbol · fix · guarding §V); add or strengthen the §V it names.
- **distil** — re-derive §I/§C from code; every claim checked by grep first.
- **new** — only if SPEC.md is missing.

Rules:
1. IDs only go up. Retire with ~~strike~~ + reason; never renumber or delete.
2. Every §V ends with `Guard: <test id or hook path>` or `Guard: unguarded`.
3. One rule per entry; each entry reads alone.
4. §D questions are resolved inline (`**Decided YYYY-MM-DD:** …`), never deleted.
5. Cite `path:line` + symbol; verify the line before writing it.
6. Bump the **Reconciled** date in the header.
7. Show the diff (`git diff -- SPEC.md`) to the user.
