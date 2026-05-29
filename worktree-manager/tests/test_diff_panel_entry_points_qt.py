from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QListWidget

from worktree_manager.diff_models import HistoryPoint
from worktree_manager.ui.diff_panel import DiffPanel
from worktree_manager.ui.diff_point_selector import DiffPointSelector


def _points():
    return [
        HistoryPoint(kind="working_tree_unstaged", label="Working tree (unstaged)"),
        HistoryPoint(kind="working_tree_staged", label="Working tree (staged)"),
        HistoryPoint(kind="branch", label="main", short_sha="abc1234", message="Merge PR #1"),
    ]


def _make_panel(qtbot):
    import time
    from worktree_manager.models import WorktreeModel
    now = int(time.time())
    git = MagicMock()
    git.list_points.return_value = _points()
    git.diff_files.return_value = []
    git.list_worktrees.return_value = [
        WorktreeModel(path="/repos/myapp", branch="main", is_main=True,
                      last_commit_ts=now, is_merged=False, is_stale=False),
    ]
    store = MagicMock()
    store.all_repos.return_value = ["/repos/myapp"]
    store.get_ui_pref.return_value = "cursor"
    panel = DiffPanel(git_service=git, config_store=store)
    qtbot.addWidget(panel)
    return panel


# ── DiffPointSelector.pre_select ─────────────────────────────────────────────

def test_pre_select_locks_to_ref_in_to_list(qtbot):
    sel = DiffPointSelector()
    qtbot.addWidget(sel)
    sel.set_repo("/repo", _points())
    sel.pre_select(from_ref=None, to_ref="working_tree_unstaged")
    # TO list should have "Working tree (unstaged)" selected
    to_item = sel._to_list.currentItem()
    assert to_item is not None
    assert to_item.data(from_item_role()) == "working_tree_unstaged"


def from_item_role():
    from PySide6.QtCore import Qt
    return Qt.UserRole


def test_pre_select_leaves_from_empty_when_none(qtbot):
    sel = DiffPointSelector()
    qtbot.addWidget(sel)
    sel.set_repo("/repo", _points())
    sel.pre_select(from_ref=None, to_ref="working_tree_unstaged")
    assert sel._from_list.currentItem() is None


def test_pre_select_selects_both_when_given(qtbot):
    sel = DiffPointSelector()
    qtbot.addWidget(sel)
    sel.set_repo("/repo", _points())
    sel.pre_select(from_ref="main", to_ref="working_tree_unstaged")
    from_item = sel._from_list.currentItem()
    assert from_item is not None
    from PySide6.QtCore import Qt
    assert from_item.data(Qt.UserRole) == "main"


# ── DiffPanel.show_for_repo ───────────────────────────────────────────────────

def test_show_for_repo_selects_correct_repo_in_combo(qtbot):
    import time
    from worktree_manager.models import WorktreeModel
    now = int(time.time())
    git = MagicMock()
    git.list_points.return_value = _points()
    git.diff_files.return_value = []
    git.list_worktrees.return_value = [
        WorktreeModel(path="/repos/alpha", branch="main", is_main=True,
                      last_commit_ts=now, is_merged=False, is_stale=False),
    ]
    store = MagicMock()
    store.all_repos.return_value = ["/repos/alpha", "/repos/beta"]
    store.get_ui_pref.return_value = "cursor"
    panel = DiffPanel(git_service=git, config_store=store)
    qtbot.addWidget(panel)
    panel.show_for_repo("/repos/beta")
    assert panel._repo_combo.currentData() == "/repos/beta"


def test_show_for_repo_lands_on_point_selector(qtbot):
    panel = _make_panel(qtbot)
    panel.show_for_repo("/repos/myapp")
    assert panel._right_area.currentWidget() is panel._point_selector


def test_show_for_repo_auto_selects_newer_point(qtbot):
    from PySide6.QtCore import Qt
    panel = _make_panel(qtbot)
    panel.show_for_repo("/repos/myapp")
    newer_item = panel._point_selector._to_list.currentItem()
    assert newer_item is not None
    assert newer_item.data(Qt.UserRole) == "working_tree_unstaged"


# ── DiffPanel.show_diff ───────────────────────────────────────────────────────

def test_show_diff_selects_correct_repo(qtbot):
    import time
    from worktree_manager.models import WorktreeModel
    now = int(time.time())
    git = MagicMock()
    git.list_points.return_value = _points()
    git.diff_files.return_value = []
    git.list_worktrees.return_value = [
        WorktreeModel(path="/repos/alpha", branch="main", is_main=True,
                      last_commit_ts=now, is_merged=False, is_stale=False),
    ]
    store = MagicMock()
    store.all_repos.return_value = ["/repos/alpha", "/repos/myapp"]
    store.get_ui_pref.return_value = "cursor"
    panel = DiffPanel(git_service=git, config_store=store)
    qtbot.addWidget(panel)
    panel.show_diff("/repos/myapp", to_ref="working_tree_unstaged", from_ref=None)
    assert panel._repo_combo.currentData() == "/repos/myapp"


def test_show_diff_preselects_to_ref(qtbot):
    panel = _make_panel(qtbot)
    panel.show_diff("/repos/myapp", to_ref="working_tree_unstaged", from_ref=None)
    from PySide6.QtCore import Qt
    to_item = panel._point_selector._to_list.currentItem()
    assert to_item is not None
    assert to_item.data(Qt.UserRole) == "working_tree_unstaged"


def test_show_diff_leaves_from_empty_when_none(qtbot):
    panel = _make_panel(qtbot)
    panel.show_diff("/repos/myapp", to_ref="working_tree_unstaged", from_ref=None)
    assert panel._point_selector._from_list.currentItem() is None


def test_show_diff_lands_on_point_selector(qtbot):
    panel = _make_panel(qtbot)
    panel.show_diff("/repos/myapp", to_ref="working_tree_unstaged", from_ref=None)
    assert panel._right_area.currentWidget() is panel._point_selector
