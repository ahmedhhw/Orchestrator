# PR List Descriptive Rows

## Overview

The "My PRs" list currently shows each PR as a single line: `#N  Title   ⏳`. The original design mockups show a richer two-line row format with the `head → base` branch on a second line and a more descriptive status badge (e.g. "⏳ checks running", "✅ ready to merge", "❌ checks failed"). This feature upgrades the list to match those mockups and removes the "← current branch" indicator that the user does not want on this page.

---

## UI / Flow

### PR list — current (before)

```
┌────────────────────────────────────────────────────────────────┐
│  My PRs tab                                                    │
│────────────────────────────────────────────────────────────────│
│  #142  My Work   ⏳                                            │
│  #138  Fix login timeout   ✅                                  │
│  #131  Refactor auth layer   ❌                                │
└────────────────────────────────────────────────────────────────┘
```

### PR list — target (after), matches original mockup minus "current branch"

```
┌────────────────────────────────────────────────────────────────┐
│  My PRs tab                                                    │
│────────────────────────────────────────────────────────────────│
│  #142  My Work              ⏳ checks running       [↗ View]   │
│  feature/my-work → main                                        │
│                                                                │
│  #138  Fix login timeout    ✅ ready to merge       [↗ View]   │
│  fix/login-timeout → main                                      │
│                                                                │
│  #131  Refactor auth layer  ❌ checks failed        [↗ View]   │
│  refactor/auth → main                                          │
└────────────────────────────────────────────────────────────────┘
```

### With unread comment badge

```
│  #142  My Work    🔴 2 new  ❌ checks failed        [↗ View]   │
│  feature/my-work → main                                        │
```

### Right-click context menu on a PR row

```
│  #138  Fix login timeout    ✅ ready to merge       [↗ View]   │◀ right-click
│  fix/login-timeout → main                                      │
         ┌─────────────────────┐
         │  ↗ View details     │
         │  ✓ Merge (squash)   │  ← only shown when is_ready_to_merge()
         │  ⧉ Copy URL         │
         └─────────────────────┘
```

"Merge (squash)" only appears in the context menu when `pr.is_ready_to_merge()` is `True`. Clicking it calls `vm.merge_pr(pr.number, squash=True)` directly — same path as the merge button in the detail view.

### Status labels mapping

| CI status  | Badge text                   |
|------------|------------------------------|
| running    | ⏳ checks running            |
| failed     | ❌ checks failed             |
| passed     | ✅ ready to merge (if mergeable + approved) OR ✅ checks passed |
| unknown    | – no checks                  |

---

### Tracked repos footer + fetch status

A compact footer sits below the PR list at all times, showing which repos are being tracked and live fetch progress. This gives the user visibility into what's being polled and a way to force a re-bootstrap when the tracked set is stale.

#### Normal state — repos known, idle

```
┌────────────────────────────────────────────────────────────────┐
│  #142  My Work                              ⏳ checks running  │
│  feature/my-work → main                                        │
│  ...                                                           │
│────────────────────────────────────────────────────────────────│
│  Tracking: myorg/api  myorg/frontend                [↺ Rescan] │
└────────────────────────────────────────────────────────────────┘
```

#### During a poll — per-repo fetch progress

```
│────────────────────────────────────────────────────────────────│
│  Fetching: myorg/api ✅  myorg/frontend ⏳…          [↺ Rescan] │
└────────────────────────────────────────────────────────────────┘
```

Each repo token updates in place as its fetch completes (✅) or fails (❌). Once all are done the footer returns to "Tracking:" idle state.

#### Bootstrap / rescan in progress

Shown on first load and when the user clicks `[↺ Rescan]`:

```
│────────────────────────────────────────────────────────────────│
│  Scanning GitHub for repos with your open PRs…                [↺ Rescan] │
└────────────────────────────────────────────────────────────────┘
```

#### New repo discovered mid-session (PR opened in untracked repo)

When a poll finds a PR whose repo is not yet in `_known_repos` the repo is added automatically and the footer updates without a full rescan:

```
│────────────────────────────────────────────────────────────────│
│  Tracking: myorg/api  myorg/frontend  myorg/new-repo  [↺ Rescan] │
└────────────────────────────────────────────────────────────────┘
```

However if the user opens a PR in a brand-new repo and the next poll doesn't catch it (because `_known_repos` was stale), clicking `[↺ Rescan]` forces a fresh Search API call to rediscover all repos and resets `_known_repos`.

---

## Architecture

### Data fetching strategy

**Current problem:** [`worktree_manager/github_service.py`](worktree_manager/github_service.py) `list_my_open_prs` uses the GitHub Search API (`GET /search/issues`), which returns PR metadata only — no `head_branch`, `base_branch`, `checks`, or `reviews`. The check-runs and branch info are only fetched lazily in `get_pr_detail` when a row is clicked. So the list currently shows empty branches and no CI badges.

**New strategy:**

1. **Bootstrap (once per panel open):** Call the Search API (`GET /search/issues?q=is:pr+is:open+author:{login}`) once to discover which `{owner}/{repo}` pairs the user has open PRs in. Cache this set of repos in `GitHubViewModel._known_repos: set[tuple[str, str]]`.

2. **Every poll:** For each known repo, call `GET /repos/{owner}/{repo}/pulls?state=open&per_page=100`. This endpoint returns full PR objects including `head.ref`, `base.ref`, and `mergeable` in a single call per repo. Filter results to PRs authored by the authenticated user. Merge all repos' results into `self.prs`.

3. **CI checks:** After fetching the PR list, fetch check-runs for each PR (`GET /repos/{owner}/{repo}/commits/{sha}/check-runs`) using `concurrent.futures.ThreadPoolExecutor` so all repos' check fetches run in parallel. The head SHA is available from the `GET /pulls` response (`head.sha`).

4. **Reviews and comments** remain lazy — fetched only when opening the detail view. Not needed for list display.

5. **Cache invalidation:** If a poll finds a PR from a repo not yet in `_known_repos`, add it. The cache never shrinks during a session (closed PRs just stop appearing in poll results naturally).

