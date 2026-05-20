import pytest
import time
from unittest.mock import MagicMock, patch
from worktree_manager.models import WorktreeModel, WindowRecord


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


def _make_vm(is_open_for=None):
    vm = MagicMock()
    now = int(time.time())
    vm.load_worktrees.return_value = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
        WorktreeModel("/repos/proj-wt/feat", "feature/auth", False, now - 3600, False, False),
    ]
    vm.default_editor.return_value = ("cursor", "reuse")
    vm.is_open.side_effect = lambda path: path == is_open_for
    vm.get_window.side_effect = lambda path: (
        WindowRecord("/repos/proj", path, "cursor", 42) if path == is_open_for else None
    )
    return vm


def _collect_labels(widget):
    import customtkinter as ctk
    result = []
    if isinstance(widget, ctk.CTkLabel):
        result.append(widget)
    for child in widget.winfo_children():
        result.extend(_collect_labels(child))
    return result


def _collect_buttons(widget):
    import customtkinter as ctk
    result = []
    if isinstance(widget, ctk.CTkButton):
        result.append(widget)
    for child in widget.winfo_children():
        result.extend(_collect_buttons(child))
    return result


def test_open_badge_visible_when_window_tracked(root):
    from worktree_manager.ui.main_window import MainWindow
    vm = _make_vm(is_open_for="/repos/proj-wt/feat")
    win = MainWindow(root, vm=vm, repo_name="proj", on_settings=MagicMock(), on_cleanup=MagicMock())
    labels = _collect_labels(win)
    assert any("[OPEN]" in str(getattr(lbl, "_text", "")) for lbl in labels)
    win.destroy()


def test_open_badge_absent_when_no_window(root):
    from worktree_manager.ui.main_window import MainWindow
    vm = _make_vm(is_open_for=None)
    win = MainWindow(root, vm=vm, repo_name="proj", on_settings=MagicMock(), on_cleanup=MagicMock())
    labels = _collect_labels(win)
    assert not any("[OPEN]" in str(getattr(lbl, "_text", "")) for lbl in labels)
    win.destroy()


def test_open_button_says_focus_when_window_tracked(root):
    from worktree_manager.ui.main_window import MainWindow
    vm = _make_vm(is_open_for="/repos/proj-wt/feat")
    win = MainWindow(root, vm=vm, repo_name="proj", on_settings=MagicMock(), on_cleanup=MagicMock())
    buttons = _collect_buttons(win)
    labels = [getattr(b, "_text", "") for b in buttons]
    assert "Focus" in labels
    win.destroy()


def test_open_button_says_open_when_no_window(root):
    from worktree_manager.ui.main_window import MainWindow
    vm = _make_vm(is_open_for=None)
    win = MainWindow(root, vm=vm, repo_name="proj", on_settings=MagicMock(), on_cleanup=MagicMock())
    buttons = _collect_buttons(win)
    labels = [getattr(b, "_text", "") for b in buttons]
    assert "Open" in labels
    win.destroy()


def test_open_delete_passes_live_window_to_dialog(root):
    from worktree_manager.ui.main_window import MainWindow
    vm = _make_vm(is_open_for="/repos/proj-wt/feat")
    win = MainWindow(root, vm=vm, repo_name="proj", on_settings=MagicMock(), on_cleanup=MagicMock())
    wt = WorktreeModel("/repos/proj-wt/feat", "feature/auth", False, int(time.time()), False, False)
    captured = {}
    with patch("worktree_manager.ui.delete_dialog.DeleteDialog") as MockDlg:
        MockDlg.return_value = MagicMock()
        win._open_delete(wt)
        _, kwargs = MockDlg.call_args
        captured["live_window"] = kwargs.get("live_window")
    assert captured["live_window"] is not None
    win.destroy()
