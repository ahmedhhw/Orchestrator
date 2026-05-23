import pytest
from unittest.mock import MagicMock
from worktree_manager.models import SavedCommand


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
    m = MagicMock()
    m.all_repos.return_value = {"/repos/proj": MagicMock(repo_path="/repos/proj")}
    m.saved_commands.return_value = [
        SavedCommand(name="frontend", command="npm run dev"),
        SavedCommand(name="build",    command="npm run build"),
    ]
    m.get_last_used_repo.return_value = "/repos/proj"
    return m


@pytest.fixture
def dialog(root, vm):
    from worktree_manager.ui.manage_commands_dialog import ManageCommandsDialog
    return ManageCommandsDialog(root, vm=vm)


def _find_widget_type(widget, cls):
    if isinstance(widget, cls):
        return True
    for child in widget.winfo_children():
        if _find_widget_type(child, cls):
            return True
    return False


def test_dialog_renders_without_crash(dialog):
    assert dialog is not None


def test_copy_command_puts_string_on_clipboard(dialog):
    dialog._copy_command("npm run dev")
    assert dialog.clipboard_get() == "npm run dev"


def test_copy_command_overwrites_previous_clipboard(dialog):
    dialog._copy_command("npm run dev")
    dialog._copy_command("npm run build")
    assert dialog.clipboard_get() == "npm run build"


def test_edit_row_command_field_is_textbox(dialog):
    import customtkinter as ctk
    dialog._start_edit("frontend")
    dialog.update_idletasks()
    assert _find_widget_type(dialog._list_frame, ctk.CTkTextbox)


def test_delete_calls_vm_delete_command(dialog, vm):
    dialog._delete("frontend")
    vm.delete_command.assert_called_with("/repos/proj", "frontend")
