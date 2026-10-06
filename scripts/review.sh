#!/usr/bin/env bash
# Cross-model, read-only review of the current branch against a base using Codex CLI.
# Usage: scripts/review.sh [base-branch] [extra instructions]
# Set REVIEW_OUT=<file> to also save the final report there.
# (`codex review --base` rejects a custom prompt, so this uses `codex exec` in a
#  read-only sandbox and lets Codex read the diff itself.)
set -euo pipefail

base="${1:-main}"
extra="${2:-}"
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
command -v codex >/dev/null || { echo "codex CLI not found on PATH" >&2; exit 1; }

prompt="You are reviewing a branch. Run \`git diff ${base}...HEAD\` and \`git log --oneline ${base}..HEAD\`
to see the change. Read AGENTS.md and SPEC.md first, then the touched files.
Report: correctness bugs, broken or unguarded SPEC.md invariants (§V), doc claims that do
not match the code (verify path:line cites), test gaps, and security issues (shell use,
innerHTML, secret paths, hook bypasses in .claude/hooks/guard.py).
For each finding: file:line, concrete failure scenario, severity (high/medium/low).
Do not modify any file. ${extra}"

cd "$repo"
out_args=()
[[ -n "${REVIEW_OUT:-}" ]] && out_args=(-o "$REVIEW_OUT")
# stdin from /dev/null: codex exec otherwise waits for extra input when not on a TTY.
codex exec -s read-only "${out_args[@]}" "$prompt" </dev/null
