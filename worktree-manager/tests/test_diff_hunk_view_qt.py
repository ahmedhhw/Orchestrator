"""Tests for DiffHunkView widget — displays hunks with coloured diff lines."""
import pytest
from PySide6.QtWidgets import QLabel, QPushButton, QScrollArea
from PySide6.QtGui import QColor

from worktree_manager.ui.diff_hunk_view import DiffHunkView
from worktree_manager.diff_models import DiffHunk


def _make_hunk(index=0, header="@@ -1,3 +1,4 @@", lines=None):
    return DiffHunk(
        index=index,
        header=header,
        lines=lines or [" context", "-removed", "+added", " more context"],
        old_start=1, old_count=3, new_start=1, new_count=4,
    )


def _make_view(qtbot):
    view = DiffHunkView()
    qtbot.addWidget(view)
    return view


# ── initial state ──────────────────────────────────────────────────────────────

def test_hunk_view_can_be_instantiated(qtbot):
    view = _make_view(qtbot)
    assert view is not None


def test_hunk_view_has_file_header_label(qtbot):
    view = _make_view(qtbot)
    assert view._file_label is not None


def test_hunk_view_has_open_file_button(qtbot):
    view = _make_view(qtbot)
    buttons = view.findChildren(QPushButton)
    assert any("Open" in b.text() for b in buttons)


def test_open_file_button_disabled_initially(qtbot):
    view = _make_view(qtbot)
    btn = next(b for b in view.findChildren(QPushButton) if "Open" in b.text())
    assert not btn.isEnabled()


# ── set_hunks (read-only mode) ─────────────────────────────────────────────────

def test_set_hunks_shows_hunk_headers(qtbot):
    view = _make_view(qtbot)
    hunks = [_make_hunk(header="@@ -10,5 +10,6 @@")]
    view.set_hunks("src/foo.py", hunks, live_mode=False)
    labels = view.findChildren(QLabel)
    texts = [l.text() for l in labels]
    assert any("@@ -10,5 +10,6 @@" in t for t in texts)


def test_set_hunks_updates_file_label(qtbot):
    view = _make_view(qtbot)
    view.set_hunks("src/auth.py", [_make_hunk()], live_mode=False)
    assert "src/auth.py" in view._file_label.text()


def test_set_hunks_shows_removed_lines(qtbot):
    view = _make_view(qtbot)
    hunks = [_make_hunk(lines=["-old_line", "+new_line", " context"])]
    view.set_hunks("src/foo.py", hunks, live_mode=False)
    labels = view.findChildren(QLabel)
    texts = [l.text() for l in labels]
    assert any("-old_line" in t for t in texts)


def test_set_hunks_shows_added_lines(qtbot):
    view = _make_view(qtbot)
    hunks = [_make_hunk(lines=["-old_line", "+new_line", " context"])]
    view.set_hunks("src/foo.py", hunks, live_mode=False)
    labels = view.findChildren(QLabel)
    texts = [l.text() for l in labels]
    assert any("+new_line" in t for t in texts)


def test_set_hunks_no_checkboxes_in_read_only_mode(qtbot):
    from PySide6.QtWidgets import QCheckBox
    view = _make_view(qtbot)
    view.set_hunks("src/foo.py", [_make_hunk()], live_mode=False)
    assert len(view.findChildren(QCheckBox)) == 0


def test_set_hunks_no_restore_button_in_read_only_mode(qtbot):
    view = _make_view(qtbot)
    view.set_hunks("src/foo.py", [_make_hunk()], live_mode=False)
    buttons = view.findChildren(QPushButton)
    assert not any("Restore" in b.text() and b.isVisible() for b in buttons)


def test_set_hunks_open_file_button_disabled_in_read_only_mode(qtbot):
    view = _make_view(qtbot)
    view.set_hunks("src/foo.py", [_make_hunk()], live_mode=False)
    btn = next(b for b in view.findChildren(QPushButton) if "Open" in b.text())
    assert not btn.isEnabled()


def test_set_hunks_multiple_hunks_shows_all_headers(qtbot):
    view = _make_view(qtbot)
    hunks = [
        _make_hunk(index=0, header="@@ -1,3 +1,4 @@"),
        _make_hunk(index=1, header="@@ -20,5 +21,6 @@"),
    ]
    view.set_hunks("src/foo.py", hunks, live_mode=False)
    labels = view.findChildren(QLabel)
    texts = [l.text() for l in labels]
    assert any("@@ -1,3 +1,4 @@" in t for t in texts)
    assert any("@@ -20,5 +21,6 @@" in t for t in texts)


def test_set_hunks_clears_previous_content(qtbot):
    view = _make_view(qtbot)
    view.set_hunks("src/old.py", [_make_hunk(header="@@ -1,1 +1,1 @@")], live_mode=False)
    view.set_hunks("src/new.py", [_make_hunk(header="@@ -5,3 +5,3 @@")], live_mode=False)
    labels = view.findChildren(QLabel)
    texts = [l.text() for l in labels]
    assert not any("@@ -1,1 +1,1 @@" in t for t in texts)
    assert any("@@ -5,3 +5,3 @@" in t for t in texts)


def test_set_hunks_empty_list_shows_no_headers(qtbot):
    view = _make_view(qtbot)
    view.set_hunks("src/foo.py", [], live_mode=False)
    labels = view.findChildren(QLabel)
    texts = [l.text() for l in labels]
    assert not any("@@" in t for t in texts)


# ── word-wrap (iteration 2) ────────────────────────────────────────────────────

def test_diff_line_labels_have_word_wrap_enabled(qtbot):
    """All diff-line labels must have wordWrap() True after rendering hunks."""
    view = _make_view(qtbot)
    hunks = [_make_hunk(lines=[" context", "-removed", "+added"])]
    view.set_hunks("src/foo.py", hunks, live_mode=False)
    diff_labels = [l for l in view.findChildren(QLabel) if l.objectName() == "diff_line"]
    assert len(diff_labels) > 0, "expected at least one diff_line label"
    assert all(lbl.wordWrap() for lbl in diff_labels)


def test_word_wrap_does_not_remove_added_or_removed_styling(qtbot):
    """Enabling word wrap must not strip the +/- background-colour styles."""
    view = _make_view(qtbot)
    hunks = [_make_hunk(lines=["-removed_line", "+added_line", " context"])]
    view.set_hunks("src/foo.py", hunks, live_mode=False)
    diff_labels = [l for l in view.findChildren(QLabel) if l.objectName() == "diff_line"]
    by_text = {lbl.text(): lbl.styleSheet() for lbl in diff_labels}

    assert "#3d0000" in by_text["-removed_line"], "removed line must keep red background"
    assert "#003d00" in by_text["+added_line"], "added line must keep green background"
