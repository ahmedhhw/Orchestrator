from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QPushButton

from worktree_manager.cli import App
from worktree_manager.ui.sidebar import Sidebar
from worktree_manager.ui.sidebar_strip import SidebarStrip


@pytest.fixture
def empty_store(monkeypatch):
    store = MagicMock()
    store.all_repos.return_value = {}
    store.get_ui_pref.side_effect = lambda key, default=None: default
    monkeypatch.setattr("worktree_manager.cli.ConfigStore", lambda *a, **kw: store)
    monkeypatch.setattr("worktree_manager.cli.GitService", lambda *a, **kw: MagicMock())
    return store


def test_app_sidebar_has_hide_button(qtbot, empty_store):
    app = App(repo_path=None)
    qtbot.addWidget(app)
    texts = [b.text() for b in app._sidebar.findChildren(QPushButton)]
    assert any("Hide" in t for t in texts)


def test_collapse_sidebar_hides_sidebar_and_shows_strip(qtbot, empty_store):
    app = App(repo_path=None)
    qtbot.addWidget(app)
    app._collapse_sidebar()

    assert app._sidebar.isHidden()
    assert app._sidebar_strip is not None
    assert isinstance(app._sidebar_strip, SidebarStrip)


def test_clicking_strip_restores_sidebar(qtbot, empty_store):
    app = App(repo_path=None)
    qtbot.addWidget(app)
    app._collapse_sidebar()
    app._restore_sidebar()

    assert not app._sidebar.isHidden()
    assert app._sidebar_strip is None


def test_collapse_restore_cycle_no_crash(qtbot, empty_store):
    app = App(repo_path=None)
    qtbot.addWidget(app)
    for _ in range(3):
        app._collapse_sidebar()
        app._restore_sidebar()
    assert not app._sidebar.isHidden()
