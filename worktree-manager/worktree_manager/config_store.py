import json
from pathlib import Path
from typing import Optional
from worktree_manager.models import RepoConfig


class ConfigStore:
    def __init__(self, path: Optional[Path] = None):
        if path is None:
            path = Path.home() / ".config" / "worktree-manager" / "config.json"
        self._path = path

    def _load_raw(self) -> dict:
        if not self._path.exists():
            return {"repos": {}}
        return json.loads(self._path.read_text())

    def _save_raw(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2))

    def get_repo(self, repo_path: str) -> Optional[RepoConfig]:
        data = self._load_raw()
        entry = data["repos"].get(repo_path)
        if entry is None:
            return None
        return RepoConfig(repo_path=repo_path, **entry)

    def save_repo(self, cfg: RepoConfig) -> None:
        data = self._load_raw()
        data["repos"][cfg.repo_path] = {
            "worktree_storage": cfg.worktree_storage,
            "stale_days": cfg.stale_days,
            "last_editor": cfg.last_editor,
            "last_editor_mode": cfg.last_editor_mode,
            "last_opened": cfg.last_opened,
        }
        self._save_raw(data)

    def all_repos(self) -> dict:
        data = self._load_raw()
        return {
            path: RepoConfig(repo_path=path, **entry)
            for path, entry in data["repos"].items()
        }
