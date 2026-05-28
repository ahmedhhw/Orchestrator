import os
import subprocess
import time
from dataclasses import dataclass

from worktree_manager.models import WorktreeModel


@dataclass
class UpstreamStatus:
    has_upstream: bool
    ahead: int
    behind: int


@dataclass
class PullOutcome:
    status: str   # "up_to_date" | "pulled" | "non_ff" | "dirty" | "error"
    new_commits: int = 0
    error: str | None = None


@dataclass
class UpdateOutcome:
    status: str   # "up_to_date" | "pulled" | "non_ff" | "error"
    error: str | None = None


class GitService:
    def _run(self, cmd: list, cwd: str = None) -> str:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, check=True
        )
        return result.stdout

    def is_valid_repo(self, path: str) -> bool:
        return os.path.isdir(os.path.join(path, ".git"))

    def last_commit_ts(self, repo_path: str, branch: str) -> int:
        try:
            out = self._run(
                ["git", "log", "-1", "--format=%ct", branch], cwd=repo_path
            ).strip()
            return int(out) if out else 0
        except subprocess.CalledProcessError:
            return 0

    def is_merged(self, repo_path: str, branch: str, main_branch: str) -> bool:
        out = self._run(
            ["git", "branch", "--merged", main_branch], cwd=repo_path
        )
        merged = [b.strip().lstrip("* ") for b in out.splitlines()]
        return branch in merged

    def list_local_branches(self, repo_path: str) -> list:
        out = self._run(["git", "branch", "--format=%(refname:short)"], cwd=repo_path)
        return [b for b in out.splitlines() if b]

    def list_worktrees(self, repo_path: str, stale_days: int = 30) -> list:
        out = self._run(["git", "worktree", "list", "--porcelain"], cwd=repo_path)
        blocks = [b.strip() for b in out.strip().split("\n\n") if b.strip()]
        stale_threshold = int(time.time()) - stale_days * 86400
        worktrees = []
        for i, block in enumerate(blocks):
            lines = {
                k: v
                for k, v in (
                    line.split(" ", 1) for line in block.splitlines() if " " in line
                )
            }
            path = lines.get("worktree", "")
            branch_ref = lines.get("branch", "")
            branch = branch_ref.removeprefix("refs/heads/") if branch_ref else "(detached)"
            is_main = i == 0
            ts = self.last_commit_ts(repo_path, branch)
            merged = self.is_merged(repo_path, branch, "main") if not is_main else False
            stale = ts > 0 and ts < stale_threshold
            worktrees.append(WorktreeModel(
                path=path,
                branch=branch,
                is_main=is_main,
                last_commit_ts=ts,
                is_merged=merged,
                is_stale=stale,
            ))
        return worktrees

    def create_worktree(
        self, repo_path: str, worktree_path: str, branch: str, base_branch: str
    ) -> None:
        self._run(
            ["git", "worktree", "add", "-b", branch, worktree_path, base_branch],
            cwd=repo_path,
        )

    def delete_worktree(self, repo_path: str, worktree_path: str) -> None:
        self._run(
            ["git", "worktree", "remove", "--force", worktree_path],
            cwd=repo_path,
        )

    def delete_branch(self, repo_path: str, branch: str) -> None:
        self._run(["git", "branch", "-D", branch], cwd=repo_path)

    def has_uncommitted_changes(self, worktree_path: str) -> bool:
        try:
            out = self._run(["git", "status", "--porcelain"], cwd=worktree_path)
            return bool(out.strip())
        except subprocess.CalledProcessError:
            return False

    def checked_out_branch(self, worktree_path: str) -> str:
        try:
            result = self._run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=worktree_path
            ).strip()
            return "(detached)" if result == "HEAD" else result
        except subprocess.CalledProcessError:
            return "(detached)"

    def checkout_branch(self, worktree_path: str, branch: str) -> None:
        self._run(["git", "checkout", branch], cwd=worktree_path)

    def checkout_new_branch(self, worktree_path: str, new_branch: str, base_branch: str) -> None:
        if base_branch == "HEAD":
            self._run(["git", "checkout", "-b", new_branch], cwd=worktree_path)
        else:
            self._run(["git", "checkout", "-b", new_branch, base_branch], cwd=worktree_path)

    def create_worktree_from_existing(
        self, repo_path: str, worktree_path: str, branch: str
    ) -> None:
        self._run(
            ["git", "worktree", "add", worktree_path, branch],
            cwd=repo_path,
        )

    def repo_root(self, worktree_path: str) -> str:
        return self._run(
            ["git", "rev-parse", "--show-toplevel"], cwd=worktree_path
        ).strip()

    def list_feature_branches(self, repo_path: str) -> list[str]:
        out = self._run(["git", "branch", "--format=%(refname:short)"], cwd=repo_path)
        return [b for b in out.splitlines() if b.startswith("feature/")]

    def is_merged_into_any(
        self, repo_path: str, branch: str, targets: list[str]
    ) -> tuple[bool, str | None]:
        for target in targets:
            out = self._run(["git", "branch", "--merged", target], cwd=repo_path)
            merged = [b.strip().lstrip("* ") for b in out.splitlines()]
            if branch in merged:
                return True, target
        return False, None

    def build_merged_map(self, repo_path: str, targets: list[str]) -> dict[str, str]:
        target_set = set(targets)
        result: dict[str, str] = {}
        for target in targets:
            out = self._run(["git", "branch", "--merged", target], cwd=repo_path)
            for line in out.splitlines():
                branch = line.strip().lstrip("* ")
                if branch and branch not in result and branch not in target_set:
                    result[branch] = target
        return result

    # ── sync methods ──────────────────────────────────────────────────────────

    def fetch(self, repo_path: str) -> str | None:
        """Fetch from origin. Returns None on success, error string on failure."""
        try:
            self._run(["git", "fetch", "origin"], cwd=repo_path)
            return None
        except subprocess.CalledProcessError as e:
            return e.stderr or str(e)

    def upstream_status(self, repo_path: str, branch: str) -> UpstreamStatus:
        """Return ahead/behind counts vs the tracking branch, or has_upstream=False."""
        try:
            out = self._run(
                ["git", "rev-list", "--left-right", "--count",
                 f"{branch}...@{{u}}"],
                cwd=repo_path,
            ).strip()
            ahead_str, behind_str = out.split()
            return UpstreamStatus(
                has_upstream=True, ahead=int(ahead_str), behind=int(behind_str)
            )
        except (subprocess.CalledProcessError, ValueError):
            return UpstreamStatus(has_upstream=False, ahead=0, behind=0)

    def list_feature_and_main_branches(self, repo_path: str) -> list[str]:
        """Return local branches that are main or start with feature/."""
        out = self._run(["git", "branch", "--format=%(refname:short)"], cwd=repo_path)
        return [
            b for b in out.splitlines()
            if b == "main" or b.startswith("feature/")
        ]

    def worktree_for_branch(self, repo_path: str, branch: str) -> str | None:
        """Return the worktree path that has branch checked out, or None."""
        out = self._run(["git", "worktree", "list", "--porcelain"], cwd=repo_path)
        blocks = [b.strip() for b in out.strip().split("\n\n") if b.strip()]
        for block in blocks:
            lines = {
                k: v
                for k, v in (
                    line.split(" ", 1) for line in block.splitlines() if " " in line
                )
            }
            branch_ref = lines.get("branch", "")
            wt_branch = branch_ref.removeprefix("refs/heads/")
            if wt_branch == branch:
                return lines.get("worktree")
        return None

    def pull_ff_only(self, worktree_path: str) -> PullOutcome:
        """Run git pull --ff-only in a worktree. Returns a PullOutcome."""
        try:
            out = self._run(["git", "pull", "--ff-only"], cwd=worktree_path)
            if "Already up to date" in out or "Already up-to-date" in out:
                return PullOutcome(status="up_to_date", new_commits=0)
            return PullOutcome(status="pulled", new_commits=0)
        except subprocess.CalledProcessError as e:
            raw_stderr = e.stderr or str(e)
            stderr = raw_stderr.lower()
            if "local changes" in stderr or "overwritten" in stderr:
                return PullOutcome(status="dirty", error=raw_stderr)
            return PullOutcome(status="non_ff", error=raw_stderr)

    def update_ref_from_remote(self, repo_path: str, branch: str) -> UpdateOutcome:
        """Fast-forward a local branch from origin without checking it out."""
        try:
            self._run(
                ["git", "fetch", "origin", f"{branch}:{branch}"], cwd=repo_path
            )
            return UpdateOutcome(status="pulled")
        except subprocess.CalledProcessError as e:
            raw_stderr = e.stderr or str(e)
            stderr = raw_stderr.lower()
            if "non-fast-forward" in stderr or "rejected" in stderr:
                return UpdateOutcome(status="non_ff", error=raw_stderr)
            return UpdateOutcome(status="error", error=raw_stderr)