**Result:** Panel open = 1 Search call. Every poll = N calls (one per repo) + N×M check-run calls (parallelised), where N = number of repos with open PRs and M is typically 1–3. For a typical developer with PRs in 2–5 repos this is 3–10 total network calls per poll, all returning full data.

### Key code changes

1. **[`worktree_manager/github_service.py`](worktree_manager/github_service.py)**
   - `list_my_open_prs` → split into `discover_open_pr_repos(login) -> set[tuple[str,str]]` (Search API, called once) and `list_prs_for_repo(owner, repo, login) -> list[PullRequest]` (`GET /pulls?state=open`, returns full objects)
   - `list_prs_for_repo` populates `head_branch`, `base_branch`, `mergeable`, and `head_sha` on each `PullRequest`
   - Add `fetch_check_runs(owner, repo, sha) -> list[CICheck]` extracted from `get_pr_detail`
   - `get_pr_detail` updated to accept an already-fetched `PullRequest` and only supplement it with reviews + comments (skips the `GET /pulls/{n}` and check-runs calls since the list fetch already has that data)

2. **[`worktree_manager/github_models.py`](worktree_manager/github_models.py)**
   - Add `head_sha: str = ""` field to `PullRequest` (needed to call check-runs endpoint from the list fetch)

3. **[`worktree_manager/github_vm.py`](worktree_manager/github_vm.py)**
   - Add `_known_repos: set[tuple[str, str]] = set()` and `_login: str = ""`
   - On first `refresh_prs` call: populate `_known_repos` via `discover_open_pr_repos`
   - Each subsequent poll: call `list_prs_for_repo` for all known repos, then fetch check-runs in parallel via `ThreadPoolExecutor`
   - `select_pr` uses the already-fetched `PullRequest` from `self.prs` as the base and only calls `get_pr_detail` to layer in reviews + comments — no re-fetch of branch info or checks
   - `fetch_status_changed = Signal(str)` — emitted with the footer label text at each stage transition (scanning, per-repo progress updates, idle)
   - `rescan_repos()` — public method that clears `_known_repos`/`_login` and re-runs bootstrap

4. **[`worktree_manager/ui/github_panel.py`](worktree_manager/ui/github_panel.py)**
   - `_ci_badge(pr)` → returns a full descriptive string: `"⏳ checks running"`, `"❌ checks failed"`, `"✅ ready to merge"`, `"✅ checks passed"`, `"– no checks"`
   - `_on_prs_updated` → two-line item text + a `[↗ View]` button per row rendered via a custom item widget (`QWidget` with `QHBoxLayout`); removes `← current branch` logic; double-click on the list is also removed as the sole entry point
   - Add a footer bar below the PR list containing a `QLabel` for fetch status and a `[↺ Rescan]` `QPushButton`
   - Footer label transitions: "Scanning…" during bootstrap, "Fetching: owner/repo ✅  owner/repo2 ⏳…" during a poll (updated per-repo as results arrive), "Tracking: owner/repo  owner/repo2" when idle
   - `[↺ Rescan]` button calls `GitHubViewModel.rescan_repos()` which clears `_known_repos` and re-runs bootstrap

### Files touched

- [`worktree_manager/github_service.py`](worktree_manager/github_service.py) — new fetch methods
- [`worktree_manager/github_models.py`](worktree_manager/github_models.py) — `head_sha` field on `PullRequest`
- [`worktree_manager/github_vm.py`](worktree_manager/github_vm.py) — bootstrap + poll logic, `fetch_status_changed` signal, `rescan_repos()`
- [`worktree_manager/ui/github_panel.py`](worktree_manager/ui/github_panel.py) — `_ci_badge`, `_on_prs_updated`, footer bar

---

## Open Questions

None.

---

## Iteration Plan

### Iteration 0 — Walking Skeleton

**Delivers:** The My PRs list shows two-line rows (`#N  Title   ⏳ checks running` / `head → base`) with real CI status, a tracked-repos footer with live fetch progress, and a `[↺ Rescan]` button. The "← current branch" label is gone.

**Scope:**
- Add `head_sha: str = ""` field to `PullRequest` in [`worktree_manager/github_models.py`](worktree_manager/github_models.py)
- Add to [`worktree_manager/github_service.py`](worktree_manager/github_service.py):
  - `get_authenticated_user() -> str` (already exists — reuse)
  - `discover_open_pr_repos(login: str) -> set[tuple[str, str]]` — Search API, returns `{(owner, repo), …}`
  - `list_prs_for_repo(owner: str, repo: str, login: str) -> list[PullRequest]` — `GET /repos/{owner}/{repo}/pulls?state=open`, populates `head_branch`, `base_branch`, `mergeable`, `head_sha`
  - `fetch_check_runs(owner: str, repo: str, sha: str) -> list[CICheck]` — extracted from `get_pr_detail`
- Update [`worktree_manager/github_vm.py`](worktree_manager/github_vm.py):
  - Add `_known_repos: set[tuple[str, str]] = set()`, `_login: str = ""`
  - Add `fetch_status_changed = Signal(str)` signal
  - Add `rescan_repos()` — clears `_known_repos` and `_login`, triggers `refresh_prs()`
  - `refresh_prs()`: on first call (or after rescan) emit `"Scanning GitHub for repos with your open PRs…"`, call `discover_open_pr_repos`, populate `_known_repos`; then for each known repo call `list_prs_for_repo` + `fetch_check_runs` in parallel via `ThreadPoolExecutor`, emitting per-repo progress via `fetch_status_changed`; finally emit idle "Tracking: owner/repo …" string
  - New repos discovered mid-poll (PR in a repo not yet in `_known_repos`) are added to `_known_repos` automatically
- Update [`worktree_manager/ui/github_panel.py`](worktree_manager/ui/github_panel.py):
  - `_ci_badge(pr)` accepts a `PullRequest`, returns `"⏳ checks running"` / `"❌ checks failed"` / `"✅ ready to merge"` / `"✅ checks passed"` / `"– no checks"`
  - `_on_prs_updated`: two-line item text, `item.setSizeHint` for row height, remove `← current branch` logic
  - Add footer bar below `_pr_list`: `QLabel` for fetch status + `[↺ Rescan]` `QPushButton`
  - Connect `vm.fetch_status_changed` → footer label update
  - `[↺ Rescan]` calls `vm.rescan_repos()`

