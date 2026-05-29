"""Tests for DiffHunkView live mode: checkboxes, restore button, toast."""
import pytest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QCheckBox, QPushButton, QLabel
from PySide6.QtCore import Qt

from worktree_manager.ui.diff_hunk_view import DiffHunkView
from worktree_manager.diff_models import DiffHunk


def _make_hunk(index=0, header="@@ -1,3 +1,4 @@", lines=None):
    return DiffHunk(
        index=index,
        header=header,
        lines=lines or [" context", "-removed", "+added"],
        old_start=1, old_count=3, new_start=1, new_count=4,
    )


def _make_view(qtbot):
    view = DiffHunkView()
    qtbot.addWidget(view)
    return view


# ── live mode: checkboxes ─────────────────────────────────────────────────────

def test_live_mode_shows_checkboxes(qtbot):
    view = _make_view(qtbot)
    view.set_hunks("src/foo.py", [_make_hunk()], live_mode=True)
    assert len(view.findChildren(QCheckBox)) > 0


def test_live_mode_one_checkbox_per_hunk(qtbot):
    view = _make_view(qtbot)
    hunks = [_make_hunk(index=0), _make_hunk(index=1, header="@@ -20,3 +21,4 @@")]
    view.set_hunks("src/foo.py", hunks, live_mode=True)
    assert len(view.findChildren(QCheckBox)) == 2


def test_live_mode_checkboxes_unchecked_by_default(qtbot):
    view = _make_view(qtbot)
    view.set_hunks("src/foo.py", [_make_hunk()], live_mode=True)
    for cb in view.findChildren(QCheckBox):
        assert not cb.isChecked()


def test_read_only_mode_has_no_checkboxes(qtbot):
    view = _make_view(qtbot)
    view.set_hunks("src/foo.py", [_make_hunk()], live_mode=False)
    assert len(view.findChildren(QCheckBox)) == 0


# ── live mode: select all / none ──────────────────────────────────────────────

def test_live_mode_has_select_all_button(qtbot):
    view = _make_view(qtbot)
    view.set_hunks("src/foo.py", [_make_hunk()], live_mode=True)
    buttons = view.findChildren(QPushButton)
    assert any("All" in b.text() for b in buttons)


def test_live_mode_has_select_none_button(qtbot):
    view = _make_view(qtbot)
    view.set_hunks("src/foo.py", [_make_hunk()], live_mode=True)
    buttons = view.findChildren(QPushButton)
    assert any("None" in b.text() for b in buttons)


def test_select_all_checks_all_checkboxes(qtbot):
    view = _make_view(qtbot)
    view.set_hunks("src/foo.py", [_make_hunk(index=0), _make_hunk(index=1)], live_mode=True)
    all_btn = next(b for b in view.findChildren(QPushButton) if "All" in b.text())
    all_btn.click()
    for cb in view.findChildren(QCheckBox):
        assert cb.isChecked()


def test_select_none_unchecks_all_checkboxes(qtbot):
    view = _make_view(qtbot)
    view.set_hunks("src/foo.py", [_make_hunk(index=0), _make_hunk(index=1)], live_mode=True)
    all_btn = next(b for b in view.findChildren(QPushButton) if "All" in b.text())
    all_btn.click()
    none_btn = next(b for b in view.findChildren(QPushButton) if "None" in b.text())
    none_btn.click()
    for cb in view.findChildren(QCheckBox):
        assert not cb.isChecked()


# ── live mode: restore button ─────────────────────────────────────────────────

def test_live_mode_has_restore_button(qtbot):
    view = _make_view(qtbot)
    view.set_hunks("src/foo.py", [_make_hunk()], live_mode=True)
    buttons = view.findChildren(QPushButton)
    assert any("Restore" in b.text() for b in buttons)


def test_read_only_mode_has_no_restore_button(qtbot):
    view = _make_view(qtbot)
    view.set_hunks("src/foo.py", [_make_hunk()], live_mode=False)
    buttons = view.findChildren(QPushButton)
    assert not any("Restore" in b.text() and b.isVisible() for b in buttons)


