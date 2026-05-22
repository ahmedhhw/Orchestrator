from dataclasses import dataclass, field


@dataclass
class WindowRecord:
    repo_path: str
    worktree_path: str
    editor: str
    pid: int
    proc: object = field(default=None, repr=False, compare=False)


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
    merged_into: str | None = None
    has_uncommitted: bool = False
    is_checked_out: bool = False


@dataclass
class SavedCommand:
    name: str
    command: str


@dataclass
class WorkspaceEntry:
    worktree_path: str


@dataclass
class WorkspaceProject:
    name: str
    entries: list = field(default_factory=list)


@dataclass
class RepoConfig:
    repo_path: str
    worktree_storage: str
    stale_days: int
    last_editor: str
    last_editor_mode: str
    last_opened: str
    commands: list = field(default_factory=list)
