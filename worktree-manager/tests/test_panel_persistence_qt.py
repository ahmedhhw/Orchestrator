import shiboken6
from unittest.mock import MagicMock, patch

from worktree_manager.cli import App
from worktree_manager.ui.branch_management_panel import BranchManagementPanel
from worktree_manager.ui.command_center_panel import CommandCenterPanel
from worktree_manager.ui.workspace_projects_panel import WorkspaceProjectsPanel
from worktree_manager.ui.worktree_management_panel import WorktreeManagementPanel


def _make_app(qtbot):
    with (
        patch("worktree_manager.cli.ConfigStore") as MockStore,
        patch("worktree_manager.cli.GitService"),
    ):
        MockStore.return_value.get_repo.return_value = None
        MockStore.return_value.all_repos.return_value = {}
        MockStore.return_value.get_ui_pref.side_effect = lambda k, d=None: d
        app = App(repo_path=None)
        qtbot.addWidget(app)
    return app


# ── WorkspaceProjectsPanel persistence ──────────────────────────────────────

def test_workspace_projects_panel_reuses_same_instance(qtbot):
    app = _make_app(qtbot)
    app._show_workspace_projects()
    first = app._current_panel
    assert isinstance(first, WorkspaceProjectsPanel)
    app._show_worktree_management()
    app._show_workspace_projects()
    assert app._current_panel is first


def test_switching_away_from_workspace_projects_hides_not_destroys(qtbot):
    app = _make_app(qtbot)
    app._show_workspace_projects()
    panel = app._current_panel
    app._show_worktree_management()
    assert shiboken6.isValid(panel)
    assert panel.isHidden()


def test_workspace_projects_close_restores_on_reopen(qtbot):
    app = _make_app(qtbot)
    app._show_workspace_projects()
    panel = app._current_panel
    panel.trigger_close()
    assert not isinstance(app._current_panel, WorkspaceProjectsPanel)
    app._show_workspace_projects()
    assert app._current_panel is panel


# ── WorktreeManagementPanel persistence ─────────────────────────────────────

def test_worktree_management_panel_reuses_same_instance(qtbot):
    app = _make_app(qtbot)
    app._show_worktree_management()
    first = app._current_panel
    assert isinstance(first, WorktreeManagementPanel)
    app._show_branch_management()
    app._show_worktree_management()
    assert app._current_panel is first


def test_switching_away_from_worktree_management_hides_not_destroys(qtbot):
    app = _make_app(qtbot)
    app._show_worktree_management()
    panel = app._current_panel
    app._show_branch_management()
    assert shiboken6.isValid(panel)
    assert panel.isHidden()


# ── BranchManagementPanel persistence ───────────────────────────────────────

def test_branch_management_panel_reuses_same_instance(qtbot):
    app = _make_app(qtbot)
    app._show_branch_management()
    first = app._current_panel
    assert isinstance(first, BranchManagementPanel)
    app._show_worktree_management()
    app._show_branch_management()
    assert app._current_panel is first


def test_switching_away_from_branch_management_hides_not_destroys(qtbot):
    app = _make_app(qtbot)
    app._show_branch_management()
    panel = app._current_panel
    app._show_worktree_management()
    assert shiboken6.isValid(panel)
    assert panel.isHidden()


# ── Cross-panel: all four survive together ───────────────────────────────────

def test_all_four_panels_are_cached_independently(qtbot):
    app = _make_app(qtbot)
    app._show_command_center()
    cc = app._current_panel
    app._show_workspace_projects()
    wp = app._current_panel
    app._show_worktree_management()
    wt = app._current_panel
    app._show_branch_management()
    bm = app._current_panel

    assert len({id(cc), id(wp), id(wt), id(bm)}) == 4
    for panel in (cc, wp, wt):
        assert shiboken6.isValid(panel)
        assert panel.isHidden()

    app._show_command_center()
    assert app._current_panel is cc