def test_restore_button_calls_on_restore_with_checked_indices(qtbot):
    view = _make_view(qtbot)
    h0 = _make_hunk(index=0)
    h1 = _make_hunk(index=1, header="@@ -20,3 +21,4 @@")
    view.set_hunks("src/foo.py", [h0, h1], live_mode=True)
    cb = view.findChildren(QCheckBox)[1]
    cb.setChecked(True)
    restore_cb = MagicMock()
    view.on_restore(restore_cb)
    restore_btn = next(b for b in view.findChildren(QPushButton) if "Restore" in b.text())
    restore_btn.click()
    restore_cb.assert_called_once_with([1])


def test_restore_button_text_reflects_checked_count(qtbot):
    view = _make_view(qtbot)
    view.set_hunks("src/foo.py", [_make_hunk(index=0), _make_hunk(index=1)], live_mode=True)
    cb = view.findChildren(QCheckBox)[0]
    cb.setChecked(True)
    restore_btn = next(b for b in view.findChildren(QPushButton) if "Restore" in b.text())
    assert "1" in restore_btn.text()


# ── live mode: open file button ───────────────────────────────────────────────

def test_live_mode_open_file_button_enabled(qtbot):
    view = _make_view(qtbot)
    view.set_hunks("src/foo.py", [_make_hunk()], live_mode=True)
    btn = next(b for b in view.findChildren(QPushButton) if "Open" in b.text())
    assert btn.isEnabled()


def test_read_only_mode_open_file_button_disabled(qtbot):
    view = _make_view(qtbot)
    view.set_hunks("src/foo.py", [_make_hunk()], live_mode=False)
    btn = next(b for b in view.findChildren(QPushButton) if "Open" in b.text())
    assert not btn.isEnabled()


def test_open_file_button_fires_callback(qtbot):
    view = _make_view(qtbot)
    view.set_hunks("src/foo.py", [_make_hunk()], live_mode=True)
    cb = MagicMock()
    view.on_open_file(cb)
    btn = next(b for b in view.findChildren(QPushButton) if "Open" in b.text())
    btn.click()
    cb.assert_called_once()


# ── toast ─────────────────────────────────────────────────────────────────────

def test_show_toast_displays_message(qtbot):
    view = _make_view(qtbot)
    view.show_toast("Restored 1 hunk in src/foo.py", undo_cb=None)
    labels = view.findChildren(QLabel)
    assert any("Restored 1 hunk" in l.text() for l in labels)


def test_show_toast_has_undo_button(qtbot):
    view = _make_view(qtbot)
    view.show_toast("Restored 1 hunk", undo_cb=MagicMock())
    buttons = view.findChildren(QPushButton)
    assert any("Undo" in b.text() for b in buttons)


def test_toast_undo_button_calls_undo_callback(qtbot):
    view = _make_view(qtbot)
    undo_cb = MagicMock()
    view.show_toast("Restored 1 hunk", undo_cb=undo_cb)
    undo_btn = next(b for b in view.findChildren(QPushButton) if "Undo" in b.text())
    undo_btn.click()
    undo_cb.assert_called_once()


def test_show_toast_no_undo_button_when_no_callback(qtbot):
    view = _make_view(qtbot)
    view.show_toast("Done", undo_cb=None)
    buttons = view.findChildren(QPushButton)
    assert not any("Undo" in b.text() and b.isVisible() for b in buttons)


def test_dismiss_toast_removes_message(qtbot):
    view = _make_view(qtbot)
    view.show_toast("Restored 1 hunk", undo_cb=None)
    view.dismiss_toast()
    labels = view.findChildren(QLabel)
    assert not any("Restored 1 hunk" in l.text() for l in labels)


def test_second_toast_replaces_first(qtbot):
    view = _make_view(qtbot)
    view.show_toast("First message", undo_cb=None)
    view.show_toast("Second message", undo_cb=None)
    labels = view.findChildren(QLabel)
    assert not any("First message" in l.text() for l in labels)
    assert any("Second message" in l.text() for l in labels)
