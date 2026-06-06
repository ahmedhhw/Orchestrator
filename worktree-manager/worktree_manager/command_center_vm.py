from pathlib import Path
from worktree_manager.config_store import ConfigStore
from worktree_manager.command_runner import CommandRunner, RunHandle, RunStatus
from worktree_manager.models import SavedCommand
from worktree_manager.git_service import GitService


def _norm_path(p: str) -> str:
    return str(Path(p).resolve())


class DuplicateRunError(Exception):
    """Raised when the same command is already running for the same repo+worktree."""
    def __init__(self, run_id: str):
        self.run_id = run_id
        super().__init__(f"Command already running: {run_id}")


class CommandCenterViewModel:
    def __init__(self, config_store: ConfigStore, git_service: GitService | None = None):
        self._store = config_store
        self._git = git_service or GitService()
        self._runner = CommandRunner()
        self._runner.output_callback = self._on_runner_output
        self._runner.exit_callback = self._on_runner_exit
        self._run_meta: dict[str, dict] = {}
        self._startup_fired: set[str] = set()

        self.on_run_added = None        # Callable[[RunHandle], None]
        self.on_output = None           # Callable[[run_id, line], None]
        self.on_status_changed = None   # Callable[[run_id, RunStatus], None]
        self.on_run_id_changed = None   # Callable[[old_id, new_id], None]
        self.on_finished = None         # Callable[[run_id, RunHandle], None]
        self.on_startup_detected = None # Callable[[run_id, RunHandle], None]

    # --- saved command CRUD ---

    def saved_commands(self, repo_path: str) -> list[SavedCommand]:
        return self._store.get_commands(repo_path)

    def save_command(self, repo_path: str, name: str, command: str, startup_pattern: str | None = None) -> None:
        self._store.save_command(repo_path, SavedCommand(name=name, command=command, startup_pattern=startup_pattern))
        self._sync_run_meta(repo_path, name, command, startup_pattern)

    def _sync_run_meta(self, repo_path: str, cmd_name: str, command_str: str, startup_pattern: str | None) -> None:
        """Update _run_meta for any live run matching this command, so restart and startup detection use the new values."""
        for run_id, meta in self._run_meta.items():
            if meta.get("repo_path") == repo_path and meta.get("cmd_name") == cmd_name:
                meta["command_str"] = command_str
                meta["startup_pattern"] = startup_pattern
                self._startup_fired.discard(run_id)

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
        startup_pattern: str | None = None,
    ) -> str:
        for handle in self._runner._handles.values():
            if (
                handle.status == RunStatus.RUNNING
                and handle.cmd_name == cmd_name
                and handle.repo_path == repo_path
                and _norm_path(handle.worktree_path) == _norm_path(worktree_path)
            ):
                raise DuplicateRunError(handle.run_id)

        self._runner.shell = self._store.get_ui_pref("shell", "zsh")
        handle = self._runner.start(
            command_str=command_str,
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
            "startup_pattern": startup_pattern,
        }
        if self.on_run_added:
            self.on_run_added(handle)
        return handle.run_id

    def stop(self, run_id: str) -> None:
        self._runner.terminate(run_id, intentional=True)

    def remove_run(self, run_id: str) -> None:
        self._runner.terminate(run_id, intentional=True)
        self._runner.forget(run_id)
        self._run_meta.pop(run_id, None)
        self._startup_fired.discard(run_id)

    def restart(self, run_id: str) -> str:
        meta = self._run_meta.get(run_id)
        if not meta:
            raise KeyError(run_id)
        old_handle = self._runner.get_handle(run_id)
        if old_handle:
            self._runner.terminate(run_id, intentional=True)
            old_handle.output_lines.clear()
            self._runner.forget(run_id)
        self._startup_fired.discard(run_id)

        saved_on_run_added = self.on_run_added
        self.on_run_added = None
        new_run_id = self.launch(**meta)
        self.on_run_added = saved_on_run_added

        if self.on_run_id_changed:
            self.on_run_id_changed(run_id, new_run_id)
        return new_run_id

    def get_run(self, run_id: str) -> RunHandle | None:
        return self._runner.get_handle(run_id)

    def find_existing_run(self, cmd_name: str, repo_path: str, worktree_path: str) -> RunHandle | None:
        """Return any existing handle (any status) matching the given command+repo+worktree."""
        for handle in self._runner._handles.values():
            if (
                handle.cmd_name == cmd_name
                and handle.repo_path == repo_path
                and _norm_path(handle.worktree_path) == _norm_path(worktree_path)
            ):
                return handle
        return None

    def all_runs(self) -> list[RunHandle]:
        return list(self._runner._handles.values())

    # --- repo / worktree helpers ---

    def get_last_used_repo(self) -> str | None:
        return self._store.get_ui_pref("last_used_repo")

    def set_last_used_repo(self, repo_path: str) -> None:
        self._store.set_ui_pref("last_used_repo", repo_path)

    def all_repos(self) -> dict:
        return self._store.all_repos()

    def list_worktrees(self, repo_path: str) -> list:
        cfg = self._store.get_repo(repo_path)
        stale_days = cfg.stale_days if cfg else 30
        return self._git.list_worktrees(repo_path, stale_days=stale_days)

    # --- runner callbacks (background thread) ---

    def _on_runner_output(self, run_id: str, line: str) -> None:
        if self.on_startup_detected and run_id not in self._startup_fired:
            meta = self._run_meta.get(run_id, {})
            pattern = meta.get("startup_pattern")
            if pattern and pattern in line:
                self._startup_fired.add(run_id)
                handle = self._runner.get_handle(run_id)
                if handle:
                    self.on_startup_detected(run_id, handle)
        if self.on_output:
            self.on_output(run_id, line)

    def _on_runner_exit(self, run_id: str, returncode: int) -> None:
        handle = self._runner.get_handle(run_id)
        if handle:
            if self.on_status_changed:
                self.on_status_changed(run_id, handle.status)
            if self.on_finished:
                self.on_finished(run_id, handle)
