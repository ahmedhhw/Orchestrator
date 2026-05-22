import pytest
from unittest.mock import MagicMock, patch


def _ctk_available():
    try:
        import customtkinter
        return True
    except ImportError:
        return False


pytestmark = pytest.mark.skipif(not _ctk_available(), reason="customtkinter not installed")


@pytest.fixture
def app(tmp_path):
    mock_store = MagicMock()
    mock_store.all_repos.return_value = {}
    mock_store.all_projects.return_value = []
    mock_git = MagicMock()
    with patch("worktree_manager.config_store.ConfigStore.__init__", return_value=None), \
         patch("worktree_manager.config_store.ConfigStore.all_repos", return_value={}), \
         patch("worktree_manager.config_store.ConfigStore._load_raw", return_value={"repos": {}, "projects": {}}), \
         patch("worktree_manager.git_service.GitService.__init__", return_value=None):
        from worktree_manager.cli import App
        a = App(repo_path=None)
        a._store = mock_store
        a._git = mock_git
        yield a
        try:
            a._root.destroy()
        except Exception:
            pass


def test_sidebar_has_workspace_projects_button(app):
    import customtkinter as ctk

    def find_buttons(widget):
        texts = []
        for child in widget.winfo_children():
            if isinstance(child, ctk.CTkButton):
                texts.append(child.cget("text"))
            texts.extend(find_buttons(child))
        return texts

    all_button_texts = find_buttons(app._root)
    assert any("Workspace" in t or "Projects" in t for t in all_button_texts)


def test_show_workspace_projects_method_exists(app):
    assert hasattr(app, "_show_workspace_projects")
    assert callable(app._show_workspace_projects)
