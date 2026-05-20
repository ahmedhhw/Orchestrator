import os
import platform
import shutil
import subprocess
from worktree_manager.config_store import ConfigStore

_EDITOR_FALLBACKS = {
    "cursor": [
        "/usr/local/bin/cursor",
        "/opt/homebrew/bin/cursor",
        "/Applications/Cursor.app/Contents/Resources/app/bin/cursor",
    ],
    "vscode": [
        "/usr/local/bin/code",
        "/opt/homebrew/bin/code",
        "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code",
    ],
}


def _resolve_editor_cmd(editor: str) -> str:
    short = "cursor" if editor == "cursor" else "code"
    found = shutil.which(short)
    if found:
        return found
    env_path = os.environ.get("PATH", "") + ":/usr/local/bin:/opt/homebrew/bin"
    found = shutil.which(short, path=env_path)
    if found:
        return found
    for fallback in _EDITOR_FALLBACKS.get(editor, []):
        if os.path.isfile(fallback):
            return fallback
    raise FileNotFoundError(
        f"Cannot find '{short}' editor binary. "
        f"Make sure it is installed and the CLI command is available."
    )


class EditorService:
    def __init__(self, config_store: ConfigStore, window_registry=None):
        self._store = config_store
        self._registry = window_registry

    def open(self, path: str, editor: str, reuse_window: bool, repo_path: str):
        cmd = _resolve_editor_cmd(editor)
        window_flag = "--reuse-window" if reuse_window else "--new-window"
        proc = subprocess.Popen([cmd, window_flag, path])

        if self._registry is not None:
            self._registry.register(repo_path, path, proc.pid, editor, proc=proc)

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
