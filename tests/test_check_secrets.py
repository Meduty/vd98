"""scripts/check_secrets.py: effect-level commit check (SPEC V.12).

Fake credentials are assembled at runtime so this file itself never contains a
credential-shaped string (the CI `--all` scan reads it too).
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_secrets.py"
spec = importlib.util.spec_from_file_location("check_secrets", SCRIPT)
cs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cs)

FAKE = {
    "private key block": b"-----BEGIN " + b"RSA PRIVATE KEY-----\nMIIB\n",
    "GitHub token": b"token = gh" + b"p_" + b"A" * 36,
    "AWS access key id": b"AKIA" + b"ABCDEFGHIJKLMNOP",
    "JWT": b"eyJ" + b"a" * 12 + b".eyJ" + b"b" * 12 + b"." + b"c" * 12,
}


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        "config/.env.local",
        ".envrc",
        "secret/notes.txt",
        "a/secrets/x",
        "k.pem",
        "app.keystore",
        "id_ed25519",
    ],
)
def test_secret_names_rejected(path):
    assert cs.check([(path, b"")]), path


@pytest.mark.parametrize(
    "path",
    [".env.example", "src/vd98/settings.py", "id_rsa.pub", "docs/secret-handling.md"],
)
def test_ordinary_names_accepted(path):
    assert cs.check([(path, b"hello")]) == [], path


@pytest.mark.parametrize("label", sorted(FAKE))
def test_credential_shaped_content_rejected(label):
    problems = cs.check([("notes.md", FAKE[label])])
    assert problems == [f"notes.md: contains a {label}"]


def test_words_about_secrets_are_fine():
    text = b"Never commit .env or secret/ files; tokens live in the vault."
    assert cs.check([("README.md", text)]) == []


def test_report_never_contains_the_secret(tmp_path, monkeypatch, capsys):
    blob = FAKE["GitHub token"]
    monkeypatch.setattr(cs, "files_and_blobs", lambda staged: [("leak.txt", blob)])
    assert cs.main(["check_secrets.py", "--staged"]) == 1
    err = capsys.readouterr().err
    assert "leak.txt" in err
    assert blob.decode().split("= ")[1] not in err


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def test_staged_mode_checks_the_staged_blob(tmp_path):
    """git add -f of an ignored key file is caught, however it was staged."""
    git(tmp_path, "init", "-q")
    (tmp_path / ".gitignore").write_text("*.pem\n")
    (tmp_path / "ok.txt").write_text("fine")
    (tmp_path / "server.pem").write_bytes(FAKE["private key block"])
    git(tmp_path, "add", "ok.txt", ".gitignore")
    git(tmp_path, "add", "-f", "server.pem")
    res = subprocess.run(
        [sys.executable, str(SCRIPT), "--staged"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 1
    assert "server.pem" in res.stderr
    assert "MIIB" not in res.stderr


def test_whole_repo_is_clean():
    """The repo itself passes the CI scan (this file included)."""
    res = subprocess.run(
        [sys.executable, str(SCRIPT), "--all"],
        cwd=SCRIPT.parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, res.stderr
