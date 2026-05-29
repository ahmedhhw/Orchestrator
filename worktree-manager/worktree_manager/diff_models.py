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
