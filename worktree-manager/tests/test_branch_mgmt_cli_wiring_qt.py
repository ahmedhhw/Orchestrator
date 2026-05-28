"""Tests for Iteration 1 cli.py wiring: BranchMgmtViewModel + deep-link."""
from unittest.mock import MagicMock, patch

from worktree_manager.cli import App
from worktree_manager.ui.branch_management_panel import BranchManagementPanel


@patch("worktree_manager.cli.ConfigStore")
@patch("worktree_manager.cli.GitService")
def _make_app(qtbot, MockGit, MockStore):
    MockStore.return_value.all_repos.return_value = {}
    MockStore.return_value.get_repo.return_value = None
    MockStore.return_value.get_ui_pref.side_effect = lambda k, d=None: d
    app = App(repo_path=None)
    qtbot.addWidget(app)
    return app


def test_show_branch_management_mounts_panel(qtbot):
    with (
        patch("worktree_manager.cli.ConfigStore") as MockStore,
        patch("worktree_manager.cli.GitService"),
    ):
        MockStore.return_value.all_repos.return_value = {}
        MockStore.return_value.get_repo.return_value = None
        MockStore.return_value.get_ui_pref.side_effect = lambda k, d=None: d
        app = App(repo_path=None)
        qtbot.addWidget(app)

    app._show_branch_management()
    assert isinstance(app._current_panel, BranchManagementPanel)


def test_show_branch_management_passes_vm(qtbot):
    with (
        patch("worktree_manager.cli.ConfigStore") as MockStore,
        patch("worktree_manager.cli.GitService"),
    ):
        MockStore.return_value.all_repos.return_value = {}
        MockStore.return_value.get_repo.return_value = None
        MockStore.return_value.get_ui_pref.side_effect = lambda k, d=None: d
        app = App(repo_path=None)
        qtbot.addWidget(app)

    app._show_branch_management()
    # The panel should have a _vm (BranchMgmtViewModel)
    assert app._current_panel._vm is not None


def test_show_cleanup_for_repo_mounts_branch_management_panel(qtbot):
    with (
        patch("worktree_manager.cli.ConfigStore") as MockStore,
        patch("worktree_manager.cli.GitService"),
    ):
        MockStore.return_value.all_repos.return_value = {"/repo/a": MagicMock(stale_days=30)}
        MockStore.return_value.get_repo.return_value = MagicMock(stale_days=30)
        MockStore.return_value.get_ui_pref.side_effect = lambda k, d=None: d
        app = App(repo_path=None)
        qtbot.addWidget(app)

    with patch.object(
        app,
        "_show_cleanup_for_repo",
        wraps=app._show_cleanup_for_repo,
    ):
        with patch(
            "worktree_manager.branch_mgmt_vm.MainWindowViewModel"
        ) as MockVM:
            MockVM.return_value.load_worktrees.return_value = []
            MockVM.return_value.all_cleanup_candidates.return_value = []
            MockVM.return_value.list_repos = MagicMock(return_value=["/repo/a"])
            app._show_cleanup_for_repo("/repo/a")

    assert isinstance(app._current_panel, BranchManagementPanel)


def test_show_cleanup_for_repo_activates_cleanup_section(qtbot):
    with (
        patch("worktree_manager.cli.ConfigStore") as MockStore,
        patch("worktree_manager.cli.GitService"),
    ):
        MockStore.return_value.all_repos.return_value = {"/repo/a": MagicMock(stale_days=30)}
        MockStore.return_value.get_repo.return_value = MagicMock(stale_days=30)
        MockStore.return_value.get_ui_pref.side_effect = lambda k, d=None: d
        app = App(repo_path=None)
        qtbot.addWidget(app)

    with patch(
        "worktree_manager.branch_mgmt_vm.MainWindowViewModel"
    ) as MockVM:
        MockVM.return_value.load_worktrees.return_value = []
        MockVM.return_value.all_cleanup_candidates.return_value = []
        app._show_cleanup_for_repo("/repo/a")

    from PySide6.QtWidgets import QPushButton
    panel = app._current_panel
    cleanup_btn = next(
        (b for b in panel.findChildren(QPushButton) if b.text() == "Cleanup"),
        None,
    )
    assert cleanup_btn is not None
    assert cleanup_btn.isChecked()
