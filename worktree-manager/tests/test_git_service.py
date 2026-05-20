import pytest
from unittest.mock import patch, MagicMock
from worktree_manager.git_service import GitService
from worktree_manager.models import WorktreeModel


@pytest.fixture
def svc():
    return GitService()


PORCELAIN_OUTPUT = """\
worktree /repos/proj
HEAD abc123
branch refs/heads/main

worktree /repos/proj-wt/feature-auth
HEAD def456
branch refs/heads/feature/auth

"""


def test_parse_worktree_list(svc):
    with patch.object(svc, "_run", return_value=PORCELAIN_OUTPUT):
        with patch.object(svc, "last_commit_ts", return_value=1_700_000_000):
            with patch.object(svc, "is_merged", return_value=False):
                results = svc.list_worktrees("/repos/proj", stale_days=30)
    assert len(results) == 2
    assert results[0].branch == "main"
    assert results[0].is_main is True
    assert results[1].branch == "feature/auth"
    assert results[1].is_main is False


def test_list_worktrees_marks_stale(svc):
    import time
    old_ts = int(time.time()) - (35 * 86400)
    with patch.object(svc, "_run", return_value=PORCELAIN_OUTPUT):
        with patch.object(svc, "last_commit_ts", return_value=old_ts):
            with patch.object(svc, "is_merged", return_value=False):
                results = svc.list_worktrees("/repos/proj", stale_days=30)
    assert all(wt.is_stale for wt in results)


def test_list_worktrees_marks_not_stale(svc):
    import time
    recent_ts = int(time.time()) - (5 * 86400)
    with patch.object(svc, "_run", return_value=PORCELAIN_OUTPUT):
        with patch.object(svc, "last_commit_ts", return_value=recent_ts):
            with patch.object(svc, "is_merged", return_value=False):
                results = svc.list_worktrees("/repos/proj", stale_days=30)
    assert all(not wt.is_stale for wt in results)


def test_is_valid_repo_true(svc, tmp_path):
    repo = tmp_path / "myrepo"
    repo.mkdir()
    (repo / ".git").mkdir()
    assert svc.is_valid_repo(str(repo)) is True


def test_is_valid_repo_false(svc, tmp_path):
    assert svc.is_valid_repo(str(tmp_path)) is False


def test_create_worktree_calls_git(svc):
    with patch.object(svc, "_run") as mock_run:
        svc.create_worktree(
            repo_path="/repos/proj",
            worktree_path="/repos/proj-wt/feat",
            branch="feature/new",
            base_branch="main",
        )
    mock_run.assert_called_once_with(
        ["git", "worktree", "add", "-b", "feature/new",
         "/repos/proj-wt/feat", "main"],
        cwd="/repos/proj",
    )


def test_delete_worktree_calls_git(svc):
    with patch.object(svc, "_run") as mock_run:
        svc.delete_worktree(repo_path="/repos/proj", worktree_path="/repos/proj-wt/feat")
    mock_run.assert_called_once_with(
        ["git", "worktree", "remove", "--force", "/repos/proj-wt/feat"],
        cwd="/repos/proj",
    )


def test_delete_branch_calls_git(svc):
    with patch.object(svc, "_run") as mock_run:
        svc.delete_branch(repo_path="/repos/proj", branch="feature/old")
    mock_run.assert_called_once_with(
        ["git", "branch", "-D", "feature/old"],
        cwd="/repos/proj",
    )


def test_list_local_branches(svc):
    with patch.object(svc, "_run", return_value="main\nfeature/auth\nfix/bug\n"):
        branches = svc.list_local_branches("/repos/proj")
    assert branches == ["main", "feature/auth", "fix/bug"]


def test_is_merged_true(svc):
    with patch.object(svc, "_run", return_value="feature/auth\n"):
        assert svc.is_merged("/repos/proj", "feature/auth", "main") is True


def test_is_merged_false(svc):
    with patch.object(svc, "_run", return_value="fix/wip\n"):
        assert svc.is_merged("/repos/proj", "feature/unmerged", "main") is False
