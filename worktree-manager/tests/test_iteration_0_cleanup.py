"""Iteration 0 cleanup: assert that dead modules and obsolete tests are gone."""
import importlib
import pathlib

import pytest


def test_scroll_fix_module_removed():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("worktree_manager.ui.scroll_fix")


@pytest.mark.parametrize("relpath", [
    "tests/test_hover_scoped_scroll.py",
    "tests/test_main_window_iter0.py",
    "tests/test_sidebar_redesign.py",
    "tests/test_sidebar_stable_repo_list.py",
    "tests/test_workspace_projects_sidebar_wiring.py",
    "tests/test_cli.py",
])
def test_legacy_ctk_test_file_removed(relpath):
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    assert not (repo_root / relpath).exists(), \
        f"{relpath} still exists — delete it as part of Iteration 0 cleanup"


def test_no_iter0_ui_file_imports_customtkinter():
    """Iteration 0's rewritten UI files must not import customtkinter or tkinter."""
    import worktree_manager.cli as cli_mod
    import worktree_manager.ui.landing_screen as ls_mod
    import worktree_manager.ui.main_window as mw_mod
    import worktree_manager.ui.sidebar as sb_mod
    for mod in (cli_mod, ls_mod, mw_mod, sb_mod):
        src = pathlib.Path(mod.__file__).read_text()
        assert "customtkinter" not in src, f"{mod.__name__} still imports customtkinter"
        assert "import tkinter" not in src, f"{mod.__name__} still imports tkinter"


def test_app_can_be_constructed_and_destroyed_cleanly(qtbot, monkeypatch):
    """End-to-end smoke: App constructs, shows, and tears down without raising."""
    from unittest.mock import MagicMock
    store = MagicMock()
    store.all_repos.return_value = {}
    store.get_ui_pref.side_effect = lambda key, default=None: default
    monkeypatch.setattr("worktree_manager.cli.ConfigStore", lambda *a, **kw: store)
    monkeypatch.setattr("worktree_manager.cli.GitService", lambda *a, **kw: MagicMock())
    from worktree_manager.cli import App
    app = App(repo_path=None)
    qtbot.addWidget(app)
    app.show()
    qtbot.waitExposed(app)
    app.close()
