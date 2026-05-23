import pytest
import time
from unittest.mock import MagicMock, patch
from worktree_manager.workspace_projects_vm import WorkspaceProjectsViewModel
from worktree_manager.models import WorkspaceProject, WorkspaceEntry, WorktreeModel


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


def _make_vm_store(editor="cursor"):
    store = MagicMock()
    store.get_ui_pref.return_value = editor
    return store


@pytest.fixture
def vm():
    m = MagicMock(spec=WorkspaceProjectsViewModel)
    m.load_projects.return_value = []
    m.list_worktrees_for_repo.return_value = []
    m._store = _make_vm_store()
    return m


@pytest.fixture
def vm_with_projects():
    m = MagicMock(spec=WorkspaceProjectsViewModel)
    m.load_projects.return_value = [
        WorkspaceProject("my-feature", [
            WorkspaceEntry("/repos/api-wt/fix-login"),
            WorkspaceEntry("/repos/web-wt/fix-login"),
        ]),
        WorkspaceProject("auth-refactor", []),
    ]
    m.list_worktrees_for_repo.return_value = []
    m._store = _make_vm_store()
    return m


def test_panel_renders_without_crash(root, vm):
    from worktree_manager.ui.workspace_projects_panel import WorkspaceProjectsPanel
    panel = WorkspaceProjectsPanel(root, vm=vm, on_close=lambda: None)
    assert panel.winfo_exists()
    panel.destroy()


def test_panel_shows_new_button(root, vm):
    import customtkinter as ctk
    from worktree_manager.ui.workspace_projects_panel import WorkspaceProjectsPanel
    panel = WorkspaceProjectsPanel(root, vm=vm, on_close=lambda: None)

    def find_buttons(widget):
        results = []
        for child in widget.winfo_children():
            if isinstance(child, ctk.CTkButton):
                results.append(child.cget("text"))
            results.extend(find_buttons(child))
        return results

    button_texts = find_buttons(panel)
    assert any("New" in t or "+" in t for t in button_texts)
    panel.destroy()


def test_panel_shows_editor_toggle(root, vm):
    import customtkinter as ctk
    from worktree_manager.ui.workspace_projects_panel import WorkspaceProjectsPanel
    panel = WorkspaceProjectsPanel(root, vm=vm, on_close=lambda: None)

    def find_segmented(widget):
        results = []
        for child in widget.winfo_children():
            if isinstance(child, ctk.CTkSegmentedButton):
                results.append(child)
            results.extend(find_segmented(child))
        return results

    segs = find_segmented(panel)
    assert len(segs) >= 1
    panel.destroy()


def test_panel_shows_project_names(root, vm_with_projects):
    import customtkinter as ctk
    from worktree_manager.ui.workspace_projects_panel import WorkspaceProjectsPanel
    panel = WorkspaceProjectsPanel(root, vm=vm_with_projects, on_close=lambda: None)

    def collect_labels(widget):
        texts = []
        if isinstance(widget, ctk.CTkLabel):
            texts.append(widget.cget("text"))
        for child in widget.winfo_children():
            texts.extend(collect_labels(child))
        return texts

    def collect_buttons(widget):
        texts = []
        if isinstance(widget, ctk.CTkButton):
            texts.append(widget.cget("text"))
        for child in widget.winfo_children():
            texts.extend(collect_buttons(child))
        return texts

    all_text = " ".join(collect_labels(panel) + collect_buttons(panel))
    assert "my-feature" in all_text
    assert "auth-refactor" in all_text
    panel.destroy()


def test_panel_open_project_calls_vm(root, vm_with_projects):
    from worktree_manager.ui.workspace_projects_panel import WorkspaceProjectsPanel
    panel = WorkspaceProjectsPanel(root, vm=vm_with_projects, on_close=lambda: None)
    panel._open_project("my-feature", "cursor")
    vm_with_projects.open_project.assert_called_once_with("my-feature", "cursor")
    panel.destroy()


def test_panel_delete_project_calls_vm_and_refreshes(root, vm_with_projects):
    from worktree_manager.ui.workspace_projects_panel import WorkspaceProjectsPanel
    panel = WorkspaceProjectsPanel(root, vm=vm_with_projects, on_close=lambda: None)
    panel._delete_project("my-feature")
    vm_with_projects.delete_project.assert_called_once_with("my-feature")
    assert vm_with_projects.load_projects.call_count >= 2
    panel.destroy()


