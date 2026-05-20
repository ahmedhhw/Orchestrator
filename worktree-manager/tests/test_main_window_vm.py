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
def worktrees():
    now = int(time.time())
    return [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
        WorktreeModel("/repos/proj-wt/feature-auth", "feature/auth", False, now - 3600, False, False),
        WorktreeModel("/repos/proj-wt/chore-deps", "chore/deps", False, now - 35 * 86400, False, True),
        WorktreeModel("/repos/proj-wt/fix-old", "fix/old-bug", False, now - 40 * 86400, True, True),
    ]


@pytest.fixture
def vm(store, git, editor, worktrees):
    git.list_worktrees.return_value = worktrees
    git.list_feature_branches.return_value = []
    git.is_merged_into_any.return_value = (False, None)
    return MainWindowViewModel(
        repo_path="/repos/proj",
        config_store=store,
        git_service=git,
        editor_service=editor,
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
    import time
    now = int(time.time())
    vm.load_worktrees()
    vm._git.list_local_branches.return_value = []
    # chore/deps is stale (35d), fix/old-bug is stale (40d) and merged
    def merged_side_effect(repo, branch, targets):
        return (True, "main") if branch == "fix/old-bug" else (False, None)
    vm._git.is_merged_into_any.side_effect = merged_side_effect
    candidates = vm.all_cleanup_candidates()
    branches = [c.branch for c in candidates]
    assert "chore/deps" in branches
    assert "fix/old-bug" in branches


def test_all_cleanup_candidates_excludes_main_worktree(vm):
    vm.load_worktrees()
    vm._git.list_local_branches.return_value = []
    candidates = vm.all_cleanup_candidates()
    assert all(c.branch != "main" for c in candidates)


def test_all_cleanup_candidates_excludes_healthy_worktrees(vm):
    vm.load_worktrees()
    vm._git.list_local_branches.return_value = []
    candidates = vm.all_cleanup_candidates()
    assert all(c.branch != "feature/auth" for c in candidates)


def test_all_cleanup_candidates_worktree_has_path(vm):
    vm.load_worktrees()
    vm._git.list_local_branches.return_value = []
    def merged_side_effect(repo, branch, targets):
        return (True, "main") if branch == "fix/old-bug" else (False, None)
    vm._git.is_merged_into_any.side_effect = merged_side_effect
    candidates = vm.all_cleanup_candidates()
    wt_candidates = [c for c in candidates if c.path is not None]
    assert all(c.path for c in wt_candidates)


def test_all_cleanup_candidates_includes_orphan_merged_branch(store, git, editor):
    now = int(time.time())
    git.list_worktrees.return_value = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
    ]
    git.list_local_branches.return_value = ["main", "release/1.0"]
    git.list_feature_branches.return_value = []
    git.is_merged_into_any.return_value = (True, "main")
    git.last_commit_ts.return_value = now - 5 * 86400
    vm = MainWindowViewModel(
        repo_path="/repos/proj", config_store=store,
        git_service=git, editor_service=editor,
    )
    vm.load_worktrees()
    candidates = vm.all_cleanup_candidates()
    assert "release/1.0" in [c.branch for c in candidates]


def test_all_cleanup_candidates_includes_orphan_stale_branch(store, git, editor):
    now = int(time.time())
    git.list_worktrees.return_value = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
    ]
    git.list_local_branches.return_value = ["main", "experiment/xyz"]
    git.list_feature_branches.return_value = []
    git.is_merged_into_any.return_value = (False, None)
    git.last_commit_ts.return_value = now - 40 * 86400
    vm = MainWindowViewModel(
        repo_path="/repos/proj", config_store=store,
        git_service=git, editor_service=editor,
    )
    vm.load_worktrees()
    candidates = vm.all_cleanup_candidates()
    assert "experiment/xyz" in [c.branch for c in candidates]


def test_all_cleanup_candidates_excludes_healthy_orphan_branch(store, git, editor):
    now = int(time.time())
    git.list_worktrees.return_value = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
    ]
    git.list_local_branches.return_value = ["main", "feature/wip"]
    git.list_feature_branches.return_value = []
    git.is_merged_into_any.return_value = (False, None)
    git.last_commit_ts.return_value = now - 2 * 86400
    vm = MainWindowViewModel(
        repo_path="/repos/proj", config_store=store,
        git_service=git, editor_service=editor,
    )
    vm.load_worktrees()
    candidates = vm.all_cleanup_candidates()
    assert all(c.branch != "feature/wip" for c in candidates)


def test_all_cleanup_candidates_orphan_has_no_path(store, git, editor):
    now = int(time.time())
    git.list_worktrees.return_value = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
    ]
    git.list_local_branches.return_value = ["main", "release/1.0"]
    git.list_feature_branches.return_value = []
    git.is_merged_into_any.return_value = (True, "main")
    git.last_commit_ts.return_value = now - 5 * 86400
    vm = MainWindowViewModel(
        repo_path="/repos/proj", config_store=store,
        git_service=git, editor_service=editor,
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


def test_open_worktree_delegates_to_editor(vm, editor):
    vm.open_worktree("/repos/proj-wt/feat", editor="vscode", reuse_window=True)
    editor.open.assert_called_once_with(
        "/repos/proj-wt/feat", editor="vscode", reuse_window=True, repo_path="/repos/proj"
    )


def test_default_editor_from_config(vm):
    ed, mode = vm.default_editor()
    assert ed == "cursor"
    assert mode == "reuse"