**Explicitly out of scope:**
- Any changes to the PR detail view or Open PR tab
- Reviews in the list fetch (lazy only)
- Comments in the list fetch (lazy only)

---

## Iteration 0 — Walking Skeleton

### Phase 0.1 — `head_sha` field on `PullRequest` + new service methods

**What it covers:** Add `head_sha` to the model, then add `discover_open_pr_repos`, `list_prs_for_repo`, and `fetch_check_runs` to `GitHubService`. Existing methods untouched.

**Files touched:**
- [`worktree_manager/github_models.py`](worktree_manager/github_models.py)
- [`worktree_manager/github_service.py`](worktree_manager/github_service.py)

**Tests (Red) — write these first:**
```python
# tests/test_github_service_list_prs.py
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
```

**Production code (Green):**

In [`worktree_manager/github_models.py`](worktree_manager/github_models.py), add `head_sha` field to `PullRequest`:
```python
head_sha: str = field(default="")
```

In [`worktree_manager/github_service.py`](worktree_manager/github_service.py), update `_pr_from_dict` to capture `head_sha`, and add three new methods:
```python
def _pr_from_dict(self, data: dict) -> PullRequest:
    return PullRequest(
        number=data["number"],
        title=data["title"],
        body=data.get("body") or "",
        html_url=data["html_url"],
        head_branch=data["head"]["ref"],
        base_branch=data["base"]["ref"],
        state=data["state"],
        draft=data.get("draft", False),
        mergeable=data.get("mergeable"),
        head_sha=data["head"].get("sha", ""),
    )

def discover_open_pr_repos(self, login: str) -> set[tuple[str, str]]:
    resp = requests.get(
        "https://api.github.com/search/issues",
        headers=self._headers,
        params={"q": f"is:pr is:open author:{login}", "per_page": 100},
    )
    if resp.status_code == 401:
        raise PermissionError("GitHub token is invalid or expired")
    resp.raise_for_status()
    repos: set[tuple[str, str]] = set()
    for item in resp.json().get("items", []):
        parts = urlparse(item["html_url"]).path.strip("/").split("/")
        if len(parts) >= 2:
            repos.add((parts[0], parts[1]))
    return repos

def list_prs_for_repo(self, owner: str, repo: str, login: str) -> list[PullRequest]:
    resp = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}/pulls",
        headers=self._headers,
        params={"state": "open", "per_page": 100},
    )
    if resp.status_code == 401:
        raise PermissionError("GitHub token is invalid or expired")
    resp.raise_for_status()
    return [
        self._pr_from_dict(item)
        for item in resp.json()
        if item.get("user", {}).get("login") == login
    ]

def fetch_check_runs(self, owner: str, repo: str, sha: str) -> list[CICheck]:
    resp = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}/check-runs",
        headers=self._headers,
        params={"per_page": 100},
    )
    if resp.status_code != 200:
        return []
    return [
        CICheck(
            name=c["name"],
            status=c["status"],
            conclusion=c.get("conclusion"),
            check_suite_id=str(c["check_suite"]["id"]) if c.get("check_suite") else None,
        )
        for c in resp.json().get("check_runs", [])
    ]
```

**Done when:** All tests in `test_github_service_list_prs.py` pass; `head_sha` field exists on `PullRequest` and defaults to `""`.

---

### Phase 0.2 — VM bootstrap + poll logic with `fetch_status_changed` signal

**What it covers:** Update `GitHubViewModel.refresh_prs` to use the new service methods: bootstrap `_known_repos` on first call via `discover_open_pr_repos`, then poll per-repo via `list_prs_for_repo` + `fetch_check_runs` in a `ThreadPoolExecutor`. Emit `fetch_status_changed` at each stage. Add `rescan_repos()`.

**Files touched:**
- [`worktree_manager/github_vm.py`](worktree_manager/github_vm.py)

