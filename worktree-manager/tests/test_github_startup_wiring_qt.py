"""Tests for GitHub VM startup construction and panel cache behaviour (iter 0)."""
import pytest
from unittest.mock import MagicMock, patch
from worktree_manager.github_vm import TokenState


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_store(experimental=False, token=None):
    store = MagicMock()
    store.get_repo.return_value = None
    store.all_repos.return_value = {}
    store.get_ui_pref.side_effect = lambda k, d=None: d
    store.get_github_token.return_value = token
    store.get_github_poll_interval.return_value = 30
    store.get_experimental_features.return_value = experimental
    return store


def _make_vm_mock(token_state=TokenState.MISSING, prs=None):
    """Return a MagicMock GitHubViewModel with realistic token_state and prs."""
    vm = MagicMock()
    type(vm).token_state = property(lambda self: token_state)
    vm.prs = prs if prs is not None else []
    vm.list_open_pr_repos_display.return_value = {}
    vm._store.get_ui_pref.return_value = True
    vm._store.get_github_poll_interval.return_value = 30
    return vm


def _make_app(qtbot, store, vm_factory=None):
    """Construct App under patches. Returns (app, MockGitHubViewModel class)."""
    with patch("worktree_manager.cli.ConfigStore", return_value=store), \
         patch("worktree_manager.cli.GitService"), \
         patch("worktree_manager.cli.GitHubViewModel") as MockVM:
        if vm_factory is not None:
            MockVM.side_effect = vm_factory
        from worktree_manager.cli import App
        app = App(repo_path=None)
        qtbot.addWidget(app)
    return app, MockVM


# ── Test 1: VM constructed at startup when experimental on ────────────────────

def test_github_vm_constructed_at_startup_when_experimental_on(qtbot):
    store = _make_store(experimental=True)
    app, MockVM = _make_app(qtbot, store)
    MockVM.assert_called_once_with(store=store)
    assert hasattr(app, "_github_vm")


# ── Test 2: VM not constructed when experimental off ──────────────────────────

def test_github_vm_not_constructed_at_startup_when_experimental_off(qtbot):
    store = _make_store(experimental=False)
    app, MockVM = _make_app(qtbot, store)
    MockVM.assert_not_called()
    assert not hasattr(app, "_github_vm")


# ── Test 3: Opening panel reuses already-constructed VM ───────────────────────

def test_opening_panel_reuses_vm_constructed_at_startup(qtbot):
    from PySide6.QtWidgets import QWidget
    store = _make_store(experimental=True)
    vm_instance = _make_vm_mock(token_state=TokenState.MISSING)
    stub_panel = QWidget()

    with patch("worktree_manager.cli.ConfigStore", return_value=store), \
         patch("worktree_manager.cli.GitService"), \
         patch("worktree_manager.cli.GitHubViewModel", return_value=vm_instance) as MockVM, \
         patch("worktree_manager.ui.github_panel.GitHubPanel", return_value=stub_panel):
        from worktree_manager.cli import App
        app = App(repo_path=None)
        qtbot.addWidget(app)
        app._show_github_panel()

    # VM must only be constructed once — at startup, not again when panel opens
    assert MockVM.call_count == 1


# ── Test 4: Panel renders cached PRs immediately, loading label stays hidden ──

def test_panel_renders_cached_prs_immediately_with_no_loading_flash(qtbot):
    from worktree_manager.github_models import PullRequest
    from worktree_manager.ui.github_panel import GitHubPanel

    cached_pr = MagicMock(spec=PullRequest)
    cached_pr.number = 1
    cached_pr.title = "My PR"
    cached_pr.draft = False
    cached_pr.state = "open"
    cached_pr.owner = "org"
    cached_pr.repo = "myrepo"
    cached_pr.head_branch = "feat"
    cached_pr.base_branch = "main"
    cached_pr.body = ""
    cached_pr.html_url = "https://github.com/org/myrepo/pull/1"
    cached_pr.checks = []
    cached_pr.reviews = []
    cached_pr.comments = []
    cached_pr.mergeable = True

    vm = _make_vm_mock(token_state=TokenState.CONFIGURED, prs=[cached_pr])
    panel = GitHubPanel(vm=vm)
    qtbot.addWidget(panel)

    assert panel._loading_label.isHidden()
    assert not panel._pr_list.isHidden()


# ── Test 5: Panel shows loading label when no cached PRs and token configured ─

def test_panel_shows_loading_label_when_no_cache_and_token_configured(qtbot):
    from worktree_manager.ui.github_panel import GitHubPanel

    vm = _make_vm_mock(token_state=TokenState.CONFIGURED, prs=[])
    panel = GitHubPanel(vm=vm)
    qtbot.addWidget(panel)

    assert not panel._loading_label.isHidden()
    assert panel._pr_list.isHidden()


# ── Test 6: pr_event before panel opened still triggers notification ──────────

def test_pr_event_before_panel_opened_triggers_notification(qtbot):
    store = _make_store(experimental=True)
    vm_instance = _make_vm_mock()

    with patch("worktree_manager.cli.ConfigStore", return_value=store), \
         patch("worktree_manager.cli.GitService"), \
         patch("worktree_manager.cli.GitHubViewModel", return_value=vm_instance):
        from worktree_manager.cli import App
        app = App(repo_path=None)
        qtbot.addWidget(app)

    # pr_event.connect must have been called with app._on_pr_event at startup,
    # before any panel is opened
    connect_calls = vm_instance.pr_event.connect.call_args_list
    connected_handlers = [c.args[0] for c in connect_calls]
    assert app._on_pr_event in connected_handlers
