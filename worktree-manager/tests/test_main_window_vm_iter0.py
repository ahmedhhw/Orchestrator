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
    g = MagicMock(spec=GitService)
    now = int(time.time())
    g.list_worktrees.return_value = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
        WorktreeModel("/repos/proj-wt/fix-auth", "fix/auth", False, now - 3600, False, False),
    ]
    g.list_feature_branches.return_value = []
    g.build_merged_map.return_value = {}
    g.has_uncommitted_changes.return_value = False
    return g


@pytest.fixture
def vm(store, git):
    v = MainWindowViewModel(
        repo_path="/repos/proj",
        config_store=store,
        git_service=git,
    )
    v.load_worktrees()
    return v


def test_vm_init_requires_no_editor_service(store, git):
    vm = MainWindowViewModel(
        repo_path="/repos/proj",
        config_store=store,
        git_service=git,
    )
    assert vm is not None


def test_vm_has_no_open_worktree(vm):
    assert not hasattr(vm, "open_worktree")


def test_vm_has_no_set_editor(vm):
    assert not hasattr(vm, "set_editor")


def test_vm_has_no_set_window_mode(vm):
    assert not hasattr(vm, "set_window_mode")


def test_vm_has_no_cur_open_path(vm):
    assert not hasattr(vm, "cur_open_path")


def test_vm_has_no_show_switch_label(vm):
    assert not hasattr(vm, "show_switch_label")


def test_vm_has_no_default_editor(vm):
    assert not hasattr(vm, "default_editor")
