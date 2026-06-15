import pytest
from unittest.mock import MagicMock, patch
import requests
from worktree_manager.github_service import GitHubService
from worktree_manager.github_models import PullRequest


@pytest.fixture
def svc():
    return GitHubService(token="ghp_test")


def _make_pr(owner="myorg", repo="myrepo"):
    return PullRequest(
        number=1, title="T", body="", html_url=f"https://github.com/{owner}/{repo}/pull/1",
        head_branch="feat", base_branch="main", state="open", draft=False, mergeable=True,
    )


# ── rerun_all_checks (renamed from rerun_failed_checks) ──────────────────────

def test_rerun_all_checks_posts_to_check_suite_rerequest_endpoint(svc):
    pr = _make_pr()
    with patch("worktree_manager.github_service.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=201)
        svc.rerun_all_checks("suite-42", pr)
    mock_post.assert_called_once()
    url = mock_post.call_args[0][0]
    assert "check-suites/suite-42/rerequest" in url


def test_rerun_all_checks_raises_on_http_error(svc):
    pr = _make_pr()
    with patch("worktree_manager.github_service.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=403, ok=False)
        mock_post.return_value.raise_for_status.side_effect = requests.HTTPError("403")
        with pytest.raises(requests.HTTPError):
            svc.rerun_all_checks("suite-42", pr)


# ── rerun_failed_jobs ────────────────────────────────────────────────────────

def test_rerun_failed_jobs_posts_to_actions_rerun_failed_jobs_endpoint(svc):
    pr = _make_pr()
    with patch("worktree_manager.github_service.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=201)
        svc.rerun_failed_jobs("99", pr)
    mock_post.assert_called_once()
    url = mock_post.call_args[0][0]
    assert "actions/runs/99/rerun-failed-jobs" in url


def test_rerun_failed_jobs_raises_on_http_error(svc):
    pr = _make_pr()
    with patch("worktree_manager.github_service.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=422, ok=False)
        mock_post.return_value.raise_for_status.side_effect = requests.HTTPError("422")
        with pytest.raises(requests.HTTPError):
            svc.rerun_failed_jobs("99", pr)
