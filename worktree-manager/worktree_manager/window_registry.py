import os
import signal
from worktree_manager.models import WindowRecord


class WindowRegistry:
    def __init__(self):
        self._windows: dict[tuple[str, str], WindowRecord] = {}

    def register(
        self, repo_path: str, worktree_path: str, pid: int, editor: str, proc=None
    ) -> None:
        key = (repo_path, worktree_path)
        self._windows[key] = WindowRecord(
            repo_path=repo_path,
            worktree_path=worktree_path,
            editor=editor,
            pid=pid,
            proc=proc,
        )

    def get_window(self, repo_path: str, worktree_path: str) -> WindowRecord | None:
        return self._windows.get((repo_path, worktree_path))

    def is_alive(self, record: WindowRecord) -> bool:
        if record.proc is not None:
            return record.proc.poll() is None
        try:
            os.kill(record.pid, 0)
            return True
        except OSError:
            return False

    def prune(self) -> None:
        dead = [key for key, rec in self._windows.items() if not self.is_alive(rec)]
        for key in dead:
            del self._windows[key]

    def all_for_repo(self, repo_path: str) -> list[WindowRecord]:
        return [
            rec for rec in self._windows.values()
            if rec.repo_path == repo_path and self.is_alive(rec)
        ]

    def close(self, record: WindowRecord) -> None:
        if record.proc is not None:
            try:
                record.proc.terminate()
            except OSError:
                pass
        else:
            try:
                os.kill(record.pid, signal.SIGTERM)
            except OSError:
                pass
