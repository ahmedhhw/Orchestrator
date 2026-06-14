import json
from pathlib import Path
from typing import Optional
from worktree_manager.models import RepoConfig, SavedCommand, WorkspaceProject, WorkspaceEntry


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
            commands=[
                SavedCommand(name=c["name"], command=c["command"], startup_pattern=c.get("startup_pattern"))
                for c in entry.get("commands", [])
            ],
        )

    def get_commands(self, repo_path: str) -> list:
        data = self._load_raw()
        entry = data["repos"].get(repo_path, {})
        return [
            SavedCommand(name=c["name"], command=c["command"], startup_pattern=c.get("startup_pattern"))
            for c in entry.get("commands", [])
        ]

    def save_command(self, repo_path: str, cmd: SavedCommand) -> None:
        data = self._load_raw()
        entry = data["repos"].setdefault(repo_path, {})
        commands = [c for c in entry.get("commands", []) if c["name"] != cmd.name]
        raw = {"name": cmd.name, "command": cmd.command}
        if cmd.startup_pattern:
            raw["startup_pattern"] = cmd.startup_pattern
        commands.append(raw)
        entry["commands"] = commands
        self._save_raw(data)

    def delete_command(self, repo_path: str, name: str) -> None:
        data = self._load_raw()
        entry = data["repos"].get(repo_path, {})
        entry["commands"] = [c for c in entry.get("commands", []) if c["name"] != name]
        self._save_raw(data)

    def delete_repo(self, repo_path: str) -> None:
        data = self._load_raw()
        data.setdefault("repos", {}).pop(repo_path, None)
        self._save_raw(data)

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

    def get_ui_pref(self, key: str, default=None):
        data = self._load_raw()
        return data.get("ui", {}).get(key, default)

    def set_ui_pref(self, key: str, value) -> None:
        data = self._load_raw()
        data.setdefault("ui", {})[key] = value
        self._save_raw(data)

    # ── spotlight shortcut ────────────────────────────────────────────────────

    def get_spotlight_shortcut(self) -> str:
        return self.get_ui_pref("spotlight_shortcut", "Ctrl+K")

    def set_spotlight_shortcut(self, seq: str) -> None:
        self.set_ui_pref("spotlight_shortcut", seq)

    # ── per-repo settings ─────────────────────────────────────────────────────

    def _repo_settings(self, data: dict) -> dict:
        return data.setdefault("ui", {}).setdefault("github_repo_settings", {})

    def get_repo_muted_checks(self, repo: str) -> list[str]:
        return self.get_ui_pref("github_repo_settings", {}).get(repo, {}).get("muted_checks", [])

    def set_repo_muted_checks(self, repo: str, names) -> None:
        data = self._load_raw()
        self._repo_settings(data).setdefault(repo, {})["muted_checks"] = list(names)
        self._save_raw(data)

    def get_repo_notification_pref(self, repo: str, event_type: str) -> bool:
        return self.get_ui_pref("github_repo_settings", {}).get(repo, {}).get("notifications", {}).get(event_type, True)

    def set_repo_notification_pref(self, repo: str, event_type: str, enabled: bool) -> None:
        data = self._load_raw()
        s = self._repo_settings(data).setdefault(repo, {})
        s.setdefault("notifications", {})[event_type] = bool(enabled)
        self._save_raw(data)

    def get_repo_collapsed(self, repo: str) -> bool:
        return bool(self.get_ui_pref("github_repo_settings", {}).get(repo, {}).get("collapsed", False))

    def set_repo_collapsed(self, repo: str, collapsed: bool) -> None:
        data = self._load_raw()
        self._repo_settings(data).setdefault(repo, {})["collapsed"] = bool(collapsed)
        self._save_raw(data)

    def get_diff_pref(self, repo_path: str) -> dict | None:
        data = self._load_raw()
        return data.get("ui", {}).get("diff", {}).get(repo_path)

    def set_diff_pref(self, repo_path: str, from_ref: str, to_ref: str) -> None:
        data = self._load_raw()
        data.setdefault("ui", {}).setdefault("diff", {})[repo_path] = {
            "from_ref": from_ref,
            "to_ref": to_ref,
        }
        self._save_raw(data)

    def get_diff_selection(self) -> dict:
        data = self._load_raw()
        return data.get("ui", {}).get("diff_selection", {})

    def set_diff_selection(self, repo_path: str, worktree_path: str) -> None:
        data = self._load_raw()
        data.setdefault("ui", {})["diff_selection"] = {
            "repo_path": repo_path,
            "worktree_path": worktree_path,
        }
        self._save_raw(data)

    def _project_from_dict(self, name: str, data: dict) -> WorkspaceProject:
        return WorkspaceProject(
            name=name,
            entries=[WorkspaceEntry(worktree_path=e["worktree_path"]) for e in data.get("entries", [])],
        )

    def all_projects(self) -> list:
        data = self._load_raw()
        return [
            self._project_from_dict(name, entry)
            for name, entry in data.get("projects", {}).items()
        ]

    def get_project(self, name: str) -> Optional[WorkspaceProject]:
        data = self._load_raw()
        entry = data.get("projects", {}).get(name)
        if entry is None:
            return None
        return self._project_from_dict(name, entry)

    def save_project(self, project: WorkspaceProject) -> None:
        data = self._load_raw()
        data.setdefault("projects", {})[project.name] = {
            "entries": [{"worktree_path": e.worktree_path} for e in project.entries],
        }
        self._save_raw(data)

    def delete_project(self, name: str) -> None:
        data = self._load_raw()
        data.setdefault("projects", {}).pop(name, None)
        self._save_raw(data)

    def rename_project(self, old_name: str, new_name: str, entries: list) -> None:
        data = self._load_raw()
        projects = data.setdefault("projects", {})
        projects.pop(old_name, None)
        projects[new_name] = {
            "entries": [{"worktree_path": e.worktree_path} for e in entries],
        }
        self._save_raw(data)

    def rename_worktree_path(self, old_path: str, new_path: str) -> None:
        data = self._load_raw()
        for project in data.get("projects", {}).values():
            for entry in project.get("entries", []):
                if entry.get("worktree_path") == old_path:
                    entry["worktree_path"] = new_path
        for diff_entry in data.get("ui", {}).get("diff", {}).values():
            if diff_entry.get("worktree_path") == old_path:
                diff_entry["worktree_path"] = new_path
        diff_sel = data.get("ui", {}).get("diff_selection", {})
        if diff_sel.get("worktree_path") == old_path:
            diff_sel["worktree_path"] = new_path
        self._save_raw(data)

    def get_branch_diff_mode(self) -> str:
        return self.get_ui_pref("branch_diff_mode", "merge_base")

    def set_branch_diff_mode(self, mode: str) -> None:
        self.set_ui_pref("branch_diff_mode", mode)

    def get_experimental_features(self) -> bool:
        return bool(self.get_ui_pref("experimental_features", False))

    def set_experimental_features(self, enabled: bool) -> None:
        self.set_ui_pref("experimental_features", enabled)

    def get_github_token(self) -> str | None:
        return self.get_ui_pref("github_token", None)

    def save_github_token(self, token: str) -> None:
        self.set_ui_pref("github_token", token)

    def get_github_poll_interval(self) -> int:
        return int(self.get_ui_pref("github_poll_interval_seconds", 30))

    def save_github_poll_interval(self, seconds: int) -> None:
        self.set_ui_pref("github_poll_interval_seconds", seconds)

    def get_github_total_fetch_interval(self) -> int:
        return int(self.get_ui_pref("github_total_fetch_interval_seconds", 300))

    def save_github_total_fetch_interval(self, seconds: int) -> None:
        self.set_ui_pref("github_total_fetch_interval_seconds", seconds)

    def push_mru(self, action_name: str, args: dict, cap: int = 10) -> None:
        entry = {"action": action_name, "args": dict(args)}
        mru: list = self.get_ui_pref("mru", [])
        mru = [e for e in mru if not (e["action"] == action_name and e["args"] == dict(args))]
        mru.insert(0, entry)
        self.set_ui_pref("mru", mru[:cap])

    def get_mru(self) -> list[dict]:
        return self.get_ui_pref("mru", [])

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
                commands=[
                    SavedCommand(name=c["name"], command=c["command"], startup_pattern=c.get("startup_pattern"))
                    for c in entry.get("commands", [])
                ],
            )
            for path, entry in data["repos"].items()
        }
        return dict(
            sorted(repos.items(), key=lambda kv: kv[1].last_opened, reverse=True)
        )
