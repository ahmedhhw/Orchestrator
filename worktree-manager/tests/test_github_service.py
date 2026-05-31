import pytest
from unittest.mock import MagicMock, patch, call
from worktree_manager.github_service import GitHubService
from worktree_manager.github_models import PullRequest, CICheck, Review, PRComment


TOKEN = "ghp_test"


@pytest.fixture
def service():
    return GitHubService(token=TOKEN)


def _make_pr(number=1):
    return PullRequest(
        number=number, title="Test PR", body="",
        html_url=f"https://github.com/myorg/myrepo/pull/{number}",
        head_branch="feat", base_branch="main",
        state="open", draft=False, mergeable=True,
    )


# ── get_authenticated_user ───────────────────────────────────────────────────


def test_get_authenticated_user_returns_login(service):
    fake = MagicMock(status_code=200)
    fake.json.return_value = {"login": "ahmedhhw", "id": 1}
    with patch("requests.get", return_value=fake) as mock_get:
        login = service.get_authenticated_user()
    assert login == "ahmedhhw"
    mock_get.assert_called_once_with(
        "https://api.github.com/user",
        headers=service._headers,
    )


def test_get_authenticated_user_raises_on_401(service):
    fake = MagicMock(status_code=401)
    fake.raise_for_status.side_effect = Exception("401")
    with patch("requests.get", return_value=fake):
        with pytest.raises(PermissionError):
            service.get_authenticated_user()


# ── list_my_open_prs ─────────────────────────────────────────────────────────


def _search_issue_payload(number=42, title="My feature", login="ahmedhhw"):
    return {
        "number": number,
        "title": title,
        "body": "desc",
        "html_url": f"https://github.com/myorg/myrepo/pull/{number}",
        "state": "open",
        "draft": False,
        "pull_request": {"url": f"https://api.github.com/repos/myorg/myrepo/pulls/{number}"},
        "repository_url": "https://api.github.com/repos/myorg/myrepo",
        "user": {"login": login},
    }


def test_list_my_open_prs_uses_search_api(service):
    user_resp = MagicMock(status_code=200)
    user_resp.json.return_value = {"login": "ahmedhhw"}

    search_resp = MagicMock(status_code=200)
    search_resp.ok = True
    search_resp.json.return_value = {
        "total_count": 1,
        "items": [_search_issue_payload(number=42)],
    }

    with patch("requests.get", side_effect=[user_resp, search_resp]) as mock_get:
        prs = service.list_my_open_prs()

    assert len(prs) == 1
    assert prs[0].number == 42
    assert prs[0].title == "My feature"
    assert prs[0].html_url == "https://github.com/myorg/myrepo/pull/42"

    search_call = mock_get.call_args_list[1]
    assert search_call[0][0] == "https://api.github.com/search/issues"
    assert "is:pr is:open author:ahmedhhw" in search_call[1]["params"]["q"]


def test_list_my_open_prs_returns_empty_when_none(service):
    user_resp = MagicMock(status_code=200)
    user_resp.json.return_value = {"login": "ahmedhhw"}

    search_resp = MagicMock(status_code=200)
    search_resp.ok = True
    search_resp.json.return_value = {"total_count": 0, "items": []}

    with patch("requests.get", side_effect=[user_resp, search_resp]):
        prs = service.list_my_open_prs()

    assert prs == []


def test_list_my_open_prs_raises_permission_error_on_401_user(service):
    user_resp = MagicMock(status_code=401)
    user_resp.raise_for_status.side_effect = Exception("401")
    with patch("requests.get", return_value=user_resp):
        with pytest.raises(PermissionError):
            service.list_my_open_prs()


def test_list_my_open_prs_raises_permission_error_on_401_search(service):
    user_resp = MagicMock(status_code=200)
    user_resp.json.return_value = {"login": "ahmedhhw"}

    search_resp = MagicMock(status_code=401)
    search_resp.ok = False
    search_resp.raise_for_status.side_effect = Exception("401")

    with patch("requests.get", side_effect=[user_resp, search_resp]):
        with pytest.raises(PermissionError):
            service.list_my_open_prs()


