from worktree_manager.config_store import ConfigStore
from worktree_manager.git_service import GitService
from worktree_manager.main_window_vm import MainWindowViewModel


class BranchMgmtViewModel:
    def __init__(self, config_store: ConfigStore, git_service: GitService):
        self._store = config_store
        self._git = git_service
        # Maps candidate branch name → repo_path; populated during load_cleanup_candidates.
        self._candidate_repo: dict[str, str] = {}

    def list_repos(self) -> list[str]:
        return list(self._store.all_repos().keys())

    def _repo_vm(self, repo_path: str) -> MainWindowViewModel:
        vm = MainWindowViewModel(
            repo_path=repo_path,
            config_store=self._store,
            git_service=self._git,
        )
        vm.load_worktrees()
        return vm

    def load_cleanup_candidates(self, repo_path: str | None) -> list:
        """Return cleanup candidates for one repo (repo_path) or all repos (None)."""
        self._candidate_repo = {}
        if repo_path is not None:
            candidates = self._repo_vm(repo_path).all_cleanup_candidates()
            for c in candidates:
                self._candidate_repo[c.branch] = repo_path
            return candidates
        all_candidates = []
        for path in self.list_repos():
            candidates = self._repo_vm(path).all_cleanup_candidates()
            for c in candidates:
                self._candidate_repo[c.branch] = path
            all_candidates.extend(candidates)
        return all_candidates

    def delete_cleanup_selection(self, repo_path: str | None, candidates: list) -> None:
        """Delete selected candidates. If repo_path is None, route each to its repo."""
        if repo_path is not None:
            self._repo_vm(repo_path).delete_cleanup_candidates(
                candidates, also_delete_branches=True
            )
            return
        # Group by repo using the mapping built during the last load.
        by_repo: dict[str, list] = {}
        for c in candidates:
            r = self._candidate_repo.get(c.branch)
            if r is None:
                continue
            by_repo.setdefault(r, []).append(c)
        for r, group in by_repo.items():
            self._repo_vm(r).delete_cleanup_candidates(group, also_delete_branches=True)
