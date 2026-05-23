import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(scope="module", autouse=True)
def require_display():
    try:
        import tkinter as tk
        r = tk.Tk()
        r.withdraw()
        r.destroy()
    except Exception:
        pytest.skip("no display available")


def _make_app(tmp_path):
    from worktree_manager.config_store import ConfigStore
    from worktree_manager.models import RepoConfig
    import worktree_manager.cli as cli_mod
    from worktree_manager.window_registry import WindowRegistry

    store = ConfigStore(tmp_path / "config.json")
    store.save_repo(RepoConfig(
        repo_path=str(tmp_path),
        worktree_storage=str(tmp_path / "wt"),
        stale_days=30,
        last_editor="cursor",
        last_editor_mode="reuse",
        last_opened="2026-05-20T10:00:00",
    ))

    import customtkinter as ctk
    app = object.__new__(cli_mod.App)
    app._ctk = ctk
    app._root = ctk.CTk()
    app._root.withdraw()
    app._store = store
    app._git = MagicMock()
    app._git.list_worktrees.return_value = []
    app._editor = MagicMock()
    app._current_frame = None
    app._sidebar_frame = None
    app._repo_buttons = {}
    app._active_repo_path = None
    app._cc_panel = None
    app._window_registry = WindowRegistry()

    from worktree_manager.command_center_vm import CommandCenterViewModel
    app._cc_vm = CommandCenterViewModel(config_store=store, git_service=app._git)

    app._root.bind_all("<Command-k>", lambda e: app._open_command_palette())
    return app


@pytest.fixture
def app(tmp_path):
    a = _make_app(tmp_path)
    yield a
    a._root.destroy()


def test_app_has_command_center_vm(app):
    from worktree_manager.command_center_vm import CommandCenterViewModel
    assert isinstance(app._cc_vm, CommandCenterViewModel)


def test_sidebar_contains_command_center_button(app):
    app._show_sidebar(active_repo_path=None)
    texts = []
    for w in app._sidebar_frame.winfo_children():
        try:
            texts.append(w.cget("text"))
        except Exception:
            pass
    assert any("Command Center" in t or "⊞" in t for t in texts)


def test_show_command_center_replaces_main_frame(app):
    app._show_command_center()
    from worktree_manager.ui.command_center_panel import CommandCenterPanel
    assert isinstance(app._current_frame, CommandCenterPanel)


def test_close_command_center_returns_to_empty_main(app):
    app._show_command_center()
    app._close_command_center()
    from worktree_manager.ui.command_center_panel import CommandCenterPanel
    assert not isinstance(app._current_frame, CommandCenterPanel)