**Tests (Red) — write these first:**
```python
# tests/test_github_vm_bootstrap.py
import pytest
from unittest.mock import MagicMock, patch, call
from worktree_manager.github_models import PullRequest, CICheck
from worktree_manager.github_vm import GitHubViewModel, TokenState


def _make_pr(number=1, owner="myorg", repo="myrepo", sha="abc"):
    return PullRequest(
        number=number, title=f"PR {number}", body="",
        html_url=f"https://github.com/{owner}/{repo}/pull/{number}",
        head_branch="feat", base_branch="main",
        state="open", draft=False, mergeable=True,
        head_sha=sha,
    )


@pytest.fixture
def store(tmp_path):
    from worktree_manager.config_store import ConfigStore
    s = ConfigStore(path=tmp_path / "config.json")
    s.save_github_token("ghp_test")
    return s


@pytest.fixture
def vm(store):
    with patch("worktree_manager.github_vm.GitHubService") as MockSvc:
        MockSvc.return_value = MagicMock()
        v = GitHubViewModel(store=store)
    return v


# ── bootstrap ────────────────────────────────────────────────────────────────

def test_refresh_prs_calls_discover_on_first_run(vm, qtbot):
    vm._svc.discover_open_pr_repos.return_value = {("myorg", "myrepo")}
    vm._svc.list_prs_for_repo.return_value = []
    vm._login = "me"
    vm.refresh_prs()
    vm._svc.discover_open_pr_repos.assert_called_once_with("me")


def test_refresh_prs_skips_discover_on_subsequent_runs(vm, qtbot):
    vm._known_repos = {("myorg", "myrepo")}
    vm._login = "me"
    vm._svc.list_prs_for_repo.return_value = []
    vm._svc.fetch_check_runs.return_value = []
    vm.refresh_prs()
    vm._svc.discover_open_pr_repos.assert_not_called()


def test_refresh_prs_populates_known_repos_after_bootstrap(vm, qtbot):
    vm._svc.discover_open_pr_repos.return_value = {("myorg", "api"), ("myorg", "frontend")}
    vm._svc.list_prs_for_repo.return_value = []
    vm._login = "me"
    vm.refresh_prs()
    assert ("myorg", "api") in vm._known_repos
    assert ("myorg", "frontend") in vm._known_repos


def test_refresh_prs_merges_prs_from_all_known_repos(vm, qtbot):
    vm._known_repos = {("myorg", "api"), ("myorg", "frontend")}
    vm._login = "me"
    pr1 = _make_pr(1, "myorg", "api")
    pr2 = _make_pr(2, "myorg", "frontend")
    vm._svc.list_prs_for_repo.side_effect = lambda o, r, l: [pr1] if r == "api" else [pr2]
    vm._svc.fetch_check_runs.return_value = []
    vm.refresh_prs()
    assert len(vm.prs) == 2
    assert {p.number for p in vm.prs} == {1, 2}


def test_refresh_prs_attaches_check_runs_to_each_pr(vm, qtbot):
    vm._known_repos = {("myorg", "myrepo")}
    vm._login = "me"
    pr = _make_pr(1, sha="deadbeef")
    vm._svc.list_prs_for_repo.return_value = [pr]
    checks = [CICheck("build", "completed", "success")]
    vm._svc.fetch_check_runs.return_value = checks
    vm.refresh_prs()
    assert vm.prs[0].checks == checks
    vm._svc.fetch_check_runs.assert_called_once_with("myorg", "myrepo", "deadbeef")


def test_refresh_prs_auto_adds_new_repo_discovered_via_pr(vm, qtbot):
    """A PR in a repo not yet in _known_repos gets its repo added automatically."""
    vm._known_repos = {("myorg", "api")}
    vm._login = "me"
    pr_known = _make_pr(1, "myorg", "api")
    pr_new   = _make_pr(2, "myorg", "new-repo")
    vm._svc.list_prs_for_repo.side_effect = lambda o, r, l: [pr_known] if r == "api" else []
    vm._svc.fetch_check_runs.return_value = []
    # Simulate discovering a new PR in an untracked repo via some future path:
    # The VM should add it when it encounters it during polling.
    # We test the lower-level helper directly.
    vm._add_repo_if_new("myorg", "new-repo")
    assert ("myorg", "new-repo") in vm._known_repos


# ── fetch_status_changed signal ──────────────────────────────────────────────

def test_fetch_status_changed_emits_scanning_during_bootstrap(vm, qtbot):
    vm._svc.discover_open_pr_repos.return_value = set()
    vm._login = "me"
    statuses = []
    vm.fetch_status_changed.connect(statuses.append)
    vm.refresh_prs()
    assert any("Scanning" in s for s in statuses)


def test_fetch_status_changed_emits_tracking_when_idle(vm, qtbot):
    vm._known_repos = {("myorg", "myrepo")}
    vm._login = "me"
    vm._svc.list_prs_for_repo.return_value = []
    vm._svc.fetch_check_runs.return_value = []
    statuses = []
    vm.fetch_status_changed.connect(statuses.append)
    vm.refresh_prs()
    assert any("Tracking" in s for s in statuses)


def test_fetch_status_changed_includes_repo_names_in_tracking(vm, qtbot):
    vm._known_repos = {("myorg", "api"), ("myorg", "frontend")}
    vm._login = "me"
    vm._svc.list_prs_for_repo.return_value = []
    vm._svc.fetch_check_runs.return_value = []
    statuses = []
    vm.fetch_status_changed.connect(statuses.append)
    vm.refresh_prs()
    idle = next(s for s in statuses if "Tracking" in s)
    assert "myorg/api" in idle or "myorg/frontend" in idle


def test_fetch_status_changed_emits_no_repos_when_none_tracked(vm, qtbot):
    vm._known_repos = set()
    vm._login = "me"
    vm._svc.discover_open_pr_repos.return_value = set()
    statuses = []
    vm.fetch_status_changed.connect(statuses.append)
    vm.refresh_prs()
    assert any("Tracking" in s or "No repos" in s for s in statuses)


# ── rescan_repos ─────────────────────────────────────────────────────────────

def test_rescan_repos_clears_known_repos(vm, qtbot):
    vm._known_repos = {("myorg", "api")}
    vm._login = "me"
    vm.rescan_repos()
    assert vm._known_repos == set()


def test_rescan_repos_clears_login_so_next_refresh_re_bootstraps(vm, qtbot):
    vm._known_repos = {("myorg", "api")}
    vm._login = "me"
    vm.rescan_repos()
    assert vm._login == ""


def test_rescan_repos_triggers_refresh(vm, qtbot):
    vm._known_repos = {("myorg", "api")}
    vm._login = "me"
    with patch.object(vm, "refresh_prs") as mock_refresh:
        vm.rescan_repos()
    mock_refresh.assert_called_once()
```

**Production code (Green):**

In [`worktree_manager/github_vm.py`](worktree_manager/github_vm.py):

