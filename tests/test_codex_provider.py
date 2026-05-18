"""CodexProvider wiring tests.

We cannot install the real codex CLI in CI (subscription auth, network
policy), so these tests mock subprocess.run to verify CodexProvider:
- builds the right argv from CodexConfig
- pipes the prompt via stdin (not argv) so Windows multi-line works
- bubbles non-zero exits with a useful error
- respects env-var overrides for binary / model / extra args
- gracefully reports FileNotFoundError when codex isn't installed
"""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from forge.llm.codex import CodexConfig, CodexProvider
from forge.llm.provider import Message


def _fake_run(stdout: str = "```java\nclass X {}\n```", returncode: int = 0):
    """Build a fake subprocess.run that captures the call and returns canned output."""
    captured: dict = {}

    def fake(cmd, **kw):
        captured["cmd"] = cmd
        captured["input"] = kw.get("input")
        captured["timeout"] = kw.get("timeout")
        return subprocess.CompletedProcess(
            args=cmd, returncode=returncode, stdout=stdout, stderr=""
        )

    return fake, captured


def test_codex_pipes_prompt_via_stdin_not_argv():
    fake, captured = _fake_run()
    provider = CodexProvider(CodexConfig(binary="codex"))
    with patch("forge.llm.codex.subprocess.run", fake), \
         patch("forge.llm.codex.shutil.which", return_value="/usr/bin/codex"):
        resp = provider.complete([Message(role="user", content="migrate this code")])

    # Prompt must be on stdin, not in argv. Windows multi-line quoting is a
    # nightmare if we put it on the command line.
    assert captured["input"] == "migrate this code"
    assert "migrate this code" not in " ".join(captured["cmd"])
    # Subcommand + model flag should be present.
    assert captured["cmd"][0] == "/usr/bin/codex"
    assert "exec" in captured["cmd"]
    assert "--model" in captured["cmd"]
    assert "gpt-5-codex" in captured["cmd"]
    # stdout flows through verbatim.
    assert "class X" in resp.text


def test_codex_nonzero_exit_raises_with_context():
    fake, _ = _fake_run(stdout="", returncode=2)
    fake_with_stderr = lambda cmd, **kw: subprocess.CompletedProcess(  # noqa: E731
        args=cmd, returncode=2, stdout="", stderr="auth failed: not logged in"
    )
    provider = CodexProvider(CodexConfig(binary="codex"))
    with patch("forge.llm.codex.subprocess.run", fake_with_stderr), \
         patch("forge.llm.codex.shutil.which", return_value="/usr/bin/codex"):
        with pytest.raises(RuntimeError, match="codex exited 2"):
            provider.complete([Message(role="user", content="x")])


def test_codex_missing_binary_message_points_to_windows_hint():
    def fake_missing(*a, **kw):
        raise FileNotFoundError("codex")

    provider = CodexProvider(CodexConfig(binary="codex"))
    with patch("forge.llm.codex.subprocess.run", fake_missing), \
         patch("forge.llm.codex.shutil.which", return_value=None):
        with pytest.raises(RuntimeError, match="FORGE_CODEX_BIN"):
            provider.complete([Message(role="user", content="x")])


def test_codex_env_var_overrides(monkeypatch):
    monkeypatch.setenv("FORGE_CODEX_BIN", "codex.cmd")
    monkeypatch.setenv("FORGE_CODEX_MODEL", "gpt-9-future")
    monkeypatch.setenv("FORGE_CODEX_EXTRA", "--skip-git-repo-check --color=never")
    monkeypatch.setenv("FORGE_CODEX_SUBCMD", "run --batch")

    cfg = CodexConfig()
    assert cfg.binary == "codex.cmd"
    assert cfg.model == "gpt-9-future"
    assert cfg.extra_args == ("--skip-git-repo-check", "--color=never")
    assert cfg.subcommand == ("run", "--batch")

    fake, captured = _fake_run()
    provider = CodexProvider(cfg)
    with patch("forge.llm.codex.subprocess.run", fake), \
         patch("forge.llm.codex.shutil.which", return_value="C:\\bin\\codex.cmd"):
        provider.complete([Message(role="user", content="x")])

    cmd_str = " ".join(captured["cmd"])
    assert "C:\\bin\\codex.cmd" in cmd_str
    assert "run" in captured["cmd"]
    assert "--batch" in captured["cmd"]
    assert "gpt-9-future" in captured["cmd"]
    assert "--skip-git-repo-check" in captured["cmd"]


def test_codex_dropping_model_flag(monkeypatch):
    """Some codex versions don't accept --model. Setting FORGE_CODEX_MODEL_FLAG=''
    removes the flag entirely without the user having to subclass."""
    monkeypatch.setenv("FORGE_CODEX_MODEL_FLAG", "")
    cfg = CodexConfig()
    assert cfg.model_flag == ""

    fake, captured = _fake_run()
    provider = CodexProvider(cfg)
    with patch("forge.llm.codex.subprocess.run", fake), \
         patch("forge.llm.codex.shutil.which", return_value="/usr/bin/codex"):
        provider.complete([Message(role="user", content="x")])

    assert "--model" not in captured["cmd"]


def test_codex_single_user_message_passes_content_verbatim():
    """A solo user message must not get wrapped in `[user]` headers — the
    codex CLI should see exactly what the agent rendered."""
    fake, captured = _fake_run()
    provider = CodexProvider(CodexConfig(binary="codex"))
    with patch("forge.llm.codex.subprocess.run", fake), \
         patch("forge.llm.codex.shutil.which", return_value="/usr/bin/codex"):
        provider.complete([Message(role="user", content="migrate File.java to Java 21")])

    assert captured["input"] == "migrate File.java to Java 21"


def test_codex_multi_message_includes_role_headers():
    """Repair loop sends user + assistant + user. The CLI is single-prompt,
    so we flatten with `[role]` headers so the model can see the turn shape."""
    fake, captured = _fake_run()
    provider = CodexProvider(CodexConfig(binary="codex"))
    with patch("forge.llm.codex.subprocess.run", fake), \
         patch("forge.llm.codex.shutil.which", return_value="/usr/bin/codex"):
        provider.complete([
            Message(role="user", content="first prompt"),
            Message(role="assistant", content="bad response"),
            Message(role="user", content="please retry with a fenced block"),
        ])

    text = captured["input"]
    assert "[user]" in text
    assert "[assistant]" in text
    assert "first prompt" in text
    assert "please retry" in text
