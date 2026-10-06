#!/usr/bin/env bash
# Cross-model, read-only review of the current branch against main using Codex CLI.
# Usage: scripts/review.sh [base-branch] [extra instructions]
set -euo pipefail

base="${1:-main}"
extra="${2:-}"
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
command -v codex >/dev/null || { echo "codex CLI not found on PATH" >&2; exit 1; }

prompt="Review this branch against ${base} for correctness bugs, broken SPEC.md invariants (§V),
doc claims that do not match code, test gaps, and security issues (shell use, innerHTML,
secret paths). Read SPEC.md and AGENTS.md first. For each finding give file:line, the concrete
failure scenario, and severity. Do not modify files. ${extra}"

cd "$repo"
codex review -c sandbox_mode='"read-only"' --base "$base" "$prompt"
