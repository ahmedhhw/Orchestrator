from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

from worktree_manager.cli import App
from worktree_manager.ui.command_center_panel import CommandCenterPanel


def _make_app(qtbot):
    with (
        patch("worktree_manager.cli.ConfigStore") as MockStore,
        patch("worktree_manager.cli.GitService"),
    ):
        MockStore.return_value.get_repo.return_value = None
        app = App(repo_path=None)
        qtbot.addWidget(app)
    return app


def test_show_command_center_creates_panel(qtbot):
    app = _make_app(qtbot)
    with patch("worktree_manager.cli.CommandCenterViewModel") as MockVM:
        mock_vm = MagicMock()
        mock_vm.all_runs.return_value = []
        mock_vm.all_repos.return_value = {}
        MockVM.return_value = mock_vm
        app._show_command_center()
    assert isinstance(app._current_panel, CommandCenterPanel)


def test_show_command_center_reuses_existing_vm(qtbot):
    app = _make_app(qtbot)
    with patch("worktree_manager.cli.CommandCenterViewModel") as MockVM:
        mock_vm = MagicMock()
        mock_vm.all_runs.return_value = []
        mock_vm.all_repos.return_value = {}
        MockVM.return_value = mock_vm
        app._show_command_center()
        app._show_command_center()
    assert MockVM.call_count == 1


def test_show_command_center_close_removes_panel(qtbot):
    app = _make_app(qtbot)
    with patch("worktree_manager.cli.CommandCenterViewModel") as MockVM:
        mock_vm = MagicMock()
        mock_vm.all_runs.return_value = []
        mock_vm.all_repos.return_value = {}
        MockVM.return_value = mock_vm
        app._show_command_center()
    panel = app._current_panel
    assert isinstance(panel, CommandCenterPanel)
    panel.trigger_close()
    assert app._current_panel is None or not isinstance(app._current_panel, CommandCenterPanel)
