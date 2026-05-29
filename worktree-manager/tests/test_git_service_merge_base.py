import subprocess
from unittest.mock import patch, MagicMock

from worktree_manager.git_service import GitService


def _svc():
    return GitService()


def _run_returns(output):
    m = MagicMock(return_value=output)
    return patch.object(GitService, "_run", m)


def test_resolve_merge_base_returns_sha(tmp_path):
    svc = _svc()
    with _run_returns("abc1234\n") as mock_run:
        result = svc.resolve_merge_base("/repo", "feature/login", "main")
    assert result == "abc1234"
    mock_run.assert_called_once_with(
        ["git", "merge-base", "main", "feature/login"], cwd="/repo"
    )


def test_resolve_merge_base_strips_whitespace(tmp_path):
    svc = _svc()
    with _run_returns("  def5678  \n"):
        result = svc.resolve_merge_base("/repo", "feature/x", "main")
    assert result == "def5678"


def test_resolve_merge_base_raises_on_failure():
    svc = _svc()
    with patch.object(GitService, "_run", side_effect=subprocess.CalledProcessError(1, "git")):
        try:
            svc.resolve_merge_base("/repo", "orphan", "main")
            assert False, "Expected exception"
        except subprocess.CalledProcessError:
            pass
