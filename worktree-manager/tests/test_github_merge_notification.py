import pytest
from unittest.mock import MagicMock, patch
from worktree_manager.cli import App


def _make_app(qtbot, monkeypatch):
    store = MagicMock()
    store.get_ui_pref.side_effect = lambda key, default=None: default
    store.all_repos.return_value = {}
    store.all_projects.return_value = []
    store.get_github_token.return_value = None
    store.get_github_poll_interval.return_value = 30
    monkeypatch.setattr("worktree_manager.cli.ConfigStore", lambda *a, **kw: store)
    monkeypatch.setattr("worktree_manager.cli.GitService", lambda *a, **kw: MagicMock())
    with patch("worktree_manager.main_window_vm.MainWindowViewModel") as MockVM:
        MockVM.return_value.load_worktrees.return_value = []
        MockVM.return_value.list_branches_with_checkout_status.return_value = []
        app = App()
        qtbot.addWidget(app)
    return app, store


def test_merge_notification_fires_when_enabled(qtbot, monkeypatch):
    app, store = _make_app(qtbot, monkeypatch)
    store.get_ui_pref.side_effect = lambda key, default=None: True if key == "github_notifications_enabled" else default

    shown = []
    with patch.object(app, "_show_notification", side_effect=lambda t, b: shown.append((t, b))):
        app._on_pr_event(("myorg", "myrepo", 1), "pr_merged", '✅ "My Work" merged')

    assert len(shown) == 1
    assert "My Work" in shown[0][1]
    assert "merged" in shown[0][1]
