from worktree_manager.config_store import ConfigStore
from worktree_manager.git_service import GitService
from worktree_manager.main_window_vm import MainWindowViewModel


class WorktreeMgmtViewModel:
    def __init__(self, config_store: ConfigStore, git_service: GitService):
        self._store = config_store
        self._git = git_service
        self._selected_repo: str | None = None

    def list_repos(self) -> list[str]:
        return list(self._store.all_repos().keys())

    def select_repo(self, repo_path: str) -> None:
        self._selected_repo = repo_path

    def selected_repo(self) -> str | None:
        return self._selected_repo

    def per_repo_vm(self, repo_path: str) -> MainWindowViewModel:
        return MainWindowViewModel(
            repo_path=repo_path,
            config_store=self._store,
            git_service=self._git,
        )
