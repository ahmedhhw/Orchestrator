import logging
import re
import subprocess
from urllib.parse import urlparse

import requests

from worktree_manager.github_models import CICheck, PRComment, PullRequest, Review

log = logging.getLogger(__name__)

GRAPHQL_QUERY = """
{
  viewer { login }
  search(query: "is:pr is:open author:@me", type: ISSUE, first: 100) {
    nodes {
      ... on PullRequest {
        number
        title
        body
        url
        state
        isDraft
        headRefName
        baseRefName
        headRefOid
        mergeable
        mergeStateStatus
        repository { nameWithOwner }
        reviews(first: 50) {
          nodes {
            author { login }
            state
          }
        }
        comments(first: 100) {
          nodes {
            databaseId
            author { login }
            body
            createdAt
          }
        }
        commits(last: 1) {
          nodes {
            commit {
              statusCheckRollup {
                contexts(first: 100) {
                  nodes {
                    __typename
                    ... on CheckRun {
                      name
                      status
                      conclusion
                      checkSuite {
                        databaseId
                        workflowRun {
                          databaseId
                        }
                      }
                    }
                    ... on StatusContext {
                      context
                      state
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
  rateLimit {
    cost
    remaining
  }
}
"""

_MERGEABLE_MAP = {
    "MERGEABLE": True,
    "CONFLICTING": False,
    "UNKNOWN": None,
}

_STATUS_CONTEXT_CONCLUSION_MAP = {
    "SUCCESS": "success",
    "FAILURE": "failure",
    "ERROR": "failure",
    "PENDING": None,
    "EXPECTED": None,
}


def _pr_from_graphql_node(node: dict) -> "PullRequest":
    """Map a single GraphQL PullRequest node dict into a PullRequest model object."""
    # Parse owner/repo from repository.nameWithOwner
    name_with_owner = node["repository"]["nameWithOwner"]
    owner, repo = name_with_owner.split("/", 1)

    # Build CI checks from the statusCheckRollup contexts
    checks: list[CICheck] = []
    commits = node.get("commits", {}).get("nodes", [])
    if commits:
        rollup = commits[0].get("commit", {}).get("statusCheckRollup")
        if rollup:
            for ctx in rollup.get("contexts", {}).get("nodes", []):
                typename = ctx.get("__typename")
                if typename == "CheckRun":
                    suite = ctx.get("checkSuite")
                    check_suite_id = str(suite["databaseId"]) if suite else None
                    wr = suite.get("workflowRun") if suite else None
                    run_id = str(wr["databaseId"]) if wr else None
                    checks.append(
                        CICheck(
                            name=ctx["name"],
                            status=ctx["status"].lower(),
                            conclusion=(ctx["conclusion"].lower() if ctx.get("conclusion") else None),
                            check_suite_id=check_suite_id,
                            run_id=run_id,
                        )
                    )
                elif typename == "StatusContext":
                    checks.append(
                        CICheck(
                            name=ctx["context"],
                            status="completed",
                            conclusion=_STATUS_CONTEXT_CONCLUSION_MAP.get(ctx.get("state")),
                            check_suite_id=None,
                            run_id=None,
                        )
                    )

    # Reviews — keep state UPPERCASE (model compares == "APPROVED" etc.)
    reviews = [
        Review(author=r["author"]["login"], state=r["state"])
        for r in node.get("reviews", {}).get("nodes", [])
    ]

    # Comments
    comments = [
        PRComment(
            id=c["databaseId"],
            author=c["author"]["login"],
            body=c["body"],
            created_at=c["createdAt"],
        )
        for c in node.get("comments", {}).get("nodes", [])
    ]

    mergeable_raw = node.get("mergeable", "UNKNOWN")
    mergeable = _MERGEABLE_MAP.get(mergeable_raw)

    merge_state_status_raw = node.get("mergeStateStatus", "")
    mergeable_state = merge_state_status_raw.lower() if merge_state_status_raw else ""

    return PullRequest(
        number=node["number"],
        title=node["title"],
        body=node.get("body") or "",
        html_url=node["url"],
        head_branch=node["headRefName"],
        base_branch=node["baseRefName"],
        head_sha=node["headRefOid"],
        state=node["state"].lower(),
        draft=node["isDraft"],
        mergeable=mergeable,
        mergeable_state=mergeable_state,
        owner=owner,
        repo=repo,
        checks=checks,
        reviews=reviews,
        comments=comments,
    )


