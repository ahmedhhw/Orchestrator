from unittest.mock import MagicMock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

from worktree_manager.ui.sidebar import Sidebar
from worktree_manager.ui.sidebar_strip import SidebarStrip


def _make_store():
    return MagicMock()


def _make_sidebar(qtbot, on_hide=None, **overrides):
    callbacks = {
        "on_command_center": lambda: None,
        "on_workspace_projects": lambda: None,
        "on_branch_management": lambda: None,
        "on_worktree_management": lambda: None,
        "on_settings": lambda: None,
        "on_refresh": lambda: None,
        "on_hide": on_hide or (lambda: None),
    }
    callbacks.update(overrides)
    sb = Sidebar(store=_make_store(), **callbacks)
    qtbot.addWidget(sb)
    return sb


def test_sidebar_has_hide_button(qtbot):
    sb = _make_sidebar(qtbot)
    texts = [b.text() for b in sb.findChildren(QPushButton)]
    assert any("Hide" in t for t in texts)


def test_sidebar_hide_button_below_settings(qtbot):
    sb = _make_sidebar(qtbot)
    buttons = sb.findChildren(QPushButton)
    texts = [b.text() for b in buttons]
    settings_idx = next(i for i, t in enumerate(texts) if "Settings" in t)
    hide_idx = next(i for i, t in enumerate(texts) if "Hide" in t)
    assert hide_idx > settings_idx


def test_sidebar_hide_button_fires_on_hide_callback(qtbot):
    triggered = []
    sb = _make_sidebar(qtbot, on_hide=lambda: triggered.append(True))
    btn = next(b for b in sb.findChildren(QPushButton) if "Hide" in b.text())
    qtbot.mouseClick(btn, Qt.LeftButton)
    assert triggered == [True]


def test_sidebar_strip_has_restore_button(qtbot):
    strip = SidebarStrip(on_restore=lambda: None)
    qtbot.addWidget(strip)
    btns = strip.findChildren(QPushButton)
    assert len(btns) == 1


def test_sidebar_strip_fixed_width_is_24(qtbot):
    strip = SidebarStrip(on_restore=lambda: None)
    qtbot.addWidget(strip)
    assert strip.maximumWidth() == 24


def test_sidebar_strip_restore_button_fires_callback(qtbot):
    triggered = []
    strip = SidebarStrip(on_restore=lambda: triggered.append(True))
    qtbot.addWidget(strip)
    btn = strip.findChildren(QPushButton)[0]
    qtbot.mouseClick(btn, Qt.LeftButton)
    assert triggered == [True]
