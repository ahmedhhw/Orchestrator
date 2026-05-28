from unittest.mock import MagicMock, patch

import pytest

from worktree_manager.models import CleanupCandidate
from worktree_manager.branch_mgmt_vm import BranchMgmtViewModel


def _candidate(
    branch="fix/old",
    path=None,
    is_merged=False,
    is_stale=False,
    last_commit_ts=0,
    merged_into=None,
    has_uncommitted=False,
    is_checked_out=False,
    is_protected=False,
):
    return CleanupCandidate(
        branch=branch,
        path=path,
        is_merged=is_merged,
        is_stale=is_stale,
        last_commit_ts=last_commit_ts,
        merged_into=merged_into,
        has_uncommitted=has_uncommitted,
        is_checked_out=is_checked_out,
        is_protected=is_protected,
    )


def _make_vm(repos=None):
    store = MagicMock()
    git = MagicMock()

    if repos is None:
        repos = {"/repo/a": MagicMock(stale_days=30)}

    store.all_repos.return_value = repos
    store.get_repo.side_effect = lambda p: repos.get(p)

    return BranchMgmtViewModel(config_store=store, git_service=git), store, git


# ── load_cleanup_candidates ───────────────────────────────────────────────────

def test_load_for_single_repo_calls_vm_all_candidates():
    vm, store, git = _make_vm()
    with patch(
        "worktree_manager.branch_mgmt_vm.MainWindowViewModel"
    ) as MockVM:
        mock_repo_vm = MagicMock()
        mock_repo_vm.all_cleanup_candidates.return_value = [
            _candidate("fix/old", is_merged=True, merged_into="main"),
        ]
        MockVM.return_value = mock_repo_vm
        mock_repo_vm.load_worktrees.return_value = []
        candidates = vm.load_cleanup_candidates(repo_path="/repo/a")

    assert len(candidates) == 1
    assert candidates[0].branch == "fix/old"


def test_load_for_all_repos_aggregates_candidates():
    repos = {
        "/repo/a": MagicMock(stale_days=30),
        "/repo/b": MagicMock(stale_days=30),
    }
    vm, store, git = _make_vm(repos=repos)
    with patch(
        "worktree_manager.branch_mgmt_vm.MainWindowViewModel"
    ) as MockVM:
        def _side_effect(repo_path, config_store, git_service):
            m = MagicMock()
            m.load_worktrees.return_value = []
            if repo_path == "/repo/a":
                m.all_cleanup_candidates.return_value = [
                    _candidate("branch-a", is_merged=True, merged_into="main"),
                ]
            else:
                m.all_cleanup_candidates.return_value = [
                    _candidate("branch-b", is_stale=True),
                ]
            return m

        MockVM.side_effect = _side_effect
        candidates = vm.load_cleanup_candidates(repo_path=None)

    branches = {c.branch for c in candidates}
    assert "branch-a" in branches
    assert "branch-b" in branches


def test_load_for_all_repos_passes_none_returns_all():
    repos = {"/repo/x": MagicMock(stale_days=30)}
    vm, store, git = _make_vm(repos=repos)
    with patch(
        "worktree_manager.branch_mgmt_vm.MainWindowViewModel"
    ) as MockVM:
        mock_repo_vm = MagicMock()
        mock_repo_vm.load_worktrees.return_value = []
        mock_repo_vm.all_cleanup_candidates.return_value = [
            _candidate("feat/z", is_stale=True),
        ]
        MockVM.return_value = mock_repo_vm
        candidates = vm.load_cleanup_candidates(repo_path=None)

    assert any(c.branch == "feat/z" for c in candidates)


# ── delete_cleanup_selection ──────────────────────────────────────────────────

def test_delete_delegates_to_per_repo_vm():
    vm, store, git = _make_vm()
    c1 = _candidate("fix/old", path="/repo/a/wt", is_merged=True, merged_into="main")
    c2 = _candidate("fix/stale", path=None, is_stale=True)

    with patch(
        "worktree_manager.branch_mgmt_vm.MainWindowViewModel"
    ) as MockVM:
        mock_repo_vm = MagicMock()
        MockVM.return_value = mock_repo_vm
        vm.delete_cleanup_selection(repo_path="/repo/a", candidates=[c1, c2])

    mock_repo_vm.delete_cleanup_candidates.assert_called_once_with(
        [c1, c2], also_delete_branches=True
    )


