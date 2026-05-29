from unittest.mock import MagicMock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

from worktree_manager.ui.sidebar import Sidebar


def _make_store():
    return MagicMock()


def _make_sidebar(qtbot, **overrides):
    callbacks = {
        "on_command_center": lambda: None,
        "on_workspace_projects": lambda: None,
        "on_branch_management": lambda: None,
        "on_worktree_management": lambda: None,
        "on_diff": lambda: None,
        "on_settings": lambda: None,
        "on_refresh": lambda: None,
    }
    callbacks.update(overrides)
    sb = Sidebar(store=_make_store(), **callbacks)
    qtbot.addWidget(sb)
    return sb


def _button_texts(widget):
    return [b.text() for b in widget.findChildren(QPushButton)]


def test_sidebar_has_diff_tab(qtbot):
    sb = _make_sidebar(qtbot)
    assert any("Diff" in t for t in _button_texts(sb))


def test_sidebar_diff_tab_is_between_commands_and_worktrees(qtbot):
    sb = _make_sidebar(qtbot)
    tab_labels = ("Projects", "Commands", "Diff", "Worktrees", "Branches")
    btns = [
        b for b in sb.findChildren(QPushButton)
        if any(label in b.text() for label in tab_labels)
    ]
    labels = [b.text().strip() for b in btns]
    commands_idx = next(i for i, t in enumerate(labels) if "Commands" in t)
    diff_idx = next(i for i, t in enumerate(labels) if "Diff" in t)
    worktrees_idx = next(i for i, t in enumerate(labels) if "Worktrees" in t)
    assert commands_idx < diff_idx < worktrees_idx


def test_diff_tab_invokes_callback(qtbot):
    triggered = []
    sb = _make_sidebar(qtbot, on_diff=lambda: triggered.append("diff"))
    btn = next(b for b in sb.findChildren(QPushButton) if "Diff" in b.text())
    qtbot.mouseClick(btn, Qt.LeftButton)
    assert triggered == ["diff"]


def test_diff_tab_highlights_on_click(qtbot):
    sb = _make_sidebar(qtbot)
    btn = next(b for b in sb.findChildren(QPushButton) if "Diff" in b.text())
    qtbot.mouseClick(btn, Qt.LeftButton)
    assert btn.property("active_tab") is True


def test_set_active_tab_diff_highlights_diff_button(qtbot):
    sb = _make_sidebar(qtbot)
    sb.set_active_tab("diff")
    btn = next(b for b in sb.findChildren(QPushButton) if "Diff" in b.text())
    assert btn.property("active_tab") is True
