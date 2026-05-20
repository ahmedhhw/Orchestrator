from worktree_manager.config_store import ConfigStore
from worktree_manager.git_service import GitService
from worktree_manager.models import RepoConfig


class LandingScreenViewModel:
    def __init__(self, config_store: ConfigStore, git_service: GitService):
        self._store = config_store
        self._git = git_service

    def recent_repos(self) -> list:
        return list(self._store.all_repos().values())

    def validate_repo(self, path: str) -> tuple:
        if not path:
            return False, "Please select a folder."
        if not self._git.is_valid_repo(path):
            return False, "Not a git repository — please select a folder that contains a .git directory."
        return True, ""

    def on_repo_selected(self, path: str, callback) -> None:
        ok, _ = self.validate_repo(path)
        if ok:
            callback(path)