def test_panel_shows_edit_button_per_project(root, vm_with_projects):
    import customtkinter as ctk
    from worktree_manager.ui.workspace_projects_panel import WorkspaceProjectsPanel
    panel = WorkspaceProjectsPanel(root, vm=vm_with_projects, on_close=lambda: None)

    def find_buttons(widget):
        texts = []
        if isinstance(widget, ctk.CTkButton):
            texts.append(widget.cget("text"))
        for child in widget.winfo_children():
            texts.extend(find_buttons(child))
        return texts

    button_texts = find_buttons(panel)
    edit_buttons = [t for t in button_texts if t == "Edit"]
    assert len(edit_buttons) == 2  # one per project
    panel.destroy()


def test_handle_edit_calls_vm_update_project(root, vm_with_projects):
    from worktree_manager.ui.workspace_projects_panel import WorkspaceProjectsPanel
    from worktree_manager.models import WorkspaceEntry
    panel = WorkspaceProjectsPanel(root, vm=vm_with_projects, on_close=lambda: None)
    entries = [WorkspaceEntry("/repos/api-wt/main")]
    panel._handle_edit("my-feature", "my-feature-renamed", entries)
    vm_with_projects.update_project.assert_called_once_with(
        old_name="my-feature", new_name="my-feature-renamed", entries=entries
    )
    panel.destroy()


def test_handle_edit_refreshes_panel(root, vm_with_projects):
    from worktree_manager.ui.workspace_projects_panel import WorkspaceProjectsPanel
    from worktree_manager.models import WorkspaceEntry
    panel = WorkspaceProjectsPanel(root, vm=vm_with_projects, on_close=lambda: None)
    initial_load_count = vm_with_projects.load_projects.call_count
    panel._handle_edit("my-feature", "my-feature", [WorkspaceEntry("/repos/api-wt/main")])
    assert vm_with_projects.load_projects.call_count > initial_load_count
    panel.destroy()


def test_panel_empty_state_visible_when_no_projects(root, vm):
    import customtkinter as ctk
    from worktree_manager.ui.workspace_projects_panel import WorkspaceProjectsPanel
    panel = WorkspaceProjectsPanel(root, vm=vm, on_close=lambda: None)

    def collect_labels(widget):
        texts = []
        if isinstance(widget, ctk.CTkLabel):
            texts.append(widget.cget("text"))
        for child in widget.winfo_children():
            texts.extend(collect_labels(child))
        return texts

    texts = collect_labels(panel)
    assert any("No" in t or "project" in t.lower() for t in texts)
    panel.destroy()


def test_panel_loads_saved_editor_pref(root):
    from worktree_manager.ui.workspace_projects_panel import WorkspaceProjectsPanel
    m = MagicMock(spec=WorkspaceProjectsViewModel)
    m.load_projects.return_value = []
    m._store = _make_vm_store(editor="vscode")
    panel = WorkspaceProjectsPanel(root, vm=m, on_close=lambda: None)
    assert panel._editor_var.get() == "vscode"
    panel.destroy()


def test_panel_persists_editor_pref_on_change(root, vm):
    from worktree_manager.ui.workspace_projects_panel import WorkspaceProjectsPanel
    panel = WorkspaceProjectsPanel(root, vm=vm, on_close=lambda: None)
    panel._editor_var.set("vscode")
    vm._store.set_ui_pref.assert_called_with("projects_editor", "vscode")
    panel.destroy()


def test_panel_loads_saved_collapsed_state(root):
    from worktree_manager.ui.workspace_projects_panel import WorkspaceProjectsPanel
    m = MagicMock(spec=WorkspaceProjectsViewModel)
    m.load_projects.return_value = []
    store = _make_vm_store()
    store.get_ui_pref.side_effect = lambda key, default=None: {
        "projects_editor": "cursor",
        "projects_collapsed": ["auth-refactor"],
    }.get(key, default)
    m._store = store
    panel = WorkspaceProjectsPanel(root, vm=m, on_close=lambda: None)
    assert "auth-refactor" in panel._collapsed
    panel.destroy()


def test_panel_persists_collapsed_state_on_toggle(root, vm_with_projects):
    from worktree_manager.ui.workspace_projects_panel import WorkspaceProjectsPanel
    panel = WorkspaceProjectsPanel(root, vm=vm_with_projects, on_close=lambda: None)
    panel._toggle_collapse("my-feature")
    saved = vm_with_projects._store.set_ui_pref.call_args
    assert saved[0][0] == "projects_collapsed"
    assert "my-feature" in saved[0][1]
    panel.destroy()
