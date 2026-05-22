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


@pytest.fixture
def vm():
    m = MagicMock(spec=WorkspaceProjectsViewModel)
    m.load_projects.return_value = []
    m.list_worktrees_for_repo.return_value = []
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
