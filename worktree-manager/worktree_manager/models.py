from dataclasses import dataclass


@dataclass
class WorktreeModel:
    path: str
    branch: str
    is_main: bool
    last_commit_ts: int
    is_merged: bool
    is_stale: bool


@dataclass
class CleanupCandidate:
    branch: str
    path: str | None
    is_merged: bool
    is_stale: bool
    last_commit_ts: int


@dataclass
class RepoConfig:
    repo_path: str
    worktree_storage: str
    stale_days: int
    last_editor: str
    last_editor_mode: str
    last_opened: str
