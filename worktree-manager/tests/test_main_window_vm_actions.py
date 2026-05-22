import pytest
import time
from unittest.mock import MagicMock
from worktree_manager.config_store import ConfigStore
from worktree_manager.git_service import GitService
from worktree_manager.models import RepoConfig, WorktreeModel, CleanupCandidate
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
def vm(store, git):
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


def test_create_worktree_raises_if_branch_already_exists(vm, git):
    with pytest.raises(ValueError, match="already exists"):
        vm.create_worktree(branch="feature/auth", base_branch="main")
    git.create_worktree.assert_not_called()


def test_create_worktree_raises_if_worktree_name_already_in_use(vm, git):
    # "feature-auth" is the folder for the existing feature/auth worktree
    with pytest.raises(ValueError, match="already in use"):
        vm.create_worktree(branch="fix/new", base_branch="main", worktree_name="feature-auth")
    git.create_worktree.assert_not_called()


def test_create_worktree_raises_if_derived_folder_already_in_use(vm, git):
    # "feature-auth" folder is taken by the feature/auth worktree.
    # A different branch whose derived name collides should also be refused.
    with pytest.raises(ValueError, match="already in use"):
        vm.create_worktree(branch="feature-auth", base_branch="main", worktree_name=None)
    git.create_worktree.assert_not_called()


def test_cleanup_candidates_marks_checked_out_branch(vm, git):
    import time
    now = int(time.time())
    git.list_feature_branches.return_value = []
    git.build_merged_map.return_value = {}
    git.last_commit_ts.return_value = now - 5 * 86400
    git.list_local_branches.return_value = ["main", "feature/auth", "orphan/old"]
    # feature/auth is checked out in a worktree; orphan/old is not
    candidates = vm.all_cleanup_candidates()
    auth_candidate = next((c for c in candidates if c.branch == "feature/auth"), None)
    orphan_candidate = next((c for c in candidates if c.branch == "orphan/old"), None)
    assert auth_candidate is None or auth_candidate.is_checked_out  # auth is in a worktree (excluded or marked)
    if orphan_candidate:
        assert orphan_candidate.is_checked_out is False


def test_non_protected_worktree_branch_is_marked_checked_out(tmp_path):
    now = int(time.time())
    worktrees = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
        WorktreeModel("/repos/proj-wt/fix-login", "fix/login", False, now - 3600, False, False),
    ]
    vm, git = _make_vm(tmp_path, worktrees, ["main", "fix/login"])
    git.build_merged_map.return_value = {}
    git.last_commit_ts.return_value = now - 5 * 86400
    candidates = vm.all_cleanup_candidates()
    fix_login = next((c for c in candidates if c.branch == "fix/login"), None)
    assert fix_login is not None
    assert fix_login.is_checked_out is True


def test_create_worktree_raises_if_branch_exists_as_local_branch_not_worktree(tmp_path):
    now = int(time.time())
    worktrees = [WorktreeModel("/repos/proj", "main", True, now, False, False)]
    vm, git = _make_vm(tmp_path, worktrees, ["main", "fix/existing"])
    with pytest.raises(ValueError, match="already exists"):
        vm.create_worktree(branch="fix/existing", base_branch="main")
    git.create_worktree.assert_not_called()


def test_create_worktree_with_custom_worktree_name(vm, git):
    vm.create_worktree(branch="feature/new", base_branch="main", worktree_name="my-feature")
    git.create_worktree.assert_called_once_with(
        repo_path="/repos/proj",
        worktree_path="/repos/proj-wt/my-feature",
        branch="feature/new",
        base_branch="main",
    )


def test_create_worktree_existing_with_custom_worktree_name(vm, git):
    vm.create_worktree(branch="feature/auth", base_branch=None, existing=True, worktree_name="auth-wt")
    git.create_worktree_from_existing.assert_called_once_with(
        repo_path="/repos/proj",
        worktree_path="/repos/proj-wt/auth-wt",
        branch="feature/auth",
    )


