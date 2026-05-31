import pytest
from unittest.mock import MagicMock, patch
from worktree_manager.github_service import GitHubService
from worktree_manager.github_models import PullRequest, CICheck, Review, PRComment


@pytest.fixture
def svc():
    return GitHubService(token="ghp_test")


def _make_pr(number=1):
    return PullRequest(
        number=number, title="My PR", body="",
        html_url=f"https://github.com/myorg/myrepo/pull/{number}",
        head_branch="feat", base_branch="main",
        state="open", draft=False, mergeable=True,
        head_sha="abc123",
        checks=[CICheck("build", "completed", "success")],
    )


def test_get_pr_detail_with_cached_pr_skips_pr_and_checks_fetch(svc):
    """When a cached pr is passed, only reviews + comments are fetched (2 calls, not 4)."""
    pr = _make_pr(1)
    reviews_resp = MagicMock(status_code=200)
    reviews_resp.json.return_value = [{"user": {"login": "alice"}, "state": "APPROVED"}]
    comments_resp = MagicMock(status_code=200)
    comments_resp.json.return_value = []

    with patch("requests.get", side_effect=[reviews_resp, comments_resp]) as mock_get:
        detail = svc.get_pr_detail(1, pr=pr)

    assert mock_get.call_count == 2
    assert detail.checks == pr.checks
    assert len(detail.reviews) == 1
    assert detail.reviews[0].author == "alice"


def test_get_pr_detail_without_cached_pr_fetches_all(svc):
    """When no cached pr is passed (pr has no head_sha), all 4 calls are made."""
    bare_pr = PullRequest(
        number=1, title="t", body="",
        html_url="https://github.com/myorg/myrepo/pull/1",
        head_branch="feat", base_branch="main",
        state="open", draft=False, mergeable=None,
        head_sha="",
    )
    pr_resp = MagicMock(status_code=200)
    pr_resp.json.return_value = {
        "number": 1, "title": "t", "body": "", "state": "open", "draft": False,
        "mergeable": True, "html_url": "https://github.com/myorg/myrepo/pull/1",
        "head": {"ref": "feat", "sha": "abc123"}, "base": {"ref": "main"},
    }
    checks_resp = MagicMock(status_code=200)
    checks_resp.json.return_value = {"check_runs": []}
    reviews_resp = MagicMock(status_code=200)
    reviews_resp.json.return_value = []
    comments_resp = MagicMock(status_code=200)
    comments_resp.json.return_value = []

    with patch("requests.get", side_effect=[pr_resp, checks_resp, reviews_resp, comments_resp]) as mock_get:
        svc.get_pr_detail(1, pr=bare_pr)

    assert mock_get.call_count == 4
