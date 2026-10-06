#!/usr/bin/env python3
"""Refuse to commit secrets: check staged (or all tracked) files by name and content.

Effect-level check (SPEC V.12): it looks at what would actually enter git, so it
doesn't matter how the files got staged (`git add -A`, globs, `-f`, an editor).
Prints file names and the rule that matched, never the matching content.

    python3 scripts/check_secrets.py --staged   # pre-commit hook (.githooks/pre-commit)
    python3 scripts/check_secrets.py --all      # CI: every tracked file

Exit 1 if anything matched. Stdlib only, so the hook runs without the venv.
"""

import re
import subprocess
import sys
from pathlib import PurePosixPath

SECRET_DIRS = {"secret", "secrets"}
SECRET_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".jks", ".keystore", ".kdbx")
ENV_ALLOWED = {".env.example", ".env.sample", ".env.template"}

# Content rules: name -> pattern. Shapes of real credentials, not words about them.
CONTENT_RULES = {
    "private key block": re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "GitHub token": re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "GitHub fine-grained token": re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{60,}\b"),
    "AWS access key id": re.compile(rb"\b(AKIA|ASIA)[0-9A-Z]{16}\b"),
    "OpenAI/Anthropic-style key": re.compile(rb"\bsk-(ant-)?[A-Za-z0-9_-]{32,}\b"),
    "JWT": re.compile(
        rb"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"
    ),
    "Slack token": re.compile(rb"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
}
MAX_BYTES = 2_000_000  # skip huge blobs (fonts, media); names are still checked


def name_rule(path: str) -> str | None:
    p = PurePosixPath(path)
    if any(part in SECRET_DIRS for part in p.parts[:-1]):
        return "inside a secret/ folder"
    name = p.name
    if name in ENV_ALLOWED:
        return None
    if name.startswith(".env"):
        return "env file"
    if name.endswith(SECRET_SUFFIXES):
        return "key/keystore file"
    if name.startswith(
        ("id_rsa", "id_ed25519", "id_ecdsa", "id_dsa")
    ) and not name.endswith(".pub"):
        return "SSH private key"
    return None


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], capture_output=True, check=True).stdout


def files_and_blobs(staged: bool) -> list[tuple[str, bytes]]:
    if staged:
        names = git(
            "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"
        ).split(b"\0")
        out = []
        for raw in filter(None, names):
            path = raw.decode("utf-8", "surrogateescape")
            out.append(
                (path, git("show", f":{path}"))
            )  # the staged blob, not the worktree
        return out
    out = []
    for raw in filter(None, git("ls-files", "-z").split(b"\0")):
        path = raw.decode("utf-8", "surrogateescape")
        try:
            with open(path, "rb") as fh:
                out.append((path, fh.read(MAX_BYTES + 1)))
        except OSError:
            continue
    return out


def check(files: list[tuple[str, bytes]]) -> list[str]:
    problems = []
    for path, blob in files:
        rule = name_rule(path)
        if rule:
            problems.append(f"{path}: {rule}")
            continue
        if len(blob) > MAX_BYTES:
            continue
        for label, pattern in CONTENT_RULES.items():
            if pattern.search(blob):
                problems.append(f"{path}: contains a {label}")
                break
    return problems


def main(argv: list[str]) -> int:
    if argv[1:] not in (["--staged"], ["--all"]):
        print(__doc__, file=sys.stderr)
        return 2
    problems = check(files_and_blobs(staged=argv[1] == "--staged"))
    if problems:
        print(
            "check_secrets: refusing; these look like secrets (contents not shown):",
            file=sys.stderr,
        )
        for line in problems:
            print(f"  {line}", file=sys.stderr)
        print(
            "Unstage them (git restore --staged <path>) and keep secrets in the vault.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