# ── get_pr_detail ─────────────────────────────────────────────────────────────


def _pr_api_payload(number=1, sha="abc123"):
    return {
        "number": number,
        "title": "Test PR",
        "body": "body",
        "html_url": f"https://github.com/myorg/myrepo/pull/{number}",
        "head": {"ref": "feat", "sha": sha},
        "base": {"ref": "main"},
        "state": "open",
        "draft": False,
        "mergeable": True,
    }


def test_get_pr_detail_fetches_checks_reviews_comments(service):
    pr = _make_pr(1)
    pr_resp = MagicMock(status_code=200)
    pr_resp.json.return_value = _pr_api_payload(sha="abc123")

    checks_resp = MagicMock(status_code=200)
    checks_resp.json.return_value = {"check_runs": [
        {"name": "build", "status": "completed", "conclusion": "success",
         "check_suite": {"id": 99}},
    ]}

    reviews_resp = MagicMock(status_code=200)
    reviews_resp.json.return_value = [
        {"user": {"login": "alice"}, "state": "APPROVED"},
    ]

    comments_resp = MagicMock(status_code=200)
    comments_resp.json.return_value = [
        {"id": 1, "user": {"login": "bob"}, "body": "LGTM", "created_at": "2024-01-01T00:00:00Z"},
    ]

    with patch("requests.get", side_effect=[pr_resp, checks_resp, reviews_resp, comments_resp]):
        detail = service.get_pr_detail(1, pr=pr)

    assert detail.number == 1
    assert len(detail.checks) == 1
    assert detail.checks[0].name == "build"
    assert detail.checks[0].conclusion == "success"
    assert detail.checks[0].check_suite_id == "99"
    assert len(detail.reviews) == 1
    assert detail.reviews[0].author == "alice"
    assert detail.reviews[0].state == "APPROVED"
    assert len(detail.comments) == 1
    assert detail.comments[0].author == "bob"
    assert detail.comments[0].id == 1


# ── create_pull_request ───────────────────────────────────────────────────────


def test_create_pull_request_posts_and_returns_pr(service):
    fake_response = MagicMock(status_code=201)
    fake_response.json.return_value = {
        "number": 99,
        "title": "New PR",
        "body": "body",
        "html_url": "https://github.com/myorg/myrepo/pull/99",
        "head": {"ref": "feat", "sha": "abc"},
        "base": {"ref": "main"},
        "state": "open",
        "draft": False,
        "mergeable": None,
    }
    with patch("requests.post", return_value=fake_response) as mock_post:
        pr = service.create_pull_request(
            title="New PR", body="body", base="main", draft=False,
            repo_base_url="https://api.github.com/repos/myorg/myrepo",
        )
    assert pr.number == 99
    call_kwargs = mock_post.call_args[1]["json"]
    assert call_kwargs["title"] == "New PR"
    assert call_kwargs["base"] == "main"
    assert call_kwargs["draft"] is False


def test_create_pull_request_raises_on_422(service):
    fake_response = MagicMock(status_code=422)
    fake_response.json.return_value = {"message": "Validation Failed"}
    with patch("requests.post", return_value=fake_response):
        with pytest.raises(RuntimeError, match="Validation Failed"):
            service.create_pull_request(
                title="X", body="", base="main", draft=False,
                repo_base_url="https://api.github.com/repos/myorg/myrepo",
            )


# ── push_branch ────────────────────────────────────────────────────────────────


def test_push_branch_calls_git(service):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        service.push_branch("feature/x", repo_path="/tmp/repo")
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert "git" in args
    assert "push" in args


def test_push_branch_raises_on_failure(service):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        with pytest.raises(RuntimeError):
            service.push_branch("feature/x", repo_path="/tmp/repo")