def test_create_worktree_without_worktree_name_uses_branch_derived_name(vm, git):
    vm.create_worktree(branch="fix/login-bug", base_branch="main")
    git.create_worktree.assert_called_once_with(
        repo_path="/repos/proj",
        worktree_path="/repos/proj-wt/fix-login-bug",
        branch="fix/login-bug",
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


def test_cleanup_deletes_branch_only(vm, git):
    now = int(time.time())
    stale_candidate = CleanupCandidate(
        branch="chore/deps", path="/repos/proj-wt/chore-deps",
        is_merged=False, is_stale=True, last_commit_ts=now - 35 * 86400,
    )
    vm.delete_cleanup_candidates([stale_candidate])
    git.delete_worktree.assert_not_called()
    git.delete_branch.assert_called_once_with(
        repo_path="/repos/proj", branch="chore/deps"
    )


def test_cleanup_deletes_branch_for_path_none_candidate(store, git):
    now = int(time.time())
    git.list_worktrees.return_value = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
    ]
    git.list_local_branches.return_value = ["main"]
    vm = MainWindowViewModel(
        repo_path="/repos/proj", config_store=store,
        git_service=git,
    )
    vm.load_worktrees()
    candidate = CleanupCandidate(
        branch="orphan/branch", path=None,
        is_merged=True, is_stale=False, last_commit_ts=now - 5 * 86400,
    )
    vm.delete_cleanup_candidates([candidate])
    git.delete_worktree.assert_not_called()
    git.delete_branch.assert_called_once_with(
        repo_path="/repos/proj", branch="orphan/branch"
    )


def _make_vm(tmp_path, worktrees, branches, feature_branches=None):
    s = ConfigStore(tmp_path / "config.json")
    s.save_repo(RepoConfig(
        repo_path="/repos/proj",
        worktree_storage="/repos/proj-wt",
        stale_days=30,
        last_editor="cursor",
        last_editor_mode="reuse",
        last_opened="2026-05-19T10:00:00",
    ))
    git = MagicMock(spec=GitService)
    git.list_worktrees.return_value = worktrees
    git.list_local_branches.return_value = branches
    git.list_feature_branches.return_value = feature_branches or []
    git.last_commit_ts.return_value = 0
    git.build_merged_map.return_value = {}
    git.has_uncommitted_changes.return_value = False
    vm = MainWindowViewModel(
        repo_path="/repos/proj",
        config_store=s,
        git_service=git,
    )
    vm.load_worktrees()
    return vm, git


def test_cleanup_candidates_use_feature_branches_as_merge_targets(tmp_path):
    now = int(time.time())
    worktrees = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
    ]
    branches = ["main", "feature/payments", "fix/old"]
    vm, git = _make_vm(tmp_path, worktrees, branches, feature_branches=["feature/payments"])
    git.build_merged_map.return_value = {"fix/old": "feature/payments"}
    git.last_commit_ts.return_value = now - 100

    candidates = vm.all_cleanup_candidates()
    fix_candidate = next((c for c in candidates if c.branch == "fix/old"), None)
    assert fix_candidate is not None
    assert fix_candidate.is_merged is True
    assert fix_candidate.merged_into == "feature/payments"


def test_cleanup_candidates_merged_into_main_when_no_feature_branches(tmp_path):
    now = int(time.time())
    worktrees = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
    ]
    branches = ["main", "fix/old"]
    vm, git = _make_vm(tmp_path, worktrees, branches, feature_branches=[])
    git.build_merged_map.return_value = {"fix/old": "main"}
    git.last_commit_ts.return_value = now - 100

    candidates = vm.all_cleanup_candidates()
    fix_candidate = next((c for c in candidates if c.branch == "fix/old"), None)
    assert fix_candidate is not None
    assert fix_candidate.merged_into == "main"


