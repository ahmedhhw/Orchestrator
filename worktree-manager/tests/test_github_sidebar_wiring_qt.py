import pytest
from unittest.mock import MagicMock, patch


def _make_app(qtbot):
    from worktree_manager.github_vm import TokenState
    with patch("worktree_manager.cli.ConfigStore") as MockStore, \
         patch("worktree_manager.cli.GitService"), \
         patch("worktree_manager.cli.GitHubViewModel") as MockVM:
        store = MockStore.return_value
        store.get_repo.return_value = None
        store.all_repos.return_value = {}
        store.get_ui_pref.side_effect = lambda k, d=None: d
        store.get_github_token.return_value = None
        store.get_github_poll_interval.return_value = 30
        store.get_experimental_features.return_value = True
        # Configure the vm mock so GitHubPanel can be constructed safely
        vm_instance = MockVM.return_value
        vm_instance.list_open_pr_repos_display.return_value = {}
        vm_instance.prs = []
        vm_instance._store = store
        type(vm_instance).token_state = property(lambda self: TokenState.MISSING)
        from worktree_manager.cli import App
        app = App(repo_path=None)
        qtbot.addWidget(app)
    return app


def test_github_entry_in_sidebar(qtbot):
    app = _make_app(qtbot)
    sidebar = app._sidebar
    assert "github" in sidebar._tab_buttons


def test_clicking_github_shows_github_panel(qtbot):
    app = _make_app(qtbot)
    app._sidebar._activate("github")
    assert app._current_panel is app._panel_cache.get("github")


def test_github_panel_cached_on_second_click(qtbot):
    app = _make_app(qtbot)
    app._sidebar._activate("github")
    first = app._current_panel
    app._sidebar._activate("worktree_management")
    app._sidebar._activate("github")
    assert app._current_panel is first
