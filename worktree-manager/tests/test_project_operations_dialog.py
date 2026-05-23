import pytest
import time
from unittest.mock import MagicMock
from worktree_manager.workspace_projects_vm import WorkspaceProjectsViewModel
from worktree_manager.models import WorkspaceProject, WorkspaceEntry, WorktreeModel, RepoConfig


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
            last_opened="2026-05-22T10:00:00",
        ),
    }


@pytest.fixture
def vm():
    now = int(time.time())
    m = MagicMock(spec=WorkspaceProjectsViewModel)
    m.list_worktrees_for_repo.return_value = [
        WorktreeModel("/repos/api", "main", True, now, False, False),
        WorktreeModel("/repos/api-wt/feat", "feat", False, now - 3600, False, False),
    ]
    return m


@pytest.fixture
def existing_project():
    return WorkspaceProject(
        name="my-project",
        entries=[
            WorkspaceEntry(worktree_path="/repos/api"),
            WorkspaceEntry(worktree_path="/repos/api-wt/feat"),
        ],
    )


def _make_create_dialog(root, vm, repos, on_create=None):
    from worktree_manager.ui.project_operations_dialog import ProjectOperationsDialog
    return ProjectOperationsDialog(
        root, vm=vm, repos=repos,
        on_create=on_create or (lambda name, entries: None),
    )


def _make_edit_dialog(root, vm, repos, existing_project, on_edit=None):
    from worktree_manager.ui.project_operations_dialog import ProjectOperationsDialog
    return ProjectOperationsDialog(
        root, vm=vm, repos=repos,
        on_edit=on_edit or (lambda old, new, entries: None),
        existing_project=existing_project,
    )


# --- Create mode ---

def test_create_dialog_renders_without_crash(root, vm, repos):
    d = _make_create_dialog(root, vm, repos)
    assert d.winfo_exists()
    d.destroy()


def test_create_dialog_title_is_new_project(root, vm, repos):
    d = _make_create_dialog(root, vm, repos)
    assert "New" in d.title()
    d.destroy()


def test_create_dialog_confirm_button_says_create_project(root, vm, repos):
    import customtkinter as ctk
    d = _make_create_dialog(root, vm, repos)

    def find_buttons(w):
        texts = []
        for child in w.winfo_children():
            if isinstance(child, ctk.CTkButton):
                texts.append(child.cget("text"))
            texts.extend(find_buttons(child))
        return texts

    assert any("Create" in t for t in find_buttons(d))
    d.destroy()


def test_create_confirm_calls_on_create(root, vm, repos):
    calls = []
    d = _make_create_dialog(root, vm, repos, on_create=lambda n, e: calls.append((n, e)))
    d._name_var.set("brand-new")
    d.trigger_add_entry("/repos/api")
    d.trigger_confirm()
    assert len(calls) == 1
    assert calls[0][0] == "brand-new"
    assert any(e.worktree_path == "/repos/api" for e in calls[0][1])


def test_create_confirm_does_not_call_on_create_with_empty_name(root, vm, repos):
    calls = []
    d = _make_create_dialog(root, vm, repos, on_create=lambda n, e: calls.append((n, e)))
    d._name_var.set("")
    d.trigger_add_entry("/repos/api")
    d.trigger_confirm()
    assert calls == []
    d.destroy()


def test_create_confirm_does_not_call_on_create_with_no_entries(root, vm, repos):
    calls = []
    d = _make_create_dialog(root, vm, repos, on_create=lambda n, e: calls.append((n, e)))
    d._name_var.set("proj")
    d.trigger_confirm()
    assert calls == []
    d.destroy()


def test_add_and_remove_entry(root, vm, repos):
    d = _make_create_dialog(root, vm, repos)
    d.trigger_add_entry("/repos/api")
    assert "/repos/api" in d.get_entries()
    d.trigger_remove_entry("/repos/api")
    assert "/repos/api" not in d.get_entries()
    d.destroy()


def test_duplicate_entry_not_added_twice(root, vm, repos):
    d = _make_create_dialog(root, vm, repos)
    d.trigger_add_entry("/repos/api")
    d.trigger_add_entry("/repos/api")
    assert d.get_entries().count("/repos/api") == 1
    d.destroy()


# --- Edit mode ---

def test_edit_dialog_renders_without_crash(root, vm, repos, existing_project):
    d = _make_edit_dialog(root, vm, repos, existing_project)
    assert d.winfo_exists()
    d.destroy()


def test_edit_dialog_title_is_edit_project(root, vm, repos, existing_project):
    d = _make_edit_dialog(root, vm, repos, existing_project)
    assert "Edit" in d.title()
    d.destroy()


def test_edit_dialog_prepopulates_name(root, vm, repos, existing_project):
    d = _make_edit_dialog(root, vm, repos, existing_project)
    assert d.get_name() == "my-project"
    d.destroy()


def test_edit_dialog_prepopulates_entries(root, vm, repos, existing_project):
    d = _make_edit_dialog(root, vm, repos, existing_project)
    entries = d.get_entries()
    assert "/repos/api" in entries
    assert "/repos/api-wt/feat" in entries
    d.destroy()


def test_edit_dialog_confirm_button_says_save_changes(root, vm, repos, existing_project):
    import customtkinter as ctk
    d = _make_edit_dialog(root, vm, repos, existing_project)

    def find_buttons(w):
        texts = []
        for child in w.winfo_children():
            if isinstance(child, ctk.CTkButton):
                texts.append(child.cget("text"))
            texts.extend(find_buttons(child))
        return texts

    assert any("Save" in t for t in find_buttons(d))
    d.destroy()


def test_edit_confirm_calls_on_edit_with_old_name(root, vm, repos, existing_project):
    calls = []
    d = _make_edit_dialog(root, vm, repos, existing_project,
                          on_edit=lambda old, new, entries: calls.append((old, new, entries)))
    d.trigger_confirm()
    assert len(calls) == 1
    assert calls[0][0] == "my-project"


def test_edit_confirm_passes_new_name_when_renamed(root, vm, repos, existing_project):
    calls = []
    d = _make_edit_dialog(root, vm, repos, existing_project,
                          on_edit=lambda old, new, entries: calls.append((old, new, entries)))
    d._name_var.set("renamed-project")
    d.trigger_confirm()
    assert calls[0][1] == "renamed-project"


def test_edit_confirm_passes_updated_entries(root, vm, repos, existing_project):
    calls = []
    d = _make_edit_dialog(root, vm, repos, existing_project,
                          on_edit=lambda old, new, entries: calls.append((old, new, entries)))
    d.trigger_remove_entry("/repos/api-wt/feat")
    d.trigger_add_entry("/repos/api-wt/new")
    d.trigger_confirm()
    paths = [e.worktree_path for e in calls[0][2]]
    assert "/repos/api" in paths
    assert "/repos/api-wt/new" in paths
    assert "/repos/api-wt/feat" not in paths


def test_edit_does_not_call_on_create(root, vm, repos, existing_project):
    create_calls = []
    edit_calls = []
    from worktree_manager.ui.project_operations_dialog import ProjectOperationsDialog
    d = ProjectOperationsDialog(
        root, vm=vm, repos=repos,
        on_create=lambda n, e: create_calls.append(n),
        on_edit=lambda old, new, e: edit_calls.append(new),
        existing_project=existing_project,
    )
    d.trigger_confirm()
    assert create_calls == []
    assert len(edit_calls) == 1
