import os
import signal
import pytest
from unittest.mock import patch
from worktree_manager.models import WindowRecord
from worktree_manager.window_registry import WindowRegistry


def test_window_record_fields():
    rec = WindowRecord(
        repo_path="/repos/proj",
        worktree_path="/repos/proj-wt/feat",
        editor="cursor",
        pid=12345,
    )
    assert rec.repo_path == "/repos/proj"
    assert rec.worktree_path == "/repos/proj-wt/feat"
    assert rec.editor == "cursor"
    assert rec.pid == 12345


def test_register_and_get_window():
    reg = WindowRegistry()
    reg.register("/repos/proj", "/repos/proj-wt/feat", pid=42, editor="cursor")
    rec = reg.get_window("/repos/proj", "/repos/proj-wt/feat")
    assert rec is not None
    assert rec.pid == 42
    assert rec.editor == "cursor"


def test_get_window_returns_none_for_unknown():
    reg = WindowRegistry()
    assert reg.get_window("/repos/proj", "/repos/proj-wt/unknown") is None


def test_is_alive_true_when_process_exists():
    reg = WindowRegistry()
    reg.register("/repos/proj", "/repos/proj-wt/feat", pid=42, editor="cursor")
    rec = reg.get_window("/repos/proj", "/repos/proj-wt/feat")
    with patch("os.kill") as mock_kill:
        mock_kill.return_value = None
        assert reg.is_alive(rec) is True
        mock_kill.assert_called_once_with(42, 0)


def test_is_alive_false_when_process_gone():
    reg = WindowRegistry()
    reg.register("/repos/proj", "/repos/proj-wt/feat", pid=99999, editor="cursor")
    rec = reg.get_window("/repos/proj", "/repos/proj-wt/feat")
    with patch("os.kill", side_effect=OSError):
        assert reg.is_alive(rec) is False


def test_prune_removes_dead_entries():
    reg = WindowRegistry()
    reg.register("/repos/proj", "/repos/proj-wt/feat", pid=42, editor="cursor")
    reg.register("/repos/proj", "/repos/proj-wt/fix", pid=43, editor="vscode")

    def fake_kill(pid, sig):
        if pid == 43:
            raise OSError

    with patch("os.kill", side_effect=fake_kill):
        reg.prune()
    assert reg.get_window("/repos/proj", "/repos/proj-wt/feat") is not None
    assert reg.get_window("/repos/proj", "/repos/proj-wt/fix") is None


def test_all_for_repo_returns_only_that_repo():
    reg = WindowRegistry()
    reg.register("/repos/proj", "/repos/proj-wt/feat", pid=1, editor="cursor")
    reg.register("/repos/other", "/repos/other-wt/fix", pid=2, editor="vscode")
    with patch("os.kill", return_value=None):
        results = reg.all_for_repo("/repos/proj")
    assert len(results) == 1
    assert results[0].pid == 1


def test_all_for_repo_excludes_dead_entries():
    reg = WindowRegistry()
    reg.register("/repos/proj", "/repos/proj-wt/feat", pid=1, editor="cursor")
    reg.register("/repos/proj", "/repos/proj-wt/fix", pid=2, editor="vscode")

    def fake_kill(pid, sig):
        if pid == 2:
            raise OSError

    with patch("os.kill", side_effect=fake_kill):
        results = reg.all_for_repo("/repos/proj")
    assert len(results) == 1
    assert results[0].pid == 1


def test_register_overwrites_existing_entry():
    reg = WindowRegistry()
    reg.register("/repos/proj", "/repos/proj-wt/feat", pid=1, editor="cursor")
    reg.register("/repos/proj", "/repos/proj-wt/feat", pid=2, editor="vscode")
    rec = reg.get_window("/repos/proj", "/repos/proj-wt/feat")
    assert rec.pid == 2
    assert rec.editor == "vscode"


def test_close_sends_sigterm():
    reg = WindowRegistry()
    reg.register("/repos/proj", "/repos/proj-wt/feat", pid=42, editor="cursor")
    rec = reg.get_window("/repos/proj", "/repos/proj-wt/feat")
    with patch("os.kill") as mock_kill:
        reg.close(rec)
        mock_kill.assert_called_once_with(42, signal.SIGTERM)


def test_close_ignores_already_dead_process():
    reg = WindowRegistry()
    reg.register("/repos/proj", "/repos/proj-wt/feat", pid=42, editor="cursor")
    rec = reg.get_window("/repos/proj", "/repos/proj-wt/feat")
    with patch("os.kill", side_effect=OSError):
        reg.close(rec)  # must not raise
