import pytest
import time
from unittest.mock import MagicMock
from worktree_manager.config_store import ConfigStore
from worktree_manager.git_service import GitService
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
def worktrees():
    now = int(time.time())
    return [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
        WorktreeModel("/repos/proj-wt/feature-auth", "feature/auth", False, now - 3600, False, False),
        WorktreeModel("/repos/proj-wt/chore-deps", "chore/deps", False, now - 35 * 86400, False, True),
        WorktreeModel("/repos/proj-wt/fix-old", "fix/old-bug", False, now - 40 * 86400, True, True),
    ]


@pytest.fixture
def vm(store, git, worktrees):
    git.list_worktrees.return_value = worktrees
    git.list_feature_branches.return_value = []
    git.build_merged_map.return_value = {}
    git.has_uncommitted_changes.return_value = False
    return MainWindowViewModel(
        repo_path="/repos/proj",
        config_store=store,
        git_service=git,
    )


def test_load_worktrees(vm, git):
    wts = vm.load_worktrees()
    git.list_worktrees.assert_called_once_with("/repos/proj", stale_days=30)
    assert len(wts) == 4


def test_cleanup_candidates_excludes_main(vm):
    vm.load_worktrees()
    candidates = vm.cleanup_candidates()
    assert all(not c.is_main for c in candidates)


def test_cleanup_candidates_includes_stale_and_merged(vm):
    vm.load_worktrees()
    candidates = vm.cleanup_candidates()
    branches = [c.branch for c in candidates]
    assert "chore/deps" in branches
    assert "fix/old-bug" in branches


def test_cleanup_candidates_excludes_healthy(vm):
    vm.load_worktrees()
    candidates = vm.cleanup_candidates()
    branches = [c.branch for c in candidates]
    assert "feature/auth" not in branches


def test_all_cleanup_candidates_includes_worktree_candidates(vm):
    vm.load_worktrees()
    vm._git.list_local_branches.return_value = []
    vm._git.build_merged_map.return_value = {"fix/old-bug": "main"}
    candidates = vm.all_cleanup_candidates()
    branches = [c.branch for c in candidates]
    assert "chore/deps" in branches
    assert "fix/old-bug" in branches


def test_all_cleanup_candidates_build_merged_map_called_once(vm):
    vm.load_worktrees()
    vm._git.list_local_branches.return_value = []
    vm.all_cleanup_candidates()
    vm._git.build_merged_map.assert_called_once()


def test_all_cleanup_candidates_is_merged_into_any_not_called(vm):
    vm.load_worktrees()
    vm._git.list_local_branches.return_value = []
    vm.all_cleanup_candidates()
    vm._git.is_merged_into_any.assert_not_called()


def test_all_cleanup_candidates_has_uncommitted_only_for_worktrees(vm):
    vm.load_worktrees()
    vm._git.list_local_branches.return_value = ["main", "orphan/branch"]
    vm._git.last_commit_ts.return_value = int(time.time()) - 2 * 86400
    vm.all_cleanup_candidates()
    for call in vm._git.has_uncommitted_changes.call_args_list:
        path = call.args[0]
        assert path is not None


def test_all_cleanup_candidates_merged_into_field_populated(vm):
    vm.load_worktrees()
    vm._git.list_local_branches.return_value = []
    vm._git.build_merged_map.return_value = {"fix/old-bug": "main"}
    candidates = vm.all_cleanup_candidates()
    merged = [c for c in candidates if c.branch == "fix/old-bug"]
    assert len(merged) == 1
    assert merged[0].merged_into == "main"
    assert merged[0].is_merged is True


def test_all_cleanup_candidates_includes_main_worktree_as_protected(vm):
    vm.load_worktrees()
    vm._git.list_local_branches.return_value = []
    candidates = vm.all_cleanup_candidates()
    main_candidates = [c for c in candidates if c.branch == "main"]
    assert len(main_candidates) == 1
    assert main_candidates[0].is_protected is True
    assert main_candidates[0].is_checked_out is True


