import pytest
import time
from unittest.mock import MagicMock
from worktree_manager.config_store import ConfigStore
from worktree_manager.git_service import GitService
from worktree_manager.editor_service import EditorService
from worktree_manager.models import RepoConfig, WorktreeModel
from worktree_manager.main_window_vm import MainWindowViewModel


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
    return MagicMock(spec=GitService)


@pytest.fixture
def editor():
    return MagicMock(spec=EditorService)


@pytest.fixture
def vm(store, git, editor):
    now = int(time.time())
    git.list_worktrees.return_value = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
        WorktreeModel("/repos/proj-wt/feature-auth", "feature/auth", False, now - 3600, False, False),
    ]
    git.list_local_branches.return_value = ["main", "feature/auth"]
    m = MainWindowViewModel(
        repo_path="/repos/proj",
        config_store=store,
        git_service=git,
        editor_service=editor,
    )
    m.load_worktrees()
    return m


def test_create_worktree(vm, git):
    vm.create_worktree(branch="feature/new", base_branch="main")
    git.create_worktree.assert_called_once_with(
        repo_path="/repos/proj",
        worktree_path="/repos/proj-wt/feature-new",
        branch="feature/new",
        base_branch="main",
    )


def test_delete_worktree_without_branch(vm, git):
    vm.delete_worktree(
        path="/repos/proj-wt/feature-auth",
        branch="feature/auth",
        also_delete_branch=False,
    )
    git.delete_worktree.assert_called_once_with(
        repo_path="/repos/proj", worktree_path="/repos/proj-wt/feature-auth"
    )
    git.delete_branch.assert_not_called()


def test_delete_worktree_with_branch(vm, git):
    vm.delete_worktree(
        path="/repos/proj-wt/feature-auth",
        branch="feature/auth",
        also_delete_branch=True,
    )
    git.delete_worktree.assert_called_once()
    git.delete_branch.assert_called_once_with(
        repo_path="/repos/proj", branch="feature/auth"
    )


def test_list_local_branches(vm, git):
    branches = vm.list_local_branches()
    assert "main" in branches
    assert "feature/auth" in branches


def test_cleanup_deletes_selected(vm, git):
    now = int(time.time())
    stale_wt = WorktreeModel(
        "/repos/proj-wt/chore-deps", "chore/deps", False, now - 35 * 86400, False, True
    )
    vm.delete_cleanup_candidates([stale_wt], also_delete_branches=True)
    git.delete_worktree.assert_called_once_with(
        repo_path="/repos/proj", worktree_path="/repos/proj-wt/chore-deps"
    )
    git.delete_branch.assert_called_once_with(
        repo_path="/repos/proj", branch="chore/deps"
    )
