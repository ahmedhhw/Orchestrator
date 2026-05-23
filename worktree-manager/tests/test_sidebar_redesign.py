import pytest
from unittest.mock import MagicMock, patch, call
from pathlib import Path


def _ctk_available():
    try:
        import customtkinter
        return True
    except ImportError:
        return False


pytestmark = pytest.mark.skipif(not _ctk_available(), reason="customtkinter not installed")


def _make_repo_config(path, last_opened="2026-01-01T00:00:00"):
    from worktree_manager.models import RepoConfig
    return RepoConfig(
        repo_path=path,
        worktree_storage=path + "-wt",
        stale_days=30,
        last_editor="cursor",
        last_editor_mode="new",
        last_opened=last_opened,
    )


@pytest.fixture
def app(tmp_path):
    repos = {
        "/repos/alpha": _make_repo_config("/repos/alpha", "2026-05-01T00:00:00"),
        "/repos/beta":  _make_repo_config("/repos/beta",  "2026-04-01T00:00:00"),
        "/repos/gamma": _make_repo_config("/repos/gamma", "2026-03-01T00:00:00"),
    }
    with patch("worktree_manager.config_store.ConfigStore.__init__", return_value=None), \
         patch("worktree_manager.config_store.ConfigStore._load_raw",
               return_value={"repos": {}, "projects": {}}), \
         patch("worktree_manager.git_service.GitService.__init__", return_value=None):
        from worktree_manager.cli import App
        a = App(repo_path=None)
        a._store = MagicMock()
        a._store.all_repos.return_value = repos
        a._store.get_ui_pref.return_value = None
        a._git = MagicMock()
        yield a
        try:
            a._root.destroy()
        except Exception:
            pass


def _all_buttons(widget):
    import customtkinter as ctk
    texts = []
    for child in widget.winfo_children():
        if isinstance(child, ctk.CTkButton):
            texts.append(child.cget("text"))
        texts.extend(_all_buttons(child))
    return texts


def _find_widgets(widget, widget_type):
    found = []
    for child in widget.winfo_children():
        if isinstance(child, widget_type):
            found.append(child)
        found.extend(_find_widgets(child, widget_type))
    return found


# ── Layout order: top buttons appear before REPOS toggle ─────────────────────

def test_command_center_button_exists_in_sidebar(app):
    app._show_sidebar(active_repo_path=None)
    texts = _all_buttons(app._sidebar_frame)
    assert any("Command Center" in t or "Cmd" in t for t in texts)


def test_workspace_projects_button_exists_in_sidebar(app):
    app._show_sidebar(active_repo_path=None)
    texts = _all_buttons(app._sidebar_frame)
    assert any("Workspace" in t or "Projects" in t for t in texts)


def test_repos_toggle_button_exists_in_sidebar(app):
    app._show_sidebar(active_repo_path=None)
    texts = _all_buttons(app._sidebar_frame)
    assert any("REPOS" in t for t in texts)


def test_command_center_button_appears_before_repos_toggle(app):
    import customtkinter as ctk
    app._show_sidebar(active_repo_path=None)

    buttons_in_order = []
    def collect(widget):
        for child in widget.winfo_children():
            if isinstance(child, ctk.CTkButton):
                buttons_in_order.append(child.cget("text"))
            collect(child)

    collect(app._sidebar_frame)
    cc_idx = next((i for i, t in enumerate(buttons_in_order) if "Command" in t or "Cmd" in t), None)
    repos_idx = next((i for i, t in enumerate(buttons_in_order) if "REPOS" in t), None)
    assert cc_idx is not None
    assert repos_idx is not None
    assert cc_idx < repos_idx, f"Command Center ({cc_idx}) should appear before REPOS toggle ({repos_idx})"


def test_workspace_projects_button_appears_before_repos_toggle(app):
    import customtkinter as ctk
    app._show_sidebar(active_repo_path=None)

    buttons_in_order = []
    def collect(widget):
        for child in widget.winfo_children():
            if isinstance(child, ctk.CTkButton):
                buttons_in_order.append(child.cget("text"))
            collect(child)

    collect(app._sidebar_frame)
    wp_idx = next((i for i, t in enumerate(buttons_in_order) if "Workspace" in t or "Projects" in t), None)
    repos_idx = next((i for i, t in enumerate(buttons_in_order) if "REPOS" in t), None)
    assert wp_idx is not None
    assert repos_idx is not None
    assert wp_idx < repos_idx, f"Workspace Projects ({wp_idx}) should appear before REPOS toggle ({repos_idx})"


# ── Collapsed state: no repo name buttons visible ─────────────────────────────

def test_repos_collapsed_hides_repo_buttons(app):
    app._store.get_ui_pref.return_value = True  # collapsed
    app._show_sidebar(active_repo_path=None)
    texts = _all_buttons(app._sidebar_frame)
    assert not any(t.strip().lstrip("● ○").strip() in ("alpha", "beta", "gamma") for t in texts), \
        f"Repo buttons should be hidden when collapsed, found: {texts}"


def test_repos_expanded_shows_repo_buttons(app):
    app._store.get_ui_pref.return_value = False  # expanded
    app._show_sidebar(active_repo_path=None)
    texts = _all_buttons(app._sidebar_frame)
    repo_names = [t for t in texts if any(n in t for n in ("alpha", "beta", "gamma"))]
    assert len(repo_names) == 3, f"Expected 3 repo buttons when expanded, found: {texts}"


# ── Scrollable frame used for repo list ───────────────────────────────────────