```python
import concurrent.futures

# Add to class signals:
fetch_status_changed = Signal(str)

# Add to __init__:
self._known_repos: set[tuple[str, str]] = set()
self._login: str = ""

# Add helper:
def _add_repo_if_new(self, owner: str, repo: str) -> None:
    self._known_repos.add((owner, repo))

# Replace refresh_prs:
def refresh_prs(self) -> None:
    if self._svc is None:
        return
    self.loading_started.emit()
    try:
        # Bootstrap: resolve login + known repos on first call
        if not self._login:
            self._login = self._svc.get_authenticated_user()
        if not self._known_repos:
            self.fetch_status_changed.emit("Scanning GitHub for repos with your open PRs…")
            self._known_repos = self._svc.discover_open_pr_repos(self._login)

        if not self._known_repos:
            self.prs = []
            self._emit_pr_events(self.prs)
            self.prs_updated.emit()
            self.fetch_status_changed.emit("Tracking: no repos found")
            return

        # Poll: fetch PRs for each known repo, then check-runs in parallel
        status_parts: dict[str, str] = {f"{o}/{r}": "⏳" for o, r in self._known_repos}
        self.fetch_status_changed.emit(
            "Fetching: " + "  ".join(f"{k} {v}" for k, v in status_parts.items())
        )

        all_prs: list[PullRequest] = []

        def _fetch_repo(owner_repo: tuple[str, str]) -> list[PullRequest]:
            owner, repo = owner_repo
            prs = self._svc.list_prs_for_repo(owner, repo, self._login)
            checks_futures = {}
            with concurrent.futures.ThreadPoolExecutor() as inner:
                for pr in prs:
                    if pr.head_sha:
                        checks_futures[pr.number] = inner.submit(
                            self._svc.fetch_check_runs, owner, repo, pr.head_sha
                        )
            for pr in prs:
                if pr.number in checks_futures:
                    pr.checks = checks_futures[pr.number].result()
            return prs

        with concurrent.futures.ThreadPoolExecutor() as pool:
            futures = {pool.submit(_fetch_repo, repo): repo for repo in self._known_repos}
            for future in concurrent.futures.as_completed(futures):
                owner, repo = futures[future]
                key = f"{owner}/{repo}"
                try:
                    repo_prs = future.result()
                    all_prs.extend(repo_prs)
                    status_parts[key] = "✅"
                except PermissionError:
                    raise
                except Exception as exc:
                    log.error("fetch failed for %s/%s: %s", owner, repo, exc)
                    status_parts[key] = "❌"
                self.fetch_status_changed.emit(
                    "Fetching: " + "  ".join(f"{k} {v}" for k, v in status_parts.items())
                )

        self.prs = all_prs
        self._emit_pr_events(self.prs)
        self.prs_updated.emit()
        self.fetch_status_changed.emit(
            "Tracking: " + "  ".join(f"{o}/{r}" for o, r in sorted(self._known_repos))
        )
    except PermissionError:
        self._token_state = TokenState.EXPIRED
        self._timer.stop()
        self.token_state_changed.emit()
    except Exception as exc:
        log.error("refresh_prs: unexpected error: %s", exc, exc_info=True)
        self.refresh_error.emit(str(exc))

# Add rescan_repos:
def rescan_repos(self) -> None:
    self._known_repos = set()
    self._login = ""
    self.refresh_prs()
```

**Done when:** All tests in `test_github_vm_bootstrap.py` pass; `fetch_status_changed` emits scanning/fetching/tracking strings at the right times; `rescan_repos` clears state and triggers a fresh bootstrap.

---

### Phase 0.3 — Two-line PR list rows with `[↗ View]` button + footer bar

**What it covers:** Update `_ci_badge` to return descriptive strings. Replace the plain `QListWidgetItem` rows with custom item widgets: each row is a `QWidget` with a two-line label on the left and a `[↗ View]` button on the right. Remove the `itemActivated` double-click connection. Add a right-click context menu on each row with "↗ View details", "✓ Merge (squash)" (only when `is_ready_to_merge()`), and "⧉ Copy URL". Add the footer bar wired to `fetch_status_changed` and `[↺ Rescan]`.

**Files touched:**
- [`worktree_manager/ui/github_panel.py`](worktree_manager/ui/github_panel.py)

