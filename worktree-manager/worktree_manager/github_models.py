from dataclasses import dataclass, field
from urllib.parse import urlparse


@dataclass
class CICheck:
    name: str
    status: str          # queued | in_progress | completed
    conclusion: str | None  # success | failure | neutral | cancelled | skipped | None
    check_suite_id: str | None = None


@dataclass
class Review:
    author: str
    state: str           # APPROVED | CHANGES_REQUESTED | COMMENTED | DISMISSED


@dataclass
class PRComment:
    id: int
    author: str
    body: str
    created_at: str
    seen: bool = False


@dataclass
class PullRequest:
    number: int
    title: str
    body: str
    html_url: str
    head_branch: str
    base_branch: str
    state: str           # open | closed
    draft: bool
    mergeable: bool | None
    checks: list[CICheck] = field(default_factory=list)
    reviews: list[Review] = field(default_factory=list)
    comments: list[PRComment] = field(default_factory=list)
    head_sha: str = field(default="")
    owner: str = field(default="")
    repo: str = field(default="")
    mergeable_state: str = field(default="")

    def __post_init__(self):
        if (not self.owner or not self.repo) and self.html_url:
            parts = urlparse(self.html_url).path.strip("/").split("/")
            if len(parts) >= 2:
                self.owner = parts[0]
                self.repo = parts[1]

    def ci_status(self) -> str:
        """Return 'running', 'failed', 'passed', or 'unknown'."""
        if not self.checks:
            return "unknown"
        conclusions = [c.conclusion for c in self.checks]
        if any(c == "failure" for c in conclusions):
            return "failed"
        if any(c is None for c in conclusions):
            return "running"
        return "passed"

    def mergeability(self) -> str:
        """Return 'mergeable' | 'conflicts' | 'behind' | 'blocked' | 'checking'."""
        if self.mergeable is None:
            return "checking"
        state = self.mergeable_state
        if state == "dirty":
            return "conflicts"
        if state == "behind":
            return "behind"
        if state == "blocked":
            return "blocked"
        if state in ("unknown",):
            return "checking"
        if state in ("clean", "has_hooks", "unstable", ""):
            return "mergeable" if self.mergeable else "checking"
        return "mergeable" if self.mergeable else "conflicts"

    def is_ready_to_merge(self) -> bool:
        #DON'T CHANGE THIS METHOD, I want this to depend on only whether the PR is marked as mergeable by GitHub, 
        #which is what the real UI does.
        return self.mergeable