from unittest.mock import MagicMock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QListWidget

from worktree_manager.ui.diff_file_list import DiffFileList
from worktree_manager.ui.file_list_strip import FileListStrip


# ── FileListStrip ──────────────────────────────────────────────────────────

def test_file_list_strip_has_one_button(qtbot):
    strip = FileListStrip(on_restore=lambda: None)
    qtbot.addWidget(strip)
    assert len(strip.findChildren(QPushButton)) == 1


def test_file_list_strip_fixed_width_is_24(qtbot):
    strip = FileListStrip(on_restore=lambda: None)
    qtbot.addWidget(strip)
    assert strip.maximumWidth() == 24


def test_file_list_strip_restore_callback_fires(qtbot):
    triggered = []
    strip = FileListStrip(on_restore=lambda: triggered.append(True))
    qtbot.addWidget(strip)
    btn = strip.findChildren(QPushButton)[0]
    qtbot.mouseClick(btn, Qt.LeftButton)
    assert triggered == [True]


# ── DiffFileList hide button ───────────────────────────────────────────────

def _make_file_list(qtbot):
    fl = DiffFileList()
    qtbot.addWidget(fl)
    return fl


def test_diff_file_list_has_hide_button(qtbot):
    fl = _make_file_list(qtbot)
    assert fl._hide_btn is not None


def test_diff_file_list_hide_button_fires_callback(qtbot):
    triggered = []
    fl = _make_file_list(qtbot)
    fl.on_hide(lambda: triggered.append(True))
    qtbot.mouseClick(fl._hide_btn, Qt.LeftButton)
    assert triggered == [True]


def test_diff_file_list_hide_button_not_fires_when_no_callback(qtbot):
    fl = _make_file_list(qtbot)
    # must not raise
    qtbot.mouseClick(fl._hide_btn, Qt.LeftButton)


# ── DiffFileList selection highlight ─────────────────────────────────────

def test_diff_file_list_uses_single_selection_mode(qtbot):
    fl = _make_file_list(qtbot)
    lw = fl.findChildren(QListWidget)[0]
    assert lw.selectionMode() == QListWidget.SingleSelection


def test_diff_file_list_has_selection_stylesheet(qtbot):
    fl = _make_file_list(qtbot)
    lw = fl.findChildren(QListWidget)[0]
    assert "item:selected" in lw.styleSheet()