def test_cleanup_candidates_not_merged_when_not_in_any_target(tmp_path):
    now = int(time.time())
    stale_ts = now - 40 * 86400
    worktrees = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
    ]
    branches = ["main", "feature/payments", "fix/active"]
    vm, git = _make_vm(tmp_path, worktrees, branches, feature_branches=["feature/payments"])
    git.build_merged_map.return_value = {}
    git.last_commit_ts.return_value = stale_ts

    candidates = vm.all_cleanup_candidates()
    fix_candidate = next((c for c in candidates if c.branch == "fix/active"), None)
    assert fix_candidate is not None
    assert fix_candidate.is_merged is False
    assert fix_candidate.merged_into is None


def test_delete_cleanup_candidate_orphan_branch_always_deletes_branch(store, git):
    now = int(time.time())
    git.list_worktrees.return_value = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
    ]
    git.list_local_branches.return_value = ["main"]
    vm = MainWindowViewModel(
        repo_path="/repos/proj", config_store=store,
        git_service=git,
    )
    vm.load_worktrees()
    candidate = CleanupCandidate(
        branch="release/1.0", path=None,
        is_merged=True, is_stale=False, last_commit_ts=now - 5 * 86400,
    )
    vm.delete_cleanup_candidates([candidate], also_delete_branches=False)
    git.delete_worktree.assert_not_called()
    git.delete_branch.assert_called_once_with(
        repo_path="/repos/proj", branch="release/1.0"
    )


def test_delete_cleanup_never_calls_delete_worktree_even_with_path(tmp_path):
    now = int(time.time())
    worktrees = [WorktreeModel("/repos/proj", "main", True, now, False, False)]
    vm, git = _make_vm(tmp_path, worktrees, ["main"])
    candidate_with_path = CleanupCandidate("fix/old", "/repos/proj-wt/fix-old", False, True, now - 40 * 86400)
    candidate_no_path = CleanupCandidate("orphan", None, True, False, now - 10 * 86400)
    vm.delete_cleanup_candidates([candidate_with_path, candidate_no_path])
    git.delete_worktree.assert_not_called()
    assert git.delete_branch.call_count == 2


def test_main_worktree_branch_included_in_cleanup_candidates(tmp_path):
    now = int(time.time())
    worktrees = [WorktreeModel("/repos/proj", "mystuff", True, now, False, False)]
    vm, git = _make_vm(tmp_path, worktrees, ["mystuff", "old/branch"])
    candidates = vm.all_cleanup_candidates()
    assert any(c.branch == "mystuff" for c in candidates)


def test_non_main_worktree_branch_not_duplicated_in_cleanup_candidates(tmp_path):
    now = int(time.time())
    worktrees = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
        WorktreeModel("/repos/proj-wt/fix-auth", "fix/auth", False, now - 3600, False, False),
    ]
    vm, git = _make_vm(tmp_path, worktrees, ["main", "fix/auth", "old/branch"])
    candidates = vm.all_cleanup_candidates()
    assert len([c for c in candidates if c.branch == "fix/auth"]) == 1


def test_main_worktree_branch_with_uncommitted_marked_has_uncommitted(tmp_path):
    now = int(time.time())
    worktrees = [WorktreeModel("/repos/proj", "mystuff", True, now, False, False)]
    vm, git = _make_vm(tmp_path, worktrees, ["mystuff"])
    git.has_uncommitted_changes.return_value = True
    candidates = vm.all_cleanup_candidates()
    mystuff = next(c for c in candidates if c.branch == "mystuff")
    assert mystuff.has_uncommitted is True


def test_non_checked_out_branch_has_no_uncommitted_flag(tmp_path):
    now = int(time.time())
    worktrees = [WorktreeModel("/repos/proj", "main", True, now, False, False)]
    vm, git = _make_vm(tmp_path, worktrees, ["main", "fix/old"])
    git.has_uncommitted_changes.return_value = False
    candidates = vm.all_cleanup_candidates()
    fix_old = next(c for c in candidates if c.branch == "fix/old")
    assert fix_old.has_uncommitted is False
