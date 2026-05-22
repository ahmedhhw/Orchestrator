import pytest
import time
from unittest.mock import MagicMock, patch
from worktree_manager.models import WorktreeModel, RepoConfig
from worktree_manager.config_store import ConfigStore
from worktree_manager.git_service import GitService
from worktree_manager.main_window_vm import MainWindowViewModel


def _ctk_available():
    try:
        import customtkinter
        return True
    except ImportError:
        return False


pytestmark = pytest.mark.skipif(not _ctk_available(), reason="customtkinter not installed")


@pytest.fixture
def root():
    import customtkinter as ctk
    r = ctk.CTk()
    r.withdraw()
    yield r
    r.destroy()


@pytest.fixture
def vm():
    now = int(time.time())
    m = MagicMock(spec=MainWindowViewModel)
    m.load_worktrees.return_value = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
        WorktreeModel("/repos/proj-wt/fix-auth", "fix/auth", False, now - 3600, False, False),
    ]
    m.list_branches_with_checkout_status.return_value = [
        ("main", True), ("fix/auth", True), ("hotfix/2.1", False)
    ]
    return m


def test_main_window_renders_without_editor_toolbar(root, vm):
    import customtkinter as ctk
    from worktree_manager.ui.main_window import MainWindow
    win = MainWindow(root, vm=vm, repo_name="proj", on_settings=lambda: None, on_cleanup=lambda: None)

    def find_segmented(widget):
        results = []
        for child in widget.winfo_children():
            if isinstance(child, ctk.CTkSegmentedButton):
                results.append(child)
            results.extend(find_segmented(child))
        return results

    assert find_segmented(win) == []
    win.destroy()


def test_main_window_has_no_open_focus_switch_buttons(root, vm):
    import customtkinter as ctk
    from worktree_manager.ui.main_window import MainWindow
    win = MainWindow(root, vm=vm, repo_name="proj", on_settings=lambda: None, on_cleanup=lambda: None)

    def find_buttons(widget):
        buttons = []
        for child in widget.winfo_children():
            if isinstance(child, ctk.CTkButton) and child.cget("text") in ("Open", "Focus", "Switch"):
                buttons.append(child)
            buttons.extend(find_buttons(child))
        return buttons

    assert find_buttons(win) == []
    win.destroy()


def test_main_window_switch_branch_calls_vm(root, vm):
    from worktree_manager.ui.main_window import MainWindow
    win = MainWindow(root, vm=vm, repo_name="proj", on_settings=lambda: None, on_cleanup=lambda: None)
    win._switch_branch("/repos/proj-wt/fix-auth", "hotfix/2.1")
    vm.switch_branch.assert_called_once_with("/repos/proj-wt/fix-auth", "hotfix/2.1")
    win.destroy()


def test_main_window_switch_branch_shows_error_on_uncommitted(root, vm):
    from worktree_manager.ui.main_window import MainWindow
    vm.switch_branch.side_effect = ValueError("uncommitted changes")
    win = MainWindow(root, vm=vm, repo_name="proj", on_settings=lambda: None, on_cleanup=lambda: None)
    with patch("tkinter.messagebox.showerror") as mock_err:
        win._switch_branch("/repos/proj-wt/fix-auth", "hotfix/2.1")
    mock_err.assert_called_once()
    win.destroy()


def test_main_window_switch_branch_refreshes_on_success(root, vm):
    from worktree_manager.ui.main_window import MainWindow
    win = MainWindow(root, vm=vm, repo_name="proj", on_settings=lambda: None, on_cleanup=lambda: None)
    initial_load_count = vm.load_worktrees.call_count
    win._switch_branch("/repos/proj-wt/fix-auth", "hotfix/2.1")
    assert vm.load_worktrees.call_count > initial_load_count
    win.destroy()
