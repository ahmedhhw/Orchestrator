import subprocess
from worktree_manager.config_store import ConfigStore


class EditorService:
    def __init__(self, config_store: ConfigStore):
        self._store = config_store

    def open(self, path: str, editor: str, reuse_window: bool, repo_path: str) -> None:
        cmd = "cursor" if editor == "cursor" else "code"
        window_flag = "--reuse-window" if reuse_window else "--new-window"
        subprocess.Popen([cmd, window_flag, path])

        cfg = self._store.get_repo(repo_path)
        if cfg is not None:
            cfg.last_editor = editor
            cfg.last_editor_mode = "reuse" if reuse_window else "new"
            self._store.save_repo(cfg)
