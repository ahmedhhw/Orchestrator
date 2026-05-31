import pytest
from unittest.mock import patch, MagicMock
from worktree_manager.git_service import GitService


@pytest.fixture
def git():
    return GitService()


def test_list_remote_branches_returns_branch_names(git):
    raw = "  origin/main\n  origin/develop\n  origin/feature/foo\n"
    with patch.object(git, "_run", return_value=raw):
        branches = git.list_remote_branches("/repos/alpha")
    assert branches == ["main", "develop", "feature/foo"]


def test_list_remote_branches_strips_origin_prefix(git):
    raw = "  origin/release/1.0\n  origin/hotfix/xyz\n"
    with patch.object(git, "_run", return_value=raw):
        branches = git.list_remote_branches("/repos/alpha")
    assert "release/1.0" in branches
    assert "hotfix/xyz" in branches


def test_list_remote_branches_excludes_head(git):
    raw = "  origin/HEAD -> origin/main\n  origin/main\n  origin/develop\n"
    with patch.object(git, "_run", return_value=raw):
        branches = git.list_remote_branches("/repos/alpha")
    assert "HEAD" not in " ".join(branches)
    assert branches == ["main", "develop"]


def test_list_remote_branches_returns_empty_on_error(git):
    with patch.object(git, "_run", side_effect=Exception("not a git repo")):
        branches = git.list_remote_branches("/not/a/repo")
    assert branches == []
