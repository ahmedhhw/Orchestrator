import time
import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QLineEdit

from worktree_manager.models import WorktreeModel
from worktree_manager.ui.per_repo_worktrees_view import PerRepoWorktreesView


def _make_vm(worktrees=None):
    if worktrees is None:
        now = int(time.time())
        worktrees = [
            WorktreeModel(path="/repos/app", branch="main", is_main=True,
                          last_commit_ts=now, is_merged=False, is_stale=False),
            WorktreeModel(path="/repos/app/worktrees/feature-foo", branch="feature/foo",
                          is_main=False, last_commit_ts=now, is_merged=False, is_stale=False),
        ]
    vm = MagicMock()
    vm.load_worktree_view_data.return_value = {
        "worktrees": worktrees,
        "branch_status": [("main", True), ("feature/foo", True)],
    }
    vm.is_protected_branch.return_value = False
    return vm


def _make_view(qtbot, on_rename=None, worktrees=None):
    vm = _make_vm(worktrees)
    view = PerRepoWorktreesView(
        vm=vm,
        repo_name="app",
        on_cleanup=MagicMock(),
        on_new=MagicMock(),
        on_rename=on_rename,
    )
    qtbot.addWidget(view)
    view.show()
    qtbot.waitUntil(lambda: view._loading is False, timeout=3000)
    return view, vm


def test_rename_button_shown_for_non_main_worktree(qtbot):
    view, _ = _make_view(qtbot)
    rename_btns = [b for b in view.findChildren(QPushButton) if b.text() == "✏"]
    assert len(rename_btns) == 1


def test_rename_button_not_shown_for_main_worktree(qtbot):
    now = int(time.time())
    worktrees = [
        WorktreeModel(path="/repos/app", branch="main", is_main=True,
                      last_commit_ts=now, is_merged=False, is_stale=False),
    ]
    view, _ = _make_view(qtbot, worktrees=worktrees)
    rename_btns = [b for b in view.findChildren(QPushButton) if b.text() == "✏"]
    assert len(rename_btns) == 0


def test_clicking_rename_button_shows_inline_panel(qtbot):
    view, _ = _make_view(qtbot)
    rename_btn = next(b for b in view.findChildren(QPushButton) if b.text() == "✏")
    qtbot.mouseClick(rename_btn, Qt.LeftButton)
    assert view._active_rename_panel is not None


def test_rename_panel_prefills_current_folder_name(qtbot):
    view, _ = _make_view(qtbot)
    rename_btn = next(b for b in view.findChildren(QPushButton) if b.text() == "✏")
    qtbot.mouseClick(rename_btn, Qt.LeftButton)
    assert view._active_rename_panel is not None
    inputs = view._active_rename_panel.findChildren(QLineEdit)
    assert any("feature-foo" in inp.text() for inp in inputs)


def test_cancel_rename_hides_panel(qtbot):
    view, _ = _make_view(qtbot)
    rename_btn = next(b for b in view.findChildren(QPushButton) if b.text() == "✏")
    qtbot.mouseClick(rename_btn, Qt.LeftButton)
    assert view._active_rename_panel is not None
    cancel_btn = next(
        b for b in view._active_rename_panel.findChildren(QPushButton)
        if b.text() == "Cancel"
    )
    qtbot.mouseClick(cancel_btn, Qt.LeftButton)
    assert view._active_rename_panel is None


def test_confirm_rename_calls_on_rename(qtbot):
    on_rename = MagicMock()
    view, _ = _make_view(qtbot, on_rename=on_rename)

    rename_btn = next(b for b in view.findChildren(QPushButton) if b.text() == "✏")
    qtbot.mouseClick(rename_btn, Qt.LeftButton)
    assert view._active_rename_panel is not None

    line_edit = view._active_rename_panel.findChildren(QLineEdit)[0]
    line_edit.clear()
    qtbot.keyClicks(line_edit, "feature-bar")

    confirm_btn = next(
        b for b in view._active_rename_panel.findChildren(QPushButton)
        if b.text() == "Rename"
    )
    qtbot.mouseClick(confirm_btn, Qt.LeftButton)

    on_rename.assert_called_once_with(
        "/repos/app/worktrees/feature-foo", "feature-bar"
    )
