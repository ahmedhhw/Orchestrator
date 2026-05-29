import os
import subprocess
import pytest
from unittest.mock import MagicMock, patch, call

from worktree_manager.git_service import GitService


def test_rename_worktree_renames_directory_and_repairs(tmp_path):
    old_path = str(tmp_path / "old-wt")
    new_path = str(tmp_path / "new-wt")
    os.makedirs(old_path)

    svc = GitService()
    with patch.object(svc, "_run") as mock_run:
        svc.rename_worktree("/repo", old_path, new_path)

    assert not os.path.exists(old_path)
    assert os.path.exists(new_path)
    mock_run.assert_called_once_with(
        ["git", "worktree", "repair"], cwd=new_path
    )


def test_rename_worktree_raises_if_old_path_missing(tmp_path):
    svc = GitService()
    with pytest.raises(FileNotFoundError):
        svc.rename_worktree("/repo", str(tmp_path / "missing"), str(tmp_path / "dest"))


def test_rename_worktree_raises_if_new_path_exists(tmp_path):
    old_path = str(tmp_path / "old-wt")
    new_path = str(tmp_path / "new-wt")
    os.makedirs(old_path)
    os.makedirs(new_path)

    svc = GitService()
    with pytest.raises(FileExistsError):
        svc.rename_worktree("/repo", old_path, new_path)
