import pytest
import time
from unittest.mock import MagicMock
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


def _make_wt():
    return WorktreeModel(
        path="/repos/proj-wt/feat",
        branch="feature/auth",
        is_main=False,
        last_commit_ts=int(time.time()) - 3600,
        is_merged=False,
        is_stale=False,
    )


def _collect_text(widget):
    import customtkinter as ctk
    result = []
    if isinstance(widget, ctk.CTkLabel):
        result.append(getattr(widget, "_text", ""))
    for child in widget.winfo_children():
        result.extend(_collect_text(child))
    return result


def _collect_buttons(widget):
    import customtkinter as ctk
    result = []
    if isinstance(widget, ctk.CTkButton):
        result.append(widget)
    for child in widget.winfo_children():
        result.extend(_collect_buttons(child))
    return result


def test_delete_dialog_shows_warning_when_window_open(root):
    from worktree_manager.ui.delete_dialog import DeleteDialog
    wt = _make_wt()
    rec = WindowRecord("/repos/proj", wt.path, "cursor", 42)
    dlg = DeleteDialog(root, wt=wt, on_delete=MagicMock(), live_window=rec)
    texts = _collect_text(dlg)
    assert any("open" in t.lower() or "cursor" in t.lower() for t in texts)
    dlg.destroy()


def test_delete_dialog_confirm_button_says_delete_and_close_when_window_open(root):
    from worktree_manager.ui.delete_dialog import DeleteDialog
    wt = _make_wt()
    rec = WindowRecord("/repos/proj", wt.path, "cursor", 42)
    dlg = DeleteDialog(root, wt=wt, on_delete=MagicMock(), live_window=rec)
    buttons = _collect_buttons(dlg)
    labels = [getattr(b, "_text", "") for b in buttons]
    assert any("close" in lbl.lower() for lbl in labels)
    dlg.destroy()


def test_delete_dialog_no_warning_when_no_window(root):
    from worktree_manager.ui.delete_dialog import DeleteDialog
    wt = _make_wt()
    dlg = DeleteDialog(root, wt=wt, on_delete=MagicMock(), live_window=None)
    texts = _collect_text(dlg)
    assert not any("open in" in t.lower() for t in texts)
    dlg.destroy()


def test_delete_dialog_confirm_button_says_delete_when_no_window(root):
    from worktree_manager.ui.delete_dialog import DeleteDialog
    wt = _make_wt()
    dlg = DeleteDialog(root, wt=wt, on_delete=MagicMock(), live_window=None)
    buttons = _collect_buttons(dlg)
    labels = [getattr(b, "_text", "") for b in buttons]
    assert "Delete" in labels
    assert "Delete & Close" not in labels
    dlg.destroy()