**Tests (Red) — write these first:**
```python
# tests/test_github_panel_pr_list_rows_qt.py
import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QLabel
from worktree_manager.github_models import PullRequest, CICheck, Review
from worktree_manager.github_vm import GitHubViewModel
from worktree_manager.ui.github_panel import GitHubPanel


def _make_pr(number=1, head="feat", base="main", checks=None, reviews=None, mergeable=True):
    return PullRequest(
        number=number, title=f"PR {number}", body="",
        html_url=f"https://github.com/myorg/myrepo/pull/{number}",
        head_branch=head, base_branch=base,
        state="open", draft=False, mergeable=mergeable,
        checks=checks or [], reviews=reviews or [],
    )


@pytest.fixture
def vm(tmp_path):
    from worktree_manager.config_store import ConfigStore
    store = ConfigStore(path=tmp_path / "config.json")
    store.save_github_token("ghp_test")
    with patch("worktree_manager.github_vm.GitHubService"):
        v = GitHubViewModel(store=store)
    return v


@pytest.fixture
def panel(vm, qtbot):
    p = GitHubPanel(vm=vm)
    qtbot.addWidget(p)
    p.show()
    return p


def _row_label_text(panel, row: int) -> str:
    """Return the text of the QLabel in a custom row widget."""
    item = panel._pr_list.item(row)
    widget = panel._pr_list.itemWidget(item)
    label = widget.findChild(QLabel)
    return label.text() if label else ""


def _row_view_btn(panel, row: int) -> QPushButton:
    item = panel._pr_list.item(row)
    widget = panel._pr_list.itemWidget(item)
    return widget.findChild(QPushButton)


# ── two-line row format ───────────────────────────────────────────────────────

def test_pr_row_label_contains_number_and_title(vm, panel, qtbot):
    vm.prs = [_make_pr(42)]
    vm.prs_updated.emit()
    text = _row_label_text(panel, 0)
    assert "#42" in text
    assert "PR 42" in text


def test_pr_row_label_contains_head_to_base(vm, panel, qtbot):
    vm.prs = [_make_pr(1, head="feature/x", base="main")]
    vm.prs_updated.emit()
    text = _row_label_text(panel, 0)
    assert "feature/x → main" in text


def test_pr_row_label_has_newline_separating_lines(vm, panel, qtbot):
    vm.prs = [_make_pr(1)]
    vm.prs_updated.emit()
    text = _row_label_text(panel, 0)
    assert "\n" in text


# ── view button ───────────────────────────────────────────────────────────────

def test_pr_row_has_view_button(vm, panel, qtbot):
    vm.prs = [_make_pr(1)]
    vm.prs_updated.emit()
    btn = _row_view_btn(panel, 0)
    assert btn is not None


def test_view_button_opens_detail(vm, panel, qtbot):
    vm.prs = [_make_pr(42)]
    vm.prs_updated.emit()
    with patch.object(vm, "select_pr") as mock_select:
        _row_view_btn(panel, 0).click()
    mock_select.assert_called_once_with(42)


def test_multiple_rows_view_buttons_call_correct_pr(vm, panel, qtbot):
    vm.prs = [_make_pr(10), _make_pr(20)]
    vm.prs_updated.emit()
    with patch.object(vm, "select_pr") as mock_select:
        _row_view_btn(panel, 1).click()
    mock_select.assert_called_once_with(20)


# ── descriptive status badge ─────────────────────────────────────────────────

def test_badge_shows_checks_running(vm, panel, qtbot):
    vm.prs = [_make_pr(1, checks=[CICheck("build", "in_progress", None)])]
    vm.prs_updated.emit()
    assert "checks running" in _row_label_text(panel, 0)


def test_badge_shows_checks_failed(vm, panel, qtbot):
    vm.prs = [_make_pr(1, checks=[CICheck("build", "completed", "failure")])]
    vm.prs_updated.emit()
    assert "checks failed" in _row_label_text(panel, 0)


def test_badge_shows_ready_to_merge(vm, panel, qtbot):
    vm.prs = [_make_pr(
        1,
        checks=[CICheck("build", "completed", "success")],
        reviews=[Review("alice", "APPROVED")],
        mergeable=True,
    )]
    vm.prs_updated.emit()
    assert "ready to merge" in _row_label_text(panel, 0)


def test_badge_shows_checks_passed_without_approval(vm, panel, qtbot):
    vm.prs = [_make_pr(1, checks=[CICheck("build", "completed", "success")], reviews=[])]
    vm.prs_updated.emit()
    assert "checks passed" in _row_label_text(panel, 0)


def test_badge_shows_no_checks(vm, panel, qtbot):
    vm.prs = [_make_pr(1, checks=[])]
    vm.prs_updated.emit()
    assert "no checks" in _row_label_text(panel, 0)


# ── current branch label removed ─────────────────────────────────────────────

def test_current_branch_label_absent(vm, panel, qtbot):
    vm.prs = [_make_pr(1, head="main"), _make_pr(2, head="feat")]
    vm.prs_updated.emit()
    for i in range(panel._pr_list.count()):
        assert "current branch" not in _row_label_text(panel, i)


# ── footer bar ───────────────────────────────────────────────────────────────

def test_footer_label_exists(panel):
    assert hasattr(panel, "_fetch_status_label")


def test_rescan_button_exists(panel):
    assert hasattr(panel, "_rescan_btn")


def test_fetch_status_signal_updates_footer_label(vm, panel, qtbot):
    vm.fetch_status_changed.emit("Tracking: myorg/api")
    assert "myorg/api" in panel._fetch_status_label.text()


def test_rescan_button_calls_vm_rescan(vm, panel, qtbot):
    with patch.object(vm, "rescan_repos") as mock_rescan:
        panel._rescan_btn.click()
    mock_rescan.assert_called_once()


# ── right-click context menu ──────────────────────────────────────────────────

def test_context_menu_view_action_calls_select_pr(vm, panel, qtbot):
    vm.prs = [_make_pr(42)]
    vm.prs_updated.emit()
    with patch.object(vm, "select_pr") as mock_select, \
         patch("worktree_manager.ui.github_panel.QMenu") as MockMenu:
        mock_menu = MagicMock()
        MockMenu.return_value = mock_menu
        view_action = MagicMock()
        view_action.text.return_value = "↗ View details"
        mock_menu.exec.return_value = view_action
        mock_menu.addAction.return_value = view_action
        panel._show_pr_context_menu(42, panel._pr_list.item(0))
    mock_select.assert_called_once_with(42)


def test_context_menu_merge_action_absent_when_not_ready(vm, panel, qtbot):
    pr = _make_pr(1, checks=[CICheck("build", "completed", "failure")])
    vm.prs = [pr]
    vm.prs_updated.emit()
    actions_added = []
    with patch("worktree_manager.ui.github_panel.QMenu") as MockMenu:
        mock_menu = MagicMock()
        MockMenu.return_value = mock_menu
        mock_menu.exec.return_value = None
        mock_menu.addAction.side_effect = lambda text: actions_added.append(text)
        panel._show_pr_context_menu(1, panel._pr_list.item(0))
    assert not any("Merge" in a for a in actions_added)


def test_context_menu_merge_action_present_when_ready(vm, panel, qtbot):
    pr = _make_pr(
        1,
        checks=[CICheck("build", "completed", "success")],
        reviews=[Review("alice", "APPROVED")],
        mergeable=True,
    )
    vm.prs = [pr]
    vm.prs_updated.emit()
    actions_added = []
    with patch("worktree_manager.ui.github_panel.QMenu") as MockMenu:
        mock_menu = MagicMock()
        MockMenu.return_value = mock_menu
        mock_menu.exec.return_value = None
        mock_menu.addAction.side_effect = lambda text: actions_added.append(text)
        panel._show_pr_context_menu(1, panel._pr_list.item(0))
    assert any("Merge" in a for a in actions_added)


def test_context_menu_merge_action_calls_vm_merge(vm, panel, qtbot):
    pr = _make_pr(
        42,
        checks=[CICheck("build", "completed", "success")],
        reviews=[Review("alice", "APPROVED")],
        mergeable=True,
    )
    vm.prs = [pr]
    vm.prs_updated.emit()
    with patch.object(vm, "merge_pr") as mock_merge, \
         patch("worktree_manager.ui.github_panel.QMenu") as MockMenu:
        mock_menu = MagicMock()
        MockMenu.return_value = mock_menu
        merge_action = MagicMock()
        merge_action.text.return_value = "✓ Merge (squash)"
        mock_menu.exec.return_value = merge_action
        mock_menu.addAction.return_value = merge_action
        panel._show_pr_context_menu(42, panel._pr_list.item(0))
    mock_merge.assert_called_once_with(42, squash=True)


def test_context_menu_copy_url_writes_clipboard(vm, panel, qtbot):
    vm.prs = [_make_pr(42)]
    vm.prs_updated.emit()
    with patch("worktree_manager.ui.github_panel.QMenu") as MockMenu, \
         patch("worktree_manager.ui.github_panel.QApplication") as MockApp:
        mock_menu = MagicMock()
        MockMenu.return_value = mock_menu
        copy_action = MagicMock()
        copy_action.text.return_value = "⧉ Copy URL"
        mock_menu.exec.return_value = copy_action
        mock_menu.addAction.return_value = copy_action
        panel._show_pr_context_menu(42, panel._pr_list.item(0))
    MockApp.clipboard.return_value.setText.assert_called()
```

