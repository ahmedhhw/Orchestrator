from unittest.mock import MagicMock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

from worktree_manager.ui.sidebar import Sidebar


def _make_store():
    return MagicMock()


def _make_sidebar(qtbot, store=None, **overrides):
    callbacks = {
        "on_command_center": lambda: None,
        "on_workspace_projects": lambda: None,
        "on_branch_management": lambda: None,
        "on_worktree_management": lambda: None,
        "on_settings": lambda: None,
        "on_refresh": lambda: None,
    }
    callbacks.update(overrides)
    sb = Sidebar(store=store or _make_store(), **callbacks)
    qtbot.addWidget(sb)
    return sb


def _button_texts(widget):
    return [b.text() for b in widget.findChildren(QPushButton)]


def test_sidebar_has_four_tab_buttons(qtbot):
    sb = _make_sidebar(qtbot)
    texts = _button_texts(sb)
    assert any("Projects" in t for t in texts)
    assert any("Commands" in t for t in texts)
    assert any("Worktrees" in t for t in texts)
    assert any("Branches" in t for t in texts)


def test_sidebar_tab_order_is_projects_commands_worktrees_branches(qtbot):
    sb = _make_sidebar(qtbot)
    btns = [b for b in sb.findChildren(QPushButton)
            if any(label in b.text() for label in ("Projects", "Commands", "Worktrees", "Branches"))]
    labels = [b.text().strip() for b in btns]
    projects_idx = next(i for i, t in enumerate(labels) if "Projects" in t)
    commands_idx = next(i for i, t in enumerate(labels) if "Commands" in t)
    worktrees_idx = next(i for i, t in enumerate(labels) if "Worktrees" in t)
    branches_idx = next(i for i, t in enumerate(labels) if "Branches" in t)
    assert projects_idx < commands_idx < worktrees_idx < branches_idx


def test_sidebar_has_refresh_button(qtbot):
    sb = _make_sidebar(qtbot)
    assert any("Refresh" in t for t in _button_texts(sb))


def test_sidebar_has_settings_button(qtbot):
    sb = _make_sidebar(qtbot)
    assert any("Settings" in t for t in _button_texts(sb))


def test_sidebar_has_no_repos_list(qtbot):
    sb = _make_sidebar(qtbot)
    assert not any("REPOS" in t for t in _button_texts(sb))


def test_sidebar_has_no_add_repo_button(qtbot):
    sb = _make_sidebar(qtbot)
    assert not any("Add Repo" in t for t in _button_texts(sb))


def test_projects_tab_invokes_callback(qtbot):
    triggered: list = []
    sb = _make_sidebar(qtbot, on_workspace_projects=lambda: triggered.append("wp"))
    btn = next(b for b in sb.findChildren(QPushButton) if "Projects" in b.text())
    qtbot.mouseClick(btn, Qt.LeftButton)
    assert triggered == ["wp"]


def test_commands_tab_invokes_callback(qtbot):
    triggered: list = []
    sb = _make_sidebar(qtbot, on_command_center=lambda: triggered.append("cc"))
    btn = next(b for b in sb.findChildren(QPushButton) if "Commands" in b.text())
    qtbot.mouseClick(btn, Qt.LeftButton)
    assert triggered == ["cc"]


def test_worktrees_tab_invokes_callback(qtbot):
    triggered: list = []
    sb = _make_sidebar(qtbot, on_worktree_management=lambda: triggered.append("wm"))
    btn = next(b for b in sb.findChildren(QPushButton) if "Worktrees" in b.text())
    qtbot.mouseClick(btn, Qt.LeftButton)
    assert triggered == ["wm"]


def test_branches_tab_invokes_callback(qtbot):
    triggered: list = []
    sb = _make_sidebar(qtbot, on_branch_management=lambda: triggered.append("bm"))
    btn = next(b for b in sb.findChildren(QPushButton) if "Branches" in b.text())
    qtbot.mouseClick(btn, Qt.LeftButton)
    assert triggered == ["bm"]


def test_refresh_button_invokes_callback(qtbot):
    triggered: list = []
    sb = _make_sidebar(qtbot, on_refresh=lambda: triggered.append("refresh"))
    btn = next(b for b in sb.findChildren(QPushButton) if "Refresh" in b.text())
    qtbot.mouseClick(btn, Qt.LeftButton)
    assert triggered == ["refresh"]


def test_settings_button_invokes_callback(qtbot):
    triggered: list = []
    sb = _make_sidebar(qtbot, on_settings=lambda: triggered.append("settings"))
    btn = next(b for b in sb.findChildren(QPushButton) if "Settings" in b.text())
    qtbot.mouseClick(btn, Qt.LeftButton)
    assert triggered == ["settings"]


def test_projects_tab_is_active_by_default(qtbot):
    sb = _make_sidebar(qtbot)
    btn = next(b for b in sb.findChildren(QPushButton) if "Projects" in b.text())
    assert btn.property("active_tab") is True


def test_clicking_tab_updates_active_highlight(qtbot):
    sb = _make_sidebar(qtbot)
    wt_btn = next(b for b in sb.findChildren(QPushButton) if "Worktrees" in b.text())
    qtbot.mouseClick(wt_btn, Qt.LeftButton)
    assert wt_btn.property("active_tab") is True
    proj_btn = next(b for b in sb.findChildren(QPushButton) if "Projects" in b.text())
    assert proj_btn.property("active_tab") is not True


def test_tab_buttons_have_minimum_height(qtbot):
    sb = _make_sidebar(qtbot)
    for key in ("Projects", "Commands", "Worktrees", "Branches"):
        btn = next(b for b in sb.findChildren(QPushButton) if key in b.text())
        assert btn.height() >= 40


def test_sidebar_minimum_width_is_at_least_220(qtbot):
    sb = _make_sidebar(qtbot)
    assert sb.minimumWidth() >= 220
