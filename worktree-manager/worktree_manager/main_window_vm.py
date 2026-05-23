import time
from concurrent.futures import ThreadPoolExecutor
from worktree_manager.config_store import ConfigStore
from worktree_manager.git_service import GitService
from worktree_manager.models import WorktreeModel, CleanupCandidate


class MainWindowViewModel:
    def __init__(
        self,
        repo_path: str,
        config_store: ConfigStore,
        git_service: GitService,
    ):
        self._repo_path = repo_path
        self._store = config_store
        self._git = git_service
        self._worktrees: list = []

    def load_worktrees(self) -> list:
        cfg = self._store.get_repo(self._repo_path)
        self._worktrees = self._git.list_worktrees(self._repo_path, stale_days=cfg.stale_days)
        return self._worktrees

    def cleanup_candidates(self) -> list:
        return [wt for wt in self._worktrees if not wt.is_main and (wt.is_stale or wt.is_merged)]

    def branch_to_folder_name(self, branch: str) -> str:
        return branch.replace("/", "-")

    def worktree_path_for_branch(self, branch: str) -> str:
        cfg = self._store.get_repo(self._repo_path)
        return cfg.worktree_storage + "/" + self.branch_to_folder_name(branch)

    def is_protected_branch(self, branch: str) -> bool:
        return branch == "main" or branch.startswith("feature/")

    def has_uncommitted_changes_for_branch(self, branch: str) -> bool:
        import os
        path = self.worktree_path_for_branch(branch)
        if not os.path.isdir(path):
            return False
        return self._git.has_uncommitted_changes(path)

    def has_uncommitted_changes(self, path: str) -> bool:
        import os
        if not os.path.isdir(path):
            return False
        return self._git.has_uncommitted_changes(path)

    def create_worktree(self, branch: str, base_branch: str | None, existing: bool = False, worktree_name: str | None = None) -> None:
        cfg = self._store.get_repo(self._repo_path)
        folder = worktree_name if worktree_name else self.branch_to_folder_name(branch)
        path = cfg.worktree_storage + "/" + folder

        all_local_branches = set(self._git.list_local_branches(self._repo_path))
        worktree_branches = {wt.branch for wt in self._worktrees}
        existing_branches = all_local_branches | worktree_branches
        if not existing and branch in existing_branches:
            raise ValueError(f"Branch '{branch}' already exists in this repo.")

        existing_paths = {wt.path for wt in self._worktrees}
        if path in existing_paths:
            raise ValueError(f"Worktree folder '{folder}' is already in use.")

        if existing:
            self._git.create_worktree_from_existing(
                repo_path=self._repo_path,
                worktree_path=path,
                branch=branch,
            )
        else:
            self._git.create_worktree(
                repo_path=self._repo_path,
                worktree_path=path,
                branch=branch,
                base_branch=base_branch,
            )

    def delete_worktree(self, path: str, branch: str, also_delete_branch: bool) -> None:
        self._git.delete_worktree(repo_path=self._repo_path, worktree_path=path)
        if also_delete_branch:
            self._git.delete_branch(repo_path=self._repo_path, branch=branch)

    def all_cleanup_candidates(self) -> list:
        cfg = self._store.get_repo(self._repo_path)
        stale_threshold = int(time.time()) - cfg.stale_days * 86400

        feature_branches = self._git.list_feature_branches(self._repo_path)
        merge_targets = ["main"] + feature_branches
        merged_map = self._git.build_merged_map(self._repo_path, merge_targets)

        non_main_worktree_branches = {wt.branch for wt in self._worktrees if not wt.is_main}
        candidates = []

        worktree_wts = list(self._worktrees)

        with ThreadPoolExecutor() as executor:
            uncommitted_results = list(executor.map(
                lambda wt: self._git.has_uncommitted_changes(wt.path),
                worktree_wts,
            ))

        for wt, has_uncommitted in zip(worktree_wts, uncommitted_results):
            merged_into = merged_map.get(wt.branch)
            stale = wt.last_commit_ts > 0 and wt.last_commit_ts < stale_threshold
            candidates.append(CleanupCandidate(
                branch=wt.branch,
                path=wt.path,
                is_merged=merged_into is not None,
                is_stale=stale,
                last_commit_ts=wt.last_commit_ts,
                merged_into=merged_into,
                has_uncommitted=has_uncommitted,
                is_checked_out=True,
                is_protected=wt.is_main or self.is_protected_branch(wt.branch),
            ))

        all_checked_out = {wt.branch for wt in self._worktrees}
        main_wt = next((wt for wt in self._worktrees if wt.is_main), None)
        main_branch = main_wt.branch if main_wt else None

        for branch in self._git.list_local_branches(self._repo_path):
            if branch in non_main_worktree_branches:
                continue
            if branch == main_branch:
                continue
            is_protected = self.is_protected_branch(branch)
            ts = self._git.last_commit_ts(self._repo_path, branch)
            merged_into = merged_map.get(branch)
            stale = ts > 0 and ts < stale_threshold
            is_checked_out = branch in all_checked_out
            candidates.append(CleanupCandidate(
                branch=branch,
                path=None,
                is_merged=merged_into is not None,
                is_stale=stale,
                last_commit_ts=ts,
                merged_into=merged_into,
                has_uncommitted=False,
                is_checked_out=is_checked_out,
                is_protected=is_protected,
            ))

        return candidates

    def list_local_branches(self) -> list:
        return self._git.list_local_branches(self._repo_path)

    def list_available_branches(self) -> list:
        checked_out = {wt.branch for wt in self._worktrees}
        return [b for b in self._git.list_local_branches(self._repo_path) if b not in checked_out]

    def list_branches_with_checkout_status(self) -> list[tuple[str, bool]]:
        checked_out = {wt.branch for wt in self._worktrees}
        all_branches = self._git.list_local_branches(self._repo_path)
        return [(b, b in checked_out) for b in all_branches]

    def switch_branch(self, worktree_path: str, new_branch: str) -> None:
        if self._git.has_uncommitted_changes(worktree_path):
            raise ValueError("uncommitted changes")
        self._git.checkout_branch(worktree_path, new_branch)

    def delete_cleanup_candidates(self, candidates: list, also_delete_branches: bool = True) -> None:
        for c in candidates:
            self._git.delete_branch(repo_path=self._repo_path, branch=c.branch)
