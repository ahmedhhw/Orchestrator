import pytest
from unittest.mock import MagicMock, patch, call
import worktree_manager.cli as cli_mod


def _make_app(repos=None):
    app = object.__new__(cli_mod.App)
    app._ctk = MagicMock()
    app._root = MagicMock()
    app._store = MagicMock()
    app._git = MagicMock()
    app._current_frame = None
    app._sidebar_frame = MagicMock()
    app._sidebar_frame.winfo_exists.return_value = True
    app._repo_scroll = MagicMock()
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


# ── _rebuild_repo_rows ────────────────────────────────────────────────────────

def test_rebuild_repo_rows_clears_existing_buttons():
    app = _make_app(repos={})
    old_btn = MagicMock()
    app._repo_buttons = {"/old": old_btn}

    with patch.object(app, "_update_repo_selection"):
        app._rebuild_repo_rows()

    assert "/old" not in app._repo_buttons


def test_rebuild_repo_rows_does_not_rebuild_sidebar_chrome():
    app = _make_app(repos={})
    original_sidebar = app._sidebar_frame

    with patch.object(app, "_update_repo_selection"):
        app._rebuild_repo_rows()

    assert app._sidebar_frame is original_sidebar


def test_rebuild_repo_rows_calls_update_repo_selection():
    app = _make_app(repos={})
    app._active_repo_path = "/a"

    with patch.object(app, "_update_repo_selection") as mock_update:
        app._rebuild_repo_rows()

    mock_update.assert_called_once_with("/a")


def test_rebuild_repo_rows_noop_when_no_scroll_frame():
    """If sidebar not fully built yet (e.g. collapsed), no crash."""
    app = _make_app(repos={"/a": MagicMock()})
    app._repo_scroll = None

    with patch.object(app, "_update_repo_selection"):
        app._rebuild_repo_rows()  # should not raise


# ── delete repo (non-active) calls _rebuild_repo_rows ────────────────────────

def test_delete_non_active_repo_calls_rebuild_not_show_sidebar():
    import tkinter.messagebox as mb
    app = _make_app()
    app._store.delete_repo = MagicMock()
    app._active_repo_path = "/other"

    with patch("tkinter.messagebox.askyesno", return_value=True), \
         patch.object(app, "_rebuild_repo_rows") as mock_rebuild, \
         patch.object(app, "_show_sidebar") as mock_rebuild_sidebar:
        app._confirm_delete_repo("/a", is_active=False)

    mock_rebuild.assert_called_once()
    mock_rebuild_sidebar.assert_not_called()


def test_delete_non_active_repo_does_not_repack_main_frame():
    """The main content frame should not be pack_forget/pack cycled on non-active delete."""
    app = _make_app()
    app._store.delete_repo = MagicMock()
    app._active_repo_path = "/other"
    main_frame = MagicMock()
    app._current_frame = main_frame

    with patch("tkinter.messagebox.askyesno", return_value=True), \
         patch.object(app, "_rebuild_repo_rows"):
        app._confirm_delete_repo("/a", is_active=False)

    main_frame.pack_forget.assert_not_called()


# ── collapse/expand calls _rebuild_repo_rows ─────────────────────────────────

def test_toggle_repos_section_never_calls_show_sidebar():
    app = _make_app()
    app._repos_collapsed = False
    app._store.set_ui_pref = MagicMock()

    with patch.object(app, "_rebuild_repo_rows"), \
         patch.object(app, "_show_sidebar") as mock_show_sidebar:
        app._toggle_repos_section()

    mock_show_sidebar.assert_not_called()


def test_toggle_repos_section_expand_calls_rebuild():
    """Expanding the section (collapsed→visible) refreshes the rows."""
    app = _make_app()
    app._repos_collapsed = True  # start collapsed, toggle to expanded
    app._store.set_ui_pref = MagicMock()

    with patch.object(app, "_rebuild_repo_rows") as mock_rebuild, \
         patch.object(app, "_show_sidebar"):
        app._toggle_repos_section()

    mock_rebuild.assert_called_once()


def test_toggle_repos_section_flips_collapsed_state():
    app = _make_app()
    app._repos_collapsed = False
    app._store.set_ui_pref = MagicMock()

    with patch.object(app, "_rebuild_repo_rows"):
        app._toggle_repos_section()

    assert app._repos_collapsed is True
    app._store.set_ui_pref.assert_called_once_with("repos_collapsed", True)


def test_toggle_repos_section_does_not_repack_main_frame():
    app = _make_app()
    app._repos_collapsed = False
    app._store.set_ui_pref = MagicMock()
    main_frame = MagicMock()
    app._current_frame = main_frame

    with patch.object(app, "_rebuild_repo_rows"):
        app._toggle_repos_section()

    main_frame.pack_forget.assert_not_called()


# ── refresh calls _rebuild_repo_rows for repo view ───────────────────────────

def test_refresh_calls_rebuild_repo_rows_not_show_main():
    app = _make_app()
    app._active_repo_path = "/repos/proj"
    app._cc_panel = MagicMock()
    app._wp_panel = None
    app._current_frame = MagicMock()

    with patch.object(app, "_rebuild_repo_rows") as mock_rebuild, \
         patch.object(app, "_show_main") as mock_show_main:
        app._refresh()

    mock_rebuild.assert_called_once()
    mock_show_main.assert_not_called()
