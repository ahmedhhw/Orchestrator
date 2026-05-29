"""Tests for DiffPanel file→hunk wiring: clicking a file loads hunks in DiffHunkView."""
import time
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QSplitter

from worktree_manager.ui.diff_panel import DiffPanel
from worktree_manager.diff_models import HistoryPoint, DiffFile, DiffHunk


def _make_hunk(index=0, header="@@ -1,3 +1,4 @@"):
    return DiffHunk(
        index=index, header=header,
        lines=[" ctx", "-old", "+new"],
        old_start=1, old_count=3, new_start=1, new_count=4,
    )


def _make_git(points=None, files=None, hunks=None):
    from worktree_manager.models import WorktreeModel
    now = int(time.time())
    git = MagicMock()
    git.list_points.return_value = points or [
        HistoryPoint(kind="working_tree_unstaged", label="Working tree (unstaged)"),
        HistoryPoint(kind="branch", label="main", short_sha="abc", message="Merge"),
    ]
    git.diff_files.return_value = files or [
        DiffFile(path="src/foo.py", status="M"),
        DiffFile(path="src/bar.py", status="A"),
    ]
    git.diff_hunks.return_value = hunks or [_make_hunk()]
    git.list_worktrees.return_value = [
        WorktreeModel(path="/repos/myapp", branch="main", is_main=True,
                      last_commit_ts=now, is_merged=False, is_stale=False),
    ]
    return git


def _make_store(repos=None):
    store = MagicMock()
    store.all_repos.return_value = repos or ["/repos/myapp"]
    return store


def _make_panel(qtbot, git=None, store=None):
    panel = DiffPanel(
        git_service=git or _make_git(),
        config_store=store or _make_store(),
    )
    qtbot.addWidget(panel)
    return panel


def _navigate_to_file_list(panel, qtbot):
    """Helper: compare two points so the file list is shown."""
    panel._repo_combo.setCurrentIndex(0)
    from worktree_manager.ui.diff_point_selector import DiffPointSelector
    sel = panel._right_area.currentWidget()
    sel._select_by_ref(sel._older_list, "main")
    sel._select_by_ref(sel._newer_list, "working_tree_unstaged")
    btn = next(b for b in sel.findChildren(QPushButton) if "Compare" in b.text())
    qtbot.mouseClick(btn, Qt.LeftButton)


# ── structure after compare ────────────────────────────────────────────────────

def test_file_list_area_is_a_splitter_after_compare(qtbot):
    panel = _make_panel(qtbot)
    _navigate_to_file_list(panel, qtbot)
    from worktree_manager.ui.diff_file_list import DiffFileList
    current = panel._right_area.currentWidget()
    # The current widget should be a QSplitter containing DiffFileList
    assert isinstance(current, QSplitter)


def test_splitter_contains_file_list(qtbot):
    panel = _make_panel(qtbot)
    _navigate_to_file_list(panel, qtbot)
    current = panel._right_area.currentWidget()
    from worktree_manager.ui.diff_file_list import DiffFileList
    children = [current.widget(i) for i in range(current.count())]
    assert any(isinstance(c, DiffFileList) for c in children)


def test_splitter_contains_hunk_view(qtbot):
    panel = _make_panel(qtbot)
    _navigate_to_file_list(panel, qtbot)
    current = panel._right_area.currentWidget()
    from worktree_manager.ui.diff_hunk_view import DiffHunkView
    children = [current.widget(i) for i in range(current.count())]
    assert any(isinstance(c, DiffHunkView) for c in children)


# ── file selection loads hunks ─────────────────────────────────────────────────

def test_clicking_file_calls_diff_hunks(qtbot):
    git = _make_git()
    panel = _make_panel(qtbot, git=git)
    _navigate_to_file_list(panel, qtbot)
    panel._file_list._list_widget.setCurrentRow(0)
    git.diff_hunks.assert_called()


def test_clicking_file_shows_hunk_header_in_hunk_view(qtbot):
    hunks = [_make_hunk(header="@@ -10,5 +10,6 @@")]
    git = _make_git(hunks=hunks)
    panel = _make_panel(qtbot, git=git)
    _navigate_to_file_list(panel, qtbot)
    panel._file_list._list_widget.setCurrentRow(0)
    labels = panel._hunk_view.findChildren(QLabel)
    texts = [l.text() for l in labels]
    assert any("@@ -10,5 +10,6 @@" in t for t in texts)


def test_clicking_second_file_updates_hunk_view(qtbot):
    hunks_foo = [_make_hunk(header="@@ -1,2 +1,3 @@")]
    hunks_bar = [_make_hunk(header="@@ -50,4 +50,5 @@")]
    git = _make_git(
        files=[DiffFile(path="src/foo.py", status="M"), DiffFile(path="src/bar.py", status="A")],
    )
    git.diff_hunks.side_effect = lambda *args: (
        hunks_foo if "foo.py" in args[-1] else hunks_bar
    )
    panel = _make_panel(qtbot, git=git)
    _navigate_to_file_list(panel, qtbot)
    panel._file_list._list_widget.setCurrentRow(0)
    panel._file_list._list_widget.setCurrentRow(1)
    labels = panel._hunk_view.findChildren(QLabel)
    texts = [l.text() for l in labels]
    assert any("@@ -50,4 +50,5 @@" in t for t in texts)


# ── open file button state depends on live mode ───────────────────────────────

def test_open_file_button_enabled_when_to_is_working_tree(qtbot):
    panel = _make_panel(qtbot)
    _navigate_to_file_list(panel, qtbot)  # TO = working_tree_unstaged
    panel._file_list._list_widget.setCurrentRow(0)
    btn = next(b for b in panel._hunk_view.findChildren(QPushButton) if "Open" in b.text())
    assert btn.isEnabled()
