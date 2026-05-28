from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton

from worktree_manager.ui.branch_management_panel import BranchManagementPanel


def _make_panel(qtbot):
    panel = BranchManagementPanel()
    qtbot.addWidget(panel)
    return panel


def _button_texts(widget):
    return [b.text() for b in widget.findChildren(QPushButton)]


def _label_texts(widget):
    return [lbl.text() for lbl in widget.findChildren(QLabel)]


def test_has_sync_from_origin_section_tab(qtbot):
    panel = _make_panel(qtbot)
    assert any("Sync from origin" in t for t in _button_texts(panel))


def test_has_cleanup_section_tab(qtbot):
    panel = _make_panel(qtbot)
    assert any("Cleanup" in t for t in _button_texts(panel))


def test_shows_section_tab_buttons(qtbot):
    panel = _make_panel(qtbot)
    btns = _button_texts(panel)
    assert any("Sync from origin" in t for t in btns)
    assert any("Cleanup" in t for t in btns)


def test_clicking_section_tabs_does_not_crash(qtbot):
    panel = _make_panel(qtbot)
    sync_btn = next(b for b in panel.findChildren(QPushButton) if "Sync from origin" in b.text())
    cleanup_btn = next(b for b in panel.findChildren(QPushButton) if "Cleanup" in b.text())
    qtbot.mouseClick(sync_btn, Qt.LeftButton)
    qtbot.mouseClick(cleanup_btn, Qt.LeftButton)
