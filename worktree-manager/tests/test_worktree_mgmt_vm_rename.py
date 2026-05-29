import os
import pytest
from unittest.mock import MagicMock, patch

from worktree_manager.worktree_mgmt_vm import WorktreeMgmtViewModel


def _make_vm():
    store = MagicMock()
    store.all_repos.return_value = {}
    git = MagicMock()
    return WorktreeMgmtViewModel(config_store=store, git_service=git), store, git


def test_rename_worktree_calls_git_and_store(tmp_path):
    vm, store, git = _make_vm()
    old_path = str(tmp_path / "feature-foo")
    os.makedirs(old_path)

    result = vm.rename_worktree("/repos/app", old_path, "feature-bar")

    expected_new = str(tmp_path / "feature-bar")
    git.rename_worktree.assert_called_once_with("/repos/app", old_path, expected_new)
    store.rename_worktree_path.assert_called_once_with(old_path, expected_new)
    assert result == expected_new


def test_rename_worktree_returns_new_path(tmp_path):
    vm, store, git = _make_vm()
    old_path = str(tmp_path / "worktrees" / "old-name")
    os.makedirs(old_path)

    new_path = vm.rename_worktree("/repos/app", old_path, "new-name")

    assert new_path == str(tmp_path / "worktrees" / "new-name")


def test_rename_worktree_propagates_git_error(tmp_path):
    vm, store, git = _make_vm()
    old_path = str(tmp_path / "wt")
    os.makedirs(old_path)
    git.rename_worktree.side_effect = RuntimeError("git failed")

    with pytest.raises(RuntimeError, match="git failed"):
        vm.rename_worktree("/repos/app", old_path, "new-name")
