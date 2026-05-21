import pytest
from unittest.mock import MagicMock
from worktree_manager.models import SavedCommand, WorktreeModel


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
    }
    m.saved_commands.return_value = [
        SavedCommand(name="frontend", command="npm run dev"),
        SavedCommand(name="backend",  command="python manage.py runserver"),
    ]
    m.list_worktrees.return_value = [
        WorktreeModel(path="/repos/proj-wt/main", branch="main",
                      is_main=True, last_commit_ts=0, is_merged=False, is_stale=False),
        WorktreeModel(path="/repos/proj-wt/feat", branch="feat-auth",
                      is_main=False, last_commit_ts=0, is_merged=False, is_stale=False),
    ]
    return m


@pytest.fixture
def dialog(root, vm):
    from worktree_manager.ui.launch_dialog import LaunchDialog
    return LaunchDialog(root, vm=vm)


def test_command_dropdown_populated_from_vm(dialog):
    choices = dialog.command_choices()
    assert "frontend" in choices
    assert "backend" in choices


def test_worktree_dropdown_populated_from_vm(dialog):
    choices = dialog.worktree_choices()
    assert any("main" in c for c in choices)
    assert any("feat-auth" in c for c in choices)


def test_launch_calls_vm_launch(dialog, vm):
    dialog.set_command("frontend")
    dialog.set_worktree("/repos/proj-wt/main")
    dialog.trigger_launch()
    vm.launch.assert_called_once()
    kwargs = vm.launch.call_args[1]
    assert kwargs["repo_path"] == "/repos/proj"
    assert kwargs["cmd_name"] == "frontend"
    assert kwargs["worktree_path"] == "/repos/proj-wt/main"
    assert kwargs["command_str"] == "npm run dev"


def test_launch_with_no_command_does_not_call_vm(root, vm):
    from worktree_manager.ui.launch_dialog import LaunchDialog
    empty_vm = MagicMock()
    empty_vm.all_repos.return_value = {"/repos/proj": MagicMock()}
    empty_vm.saved_commands.return_value = []
    empty_vm.list_worktrees.return_value = []
    d = LaunchDialog(root, vm=empty_vm)
    # no commands → no selection → launch is a no-op
    d.trigger_launch()
    empty_vm.launch.assert_not_called()


def test_cancel_closes_without_launching(root, vm):
    from worktree_manager.ui.launch_dialog import LaunchDialog
    d = LaunchDialog(root, vm=vm)
    d.trigger_cancel()
    vm.launch.assert_not_called()
