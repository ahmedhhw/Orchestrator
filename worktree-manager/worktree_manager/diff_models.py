from dataclasses import dataclass, field
from typing import Literal


@dataclass
class HistoryPoint:
    kind: Literal["working_tree_unstaged", "working_tree_staged", "commit", "branch"]
    label: str
    short_sha: str = ""
    message: str = ""


@dataclass
class DiffFile:
    path: str
    status: Literal["M", "A", "D", "R", "?"]
    old_path: str = ""


@dataclass
class DiffHunk:
    index: int
    header: str
    lines: list
    old_start: int = 0
    old_count: int = 0
    new_start: int = 0
    new_count: int = 0
