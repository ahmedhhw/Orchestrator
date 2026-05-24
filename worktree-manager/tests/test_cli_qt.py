import sys
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QMainWindow

from worktree_manager.cli import App, parse_args, resolve_repo_path
from worktree_manager.git_service import GitService


# ── parse_args / resolve_repo_path ──────────────────────────────────────────

def test_parse_args_no_argument():
    args = parse_args([])
    assert args.repo_path is None


def test_parse_args_with_path():
    args = parse_args(["/repos/proj"])
    assert args.repo_path == "/repos/proj"


def test_resolve_repo_path_valid(tmp_path):
    git = MagicMock(spec=GitService)
    git.is_valid_repo.return_value = True
    repo = tmp_path / "myrepo"
    repo.mkdir()
    assert resolve_repo_path(str(repo), git) == str(repo)


def test_resolve_repo_path_invalid(tmp_path, capsys):
    git = MagicMock(spec=GitService)
    git.is_valid_repo.return_value = False
    with pytest.raises(SystemExit):
        resolve_repo_path(str(tmp_path / "no"), git)
    assert "not a git repository" in capsys.readouterr().err.lower()


def test_resolve_repo_path_none_returns_none():
    assert resolve_repo_path(None, MagicMock(spec=GitService)) is None


# ── App: QMainWindow wiring ──────────────────────────────────────────────────

@pytest.fixture
def empty_store(monkeypatch):
    store = MagicMock()
    store.all_repos.return_value = {}
    store.get_ui_pref.side_effect = lambda key, default=None: default
    monkeypatch.setattr("worktree_manager.cli.ConfigStore", lambda *a, **kw: store)
    monkeypatch.setattr("worktree_manager.cli.GitService", lambda *a, **kw: MagicMock())
    return store


def test_app_is_qmainwindow(qtbot, empty_store):
    app = App(repo_path=None)
    qtbot.addWidget(app)
    assert isinstance(app, QMainWindow)


def test_app_window_title_set(qtbot, empty_store):
    app = App(repo_path=None)
    qtbot.addWidget(app)
    assert "Worktree Manager" in app.windowTitle()


def test_app_shows_landing_when_no_repo(qtbot, empty_store):
    from worktree_manager.ui.landing_screen import LandingScreen
    app = App(repo_path=None)
    qtbot.addWidget(app)
    assert isinstance(app._current_panel, LandingScreen)


def test_app_sidebar_present_when_no_repo(qtbot, empty_store):
    from worktree_manager.ui.sidebar import Sidebar
    app = App(repo_path=None)
    qtbot.addWidget(app)
    assert isinstance(app._sidebar, Sidebar)


def test_app_loads_main_window_when_repo_configured(qtbot, empty_store):
    from worktree_manager.models import RepoConfig
    from worktree_manager.ui.main_window import MainWindow

    cfg = RepoConfig(
        repo_path="/repos/proj", worktree_storage="/repos/proj-wt",
        stale_days=30, last_editor="cursor", last_editor_mode="reuse",
        last_opened="2026-05-19T10:00:00",
    )
    empty_store.get_repo.return_value = cfg
    empty_store.all_repos.return_value = {"/repos/proj": cfg}

    with patch("worktree_manager.main_window_vm.MainWindowViewModel") as MockVM:
        MockVM.return_value.load_worktrees.return_value = []
        MockVM.return_value.list_branches_with_checkout_status.return_value = []
        app = App(repo_path="/repos/proj")
        qtbot.addWidget(app)
        assert isinstance(app._current_panel, MainWindow)


def test_app_pick_repo_uses_qfiledialog(qtbot, empty_store):
    app = App(repo_path=None)
    qtbot.addWidget(app)
    with patch("PySide6.QtWidgets.QFileDialog.getExistingDirectory",
               return_value="") as mock_dlg:
        app._pick_and_add_repo()
    mock_dlg.assert_called_once()


def test_app_pick_repo_rejects_non_git_with_messagebox(qtbot, empty_store, tmp_path):
    app = App(repo_path=None)
    qtbot.addWidget(app)
    app._git.is_valid_repo = MagicMock(return_value=False)
    with patch("PySide6.QtWidgets.QFileDialog.getExistingDirectory",
               return_value=str(tmp_path)):
        with patch("PySide6.QtWidgets.QMessageBox.critical") as mock_err:
            app._pick_and_add_repo()
    mock_err.assert_called_once()


def test_app_confirm_delete_repo_yes_removes_from_store(qtbot, empty_store):
    from worktree_manager.models import RepoConfig
    cfg = RepoConfig(
        repo_path="/repos/proj", worktree_storage="/repos/proj-wt",
        stale_days=30, last_editor="cursor", last_editor_mode="reuse",
        last_opened="2026-05-19T10:00:00",
    )
    empty_store.all_repos.return_value = {"/repos/proj": cfg}
    app = App(repo_path=None)
    qtbot.addWidget(app)
    from PySide6.QtWidgets import QMessageBox
    with patch("PySide6.QtWidgets.QMessageBox.question",
               return_value=QMessageBox.Yes):
        app._confirm_delete_repo("/repos/proj", is_active=False)
    empty_store.delete_repo.assert_called_once_with("/repos/proj")


def test_app_confirm_delete_repo_no_keeps_store_intact(qtbot, empty_store):
    app = App(repo_path=None)
    qtbot.addWidget(app)
    from PySide6.QtWidgets import QMessageBox
    with patch("PySide6.QtWidgets.QMessageBox.question",
               return_value=QMessageBox.No):
        app._confirm_delete_repo("/repos/proj", is_active=False)
    empty_store.delete_repo.assert_not_called()


def test_app_show_command_center_is_stubbed_no_crash(qtbot, empty_store):
    app = App(repo_path=None)
    qtbot.addWidget(app)
    with patch("PySide6.QtWidgets.QMessageBox.information"):
        app._show_command_center()


def test_app_show_workspace_projects_is_stubbed_no_crash(qtbot, empty_store):
    app = App(repo_path=None)
    qtbot.addWidget(app)
    with patch("PySide6.QtWidgets.QMessageBox.information"):
        app._show_workspace_projects()
