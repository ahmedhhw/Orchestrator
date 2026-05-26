from unittest.mock import MagicMock, patch, call

import pytest

from worktree_manager.cli import App
from worktree_manager.command_runner import RunHandle, RunStatus
from worktree_manager.models import RepoConfig
from worktree_manager.ui.command_center_panel import CommandCenterPanel


def _repo_cfg(path="/repos/proj"):
    return RepoConfig(
        repo_path=path, worktree_storage="/repos/proj-wt",
        stale_days=30, last_editor="cursor", last_editor_mode="reuse",
        last_opened="2026-05-19T10:00:00",
    )


def _make_app(qtbot, monkeypatch):
    store = MagicMock()
    cfg = _repo_cfg()
    store.all_repos.return_value = {"/repos/proj": cfg}
    store.get_repo.return_value = cfg
    store.get_ui_pref.side_effect = lambda key, default=None: default
    store.all_projects.return_value = []
    monkeypatch.setattr("worktree_manager.cli.ConfigStore", lambda *a, **kw: store)
    monkeypatch.setattr("worktree_manager.cli.GitService", lambda *a, **kw: MagicMock())

    with patch("worktree_manager.main_window_vm.MainWindowViewModel") as MockVM:
        MockVM.return_value.load_worktrees.return_value = []
        MockVM.return_value.list_branches_with_checkout_status.return_value = []
        app = App(repo_path="/repos/proj")
        qtbot.addWidget(app)

    return app


def _handle(cmd_name="my-cmd", status=RunStatus.STOPPED, returncode=0):
    h = RunHandle(
        run_id="run-1", cmd_name=cmd_name,
        repo_path="/repos/proj", repo_name="proj",
        worktree_path="/repos/proj", command="echo hi",
    )
    h.status = status
    h.returncode = returncode
    return h


def test_notification_fires_when_command_center_not_visible(qtbot, monkeypatch):
    app = _make_app(qtbot, monkeypatch)
    # Command Center is not the current panel
    assert not isinstance(app._current_panel, CommandCenterPanel)

    shown = []
    with patch.object(app, "_show_notification", side_effect=lambda t, b: shown.append((t, b))):
        app._on_command_finished("run-1", _handle(status=RunStatus.STOPPED, returncode=0))

    assert len(shown) == 1


def test_notification_not_fired_when_command_center_is_visible(qtbot, monkeypatch):
    app = _make_app(qtbot, monkeypatch)
    app._show_command_center()
    assert isinstance(app._current_panel, CommandCenterPanel)

    shown = []
    with patch.object(app, "_show_notification", side_effect=lambda t, b: shown.append((t, b))):
        app._on_command_finished("run-1", _handle(status=RunStatus.STOPPED, returncode=0))

    assert shown == []


def test_finished_notification_message(qtbot, monkeypatch):
    app = _make_app(qtbot, monkeypatch)
    shown = []
    with patch.object(app, "_show_notification", side_effect=lambda t, b: shown.append((t, b))):
        app._on_command_finished("run-1", _handle(cmd_name="my-cmd", status=RunStatus.STOPPED, returncode=0))
    assert "my-cmd" in shown[0][1]
    assert "✅" in shown[0][1]


def test_error_notification_message(qtbot, monkeypatch):
    app = _make_app(qtbot, monkeypatch)
    shown = []
    with patch.object(app, "_show_notification", side_effect=lambda t, b: shown.append((t, b))):
        app._on_command_finished("run-1", _handle(cmd_name="my-cmd", status=RunStatus.ERROR, returncode=2))
    assert "my-cmd" in shown[0][1]
    assert "❌" in shown[0][1]
    assert "2" in shown[0][1]


def test_cancelled_notification_message(qtbot, monkeypatch):
    app = _make_app(qtbot, monkeypatch)
    shown = []
    with patch.object(app, "_show_notification", side_effect=lambda t, b: shown.append((t, b))):
        app._on_command_finished("run-1", _handle(cmd_name="my-cmd", status=RunStatus.STOPPED, returncode=-15))
    assert "my-cmd" in shown[0][1]
    assert "⏹" in shown[0][1]


def test_notification_switches_to_command_center(qtbot, monkeypatch):
    app = _make_app(qtbot, monkeypatch)
    assert not isinstance(app._current_panel, CommandCenterPanel)

    with patch.object(app, "_show_notification"):
        app._on_command_finished("run-1", _handle())

    assert isinstance(app._current_panel, CommandCenterPanel)


def test_vm_on_finished_wired_after_show_command_center(qtbot, monkeypatch):
    app = _make_app(qtbot, monkeypatch)
    app._show_command_center()
    assert app._command_center_vm is not None
    assert app._command_center_vm.on_finished is not None
