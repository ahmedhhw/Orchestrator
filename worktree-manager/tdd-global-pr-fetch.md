# TDD Plan — Global PR Fetch via Search API

## Problem

`list_my_open_prs()` currently calls `GET /repos/{owner}/{repo}/pulls`, which only returns PRs
for one specific repo and requires the owner/repo to be known up front. The correct approach is:

1. `GET /user` → resolve the authenticated user's login
2. `GET /search/issues?q=is:pr+is:open+author:{login}` → fetch all open PRs across all repos

This removes the dependency on owner/repo for the PR list entirely. Owner/repo is still needed
for PR detail (checks, reviews, comments) — those endpoints stay as-is.

---

## What changes

### `GitHubService`

- Add `get_authenticated_user() -> str` — calls `GET /user`, returns `login`
- Rewrite `list_my_open_prs()` — calls `GET /search/issues` with
  `q=is:pr is:open author:{login}`, maps search results to `PullRequest` objects
- `GitHubService.__init__` owner/repo become optional (defaulting to `""`) since
  `list_my_open_prs` no longer needs them

### `_pr_from_search_result(data: dict) -> PullRequest`

Search results have a different shape from PR API responses:
- No `head`/`base` keys — use `pull_request.html_url` to infer `head_branch` is unknown;
  store `""` for head/base branch (detail view fetches the real PR object anyway)
- `number`, `title`, `body`, `html_url`, `state`, `draft` are present and identical

---

## Phase 1 — `get_authenticated_user()`

### Tests (Red)

```python
# tests/test_github_service.py  (add to existing file)

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
```

### Production code (Green)

In `worktree_manager/github_service.py`, add after `from_remote_url`:

```python
def get_authenticated_user(self) -> str:
    resp = requests.get("https://api.github.com/user", headers=self._headers)
    if resp.status_code == 401:
        raise PermissionError("GitHub token is invalid or expired")
    resp.raise_for_status()
    return resp.json()["login"]
```

### Done when

`test_get_authenticated_user_returns_login` and `test_get_authenticated_user_raises_on_401` pass.

---

## Phase 2 — `list_my_open_prs()` via Search API

### Tests (Red)

```python
# tests/test_github_service.py  (add to existing file)

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

    # Confirm the search URL and query param
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
```

### Production code (Green)

Replace `list_my_open_prs` in `worktree_manager/github_service.py`:

```python
def list_my_open_prs(self) -> list[PullRequest]:
    login = self.get_authenticated_user()
    log.debug("list_my_open_prs: searching for PRs authored by %r", login)

    resp = requests.get(
        "https://api.github.com/search/issues",
        headers=self._headers,
        params={"q": f"is:pr is:open author:{login}", "per_page": 50},
    )
    log.debug("list_my_open_prs: search status=%d", resp.status_code)
    if resp.status_code == 401:
        raise PermissionError("GitHub token is invalid or expired")
    if not resp.ok:
        log.error("list_my_open_prs: error body: %s", resp.text[:500])
    resp.raise_for_status()

    items = resp.json().get("items", [])
    log.debug("list_my_open_prs: got %d PRs", len(items))
    return [self._pr_from_search_result(item) for item in items]

def _pr_from_search_result(self, data: dict) -> PullRequest:
    # Search results don't include head/base branch — detail view fetches the
    # full PR object which has them.
    return PullRequest(
        number=data["number"],
        title=data["title"],
        body=data.get("body") or "",
        html_url=data["html_url"],
        head_branch="",
        base_branch="",
        state=data["state"],
        draft=data.get("draft", False),
        mergeable=None,
    )
```

Also remove the `owner/repo` guard that was added to the old `list_my_open_prs` — it's no longer needed.

### Done when

All four new `list_my_open_prs` tests pass, and the existing `test_list_my_open_prs_raises_on_401` test is updated or replaced by the new equivalents.

---

## Phase 3 — Update `GitHubViewModel` init: drop owner/repo requirement

Now that `list_my_open_prs` needs no owner/repo, the VM no longer needs to treat a missing
owner/repo as MISSING token state. Token alone is sufficient to enter CONFIGURED state.

### Tests (Red)

```python
# tests/test_github_vm.py  (add to existing file)

def test_vm_enters_configured_state_with_token_only(tmp_path):
    from unittest.mock import MagicMock
    from worktree_manager.github_vm import GitHubViewModel, TokenState

    store = MagicMock()
    store.get_github_token.return_value = "ghp_test"
    store.get_github_owner.return_value = ""   # no owner
    store.get_github_repo.return_value = ""    # no repo
    store.get_github_poll_interval.return_value = 30

    vm = GitHubViewModel(store=store, repo_path="")
    assert vm.token_state == TokenState.CONFIGURED
```

### Production code (Green)

In `worktree_manager/github_vm.py`, change the init check:

```python
# Before:
token = store.get_github_token()
owner = store.get_github_owner()
repo = store.get_github_repo()
if token and owner and repo:
    self._token_state = TokenState.CONFIGURED
    self._init_service(token)
else:
    self._token_state = TokenState.MISSING

# After:
token = store.get_github_token()
if token:
    self._token_state = TokenState.CONFIGURED
    self._init_service(token)
else:
    self._token_state = TokenState.MISSING
```

### Done when

`test_vm_enters_configured_state_with_token_only` passes.

---

## Existing tests to update

`test_list_my_open_prs_returns_pull_requests` and `test_list_my_open_prs_raises_on_401` in
`tests/test_github_service.py` test the old single-`requests.get` shape. After Phase 2 they will
fail because `list_my_open_prs` now makes two requests. Replace them with the new tests from
Phase 2 (the new tests cover the same assertions).

---

## Implementation order

1. Phase 1 — write the two `get_authenticated_user` tests, make them pass
2. Phase 2 — write the four `list_my_open_prs` tests, replace the old two, make them pass
3. Phase 3 — write the VM init test, update the VM init condition, make it pass
