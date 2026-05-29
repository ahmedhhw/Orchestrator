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


def test_diff_from_working_tree_switches_to_diff_tab(qtbot):
    app = _make_app(qtbot)
    app._diff_from_working_tree("/repos/myapp")
    assert isinstance(app._current_panel, DiffPanel)


def test_diff_from_working_tree_sets_repo_in_panel(qtbot):
    app = _make_app(qtbot)
    app._diff_from_working_tree("/repos/myapp")
    panel = app._current_panel
    assert panel._repo_combo.currentData() == "/repos/myapp"


def test_diff_from_working_tree_preselects_to_working_tree_unstaged(qtbot):
    app = _make_app(qtbot)
    app._git.list_points.return_value = [
        MagicMock(kind="working_tree_unstaged", label="Working tree (unstaged)", short_sha="", message=""),
    ]
    app._panel_cache.pop("diff", None)
    app._diff_from_working_tree("/repos/myapp")
    panel = app._current_panel
    from PySide6.QtCore import Qt
    to_item = panel._point_selector._to_list.currentItem()
    assert to_item is not None
    assert to_item.data(Qt.UserRole) == "working_tree_unstaged"


def test_diff_compare_branches_switches_to_diff_tab(qtbot):
    app = _make_app(qtbot)
    app._diff_compare_branches("/repos/myapp")
    assert isinstance(app._current_panel, DiffPanel)


def test_diff_compare_branches_sets_repo_in_panel(qtbot):
    app = _make_app(qtbot)
    app._diff_compare_branches("/repos/myapp")
    panel = app._current_panel
    assert panel._repo_combo.currentData() == "/repos/myapp"


def test_diff_compare_branches_leaves_both_unpopulated(qtbot):
    app = _make_app(qtbot)
    app._diff_compare_branches("/repos/myapp")
    panel = app._current_panel
    assert panel._point_selector._from_list.currentItem() is None
    assert panel._point_selector._to_list.currentItem() is None
