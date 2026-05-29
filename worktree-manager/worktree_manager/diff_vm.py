class DiffViewModel:
    def __init__(self, git_service, config_store):
        self._git = git_service
        self._store = config_store
        self.repo_path = None
        self.worktree_path = None
        self.available_points = []
        self.diff_files = []
        self.base_ref = None
        self.target_ref = None

    def set_repo(self, repo_path: str) -> None:
        self.repo_path = repo_path
        self.worktree_path = None
        self.base_ref = None
        self.target_ref = None
        self.diff_files = []
        self.available_points = self._git.list_points(repo_path)

    def set_worktree(self, worktree_path: str) -> None:
        self.worktree_path = worktree_path
        self.base_ref = None
        self.target_ref = None
        self.diff_files = []
        self.available_points = self._git.list_points(worktree_path)

    def set_points(self, base_ref: str, target_ref: str) -> None:
        self.base_ref = base_ref
        self.target_ref = target_ref

    def load_diff_files(self) -> list:
        if self.repo_path is None:
            raise RuntimeError("No repo selected")
        if self.base_ref is None or self.target_ref is None:
            raise RuntimeError("FROM/TO refs not set")
        cwd = self.worktree_path or self.repo_path
        self.diff_files = self._git.diff_files(cwd, self.base_ref, self.target_ref)
        return self.diff_files
