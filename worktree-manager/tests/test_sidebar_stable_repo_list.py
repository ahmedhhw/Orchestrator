import pytest
from unittest.mock import MagicMock, patch, call
import worktree_manager.cli as cli_mod


def _make_app(repos=None):
    """Return a minimal App instance with mocked Tk/store."""
    app = object.__new__(cli_mod.App)
    app._ctk = MagicMock()
    app._root = MagicMock()
    app._store = MagicMock()
    app._git = MagicMock()
    app._current_frame = None
    app._sidebar_frame = None
    app._repo_scroll = None
    app._repo_buttons = {}
    app._active_repo_path = None
    app._repos_collapsed = False
    app._cc_panel = None
    app._wp_panel = None
    if repos is not None:
        app._store.all_repos.return_value = repos
    else:
        app._store.all_repos.return_value = {}
    return app


# ── _update_repo_selection ────────────────────────────────────────────────────

def test_update_repo_selection_activates_new_button():
    app = _make_app()
    old_btn = MagicMock()
    new_btn = MagicMock()
    app._repo_buttons = {"/a": old_btn, "/b": new_btn}
    app._active_repo_path = "/a"

    app._update_repo_selection("/b")

    new_btn.configure.assert_called_once()
    kwargs = new_btn.configure.call_args.kwargs
    assert kwargs["fg_color"] == "gray30"
    assert kwargs["text_color"] == "white"
    assert "● " in kwargs["text"]


def test_update_repo_selection_deactivates_old_button():
    app = _make_app()
    old_btn = MagicMock()
    old_btn.cget.return_value = "● myrepo"
    new_btn = MagicMock()
    app._repo_buttons = {"/a": old_btn, "/b": new_btn}
    app._active_repo_path = "/a"

    app._update_repo_selection("/b")

    old_btn.configure.assert_called_once()
    kwargs = old_btn.configure.call_args.kwargs
    assert kwargs["fg_color"] == "transparent"
    assert "○ " in kwargs["text"]


def test_update_repo_selection_sets_active_repo_path():
    app = _make_app()
    btn = MagicMock()
    app._repo_buttons = {"/b": btn}
    app._active_repo_path = None

    app._update_repo_selection("/b")

    assert app._active_repo_path == "/b"


def test_update_repo_selection_noop_when_path_not_in_buttons():
    """If the path isn't tracked (e.g. sidebar not built yet), no crash."""
    app = _make_app()
    app._repo_buttons = {}
    app._active_repo_path = None
    # Should not raise
    app._update_repo_selection("/unknown")


def test_update_repo_selection_noop_when_same_repo():
    """Clicking the already-active repo should not crash or double-configure."""
    app = _make_app()
    btn = MagicMock()
    app._repo_buttons = {"/a": btn}
    app._active_repo_path = "/a"

    app._update_repo_selection("/a")

    btn.configure.assert_not_called()


# ── _ensure_sidebar / stable sidebar ─────────────────────────────────────────

def test_ensure_sidebar_builds_sidebar_when_none_exists():
    app = _make_app()
    with patch.object(app, "_show_sidebar") as mock_show:
        app._ensure_sidebar()
    mock_show.assert_called_once()


def test_ensure_sidebar_noop_when_sidebar_exists():
    app = _make_app()
    existing = MagicMock()
    existing.winfo_exists.return_value = True
    app._sidebar_frame = existing
    with patch.object(app, "_show_sidebar") as mock_show:
        app._ensure_sidebar()
    mock_show.assert_not_called()


def test_show_main_does_not_call_show_sidebar_when_sidebar_exists():
    """_show_main should update selection in-place, not rebuild the sidebar."""
    from worktree_manager.models import RepoConfig
    app = _make_app(repos={"/repos/proj": MagicMock()})
    app._store.get_repo.return_value = MagicMock(spec=RepoConfig)

    existing_sidebar = MagicMock()
    existing_sidebar.winfo_exists.return_value = True
    app._sidebar_frame = existing_sidebar

    btn = MagicMock()
    app._repo_buttons = {"/repos/proj": btn}
    app._cc_vm = MagicMock()

    with patch("worktree_manager.ui.main_window.MainWindow") as MockWindow, \
         patch("worktree_manager.main_window_vm.MainWindowViewModel"):
        MockWindow.return_value = MagicMock()
        with patch.object(app, "_show_sidebar") as mock_rebuild:
            app._show_main("/repos/proj")

    mock_rebuild.assert_not_called()


def test_show_main_calls_update_repo_selection():
    """_show_main should call _update_repo_selection with the new path."""
    from worktree_manager.models import RepoConfig
    app = _make_app(repos={"/repos/proj": MagicMock()})
    app._store.get_repo.return_value = MagicMock(spec=RepoConfig)

    existing_sidebar = MagicMock()
    existing_sidebar.winfo_exists.return_value = True
    app._sidebar_frame = existing_sidebar
    app._repo_buttons = {"/repos/proj": MagicMock()}
    app._cc_vm = MagicMock()

    with patch("worktree_manager.ui.main_window.MainWindow") as MockWindow, \
         patch("worktree_manager.main_window_vm.MainWindowViewModel"), \
         patch.object(app, "_update_repo_selection") as mock_update:
        MockWindow.return_value = MagicMock()
        app._show_main("/repos/proj")

    mock_update.assert_called_once_with("/repos/proj")
