"""Tests for BranchMgmtViewModel sync half (Iteration 2)."""
from unittest.mock import MagicMock, call, patch

import pytest

from worktree_manager.branch_mgmt_vm import BranchMgmtViewModel
from worktree_manager.git_service import PullOutcome, UpdateOutcome, UpstreamStatus


def _make_vm(repos=None):
    store = MagicMock()
    git = MagicMock()
    if repos is None:
        repos = {"/repo/a": MagicMock(stale_days=30)}
    store.all_repos.return_value = repos
    store.get_repo.side_effect = lambda p: repos.get(p)
    store.get_ui_pref.return_value = {}
    return BranchMgmtViewModel(config_store=store, git_service=git), store, git


# ── load_syncable_branches ────────────────────────────────────────────────────

def test_load_syncable_branches_includes_main_and_feature():
    vm, store, git = _make_vm()
    git.list_feature_and_main_branches.return_value = ["main", "feature/x"]
    git.upstream_status.return_value = UpstreamStatus(has_upstream=True, ahead=0, behind=2)
    git.worktree_for_branch.return_value = None
    git.has_uncommitted_changes.return_value = False
    store.get_ui_pref.return_value = {}

    rows = vm.load_syncable_branches()

    branches = {r.branch for r in rows}
    assert "main" in branches
    assert "feature/x" in branches


def test_load_syncable_branches_sets_upstream_status():
    vm, store, git = _make_vm()
    git.list_feature_and_main_branches.return_value = ["main"]
    git.upstream_status.return_value = UpstreamStatus(has_upstream=True, ahead=1, behind=3)
    git.worktree_for_branch.return_value = None
    git.has_uncommitted_changes.return_value = False
    store.get_ui_pref.return_value = {}

    rows = vm.load_syncable_branches()
    main_row = next(r for r in rows if r.branch == "main")

    assert main_row.has_upstream is True
    assert main_row.behind == 3
    assert main_row.ahead == 1


def test_load_syncable_branches_no_upstream_branch():
    vm, store, git = _make_vm()
    git.list_feature_and_main_branches.return_value = ["orphan"]
    git.upstream_status.return_value = UpstreamStatus(has_upstream=False, ahead=0, behind=0)
    git.worktree_for_branch.return_value = None
    store.get_ui_pref.return_value = {}

    rows = vm.load_syncable_branches()
    assert rows[0].has_upstream is False


def test_load_syncable_branches_sets_worktree_path():
    vm, store, git = _make_vm()
    git.list_feature_and_main_branches.return_value = ["feature/x"]
    git.upstream_status.return_value = UpstreamStatus(has_upstream=True, ahead=0, behind=1)
    git.worktree_for_branch.return_value = "/repo/a-wt/feature-x"
    git.has_uncommitted_changes.return_value = True
    store.get_ui_pref.return_value = {}

    rows = vm.load_syncable_branches()
    row = rows[0]

    assert row.worktree_path == "/repo/a-wt/feature-x"
    assert row.has_uncommitted is True


def test_load_syncable_branches_respects_excluded_pref():
    vm, store, git = _make_vm()
    git.list_feature_and_main_branches.return_value = ["main", "feature/x"]
    git.upstream_status.return_value = UpstreamStatus(has_upstream=True, ahead=0, behind=0)
    git.worktree_for_branch.return_value = None
    git.has_uncommitted_changes.return_value = False
    # "feature/x" is excluded
    store.get_ui_pref.return_value = {"/repo/a::feature/x": True}

    rows = vm.load_syncable_branches()
    fx = next(r for r in rows if r.branch == "feature/x")
    assert fx.excluded is True

    main_r = next(r for r in rows if r.branch == "main")
    assert main_r.excluded is False


# ── set_excluded ──────────────────────────────────────────────────────────────

def test_set_excluded_persists_to_config_store():
    vm, store, git = _make_vm()
    store.get_ui_pref.return_value = {}
    vm.set_excluded("/repo/a", "feature/x", True)
    store.set_ui_pref.assert_called_once()
    key, value = store.set_ui_pref.call_args.args
    assert key == "branch_sync_excluded"
    assert value.get("/repo/a::feature/x") is True


def test_set_excluded_false_removes_entry():
    vm, store, git = _make_vm()
    store.get_ui_pref.return_value = {"/repo/a::feature/x": True}
    vm.set_excluded("/repo/a", "feature/x", False)
    _, value = store.set_ui_pref.call_args.args
    assert "/repo/a::feature/x" not in value


# ── fetch_all ─────────────────────────────────────────────────────────────────

