import pytest
import subprocess
import time
from unittest.mock import MagicMock, patch
from worktree_manager.config_store import ConfigStore
from worktree_manager.git_service import GitService
from worktree_manager.models import RepoConfig, WorktreeModel
from worktree_manager.main_window_vm import MainWindowViewModel


@pytest.fixture
def svc():
    return GitService()


def test_checkout_branch_calls_git_checkout(svc):
    with patch.object(svc, "_run") as mock_run:
        svc.checkout_branch("/repos/proj-wt/fix-auth", "hotfix/2.1")
    mock_run.assert_called_once_with(
        ["git", "checkout", "hotfix/2.1"],
        cwd="/repos/proj-wt/fix-auth",
    )


def test_checkout_branch_raises_on_git_error(svc):
    with patch.object(svc, "_run", side_effect=subprocess.CalledProcessError(1, "git")):
        with pytest.raises(subprocess.CalledProcessError):
            svc.checkout_branch("/repos/proj-wt/fix-auth", "hotfix/2.1")


@pytest.fixture
def store(tmp_path):
    s = ConfigStore(tmp_path / "config.json")
    s.save_repo(RepoConfig(
        repo_path="/repos/proj",
        worktree_storage="/repos/proj-wt",
        stale_days=30,
        last_editor="cursor",
        last_editor_mode="reuse",
        last_opened="2026-05-19T10:00:00",
    ))
    return s


@pytest.fixture
def git():
    now = int(time.time())
    g = MagicMock(spec=GitService)
    g.list_worktrees.return_value = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
        WorktreeModel("/repos/proj-wt/fix-auth", "fix/auth", False, now - 3600, False, False),
    ]
    g.list_local_branches.return_value = ["main", "fix/auth", "hotfix/2.1", "chore/deps"]
    g.has_uncommitted_changes.return_value = False
    g.list_feature_branches.return_value = []
    g.build_merged_map.return_value = {}
    return g


@pytest.fixture
def vm(store, git):
    v = MainWindowViewModel(
        repo_path="/repos/proj",
        config_store=store,
        git_service=git,
    )
    v.load_worktrees()
    return v


def test_list_branches_with_checkout_status_returns_all_branches(vm, git):
    result = vm.list_branches_with_checkout_status()
    branches = [b for b, _ in result]
    assert "main" in branches
    assert "fix/auth" in branches
    assert "hotfix/2.1" in branches
    assert "chore/deps" in branches


def test_list_branches_with_checkout_status_marks_checked_out(vm):
    result = vm.list_branches_with_checkout_status()
    status = {b: checked_out for b, checked_out in result}
    assert status["main"] is True
    assert status["fix/auth"] is True
    assert status["hotfix/2.1"] is False
    assert status["chore/deps"] is False


def test_switch_branch_calls_checkout_when_clean(vm, git):
    vm.switch_branch("/repos/proj-wt/fix-auth", "hotfix/2.1")
    git.checkout_branch.assert_called_once_with("/repos/proj-wt/fix-auth", "hotfix/2.1")


def test_switch_branch_raises_when_uncommitted(vm, git):
    git.has_uncommitted_changes.return_value = True
    with pytest.raises(ValueError, match="uncommitted"):
        vm.switch_branch("/repos/proj-wt/fix-auth", "hotfix/2.1")
    git.checkout_branch.assert_not_called()


def test_switch_branch_does_not_checkout_when_uncommitted(vm, git):
    git.has_uncommitted_changes.return_value = True
    try:
        vm.switch_branch("/repos/proj-wt/fix-auth", "hotfix/2.1")
    except ValueError:
        pass
    git.checkout_branch.assert_not_called()
