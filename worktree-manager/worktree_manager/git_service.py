import os
import subprocess
import time
from worktree_manager.models import WorktreeModel


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
            return self._run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=worktree_path
            ).strip()
        except subprocess.CalledProcessError:
            return "(detached)"

    def checkout_branch(self, worktree_path: str, branch: str) -> None:
        self._run(["git", "checkout", branch], cwd=worktree_path)

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
