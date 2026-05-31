import concurrent.futures
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
    fetch_status_changed = Signal(str)

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
        self._known_repos: set[tuple[str, str]] = set()
        self._login: str = ""

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

    def _add_repo_if_new(self, owner: str, repo: str) -> None:
        self._known_repos.add((owner, repo))

    def refresh_prs(self) -> None:
        if self._svc is None:
            log.debug("refresh_prs: no service, skipping")
            return
        self.loading_started.emit()
        try:
            if not self._login:
                self._login = self._svc.get_authenticated_user()
            if not self._known_repos:
                self.fetch_status_changed.emit("Scanning GitHub for repos with your open PRs…")
                self._known_repos = self._svc.discover_open_pr_repos(self._login)

            if not self._known_repos:
                self.prs = []
                self._emit_pr_events(self.prs)
                self.prs_updated.emit()
                self.fetch_status_changed.emit("Tracking: no repos found")
                return

            status_parts: dict[str, str] = {f"{o}/{r}": "⏳" for o, r in self._known_repos}
            self.fetch_status_changed.emit(
                "Fetching: " + "  ".join(f"{k} {v}" for k, v in status_parts.items())
            )

            all_prs: list[PullRequest] = []

            def _fetch_repo(owner_repo: tuple[str, str]) -> list[PullRequest]:
                owner, repo = owner_repo
                prs = self._svc.list_prs_for_repo(owner, repo, self._login)
                checks_futures = {}
                mergeable_futures = {}
                with concurrent.futures.ThreadPoolExecutor() as inner:
                    for pr in prs:
                        if pr.head_sha:
                            checks_futures[pr.number] = inner.submit(
                                self._svc.fetch_check_runs, owner, repo, pr.head_sha
                            )
                        mergeable_futures[pr.number] = inner.submit(
                            self._svc.fetch_mergeable, owner, repo, pr.number
                        )
                for pr in prs:
                    if pr.number in checks_futures:
                        pr.checks = checks_futures[pr.number].result()
                    pr.mergeable = mergeable_futures[pr.number].result()
                return prs

            with concurrent.futures.ThreadPoolExecutor() as pool:
                futures = {pool.submit(_fetch_repo, repo): repo for repo in self._known_repos}
                for future in concurrent.futures.as_completed(futures):
                    owner, repo = futures[future]
                    key = f"{owner}/{repo}"
                    try:
                        repo_prs = future.result()
                        all_prs.extend(repo_prs)
                        status_parts[key] = "✅"
                    except PermissionError:
                        raise
                    except Exception as exc:
                        log.error("fetch failed for %s/%s: %s", owner, repo, exc)
                        status_parts[key] = "❌"
                    self.fetch_status_changed.emit(
                        "Fetching: " + "  ".join(f"{k} {v}" for k, v in status_parts.items())
                    )

            prev_mergeable = {p.number: p.mergeable for p in self.prs if p.mergeable is not None}
            for pr in all_prs:
                if pr.mergeable is None and pr.number in prev_mergeable:
                    pr.mergeable = prev_mergeable[pr.number]
            self.prs = all_prs
            self._emit_pr_events(self.prs)
            self.prs_updated.emit()
            self.fetch_status_changed.emit(
                "Tracking: " + "  ".join(f"{o}/{r}" for o, r in sorted(self._known_repos))
            )
        except PermissionError:
            log.warning("refresh_prs: token expired/invalid")
            self._token_state = TokenState.EXPIRED
            self._timer.stop()
            self.token_state_changed.emit()
        except Exception as exc:
            log.error("refresh_prs: unexpected error: %s", exc, exc_info=True)
            self.refresh_error.emit(str(exc))

    def rescan_repos(self) -> None:
        self._known_repos = set()
        self._login = ""
        self.refresh_prs()

    def _write_mergeable_to_prs(self, pr_number: int, mergeable) -> None:
        for pr in self.prs:
            if pr.number == pr_number:
                pr.mergeable = mergeable
                break

    def select_pr(self, pr_number: int) -> None:
        if self._svc is None:
            return
        listed_pr = next((p for p in self.prs if p.number == pr_number), None)
        log.debug("select_pr #%d: listed mergeable=%r", pr_number, listed_pr.mergeable if listed_pr else "N/A")
        self.selected_pr = self._svc.get_pr_detail(pr_number, pr=listed_pr)
        log.debug("select_pr #%d: after get_pr_detail mergeable=%r", pr_number, self.selected_pr.mergeable)
        self._write_mergeable_to_prs(pr_number, self.selected_pr.mergeable)
        self.pr_detail_updated.emit()
        self.mark_pr_comments_seen(pr_number)
        if self.selected_pr.mergeable is None:
            log.debug("select_pr #%d: mergeable still None, scheduling refetch in 2s", pr_number)
            QTimer.singleShot(2000, lambda: self._refetch_mergeable(pr_number))

    def _refetch_mergeable(self, pr_number: int) -> None:
        if self._svc is None or self.selected_pr is None or self.selected_pr.number != pr_number:
            log.debug("_refetch_mergeable #%d: skipped (pr changed or no service)", pr_number)
            return
        log.debug("_refetch_mergeable #%d: fetching…", pr_number)
        self.selected_pr = self._svc.get_pr_detail(pr_number, pr=self.selected_pr)
        log.debug("_refetch_mergeable #%d: mergeable=%r", pr_number, self.selected_pr.mergeable)
        self._write_mergeable_to_prs(pr_number, self.selected_pr.mergeable)
        self.pr_detail_updated.emit()

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
