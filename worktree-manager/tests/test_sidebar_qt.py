from unittest.mock import MagicMock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

from worktree_manager.ui.sidebar import Sidebar


def _make_store(repos=None, collapsed=None):
    store = MagicMock()
    store.all_repos.return_value = repos or {}
    store.get_ui_pref.side_effect = lambda key, default=None: (
        collapsed if key == "repos_collapsed" else default
    )
    return store


def _make_sidebar(qtbot, store, **overrides):
    callbacks = {
        "on_command_center": lambda: None,
        "on_workspace_projects": lambda: None,
        "on_add_repo": lambda: None,
        "on_refresh": lambda: None,
        "on_repo_selected": lambda path: None,
        "on_repo_delete": lambda path: None,
    }
    callbacks.update(overrides)
    sb = Sidebar(store=store, active_repo_path=None, **callbacks)
    qtbot.addWidget(sb)
    return sb


def _button_texts(widget):
    return [b.text() for b in widget.findChildren(QPushButton)]


def test_sidebar_has_top_action_buttons(qtbot):
    sb = _make_sidebar(qtbot, _make_store())
    texts = _button_texts(sb)
    assert any("Command Center" in t for t in texts)
    assert any("Workspace Projects" in t for t in texts)
    assert any("Add Repo" in t for t in texts)
    assert any("Refresh" in t for t in texts)


def test_sidebar_lists_configured_repos(qtbot, tmp_path):
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    sb = _make_sidebar(qtbot, _make_store({str(repo_a): {}, str(repo_b): {}}))
    texts = _button_texts(sb)
    assert any("repo-a" in t for t in texts)
    assert any("repo-b" in t for t in texts)


def test_sidebar_marks_active_repo_with_filled_dot(qtbot, tmp_path):
    repo = tmp_path / "repo-a"
    store = _make_store({str(repo): {}})
    sb = Sidebar(
        store=store,
        on_command_center=lambda: None,
        on_workspace_projects=lambda: None,
        on_add_repo=lambda: None,
        on_refresh=lambda: None,
        on_repo_selected=lambda p: None,
        on_repo_delete=lambda p: None,
        active_repo_path=str(repo),
    )
    qtbot.addWidget(sb)
    texts = _button_texts(sb)
    assert any(t.startswith("● ") and "repo-a" in t for t in texts)


def test_sidebar_repo_button_invokes_on_repo_selected(qtbot, tmp_path):
    repo = tmp_path / "repo-a"
    clicked: list = []
    sb = _make_sidebar(
        qtbot, _make_store({str(repo): {}}),
        on_repo_selected=lambda p: clicked.append(p),
    )
    btn = next(b for b in sb.findChildren(QPushButton) if "repo-a" in b.text())
    qtbot.mouseClick(btn, Qt.LeftButton)
    assert clicked == [str(repo)]


def test_sidebar_delete_button_invokes_on_repo_delete(qtbot, tmp_path):
    repo = tmp_path / "repo-a"
    deleted: list = []
    sb = _make_sidebar(
        qtbot, _make_store({str(repo): {}}),
        on_repo_delete=lambda p: deleted.append(p),
    )
    del_btn = next(b for b in sb.findChildren(QPushButton) if b.text() == "✕")
    qtbot.mouseClick(del_btn, Qt.LeftButton)
    assert deleted == [str(repo)]


def test_sidebar_top_action_button_invokes_callback(qtbot):
    triggered: list = []
    sb = _make_sidebar(
        qtbot, _make_store(),
        on_command_center=lambda: triggered.append("cc"),
    )
    btn = next(b for b in sb.findChildren(QPushButton) if "Command Center" in b.text())
    qtbot.mouseClick(btn, Qt.LeftButton)
    assert triggered == ["cc"]


def test_sidebar_toggle_collapse_persists_to_store(qtbot):
    store = _make_store(collapsed=False)
    sb = _make_sidebar(qtbot, store)
    assert sb.repos_visible() is True
    sb.toggle_repos_section()
    assert sb.repos_visible() is False
    store.set_ui_pref.assert_called_with("repos_collapsed", True)


def test_sidebar_starts_collapsed_when_store_pref_is_true(qtbot):
    store = _make_store(collapsed=True)
    sb = _make_sidebar(qtbot, store)
    assert sb.repos_visible() is False


def test_sidebar_set_active_repo_updates_dot_marker(qtbot, tmp_path):
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    sb = _make_sidebar(qtbot, _make_store({str(repo_a): {}, str(repo_b): {}}))
    sb.set_active_repo(str(repo_b))
    texts = _button_texts(sb)
    assert any(t.startswith("● ") and "repo-b" in t for t in texts)
    assert any(t.startswith("○ ") and "repo-a" in t for t in texts)
