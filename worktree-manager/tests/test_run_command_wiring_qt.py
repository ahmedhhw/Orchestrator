import time
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt

from worktree_manager.cli import App
from worktree_manager.main_window_vm import MainWindowViewModel
from worktree_manager.models import RepoConfig, WorktreeModel
from worktree_manager.ui.main_window import MainWindow
from worktree_manager.ui.command_center_panel import CommandCenterPanel
from worktree_manager.ui.launch_dialog import LaunchDialog


def _repo_cfg(path="/repos/proj"):
    return RepoConfig(
        repo_path=path, worktree_storage="/repos/proj-wt",
        stale_days=30, last_editor="cursor", last_editor_mode="reuse",
        last_opened="2026-05-19T10:00:00",
    )


def _make_vm():
    now = int(time.time())
    vm = MagicMock(spec=MainWindowViewModel)
    vm.load_worktrees.return_value = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
        WorktreeModel("/repos/proj-wt/feat-auth", "feat/auth", False, now - 3600, False, False),
    ]
    vm.list_branches_with_checkout_status.return_value = [
        ("main", True), ("feat/auth", True),
    ]
    return vm


def _make_window(qtbot, on_run_command=None):
    win = MainWindow(
        vm=_make_vm(),
        repo_name="proj",
        on_settings=lambda: None,
        on_cleanup=lambda: None,
        on_new=lambda: None,
        on_generate_project=lambda path: None,
        on_run_command=on_run_command or (lambda path: None),
    )
    qtbot.addWidget(win)
    return win


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

    return app, store


def test_main_window_context_menu_has_run_command_item(qtbot):
    win = _make_window(qtbot)
    menu = win._build_context_menu("/repos/proj-wt/feat-auth")
    action_texts = [a.text() for a in menu.actions()]
    assert any("Run Command" in t for t in action_texts)


def test_main_window_accepts_on_run_command_callback(qtbot):
    called = []
    win = _make_window(qtbot, on_run_command=lambda path: called.append(path))
    assert win._on_run_command is not None


def test_trigger_run_command_fires_callback_with_worktree_path(qtbot):
    called = []
    win = _make_window(qtbot, on_run_command=lambda path: called.append(path))
    win._trigger_run_command("/repos/proj-wt/feat-auth")
    assert called == ["/repos/proj-wt/feat-auth"]


def test_app_provides_on_run_command_to_right_pane(qtbot, monkeypatch):
    from worktree_manager.ui.worktree_management_panel import WorktreeManagementPanel
    app, _ = _make_app(qtbot, monkeypatch)
    assert isinstance(app._current_panel, WorktreeManagementPanel)
    right_pane = app._current_panel._right_pane
    assert right_pane is not None
    assert right_pane._on_run_command is not None


def test_on_run_command_opens_launch_dialog_with_locked_repo_and_worktree(qtbot, monkeypatch):
    app, _ = _make_app(qtbot, monkeypatch)

    with patch("worktree_manager.cli.LaunchDialog") as MockDlg:
        MockDlg.return_value.exec.return_value = None
        app._on_run_command("/repos/proj-wt/feat-auth")

    MockDlg.assert_called_once()
    kwargs = MockDlg.call_args.kwargs
    assert kwargs["locked_worktree_path"] == "/repos/proj-wt/feat-auth"
    assert kwargs["locked_repo_path"] == "/repos/proj"


def test_launch_dialog_disables_repo_combo_when_locked(qtbot):
    vm = MagicMock()
    vm.all_repos.return_value = {"/repos/proj": MagicMock()}
    vm.get_last_used_repo.return_value = None
    vm.saved_commands.return_value = []
    vm.list_worktrees.return_value = []

    dlg = LaunchDialog(
        parent=None, vm=vm,
        locked_repo_path="/repos/proj",
        locked_worktree_path="/repos/proj-wt/feat-auth",
    )
    qtbot.addWidget(dlg)
    assert not dlg._repo_combo.isEnabled()
    assert not dlg._wt_combo.isEnabled()
