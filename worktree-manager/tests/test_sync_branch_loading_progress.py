"""Tests for on_progress support in BranchMgmtViewModel.load_syncable_branches."""
from unittest.mock import MagicMock

from worktree_manager.branch_mgmt_vm import BranchMgmtViewModel
from worktree_manager.git_service import UpstreamStatus


def _make_vm(branches=None):
    store = MagicMock()
    git = MagicMock()
    repos = {"/repo/a": MagicMock(stale_days=30)}
    store.all_repos.return_value = repos
    store.get_ui_pref.return_value = {}
    git.list_feature_and_main_branches.return_value = branches or ["main", "feature/x"]
    git.upstream_status.return_value = UpstreamStatus(has_upstream=True, ahead=0, behind=0)
    git.worktree_for_branch.return_value = None
    git.has_uncommitted_changes.return_value = False
    return BranchMgmtViewModel(config_store=store, git_service=git)


def test_on_progress_called_once_per_branch():
    vm = _make_vm(branches=["main", "feature/x", "feature/y"])
    calls = []
    vm.load_syncable_branches(on_progress=lambda cur, tot, lbl: calls.append((cur, tot, lbl)))
    assert len(calls) == 3


def test_on_progress_total_equals_branch_count():
    vm = _make_vm(branches=["main", "feature/x"])
    totals = []
    vm.load_syncable_branches(on_progress=lambda cur, tot, lbl: totals.append(tot))
    assert all(t == 2 for t in totals)


def test_on_progress_label_is_branch_name():
    vm = _make_vm(branches=["main"])
    labels = []
    vm.load_syncable_branches(on_progress=lambda cur, tot, lbl: labels.append(lbl))
    assert labels == ["main"]


def test_on_progress_current_increments():
    vm = _make_vm(branches=["main", "feature/x"])
    currents = []
    vm.load_syncable_branches(on_progress=lambda cur, tot, lbl: currents.append(cur))
    assert currents == [1, 2]


def test_load_syncable_branches_still_returns_rows_without_callback():
    vm = _make_vm(branches=["main"])
    rows = vm.load_syncable_branches()
    assert len(rows) == 1
    assert rows[0].branch == "main"
