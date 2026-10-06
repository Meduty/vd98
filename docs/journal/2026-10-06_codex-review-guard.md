> **Status: FROZEN** (written 2026-10-06). Append-only history.

# 2026-10-06 — Codex review of T.5 and guard hardening

## Review

`scripts/review.sh` (Codex, read-only sandbox) reviewed `main...chore/agentic-setup`. 7 findings:

| # | Finding | Response |
|---|---|---|
| 1 | `.envrc`-style names not guarded or ignored | fixed (B.13) |
| 2 | Indirect reads (`grep -R . .`, `python3 -c`) bypass the guard | partly fixed (inline interpreter code scanned, B.13); remainder recorded as D.11 |
| 3 | Newline-separated commands bypass bulk-stage detection | fixed (B.11); worst finding — confirmed by probe |
| 4 | `@import "https://…"` passes V.14 guard | fixed (B.14) |
| 5 | V.2, V.9, V.8-escape guards still open | dismissed: already tracked as T.9 |
| 6 | HANDOFF overstated xfail coverage | fixed: names exact pinned bugs |
| 7 | T.5 `doing` vs HANDOFF "done" | fixed: T.5 → done |

Every finding was reproduced (probe script or code read) before acting.
The 60 original guard tests caught none of findings 1–3: tests written by the
same agent as the code share its blind spots. Cross-model review earned its keep.

## Hook blocks during this work (stop-and-ask rule held)

1. `git add --dry-run -A` — intended live test of the guard. Blocked as designed.
2. Agent's own `python3 - <<'EOF'` edit script for `guard.py`: heredoc docstring text
   contained the bare word "secret" → false positive (became B.12). Stopped, asked,
   then applied edits with the Edit tool (checked by path, not content).
3. `for f in .env …; do git check-ignore …` — names were words of `for`, not of the
   exempt `git check-ignore`. Correct by the guard's rules. Stopped, asked; ran the
   direct `git check-ignore -v <paths>` form instead (the exemption's intended use).

## Cross-session audit

Searched all Claude Code transcripts on this machine for guard blocks: 12 across 6
sessions (10 in lottery-of-choice, 2 here before this entry). 8 were prose false
positives (heredoc prompts/briefs, edit scripts, a `git commit -F -` body naming
`.jks`, an edit script containing the text `git add .`). Fixes that helped there:
Write/Edit tools for any text that mentions secret paths; rephrasing commit
messages; dropping "is the secret absent?" checks. Recorded as memory
`guard-hook-prose-false-positives` and fed back into the agentic-repo-prep guide §4.2.

## Agent errors

- `scripts/review.sh` first used `codex review --base` with a custom prompt (rejected by
  the CLI), then `codex exec` without `</dev/null` (hung reading stdin until timeout).
- Wrote D.11 as "Decided" for a choice the user had not made; corrected to an open
  recommendation before committing.
- First prose-allow tests were quoted strings, which passed on the old guard too; added
  unquoted heredoc cases and re-ran the suite against the old guard to prove they bite.
