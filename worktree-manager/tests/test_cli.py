import pytest
import sys
from unittest.mock import MagicMock, patch
from worktree_manager.cli import parse_args, resolve_repo_path
from worktree_manager.git_service import GitService


def test_parse_args_no_argument():
    args = parse_args([])
    assert args.repo_path is None


def test_parse_args_with_path():
    args = parse_args(["/repos/proj"])
    assert args.repo_path == "/repos/proj"


def test_resolve_repo_path_valid(tmp_path):
    git = MagicMock(spec=GitService)
    git.is_valid_repo.return_value = True
    repo = tmp_path / "myrepo"
    repo.mkdir()
    result = resolve_repo_path(str(repo), git)
    assert result == str(repo)


def test_resolve_repo_path_invalid(tmp_path, capsys):
    git = MagicMock(spec=GitService)
    git.is_valid_repo.return_value = False
    with pytest.raises(SystemExit):
        resolve_repo_path(str(tmp_path / "notarepo"), git)
    captured = capsys.readouterr()
    assert "not a git repository" in captured.err.lower()


def test_resolve_repo_path_none_returns_none():
    git = MagicMock(spec=GitService)
    result = resolve_repo_path(None, git)
    assert result is None


def _make_vm(candidates):
    vm = MagicMock()
    vm.all_cleanup_candidates.return_value = candidates
    return vm


def test_show_cleanup_opens_wizard_when_branch_candidates_exist():
    from worktree_manager.models import CleanupCandidate
    import worktree_manager.cli as cli_mod
    from unittest.mock import patch
    # path=None means branch-only candidate
    vm = _make_vm([
        CleanupCandidate("chore/deps", None, False, True, 0)
    ])
    with patch("worktree_manager.ui.cleanup_wizard.CleanupWizard") as MockWizard:
        with patch("tkinter.messagebox.showinfo") as mock_info:
            app = object.__new__(cli_mod.App)
            app._root = MagicMock()
            app._current_frame = MagicMock()
            app._show_cleanup(vm)
    MockWizard.assert_called_once()
    mock_info.assert_not_called()


def test_show_cleanup_shows_wizard_for_worktree_branch_candidates():
    import worktree_manager.cli as cli_mod
    from unittest.mock import patch
    from worktree_manager.models import CleanupCandidate
    # Worktree candidates (path set) are now shown in the wizard
    vm = _make_vm([
        CleanupCandidate("chore/deps", "/wt/chore-deps", False, True, 0)
    ])
    with patch("worktree_manager.ui.cleanup_wizard.CleanupWizard") as MockWizard:
        app = object.__new__(cli_mod.App)
        app._root = MagicMock()
        app._current_frame = MagicMock()
        app._show_cleanup(vm)
    MockWizard.assert_called_once()


def test_show_cleanup_shows_messagebox_when_empty():
    import threading
    import worktree_manager.cli as cli_mod
    from unittest.mock import patch, call
    vm = _make_vm([])
    # The wizard always opens first (loading screen) with candidates=None.
    # When no candidates are found the background thread schedules destroy+showinfo
    # via wizard.after(). We verify the wizard was constructed and after() was
    # scheduled (the actual Tk dispatch happens only in a real event loop).
    with patch("worktree_manager.ui.cleanup_wizard.CleanupWizard") as MockWizard:
        with patch("tkinter.messagebox.showinfo") as mock_info:
            app = object.__new__(cli_mod.App)
            app._root = MagicMock()
            app._current_frame = MagicMock()
            threads_before = set(threading.enumerate())
            app._show_cleanup(vm)
            new_threads = set(threading.enumerate()) - threads_before
            for t in new_threads:
                t.join(timeout=5)
    MockWizard.assert_called_once_with(
        app._root, candidates=None, on_delete_selected=MockWizard.call_args.kwargs["on_delete_selected"]
    )
    # _done is scheduled via after(0, _done); verify after was called at least once
    wizard_instance = MockWizard.return_value
    assert wizard_instance.after.called


def test_app_has_window_registry():
    import worktree_manager.cli as cli_mod
    from worktree_manager.window_registry import WindowRegistry
    app = object.__new__(cli_mod.App)
    app._window_registry = WindowRegistry()
    assert isinstance(app._window_registry, WindowRegistry)


def test_show_main_creates_vm_with_correct_services():
    import worktree_manager.cli as cli_mod
    from unittest.mock import patch, MagicMock
    from worktree_manager.models import RepoConfig

    store = MagicMock()
    store.get_repo.return_value = RepoConfig(
        repo_path="/repos/proj",
        worktree_storage="/repos/proj-wt",
        stale_days=30,
        last_editor="cursor",
        last_editor_mode="reuse",
        last_opened="2026-05-19T10:00:00",
    )
    store.save_repo.return_value = None
    store.all_repos.return_value = {"/repos/proj": store.get_repo.return_value}
    captured = {}

    def fake_vm_init(self, repo_path, config_store, git_service):
        captured["repo_path"] = repo_path
        captured["config_store"] = config_store
        self._repo_path = repo_path
        self._store = config_store
        self._git = git_service
        self._worktrees = []

    with patch("worktree_manager.main_window_vm.MainWindowViewModel.__init__", fake_vm_init), \
         patch("worktree_manager.ui.main_window.MainWindow") as MockWindow, \
         patch.object(cli_mod.App, "_show_sidebar"):
        MockWindow.return_value = MagicMock()
        app = object.__new__(cli_mod.App)
        app._ctk = MagicMock()
        app._root = MagicMock()
        app._store = store
        app._git = MagicMock()
        app._current_frame = None
        app._sidebar_frame = None
        app._show_main("/repos/proj")

    assert captured["repo_path"] == "/repos/proj"
    assert captured["config_store"] is store


