import concurrent.futures
import json
import logging
import threading
from enum import Enum, auto
from pathlib import Path

import requests

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
        self._unseen_comment_ids_by_pr: dict[int, set[int]] = {}
        self._pr_state_path: Path = store._path.parent / "github_pr_state.json"
        self._pr_state: dict[int, dict] = self._load_pr_state()
        self._known_prs: list[tuple[str, str, int]] = []
        self._login: str = ""
        self._initial_load_done: bool = False
        self._total_fetch_running = False
        self._fetch_lock = threading.Lock()

        token = store.get_github_token()
        if token:
            self._token_state = TokenState.CONFIGURED
            self._init_service(token)
        else:
            self._token_state = TokenState.MISSING

        self._quick_timer = QTimer(self)
        self._quick_timer.timeout.connect(self.quick_fetch)
        self._total_timer = QTimer(self)
        self._total_timer.timeout.connect(self.total_fetch)

        if self._token_state == TokenState.CONFIGURED:
            self._start_timers()
            QTimer.singleShot(0, self.total_fetch)

    @property
    def token_state(self) -> TokenState:
        return self._token_state

    def _init_service(self, token: str) -> None:
        self._svc = GitHubService(token=token)
        log.debug("_init_service: service created")

    def _start_timers(self) -> None:
        self._quick_timer.start(self._store.get_github_poll_interval() * 1000)
        self._total_timer.start(self._store.get_github_total_fetch_interval() * 1000)

    def _stop_timers(self) -> None:
        self._quick_timer.stop()
        self._total_timer.stop()

    def save_token(self, token: str) -> None:
        self._store.save_github_token(token)
        self._init_service(token)
        self._token_state = TokenState.CONFIGURED
        self._start_timers()
        self.token_state_changed.emit()

    def unread_comment_count(self, pr_number: int) -> int:
        return len(self._unseen_comment_ids_by_pr.get(pr_number, set()))

    def mark_pr_comments_seen(self, pr_number: int) -> None:
        self._unseen_comment_ids_by_pr.pop(pr_number, None)

    # ── fetch entry points ────────────────────────────────────────────────────

    def total_fetch(self) -> None:
        if self._svc is None:
            return
        if not self._initial_load_done:
            self.loading_started.emit()
        threading.Thread(target=self._run_total_fetch, daemon=True).start()

    def quick_fetch(self) -> None:
        if self._svc is None:
            return
        with self._fetch_lock:
            if self._total_fetch_running:
                return
        threading.Thread(target=self._run_quick_fetch, daemon=True).start()

    def rescan_repos(self) -> None:
        self._known_prs = []
        self._login = ""
        self.total_fetch()

    # ── fetch internals ───────────────────────────────────────────────────────

    def _run_total_fetch(self) -> None:
        with self._fetch_lock:
            self._total_fetch_running = True
        try:
            if not self._login:
                self._login = self._svc.get_authenticated_user()
            self.fetch_status_changed.emit("Scanning repos & fetching all PRs…")
            self._known_prs = self._svc.discover_open_prs(self._login)
            self._fetch_known_prs()
        except PermissionError:
            self._token_state = TokenState.EXPIRED
            self._stop_timers()
            self.token_state_changed.emit()
        except Exception as exc:
            log.error("total_fetch failed: %s", exc, exc_info=True)
            self.refresh_error.emit(str(exc))
        finally:
            with self._fetch_lock:
                self._total_fetch_running = False

    def _run_quick_fetch(self) -> None:
        try:
            self.fetch_status_changed.emit("Refreshing PRs…")
            self._fetch_known_prs()
        except PermissionError:
            self._token_state = TokenState.EXPIRED
            self._stop_timers()
            self.token_state_changed.emit()
        except Exception as exc:
            log.error("quick_fetch failed: %s", exc, exc_info=True)
            self.refresh_error.emit(str(exc))

    def _fetch_known_prs(self) -> None:
        if not self._known_prs:
            self.prs = []
            self._emit_pr_events(self.prs)
            self._initial_load_done = True
            self.prs_updated.emit()
            self.fetch_status_changed.emit("Tracking: no open PRs found")
            return

        prev_mergeable = {
            p.number: (p.mergeable, p.mergeable_state)
            for p in self.prs if p.mergeable is not None
        }

        results: list[PullRequest] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = {
                pool.submit(self._fetch_one_pr, owner, repo, number): number
                for owner, repo, number in self._known_prs
            }
            for fut in concurrent.futures.as_completed(futures):
                pr = fut.result()
                if pr is not None:
                    results.append(pr)

        for pr in results:
            if pr.mergeable is None and pr.number in prev_mergeable:
                pr.mergeable, pr.mergeable_state = prev_mergeable[pr.number]

        results.sort(key=lambda p: p.number)
        self.prs = results
        self._emit_pr_events(self.prs)
        self._initial_load_done = True
        self.prs_updated.emit()
        repos = sorted({f"{o}/{r}" for o, r, _ in self._known_prs})
        self.fetch_status_changed.emit("Tracking: " + "  ".join(repos))

    def _fetch_one_pr(self, owner: str, repo: str, number: int) -> PullRequest | None:
        seed = PullRequest(
            number=number, title="", body="",
            html_url=f"https://github.com/{owner}/{repo}/pull/{number}",
            head_branch="", base_branch="", state="open", draft=False, mergeable=None,
        )
        try:
            return self._svc.get_pr_detail(number, pr=seed)
        except PermissionError:
            raise
        except requests.HTTPError as exc:
            if "404" in str(exc):
                log.info("PR #%d 404 — dropping (closed?)", number)
                return None
            raise

    # ── notification de-dup ───────────────────────────────────────────────────

    def _load_pr_state(self) -> dict[int, dict]:
        if not self._pr_state_path.exists():
            return {}
        try:
            raw = json.loads(self._pr_state_path.read_text())
            return {
                int(pr_num): {
                    "ci": entry["ci"],
                    "mergeable_state": entry["mergeable_state"],
                    "comment_ids": set(entry["comment_ids"]),
                    "review_keys": {tuple(k) for k in entry["review_keys"]},
                }
                for pr_num, entry in raw.items()
            }
        except Exception:
            log.warning("Failed to load PR state from disk; starting fresh", exc_info=True)
            return {}

    def _save_pr_state(self) -> None:
        if self._known_prs:
            known_numbers = {n for _, _, n in self._known_prs}
            pruned = {
                pr_num: entry
                for pr_num, entry in self._pr_state.items()
                if pr_num in known_numbers
            }
        else:
            pruned = dict(self._pr_state)
        serialisable = {
            str(pr_num): {
                "ci": entry["ci"],
                "mergeable_state": entry["mergeable_state"],
                "comment_ids": list(entry["comment_ids"]),
                "review_keys": [list(k) for k in entry["review_keys"]],
            }
            for pr_num, entry in pruned.items()
        }
        try:
            self._pr_state_path.parent.mkdir(parents=True, exist_ok=True)
            self._pr_state_path.write_text(json.dumps(serialisable, indent=2))
        except Exception:
            log.warning("Failed to save PR state to disk", exc_info=True)

    def _emit_pr_events(self, new_prs: list[PullRequest]) -> None:
        for pr in new_prs:
            state = self._pr_state.get(pr.number)
            curr_ci = pr.ci_status()
            curr_merge = pr.mergeable_state

            if state is None:
                self._pr_state[pr.number] = {
                    "ci": curr_ci,
                    "mergeable_state": curr_merge,
                    "comment_ids": {c.id for c in pr.comments},
                    "review_keys": {(r.author, r.state) for r in pr.reviews},
                }
                continue

            if state["ci"] != curr_ci:
                if curr_ci == "failed":
                    self.pr_event.emit(pr.number, "ci_failed", f'❌ "{pr.title}" — checks failed')
                elif curr_ci == "passed":
                    self.pr_event.emit(pr.number, "ci_passed", f'✅ "{pr.title}" — all checks passed')
                state["ci"] = curr_ci

            if state["mergeable_state"] != curr_merge and pr.mergeability() == "conflicts":
                self.pr_event.emit(pr.number, "pr_conflicts", f'⚠️ "{pr.title}" has merge conflicts')
            state["mergeable_state"] = curr_merge

            for comment in pr.comments:
                if comment.id not in state["comment_ids"]:
                    self.pr_event.emit(pr.number, "new_comment",
                                       f'💬 {comment.author} commented on "{pr.title}"')
                    state["comment_ids"].add(comment.id)
                    self._unseen_comment_ids_by_pr.setdefault(pr.number, set()).add(comment.id)

            for review in pr.reviews:
                key = (review.author, review.state)
                if key not in state["review_keys"]:
                    if review.state == "APPROVED":
                        self.pr_event.emit(pr.number, "review_approved",
                                           f'✅ {review.author} approved "{pr.title}"')
                    elif review.state == "CHANGES_REQUESTED":
                        self.pr_event.emit(pr.number, "review_changes_requested",
                                           f'🔄 {review.author} requested changes on "{pr.title}"')
                    state["review_keys"].add(key)

        self._save_pr_state()

    # ── PR detail / selection ─────────────────────────────────────────────────

    def select_pr(self, pr_number: int) -> None:
        if self._svc is None:
            return
        listed_pr = next((p for p in self.prs if p.number == pr_number), None)
        log.debug("select_pr #%d: listed mergeable=%r", pr_number, listed_pr.mergeable if listed_pr else "N/A")
        self.selected_pr = self._svc.get_pr_detail(pr_number, pr=listed_pr)
        log.debug("select_pr #%d: after get_pr_detail mergeable=%r", pr_number, self.selected_pr.mergeable)
        self.pr_detail_updated.emit()
        self.mark_pr_comments_seen(pr_number)

    def deselect_pr(self) -> None:
        self.selected_pr = None

    # ── polling control ───────────────────────────────────────────────────────

    def pause_polling(self) -> None:
        self._stop_timers()
        self.polling_active = False

    def resume_polling(self) -> None:
        self._start_timers()
        self.polling_active = True

    # ── merge ─────────────────────────────────────────────────────────────────

    def merge_pr(self, pr_number: int, squash: bool = True) -> None:
        if self._svc is None:
            return
        pr = next((p for p in self.prs if p.number == pr_number), None)
        if pr is None:
            return
        self._svc.merge_pr(pr, squash=squash)
        self.pr_event.emit(pr_number, "pr_merged", f'✅ "{pr.title}" merged')
        self.total_fetch()

    # ── repo/branch helpers (used by open-PR form) ────────────────────────────

    def list_open_pr_repos(self) -> list[str]:
        return list(self._store.all_repos().keys())

    def list_open_pr_repos_display(self) -> dict[str, str]:
        paths = list(self._store.all_repos().keys())
        from pathlib import Path
        basenames = [Path(p).name for p in paths]
        seen: dict[str, int] = {}
        for name in basenames:
            seen[name] = seen.get(name, 0) + 1
        result: dict[str, str] = {}
        for path in paths:
            name = Path(path).name
            key = path if seen[name] > 1 else name
            result[key] = path
        return result

    def list_remote_branches_for_repo(self, repo_path: str) -> list[str]:
        try:
            git = GitService()
            return git.list_remote_branches(repo_path)
        except Exception:
            log.warning("list_remote_branches_for_repo: failed for %r", repo_path)
            return []

    def list_branches_for_repo(self, repo_path: str) -> list[str]:
        try:
            git = GitService()
            return git.list_local_branches(repo_path)
        except Exception:
            log.warning("list_branches_for_repo: failed for %r", repo_path)
            return []

    def get_parent_branch_for_repo(
        self, repo_path: str, branch: str, remote_branches: list[str]
    ) -> str | None:
        try:
            git = GitService()
            return git.infer_parent_branch(repo_path, branch, remote_branches)
        except Exception:
            log.warning("get_parent_branch_for_repo: failed for %r branch %r", repo_path, branch)
            return None