def test_all_cleanup_candidates_includes_protected_healthy_worktree_as_protected(vm):
    vm.load_worktrees()
    vm._git.list_local_branches.return_value = []
    candidates = vm.all_cleanup_candidates()
    feature_auth = [c for c in candidates if c.branch == "feature/auth"]
    assert len(feature_auth) == 1
    assert feature_auth[0].is_protected is True


def test_all_cleanup_candidates_worktree_has_path(vm):
    vm.load_worktrees()
    vm._git.list_local_branches.return_value = []
    vm._git.build_merged_map.return_value = {"fix/old-bug": "main"}
    candidates = vm.all_cleanup_candidates()
    wt_candidates = [c for c in candidates if c.path is not None]
    assert all(c.path for c in wt_candidates)


def test_all_cleanup_candidates_includes_orphan_merged_branch(store, git):
    now = int(time.time())
    git.list_worktrees.return_value = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
    ]
    git.list_local_branches.return_value = ["main", "release/1.0"]
    git.list_feature_branches.return_value = []
    git.build_merged_map.return_value = {"release/1.0": "main"}
    git.has_uncommitted_changes.return_value = False
    git.last_commit_ts.return_value = now - 5 * 86400
    vm = MainWindowViewModel(
        repo_path="/repos/proj", config_store=store,
        git_service=git,
    )
    vm.load_worktrees()
    candidates = vm.all_cleanup_candidates()
    assert "release/1.0" in [c.branch for c in candidates]


def test_all_cleanup_candidates_includes_orphan_stale_branch(store, git):
    now = int(time.time())
    git.list_worktrees.return_value = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
    ]
    git.list_local_branches.return_value = ["main", "experiment/xyz"]
    git.list_feature_branches.return_value = []
    git.build_merged_map.return_value = {}
    git.has_uncommitted_changes.return_value = False
    git.last_commit_ts.return_value = now - 40 * 86400
    vm = MainWindowViewModel(
        repo_path="/repos/proj", config_store=store,
        git_service=git,
    )
    vm.load_worktrees()
    candidates = vm.all_cleanup_candidates()
    assert "experiment/xyz" in [c.branch for c in candidates]


def test_all_cleanup_candidates_includes_protected_orphan_branch_as_protected(store, git):
    now = int(time.time())
    git.list_worktrees.return_value = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
    ]
    git.list_local_branches.return_value = ["main", "feature/wip"]
    git.list_feature_branches.return_value = []
    git.build_merged_map.return_value = {}
    git.has_uncommitted_changes.return_value = False
    git.last_commit_ts.return_value = now - 2 * 86400
    vm = MainWindowViewModel(
        repo_path="/repos/proj", config_store=store,
        git_service=git,
    )
    vm.load_worktrees()
    candidates = vm.all_cleanup_candidates()
    feature_wip = [c for c in candidates if c.branch == "feature/wip"]
    assert len(feature_wip) == 1
    assert feature_wip[0].is_protected is True


def test_all_cleanup_candidates_orphan_has_no_path(store, git):
    now = int(time.time())
    git.list_worktrees.return_value = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
    ]
    git.list_local_branches.return_value = ["main", "release/1.0"]
    git.list_feature_branches.return_value = []
    git.build_merged_map.return_value = {"release/1.0": "main"}
    git.has_uncommitted_changes.return_value = False
    git.last_commit_ts.return_value = now - 5 * 86400
    vm = MainWindowViewModel(
        repo_path="/repos/proj", config_store=store,
        git_service=git,
    )
    vm.load_worktrees()
    candidates = vm.all_cleanup_candidates()
    orphans = [c for c in candidates if c.branch == "release/1.0"]
    assert len(orphans) == 1
    assert orphans[0].path is None


