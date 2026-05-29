from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

from worktree_manager.ui.diff_panel import DiffPanel


def _make_app(qtbot):
    from worktree_manager.cli import App
    with patch("worktree_manager.cli.ConfigStore") as MockStore, \
         patch("worktree_manager.cli.GitService") as MockGit:
        store = MagicMock()
        store.all_repos.return_value = ["/repos/myapp"]
        store.all_projects.return_value = []
        store.get_ui_pref.return_value = "cursor"
        MockStore.return_value = store

        git = MagicMock()
        git.is_valid_repo.return_value = True
        git.list_worktrees.return_value = []
        git.list_local_branches.return_value = ["main"]
        git.list_points.return_value = []
        git.diff_files.return_value = []
        MockGit.return_value = git

        app = App()
        qtbot.addWidget(app)
    return app


def test_clicking_diff_tab_shows_diff_panel(qtbot):
    app = _make_app(qtbot)
    diff_btn = next(
        b for b in app._sidebar.findChildren(QPushButton) if "Diff" in b.text()
    )
    qtbot.mouseClick(diff_btn, Qt.LeftButton)
    assert isinstance(app._current_panel, DiffPanel)


def test_diff_panel_is_cached_across_visits(qtbot):
    app = _make_app(qtbot)
    diff_btn = next(
        b for b in app._sidebar.findChildren(QPushButton) if "Diff" in b.text()
    )
    qtbot.mouseClick(diff_btn, Qt.LeftButton)
    first = app._current_panel
    qtbot.mouseClick(
        next(b for b in app._sidebar.findChildren(QPushButton) if "Projects" in b.text()),
        Qt.LeftButton,
    )
    qtbot.mouseClick(diff_btn, Qt.LeftButton)
    assert app._current_panel is first


def test_diff_tab_is_highlighted_after_click(qtbot):
    app = _make_app(qtbot)
    diff_btn = next(
        b for b in app._sidebar.findChildren(QPushButton) if "Diff" in b.text()
    )
    qtbot.mouseClick(diff_btn, Qt.LeftButton)
    assert diff_btn.property("active_tab") is True
