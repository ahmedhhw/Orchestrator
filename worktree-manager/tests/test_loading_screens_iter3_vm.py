"""Tests for Iteration 3 — new VM methods for off-thread loading."""
from unittest.mock import MagicMock, call

import pytest

from worktree_manager.config_store import ConfigStore
from worktree_manager.git_service import GitService
from worktree_manager.models import WorkspaceEntry, WorkspaceProject, WorktreeModel
from worktree_manager.workspace_projects_vm import WorkspaceProjectsViewModel
from worktree_manager.workspace_service import WorkspaceService


# ── WorkspaceProjectsViewModel.load_project_entries ───────────────────────────

@pytest.fixture
def git():
    return MagicMock(spec=GitService)


@pytest.fixture
def vm(tmp_path, git):
    store = ConfigStore(tmp_path / "config.json")
    svc = WorkspaceService(workspace_dir=tmp_path / "workspaces")
    return WorkspaceProjectsViewModel(config_store=store, git_service=git, workspace_service=svc)


def test_load_project_entries_returns_one_entry_per_worktree_path(vm, git):
    git.checked_out_branch.return_value = "main"
    git.repo_root.return_value = "/repos/proj"
    git.list_local_branches.return_value = ["main", "feat/x"]

    projects = [WorkspaceProject("p", [WorkspaceEntry("/repos/proj-wt")])]
    entries = vm.load_project_entries(projects)

    assert len(entries) == 1
    assert entries[0]["worktree_path"] == "/repos/proj-wt"
    assert entries[0]["current_branch"] == "main"
    assert "main" in entries[0]["branches"]


def test_load_project_entries_skips_entries_on_git_error(vm, git):
    git.checked_out_branch.side_effect = Exception("not a git repo")
    git.repo_root.side_effect = Exception("not a git repo")

    projects = [WorkspaceProject("p", [WorkspaceEntry("/bad/path")])]
    entries = vm.load_project_entries(projects)

    assert len(entries) == 1
    assert entries[0]["current_branch"] == "(unknown)"
    assert entries[0]["branches"] == []


def test_load_project_entries_reports_progress(vm, git):
    git.checked_out_branch.return_value = "main"
    git.repo_root.return_value = "/repos/proj"
    git.list_local_branches.return_value = ["main"]

    calls = []
    projects = [
        WorkspaceProject("p", [WorkspaceEntry("/wt/a"), WorkspaceEntry("/wt/b")]),
    ]
    vm.load_project_entries(projects, on_progress=lambda cur, tot, lbl: calls.append((cur, tot, lbl)))

    assert len(calls) == 2
    assert calls[0] == (1, 2, "/wt/a")
    assert calls[1] == (2, 2, "/wt/b")


def test_load_project_entries_aggregates_across_projects(vm, git):
    git.checked_out_branch.return_value = "main"
    git.repo_root.return_value = "/repos/proj"
    git.list_local_branches.return_value = ["main"]

    projects = [
        WorkspaceProject("p1", [WorkspaceEntry("/wt/a")]),
        WorkspaceProject("p2", [WorkspaceEntry("/wt/b"), WorkspaceEntry("/wt/c")]),
    ]
    calls = []
    entries = vm.load_project_entries(
        projects, on_progress=lambda cur, tot, lbl: calls.append((cur, tot))
    )

    assert len(entries) == 3
    totals = [tot for _, tot in calls]
    assert all(t == 3 for t in totals)


# ── MainWindowViewModel.load_worktree_view_data ───────────────────────────────

import time as _time

from worktree_manager.main_window_vm import MainWindowViewModel


@pytest.fixture
def mwvm(tmp_path):
    store = MagicMock(spec=ConfigStore)
    store.get_repo.return_value = MagicMock(stale_days=30)
    git = MagicMock(spec=GitService)
    now = int(_time.time())
    git.list_worktrees.return_value = [
        WorktreeModel("/repo", "main", True, now, False, False),
        WorktreeModel("/repo-wt/fix", "fix/auth", False, now - 3600, False, False),
    ]
    git.list_local_branches.return_value = ["main", "fix/auth", "hotfix/2"]
    git.has_uncommitted_changes.return_value = False
    vm = MainWindowViewModel("/repo", store, git)
    vm._worktrees = git.list_worktrees.return_value
    return vm, git


def test_load_worktree_view_data_returns_worktrees_and_branch_status(mwvm):
    vm, git = mwvm
    result = vm.load_worktree_view_data()
    assert "worktrees" in result
    assert "branch_status" in result
    assert len(result["worktrees"]) == 2


def test_load_worktree_view_data_branch_status_includes_checkout_flags(mwvm):
    vm, git = mwvm
    result = vm.load_worktree_view_data()
    status_dict = dict(result["branch_status"])
    assert status_dict["main"] is True
    assert status_dict["fix/auth"] is True
    assert status_dict["hotfix/2"] is False


def test_load_worktree_view_data_reports_progress_per_worktree(mwvm):
    vm, git = mwvm
    calls = []
    vm.load_worktree_view_data(on_progress=lambda cur, tot, lbl: calls.append((cur, tot, lbl)))
    assert len(calls) == 2
    assert calls[-1][0] == 2
    assert calls[-1][1] == 2