def test_all_cleanup_candidates_excludes_branch_already_in_worktree(vm):
    vm.load_worktrees()
    vm._git.list_local_branches.return_value = [
        "main", "feature/auth", "chore/deps", "fix/old-bug"
    ]
    candidates = vm.all_cleanup_candidates()
    matching = [c for c in candidates if c.branch == "chore/deps"]
    assert len(matching) == 1


def test_branch_slug_simple(vm):
    assert vm.branch_to_folder_name("feature/auth") == "feature-auth"


def test_branch_slug_multiple_slashes(vm):
    assert vm.branch_to_folder_name("fix/foo/bar") == "fix-foo-bar"


def test_worktree_path_for_branch(vm):
    path = vm.worktree_path_for_branch("feature/auth")
    assert path == "/repos/proj-wt/feature-auth"


# Phase 2 — is_protected_branch, has_uncommitted_changes_for_branch, create_worktree

def test_is_protected_branch_main(vm):
    assert vm.is_protected_branch("main") is True


def test_is_protected_branch_feature(vm):
    assert vm.is_protected_branch("feature/payments") is True


def test_is_protected_branch_regular(vm):
    assert vm.is_protected_branch("chore/deps") is False


def test_is_protected_branch_fix(vm):
    assert vm.is_protected_branch("fix/auth") is False


def test_has_uncommitted_changes_for_branch_true(vm):
    from unittest.mock import patch
    vm._git.has_uncommitted_changes.return_value = True
    with patch("os.path.isdir", return_value=True):
        result = vm.has_uncommitted_changes_for_branch("chore/deps")
    assert result is True
    vm._git.has_uncommitted_changes.assert_called_once_with("/repos/proj-wt/chore-deps")


def test_has_uncommitted_changes_for_branch_false(vm):
    from unittest.mock import patch
    vm._git.has_uncommitted_changes.return_value = False
    with patch("os.path.isdir", return_value=True):
        assert vm.has_uncommitted_changes_for_branch("chore/deps") is False


def test_has_uncommitted_changes_for_branch_no_worktree(vm, tmp_path):
    # Branch has no worktree directory on disk — returns False without calling git
    assert vm.has_uncommitted_changes_for_branch("orphan/branch") is False
    vm._git.has_uncommitted_changes.assert_not_called()


def test_create_worktree_existing_branch(vm):
    vm.create_worktree(branch="feature/payments", base_branch=None, existing=True)
    vm._git.create_worktree_from_existing.assert_called_once_with(
        repo_path="/repos/proj",
        worktree_path="/repos/proj-wt/feature-payments",
        branch="feature/payments",
    )


def test_create_worktree_new_branch(vm):
    vm.create_worktree(branch="fix/new", base_branch="main", existing=False)
    vm._git.create_worktree.assert_called_once_with(
        repo_path="/repos/proj",
        worktree_path="/repos/proj-wt/fix-new",
        branch="fix/new",
        base_branch="main",
    )


# Phase 3 — all_cleanup_candidates includes protected branches with is_protected=True

def test_all_cleanup_candidates_protected_worktree_has_is_protected_true(vm):
    vm.load_worktrees()
    vm._git.list_local_branches.return_value = []
    candidates = vm.all_cleanup_candidates()
    feature_candidates = [c for c in candidates if c.branch.startswith("feature/")]
    assert all(c.is_protected for c in feature_candidates)
    main_candidates = [c for c in candidates if c.branch == "main"]
    assert len(main_candidates) == 1 and main_candidates[0].is_protected


def test_all_cleanup_candidates_includes_healthy_worktree(vm, store, git):
    now = int(time.time())
    git.list_worktrees.return_value = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
        WorktreeModel("/repos/proj-wt/wip-thing", "wip/thing", False, now - 2 * 86400, False, False),
    ]
    git.list_local_branches.return_value = []
    git.list_feature_branches.return_value = []
    git.build_merged_map.return_value = {}
    git.has_uncommitted_changes.return_value = False
    local_vm = MainWindowViewModel(
        repo_path="/repos/proj", config_store=store,
        git_service=git,
    )
    local_vm.load_worktrees()
    candidates = local_vm.all_cleanup_candidates()
    assert any(c.branch == "wip/thing" for c in candidates)


