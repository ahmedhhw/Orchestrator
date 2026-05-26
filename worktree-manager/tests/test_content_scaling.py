from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QSizePolicy

from worktree_manager.cli import App
from worktree_manager.models import RepoConfig


@pytest.fixture
def empty_store(monkeypatch):
    store = MagicMock()
    store.all_repos.return_value = {}
    store.get_ui_pref.side_effect = lambda key, default=None: default
    monkeypatch.setattr("worktree_manager.cli.ConfigStore", lambda *a, **kw: store)
    monkeypatch.setattr("worktree_manager.cli.GitService", lambda *a, **kw: MagicMock())
    return store


# ── Main window: no hard-coded 1400×900 size ────────────────────────────────

def test_main_window_minimum_width_is_not_oversized(qtbot, empty_store):
    app = App(repo_path=None)
    qtbot.addWidget(app)
    assert app.minimumWidth() <= 900


def test_main_window_minimum_height_is_not_oversized(qtbot, empty_store):
    app = App(repo_path=None)
    qtbot.addWidget(app)
    assert app.minimumHeight() <= 600


# ── Sidebar: no fixed width, has a minimum instead ──────────────────────────

def test_sidebar_is_not_fixed_width(qtbot, empty_store):
    app = App(repo_path=None)
    qtbot.addWidget(app)
    sidebar = app._sidebar
    # A widget with setFixedWidth(n) will have minimumWidth == maximumWidth == n.
    # We want it to be able to grow, so maximumWidth must not equal minimumWidth
    # (or if equal, both must be the Qt default QWIDGETSIZE_MAX).
    assert sidebar.minimumWidth() != sidebar.maximumWidth() or sidebar.maximumWidth() > 220


def test_sidebar_repo_scroll_has_no_fixed_height(qtbot, empty_store):
    app = App(repo_path=None)
    qtbot.addWidget(app)
    scroll = app._sidebar._repo_scroll
    # setFixedHeight pins min==max to the given value. We want it to stretch.
    assert scroll.minimumHeight() != scroll.maximumHeight() or scroll.maximumHeight() > 220


# ── Worktree rows: name label and combo are not fixed-width ─────────────────

@pytest.fixture
def loaded_store(monkeypatch):
    store = MagicMock()
    cfg = RepoConfig(
        repo_path="/repos/proj", worktree_storage="/repos/proj-wt",
        stale_days=30, last_editor="cursor", last_editor_mode="reuse",
        last_opened="2026-05-19T10:00:00",
    )
    store.get_repo.return_value = cfg
    store.all_repos.return_value = {"/repos/proj": cfg}
    store.get_ui_pref.side_effect = lambda key, default=None: default
    store.get_commands.return_value = []
    store.all_projects.return_value = []
    store.get_mru.return_value = []
    monkeypatch.setattr("worktree_manager.cli.ConfigStore", lambda *a, **kw: store)
    monkeypatch.setattr("worktree_manager.cli.GitService", lambda *a, **kw: MagicMock())
    return store


def test_worktree_name_label_is_not_fixed_width(qtbot, loaded_store):
    from worktree_manager.models import WorktreeModel
    from worktree_manager.ui.main_window import MainWindow

    vm = MagicMock()
    wt = WorktreeModel(
        path="/repos/proj", branch="main", is_main=True,
        last_commit_ts=0, is_stale=False, is_merged=False,
    )
    vm.load_worktrees.return_value = [wt]
    vm.list_branches_with_checkout_status.return_value = [("main", False)]
    vm.is_protected_branch.return_value = False

    with patch("worktree_manager.main_window_vm.MainWindowViewModel") as MockVM:
        MockVM.return_value = vm
        app = App(repo_path="/repos/proj")
        qtbot.addWidget(app)

    mw = app._current_panel
    assert mw._worktree_rows, "expected at least one row"
    row = mw._worktree_rows[0]
    # Find the name label (second widget in the row layout after the dot)
    layout = row.layout()
    name_label = layout.itemAt(1).widget()
    # setFixedWidth pins min==max; we want it not pinned (maxWidth > minWidth)
    assert name_label.minimumWidth() != name_label.maximumWidth() or name_label.maximumWidth() > 200


def test_worktree_branch_combo_is_not_fixed_width(qtbot, loaded_store):
    from PySide6.QtWidgets import QComboBox
    from worktree_manager.models import WorktreeModel
    from worktree_manager.ui.main_window import MainWindow

    vm = MagicMock()
    wt = WorktreeModel(
        path="/repos/proj", branch="main", is_main=True,
        last_commit_ts=0, is_stale=False, is_merged=False,
    )
    vm.load_worktrees.return_value = [wt]
    vm.list_branches_with_checkout_status.return_value = [("main", False)]
    vm.is_protected_branch.return_value = False

    with patch("worktree_manager.main_window_vm.MainWindowViewModel") as MockVM:
        MockVM.return_value = vm
        app = App(repo_path="/repos/proj")
        qtbot.addWidget(app)

    mw = app._current_panel
    row = mw._worktree_rows[0]
    layout = row.layout()
    combo = next(
        layout.itemAt(i).widget()
        for i in range(layout.count())
        if isinstance(layout.itemAt(i).widget(), QComboBox)
    )
    # setFixedWidth pins min==max; we want combo to be able to grow
    assert combo.minimumWidth() != combo.maximumWidth() or combo.maximumWidth() > 160