**Production code (Green):**

In [`worktree_manager/ui/github_panel.py`](worktree_manager/ui/github_panel.py):

```python
# Replace _ci_badge:
def _ci_badge(self, pr: PullRequest) -> str:
    s = pr.ci_status()
    if s == "running":
        return "⏳ checks running"
    if s == "failed":
        return "❌ checks failed"
    if s == "passed":
        return "✅ ready to merge" if pr.is_ready_to_merge() else "✅ checks passed"
    return "– no checks"

# Replace _on_prs_updated:
def _on_prs_updated(self):
    self._loading_label.hide()
    self._pr_list.show()
    self._pr_error_label.hide()
    self._pr_list.clear()
    for pr in self._vm.prs:
        badge = self._ci_badge(pr)
        unread = self._vm.unread_comment_count(pr.number)
        badge_prefix = f"🔴 {unread} new  " if unread > 0 else ""
        label_text = f"#{pr.number}  {pr.title}   {badge_prefix}{badge}\n{pr.head_branch} → {pr.base_branch}"

        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(8, 4, 8, 4)
        lbl = QLabel(label_text)
        lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        row_layout.addWidget(lbl, 1)
        view_btn = QPushButton("↗ View")
        view_btn.setFixedWidth(64)
        view_btn.clicked.connect(lambda checked=False, n=pr.number: self._vm.select_pr(n))
        row_layout.addWidget(view_btn)

        item = QListWidgetItem()
        item.setData(Qt.UserRole, pr.number)
        item.setSizeHint(row_widget.sizeHint().__class__(0, 48))
        self._pr_list.addItem(item)
        self._pr_list.setItemWidget(item, row_widget)

    self._check_open_pr_tab()

# Remove itemActivated connection from __init__; replace with nothing
# (the View button is the sole entry point to detail)

# In __init__, after pr_list_layout.addWidget(self._pr_list), add footer:
footer_layout = QHBoxLayout()
footer_layout.setContentsMargins(8, 4, 8, 4)
self._fetch_status_label = QLabel("Scanning GitHub for repos with your open PRs…")
self._fetch_status_label.setStyleSheet("color: gray; font-size: 11px;")
self._fetch_status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
footer_layout.addWidget(self._fetch_status_label, 1)
self._rescan_btn = QPushButton("↺ Rescan")
self._rescan_btn.setFixedWidth(80)
self._rescan_btn.clicked.connect(self._vm.rescan_repos)
footer_layout.addWidget(self._rescan_btn)
pr_list_layout.addLayout(footer_layout)

# In signal connections, add:
vm.fetch_status_changed.connect(self._fetch_status_label.setText)

# Add context menu method:
def _show_pr_context_menu(self, pr_number: int, item: QListWidgetItem) -> None:
    from PySide6.QtWidgets import QMenu
    pr = next((p for p in self._vm.prs if p.number == pr_number), None)
    if pr is None:
        return
    menu = QMenu(self)
    menu.addAction("↗ View details")
    if pr.is_ready_to_merge():
        menu.addAction("✓ Merge (squash)")
    menu.addAction("⧉ Copy URL")
    action = menu.exec(QCursor.pos())
    if action is None:
        return
    text = action.text()
    if text == "↗ View details":
        self._vm.select_pr(pr_number)
    elif text == "✓ Merge (squash)":
        self._vm.merge_pr(pr_number, squash=True)
    elif text == "⧉ Copy URL":
        QApplication.clipboard().setText(pr.html_url)

# In _on_prs_updated, enable context menu on the list and wire per-row:
# Set context menu policy on the list widget in __init__:
self._pr_list.setContextMenuPolicy(Qt.CustomContextMenu)
self._pr_list.customContextMenuRequested.connect(self._on_pr_list_context_menu)

# Add handler:
def _on_pr_list_context_menu(self, pos) -> None:
    item = self._pr_list.itemAt(pos)
    if item is None:
        return
    pr_number = item.data(Qt.UserRole)
    self._show_pr_context_menu(pr_number, item)
```

Also add `QCursor` to imports: `from PySide6.QtGui import QDesktopServices, QCursor`
And add `QMenu` to the `QWidgets` import block.

**Done when:** Each PR row has a two-line label and a `[↗ View]` button; clicking View opens the detail; right-clicking shows a context menu with View, conditionally Merge, and Copy URL; no "current branch" text; footer label and Rescan button work correctly.

---

### Phase 0.4 — No-refetch detail view: reuse list PR, supplement reviews + comments only

**What it covers:** `select_pr` in [`worktree_manager/github_vm.py`](worktree_manager/github_vm.py) currently calls `get_pr_detail` which re-fetches the full PR including branch info and checks. Since the list fetch already has that data, update `select_pr` to pass the already-fetched PR to a slimmed-down `get_pr_detail` that only fetches reviews + comments. The detail view opens instantly with no spinner.

**Files touched:**
- [`worktree_manager/github_service.py`](worktree_manager/github_service.py)
- [`worktree_manager/github_vm.py`](worktree_manager/github_vm.py)