def test_repo_list_uses_scrollable_frame_when_expanded(app):
    import customtkinter as ctk
    app._store.get_ui_pref.return_value = False  # expanded
    app._show_sidebar(active_repo_path=None)
    scrollables = _find_widgets(app._sidebar_frame, ctk.CTkScrollableFrame)
    assert len(scrollables) >= 1, "Repo list should use CTkScrollableFrame"


def test_repo_list_no_scrollable_frame_when_collapsed(app):
    import customtkinter as ctk
    app._store.get_ui_pref.return_value = True  # collapsed
    app._show_sidebar(active_repo_path=None)
    scrollables = _find_widgets(app._sidebar_frame, ctk.CTkScrollableFrame)
    assert len(scrollables) == 0, "No scrollable frame when repos are collapsed"


# ── Toggle persists collapse state ────────────────────────────────────────────

def test_toggle_repos_saves_collapsed_true_when_expanding_from_expanded(app):
    app._store.get_ui_pref.return_value = False  # currently expanded
    app._repos_collapsed = False
    app._show_sidebar(active_repo_path=None)
    app._toggle_repos_section()
    app._store.set_ui_pref.assert_called_with("repos_collapsed", True)


def test_toggle_repos_saves_collapsed_false_when_expanding_from_collapsed(app):
    app._store.get_ui_pref.return_value = True  # currently collapsed
    app._repos_collapsed = True
    app._show_sidebar(active_repo_path=None)
    app._toggle_repos_section()
    app._store.set_ui_pref.assert_called_with("repos_collapsed", False)


# ── Collapse state loaded from ui_prefs on sidebar build ─────────────────────

def test_collapse_state_loaded_from_ui_prefs(app):
    app._store.get_ui_pref.return_value = True
    app._show_sidebar(active_repo_path=None)
    assert app._repos_collapsed is True


def test_expand_state_loaded_from_ui_prefs(app):
    app._store.get_ui_pref.return_value = False
    app._show_sidebar(active_repo_path=None)
    assert app._repos_collapsed is False


def test_collapse_state_defaults_to_false_when_no_pref_saved(app):
    app._store.get_ui_pref.return_value = None
    app._show_sidebar(active_repo_path=None)
    assert app._repos_collapsed is False


# ── ✕ delete button present on every repo row ────────────────────────────────

def test_every_repo_row_has_delete_button(app):
    import customtkinter as ctk
    app._store.get_ui_pref.return_value = False  # expanded
    app._show_sidebar(active_repo_path=None)

    delete_buttons = []
    def collect(widget):
        for child in widget.winfo_children():
            if isinstance(child, ctk.CTkButton) and child.cget("text") == "✕":
                delete_buttons.append(child)
            collect(child)

    collect(app._sidebar_frame)
    assert len(delete_buttons) == 3, f"Expected 3 ✕ buttons (one per repo), got {len(delete_buttons)}"


def test_delete_buttons_absent_when_collapsed(app):
    import customtkinter as ctk
    app._store.get_ui_pref.return_value = True  # collapsed
    app._show_sidebar(active_repo_path=None)

    delete_buttons = []
    def collect(widget):
        for child in widget.winfo_children():
            if isinstance(child, ctk.CTkButton) and child.cget("text") == "✕":
                delete_buttons.append(child)
            collect(child)

    collect(app._sidebar_frame)
    assert len(delete_buttons) == 0


# ── Delete flow: calls delete_repo and refreshes sidebar ─────────────────────

def test_delete_repo_calls_store_delete_repo(app):
    app._store.get_ui_pref.return_value = False
    app._show_sidebar(active_repo_path=None)
    with patch("tkinter.messagebox.askyesno", return_value=True):
        app._confirm_delete_repo("/repos/beta", is_active=False)
    app._store.delete_repo.assert_called_once_with("/repos/beta")


def test_delete_repo_cancelled_does_not_call_store(app):
    app._store.get_ui_pref.return_value = False
    app._show_sidebar(active_repo_path=None)
    with patch("tkinter.messagebox.askyesno", return_value=False):
        app._confirm_delete_repo("/repos/beta", is_active=False)
    app._store.delete_repo.assert_not_called()


def test_delete_active_repo_clears_active_repo_path(app):
    app._store.get_ui_pref.return_value = False
    app._active_repo_path = "/repos/alpha"
    app._show_sidebar(active_repo_path="/repos/alpha")
    with patch("tkinter.messagebox.askyesno", return_value=True):
        app._confirm_delete_repo("/repos/alpha", is_active=True)
    assert app._active_repo_path is None


def test_delete_non_active_repo_preserves_active_repo_path(app):
    app._store.get_ui_pref.return_value = False
    app._active_repo_path = "/repos/alpha"
    app._show_sidebar(active_repo_path="/repos/alpha")
    with patch("tkinter.messagebox.askyesno", return_value=True):
        app._confirm_delete_repo("/repos/beta", is_active=False)
    assert app._active_repo_path == "/repos/alpha"


# ── Active repo highlight still works ────────────────────────────────────────

def test_active_repo_button_has_active_styling(app):
    import customtkinter as ctk
    app._store.get_ui_pref.return_value = False  # expanded
    app._show_sidebar(active_repo_path="/repos/alpha")

    def find_active(widget):
        for child in widget.winfo_children():
            if isinstance(child, ctk.CTkButton):
                text = child.cget("text")
                fg = child.cget("fg_color")
                if "alpha" in text and fg not in ("transparent", "", None):
                    return True
            if find_active(child):
                return True
        return False

    assert find_active(app._sidebar_frame), "Active repo should have non-transparent fg_color"
