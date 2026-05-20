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

    def open_worktree(self, path: str, editor: str, reuse_window: bool) -> None:
        self._editor.open(path, editor=editor, reuse_window=reuse_window, repo_path=self._repo_path)

    def default_editor(self) -> tuple:
        cfg = self._store.get_repo(self._repo_path)
        return cfg.last_editor, cfg.last_editor_mode

    def create_worktree(self, branch: str, base_branch: str) -> None:
        path = self.worktree_path_for_branch(branch)
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

    def list_local_branches(self) -> list:
        return self._git.list_local_branches(self._repo_path)

    def delete_cleanup_candidates(self, candidates: list, also_delete_branches: bool) -> None:
        for wt in candidates:
            self._git.delete_worktree(repo_path=self._repo_path, worktree_path=wt.path)
            if also_delete_branches:
                self._git.delete_branch(repo_path=self._repo_path, branch=wt.branch)