class GitHubService:
    def __init__(self, token: str):
        self.token = token
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        log.debug("GitHubService init")

    def get_authenticated_user(self) -> str:
        resp = requests.get("https://api.github.com/user", headers=self._headers)
        if resp.status_code == 401:
            raise PermissionError("GitHub token is invalid or expired")
        resp.raise_for_status()
        return resp.json()["login"]

    def fetch_all_open_prs(self) -> list[PullRequest]:
        """Fetch all open PRs authored by the viewer via a single GraphQL request.

        Returns a list of fully-populated PullRequest objects including checks,
        reviews, comments, and mergeability data.

        Raises:
            PermissionError: on HTTP 401.
            RuntimeError:    if the GraphQL response contains errors.
        """
        resp = requests.post(
            "https://api.github.com/graphql",
            headers=self._headers,
            json={"query": GRAPHQL_QUERY},
        )
        if resp.status_code == 401:
            raise PermissionError("GitHub token is invalid or expired")
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            raise RuntimeError(data["errors"][0]["message"])
        rate = data["data"].get("rateLimit", {})
        log.debug("fetch_all_open_prs: GraphQL cost=%s remaining=%s",
                  rate.get("cost"), rate.get("remaining"))
        nodes = data["data"]["search"]["nodes"]
        return [_pr_from_graphql_node(n) for n in nodes if n]

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
            mergeable_state=data.get("mergeable_state", "") or "",
            head_sha=data["head"].get("sha", ""),
        )

    def discover_open_prs(self, login: str) -> list[tuple[str, str, int]]:
        resp = requests.get(
            "https://api.github.com/search/issues",
            headers=self._headers,
            params={"q": f"is:pr is:open author:{login}", "per_page": 100},
        )
        if resp.status_code == 401:
            raise PermissionError("GitHub token is invalid or expired")
        resp.raise_for_status()
        out: list[tuple[str, str, int]] = []
        for item in resp.json().get("items", []):
            parts = urlparse(item["html_url"]).path.strip("/").split("/")
            if len(parts) >= 4:
                out.append((parts[0], parts[1], int(item["number"])))
        return out

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

    def fetch_mergeable(self, owner: str, repo: str, pr_number: int) -> bool | None:
        resp = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}",
            headers=self._headers,
        )
        resp.raise_for_status()
        return resp.json().get("mergeable")

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

    @staticmethod
    def _parse_run_id(details_url: str) -> str | None:
        """Extract workflow run id from a GitHub Actions details URL."""
        m = re.search(r"/actions/runs/(\d+)", details_url or "")
        return m.group(1) if m else None

    def _base_for_pr(self, pr: PullRequest) -> str:
        parts = urlparse(pr.html_url).path.strip("/").split("/")
        owner, repo = parts[0], parts[1]
        return f"https://api.github.com/repos/{owner}/{repo}"

    def get_pr_detail(self, pr_number: int, pr: PullRequest) -> PullRequest:
        base = self._base_for_pr(pr)

        pr_resp = requests.get(f"{base}/pulls/{pr_number}", headers=self._headers)
        pr_resp.raise_for_status()
        pr_data = pr_resp.json()
        log.debug("get_pr_detail #%d: API returned mergeable=%r", pr_number, pr_data.get("mergeable"))

        if pr.head_sha:
            detail = pr
            detail.mergeable = pr_data.get("mergeable")
            detail.mergeable_state = pr_data.get("mergeable_state", "") or ""
        else:
            detail = self._pr_from_dict(pr_data)
            sha = pr_data["head"]["sha"]
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
                        run_id=GitHubService._parse_run_id(c.get("details_url") or ""),
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

    def create_pull_request(self, title: str, body: str, base: str, branch: str, draft: bool, repo_base_url: str) -> PullRequest:
        resp = requests.post(
            f"{repo_base_url}/pulls",
            headers=self._headers,
            json={"title": title, "body": body, "base": base, "draft": draft,
                  "head": branch},
        )
        if resp.status_code not in (200, 201):
            msg = resp.json().get("message", f"HTTP {resp.status_code}")
            raise RuntimeError(msg)
        return self._pr_from_dict(resp.json())

    def rerun_all_checks(self, check_suite_id: str, pr: "PullRequest") -> None:
        base = self._base_for_pr(pr)
        resp = requests.post(
            f"{base}/check-suites/{check_suite_id}/rerequest",
            headers=self._headers,
        )
        resp.raise_for_status()

    def rerun_failed_jobs(self, run_id: str, pr: "PullRequest") -> None:
        base = self._base_for_pr(pr)
        resp = requests.post(
            f"{base}/actions/runs/{run_id}/rerun-failed-jobs",
            headers=self._headers,
        )
        resp.raise_for_status()

    def rerun_workflow(self, run_id: str, pr: "PullRequest") -> None:
        base = self._base_for_pr(pr)
        resp = requests.post(
            f"{base}/actions/runs/{run_id}/rerun",
            headers=self._headers,
        )
        resp.raise_for_status()

    def merge_pr(self, pr: PullRequest, squash: bool = True) -> None:
        base = self._base_for_pr(pr)
        resp = requests.put(
            f"{base}/pulls/{pr.number}/merge",
            headers=self._headers,
            json={"merge_method": "squash" if squash else "merge"},
        )
        if not resp.ok:
            msg = resp.json().get("message", f"HTTP {resp.status_code}")
            raise RuntimeError(msg)

    def push_branch(self, branch: str, repo_path: str) -> None:
        result = subprocess.run(
            ["git", "push", "-u", "origin", branch],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git push failed: {result.stderr}")
