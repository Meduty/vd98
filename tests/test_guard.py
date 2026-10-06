"""Tests for the PreToolUse hook after the effect-level redesign (SPEC V.12, V.19).

The hook no longer parses shell commands for secret reads. The bypass cases the
old text guard collected (globs, bash -lc, heredocs fed to interpreters, scripts
written then run, shell functions named cat, ...) are now effect tests in
scripts/sandbox_probe.sh, run inside the OS sandbox. Commits are checked by
scripts/check_secrets.py (tests/test_check_secrets.py).
"""

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
        "true | git add -A",
        "FOO=1 git add -A",
        "git status\ngit add -A",
        "true\ngit commit -am x",
    ],
)
def test_bulk_staging_nudged(cmd):
    assert bash(cmd) is not None, cmd


@pytest.mark.parametrize(
    "cmd",
    [
        "git add -- SPEC.md src/vd98/manager.py",
        "git add src/vd98/web/app.js",
        "git commit -m 'add -A flag docs'",
        "git commit -m 'all good' --amend",
        "git commit -F - <<'EOF'\nfix: untrack secret/ and .env\nEOF",
        "git status",
        "uv run pytest -q",
    ],
)
def test_explicit_staging_allowed(cmd):
    assert bash(cmd) is None, cmd


@pytest.mark.parametrize(
    "cmd",
    [
        "cat > review/prompt.md <<'EOF'\nNever read secret/ or .env; ask the user.\nEOF",
        "echo 'keep the secret out of git'",
        "python3 - <<'EOF'\nprint('secrets are never read')\nEOF",
        "git commit -m 'untrack .env and secret/'",
    ],
)
def test_prose_naming_secret_paths_is_never_blocked(cmd):
    """The text guard's main cost (8 of 12 real blocks) is gone with the parser."""
    assert bash(cmd) is None, cmd


def test_shell_secret_reads_are_the_sandboxes_job():
    """By design the hook does not judge shell reads; the OS sandbox does.

    If this starts failing, someone re-added command parsing to the hook. Prefer
    adding a case to scripts/sandbox_probe.sh instead (SPEC V.12).
    """
    assert bash("cat .env") is None


@pytest.mark.parametrize(
    "tool,inp",
    [
        ("Read", {"file_path": "/repo/.env"}),
        ("Read", {"file_path": "/repo/.envrc"}),
        ("Read", {"file_path": "/repo/secret/app.jks"}),
        ("Edit", {"file_path": "/repo/certs/server.pem"}),
        ("Write", {"file_path": "/repo/.env.production"}),
        ("Grep", {"pattern": "x", "path": "/repo/secrets"}),
        ("Grep", {"pattern": "x", "glob": "*.pem"}),
        ("Glob", {"pattern": "**/*.keystore"}),
        ("NotebookEdit", {"notebook_path": "/repo/secret/n.ipynb"}),
    ],
)
def test_file_tools_on_secret_paths_blocked(tool, inp):
    assert guard.check({"tool_name": tool, "tool_input": inp}) is not None


@pytest.mark.parametrize(
    "tool,inp",
    [
        ("Read", {"file_path": "/repo/src/vd98/settings.py"}),
        ("Read", {"file_path": "/repo/.env.example"}),
        ("Read", {"file_path": "/repo/id_rsa.pub"}),
        ("Read", {"file_path": "/repo/docs/secret-handling.md"}),
        ("Grep", {"pattern": "secret", "path": "/repo/src"}),
        ("Glob", {"pattern": "**/*.py"}),
    ],
)
def test_file_tools_on_ordinary_paths_allowed(tool, inp):
    assert guard.check({"tool_name": tool, "tool_input": inp}) is None


def run_hook(payload):
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload if isinstance(payload, str) else json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def test_hook_process_exit_2_with_hint_on_block():
    res = run_hook({"tool_name": "Bash", "tool_input": {"command": "git add -A"}})
    assert res.returncode == 2
    assert "explicit paths" in res.stderr
    assert "stop and ask" in res.stderr


def test_hook_process_exit_0_when_allowed():
    res = run_hook({"tool_name": "Bash", "tool_input": {"command": "git status"}})
    assert res.returncode == 0, res.stderr


def test_hook_process_survives_garbage_input():
    assert run_hook("not json").returncode == 0


