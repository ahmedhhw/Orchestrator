import time
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QDialog

from worktree_manager.models import RepoConfig, WorktreeModel


@pytest.fixture
def empty_store(monkeypatch):
    store = MagicMock()
    store.all_repos.return_value = {}
    store.get_ui_pref.side_effect = lambda key, default=None: default
    monkeypatch.setattr("worktree_manager.cli.ConfigStore", lambda *a, **kw: store)
    monkeypatch.setattr("worktree_manager.cli.GitService", lambda *a, **kw: MagicMock())
    return store


def _mock_vm(monkeypatch, worktrees=None, branch_status=None):
    vm = MagicMock()
    vm.load_worktrees.return_value = worktrees or []
    vm.list_branches_with_checkout_status.return_value = branch_status or []
    vm.is_protected_branch.return_value = False
    vm.has_uncommitted_changes.return_value = False
    monkeypatch.setattr(
        "worktree_manager.main_window_vm.MainWindowViewModel",
        lambda *a, **kw: vm,
    )
    return vm


def test_app_load_repo_unconfigured_opens_repo_setup_dialog(qtbot, empty_store):
    from worktree_manager.cli import App
    empty_store.get_repo.return_value = None
    app = App(repo_path=None)
    qtbot.addWidget(app)
    with patch("worktree_manager.cli.RepoSetupDialog") as MockDlg:
        instance = MagicMock(spec=QDialog)
        MockDlg.return_value = instance
        app._load_repo("/repos/new-repo")
    MockDlg.assert_called_once()
    instance.exec.assert_called_once()


def test_app_show_settings_opens_settings_dialog(qtbot, empty_store):
    from worktree_manager.cli import App
    cfg = RepoConfig(
        repo_path="/repos/p", worktree_storage="/repos/p-wt",
        stale_days=30, last_editor="cursor", last_editor_mode="reuse",
        last_opened="2026-05-19T10:00:00",
    )
    empty_store.get_repo.return_value = cfg
    app = App(repo_path=None)
    qtbot.addWidget(app)
    with patch("worktree_manager.cli.SettingsDialog") as MockDlg:
        instance = MagicMock(spec=QDialog)
        MockDlg.return_value = instance
        app._show_settings("/repos/p")
    MockDlg.assert_called_once()
    instance.exec.assert_called_once()


def test_app_show_new_worktree_opens_create_dialog(qtbot, empty_store, monkeypatch):
    from worktree_manager.cli import App
    vm = _mock_vm(monkeypatch)
    vm.list_local_branches.return_value = ["main", "feature/x"]
    vm.list_available_branches.return_value = ["feature/x"]
    app = App(repo_path=None)
    qtbot.addWidget(app)
    with patch("worktree_manager.cli.CreateDialog") as MockDlg:
        instance = MagicMock(spec=QDialog)
        MockDlg.return_value = instance
        app._show_new_worktree(vm)
    MockDlg.assert_called_once()
    instance.exec.assert_called_once()


def test_app_create_dialog_callback_invokes_vm_create_and_refreshes(
    qtbot, empty_store, monkeypatch,
):
    from worktree_manager.cli import App
    vm = _mock_vm(monkeypatch)
    vm.list_local_branches.return_value = ["main"]
    vm.list_available_branches.return_value = []
    app = App(repo_path=None)
    qtbot.addWidget(app)
    captured = {}

    def fake_dlg_ctor(parent, branches, existing_branches, on_create):
        captured["on_create"] = on_create
        d = MagicMock(spec=QDialog)
        return d

    with patch("worktree_manager.cli.CreateDialog", side_effect=fake_dlg_ctor):
        app._show_new_worktree(vm)
    captured["on_create"]("fix/x", "main", False, "fix-x")
    vm.create_worktree.assert_called_once_with(
        branch="fix/x", base_branch="main",
        existing=False, worktree_name="fix-x",
    )


def test_main_window_open_delete_opens_delete_dialog(qtbot, monkeypatch):
    from worktree_manager.ui.main_window import MainWindow
    vm = MagicMock()
    vm.load_worktrees.return_value = []
    vm.list_branches_with_checkout_status.return_value = []
    vm.is_protected_branch.return_value = False
    vm.has_uncommitted_changes.return_value = False
    win = MainWindow(vm=vm, repo_name="proj",
                     on_settings=lambda: None, on_cleanup=lambda: None,
                     on_new=lambda: None)
    qtbot.addWidget(win)
    wt = WorktreeModel(
        path="/r/proj-wt/fix-x", branch="fix/x", is_main=False,
        last_commit_ts=int(time.time()), is_merged=False, is_stale=False,
    )
    with patch("worktree_manager.ui.main_window.DeleteDialog") as MockDlg:
        instance = MagicMock(spec=QDialog)
        MockDlg.return_value = instance
        win._open_delete(wt)
    MockDlg.assert_called_once()
    kwargs = MockDlg.call_args.kwargs
    assert kwargs["wt"] is wt
    assert kwargs["is_protected"] is False
    assert kwargs["has_uncommitted"] is False
    instance.exec.assert_called_once()


def test_main_window_delete_dialog_callback_invokes_vm_delete_and_refreshes(
    qtbot, monkeypatch,
):
    from worktree_manager.ui.main_window import MainWindow
    vm = MagicMock()
    vm.load_worktrees.return_value = []
    vm.list_branches_with_checkout_status.return_value = []
    vm.is_protected_branch.return_value = False
    vm.has_uncommitted_changes.return_value = False
    win = MainWindow(vm=vm, repo_name="proj",
                     on_settings=lambda: None, on_cleanup=lambda: None,
                     on_new=lambda: None)
    qtbot.addWidget(win)
    wt = WorktreeModel(
        path="/r/proj-wt/fix-x", branch="fix/x", is_main=False,
        last_commit_ts=int(time.time()), is_merged=False, is_stale=False,
    )
    captured = {}

    def fake_dlg_ctor(parent, **kwargs):
        captured["on_delete"] = kwargs["on_delete"]
        return MagicMock(spec=QDialog)

    with patch("worktree_manager.ui.main_window.DeleteDialog",
               side_effect=fake_dlg_ctor):
        win._open_delete(wt)
    initial = vm.load_worktrees.call_count
    captured["on_delete"](wt, True)
    vm.delete_worktree.assert_called_once_with(
        path=wt.path, branch=wt.branch, also_delete_branch=True,
    )
    assert vm.load_worktrees.call_count > initial