def test_all_cleanup_candidates_protected_orphan_has_is_protected_true(store, git):
    now = int(time.time())
    git.list_worktrees.return_value = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
    ]
    git.list_local_branches.return_value = ["main", "feature/payments", "fix/thing"]
    git.list_feature_branches.return_value = ["feature/payments"]
    git.build_merged_map.return_value = {"fix/thing": "main", "feature/payments": "main"}
    git.has_uncommitted_changes.return_value = False
    git.last_commit_ts.return_value = now - 5 * 86400
    local_vm = MainWindowViewModel(
        repo_path="/repos/proj", config_store=store,
        git_service=git,
    )
    local_vm.load_worktrees()
    candidates = local_vm.all_cleanup_candidates()
    feature_pay = [c for c in candidates if c.branch == "feature/payments"]
    assert len(feature_pay) == 1
    assert feature_pay[0].is_protected is True


def test_all_cleanup_candidates_includes_healthy_orphan(store, git):
    now = int(time.time())
    git.list_worktrees.return_value = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
    ]
    git.list_local_branches.return_value = ["main", "hotfix/patch"]
    git.list_feature_branches.return_value = []
    git.build_merged_map.return_value = {}
    git.has_uncommitted_changes.return_value = False
    git.last_commit_ts.return_value = now - 1 * 86400
    local_vm = MainWindowViewModel(
        repo_path="/repos/proj", config_store=store,
        git_service=git,
    )
    local_vm.load_worktrees()
    candidates = local_vm.all_cleanup_candidates()
    assert any(c.branch == "hotfix/patch" for c in candidates)


# Dirty indicator tests

def test_load_worktree_view_data_marks_dirty_worktrees(store, git):
    now = int(time.time())
    dirty_wt = WorktreeModel("/repos/proj-wt/fix-auth", "fix/auth", False, now - 3600, False, False)
    clean_wt = WorktreeModel("/repos/proj-wt/chore-deps", "chore/deps", False, now - 3600, False, False)
    git.list_worktrees.return_value = [dirty_wt, clean_wt]
    git.list_local_branches.return_value = []
    git.has_uncommitted_changes.side_effect = lambda path: path == "/repos/proj-wt/fix-auth"
    local_vm = MainWindowViewModel(
        repo_path="/repos/proj", config_store=store, git_service=git,
    )
    data = local_vm.load_worktree_view_data()
    worktrees = data["worktrees"]
    fix_auth = next(w for w in worktrees if w.path == "/repos/proj-wt/fix-auth")
    chore_deps = next(w for w in worktrees if w.path == "/repos/proj-wt/chore-deps")
    assert fix_auth.is_dirty is True
    assert chore_deps.is_dirty is False


def test_load_worktree_view_data_calls_dirty_check_once_per_worktree(store, git):
    now = int(time.time())
    wt1 = WorktreeModel("/repos/proj-wt/fix-auth", "fix/auth", False, now - 3600, False, False)
    wt2 = WorktreeModel("/repos/proj-wt/chore-deps", "chore/deps", False, now - 3600, False, False)
    git.list_worktrees.return_value = [wt1, wt2]
    git.list_local_branches.return_value = []
    git.has_uncommitted_changes.return_value = False
    local_vm = MainWindowViewModel(
        repo_path="/repos/proj", config_store=store, git_service=git,
    )
    local_vm.load_worktree_view_data()
    assert git.has_uncommitted_changes.call_count == 2
    calls = {c.args[0] for c in git.has_uncommitted_changes.call_args_list}
    assert calls == {"/repos/proj-wt/fix-auth", "/repos/proj-wt/chore-deps"}
