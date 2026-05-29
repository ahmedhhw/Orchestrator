import time
from unittest.mock import MagicMock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

from worktree_manager.ui.diff_panel import DiffPanel
from worktree_manager.diff_models import HistoryPoint, DiffFile
from worktree_manager.models import WorktreeModel


def _make_git():
    now = int(time.time())
    git = MagicMock()
    git.list_points.return_value = [
        HistoryPoint(kind="working_tree_unstaged", label="Working tree (unstaged)"),
        HistoryPoint(kind="branch", label="main", short_sha="abc", message="Merge"),
    ]
    git.diff_files.return_value = [DiffFile(path="src/foo.py", status="M")]
    git.list_worktrees.return_value = [
        WorktreeModel(path="/repos/myapp", branch="main", is_main=True,
                      last_commit_ts=now, is_merged=False, is_stale=False),
    ]
    return git


def _make_store():
    store = MagicMock()
    store.all_repos.return_value = ["/repos/myapp"]
    store.get_repo.return_value = MagicMock(repo_path="/repos/myapp")
    store.get_diff_pref.return_value = None
    return store


def _trigger_compare(qtbot, panel):
    from worktree_manager.ui.diff_point_selector import DiffPointSelector
    sel = panel._right_area.currentWidget()
    sel._newer_list.setCurrentRow(0)   # working_tree_unstaged
    sel._older_list.setCurrentRow(1)   # main
    btn = next(b for b in sel.findChildren(QPushButton) if "Compare" in b.text())
    qtbot.mouseClick(btn, Qt.LeftButton)


def test_summary_bar_shows_older_label(qtbot):
    panel = DiffPanel(git_service=_make_git(), config_store=_make_store())
    qtbot.addWidget(panel)
    _trigger_compare(qtbot, panel)
    assert "OLDER" in panel._summary_label.text()


def test_summary_bar_shows_newer_label(qtbot):
    panel = DiffPanel(git_service=_make_git(), config_store=_make_store())
    qtbot.addWidget(panel)
    _trigger_compare(qtbot, panel)
    assert "NEWER" in panel._summary_label.text()


def test_summary_bar_does_not_show_from_label(qtbot):
    panel = DiffPanel(git_service=_make_git(), config_store=_make_store())
    qtbot.addWidget(panel)
    _trigger_compare(qtbot, panel)
    assert "FROM:" not in panel._summary_label.text()


def test_summary_bar_does_not_show_to_label(qtbot):
    panel = DiffPanel(git_service=_make_git(), config_store=_make_store())
    qtbot.addWidget(panel)
    _trigger_compare(qtbot, panel)
    assert "TO:" not in panel._summary_label.text()
