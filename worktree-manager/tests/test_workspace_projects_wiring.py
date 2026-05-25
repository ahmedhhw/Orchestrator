from unittest.mock import MagicMock, patch

from worktree_manager.cli import App
from worktree_manager.ui.workspace_projects_panel import WorkspaceProjectsPanel


def _make_app(qtbot):
    with (
        patch("worktree_manager.cli.ConfigStore") as MockStore,
        patch("worktree_manager.cli.GitService"),
    ):
        MockStore.return_value.get_repo.return_value = None
        app = App(repo_path=None)
        qtbot.addWidget(app)
    return app


def test_show_workspace_projects_creates_panel(qtbot):
    app = _make_app(qtbot)
    with (
        patch("worktree_manager.cli.WorkspaceProjectsViewModel") as MockVM,
        patch("worktree_manager.cli.WorkspaceService"),
    ):
        vm = MagicMock()
        vm.load_projects.return_value = []
        vm._store.get_ui_pref.side_effect = lambda key, default: default
        vm._store.all_repos.return_value = {}
        MockVM.return_value = vm
        app._show_workspace_projects()
    assert isinstance(app._current_panel, WorkspaceProjectsPanel)


def test_show_workspace_projects_close_returns_to_landing(qtbot):
    app = _make_app(qtbot)
    with (
        patch("worktree_manager.cli.WorkspaceProjectsViewModel") as MockVM,
        patch("worktree_manager.cli.WorkspaceService"),
    ):
        vm = MagicMock()
        vm.load_projects.return_value = []
        vm._store.get_ui_pref.side_effect = lambda key, default: default
        vm._store.all_repos.return_value = {}
        MockVM.return_value = vm
        app._show_workspace_projects()
    panel = app._current_panel
    panel.trigger_close()
    assert not isinstance(app._current_panel, WorkspaceProjectsPanel)
