#!/usr/bin/env python3
"""PreToolUse guard for agents working in this repo (SPEC V.12).

Blocks, deterministically:
  * bulk staging / committing: git add -A|--all|-u|--update|.|:/ and
    git commit -a|--all (incl. clusters like -am, and git -c/-C prefixes);
  * any tool call that touches a secret-looking path (.env*, *.pem, *.key,
    *.p12, *.pfx, *.jks, *.keystore, *.kdbx, id_rsa/id_ed25519/id_ecdsa,
    secret/ or secrets/ dirs).

Matching is on path *form*: `secret/x` or `./secrets` matches, the plain word
"secret" in prose does not. Newlines separate commands (as in sh) but quoted
text stays one word, so multi-line commit messages are not split apart.
Inline interpreter code (python -c, node -e, perl -e, ruby -e) is scanned for
secret-looking path tokens too.

Known limit (SPEC D.11): this inspects words, not effects. A command that
reaches a secret without naming it (e.g. `grep -R TOKEN .`) is not blocked.
The guard stops accidents; it is not a sandbox.

Metadata-only git commands (rm --cached, ls-files, check-ignore) may name
secret paths. History reads are not blocked: no secret was ever committed
(SPEC §B has no secret entry); add them here if that changes.

Protocol: JSON on stdin; exit 2 + reason on stderr blocks the call; exit 0 allows.
Unparseable input is allowed (fail-open) so a hook bug never wedges the agent;
tests/test_guard.py keeps the parser honest.
"""

import json
import re
import shlex
import sys
from itertools import pairwise

SECRET_EXTS = (".pem", ".key", ".p12", ".pfx", ".jks", ".keystore", ".kdbx")
SECRET_DIRS = {"secret", "secrets"}
SSH_KEYS = ("id_rsa", "id_ed25519", "id_ecdsa", "id_dsa")
ENV_ALLOWED = {".env.example", ".env.sample", ".env.template"}

SEPARATOR_CHARS = set(";&|()\n")  # a token made only of these splits commands
WRAPPERS = {"sudo", "env", "command", "nohup", "time", "exec", "xargs", "nice"}
SHELLS = {"bash", "sh", "zsh", "dash"}
INTERPRETERS = ("python", "node", "perl", "ruby", "deno")
INLINE_CODE_FLAGS = {"-c", "-e", "--eval"}
CODE_TOKEN = re.compile(r"""[^\s'"(),;`{}\[\]+]+""")
GIT_OPTS_WITH_ARG = {
    "-C",
    "-c",
    "--git-dir",
    "--work-tree",
    "--namespace",
    "--exec-path",
}
GIT_METADATA = {"ls-files", "check-ignore", "status"}
BULK_ADD_PATHSPECS = {".", ":/", ":", "*", "./"}


def is_secret_path(word: str) -> bool:
    raw = word.strip().strip("'\"").replace("\\", "/")
    path = raw.rstrip("/")
    if not path:
        return False
    parts = [p for p in path.split("/") if p not in ("", ".")]
    if not parts:
        return False
    # secret/ dirs only in path form; the bare word is ordinary prose.
    if "/" in raw and any(p in SECRET_DIRS for p in parts):
        return True
    base = parts[-1]
    if "=" in base:  # --include=*.key style flags
        base = base.split("=", 1)[1]
    if base in ENV_ALLOWED:
        return False
    if base.startswith(".env"):  # .env, .env.local, .envrc, .env_prod
        return True
    if base.endswith(SECRET_EXTS):
        return True
    return base.startswith(SSH_KEYS) and not base.endswith(".pub")


def split_segments(command: str) -> list[list[str]]:
    # Newline separates commands in sh, so it must not count as whitespace;
    # inside quotes shlex keeps it as part of the word.
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()<>\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        tokens = list(lexer)
    except ValueError:  # unbalanced quotes: best effort
        tokens = command.replace("\n", " ; ").split()
    segments, current = [], []
    for tok in tokens:
        if tok and set(tok) <= SEPARATOR_CHARS:
            if current:
                segments.append(current)
            current = []
        else:
            current.append(tok)
    if current:
        segments.append(current)
    return segments


def strip_prefix(words: list[str]) -> list[str]:
    i = 0
    while i < len(words):
        w = words[i]
        if "=" in w and not w.startswith("-") and w.split("=", 1)[0].isidentifier():
            i += 1  # VAR=value
        elif w in WRAPPERS:
            i += 1
        else:
            break
    return words[i:]


def git_subcommand(words: list[str]) -> tuple[str | None, list[str]]:
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


def bulk_add(args: list[str]) -> bool:
    for a in args:
        if a == "--":
            continue
        if a in ("--all", "--update", "-A", "-u") or a in BULK_ADD_PATHSPECS:
            return True
        if a.startswith("-") and not a.startswith("--") and set(a[1:]) & {"A", "u"}:
            return True
    return False


def bulk_commit(args: list[str]) -> bool:
    for a in args:
        if a == "--":
            return False
        if a == "--all":
            return True
        if a.startswith("-") and not a.startswith("--"):
            cluster = a[1:]
            for ch in cluster:
                if ch in "mFCct":  # option taking a value: rest is its argument
                    break
                if ch == "a":
                    return True
    return False


def check_segment(words: list[str]) -> str | None:
    words = strip_prefix(words)
    if not words:
        return None
    cmd = words[0].rsplit("/", 1)[-1]

    if cmd in SHELLS and "-c" in words:
        idx = words.index("-c")
        if idx + 1 < len(words):
            return check_bash(words[idx + 1])

    if cmd.startswith(INTERPRETERS):
        for flag, code in pairwise(words):
            if flag in INLINE_CODE_FLAGS:
                for tok in CODE_TOKEN.findall(code):
                    if is_secret_path(tok):
                        return f"Inline code touches a secret-looking path ({tok!r}) (SPEC V.12)."

    if cmd == "git":
        sub, args = git_subcommand(words)
        if sub == "add" and bulk_add(args):
            return "Bulk staging is not allowed: stage explicit paths with `git add -- <files>`."
        if sub == "commit" and bulk_commit(args):
            return "`git commit -a/--all` is not allowed: stage explicit paths, then `git commit`."
        if sub in GIT_METADATA or (sub == "rm" and "--cached" in args):
            return None

    for w in words[1:]:
        if is_secret_path(w):
            return f"Touches a secret-looking path ({w!r}). Secrets never enter the agent context (SPEC V.12)."
    return None


def check_bash(command: str) -> str | None:
    for segment in split_segments(command):
        reason = check_segment(segment)
        if reason:
            return reason
    return None


def check(payload: dict) -> str | None:
    tool = payload.get("tool_name", "")
    inp = payload.get("tool_input") or {}
    if tool == "Bash":
        return check_bash(str(inp.get("command", "")))
    for key in ("file_path", "notebook_path", "path", "glob", "pattern"):
        if tool == "Grep" and key == "pattern":
            continue  # regex over contents, not a path
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
        print(f"guard.py: {reason}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