def test_list_repos_returns_all_repo_paths():
    repos = {"/repo/a": MagicMock(), "/repo/b": MagicMock()}
    vm, store, git = _make_vm(repos=repos)
    result = vm.list_repos()
    assert set(result) == {"/repo/a", "/repo/b"}


# ── delete in "all repos" mode ────────────────────────────────────────────────

def test_delete_all_repos_routes_each_candidate_to_its_repo():
    """Candidates from different repos are deleted via their respective repo VMs."""
    repos = {
        "/repo/a": MagicMock(stale_days=30),
        "/repo/b": MagicMock(stale_days=30),
    }
    vm, store, git = _make_vm(repos=repos)

    c_a = _candidate("branch-a", is_merged=True, merged_into="main")
    c_b = _candidate("branch-b", is_stale=True)

    repo_vms: dict[str, MagicMock] = {}

    with patch("worktree_manager.branch_mgmt_vm.MainWindowViewModel") as MockVM:
        def _side_effect(repo_path, config_store, git_service):
            m = MagicMock()
            m.load_worktrees.return_value = []
            if repo_path == "/repo/a":
                m.all_cleanup_candidates.return_value = [c_a]
            else:
                m.all_cleanup_candidates.return_value = [c_b]
            repo_vms[repo_path] = m
            return m

        MockVM.side_effect = _side_effect
        # populate the candidate→repo map
        vm.load_cleanup_candidates(repo_path=None)
        # now delete both — each must go to its repo's VM
        vm.delete_cleanup_selection(repo_path=None, candidates=[c_a, c_b])

    repo_vms["/repo/a"].delete_cleanup_candidates.assert_called_once_with(
        [c_a], also_delete_branches=True
    )
    repo_vms["/repo/b"].delete_cleanup_candidates.assert_called_once_with(
        [c_b], also_delete_branches=True
    )


def test_delete_all_repos_skips_candidates_not_in_map():
    """Candidates whose branch isn't in the map (no prior load) are silently skipped."""
    vm, store, git = _make_vm()
    unknown = _candidate("unknown-branch")

    with patch("worktree_manager.branch_mgmt_vm.MainWindowViewModel") as MockVM:
        mock_repo_vm = MagicMock()
        MockVM.return_value = mock_repo_vm
        # delete without a prior load — _candidate_repo is empty
        vm.delete_cleanup_selection(repo_path=None, candidates=[unknown])

    mock_repo_vm.delete_cleanup_candidates.assert_not_called()


def test_load_single_repo_populates_candidate_repo_map():
    """After loading a single repo, _candidate_repo maps the branch to that repo."""
    vm, store, git = _make_vm()
    c = _candidate("fix/thing", is_merged=True, merged_into="main")

    with patch("worktree_manager.branch_mgmt_vm.MainWindowViewModel") as MockVM:
        m = MagicMock()
        m.load_worktrees.return_value = []
        m.all_cleanup_candidates.return_value = [c]
        MockVM.return_value = m
        vm.load_cleanup_candidates(repo_path="/repo/a")

    assert vm._candidate_repo.get("fix/thing") == "/repo/a"


def test_load_clears_stale_candidate_repo_map_on_reload():
    """Each load_cleanup_candidates call resets the map so stale entries don't persist."""
    vm, store, git = _make_vm()
    old = _candidate("old/branch")
    new = _candidate("new/branch", is_stale=True)

    with patch("worktree_manager.branch_mgmt_vm.MainWindowViewModel") as MockVM:
        m = MagicMock()
        m.load_worktrees.return_value = []
        m.all_cleanup_candidates.return_value = [old]
        MockVM.return_value = m
        vm.load_cleanup_candidates(repo_path="/repo/a")

        m.all_cleanup_candidates.return_value = [new]
        vm.load_cleanup_candidates(repo_path="/repo/a")

    assert "old/branch" not in vm._candidate_repo
    assert vm._candidate_repo.get("new/branch") == "/repo/a"
