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


def test_delete_worktree_clears_cur_open_path_when_focused(store, git, editor):
    cfg = store.get_repo("/repos/proj")
    cfg.cur_open_path = "/repos/proj-wt/feature-auth"
    store.save_repo(cfg)

    now = int(time.time())
    git.list_worktrees.return_value = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
        WorktreeModel("/repos/proj-wt/feature-auth", "feature/auth", False, now - 3600, False, False),
    ]
    vm = MainWindowViewModel(
        repo_path="/repos/proj",
        config_store=store,
        git_service=git,
        editor_service=editor,
    )
    vm.load_worktrees()
    vm.delete_worktree(
        path="/repos/proj-wt/feature-auth",
        branch="feature/auth",
        also_delete_branch=False,
    )
    assert store.get_repo("/repos/proj").cur_open_path is None


def test_delete_worktree_does_not_clear_cur_open_path_for_other(store, git, editor):
    cfg = store.get_repo("/repos/proj")
    cfg.cur_open_path = "/repos/proj-wt/feature-other"
    store.save_repo(cfg)

    now = int(time.time())
    git.list_worktrees.return_value = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
        WorktreeModel("/repos/proj-wt/feature-auth", "feature/auth", False, now - 3600, False, False),
    ]
    vm = MainWindowViewModel(
        repo_path="/repos/proj",
        config_store=store,
        git_service=git,
        editor_service=editor,
    )
    vm.load_worktrees()
    vm.delete_worktree(
        path="/repos/proj-wt/feature-auth",
        branch="feature/auth",
        also_delete_branch=False,
    )
    assert store.get_repo("/repos/proj").cur_open_path == "/repos/proj-wt/feature-other"


def test_list_local_branches(vm, git):
    branches = vm.list_local_branches()
    assert "main" in branches
    assert "feature/auth" in branches


def test_cleanup_deletes_selected(vm, git):
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    stale_candidate = CleanupCandidate(
        branch="chore/deps", path="/repos/proj-wt/chore-deps",
        is_merged=False, is_stale=True, last_commit_ts=now - 35 * 86400,
    )
    vm.delete_cleanup_candidates([stale_candidate], also_delete_branches=True)
    git.delete_worktree.assert_called_once_with(
        repo_path="/repos/proj", worktree_path="/repos/proj-wt/chore-deps"
    )
    git.delete_branch.assert_called_once_with(
        repo_path="/repos/proj", branch="chore/deps"
    )


def test_delete_cleanup_candidate_worktree_with_branch(store, git, editor):
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    git.list_worktrees.return_value = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
    ]
    git.list_local_branches.return_value = ["main"]
    vm = MainWindowViewModel(
        repo_path="/repos/proj", config_store=store,
        git_service=git, editor_service=editor,
    )
    vm.load_worktrees()
    candidate = CleanupCandidate(
        branch="chore/deps", path="/repos/proj-wt/chore-deps",
        is_merged=False, is_stale=True, last_commit_ts=now - 35 * 86400,
    )
    vm.delete_cleanup_candidates([candidate], also_delete_branches=True)
    git.delete_worktree.assert_called_once_with(
        repo_path="/repos/proj", worktree_path="/repos/proj-wt/chore-deps"
    )
    git.delete_branch.assert_called_once_with(
        repo_path="/repos/proj", branch="chore/deps"
    )


def test_delete_cleanup_candidate_worktree_without_branch(store, git, editor):
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    git.list_worktrees.return_value = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
    ]
    git.list_local_branches.return_value = ["main"]
    vm = MainWindowViewModel(
        repo_path="/repos/proj", config_store=store,
        git_service=git, editor_service=editor,
    )
    vm.load_worktrees()
    candidate = CleanupCandidate(
        branch="chore/deps", path="/repos/proj-wt/chore-deps",
        is_merged=False, is_stale=True, last_commit_ts=now - 35 * 86400,
    )
    vm.delete_cleanup_candidates([candidate], also_delete_branches=False)
    git.delete_worktree.assert_called_once_with(
        repo_path="/repos/proj", worktree_path="/repos/proj-wt/chore-deps"
    )
    git.delete_branch.assert_not_called()


def _make_vm(tmp_path, worktrees, branches, feature_branches=None):
    from worktree_manager.config_store import ConfigStore
    from worktree_manager.models import RepoConfig
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
    git.is_merged_into_any.return_value = (False, None)
    editor = MagicMock(spec=EditorService)
    vm = MainWindowViewModel(
        repo_path="/repos/proj",
        config_store=s,
        git_service=git,
        editor_service=editor,
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
    git.is_merged_into_any.return_value = (True, "feature/payments")
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
    git.is_merged_into_any.return_value = (True, "main")
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
    git.is_merged_into_any.return_value = (False, None)
    git.last_commit_ts.return_value = stale_ts

    candidates = vm.all_cleanup_candidates()
    fix_candidate = next((c for c in candidates if c.branch == "fix/active"), None)
    assert fix_candidate is not None
    assert fix_candidate.is_merged is False
    assert fix_candidate.merged_into is None


def test_open_worktree_focus_calls_focus_not_open_replacing(store, git, editor):
    store.save_repo(RepoConfig(
        repo_path="/repos/proj",
        worktree_storage="/repos/proj-wt",
        stale_days=30,
        last_editor="vscode",
        last_editor_mode="reuse",
        last_opened="2026-05-20T10:00:00",
        editor="vscode",
        window_mode="single",
        cur_open_path="/repos/proj-wt/feature-auth",
    ))
    now = int(time.time())
    git.list_worktrees.return_value = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
        WorktreeModel("/repos/proj-wt/feature-auth", "feature/auth", False, now - 3600, False, False),
    ]
    vm = MainWindowViewModel(
        repo_path="/repos/proj", config_store=store,
        git_service=git, editor_service=editor,
    )
    vm.load_worktrees()
    vm.open_worktree("/repos/proj-wt/feature-auth")
    editor.focus.assert_called_once_with("/repos/proj-wt/feature-auth", editor="vscode")
    editor.open_replacing.assert_not_called()


def test_open_worktree_switch_calls_open_replacing_with_r(store, git, editor):
    store.save_repo(RepoConfig(
        repo_path="/repos/proj",
        worktree_storage="/repos/proj-wt",
        stale_days=30,
        last_editor="vscode",
        last_editor_mode="reuse",
        last_opened="2026-05-20T10:00:00",
        editor="vscode",
        window_mode="single",
        cur_open_path="/repos/proj-wt/feature-auth",
    ))
    now = int(time.time())
    git.list_worktrees.return_value = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
        WorktreeModel("/repos/proj-wt/feature-auth", "feature/auth", False, now - 3600, False, False),
    ]
    vm = MainWindowViewModel(
        repo_path="/repos/proj", config_store=store,
        git_service=git, editor_service=editor,
    )
    vm.load_worktrees()
    vm.open_worktree("/repos/proj-wt/fix-bug")
    editor.open_replacing.assert_called_once_with(
        cur_path="/repos/proj-wt/feature-auth",
        new_path="/repos/proj-wt/fix-bug",
        editor="vscode",
    )
    editor.focus.assert_not_called()


def test_delete_cleanup_candidate_orphan_branch_always_deletes_branch(store, git, editor):
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    git.list_worktrees.return_value = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
    ]
    git.list_local_branches.return_value = ["main"]
    vm = MainWindowViewModel(
        repo_path="/repos/proj", config_store=store,
        git_service=git, editor_service=editor,
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
