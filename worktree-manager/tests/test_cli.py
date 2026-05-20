import pytest
import sys
from unittest.mock import MagicMock
from worktree_manager.cli import parse_args, resolve_repo_path
from worktree_manager.git_service import GitService


def test_parse_args_no_argument():
    args = parse_args([])
    assert args.repo_path is None


def test_parse_args_with_path():
    args = parse_args(["/repos/proj"])
    assert args.repo_path == "/repos/proj"


def test_resolve_repo_path_valid(tmp_path):
    git = MagicMock(spec=GitService)
    git.is_valid_repo.return_value = True
    repo = tmp_path / "myrepo"
    repo.mkdir()
    result = resolve_repo_path(str(repo), git)
    assert result == str(repo)


def test_resolve_repo_path_invalid(tmp_path, capsys):
    git = MagicMock(spec=GitService)
    git.is_valid_repo.return_value = False
    with pytest.raises(SystemExit):
        resolve_repo_path(str(tmp_path / "notarepo"), git)
    captured = capsys.readouterr()
    assert "not a git repository" in captured.err.lower()


def test_resolve_repo_path_none_returns_none():
    git = MagicMock(spec=GitService)
    result = resolve_repo_path(None, git)
    assert result is None
