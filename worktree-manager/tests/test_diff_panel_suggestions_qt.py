import time
from unittest.mock import MagicMock, patch
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

from worktree_manager.ui.diff_panel import DiffPanel
from worktree_manager.diff_models import HistoryPoint, DiffFile
from worktree_manager.models import WorktreeModel


def _make_points():
    return [
        HistoryPoint(kind="working_tree_unstaged", label="Working tree (unstaged)"),
        HistoryPoint(kind="working_tree_staged", label="Working tree (staged)"),
        HistoryPoint(kind="branch", label="main", short_sha="abc", message="init"),
        HistoryPoint(kind="branch", label="feature/foo", short_sha="def", message="foo"),
    ]


def _make_git(parent="main"):
    now = int(time.time())
    git = MagicMock()
    git.list_points.return_value = _make_points()
    git.diff_files.return_value = [DiffFile(path="src/foo.py", status="M")]
    git.list_worktrees.return_value = [
        WorktreeModel(path="/repos/myapp", branch="main", is_main=True,
                      last_commit_ts=now, is_merged=False, is_stale=False),
    ]
    git.infer_branch_suggestions.return_value = (parent, None)
    git.checked_out_branch.return_value = "feature/bar"
    return git


def _make_store():
    store = MagicMock()
    store.all_repos.return_value = ["/repos/myapp"]
    store.get_repo.return_value = MagicMock(repo_path="/repos/myapp")
    store.get_diff_pref.return_value = None
    store.get_diff_selection.return_value = {}
    return store


def test_older_list_has_suggested_section_after_load(qtbot):
    panel = DiffPanel(git_service=_make_git(), config_store=_make_store())
    qtbot.addWidget(panel)
    sel = panel._point_selector
    texts = [sel._older_list.item(i).text() for i in range(sel._older_list.count())]
    assert any("Suggested" in t for t in texts)


def test_newer_list_has_suggested_section_after_load(qtbot):
    panel = DiffPanel(git_service=_make_git(), config_store=_make_store())
    qtbot.addWidget(panel)
    sel = panel._point_selector
    texts = [sel._newer_list.item(i).text() for i in range(sel._newer_list.count())]
    assert any("Suggested" in t for t in texts)


def test_newer_point_auto_selected_after_load(qtbot):
    panel = DiffPanel(git_service=_make_git(), config_store=_make_store())
    qtbot.addWidget(panel)
    sel = panel._point_selector
    item = sel._newer_list.currentItem()
    assert item is not None
    assert item.data(Qt.UserRole) == "working_tree_unstaged"


def test_older_point_auto_selected_with_inferred_parent(qtbot):
    panel = DiffPanel(git_service=_make_git(parent="main"), config_store=_make_store())
    qtbot.addWidget(panel)
    sel = panel._point_selector
    item = sel._older_list.currentItem()
    assert item is not None
    assert item.data(Qt.UserRole) == "main"


def test_compare_works_immediately_after_load(qtbot):
    panel = DiffPanel(git_service=_make_git(), config_store=_make_store())
    qtbot.addWidget(panel)
    sel = panel._point_selector
    btn = next(b for b in sel.findChildren(QPushButton) if "Compare" in b.text())
    qtbot.mouseClick(btn, Qt.LeftButton)
    assert panel._summary_label.text() != ""
