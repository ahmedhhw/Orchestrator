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


def test_worktree_panel_repo_scroll_has_no_fixed_height(qtbot, empty_store):
    from worktree_manager.ui.worktree_management_panel import WorktreeManagementPanel
    app = App(repo_path=None)
    qtbot.addWidget(app)
    # Trigger Worktree Management tab to mount the panel
    app._show_worktree_management()
    panel = app._current_panel
    assert isinstance(panel, WorktreeManagementPanel)
    scroll = panel._repo_scroll
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


def test_worktree_name_label_is_not_fixed_width(qtbot):
    from worktree_manager.main_window_vm import MainWindowViewModel
    from worktree_manager.models import WorktreeModel
    from worktree_manager.ui.per_repo_worktrees_view import PerRepoWorktreesView

    vm = MagicMock(spec=MainWindowViewModel)
    wt = WorktreeModel(
        path="/repos/proj", branch="main", is_main=True,
        last_commit_ts=0, is_stale=False, is_merged=False,
    )
    vm.load_worktrees.return_value = [wt]
    vm.list_branches_with_checkout_status.return_value = [("main", False)]

    view = PerRepoWorktreesView(
        vm=vm, repo_name="proj", on_cleanup=lambda: None, on_new=lambda: None,
    )
    qtbot.addWidget(view)

    assert view._worktree_rows, "expected at least one row"
    row = view._worktree_rows[0]
    layout = row.layout()
    name_label = layout.itemAt(1).widget()
    assert name_label.minimumWidth() != name_label.maximumWidth() or name_label.maximumWidth() > 200


def test_worktree_branch_combo_is_not_fixed_width(qtbot):
    from PySide6.QtWidgets import QComboBox
    from worktree_manager.main_window_vm import MainWindowViewModel
    from worktree_manager.models import WorktreeModel
    from worktree_manager.ui.per_repo_worktrees_view import PerRepoWorktreesView

    vm = MagicMock(spec=MainWindowViewModel)
    wt = WorktreeModel(
        path="/repos/proj", branch="main", is_main=True,
        last_commit_ts=0, is_stale=False, is_merged=False,
    )
    vm.load_worktrees.return_value = [wt]
    vm.list_branches_with_checkout_status.return_value = [("main", False)]

    view = PerRepoWorktreesView(
        vm=vm, repo_name="proj", on_cleanup=lambda: None, on_new=lambda: None,
    )
    qtbot.addWidget(view)

    row = view._worktree_rows[0]
    layout = row.layout()
    combo = next(
        layout.itemAt(i).widget()
        for i in range(layout.count())
        if isinstance(layout.itemAt(i).widget(), QComboBox)
    )
    assert combo.minimumWidth() != combo.maximumWidth() or combo.maximumWidth() > 160
