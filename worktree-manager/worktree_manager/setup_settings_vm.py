from pathlib import Path
from datetime import datetime, timezone
from worktree_manager.config_store import ConfigStore
from worktree_manager.models import RepoConfig


class RepoSetupViewModel:
    def __init__(self, repo_path: str, config_store: ConfigStore):
        self._repo_path = repo_path
        self._store = config_store

    def default_storage_path(self) -> str:
        p = Path(self._repo_path)
        return str(p.parent / (p.name + "-worktrees"))

    def confirm(self, storage_path: str, callback=None) -> None:
        cfg = RepoConfig(
            repo_path=self._repo_path,
            worktree_storage=storage_path,
            stale_days=30,
            last_editor="cursor",
            last_editor_mode="reuse",
            last_opened=datetime.now(timezone.utc).isoformat(),
        )
        self._store.save_repo(cfg)
        if callback:
            callback()


class SettingsViewModel:
    def __init__(self, repo_path: str, config_store: ConfigStore):
        self._repo_path = repo_path
        self._store = config_store
        cfg = config_store.get_repo(repo_path)
        self.worktree_storage = cfg.worktree_storage
        self.stale_days = cfg.stale_days
        self.last_editor = cfg.last_editor
        self.last_editor_mode = cfg.last_editor_mode

    def save(self, worktree_storage: str, stale_days: int,
             last_editor: str, last_editor_mode: str) -> None:
        cfg = self._store.get_repo(self._repo_path)
        cfg.worktree_storage = worktree_storage
        cfg.stale_days = stale_days
        cfg.last_editor = last_editor
        cfg.last_editor_mode = last_editor_mode
        self._store.save_repo(cfg)
