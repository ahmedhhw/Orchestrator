import json
from pathlib import Path
from typing import Optional
from worktree_manager.models import RepoConfig, SavedCommand


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
        return RepoConfig(
            repo_path=repo_path,
            worktree_storage=entry["worktree_storage"],
            stale_days=entry["stale_days"],
            last_editor=entry["last_editor"],
            last_editor_mode=entry["last_editor_mode"],
            last_opened=entry["last_opened"],
            editor=entry.get("editor", entry.get("last_editor", "cursor")),
            window_mode=entry.get("window_mode", "multi"),
            cur_open_path=entry.get("cur_open_path", None),
            commands=[
                SavedCommand(name=c["name"], command=c["command"])
                for c in entry.get("commands", [])
            ],
        )

    def get_commands(self, repo_path: str) -> list:
        data = self._load_raw()
        entry = data["repos"].get(repo_path, {})
        return [
            SavedCommand(name=c["name"], command=c["command"])
            for c in entry.get("commands", [])
        ]

    def save_command(self, repo_path: str, cmd: SavedCommand) -> None:
        data = self._load_raw()
        entry = data["repos"].setdefault(repo_path, {})
        commands = [c for c in entry.get("commands", []) if c["name"] != cmd.name]
        commands.append({"name": cmd.name, "command": cmd.command})
        entry["commands"] = commands
        self._save_raw(data)

    def delete_command(self, repo_path: str, name: str) -> None:
        data = self._load_raw()
        entry = data["repos"].get(repo_path, {})
        entry["commands"] = [c for c in entry.get("commands", []) if c["name"] != name]
        self._save_raw(data)

    def save_repo(self, cfg: RepoConfig) -> None:
        data = self._load_raw()
        data["repos"][cfg.repo_path] = {
            "worktree_storage": cfg.worktree_storage,
            "stale_days": cfg.stale_days,
            "last_editor": cfg.last_editor,
            "last_editor_mode": cfg.last_editor_mode,
            "last_opened": cfg.last_opened,
            "editor": cfg.editor,
            "window_mode": cfg.window_mode,
            "cur_open_path": cfg.cur_open_path,
        }
        self._save_raw(data)

    def clear_all_open_paths(self) -> None:
        data = self._load_raw()
        for entry in data["repos"].values():
            entry["cur_open_path"] = None
        self._save_raw(data)

    def all_repos(self) -> dict:
        data = self._load_raw()
        repos = {
            path: RepoConfig(
                repo_path=path,
                worktree_storage=entry["worktree_storage"],
                stale_days=entry["stale_days"],
                last_editor=entry["last_editor"],
                last_editor_mode=entry["last_editor_mode"],
                last_opened=entry["last_opened"],
                editor=entry.get("editor", entry.get("last_editor", "cursor")),
                window_mode=entry.get("window_mode", "multi"),
                cur_open_path=entry.get("cur_open_path", None),
                commands=[
                    SavedCommand(name=c["name"], command=c["command"])
                    for c in entry.get("commands", [])
                ],
            )
            for path, entry in data["repos"].items()
        }
        return dict(
            sorted(repos.items(), key=lambda kv: kv[1].last_opened, reverse=True)
        )