def test_app_shows_empty_main_when_no_repo_path():
    import worktree_manager.cli as cli_mod
    from worktree_manager.window_registry import WindowRegistry

    app = object.__new__(cli_mod.App)
    app._ctk = MagicMock()
    app._root = MagicMock()
    app._store = MagicMock()
    app._store.all_repos.return_value = {}
    app._git = MagicMock()
    app._editor = MagicMock()
    app._current_frame = None
    app._sidebar_frame = None
    app._window_registry = WindowRegistry()

    shown = {}
    app._show_sidebar = lambda active_repo_path=None: shown.update({"sidebar": active_repo_path})

    app._show_empty_main()
    assert "sidebar" in shown



def test_show_cleanup_passes_all_candidates_including_worktree_branches():
    import threading
    import worktree_manager.cli as cli_mod
    from worktree_manager.models import CleanupCandidate
    worktree_candidate = CleanupCandidate("wt/branch", "/wt/wt-branch", False, True, 0)
    branch_candidate = CleanupCandidate("orphan", None, True, False, 0)
    vm = _make_vm([worktree_candidate, branch_candidate])
    # Wizard opens with candidates=None; after load, finish_loading is scheduled via after()
    with patch("worktree_manager.ui.cleanup_wizard.CleanupWizard") as MockWizard:
        app = object.__new__(cli_mod.App)
        app._root = MagicMock()
        app._current_frame = MagicMock()
        threads_before = set(threading.enumerate())
        app._show_cleanup(vm)
        new_threads = set(threading.enumerate()) - threads_before
        for t in new_threads:
            t.join(timeout=5)
    # wizard opened with candidates=None (loading screen)
    assert MockWizard.call_args.kwargs["candidates"] is None
    # finish_loading was scheduled via after(0, ...) with the real candidates list
    wizard_instance = MockWizard.return_value
    after_calls = wizard_instance.after.call_args_list
    # find the _done call — it's after(0, _done); extract and call it to inspect
    assert len(after_calls) >= 1
    # The last after() call's second arg is _done; calling it invokes finish_loading
    _done = after_calls[-1][0][1]
    _done()
    finish_loading_calls = wizard_instance.finish_loading.call_args_list
    assert len(finish_loading_calls) == 1
    passed_candidates = finish_loading_calls[0][0][0]
    branches = [c.branch for c in passed_candidates]
    assert "wt/branch" in branches
    assert "orphan" in branches


def test_refresh_calls_show_main_when_repo_active():
    import worktree_manager.cli as cli_mod
    app = object.__new__(cli_mod.App)
    app._active_repo_path = "/repos/proj"
    app._cc_panel = MagicMock()
    app._wp_panel = None
    app._current_frame = MagicMock()  # on worktree view — not cc or wp panel
    with patch.object(app, "_show_main") as mock_show:
        app._refresh()
    mock_show.assert_called_once_with("/repos/proj")


def test_refresh_is_noop_when_no_active_repo_and_not_on_command_center():
    import worktree_manager.cli as cli_mod
    app = object.__new__(cli_mod.App)
    app._active_repo_path = None
    app._cc_panel = MagicMock()
    app._current_frame = MagicMock()  # different object — not the cc_panel
    with patch.object(app, "_show_main") as mock_show:
        with patch.object(app, "_show_command_center") as mock_cc:
            app._refresh()
    mock_show.assert_not_called()
    mock_cc.assert_not_called()


def test_refresh_reloads_command_center_when_active():
    import worktree_manager.cli as cli_mod
    app = object.__new__(cli_mod.App)
    app._active_repo_path = None
    cc_panel = MagicMock()
    app._cc_panel = cc_panel
    app._current_frame = cc_panel
    with patch.object(app, "_show_command_center") as mock_cc:
        app._refresh()
    mock_cc.assert_called_once()


def test_show_landing_is_noop(tmp_path):
    import worktree_manager.cli as cli_mod
    from worktree_manager.window_registry import WindowRegistry

    app = object.__new__(cli_mod.App)
    app._ctk = MagicMock()
    app._root = MagicMock()
    app._store = MagicMock()
    app._store.all_repos.return_value = {}
    app._git = MagicMock()
    app._editor = MagicMock()
    app._current_frame = None
    app._sidebar_frame = None
    app._window_registry = WindowRegistry()

    shown = {}
    app._show_sidebar = lambda active: shown.update({"sidebar": True})
    app._show_empty_main = lambda: shown.update({"empty": True})

    app._show_landing()
    assert shown.get("empty") is True
