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


def test_pr_event_notification_fires_when_enabled(qtbot, monkeypatch):
    app, store = _make_app(qtbot, monkeypatch)
    store.get_ui_pref.side_effect = lambda key, default=None: True if key == "github_notifications_enabled" else default

    shown = []
    with patch.object(app, "_show_notification", side_effect=lambda t, b: shown.append((t, b))):
        app._on_pr_event(1, "ci_failed", '❌ "My Work" — checks failed')

    assert len(shown) == 1
    assert shown[0][0] == "Pull Requests"
    assert "My Work" in shown[0][1]


def test_pr_event_notification_suppressed_when_disabled(qtbot, monkeypatch):
    app, store = _make_app(qtbot, monkeypatch)
    store.get_ui_pref.side_effect = lambda key, default=None: False if key == "github_notifications_enabled" else default

    shown = []
    with patch.object(app, "_show_notification", side_effect=lambda t, b: shown.append((t, b))):
        app._on_pr_event(1, "ci_passed", '✅ "My Work" — all checks passed')

    assert shown == []


def test_pr_event_alert_fires_with_notification(qtbot, monkeypatch):
    app, store = _make_app(qtbot, monkeypatch)
    store.get_ui_pref.side_effect = lambda key, default=None: True if key == "github_notifications_enabled" else default

    with patch.object(app, "_show_notification"), \
         patch("worktree_manager.cli.QApplication.alert") as mock_alert:
        app._on_pr_event(1, "ci_failed", '❌ "My Work" — checks failed')

    mock_alert.assert_called_once()
