"""Tests for DiffPanel wiring restore, undo, and open_file in live mode."""
import os
from unittest.mock import MagicMock, patch, call

import pytest
from PySide6.QtWidgets import QPushButton, QCheckBox, QLabel

from worktree_manager.ui.diff_panel import DiffPanel
from worktree_manager.diff_models import DiffHunk, DiffFile, HistoryPoint


def _make_hunk(index=0, header="@@ -1,3 +1,4 @@"):
    return DiffHunk(
        index=index, header=header,
        lines=[" ctx", "-old", "+new"],
        old_start=1, old_count=3, new_start=1, new_count=4,
    )


def _make_panel(qtbot, editor="cursor"):
    git = MagicMock()
    git.list_worktrees.return_value = [
        MagicMock(path="/repos/proj", is_main=True, branch="main"),
    ]
    git.list_points.return_value = [
        HistoryPoint(kind="working_tree_unstaged", label="Working tree (unstaged)"),
        HistoryPoint(kind="branch", label="main", short_sha="abc1234", message="init"),
    ]
    git.diff_files.return_value = [DiffFile(path="src/foo.py", status="M")]
    git.diff_hunks.return_value = [_make_hunk()]
    git.apply_reverse_patch.return_value = "forward patch"
    store = MagicMock()
    store.all_repos.return_value = ["/repos/proj"]
    store.get_ui_pref.return_value = editor
    panel = DiffPanel(git_service=git, config_store=store)
    qtbot.addWidget(panel)
    return panel, git, store


def _do_compare(panel, base_ref="main", target_ref="working_tree_unstaged"):
    panel._vm.set_points(base_ref, target_ref)
    files = panel._vm.load_diff_files()
    panel._file_list.set_files(files)
    panel._hunk_view.set_hunks("", [], live_mode=panel._vm.target_is_working_tree)
    panel._summary_bar.show()
    panel._right_area.setCurrentWidget(panel._diff_splitter)


def _load_file(panel, path="src/foo.py"):
    panel._on_file_selected(path)


# ── restore wiring ────────────────────────────────────────────────────────────

def test_restore_callback_calls_vm_restore_hunks(qtbot):
    panel, git, _ = _make_panel(qtbot)
    _do_compare(panel)
    _load_file(panel)

    cb = panel._hunk_view._on_restore_cb
    assert cb is not None
    cb([0])
    git.apply_reverse_patch.assert_called_once()


def test_restore_shows_toast(qtbot):
    panel, git, _ = _make_panel(qtbot)
    _do_compare(panel)
    _load_file(panel)

    cb = panel._hunk_view._on_restore_cb
    cb([0])
    labels = panel._hunk_view.findChildren(QLabel)
    assert any("Restored" in l.text() for l in labels)


def test_restore_refreshes_file_list(qtbot):
    panel, git, _ = _make_panel(qtbot)
    _do_compare(panel)
    _load_file(panel)

    initial_count = git.diff_files.call_count
    cb = panel._hunk_view._on_restore_cb
    cb([0])
    assert git.diff_files.call_count > initial_count


# ── undo wiring ────────────────────────────────────────────────────────────────

def test_undo_callback_calls_vm_undo_restore(qtbot):
    panel, git, _ = _make_panel(qtbot)
    _do_compare(panel)
    _load_file(panel)

    # Trigger restore first to get undo callback wired up
    restore_cb = panel._hunk_view._on_restore_cb
    restore_cb([0])

    # Now click undo
    undo_btn = next(
        b for b in panel._hunk_view.findChildren(QPushButton) if "Undo" in b.text()
    )
    undo_btn.click()
    git.apply_patch.assert_called_once_with("/repos/proj", "forward patch")


# ── open_file wiring ──────────────────────────────────────────────────────────

def test_open_file_callback_is_wired(qtbot):
    panel, git, _ = _make_panel(qtbot)
    _do_compare(panel)
    _load_file(panel)
    assert panel._hunk_view._on_open_file_cb is not None


def test_open_file_button_enabled_in_live_mode(qtbot):
    panel, git, _ = _make_panel(qtbot)
    _do_compare(panel, target_ref="working_tree_unstaged")
    _load_file(panel)
    btn = next(b for b in panel._hunk_view.findChildren(QPushButton) if "Open" in b.text())
    assert btn.isEnabled()


def test_open_file_button_disabled_in_read_only_mode(qtbot):
    panel, git, _ = _make_panel(qtbot)
    _do_compare(panel, base_ref="main", target_ref="abc1234")
    _load_file(panel)
    btn = next(b for b in panel._hunk_view.findChildren(QPushButton) if "Open" in b.text())
    assert not btn.isEnabled()


def test_open_file_fires_editor_service(qtbot):
    panel, git, _ = _make_panel(qtbot)
    _do_compare(panel)
    _load_file(panel)

    editor_svc = MagicMock()
    panel._editor_service = editor_svc

    open_cb = panel._hunk_view._on_open_file_cb
    open_cb()
    editor_svc.open_new.assert_called_once()
