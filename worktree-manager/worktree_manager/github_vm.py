import logging
from enum import Enum, auto

from PySide6.QtCore import QObject, QTimer, Signal

from worktree_manager.github_models import PullRequest
from worktree_manager.github_service import GitHubService
from worktree_manager.git_service import GitService

log = logging.getLogger(__name__)


class TokenState(Enum):
    MISSING = auto()
    CONFIGURED = auto()
    EXPIRED = auto()


class GitHubViewModel(QObject):
    prs_updated = Signal()
    pr_detail_updated = Signal()
    token_state_changed = Signal()
    refresh_error = Signal(str)
    pr_event = Signal(int, str, str)  # (pr_number, event_type, message)
    loading_started = Signal()

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self._store = store
        self._svc: GitHubService | None = None
        self.prs: list[PullRequest] = []
        self.selected_pr: PullRequest | None = None
        self.polling_active: bool = True
        self._pr_snapshots: dict[int, PullRequest] = {}
        self._seen_comment_ids: set[int] = set()
        self._unseen_comment_ids_by_pr: dict[int, set[int]] = {}

        token = store.get_github_token()
        if token:
            self._token_state = TokenState.CONFIGURED
            self._init_service(token)
        else:
            self._token_state = TokenState.MISSING

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_poll)
        if self._token_state == TokenState.CONFIGURED:
            interval_ms = store.get_github_poll_interval() * 1000
            self._timer.start(interval_ms)
            QTimer.singleShot(0, self.refresh_prs)

    @property
    def token_state(self) -> TokenState:
        return self._token_state

    def _init_service(self, token: str) -> None:
        self._svc = GitHubService(token=token)
        log.debug("_init_service: service created")

    def save_token(self, token: str) -> None:
        self._store.save_github_token(token)
        self._init_service(token)
        self._token_state = TokenState.CONFIGURED
        interval_ms = self._store.get_github_poll_interval() * 1000
        self._timer.start(interval_ms)
        self.token_state_changed.emit()

    def unread_comment_count(self, pr_number: int) -> int:
        return len(self._unseen_comment_ids_by_pr.get(pr_number, set()))

    def mark_pr_comments_seen(self, pr_number: int) -> None:
        self._unseen_comment_ids_by_pr.pop(pr_number, None)

    def _emit_pr_events(self, new_prs: list[PullRequest]) -> None:
        for pr in new_prs:
            prev = self._pr_snapshots.get(pr.number)
            if prev is None:
                self._pr_snapshots[pr.number] = pr
                continue

            prev_ci = prev.ci_status()
            curr_ci = pr.ci_status()
            if prev_ci != "failed" and curr_ci == "failed":
                self.pr_event.emit(pr.number, "ci_failed", f'❌ "{pr.title}" — checks failed')
            elif prev_ci != "passed" and curr_ci == "passed":
                self.pr_event.emit(pr.number, "ci_passed", f'✅ "{pr.title}" — all checks passed')

            prev_comment_ids = {c.id for c in prev.comments}
            for comment in pr.comments:
                if comment.id not in prev_comment_ids:
                    self.pr_event.emit(pr.number, "new_comment", f'💬 {comment.author} commented on "{pr.title}"')
                    self._unseen_comment_ids_by_pr.setdefault(pr.number, set()).add(comment.id)
                    self._seen_comment_ids.add(comment.id)

            prev_review_authors = {(r.author, r.state) for r in prev.reviews}
            for review in pr.reviews:
                if (review.author, review.state) not in prev_review_authors:
                    if review.state == "APPROVED":
                        self.pr_event.emit(pr.number, "review_approved", f'✅ {review.author} approved "{pr.title}"')
                    elif review.state == "CHANGES_REQUESTED":
                        self.pr_event.emit(pr.number, "review_changes_requested", f'🔄 {review.author} requested changes on "{pr.title}"')

            self._pr_snapshots[pr.number] = pr

    def refresh_prs(self) -> None:
        if self._svc is None:
            log.debug("refresh_prs: no service, skipping")
            return
        self.loading_started.emit()
        log.debug("refresh_prs: calling list_my_open_prs")
        try:
            self.prs = self._svc.list_my_open_prs()
            log.debug("refresh_prs: got %d PRs", len(self.prs))
            self._emit_pr_events(self.prs)
            self.prs_updated.emit()
        except PermissionError:
            log.warning("refresh_prs: token expired/invalid")
            self._token_state = TokenState.EXPIRED
            self._timer.stop()
            self.token_state_changed.emit()
        except Exception as exc:
            log.error("refresh_prs: unexpected error: %s", exc, exc_info=True)
            self.refresh_error.emit(str(exc))

    def select_pr(self, pr_number: int) -> None:
        if self._svc is None:
            return
        listed_pr = next((p for p in self.prs if p.number == pr_number), None)
        self.selected_pr = self._svc.get_pr_detail(pr_number, pr=listed_pr)
        self.pr_detail_updated.emit()
        self.mark_pr_comments_seen(pr_number)

    def deselect_pr(self) -> None:
        self.selected_pr = None

    def pause_polling(self) -> None:
        self._timer.stop()
        self.polling_active = False

    def resume_polling(self) -> None:
        interval_ms = self._store.get_github_poll_interval() * 1000
        self._timer.start(interval_ms)
        self.polling_active = True

    def merge_pr(self, pr_number: int, squash: bool = True) -> None:
        if self._svc is None:
            return
        pr = next((p for p in self.prs if p.number == pr_number), None)
        if pr is None:
            return
        self._svc.merge_pr(pr, squash=squash)
        self.pr_event.emit(pr_number, "pr_merged", f'✅ "{pr.title}" merged')
        self.refresh_prs()

    def list_open_pr_repos(self) -> list[str]:
        """Return local repo paths known to the app."""
        return list(self._store.all_repos().keys())

    def list_remote_branches_for_repo(self, repo_path: str) -> list[str]:
        """Return remote branch names via git branch -r for the given repo path."""
        try:
            git = GitService()
            return git.list_remote_branches(repo_path)
        except Exception:
            log.warning("list_remote_branches_for_repo: failed for %r", repo_path)
            return []

    def list_branches_for_repo(self, repo_path: str) -> list[str]:
        """Return local branch names for the given repo path."""
        try:
            git = GitService()
            return git.list_local_branches(repo_path)
        except Exception:
            log.warning("list_branches_for_repo: failed for %r", repo_path)
            return []

    def get_parent_branch_for_repo(
        self, repo_path: str, branch: str, remote_branches: list[str]
    ) -> str | None:
        """Return the inferred parent branch if it exists in remote_branches, else None."""
        try:
            git = GitService()
            return git.infer_parent_branch(repo_path, branch, remote_branches)
        except Exception:
            log.warning("get_parent_branch_for_repo: failed for %r branch %r", repo_path, branch)
            return None

    def _on_poll(self) -> None:
        self.refresh_prs()
        if self.selected_pr is not None:
            self.select_pr(self.selected_pr.number)
