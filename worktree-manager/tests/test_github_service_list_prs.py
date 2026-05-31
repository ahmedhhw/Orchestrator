import pytest
from unittest.mock import MagicMock, patch
from worktree_manager.github_service import GitHubService
from worktree_manager.github_models import PullRequest, CICheck


TOKEN = "ghp_test"


@pytest.fixture
def svc():
    return GitHubService(token=TOKEN)


def _pulls_api_item(number=1, head_ref="feat", base_ref="main", sha="abc", login="me", title="My PR"):
    return {
        "number": number,
        "title": title,
        "body": "body",
        "html_url": f"https://github.com/myorg/myrepo/pull/{number}",
        "head": {"ref": head_ref, "sha": sha},
        "base": {"ref": base_ref},
        "state": "open",
        "draft": False,
        "mergeable": True,
        "user": {"login": login},
    }


def _search_item(number=1, owner="myorg", repo="myrepo"):
    return {
        "number": number,
        "title": "My PR",
        "body": "",
        "html_url": f"https://github.com/{owner}/{repo}/pull/{number}",
        "state": "open",
        "draft": False,
        "repository_url": f"https://api.github.com/repos/{owner}/{repo}",
        "user": {"login": "me"},
    }


# ── discover_open_pr_repos ───────────────────────────────────────────────────

def test_discover_open_pr_repos_returns_owner_repo_tuples(svc):
    search_resp = MagicMock(status_code=200, ok=True)
    search_resp.json.return_value = {"items": [
        _search_item(1, "myorg", "api"),
        _search_item(2, "myorg", "frontend"),
        _search_item(3, "myorg", "api"),  # duplicate repo — should deduplicate
    ]}
    with patch("requests.get", return_value=search_resp):
        repos = svc.discover_open_pr_repos("me")
    assert repos == {("myorg", "api"), ("myorg", "frontend")}


def test_discover_open_pr_repos_raises_on_401(svc):
    resp = MagicMock(status_code=401, ok=False)
    resp.raise_for_status.side_effect = Exception("401")
    with patch("requests.get", return_value=resp):
        with pytest.raises(PermissionError):
            svc.discover_open_pr_repos("me")


def test_discover_open_pr_repos_returns_empty_set_when_no_prs(svc):
    resp = MagicMock(status_code=200, ok=True)
    resp.json.return_value = {"items": []}
    with patch("requests.get", return_value=resp):
        repos = svc.discover_open_pr_repos("me")
    assert repos == set()


# ── list_prs_for_repo ────────────────────────────────────────────────────────

def test_list_prs_for_repo_returns_prs_filtered_to_login(svc):
    resp = MagicMock(status_code=200, ok=True)
    resp.json.return_value = [
        _pulls_api_item(1, login="me"),
        _pulls_api_item(2, login="other"),  # not mine — should be excluded
    ]
    with patch("requests.get", return_value=resp):
        prs = svc.list_prs_for_repo("myorg", "myrepo", "me")
    assert len(prs) == 1
    assert prs[0].number == 1


def test_list_prs_for_repo_populates_head_base_sha(svc):
    resp = MagicMock(status_code=200, ok=True)
    resp.json.return_value = [_pulls_api_item(1, head_ref="feat", base_ref="main", sha="deadbeef")]
    with patch("requests.get", return_value=resp):
        prs = svc.list_prs_for_repo("myorg", "myrepo", "me")
    assert prs[0].head_branch == "feat"
    assert prs[0].base_branch == "main"
    assert prs[0].head_sha == "deadbeef"


def test_list_prs_for_repo_calls_correct_endpoint(svc):
    resp = MagicMock(status_code=200, ok=True)
    resp.json.return_value = []
    with patch("requests.get", return_value=resp) as mock_get:
        svc.list_prs_for_repo("myorg", "myrepo", "me")
    url = mock_get.call_args[0][0]
    assert url == "https://api.github.com/repos/myorg/myrepo/pulls"
    params = mock_get.call_args[1]["params"]
    assert params["state"] == "open"


def test_list_prs_for_repo_raises_on_401(svc):
    resp = MagicMock(status_code=401, ok=False)
    resp.raise_for_status.side_effect = PermissionError("401")
    with patch("requests.get", return_value=resp):
        with pytest.raises(PermissionError):
            svc.list_prs_for_repo("myorg", "myrepo", "me")


# ── fetch_check_runs ─────────────────────────────────────────────────────────

def test_fetch_check_runs_returns_ci_checks(svc):
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"check_runs": [
        {"name": "build", "status": "completed", "conclusion": "success",
         "check_suite": {"id": 42}},
        {"name": "lint",  "status": "completed", "conclusion": "failure",
         "check_suite": {"id": 42}},
    ]}
    with patch("requests.get", return_value=resp):
        checks = svc.fetch_check_runs("myorg", "myrepo", "deadbeef")
    assert len(checks) == 2
    assert checks[0].name == "build"
    assert checks[0].conclusion == "success"
    assert checks[1].conclusion == "failure"
    assert checks[0].check_suite_id == "42"


def test_fetch_check_runs_returns_empty_on_non_200(svc):
    resp = MagicMock(status_code=404)
    with patch("requests.get", return_value=resp):
        checks = svc.fetch_check_runs("myorg", "myrepo", "deadbeef")
    assert checks == []


def test_fetch_check_runs_calls_correct_endpoint(svc):
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"check_runs": []}
    with patch("requests.get", return_value=resp) as mock_get:
        svc.fetch_check_runs("myorg", "myrepo", "abc123")
    url = mock_get.call_args[0][0]
    assert "repos/myorg/myrepo/commits/abc123/check-runs" in url


# ── fetch_mergeable ──────────────────────────────────────────────────────────

def test_fetch_mergeable_returns_true_when_api_says_true(svc):
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"mergeable": True}
    with patch("requests.get", return_value=resp):
        result = svc.fetch_mergeable("myorg", "myrepo", 1)
    assert result is True


def test_fetch_mergeable_returns_none_when_api_says_null(svc):
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"mergeable": None}
    with patch("requests.get", return_value=resp):
        result = svc.fetch_mergeable("myorg", "myrepo", 1)
    assert result is None


def test_fetch_mergeable_calls_correct_endpoint(svc):
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"mergeable": True}
    with patch("requests.get", return_value=resp) as mock_get:
        svc.fetch_mergeable("myorg", "myrepo", 42)
    url = mock_get.call_args[0][0]
    assert url == "https://api.github.com/repos/myorg/myrepo/pulls/42"


# ── head_sha field on PullRequest ─────────────────────────────────────────────

def test_pull_request_has_head_sha_field():
    pr = PullRequest(
        number=1, title="t", body="", html_url="https://github.com/o/r/pull/1",
        head_branch="feat", base_branch="main", state="open", draft=False, mergeable=True,
        head_sha="deadbeef",
    )
    assert pr.head_sha == "deadbeef"


def test_pull_request_head_sha_defaults_to_empty_string():
    pr = PullRequest(
        number=1, title="t", body="", html_url="https://github.com/o/r/pull/1",
        head_branch="feat", base_branch="main", state="open", draft=False, mergeable=True,
    )
    assert pr.head_sha == ""
