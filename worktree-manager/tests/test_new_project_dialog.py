import pytest
import time
from unittest.mock import MagicMock
from worktree_manager.workspace_projects_vm import WorkspaceProjectsViewModel
from worktree_manager.models import WorkspaceProject, WorkspaceEntry, WorktreeModel, RepoConfig
from worktree_manager.config_store import ConfigStore


def _ctk_available():
    try:
        import customtkinter
        return True
    except ImportError:
        return False


pytestmark = pytest.mark.skipif(not _ctk_available(), reason="customtkinter not installed")


@pytest.fixture(scope="module", autouse=True)
def require_display():
    try:
        import tkinter as tk
        r = tk.Tk()
        r.withdraw()
        r.destroy()
    except Exception:
        pytest.skip("no display available")


@pytest.fixture
def root():
    import tkinter as tk
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


@pytest.fixture
def repos():
    return {
        "/repos/api": RepoConfig(
            repo_path="/repos/api",
            worktree_storage="/repos/api-wt",
            stale_days=30,
            last_editor="cursor",
            last_editor_mode="reuse",
            last_opened="2026-05-19T10:00:00",
        ),
        "/repos/web": RepoConfig(
            repo_path="/repos/web",
            worktree_storage="/repos/web-wt",
            stale_days=30,
            last_editor="cursor",
            last_editor_mode="reuse",
            last_opened="2026-05-19T09:00:00",
        ),
    }


@pytest.fixture
def vm(repos):
    now = int(time.time())
    m = MagicMock(spec=WorkspaceProjectsViewModel)
    m.list_worktrees_for_repo.return_value = [
        WorktreeModel("/repos/api", "main", True, now, False, False),
        WorktreeModel("/repos/api-wt/fix-login", "fix/login", False, now - 3600, False, False),
    ]
    return m


def test_dialog_renders_without_crash(root, vm, repos):
    from worktree_manager.ui.new_project_dialog import NewProjectDialog
    dialog = NewProjectDialog(root, vm=vm, repos=repos, on_create=lambda name, entries: None)
    assert dialog.winfo_exists()
    dialog.destroy()


def test_dialog_has_project_name_field(root, vm, repos):
    import customtkinter as ctk
    from worktree_manager.ui.new_project_dialog import NewProjectDialog
    dialog = NewProjectDialog(root, vm=vm, repos=repos, on_create=lambda name, entries: None)

    def find_entries(widget):
        results = []
        for child in widget.winfo_children():
            if isinstance(child, ctk.CTkEntry):
                results.append(child)
            results.extend(find_entries(child))
        return results

    entries = find_entries(dialog)
    assert len(entries) >= 1
    dialog.destroy()


def test_dialog_has_add_button(root, vm, repos):
    import customtkinter as ctk
    from worktree_manager.ui.new_project_dialog import NewProjectDialog
    dialog = NewProjectDialog(root, vm=vm, repos=repos, on_create=lambda name, entries: None)

    def find_buttons(widget):
        texts = []
        for child in widget.winfo_children():
            if isinstance(child, ctk.CTkButton):
                texts.append(child.cget("text"))
            texts.extend(find_buttons(child))
        return texts

    button_texts = find_buttons(dialog)
    assert any("Add" in t or "+" in t for t in button_texts)
    dialog.destroy()


def test_dialog_add_entry_appears_in_list(root, vm, repos):
    from worktree_manager.ui.new_project_dialog import NewProjectDialog
    dialog = NewProjectDialog(root, vm=vm, repos=repos, on_create=lambda name, entries: None)
    initial_count = len(dialog._entries)
    dialog._add_entry("/repos/api-wt/fix-login")
    assert len(dialog._entries) == initial_count + 1
    dialog.destroy()


def test_dialog_remove_entry_removes_from_list(root, vm, repos):
    from worktree_manager.ui.new_project_dialog import NewProjectDialog
    dialog = NewProjectDialog(root, vm=vm, repos=repos, on_create=lambda name, entries: None)
    dialog._add_entry("/repos/api-wt/fix-login")
    assert len(dialog._entries) == 1
    dialog._remove_entry("/repos/api-wt/fix-login")
    assert len(dialog._entries) == 0
    dialog.destroy()


def test_dialog_create_project_calls_on_create(root, vm, repos):
    from worktree_manager.ui.new_project_dialog import NewProjectDialog
    calls = []
    dialog = NewProjectDialog(root, vm=vm, repos=repos, on_create=lambda name, entries: calls.append((name, entries)))
    dialog._name_var.set("my-feature")
    dialog._add_entry("/repos/api-wt/fix-login")
    dialog._create_project()
    assert len(calls) == 1
    assert calls[0][0] == "my-feature"
    assert any(e.worktree_path == "/repos/api-wt/fix-login" for e in calls[0][1])


def test_dialog_create_project_does_not_call_on_create_with_empty_name(root, vm, repos):
    from worktree_manager.ui.new_project_dialog import NewProjectDialog
    calls = []
    dialog = NewProjectDialog(root, vm=vm, repos=repos, on_create=lambda name, entries: calls.append((name, entries)))
    dialog._name_var.set("")
    dialog._add_entry("/repos/api-wt/fix-login")
    dialog._create_project()
    assert len(calls) == 0
    dialog.destroy()
