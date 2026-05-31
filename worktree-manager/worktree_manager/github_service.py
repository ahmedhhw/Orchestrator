import logging
import subprocess
from urllib.parse import urlparse

import requests

from worktree_manager.github_models import CICheck, PRComment, PullRequest, Review

log = logging.getLogger(__name__)


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
        )

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

    def _base_for_pr(self, pr: PullRequest) -> str:
        parts = urlparse(pr.html_url).path.strip("/").split("/")
        owner, repo = parts[0], parts[1]
        return f"https://api.github.com/repos/{owner}/{repo}"

    def get_pr_detail(self, pr_number: int, pr: PullRequest) -> PullRequest:
        base = self._base_for_pr(pr)
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

    def rerun_failed_checks(self, check_suite_id: str, pr: "PullRequest") -> None:
        base = self._base_for_pr(pr)
        resp = requests.post(
            f"{base}/check-suites/{check_suite_id}/rerequest",
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
