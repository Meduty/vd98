#!/usr/bin/env python3
"""PreToolUse hook: file-tool path check + git nudges (SPEC V.12, V.18, V.19).

This hook no longer tries to stop shell commands from reading secrets. Doing that
from command TEXT means predicting what bash will do (functions, aliases, globs,
heredocs, quoting, eval), and every review round found a new way past it. Secret
protection now sits where the effect happens:

  * shell reads   -> Claude Code OS sandbox, `sandbox.filesystem.denyRead`
                     (.claude/settings.json); test: scripts/sandbox_probe.sh
  * file tools    -> permission deny rules (.claude/settings.json) + this hook's
                     path check below (file tools run outside the sandbox)
  * commits       -> scripts/check_secrets.py on the staged CONTENT
                     (.githooks/pre-commit, and CI on every push)

What remains here:
  1. Read/Edit/Write/Grep/Glob/NotebookEdit on a secret-looking path -> block.
     A glob with literal parts (`*.p?x`, `secr?t/*`) is matched against example
     secret names; a pure wildcard (`*`, `**/*`) is not, since listing names isn't
     reading contents.
  2. Git nudges (workflow hints, not a security boundary; CI's scan is the backstop):
     `git add -A|--all|-u|.|:/`, `git commit -a|--all`, and skipping the pre-commit
     scan (`--no-verify`, `-n`, `-c core.hooksPath=...`, `GIT_CONFIG_*` env,
     `git config core.hooksPath <other>`). Wrappers such as `env`,
     `sudo`, `nice -n 5` and `VAR=x` prefixes are looked through.

Protocol: JSON on stdin; exit 2 + reason on stderr blocks; exit 0 allows.
Unparseable input is allowed (fail-open); the boundaries above don't depend on it.
"""

import fnmatch
import json
import os
import shlex
import sys

SECRET_EXTS = (".pem", ".key", ".p12", ".pfx", ".jks", ".keystore", ".kdbx")
SECRET_DIRS = {"secret", "secrets"}
SSH_KEYS = ("id_rsa", "id_ed25519", "id_ecdsa", "id_dsa")
ENV_ALLOWED = {".env.example", ".env.sample", ".env.template"}
# Names a glob is tried against (review finding: `*.p?x` hid `.pfx`).
SECRET_NAME_EXAMPLES = [
    ".env",
    ".env.local",
    ".env.production",
    ".envrc",
    ".env_prod",
    ".env-local",
    "server.pem",
    "server.key",
    "cert.p12",
    "cert.pfx",
    "release.jks",
    "release.keystore",
    "vault.kdbx",
    "id_rsa",
    "id_ed25519",
    "id_ecdsa",
]
GLOB_CHARS = set("*?[")
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
WRAPPERS = {"sudo", "doas", "env", "command", "nohup", "time", "nice", "exec", "ionice"}
WRAPPER_OPTS_WITH_ARG = {"-n", "-u", "-g", "-c", "-p"}


def _is_glob(part: str) -> bool:
    return bool(GLOB_CHARS & set(part))


def _pure_wildcard(part: str) -> bool:
    """`*`, `**`, `*.*`: matches anything, so it says nothing about secrets."""
    return not part.strip("*?.[]!-")


def is_secret_path(value: str) -> bool:
    """A path (or glob) that names, or can match, a secret file or folder."""
    raw = value.strip().replace("\\", "/")
    parts = [p for p in raw.rstrip("/").split("/") if p not in ("", ".")]
    if not parts:
        return False
    dirs, base = parts[:-1], parts[-1]
    # every part, the last one too: a file-tool path is a path, so a bare `secret`
    # names the folder (PR #3 review). The old Bash-prose exemption for the bare word
    # went away with the shell parser.
    for p in dirs + [base]:
        if p in SECRET_DIRS:
            return True
        if (
            _is_glob(p)
            and not _pure_wildcard(p)
            and any(fnmatch.fnmatchcase(d, p) for d in SECRET_DIRS)
        ):
            return True
    if base in ENV_ALLOWED:
        return False
    if base.startswith(".env") or base.endswith(SECRET_EXTS):
        return True
    if base.startswith(SSH_KEYS) and not base.endswith(".pub"):
        return True
    if _is_glob(base) and not _pure_wildcard(base):
        return any(fnmatch.fnmatchcase(name, base) for name in SECRET_NAME_EXAMPLES)
    return False


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


