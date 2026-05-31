import pytest
from unittest.mock import MagicMock, patch
from worktree_manager.github_service import GitHubService
from worktree_manager.github_models import PullRequest, CICheck


@pytest.fixture
def svc():
    return GitHubService(token="ghp_test")


def _make_cached_pr(number=1, mergeable=None):
    return PullRequest(
        number=number, title="My PR", body="",
        html_url=f"https://github.com/myorg/myrepo/pull/{number}",
        head_branch="feat", base_branch="main",
        state="open", draft=False, mergeable=mergeable,
        head_sha="abc123",
        checks=[CICheck("build", "completed", "success")],
    )


def _pr_api_resp(mergeable=True):
    resp = MagicMock(status_code=200)
    resp.json.return_value = {
        "number": 1, "title": "My PR", "body": "", "state": "open", "draft": False,
        "mergeable": mergeable,
        "html_url": "https://github.com/myorg/myrepo/pull/1",
        "head": {"ref": "feat", "sha": "abc123"}, "base": {"ref": "main"},
    }
    return resp


def _reviews_resp():
    resp = MagicMock(status_code=200)
    resp.json.return_value = []
    return resp


def _comments_resp():
    resp = MagicMock(status_code=200)
    resp.json.return_value = []
    return resp


def test_cached_pr_always_fetches_pr_endpoint(svc):
    """Even when head_sha is cached, GET /pulls/{n} is called to refresh mergeable."""
    pr = _make_cached_pr(mergeable=None)

    with patch("requests.get", side_effect=[_pr_api_resp(True), _reviews_resp(), _comments_resp()]) as mock_get:
        svc.get_pr_detail(1, pr=pr)

    urls = [c.args[0] for c in mock_get.call_args_list]
    assert any("/pulls/1" in u for u in urls)


def test_cached_pr_updates_mergeable_from_api(svc):
    """mergeable is updated from the fresh API response, not left as None."""
    pr = _make_cached_pr(mergeable=None)

    with patch("requests.get", side_effect=[_pr_api_resp(True), _reviews_resp(), _comments_resp()]):
        detail = svc.get_pr_detail(1, pr=pr)

    assert detail.mergeable is True


def test_cached_pr_does_not_refetch_checks(svc):
    """Checks endpoint is still skipped when head_sha is cached."""
    pr = _make_cached_pr(mergeable=None)

    with patch("requests.get", side_effect=[_pr_api_resp(True), _reviews_resp(), _comments_resp()]) as mock_get:
        svc.get_pr_detail(1, pr=pr)

    urls = [c.args[0] for c in mock_get.call_args_list]
    assert not any("/check-runs" in u for u in urls)
    assert mock_get.call_count == 3


def test_cached_pr_preserves_existing_checks(svc):
    """Checks already on the cached PR are not cleared."""
    pr = _make_cached_pr(mergeable=None)
    original_checks = pr.checks[:]

    with patch("requests.get", side_effect=[_pr_api_resp(True), _reviews_resp(), _comments_resp()]):
        detail = svc.get_pr_detail(1, pr=pr)

    assert detail.checks == original_checks
