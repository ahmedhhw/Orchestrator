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

    @property
    def target_is_working_tree(self) -> bool:
        return self.target_ref in ("working_tree_unstaged", "working_tree_staged")

    def load_diff_files(self) -> list:
        if self.repo_path is None:
            raise RuntimeError("No repo selected")
        if self.base_ref is None or self.target_ref is None:
            raise RuntimeError("FROM/TO refs not set")
        cwd = self.worktree_path or self.repo_path
        self.diff_files = self._git.diff_files(cwd, self.base_ref, self.target_ref)
        return self.diff_files

    def get_diff_hunks(self, path: str) -> list:
        if self.repo_path is None:
            raise RuntimeError("No repo selected")
        if self.base_ref is None or self.target_ref is None:
            raise RuntimeError("FROM/TO refs not set")
        cwd = self.worktree_path or self.repo_path
        return self._git.diff_hunks(cwd, self.base_ref, self.target_ref, path)

    def restore_hunks(self, path: str, hunk_indices: list) -> str:
        if self.base_ref is None or self.target_ref is None:
            raise RuntimeError("FROM/TO refs not set")
        cwd = self.worktree_path or self.repo_path
        all_hunks = self._git.diff_hunks(cwd, self.base_ref, self.target_ref, path)
        selected = [h for h in all_hunks if h.index in hunk_indices]
        forward_patch = self._git.apply_reverse_patch(cwd, path, selected)
        self._refresh_diff_files()
        return forward_patch

    def undo_restore(self, path: str, forward_patch: str) -> None:
        cwd = self.worktree_path or self.repo_path
        self._git.apply_patch(cwd, forward_patch)
        self._refresh_diff_files()

    def open_file(self, path: str, editor_service) -> None:
        import os
        editor = self._store.get_ui_pref("editor", "cursor")
        cwd = self.worktree_path or self.repo_path
        abs_path = os.path.join(cwd, path)
        editor_service.open_new(abs_path, editor)

    def _refresh_diff_files(self) -> None:
        cwd = self.worktree_path or self.repo_path
        self.diff_files = self._git.diff_files(cwd, self.base_ref, self.target_ref)
