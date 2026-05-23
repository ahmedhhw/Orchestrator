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
    m.find_existing_run.return_value = None
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


def test_running_duplicate_shows_conflict_message_and_does_not_launch(root, vm):
    from worktree_manager.command_runner import RunHandle, RunStatus
    from worktree_manager.ui.launch_dialog import LaunchDialog
    handle = RunHandle(
        run_id="existing-r1", cmd_name="frontend", repo_path="/repos/proj",
        repo_name="proj", worktree_path="/repos/proj-wt/main",
        command=["npm", "run", "dev"], status=RunStatus.RUNNING,
    )
    vm.find_existing_run.return_value = handle
    d = LaunchDialog(root, vm=vm)
    d.set_command("frontend")
    d.set_worktree("/repos/proj-wt/main")
    d.trigger_launch()
    vm.launch.assert_not_called()
    label_text = d._conflict_label.cget("text")
    assert "already running" in label_text


def test_stopped_duplicate_shows_restart_prompt_and_does_not_launch(root, vm):
    from worktree_manager.command_runner import RunHandle, RunStatus
    from worktree_manager.ui.launch_dialog import LaunchDialog
    handle = RunHandle(
        run_id="existing-r2", cmd_name="frontend", repo_path="/repos/proj",
        repo_name="proj", worktree_path="/repos/proj-wt/main",
        command=["npm", "run", "dev"], status=RunStatus.STOPPED,
    )
    vm.find_existing_run.return_value = handle
    d = LaunchDialog(root, vm=vm)
    d.set_command("frontend")
    d.set_worktree("/repos/proj-wt/main")
    d.trigger_launch()
    vm.launch.assert_not_called()
    label_text = d._conflict_label.cget("text")
    assert "stopped" in label_text.lower() or "restart" in label_text.lower()


def test_stopped_duplicate_restart_calls_vm_restart(root, vm):
    from worktree_manager.command_runner import RunHandle, RunStatus
    from worktree_manager.ui.launch_dialog import LaunchDialog
    handle = RunHandle(
        run_id="existing-r1", cmd_name="frontend", repo_path="/repos/proj",
        repo_name="proj", worktree_path="/repos/proj-wt/main",
        command=["npm", "run", "dev"], status=RunStatus.STOPPED,
    )
    vm.find_existing_run.return_value = handle
    d = LaunchDialog(root, vm=vm)
    d.set_command("frontend")
    d.set_worktree("/repos/proj-wt/main")
    d.trigger_launch()
    d._trigger_conflict_restart()
    vm.restart.assert_called_with("existing-r1")
