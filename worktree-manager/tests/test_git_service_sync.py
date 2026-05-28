"""Tests for GitService sync methods added in Iteration 2."""
import subprocess
from unittest.mock import MagicMock, call, patch

import pytest

from worktree_manager.git_service import GitService


@pytest.fixture
def svc():
    return GitService()


# ── fetch ─────────────────────────────────────────────────────────────────────

def test_fetch_runs_git_fetch(svc):
    with patch.object(svc, "_run") as mock_run:
        mock_run.return_value = ""
        svc.fetch("/repo/a")
    mock_run.assert_called_once_with(["git", "fetch", "origin"], cwd="/repo/a")


def test_fetch_returns_none_on_success(svc):
    with patch.object(svc, "_run", return_value=""):
        result = svc.fetch("/repo/a")
    assert result is None


def test_fetch_returns_error_string_on_failure(svc):
    with patch.object(svc, "_run", side_effect=subprocess.CalledProcessError(1, "git", stderr="timeout")):
        result = svc.fetch("/repo/a")
    assert result is not None
    assert isinstance(result, str)


# ── upstream_status ───────────────────────────────────────────────────────────

def test_upstream_status_returns_ahead_behind(svc):
    with patch.object(svc, "_run", return_value="2\t3\n"):
        status = svc.upstream_status("/repo/a", "main")
    assert status.ahead == 2
    assert status.behind == 3
    assert status.has_upstream is True


def test_upstream_status_no_upstream(svc):
    with patch.object(svc, "_run", side_effect=subprocess.CalledProcessError(128, "git")):
        status = svc.upstream_status("/repo/a", "orphan-branch")
    assert status.has_upstream is False
    assert status.ahead == 0
    assert status.behind == 0


def test_upstream_status_up_to_date(svc):
    with patch.object(svc, "_run", return_value="0\t0\n"):
        status = svc.upstream_status("/repo/a", "main")
    assert status.ahead == 0
    assert status.behind == 0
    assert status.has_upstream is True


# ── list_feature_and_main_branches ────────────────────────────────────────────

def test_list_feature_and_main_branches_includes_main(svc):
    with patch.object(svc, "_run", return_value="main\nfeature/x\nfix/something\n"):
        branches = svc.list_feature_and_main_branches("/repo/a")
    assert "main" in branches


def test_list_feature_and_main_branches_includes_feature_prefix(svc):
    with patch.object(svc, "_run", return_value="main\nfeature/x\nfeature/y\nfix/z\n"):
        branches = svc.list_feature_and_main_branches("/repo/a")
    assert "feature/x" in branches
    assert "feature/y" in branches


def test_list_feature_and_main_branches_excludes_other_prefixes(svc):
    with patch.object(svc, "_run", return_value="main\nfeature/x\nfix/something\nhotfix/1\n"):
        branches = svc.list_feature_and_main_branches("/repo/a")
    assert "fix/something" not in branches
    assert "hotfix/1" not in branches


# ── worktree_for_branch ───────────────────────────────────────────────────────

PORCELAIN = """\
worktree /repos/proj
HEAD abc123
branch refs/heads/main

worktree /repos/proj-wt/fix-auth
HEAD def456
branch refs/heads/fix/auth

"""


def test_worktree_for_branch_finds_match(svc):
    with patch.object(svc, "_run", return_value=PORCELAIN):
        path = svc.worktree_for_branch("/repos/proj", "fix/auth")
    assert path == "/repos/proj-wt/fix-auth"


def test_worktree_for_branch_returns_none_when_no_match(svc):
    with patch.object(svc, "_run", return_value=PORCELAIN):
        path = svc.worktree_for_branch("/repos/proj", "feature/nonexistent")
    assert path is None


def test_worktree_for_branch_finds_main(svc):
    with patch.object(svc, "_run", return_value=PORCELAIN):
        path = svc.worktree_for_branch("/repos/proj", "main")
    assert path == "/repos/proj"


# ── pull_ff_only ──────────────────────────────────────────────────────────────

def test_pull_ff_only_success_returns_up_to_date(svc):
    with patch.object(svc, "_run", return_value="Already up to date.\n"):
        outcome = svc.pull_ff_only("/repos/proj-wt/fix-auth")
    assert outcome.status == "up_to_date"
    assert outcome.new_commits == 0


def test_pull_ff_only_success_returns_pulled(svc):
    with patch.object(svc, "_run", return_value="Updating abc..def\nFast-forward\n 3 files changed\n"):
        outcome = svc.pull_ff_only("/repos/proj-wt/fix-auth")
    assert outcome.status == "pulled"


def test_pull_ff_only_non_ff_returns_non_ff(svc):
    err = subprocess.CalledProcessError(1, "git")
    err.stderr = "Not possible to fast-forward, aborting."
    with patch.object(svc, "_run", side_effect=err):
        outcome = svc.pull_ff_only("/repos/proj-wt/fix-auth")
    assert outcome.status == "non_ff"


def test_pull_ff_only_dirty_returns_dirty(svc):
    err = subprocess.CalledProcessError(1, "git")
    err.stderr = "error: Your local changes to the following files would be overwritten"
    with patch.object(svc, "_run", side_effect=err):
        outcome = svc.pull_ff_only("/repos/proj-wt/fix-auth")
    assert outcome.status == "dirty"


def test_pull_ff_only_counts_new_commits(svc):
    output = "Updating abc..def\nFast-forward\n file1 | 1 +\n file2 | 2 ++\n 2 files changed\n"
    with patch.object(svc, "_run", return_value=output):
        outcome = svc.pull_ff_only("/repos/proj-wt/fix-auth")
    assert outcome.status == "pulled"


# ── update_ref_from_remote ────────────────────────────────────────────────────

def test_update_ref_from_remote_success(svc):
    with patch.object(svc, "_run", return_value=""):
        outcome = svc.update_ref_from_remote("/repo/a", "feature/x")
    assert outcome.status in ("pulled", "up_to_date")


def test_update_ref_from_remote_non_ff_returns_non_ff(svc):
    err = subprocess.CalledProcessError(1, "git")
    err.stderr = "! [rejected] feature/x -> feature/x (non-fast-forward)"
    with patch.object(svc, "_run", side_effect=err):
        outcome = svc.update_ref_from_remote("/repo/a", "feature/x")
    assert outcome.status == "non_ff"


def test_update_ref_from_remote_runs_correct_command(svc):
    with patch.object(svc, "_run") as mock_run:
        mock_run.return_value = ""
        svc.update_ref_from_remote("/repo/a", "feature/x")
    mock_run.assert_called_once_with(
        ["git", "fetch", "origin", "feature/x:feature/x"], cwd="/repo/a"
    )
