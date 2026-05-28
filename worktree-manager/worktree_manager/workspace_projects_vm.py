import subprocess
from dataclasses import dataclass

from worktree_manager.config_store import ConfigStore
from worktree_manager.git_service import GitService
from worktree_manager.workspace_service import WorkspaceService
from worktree_manager.models import WorkspaceProject, WorkspaceEntry


@dataclass
class WorktreeStatus:
    path: str
    branch: str
    is_main: bool
    has_uncommitted: bool


class WorkspaceProjectsViewModel:
    def __init__(
        self,
        config_store: ConfigStore,
        git_service: GitService,
        workspace_service: WorkspaceService,
    ):
        self._store = config_store
        self._git = git_service
        self._svc = workspace_service

    def load_projects(self) -> list:
        return self._store.all_projects()

    def create_project(self, name: str, entries: list) -> WorkspaceProject:
        project = WorkspaceProject(name=name, entries=entries)
        self._store.save_project(project)
        self._svc.generate_code_workspace(project)
        return project

    def delete_project(self, name: str) -> None:
        self._store.delete_project(name)
        self._svc.delete_code_workspace(name)

    def update_project(self, old_name: str, new_name: str, entries: list) -> WorkspaceProject:
        self._store.rename_project(old_name, new_name, entries)
        project = WorkspaceProject(name=new_name, entries=entries)
        self._svc.generate_code_workspace(project)
        return project

    def open_project(self, name: str, editor: str) -> None:
        project = self._store.get_project(name)
        if project is None:
            raise ValueError(f"Project '{name}' not found.")
        self._svc.generate_code_workspace(project)
        self._svc.open_in_editor(project, editor)

    def list_worktrees_for_repo(self, repo_path: str) -> list:
        return self._git.list_worktrees(repo_path)

    def list_worktrees_with_dirty(self, repo_path: str) -> list[WorktreeStatus]:
        worktrees = self._git.list_worktrees(repo_path)
        result = []
        for wt in worktrees:
            dirty = self._git.has_uncommitted_changes(wt.path)
            result.append(WorktreeStatus(
                path=wt.path,
                branch=wt.branch,
                is_main=wt.is_main,
                has_uncommitted=dirty,
            ))
        return result

    def create_worktree_for_project(self, repo_path: str, spec: dict) -> WorktreeStatus:
        if spec["mode"] == "new":
            self._git.create_worktree(
                repo_path=repo_path,
                worktree_path=spec["worktree_path"],
                branch=spec["branch"],
                base_branch=spec["base_branch"],
            )
        else:
            self._git.create_worktree_from_existing(
                repo_path=repo_path,
                worktree_path=spec["worktree_path"],
                branch=spec["branch"],
            )
        return WorktreeStatus(
            path=spec["worktree_path"],
            branch=spec["branch"],
            is_main=False,
            has_uncommitted=False,
        )

    def checkout_new_branch_on_worktree(
        self, worktree_path: str, new_branch: str, base_branch: str
    ) -> WorktreeStatus:
        dirty = self._git.has_uncommitted_changes(worktree_path)
        if dirty and base_branch != "HEAD":
            raise ValueError(
                "Worktree has uncommitted changes. Base must be current HEAD."
            )
        self._git.checkout_new_branch(worktree_path, new_branch, base_branch)
        return WorktreeStatus(
            path=worktree_path,
            branch=new_branch,
            is_main=False,
            has_uncommitted=dirty,
        )

    def list_branches_for_worktree(self, worktree_path: str) -> list[str]:
        repo_root = self._git.repo_root(worktree_path)
        return self._git.list_local_branches(repo_root)

    def switch_branch_in_project(self, worktree_path: str, new_branch: str) -> None:
        if self._git.has_uncommitted_changes(worktree_path):
            raise ValueError("Worktree has uncommitted changes.")
        try:
            self._git.checkout_branch(worktree_path, new_branch)
        except subprocess.CalledProcessError as e:
            stderr = (e.stderr or "").strip()
            raise ValueError(stderr or f"git checkout failed (exit {e.returncode})") from e