# PR #2 review round 1 (2026-10-06)
@pytest.mark.parametrize(
    "tool,inp",
    [
        ("Grep", {"pattern": "x", "path": "/repo", "glob": "*.p?x"}),
        ("Grep", {"pattern": "x", "path": "/repo", "glob": "*.[pk]e[my]"}),
        ("Glob", {"pattern": "**/*.kd?x"}),
        ("Glob", {"pattern": "**/.env*"}),
        ("Glob", {"pattern": "**/secr?t/*"}),
    ],
)
def test_file_tool_globs_that_can_match_secrets_blocked(tool, inp):
    """Finding 2: a masked extension glob slipped past the literal path check."""
    assert guard.check({"tool_name": tool, "tool_input": inp}) is not None


@pytest.mark.parametrize(
    "cmd",
    [
        "env git add -A",
        "sudo git add -A",
        "nice -n 5 git commit -am x",
        "git -c core.hooksPath=/tmp/empty commit -m x",
        "git -c core.hooksPath /tmp/empty commit -m x",
        "git commit --no-verify -m x",
        "git commit -n -m x",
    ],
)
def test_wrappers_and_hook_skips_nudged(cmd):
    """Findings 4 and 6: wrappers hid bulk staging; hooksPath / --no-verify skip pre-commit."""
    assert bash(cmd) is not None, cmd


# PR #3 review round 1, finding 4 (2026-10-06)
@pytest.mark.parametrize(
    "tool,inp",
    [
        ("Grep", {"pattern": "x", "path": "secret"}),
        ("Grep", {"pattern": "x", "path": "secrets"}),
        ("Glob", {"pattern": "*", "path": "secret"}),
        ("Read", {"file_path": "secrets"}),
    ],
)
def test_bare_relative_secret_dir_blocked(tool, inp):
    """A file-tool path is a path: bare `secret` (no slash) names the folder."""
    assert guard.check({"tool_name": tool, "tool_input": inp}) is not None


@pytest.mark.parametrize(
    "tool,inp",
    [
        ("Grep", {"pattern": "secret", "path": "src"}),
        ("Read", {"file_path": "docs/secret-handling.md"}),
        ("Glob", {"pattern": "secretary/*.py"}),
    ],
)
def test_words_that_only_contain_secret_allowed(tool, inp):
    assert guard.check({"tool_name": tool, "tool_input": inp}) is None


# PR #3 review round 2, finding 5 (SPEC B.35)
def test_symlink_to_secret_file_blocked(tmp_path):
    """A harmless-looking name that links to a secret file is the secret file."""
    (tmp_path / ".env").write_text("fake")
    (tmp_path / "notes.txt").symlink_to(tmp_path / ".env")
    payload = {
        "tool_name": "Read",
        "tool_input": {"file_path": "notes.txt"},
        "cwd": str(tmp_path),
    }
    assert guard.check(payload) is not None


def test_symlink_to_secret_dir_blocked(tmp_path):
    (tmp_path / "secrets").mkdir()
    (tmp_path / "docs").symlink_to(tmp_path / "secrets")
    payload = {
        "tool_name": "Grep",
        "tool_input": {"pattern": "x", "path": "docs"},
        "cwd": str(tmp_path),
    }
    assert guard.check(payload) is not None


def test_ordinary_symlink_allowed(tmp_path):
    (tmp_path / "real.txt").write_text("hi")
    (tmp_path / "link.txt").symlink_to(tmp_path / "real.txt")
    payload = {
        "tool_name": "Read",
        "tool_input": {"file_path": "link.txt"},
        "cwd": str(tmp_path),
    }
    assert guard.check(payload) is None


# PR #3 review round 2, finding 6 (SPEC B.36); PR #2 review round 2, finding 4 (B.37)
@pytest.mark.parametrize(
    "cmd",
    [
        (
            "GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0=/tmp/x"
            " git commit -m x"
        ),
        "GIT_CONFIG_PARAMETERS=\"'core.hooksPath'='/tmp/x'\" git commit -m x",
        "git config core.hooksPath /dev/null",
        "git config --local core.hooksPath /tmp/x",
        "git config --unset core.hooksPath",
    ],
)
def test_hookspath_overrides_nudged(cmd):
    assert bash(cmd) is not None, cmd


@pytest.mark.parametrize(
    "cmd",
    [
        "GIT_AUTHOR_NAME=x git commit -m 'msg'",
        "git config core.hooksPath .githooks",
        "git config --get core.hooksPath",
        "git config core.hooksPath",
        "git config user.name x",
    ],
)
def test_ordinary_config_and_env_allowed(cmd):
    assert bash(cmd) is None, cmd
