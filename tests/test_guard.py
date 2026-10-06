"""Tests for the PreToolUse guard hook (SPEC V.12)."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "guard.py"
spec = importlib.util.spec_from_file_location("guard", HOOK)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def bash(cmd):
    return guard.check({"tool_name": "Bash", "tool_input": {"command": cmd}})


@pytest.mark.parametrize(
    "cmd",
    [
        "git add -A",
        "git add --all",
        "git add -u",
        "git add --update",
        "git add .",
        "git add :/",
        "git add --dry-run -A",
        "git add -Av",
        "git -c core.quotepath=off add -A",
        "git -C /tmp/x add --all",
        "git --no-pager add -A",
        "git commit -a -m wip",
        "git commit -am wip",
        "git commit --all -m wip",
        "uv run pytest && git add -A",
        "true; git add -A",
        "true & git add -A",
        "true | git add -A",
        "FOO=1 git add -A",
        "env git add -A",
        "bash -c 'git add -A'",
        "cat .env",
        "cat ./config/.env.local",
        "less secret/keystore.txt",
        "cp server.pem /tmp/",
        "echo hi > .env",
        "base64 id_rsa",
        "git add secrets/token.txt",
        "grep -r foo --include=*.key .",
        # Codex review 2026-10-06: newline-separated commands
        "git status\ngit add -A",
        "true\ngit commit -am x",
        "uv run pytest -q\n\ngit add .",
        # Codex review 2026-10-06: .env prefix variants
        "cat .envrc",
        "cat config/.env_prod",
        # Codex review 2026-10-06: inline interpreter code
        "python3 -c 'print(open(\".env\").read())'",
        'node -e \'require("fs").readFileSync("secret/x")\'',
        # secret dirs still blocked in path form
        "ls secrets/",
        "ls ./secret",
        # heredoc fed to a shell/interpreter is code (B.15)
        "python3 - <<'EOF'\nprint(open('.env').read())\nEOF",
        "bash <<'EOF'\ncat .env\nEOF",
        "cat <<'EOF' | sh\ncat .env\nEOF",
        "python3 -c \"$(cat <<'EOF'\nprint(open('.env').read())\nEOF\n)\"",
        # data heredoc: unquoted delimiter expands, target and trailing lines still count
        "cat > notes.md <<EOF\n$(cat .env)\nEOF",
        "cat > notes.md <<'EOF'\nx\nEOF\ncat .env",
        "cat <<'EOF' > .env\nKEY=1\nEOF",
        # a data heredoc whose file the same command runs is code (B.17, upstream review)
        "cat > /tmp/run.sh <<'EOF'\ncat .env\nEOF\nsh /tmp/run.sh",
        "trap 'sh /tmp/r.sh' EXIT; cat > /tmp/r.sh <<'EOF'\ncat .env\nEOF",
        "tee /tmp/r.py <<'EOF'\nprint(open('.env').read())\nEOF\npython3 /tmp/r.py",
    ],
)
def test_blocks(cmd):
    assert bash(cmd) is not None, cmd


@pytest.mark.parametrize(
    "cmd",
    [
        "git add -- SPEC.md src/vd98/manager.py",
        "git add src/vd98/web/app.js",
        # prose mentioning the word is not a path (8/12 past blocks were prose)
        "git commit -m 'keep the secret out of git'",
        "echo 'reaches a secret without naming it'",
        "python3 - <<'EOF'\nprint('secrets are never read')\nEOF",
        "cat > notes.md <<'EOF'\nreaches a secret without naming it\nEOF",
        "git commit -F - <<'EOF'\nkeep secrets out\nEOF",
        # data-sink heredoc naming secret paths is prose (B.15)
        "cat > review/prompt.md <<'EOF'\nNever read secret/ or .env; ask the user.\nEOF",
        "git commit -q -F - <<'EOF'\nfix: untrack secret/ and .env.dev\nEOF",
        "tee -a notes.md <<'EOF'\nuntracked .env and secret/\nEOF",
        "git commit -m 'add -A flag docs'",
        "git commit -m 'all good' --amend",
        "git commit --author='A <a@b>' -m x",
        "git status",
        "git diff --cached --stat",
        "git log --oneline -5",
        "git rm --cached .env",
        "git ls-files .env",
        "git check-ignore -v .env",
        "uv run pytest -q",
        "uv run ruff check .",
        "cat .env.example",
        "cat id_rsa.pub",
        "echo 'keys are in the vault'",
        "grep -n monkey src/",
        "git commit -m 'line one\nline two'",
        "git status\ngit diff --stat",
        "python3 -c 'print(1)'",
    ],
)
def test_allows(cmd):
    assert bash(cmd) is None, cmd


@pytest.mark.parametrize(
    "tool,inp",
    [
        ("Read", {"file_path": "/repo/.env"}),
        ("Read", {"file_path": "/repo/secret/app.jks"}),
        ("Edit", {"file_path": "/repo/certs/server.pem"}),
        ("Write", {"file_path": "/repo/.env.production"}),
        ("Grep", {"pattern": "x", "path": "/repo/secrets"}),
        ("Grep", {"pattern": "x", "glob": "*.pem"}),
        ("Glob", {"pattern": "**/*.keystore"}),
    ],
)
def test_blocks_file_tools(tool, inp):
    assert guard.check({"tool_name": tool, "tool_input": inp}) is not None


@pytest.mark.parametrize(
    "tool,inp",
    [
        ("Read", {"file_path": "/repo/src/vd98/settings.py"}),
        ("Read", {"file_path": "/repo/.env.example"}),
        ("Grep", {"pattern": "password", "path": "/repo/src"}),
        ("Glob", {"pattern": "**/*.py"}),
    ],
)
def test_allows_file_tools(tool, inp):
    assert guard.check({"tool_name": tool, "tool_input": inp}) is None


def run_hook(payload):
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def test_hook_process_exit_2_with_reason_on_block():
    res = run_hook({"tool_name": "Bash", "tool_input": {"command": "git add -A"}})
    assert res.returncode == 2
    assert "git add -A" in res.stderr or "stage" in res.stderr


def test_hook_process_exit_0_when_allowed():
    res = run_hook({"tool_name": "Bash", "tool_input": {"command": "git status"}})
    assert res.returncode == 0, res.stderr


def test_hook_process_survives_garbage_input():
    res = subprocess.run(
        [sys.executable, str(HOOK)],
        input="not json",
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0
