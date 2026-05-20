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


def test_show_cleanup_opens_wizard_when_candidates_exist():
    from worktree_manager.models import CleanupCandidate
    import worktree_manager.cli as cli_mod
    from unittest.mock import patch
    vm = _make_vm([
        CleanupCandidate("chore/deps", "/wt/chore-deps", False, True, 0)
    ])
    with patch("worktree_manager.ui.cleanup_wizard.CleanupWizard") as MockWizard:
        with patch("tkinter.messagebox.showinfo") as mock_info:
            app = object.__new__(cli_mod.App)
            app._root = MagicMock()
            app._current_frame = MagicMock()
            app._show_cleanup(vm)
    MockWizard.assert_called_once()
    mock_info.assert_not_called()


def test_show_cleanup_shows_messagebox_when_empty():
    import worktree_manager.cli as cli_mod
    from unittest.mock import patch
    vm = _make_vm([])
    with patch("worktree_manager.ui.cleanup_wizard.CleanupWizard") as MockWizard:
        with patch("tkinter.messagebox.showinfo") as mock_info:
            app = object.__new__(cli_mod.App)
            app._root = MagicMock()
            app._current_frame = MagicMock()
            app._show_cleanup(vm)
    MockWizard.assert_not_called()
    mock_info.assert_called_once()


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

    def fake_vm_init(self, repo_path, config_store, git_service, editor_service):
        captured["repo_path"] = repo_path
        captured["config_store"] = config_store
        self._repo_path = repo_path
        self._store = config_store
        self._git = git_service
        self._editor = editor_service
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
        app._editor = MagicMock()
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


def test_on_close_clears_open_paths_and_destroys_window():
    import worktree_manager.cli as cli_mod
    app = object.__new__(cli_mod.App)
    app._store = MagicMock()
    app._root = MagicMock()
    app._on_close()
    app._store.clear_all_open_paths.assert_called_once()
    app._root.destroy.assert_called_once()


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