def test_fetch_all_calls_fetch_once_per_repo():
    repos = {"/repo/a": MagicMock(stale_days=30), "/repo/b": MagicMock(stale_days=30)}
    vm, store, git = _make_vm(repos=repos)
    git.fetch.return_value = None

    vm.fetch_all()

    assert git.fetch.call_count == 2
    called_paths = {c.args[0] for c in git.fetch.call_args_list}
    assert called_paths == {"/repo/a", "/repo/b"}


def test_fetch_all_returns_results_per_repo():
    repos = {"/repo/a": MagicMock(stale_days=30)}
    vm, store, git = _make_vm(repos=repos)
    git.fetch.return_value = None

    results = vm.fetch_all()

    assert len(results) == 1
    assert results[0].repo_path == "/repo/a"
    assert results[0].error is None


def test_fetch_all_captures_error_per_repo():
    repos = {"/repo/a": MagicMock(stale_days=30)}
    vm, store, git = _make_vm(repos=repos)
    git.fetch.return_value = "network timeout"

    results = vm.fetch_all()

    assert results[0].error == "network timeout"


# ── sync_one ──────────────────────────────────────────────────────────────────

def test_sync_one_pulls_in_worktree_when_branch_has_worktree():
    vm, store, git = _make_vm()
    git.fetch.return_value = None
    git.pull_ff_only.return_value = PullOutcome(status="pulled", new_commits=3)
    git.has_uncommitted_changes.return_value = False

    result = vm.sync_one(
        repo_path="/repo/a",
        branch="feature/x",
        worktree_path="/repo/a-wt/feature-x",
    )

    git.pull_ff_only.assert_called_once_with("/repo/a-wt/feature-x")
    assert result.status == "pulled"


def test_sync_one_skips_dirty_worktree():
    vm, store, git = _make_vm()
    git.fetch.return_value = None
    git.has_uncommitted_changes.return_value = True

    result = vm.sync_one(
        repo_path="/repo/a",
        branch="feature/x",
        worktree_path="/repo/a-wt/feature-x",
    )

    git.pull_ff_only.assert_not_called()
    assert result.status == "dirty"


def test_sync_one_updates_ref_when_no_worktree():
    vm, store, git = _make_vm()
    git.fetch.return_value = None
    git.update_ref_from_remote.return_value = UpdateOutcome(status="pulled")

    result = vm.sync_one(
        repo_path="/repo/a",
        branch="feature/x",
        worktree_path=None,
    )

    git.update_ref_from_remote.assert_called_once_with("/repo/a", "feature/x")
    assert result.status == "pulled"


def test_sync_one_returns_non_ff_from_pull():
    vm, store, git = _make_vm()
    git.fetch.return_value = None
    git.has_uncommitted_changes.return_value = False
    git.pull_ff_only.return_value = PullOutcome(status="non_ff")

    result = vm.sync_one(
        repo_path="/repo/a",
        branch="feature/x",
        worktree_path="/repo/a-wt/feature-x",
    )

    assert result.status == "non_ff"


# ── sync_included ─────────────────────────────────────────────────────────────

def test_sync_included_skips_excluded_branches():
    vm, store, git = _make_vm()
    git.list_feature_and_main_branches.return_value = ["main", "feature/x"]
    git.upstream_status.return_value = UpstreamStatus(has_upstream=True, ahead=0, behind=1)
    git.worktree_for_branch.return_value = None
    git.has_uncommitted_changes.return_value = False
    git.fetch.return_value = None
    git.update_ref_from_remote.return_value = UpdateOutcome(status="pulled")
    # feature/x excluded
    store.get_ui_pref.return_value = {"/repo/a::feature/x": True}

    vm.load_syncable_branches()
    results = vm.sync_included()

    synced_branches = {r.branch for r in results}
    assert "main" in synced_branches
    assert "feature/x" not in synced_branches


def test_sync_included_fetches_each_repo_once():
    repos = {"/repo/a": MagicMock(stale_days=30)}
    vm, store, git = _make_vm(repos=repos)
    git.list_feature_and_main_branches.return_value = ["main", "feature/x"]
    git.upstream_status.return_value = UpstreamStatus(has_upstream=True, ahead=0, behind=1)
    git.worktree_for_branch.return_value = None
    git.has_uncommitted_changes.return_value = False
    git.fetch.return_value = None
    git.update_ref_from_remote.return_value = UpdateOutcome(status="pulled")
    store.get_ui_pref.return_value = {}

    vm.load_syncable_branches()
    vm.sync_included()

    # Only one fetch call for /repo/a despite two branches
    assert git.fetch.call_count == 1