**Tests (Red) — write these first:**
```python
# tests/test_github_vm_no_refetch.py
import pytest
from unittest.mock import MagicMock, patch, call
from worktree_manager.github_models import PullRequest, CICheck, Review, PRComment
from worktree_manager.github_vm import GitHubViewModel


def _make_pr(number=1, sha="abc"):
    return PullRequest(
        number=number, title="My PR", body="",
        html_url=f"https://github.com/myorg/myrepo/pull/{number}",
        head_branch="feat", base_branch="main",
        state="open", draft=False, mergeable=True,
        head_sha=sha,
        checks=[CICheck("build", "completed", "success")],
    )


@pytest.fixture
def store(tmp_path):
    from worktree_manager.config_store import ConfigStore
    s = ConfigStore(path=tmp_path / "config.json")
    s.save_github_token("ghp_test")
    return s


@pytest.fixture
def vm(store):
    with patch("worktree_manager.github_vm.GitHubService") as MockSvc:
        MockSvc.return_value = MagicMock()
        v = GitHubViewModel(store=store)
    return v


def test_select_pr_uses_cached_pr_from_list(vm, qtbot):
    pr = _make_pr(42)
    vm.prs = [pr]
    vm._svc.get_pr_detail.return_value = pr
    with qtbot.waitSignal(vm.pr_detail_updated, timeout=1000):
        vm.select_pr(42)
    # get_pr_detail should be called with the cached pr object, not fetching from scratch
    call_args = vm._svc.get_pr_detail.call_args
    assert call_args[1]["pr"] is pr or call_args[0][1] is pr


def test_select_pr_does_not_refetch_checks(vm, qtbot):
    """get_pr_detail is called but must not re-call fetch_check_runs separately."""
    pr = _make_pr(42)
    vm.prs = [pr]
    vm._svc.get_pr_detail.return_value = pr
    vm.select_pr(42)
    vm._svc.fetch_check_runs.assert_not_called()


def test_select_pr_detail_preserves_checks_from_list(vm, qtbot):
    checks = [CICheck("build", "completed", "success")]
    pr = _make_pr(42)
    pr.checks = checks
    vm.prs = [pr]
    # get_pr_detail returns a PR with reviews/comments supplemented but same checks
    supplemented = _make_pr(42)
    supplemented.checks = checks
    supplemented.reviews = [Review("alice", "APPROVED")]
    vm._svc.get_pr_detail.return_value = supplemented
    with qtbot.waitSignal(vm.pr_detail_updated, timeout=1000):
        vm.select_pr(42)
    assert vm.selected_pr.checks == checks


# tests/test_github_service_detail_no_refetch.py
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
    assert detail.checks == pr.checks  # preserved from cached pr
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
```

**Production code (Green):**

In [`worktree_manager/github_service.py`](worktree_manager/github_service.py), update `get_pr_detail` to skip the PR + check-runs fetch when the passed `pr` already has a `head_sha`:
```python
def get_pr_detail(self, pr_number: int, pr: PullRequest) -> PullRequest:
    base = self._base_for_pr(pr)

    if pr.head_sha:
        # PR data + checks already fetched by list poll — only supplement reviews + comments
        detail = pr
    else:
        # Fallback: full fetch (e.g. PR created before bootstrap ran)
        pr_resp = requests.get(f"{base}/pulls/{pr_number}", headers=self._headers)
        pr_resp.raise_for_status()
        detail = self._pr_from_dict(pr_resp.json())
        sha = pr_resp.json()["head"]["sha"]
        checks_resp = requests.get(
            f"{base}/commits/{sha}/check-runs",
            headers=self._headers,
            params={"per_page": 100},
        )
        if checks_resp.status_code == 200:
            detail.checks = [
                CICheck(
                    name=c["name"],
                    status=c["status"],
                    conclusion=c.get("conclusion"),
                    check_suite_id=str(c["check_suite"]["id"]) if c.get("check_suite") else None,
                )
                for c in checks_resp.json().get("check_runs", [])
            ]

    reviews_resp = requests.get(f"{base}/pulls/{pr_number}/reviews", headers=self._headers)
    if reviews_resp.status_code == 200:
        detail.reviews = [
            Review(author=r["user"]["login"], state=r["state"])
            for r in reviews_resp.json()
        ]

    comments_resp = requests.get(
        f"{base}/issues/{pr_number}/comments",
        headers=self._headers,
        params={"per_page": 100},
    )
    if comments_resp.status_code == 200:
        detail.comments = [
            PRComment(
                id=c["id"],
                author=c["user"]["login"],
                body=c["body"],
                created_at=c["created_at"],
            )
            for c in comments_resp.json()
        ]

    return detail
```

**Done when:** `select_pr` passes the cached PR to `get_pr_detail`; only 2 API calls are made when `head_sha` is present; detail view opens with checks already populated and no re-fetch delay.

---

## ✋ Manual Testing Gate — Iteration 0

> STOP. Do not proceed until every item below is checked off by the user.

- [ ] Launch the app and open the Pull Requests panel — footer shows "Scanning GitHub for repos with your open PRs…" briefly, then transitions to "Tracking: owner/repo …" listing the repos where you have open PRs
- [ ] The PR list shows two-line rows: first line has `#N  Title   ⏳ checks running` (or appropriate badge), second line has `head → base`
- [ ] A PR with a failed CI check shows `❌ checks failed` in the badge
- [ ] A PR with all checks passing but no approval shows `✅ checks passed`
- [ ] A PR with all checks passing and an approval shows `✅ ready to merge`
- [ ] A PR with no checks at all shows `– no checks`
- [ ] No row has a "← current branch" label
- [ ] Each row has a `[↗ View]` button — clicking it opens the PR detail immediately with no loading delay (no re-fetch spinner)
- [ ] PR detail shows checks already populated (from the list fetch), plus reviews and comments loaded on open
- [ ] Right-click a PR row — context menu appears with "↗ View details" and "⧉ Copy URL"
- [ ] Right-click a PR that is ready to merge — "✓ Merge (squash)" also appears in the menu
- [ ] Right-click a PR with failed checks — "✓ Merge (squash)" does NOT appear
- [ ] Click "✓ Merge (squash)" from context menu on a ready PR — merge executes, PR disappears from list
- [ ] Click "⧉ Copy URL" from context menu — PR URL is in clipboard
- [ ] Click `[↺ Rescan]` — footer briefly shows "Scanning GitHub for repos with your open PRs…" then returns to "Tracking: …" with the same or updated repo list
- [ ] During a poll, the footer briefly shows "Fetching: owner/repo ⏳…" with per-repo ticks updating to ✅ as each completes, then returns to "Tracking: …"
- [ ] `← Back` from detail view returns to the updated two-line list

**How to confirm:** Run the app, perform each action above, and check off each item manually.
Reply "Iteration 0 confirmed" (or describe any failures) before I write the plan for Iteration 1.
