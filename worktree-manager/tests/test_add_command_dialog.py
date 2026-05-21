import pytest
from unittest.mock import MagicMock


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
    m.all_repos.return_value = {
        "/repos/proj": MagicMock(repo_path="/repos/proj"),
        "/repos/api":  MagicMock(repo_path="/repos/api"),
    }
    return m


@pytest.fixture
def dialog(root, vm):
    from worktree_manager.ui.add_command_dialog import AddCommandDialog
    d = AddCommandDialog(root, vm=vm)
    return d


def test_dialog_populates_repo_dropdown(dialog, vm):
    repos = dialog.repo_choices()
    assert "/repos/proj" in repos or "proj" in repos


def test_save_calls_vm_save_command(dialog, vm):
    dialog.set_repo("/repos/proj")
    dialog.set_name("frontend")
    dialog.set_command("npm run dev")
    dialog.trigger_save()
    vm.save_command.assert_called_once_with("/repos/proj", "frontend", "npm run dev")


def test_save_with_empty_name_does_not_call_vm(root, vm):
    from worktree_manager.ui.add_command_dialog import AddCommandDialog
    d = AddCommandDialog(root, vm=vm)
    d.set_repo("/repos/proj")
    d.set_name("")
    d.set_command("npm run dev")
    d.trigger_save()
    vm.save_command.assert_not_called()


def test_save_with_empty_command_does_not_call_vm(root, vm):
    from worktree_manager.ui.add_command_dialog import AddCommandDialog
    d = AddCommandDialog(root, vm=vm)
    d.set_repo("/repos/proj")
    d.set_name("frontend")
    d.set_command("")
    d.trigger_save()
    vm.save_command.assert_not_called()


def test_cancel_closes_dialog_without_saving(root, vm):
    from worktree_manager.ui.add_command_dialog import AddCommandDialog
    d = AddCommandDialog(root, vm=vm)
    d.trigger_cancel()
    vm.save_command.assert_not_called()
