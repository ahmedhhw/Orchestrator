"""Tests for WorkspaceProjectsViewModel additions — Iteration 3."""
from unittest.mock import MagicMock, call

import pytest

from worktree_manager.models import WorktreeModel
from worktree_manager.workspace_projects_vm import WorkspaceProjectsViewModel, WorktreeStatus


def _wt(path, branch="main", is_main=True):
    return WorktreeModel(
        path=path, branch=branch, is_main=is_main,
        last_commit_ts=0, is_merged=False, is_stale=False,
    )


def _vm(worktrees=None, dirty_paths=None):
    """Return a WorkspaceProjectsViewModel backed by mocked services."""
    config = MagicMock()
    git = MagicMock()
    svc = MagicMock()

    git.list_worktrees.return_value = worktrees or []
    if dirty_paths is not None:
        git.has_uncommitted_changes.side_effect = lambda p: p in dirty_paths
    else:
        git.has_uncommitted_changes.return_value = False

    return WorkspaceProjectsViewModel(
        config_store=config, git_service=git, workspace_service=svc
    ), git


# ── WorktreeStatus dataclass ──────────────────────────────────────────────────

def test_worktree_status_has_required_fields():
    ws = WorktreeStatus(path="/r/a", branch="main", is_main=True, has_uncommitted=False)
    assert ws.path == "/r/a"
    assert ws.branch == "main"
    assert ws.is_main is True
    assert ws.has_uncommitted is False


# ── list_worktrees_with_dirty ─────────────────────────────────────────────────

def test_list_worktrees_with_dirty_returns_worktree_statuses():
    vm, _ = _vm(worktrees=[_wt("/r/main"), _wt("/r/feat", "feature/x", is_main=False)])
    result = vm.list_worktrees_with_dirty("/repo")
    assert all(isinstance(s, WorktreeStatus) for s in result)


def test_list_worktrees_with_dirty_clean_worktree():
    vm, _ = _vm(worktrees=[_wt("/r/main")], dirty_paths=set())
    result = vm.list_worktrees_with_dirty("/repo")
    assert len(result) == 1
    assert result[0].has_uncommitted is False


def test_list_worktrees_with_dirty_dirty_worktree():
    vm, _ = _vm(worktrees=[_wt("/r/feat", "feature/x", is_main=False)], dirty_paths={"/r/feat"})
    result = vm.list_worktrees_with_dirty("/repo")
    assert result[0].has_uncommitted is True


def test_list_worktrees_with_dirty_mixed():
    wts = [_wt("/r/main"), _wt("/r/feat", "feature/x", is_main=False)]
    vm, _ = _vm(worktrees=wts, dirty_paths={"/r/feat"})
    result = vm.list_worktrees_with_dirty("/repo")
    assert result[0].has_uncommitted is False
    assert result[1].has_uncommitted is True


def test_list_worktrees_with_dirty_preserves_branch_and_is_main():
    wts = [_wt("/r/main", "main", True), _wt("/r/feat", "feature/x", False)]
    vm, _ = _vm(worktrees=wts, dirty_paths=set())
    result = vm.list_worktrees_with_dirty("/repo")
    assert result[0].branch == "main"
    assert result[0].is_main is True
    assert result[1].branch == "feature/x"
    assert result[1].is_main is False


def test_list_worktrees_with_dirty_calls_git_for_each_path():
    wts = [_wt("/r/main"), _wt("/r/feat", is_main=False)]
    vm, git = _vm(worktrees=wts, dirty_paths=set())
    vm.list_worktrees_with_dirty("/repo")
    paths_checked = [c.args[0] for c in git.has_uncommitted_changes.call_args_list]
    assert "/r/main" in paths_checked
    assert "/r/feat" in paths_checked


def test_list_worktrees_with_dirty_empty_repo():
    vm, _ = _vm(worktrees=[], dirty_paths=set())
    result = vm.list_worktrees_with_dirty("/repo")
    assert result == []


# ── create_worktree_for_project ───────────────────────────────────────────────

def _spec_new(worktree_path, branch, base_branch):
    return {"mode": "new", "worktree_path": worktree_path, "branch": branch, "base_branch": base_branch}


def _spec_existing(worktree_path, branch):
    return {"mode": "existing", "worktree_path": worktree_path, "branch": branch}


def test_create_worktree_for_project_new_branch_calls_git():
    vm, git = _vm()
    git.has_uncommitted_changes.return_value = False
    spec = _spec_new("/r/fix-auth", "fix/auth", "main")
    vm.create_worktree_for_project("/repo", spec)
    git.create_worktree.assert_called_once_with(
        repo_path="/repo",
        worktree_path="/r/fix-auth",
        branch="fix/auth",
        base_branch="main",
    )


def test_create_worktree_for_project_existing_branch_calls_git():
    vm, git = _vm()
    spec = _spec_existing("/r/feature-x", "feature/x")
    vm.create_worktree_for_project("/repo", spec)
    git.create_worktree_from_existing.assert_called_once_with(
        repo_path="/repo",
        worktree_path="/r/feature-x",
        branch="feature/x",
    )


def test_create_worktree_for_project_returns_worktree_status():
    vm, git = _vm()
    git.has_uncommitted_changes.return_value = False
    spec = _spec_new("/r/fix-auth", "fix/auth", "main")
    result = vm.create_worktree_for_project("/repo", spec)
    assert isinstance(result, WorktreeStatus)
    assert result.path == "/r/fix-auth"
    assert result.branch == "fix/auth"
    assert result.is_main is False
    assert result.has_uncommitted is False


def test_create_worktree_for_project_existing_branch_returns_status():
    vm, git = _vm()
    git.has_uncommitted_changes.return_value = False
    spec = _spec_existing("/r/feature-x", "feature/x")
    result = vm.create_worktree_for_project("/repo", spec)
    assert isinstance(result, WorktreeStatus)
    assert result.path == "/r/feature-x"
    assert result.branch == "feature/x"


def test_create_worktree_for_project_propagates_git_error():
    import subprocess
    vm, git = _vm()
    git.create_worktree.side_effect = subprocess.CalledProcessError(128, "git", stderr="branch already exists")
    spec = _spec_new("/r/fix-auth", "fix/auth", "main")
    with pytest.raises(subprocess.CalledProcessError):
        vm.create_worktree_for_project("/repo", spec)
