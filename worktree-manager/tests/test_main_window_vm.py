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
