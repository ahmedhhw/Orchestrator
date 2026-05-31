import pytest
from unittest.mock import MagicMock, patch
import requests
from worktree_manager.github_service import GitHubService
from worktree_manager.github_models import PullRequest


@pytest.fixture
def svc():
    return GitHubService(token="ghp_test")


def _make_pr(number=42):
    return PullRequest(
        number=number, title="My Work", body="",
        html_url=f"https://github.com/myorg/myrepo/pull/{number}",
        head_branch="feat", base_branch="main",
        state="open", draft=False, mergeable=True,
    )


def test_merge_pr_calls_correct_endpoint_squash(svc):
    pr = _make_pr(42)
    with patch("worktree_manager.github_service.requests.put") as mock_put:
        mock_put.return_value = MagicMock(status_code=200, ok=True)
        mock_put.return_value.raise_for_status = MagicMock()
        svc.merge_pr(pr, squash=True)
    mock_put.assert_called_once()
    url = mock_put.call_args[0][0]
    assert "pulls/42/merge" in url
    payload = mock_put.call_args[1]["json"]
    assert payload["merge_method"] == "squash"


def test_merge_pr_calls_correct_endpoint_merge(svc):
    pr = _make_pr(42)
    with patch("worktree_manager.github_service.requests.put") as mock_put:
        mock_put.return_value = MagicMock(status_code=200, ok=True)
        mock_put.return_value.raise_for_status = MagicMock()
        svc.merge_pr(pr, squash=False)
    payload = mock_put.call_args[1]["json"]
    assert payload["merge_method"] == "merge"


def test_merge_pr_raises_on_conflict(svc):
    pr = _make_pr(42)
    with patch("worktree_manager.github_service.requests.put") as mock_put:
        mock_put.return_value = MagicMock(status_code=405, ok=False)
        mock_put.return_value.raise_for_status.side_effect = requests.HTTPError("405")
        mock_put.return_value.json.return_value = {"message": "Merge conflict"}
        with pytest.raises(RuntimeError, match="Merge conflict"):
            svc.merge_pr(pr, squash=True)


def test_merge_pr_raises_on_branch_protection(svc):
    pr = _make_pr(42)
    with patch("worktree_manager.github_service.requests.put") as mock_put:
        mock_put.return_value = MagicMock(status_code=405, ok=False)
        mock_put.return_value.raise_for_status.side_effect = requests.HTTPError("405")
        mock_put.return_value.json.return_value = {"message": "Branch protection rule"}
        with pytest.raises(RuntimeError, match="Branch protection rule"):
            svc.merge_pr(pr, squash=True)
