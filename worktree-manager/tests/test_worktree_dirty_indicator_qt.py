"""
Tests for the dirty worktree indicator (orange ● after name).
Iteration: autobot-ui-fixes-ctx-iter-1-dirty-indicator
"""
import time
from unittest.mock import MagicMock

from PySide6.QtWidgets import QLabel

from worktree_manager.main_window_vm import MainWindowViewModel
from worktree_manager.models import WorktreeModel
from worktree_manager.ui.per_repo_worktrees_view import PerRepoWorktreesView


def _make_vm(worktrees, branch_status=None):
    vm = MagicMock(spec=MainWindowViewModel)
    vm.load_worktree_view_data.return_value = {
        "worktrees": worktrees,
        "branch_status": branch_status or [],
    }
    return vm


def _make_view(qtbot, worktrees, branch_status=None):
    vm = _make_vm(worktrees, branch_status)
    view = PerRepoWorktreesView(
        vm=vm,
        repo_name="proj",
        on_cleanup=lambda: None,
        on_new=lambda: None,
    )
    qtbot.addWidget(view)
    qtbot.waitUntil(lambda: not view._loading, timeout=3000)
    return view


def test_dirty_worktree_row_contains_dirty_marker(qtbot):
    now = int(time.time())
    dirty_wt = WorktreeModel(
        path="/repos/proj-wt/fix-auth",
        branch="fix/auth",
        is_main=False,
        last_commit_ts=now - 3600,
        is_merged=False,
        is_stale=False,
        is_dirty=True,
    )
    view = _make_view(qtbot, [dirty_wt])
    markers = [
        lbl for lbl in view.findChildren(QLabel)
        if lbl.objectName() == "dirty_marker"
    ]
    assert len(markers) == 1
    assert markers[0].text() == "●"


def test_clean_worktree_row_has_no_dirty_marker(qtbot):
    now = int(time.time())
    clean_wt = WorktreeModel(
        path="/repos/proj-wt/chore-deps",
        branch="chore/deps",
        is_main=False,
        last_commit_ts=now - 3600,
        is_merged=False,
        is_stale=False,
        is_dirty=False,
    )
    view = _make_view(qtbot, [clean_wt])
    markers = [
        lbl for lbl in view.findChildren(QLabel)
        if lbl.objectName() == "dirty_marker"
    ]
    assert len(markers) == 0
