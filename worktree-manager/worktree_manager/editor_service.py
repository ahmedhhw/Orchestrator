import os
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
    def __init__(self, config_store: ConfigStore):
        self._store = config_store

    def open_new(self, path: str, editor: str):
        cmd = _resolve_editor_cmd(editor)
        return subprocess.Popen([cmd, path])

    def open_replacing(self, cur_path: str, new_path: str, editor: str) -> None:
        cmd = _resolve_editor_cmd(editor)
        subprocess.run([cmd, "-r", cur_path], check=False)
        subprocess.run([cmd, "-r", new_path], check=False)
