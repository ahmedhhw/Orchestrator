import shlex
from pathlib import Path
from worktree_manager.config_store import ConfigStore
from worktree_manager.command_runner import CommandRunner, RunHandle, RunStatus
from worktree_manager.models import SavedCommand
from worktree_manager.git_service import GitService


class CommandCenterViewModel:
    def __init__(self, config_store: ConfigStore, git_service: GitService | None = None):
        self._store = config_store
        self._git = git_service or GitService()
        self._runner = CommandRunner()
        self._runner.output_callback = self._on_runner_output
        self._runner.exit_callback = self._on_runner_exit
        self._run_meta: dict[str, dict] = {}

        self.on_run_added = None        # Callable[[RunHandle], None]
        self.on_output = None           # Callable[[run_id, line], None]
        self.on_status_changed = None   # Callable[[run_id, RunStatus], None]
        self.on_run_id_changed = None   # Callable[[old_id, new_id], None]

    # --- saved command CRUD ---

    def saved_commands(self, repo_path: str) -> list[SavedCommand]:
        return self._store.get_commands(repo_path)

    def save_command(self, repo_path: str, name: str, command: str) -> None:
        self._store.save_command(repo_path, SavedCommand(name=name, command=command))

    def delete_command(self, repo_path: str, name: str) -> None:
        self._store.delete_command(repo_path, name)

    # --- run lifecycle ---

    def launch(
        self,
        repo_path: str,
        repo_name: str,
        cmd_name: str,
        command_str: str,
        worktree_path: str,
    ) -> str:
        command = shlex.split(command_str)
        handle = self._runner.start(
            command=command,
            cwd=worktree_path,
            cmd_name=cmd_name,
            repo_path=repo_path,
            repo_name=repo_name,
            worktree_path=worktree_path,
        )
        self._run_meta[handle.run_id] = {
            "repo_path": repo_path,
            "repo_name": repo_name,
            "cmd_name": cmd_name,
            "command_str": command_str,
            "worktree_path": worktree_path,
        }
        if self.on_run_added:
            self.on_run_added(handle)
        return handle.run_id

    def stop(self, run_id: str) -> None:
        self._runner.terminate(run_id)

    def restart(self, run_id: str) -> str:
        meta = self._run_meta.get(run_id)
        if not meta:
            raise KeyError(run_id)
        old_handle = self._runner.get_handle(run_id)
        if old_handle:
            self._runner.terminate(run_id)
            old_handle.output_lines.clear()

        saved_on_run_added = self.on_run_added
        self.on_run_added = None
        new_run_id = self.launch(**meta)
        self.on_run_added = saved_on_run_added

        if self.on_run_id_changed:
            self.on_run_id_changed(run_id, new_run_id)
        return new_run_id

    def get_run(self, run_id: str) -> RunHandle | None:
        return self._runner.get_handle(run_id)

    def all_runs(self) -> list[RunHandle]:
        return list(self._runner._handles.values())

    # --- repo / worktree helpers ---

    def all_repos(self) -> dict:
        return self._store.all_repos()

    def list_worktrees(self, repo_path: str) -> list:
        cfg = self._store.get_repo(repo_path)
        stale_days = cfg.stale_days if cfg else 30
        return self._git.list_worktrees(repo_path, stale_days=stale_days)

    # --- runner callbacks (background thread) ---

    def _on_runner_output(self, run_id: str, line: str) -> None:
        if self.on_output:
            self.on_output(run_id, line)

    def _on_runner_exit(self, run_id: str, returncode: int) -> None:
        handle = self._runner.get_handle(run_id)
        if handle and self.on_status_changed:
            self.on_status_changed(run_id, handle.status)
