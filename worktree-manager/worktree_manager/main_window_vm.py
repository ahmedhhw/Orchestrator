from worktree_manager.config_store import ConfigStore
from worktree_manager.git_service import GitService
from worktree_manager.editor_service import EditorService
from worktree_manager.models import WorktreeModel


class MainWindowViewModel:
    def __init__(
        self,
        repo_path: str,
        config_store: ConfigStore,
        git_service: GitService,
        editor_service: EditorService,
    ):
        self._repo_path = repo_path
        self._store = config_store
        self._git = git_service
        self._editor = editor_service
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

    def open_worktree(self, path: str) -> None:
        cfg = self._store.get_repo(self._repo_path)
        editor = cfg.editor
        if cfg.window_mode == "single":
            if cfg.cur_open_path:
                self._editor.open_replacing(
                    cur_path=cfg.cur_open_path,
                    new_path=path,
                    editor=editor,
                )
            else:
                self._editor.open_new(path, editor=editor)
            cfg.cur_open_path = path
            self._store.save_repo(cfg)
        else:
            self._editor.open_new(path, editor=editor)

    def set_editor(self, editor: str) -> None:
        cfg = self._store.get_repo(self._repo_path)
        cfg.editor = editor
        self._store.save_repo(cfg)

    def set_window_mode(self, mode: str) -> None:
        cfg = self._store.get_repo(self._repo_path)
        cfg.window_mode = mode
        self._store.save_repo(cfg)

    def cur_open_path(self) -> str | None:
        cfg = self._store.get_repo(self._repo_path)
        return cfg.cur_open_path

    def show_switch_label(self, path: str) -> bool:
        cfg = self._store.get_repo(self._repo_path)
        if cfg.window_mode != "single":
            return False
        if not cfg.cur_open_path:
            return False
        return cfg.cur_open_path != path

    def default_editor(self) -> tuple:
        cfg = self._store.get_repo(self._repo_path)
        return cfg.last_editor, cfg.last_editor_mode

    def is_protected_branch(self, branch: str) -> bool:
        return branch == "main" or branch.startswith("feature/")

    def has_uncommitted_changes_for_branch(self, branch: str) -> bool:
        import os
        path = self.worktree_path_for_branch(branch)
        if not os.path.isdir(path):
            return False
        return self._git.has_uncommitted_changes(path)

    def create_worktree(self, branch: str, base_branch: str | None, existing: bool = False) -> None:
        path = self.worktree_path_for_branch(branch)
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
        import time
        from worktree_manager.models import CleanupCandidate
        cfg = self._store.get_repo(self._repo_path)
        stale_threshold = int(time.time()) - cfg.stale_days * 86400

        feature_branches = self._git.list_feature_branches(self._repo_path)
        merge_targets = ["main"] + feature_branches

        worktree_branches = {wt.branch for wt in self._worktrees}
        candidates = []

        for wt in self._worktrees:
            if wt.is_main:
                continue
            if self.is_protected_branch(wt.branch):
                continue
            merged, merged_into = self._git.is_merged_into_any(
                self._repo_path, wt.branch, merge_targets
            )
            stale = wt.last_commit_ts > 0 and wt.last_commit_ts < stale_threshold
            candidates.append(CleanupCandidate(
                branch=wt.branch,
                path=wt.path,
                is_merged=merged,
                is_stale=stale,
                last_commit_ts=wt.last_commit_ts,
                merged_into=merged_into,
            ))

        for branch in self._git.list_local_branches(self._repo_path):
            if branch in worktree_branches:
                continue
            if self.is_protected_branch(branch):
                continue
            ts = self._git.last_commit_ts(self._repo_path, branch)
            merged, merged_into = self._git.is_merged_into_any(
                self._repo_path, branch, merge_targets
            )
            stale = ts > 0 and ts < stale_threshold
            candidates.append(CleanupCandidate(
                branch=branch,
                path=None,
                is_merged=merged,
                is_stale=stale,
                last_commit_ts=ts,
                merged_into=merged_into,
            ))

        return candidates

    def list_local_branches(self) -> list:
        return self._git.list_local_branches(self._repo_path)

    def list_available_branches(self) -> list:
        """Local branches not already checked out as a worktree."""
        checked_out = {wt.branch for wt in self._worktrees}
        return [b for b in self._git.list_local_branches(self._repo_path) if b not in checked_out]

    def delete_cleanup_candidates(self, candidates: list, also_delete_branches: bool) -> None:
        for c in candidates:
            if c.path is not None:
                self._git.delete_worktree(repo_path=self._repo_path, worktree_path=c.path)
                if also_delete_branches:
                    self._git.delete_branch(repo_path=self._repo_path, branch=c.branch)
            else:
                self._git.delete_branch(repo_path=self._repo_path, branch=c.branch)
