#!/usr/bin/env python3
"""PreToolUse hook: file-tool path check + bulk-staging nudge (SPEC V.12, V.19).

This hook no longer tries to stop shell commands from reading secrets. Doing that
from command TEXT means predicting what bash will do (functions, aliases, globs,
heredocs, quoting, eval), and every review round found a new way past it. Secret
protection now sits where the effect happens:

  * shell reads   -> Claude Code OS sandbox, `sandbox.filesystem.denyRead`
                     (.claude/settings.json); test: scripts/sandbox_probe.sh
  * file tools    -> permission deny rules (.claude/settings.json) + this hook's
                     path check below (paths are exact; nothing to parse)
  * commits       -> scripts/check_secrets.py on the staged CONTENT
                     (.githooks/pre-commit, and CI on every push)

What remains here:
  1. Read/Edit/Write/Grep/Glob/NotebookEdit on a secret-looking path -> block.
  2. `git add -A|--all|-u|.|:/` and `git commit -a|--all` -> block with a hint.
     A workflow nudge, not a security boundary: anything it misses is caught by
     check_secrets.py before the commit lands. It has no exemptions to get wrong.

Protocol: JSON on stdin; exit 2 + reason on stderr blocks; exit 0 allows.
Unparseable input is allowed (fail-open); the boundaries above don't depend on it.
"""

import json
import shlex
import sys

SECRET_EXTS = (".pem", ".key", ".p12", ".pfx", ".jks", ".keystore", ".kdbx")
SECRET_DIRS = {"secret", "secrets"}
SSH_KEYS = ("id_rsa", "id_ed25519", "id_ecdsa", "id_dsa")
ENV_ALLOWED = {".env.example", ".env.sample", ".env.template"}
FILE_TOOL_KEYS = ("file_path", "notebook_path", "path", "glob", "pattern")

SEPARATOR_CHARS = set(";&|()\n")
GIT_OPTS_WITH_ARG = {
    "-C",
    "-c",
    "--git-dir",
    "--work-tree",
    "--namespace",
    "--exec-path",
}
BULK_ADD_PATHSPECS = {".", ":/", ":", "*", "./"}


def is_secret_path(value: str) -> bool:
    """A path (or glob) that names a secret file or folder."""
    raw = value.strip().replace("\\", "/")
    parts = [p for p in raw.rstrip("/").split("/") if p not in ("", ".")]
    if not parts:
        return False
    if any(p in SECRET_DIRS for p in parts[:-1]) or (
        parts[-1] in SECRET_DIRS and "/" in raw
    ):
        return True
    base = parts[-1]
    if base in ENV_ALLOWED:
        return False
    if base.startswith(".env") or base.endswith(SECRET_EXTS):
        return True
    return base.startswith(SSH_KEYS) and not base.endswith(".pub")


def segments(command: str) -> list[list[str]]:
    """Split a command into simple commands (quote-aware) to find git calls."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()<>\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        tokens = list(lexer)
    except ValueError:
        tokens = command.replace("\n", " ; ").split()
    out, cur = [], []
    for tok in tokens:
        if tok and set(tok) <= SEPARATOR_CHARS:
            if cur:
                out.append(cur)
            cur = []
        else:
            cur.append(tok)
    if cur:
        out.append(cur)
    return out


def git_call(words: list[str]) -> tuple[str | None, list[str]]:
    while words and ("=" in words[0] and not words[0].startswith("-")):
        words = words[1:]  # VAR=value prefixes
    if not words or words[0].rsplit("/", 1)[-1] != "git":
        return None, []
    i = 1
    while i < len(words):
        w = words[i]
        if w in GIT_OPTS_WITH_ARG:
            i += 2
        elif w.startswith("-"):
            i += 1
        else:
            return w, words[i + 1 :]
    return None, []


def bulk_staging(sub: str | None, args: list[str]) -> str | None:
    if sub == "add":
        for a in args:
            if a in ("--all", "--update", "-A", "-u") or a in BULK_ADD_PATHSPECS:
                return "Stage explicit paths: `git add -- <files>` (no -A/-u/./:/)."
            if a.startswith("-") and not a.startswith("--") and set(a[1:]) & {"A", "u"}:
                return "Stage explicit paths: `git add -- <files>` (no -A/-u/./:/)."
    if sub == "commit":
        for a in args:
            if a == "--":
                break
            if a == "--all":
                return "`git commit -a/--all` stages everything; stage explicit paths first."
            if a.startswith("-") and not a.startswith("--"):
                for ch in a[1:]:
                    if ch in "mFCct":
                        break
                    if ch == "a":
                        return "`git commit -a` stages everything; stage explicit paths first."
    return None


def check(payload: dict) -> str | None:
    tool = payload.get("tool_name", "")
    inp = payload.get("tool_input") or {}
    if tool == "Bash":
        for words in segments(str(inp.get("command", ""))):
            reason = bulk_staging(*git_call(words))
            if reason:
                return reason
        return None
    for key in FILE_TOOL_KEYS:
        if tool == "Grep" and key == "pattern":
            continue  # a regex over contents, not a path
        value = inp.get(key)
        if isinstance(value, str) and is_secret_path(value):
            return f"{tool} on secret-looking path {value!r} is blocked (SPEC V.12)."
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if not isinstance(payload, dict):
        return 0
    reason = check(payload)
    if reason:
        print(
            f"guard.py: {reason} A block means stop and ask the user.", file=sys.stderr
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
