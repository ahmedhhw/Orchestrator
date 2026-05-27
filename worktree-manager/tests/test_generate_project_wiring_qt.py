from pathlib import Path
from unittest.mock import MagicMock, patch

from worktree_manager.cli import App
from worktree_manager.models import RepoConfig
from worktree_manager.ui.worktree_management_panel import WorktreeManagementPanel


def _repo_cfg(path="/repos/proj"):
    return RepoConfig(
        repo_path=path, worktree_storage="/repos/proj-wt",
        stale_days=30, last_editor="cursor", last_editor_mode="reuse",
        last_opened="2026-05-19T10:00:00",
    )


def _make_app(qtbot, monkeypatch):
    store = MagicMock()
    cfg = _repo_cfg()
    store.all_repos.return_value = {"/repos/proj": cfg}
    store.get_repo.return_value = cfg
    store.get_ui_pref.side_effect = lambda key, default=None: default
    store.all_projects.return_value = []
    monkeypatch.setattr("worktree_manager.cli.ConfigStore", lambda *a, **kw: store)
    monkeypatch.setattr("worktree_manager.cli.GitService", lambda *a, **kw: MagicMock())

    with patch("worktree_manager.main_window_vm.MainWindowViewModel") as MockVM:
        MockVM.return_value.load_worktrees.return_value = []
        MockVM.return_value.list_branches_with_checkout_status.return_value = []
        app = App(repo_path="/repos/proj")
        qtbot.addWidget(app)

    return app, store


def test_worktree_panel_shown_when_repo_configured(qtbot, monkeypatch):
    app, _ = _make_app(qtbot, monkeypatch)
    assert isinstance(app._current_panel, WorktreeManagementPanel)


def test_right_pane_receives_on_generate_project_callback(qtbot, monkeypatch):
    app, _ = _make_app(qtbot, monkeypatch)
    right_pane = app._current_panel._right_pane
    assert right_pane is not None
    assert right_pane._on_generate_project is not None


def test_on_generate_project_creates_project_via_workspace_service(
    qtbot, monkeypatch, tmp_path
):
    app, store = _make_app(qtbot, monkeypatch)

    with patch(
        "worktree_manager.cli.WorkspaceService",
        return_value=MagicMock(generate_code_workspace=MagicMock()),
    ) as MockSvc:
        app._on_generate_project("/repos/proj-wt/feat-auth")

    MockSvc.return_value.generate_code_workspace.assert_called_once()
    call_args = MockSvc.return_value.generate_code_workspace.call_args[0][0]
    assert call_args.name == "feat-auth"
    assert len(call_args.entries) == 1
    assert call_args.entries[0].worktree_path == "/repos/proj-wt/feat-auth"


def test_on_generate_project_shows_toast_on_status_bar(qtbot, monkeypatch):
    app, _ = _make_app(qtbot, monkeypatch)

    with patch("worktree_manager.cli.WorkspaceService"):
        app._on_generate_project("/repos/proj-wt/feat-auth")

    # Toast is shown on the App's statusBar (not a per-panel _toast_label)
    assert "feat-auth" in app.statusBar().currentMessage()
