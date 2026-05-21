import sys
import time
import pytest
from unittest.mock import MagicMock
from worktree_manager.command_center_vm import CommandCenterViewModel
from worktree_manager.models import SavedCommand, WorktreeModel
from worktree_manager.command_runner import RunStatus


@pytest.fixture
def store(tmp_path):
    from worktree_manager.config_store import ConfigStore
    from worktree_manager.models import RepoConfig
    s = ConfigStore(tmp_path / "config.json")
    s.save_repo(RepoConfig(
        repo_path="/repos/proj",
        worktree_storage="/repos/proj-wt",
        stale_days=30,
        last_editor="cursor",
        last_editor_mode="reuse",
        last_opened="2026-05-20T10:00:00",
    ))
    return s


@pytest.fixture
def vm(store):
    return CommandCenterViewModel(config_store=store)


def test_saved_commands_returns_empty_for_new_repo(vm):
    assert vm.saved_commands("/repos/proj") == []


def test_save_and_retrieve_command(vm):
    vm.save_command("/repos/proj", "frontend", "npm run dev")
    cmds = vm.saved_commands("/repos/proj")
    assert len(cmds) == 1
    assert cmds[0].name == "frontend"


def test_delete_command(vm):
    vm.save_command("/repos/proj", "frontend", "npm run dev")
    vm.delete_command("/repos/proj", "frontend")
    assert vm.saved_commands("/repos/proj") == []


def test_launch_returns_run_id(vm, tmp_path):
    run_id = vm.launch(
        repo_path="/repos/proj",
        repo_name="proj",
        cmd_name="echo-hi",
        command_str=f"{sys.executable} -c \"print('hi')\"",
        worktree_path=str(tmp_path),
    )
    assert isinstance(run_id, str) and run_id


def test_all_runs_contains_launched_run(vm, tmp_path):
    run_id = vm.launch(
        repo_path="/repos/proj",
        repo_name="proj",
        cmd_name="echo-hi",
        command_str=f"{sys.executable} -c \"print('hi')\"",
        worktree_path=str(tmp_path),
    )
    ids = [h.run_id for h in vm.all_runs()]
    assert run_id in ids


def test_get_run_returns_handle(vm, tmp_path):
    run_id = vm.launch(
        repo_path="/repos/proj",
        repo_name="proj",
        cmd_name="echo-hi",
        command_str=f"{sys.executable} -c \"print('hi')\"",
        worktree_path=str(tmp_path),
    )
    handle = vm.get_run(run_id)
    assert handle is not None
    assert handle.run_id == run_id


def test_stop_terminates_process(vm, tmp_path):
    run_id = vm.launch(
        repo_path="/repos/proj",
        repo_name="proj",
        cmd_name="sleep",
        command_str=f"{sys.executable} -c \"import time; time.sleep(60)\"",
        worktree_path=str(tmp_path),
    )
    time.sleep(0.1)
    vm.stop(run_id)
    time.sleep(0.3)
    handle = vm.get_run(run_id)
    assert handle.status != RunStatus.RUNNING


def test_restart_creates_new_run_id(vm, tmp_path):
    run_id = vm.launch(
        repo_path="/repos/proj",
        repo_name="proj",
        cmd_name="echo-hi",
        command_str=f"{sys.executable} -c \"print('hi')\"",
        worktree_path=str(tmp_path),
    )
    time.sleep(0.5)
    new_run_id = vm.restart(run_id)
    assert new_run_id != run_id
    assert vm.get_run(new_run_id) is not None


def test_restart_clears_old_run_output(vm, tmp_path):
    run_id = vm.launch(
        repo_path="/repos/proj",
        repo_name="proj",
        cmd_name="echo-hi",
        command_str=f"{sys.executable} -c \"print('hi')\"",
        worktree_path=str(tmp_path),
    )
    time.sleep(0.5)
    vm.restart(run_id)
    old_handle = vm.get_run(run_id)
    assert old_handle.output_lines == []


def test_on_run_added_callback_fires(vm, tmp_path):
    fired = []
    vm.on_run_added = lambda handle: fired.append(handle.run_id)
    run_id = vm.launch(
        repo_path="/repos/proj",
        repo_name="proj",
        cmd_name="echo-hi",
        command_str=f"{sys.executable} -c \"print('hi')\"",
        worktree_path=str(tmp_path),
    )
    assert run_id in fired


def test_on_output_callback_fires(vm, tmp_path):
    lines = []
    vm.on_output = lambda run_id, line: lines.append(line)
    vm.launch(
        repo_path="/repos/proj",
        repo_name="proj",
        cmd_name="echo-hi",
        command_str=f"{sys.executable} -c \"print('hello')\"",
        worktree_path=str(tmp_path),
    )
    deadline = time.time() + 3
    while not lines and time.time() < deadline:
        time.sleep(0.05)
    assert "hello" in lines


def test_on_status_changed_callback_fires(vm, tmp_path):
    statuses = []
    vm.on_status_changed = lambda run_id, status: statuses.append(status)
    vm.launch(
        repo_path="/repos/proj",
        repo_name="proj",
        cmd_name="echo-hi",
        command_str=f"{sys.executable} -c \"pass\"",
        worktree_path=str(tmp_path),
    )
    deadline = time.time() + 3
    while not statuses and time.time() < deadline:
        time.sleep(0.05)
    assert any(s in (RunStatus.STOPPED, RunStatus.ERROR) for s in statuses)


def test_all_repos_delegates_to_store(vm):
    repos = vm.all_repos()
    assert "/repos/proj" in repos


def test_list_worktrees_delegates_to_git(vm):
    mock_git = MagicMock()
    mock_git.list_worktrees.return_value = [
        WorktreeModel(path="/repos/proj", branch="main", is_main=True,
                      last_commit_ts=0, is_merged=False, is_stale=False)
    ]
    vm._git = mock_git
    wts = vm.list_worktrees("/repos/proj")
    assert len(wts) == 1
    mock_git.list_worktrees.assert_called_once()
