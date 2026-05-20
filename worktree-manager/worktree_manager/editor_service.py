import platform
import subprocess
from worktree_manager.config_store import ConfigStore


class EditorService:
    def __init__(self, config_store: ConfigStore, window_registry=None):
        self._store = config_store
        self._registry = window_registry

    def open(self, path: str, editor: str, reuse_window: bool, repo_path: str):
        cmd = "cursor" if editor == "cursor" else "code"
        window_flag = "--reuse-window" if reuse_window else "--new-window"
        proc = subprocess.Popen([cmd, window_flag, path])

        if self._registry is not None:
            self._registry.register(repo_path, path, proc.pid, editor)

        cfg = self._store.get_repo(repo_path)
        if cfg is not None:
            cfg.last_editor = editor
            cfg.last_editor_mode = "reuse" if reuse_window else "new"
            self._store.save_repo(cfg)

        return proc

    def focus(self, record) -> None:
        if platform.system() == "Darwin":
            script = (
                f'tell application "System Events" to set frontmost of '
                f'(first process whose unix id is {record.pid}) to true'
            )
            try:
                subprocess.run(["osascript", "-e", script], check=True)
            except subprocess.CalledProcessError:
                pass
        else:
            try:
                subprocess.run(["wmctrl", "-ip", str(record.pid)], check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
