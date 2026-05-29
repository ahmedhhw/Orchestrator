"""Tests for DiffViewModel.get_diff_hunks() and target_is_working_tree property."""
from unittest.mock import MagicMock

import pytest

from worktree_manager.diff_vm import DiffViewModel
from worktree_manager.diff_models import DiffHunk, HistoryPoint


def _make_vm(hunks=None):
    git = MagicMock()
    git.list_points.return_value = []
    git.diff_files.return_value = []
    git.diff_hunks.return_value = hunks or []
    vm = DiffViewModel(git_service=git, config_store=MagicMock())
    vm.set_repo("/repos/proj")
    return vm, git


# ── get_diff_hunks ─────────────────────────────────────────────────────────────

def test_get_diff_hunks_delegates_to_git_service():
    expected = [DiffHunk(index=0, header="@@ -1,3 +1,4 @@", lines=[" a", "-b", "+c"])]
    vm, git = _make_vm(hunks=expected)
    vm.set_points("main", "working_tree_unstaged")
    result = vm.get_diff_hunks("src/foo.py")
    git.diff_hunks.assert_called_once_with("/repos/proj", "main", "working_tree_unstaged", "src/foo.py")
    assert result == expected


def test_get_diff_hunks_uses_worktree_path_when_set():
    vm, git = _make_vm()
    vm.set_repo("/repos/proj")
    vm.set_worktree("/repos/proj-wt/feat")
    vm.set_points("main", "working_tree_unstaged")
    vm.get_diff_hunks("src/foo.py")
    git.diff_hunks.assert_called_once_with("/repos/proj-wt/feat", "main", "working_tree_unstaged", "src/foo.py")


def test_get_diff_hunks_raises_without_repo():
    git = MagicMock()
    git.list_points.return_value = []
    vm = DiffViewModel(git_service=git, config_store=MagicMock())
    with pytest.raises(RuntimeError):
        vm.get_diff_hunks("foo.py")


def test_get_diff_hunks_raises_without_refs():
    vm, _ = _make_vm()
    with pytest.raises(RuntimeError):
        vm.get_diff_hunks("foo.py")


def test_get_diff_hunks_returns_empty_list_when_no_changes():
    vm, _ = _make_vm(hunks=[])
    vm.set_points("main", "main")
    result = vm.get_diff_hunks("src/unchanged.py")
    assert result == []


# ── target_is_working_tree ────────────────────────────────────────────────────

def test_target_is_working_tree_true_for_unstaged():
    vm, _ = _make_vm()
    vm.set_points("main", "working_tree_unstaged")
    assert vm.target_is_working_tree is True


def test_target_is_working_tree_true_for_staged():
    vm, _ = _make_vm()
    vm.set_points("main", "working_tree_staged")
    assert vm.target_is_working_tree is True


def test_target_is_working_tree_false_for_commit():
    vm, _ = _make_vm()
    vm.set_points("main", "abc1234")
    assert vm.target_is_working_tree is False


def test_target_is_working_tree_false_when_no_target():
    vm, _ = _make_vm()
    assert vm.target_is_working_tree is False