def _strip_prefixes(words: list[str]) -> list[str]:
    """Drop `VAR=x` assignments and wrapper commands (with their options)."""
    i = 0
    while i < len(words):
        w = words[i]
        if "=" in w and not w.startswith("-") and w.split("=", 1)[0].isidentifier():
            i += 1
        elif w.rsplit("/", 1)[-1] in WRAPPERS:
            i += 1
            while i < len(words) and words[i].startswith("-"):
                i += 2 if words[i] in WRAPPER_OPTS_WITH_ARG else 1
        else:
            break
    return words[i:]


def git_call(words: list[str]) -> tuple[str | None, list[str], list[str]]:
    """(subcommand, its args, git's global options) or (None, [], [])."""
    words = _strip_prefixes(words)
    if not words or words[0].rsplit("/", 1)[-1] != "git":
        return None, [], []
    i, global_opts = 1, []
    while i < len(words):
        w = words[i]
        if w in GIT_OPTS_WITH_ARG:
            global_opts += words[i : i + 2]
            i += 2
        elif w.startswith("-"):
            global_opts.append(w)
            i += 1
        else:
            return w, words[i + 1 :], global_opts
    return None, [], global_opts


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


def skips_precommit(
    sub: str | None, args: list[str], global_opts: list[str]
) -> str | None:
    """The pre-commit hook runs the secret scan; don't route around it (review finding)."""
    msg = "The pre-commit hook runs the secret scan (V.17); commit without skipping it."
    if "core.hookspath" in " ".join(global_opts).lower():
        return msg
    if sub == "commit":
        for a in args:
            if a == "--":
                break
            if a == "--no-verify":
                return msg
            if a.startswith("-") and not a.startswith("--"):
                for ch in a[1:]:
                    if ch in "mFCct":
                        break
                    if ch == "n":
                        return msg
    return None


def env_skips_precommit(words: list[str]) -> str | None:
    """`GIT_CONFIG_KEY_0=core.hooksPath ... git commit` sets the hooks path from the
    environment instead of `-c` (PR #3 review round 2). Same nudge, same caveat."""
    for w in words:
        name, _, value = w.partition("=")
        if not _ or not name.isidentifier():
            break  # past the leading assignments
        if name.startswith("GIT_CONFIG") and "hookspath" in value.lower():
            return "The pre-commit hook runs the secret scan (V.17); commit without skipping it."
    return None


def config_skips_precommit(sub: str | None, args: list[str]) -> str | None:
    """`git config core.hooksPath /dev/null` (or `--unset`) turns the scan off for
    every later commit (PR #2 review round 2). Reading it, or setting `.githooks`, is fine."""
    if sub != "config":
        return None
    low = [a.lower() for a in args]
    if "core.hookspath" not in low:
        return None
    rest = args[low.index("core.hookspath") + 1 :]
    if "--unset" in low or "--unset-all" in low or "--remove-section" in low:
        return "The pre-commit hook runs the secret scan (V.17); keep core.hooksPath=.githooks."
    if rest and rest[0].rstrip("/") not in (".githooks", "./.githooks"):
        return "The pre-commit hook runs the secret scan (V.17); keep core.hooksPath=.githooks."
    return None


def real_path(value: str, cwd: str | None) -> str | None:
    """Where a literal path really points (symlinks resolved), or None for globs."""
    if not value or GLOB_CHARS & set(value):
        return None
    try:
        return os.path.realpath(
            os.path.join(cwd or os.getcwd(), os.path.expanduser(value))
        )
    except (OSError, ValueError):
        return None


def check(payload: dict) -> str | None:
    tool = payload.get("tool_name", "")
    inp = payload.get("tool_input") or {}
    if tool == "Bash":
        for words in segments(str(inp.get("command", ""))):
            sub, args, global_opts = git_call(words)
            reason = (
                bulk_staging(sub, args)
                or skips_precommit(sub, args, global_opts)
                or config_skips_precommit(sub, args)
                or (env_skips_precommit(words) if sub == "commit" else None)
            )
            if reason:
                return reason
        return None
    for key in FILE_TOOL_KEYS:
        if tool == "Grep" and key == "pattern":
            continue  # a regex over contents, not a path
        value = inp.get(key)
        if not isinstance(value, str):
            continue
        if is_secret_path(value):
            return f"{tool} on secret-looking path {value!r} is blocked (SPEC V.12)."
        # a harmless-looking name can be a symlink to a secret (PR #3 review round 2)
        target = real_path(value, payload.get("cwd"))
        if target and is_secret_path(target):
            return (
                f"{tool} on {value!r} is blocked: it resolves to a secret-looking path."
            )
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
