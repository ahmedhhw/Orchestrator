import concurrent.futures
import json
import logging
import threading
from enum import Enum, auto
from pathlib import Path

import requests

from PySide6.QtCore import QObject, QTimer, Signal

from worktree_manager.github_models import CICheck, PullRequest
from worktree_manager.github_service import GitHubService
from worktree_manager.git_service import GitService

log = logging.getLogger(__name__)

RERUN_REFETCH_MS = 4000


class TokenState(Enum):
    MISSING = auto()
    CONFIGURED = auto()
    EXPIRED = auto()


class GitHubViewModel(QObject):
    prs_updated = Signal()
    pr_detail_updated = Signal()
    token_state_changed = Signal()
    refresh_error = Signal(str)
    pr_event = Signal(object, str, str)  # (pr_key tuple, event_type, message)
    loading_started = Signal()
    fetch_status_changed = Signal(str)

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self._store = store
        self._svc: GitHubService | None = None
        self.selected_pr: PullRequest | None = None
        self.polling_active: bool = True
        self._unseen_comment_ids_by_pr: dict[tuple, set[int]] = {}
        self._pr_state_path: Path = store._path.parent / "github_pr_state.json"
        self._pr_state: dict[tuple, dict] = self._load_pr_state()
        self._pr_cache_path: Path = store._path.parent / "github_pr_cache.json"
        self._known_prs: list[tuple[str, str, int]] = []
        self._login: str = ""
        self._initial_load_done: bool = False
        self._total_fetch_running = False
        self._fetch_lock = threading.Lock()

        self.prs: list[PullRequest] = self._load_pr_cache()
        if self.prs:
            self._initial_load_done = True
            self.prs_updated.emit()

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

    def unread_comment_count(self, pr: PullRequest) -> int:
        return len(self._unseen_comment_ids_by_pr.get(pr.pr_key, set()))

    def mark_pr_comments_seen(self, pr: PullRequest) -> None:
        self._unseen_comment_ids_by_pr.pop(pr.pr_key, None)

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
            self.fetch_status_changed.emit("Tracking: no open PRs found")
            self.prs_updated.emit()
            return

        prev_mergeable = {
            p.pr_key: (p.mergeable, p.mergeable_state)
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
            if pr.mergeable is None and pr.pr_key in prev_mergeable:
                pr.mergeable, pr.mergeable_state = prev_mergeable[pr.pr_key]

        results.sort(key=lambda p: p.pr_key)
        self.prs = results
        self._save_pr_cache()
        self._emit_pr_events(self.prs)
        self._initial_load_done = True
        repos = sorted({f"{o}/{r}" for o, r, _ in self._known_prs})
        self.fetch_status_changed.emit("Tracking: " + "  ".join(repos))
        self.prs_updated.emit()

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

    def _load_pr_state(self) -> dict[tuple, dict]:
        if not self._pr_state_path.exists():
            return {}
        try:
            raw = json.loads(self._pr_state_path.read_text())
            result = {}
            for raw_key, entry in raw.items():
                owner, repo, num = raw_key.rsplit("/", 2)
                key = (owner, repo, int(num))
                result[key] = {
                    "ci": entry["ci"],
                    "mergeable_state": entry["mergeable_state"],
                    "comment_ids": set(entry["comment_ids"]),
                    "review_keys": {tuple(k) for k in entry["review_keys"]},
                    "ready": entry.get("ready"),
                }
            return result
        except Exception:
            log.warning("Failed to load PR state from disk; starting fresh", exc_info=True)
            return {}

    def _save_pr_state(self) -> None:
        if self._known_prs:
            known_keys = {(o, r, n) for o, r, n in self._known_prs}
            pruned = {k: v for k, v in self._pr_state.items() if k in known_keys}
        else:
            pruned = dict(self._pr_state)
        serialisable = {
            f"{owner}/{repo}/{num}": {
                "ci": entry["ci"],
                "mergeable_state": entry["mergeable_state"],
                "comment_ids": list(entry["comment_ids"]),
                "review_keys": [list(k) for k in entry["review_keys"]],
                "ready": entry.get("ready"),
            }
            for (owner, repo, num), entry in pruned.items()
        }
        try:
            self._pr_state_path.parent.mkdir(parents=True, exist_ok=True)
            self._pr_state_path.write_text(json.dumps(serialisable, indent=2))
        except Exception:
            log.warning("Failed to save PR state to disk", exc_info=True)

    def _save_pr_cache(self) -> None:
        rows = [
            {
                "number": p.number,
                "title": p.title,
                "html_url": p.html_url,
                "head_branch": p.head_branch,
                "base_branch": p.base_branch,
                "state": p.state,
                "draft": p.draft,
                "mergeable": p.mergeable,
                "mergeable_state": p.mergeable_state,
                "owner": p.owner,
                "repo": p.repo,
                "checks": [
                    {
                        "name": c.name,
                        "status": c.status,
                        "conclusion": c.conclusion,
                        "check_suite_id": c.check_suite_id,
                    }
                    for c in p.checks
                ],
            }
            for p in self.prs
        ]
        try:
            self._pr_cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._pr_cache_path.write_text(json.dumps(rows, indent=2))
        except Exception:
            log.warning("Failed to save PR cache to disk", exc_info=True)

    def _load_pr_cache(self) -> list[PullRequest]:
        if not self._pr_cache_path.exists():
            return []
        try:
            raw = json.loads(self._pr_cache_path.read_text())
            return [
                PullRequest(
                    number=row["number"],
                    title=row["title"],
                    body="",
                    html_url=row["html_url"],
                    head_branch=row["head_branch"],
                    base_branch=row["base_branch"],
                    state=row["state"],
                    draft=row["draft"],
                    mergeable=row["mergeable"],
                    mergeable_state=row["mergeable_state"],
                    owner=row["owner"],
                    repo=row["repo"],
                    checks=[CICheck(**c) for c in row["checks"]],
                )
                for row in raw
            ]
        except Exception:
            log.warning("Failed to load PR cache; starting empty", exc_info=True)
            return []

    def muted_checks_for(self, repo: str) -> set[str]:
        return set(self._store.get_repo_muted_checks(repo))

    def _should_notify(self, pr: PullRequest, event_type: str) -> bool:
        return self._store.get_repo_notification_pref(f"{pr.owner}/{pr.repo}", event_type)

    def _emit_pr_events(self, new_prs: list[PullRequest]) -> None:
        for pr in new_prs:
            pk = pr.pr_key
            state = self._pr_state.get(pk)
            repo_key = f"{pr.owner}/{pr.repo}"
            muted = self.muted_checks_for(repo_key)
            curr_ci = pr.ci_status(muted)
            curr_merge = pr.mergeable_state
            curr_ready = pr.is_ready_to_merge()

            if state is None:
                self._pr_state[pk] = {
                    "ci": curr_ci,
                    "mergeable_state": curr_merge,
                    "comment_ids": {c.id for c in pr.comments},
                    "review_keys": {(r.author, r.state) for r in pr.reviews},
                    "ready": curr_ready,
                }
                continue

            if state["ci"] != curr_ci:
                if curr_ci == "failed" and self._should_notify(pr, "ci_failed"):
                    self.pr_event.emit(pk, "ci_failed", f'❌ "{pr.title}" — checks failed')
                elif curr_ci == "passed" and self._should_notify(pr, "ci_passed"):
                    self.pr_event.emit(pk, "ci_passed", f'✅ "{pr.title}" — all checks passed')
                state["ci"] = curr_ci

            if state["mergeable_state"] != curr_merge and pr.mergeability() == "conflicts":
                if self._should_notify(pr, "pr_conflicts"):
                    self.pr_event.emit(pk, "pr_conflicts", f'⚠️ "{pr.title}" has merge conflicts')
            state["mergeable_state"] = curr_merge

            for comment in pr.comments:
                if comment.id not in state["comment_ids"]:
                    if self._should_notify(pr, "new_comment"):
                        self.pr_event.emit(pk, "new_comment",
                                           f'💬 {comment.author} commented on "{pr.title}"')
                    state["comment_ids"].add(comment.id)
                    self._unseen_comment_ids_by_pr.setdefault(pk, set()).add(comment.id)

            for review in pr.reviews:
                key = (review.author, review.state)
                if key not in state["review_keys"]:
                    if review.state == "APPROVED" and self._should_notify(pr, "review"):
                        self.pr_event.emit(pk, "review_approved",
                                           f'✅ {review.author} approved "{pr.title}"')
                    elif review.state == "CHANGES_REQUESTED" and self._should_notify(pr, "review"):
                        self.pr_event.emit(pk, "review_changes_requested",
                                           f'🔄 {review.author} requested changes on "{pr.title}"')
                    state["review_keys"].add(key)

            if state.get("ready") is False and curr_ready:
                if self._should_notify(pr, "ready_to_merge"):
                    self.pr_event.emit(pk, "ready_to_merge",
                                       f'🟢 "{pr.title}" is ready to merge')
            state["ready"] = curr_ready

        self._save_pr_state()

    # ── PR detail / selection ─────────────────────────────────────────────────

    def select_pr(self, pr: PullRequest) -> None:
        if self._svc is None:
            return
        log.debug("select_pr #%d: instant render from memory, mergeable=%r", pr.number, pr.mergeable)
        self.selected_pr = pr
        self.pr_detail_updated.emit()
        self.mark_pr_comments_seen(pr)
        threading.Thread(target=self._refresh_selected, args=(pr,), daemon=True).start()

    def _refresh_selected(self, pr: PullRequest) -> None:
        try:
            refreshed = self._svc.get_pr_detail(pr.number, pr=pr)
        except PermissionError:
            self._token_state = TokenState.EXPIRED
            self._stop_timers()
            self.token_state_changed.emit()
            return
        except Exception as exc:
            log.error("_refresh_selected #%d failed: %s", pr.number, exc, exc_info=True)
            self.refresh_error.emit(str(exc))
            return
        if self.selected_pr is not None and self.selected_pr.pr_key == pr.pr_key:
            log.debug("_refresh_selected #%d: swapping in fresher data", pr.number)
            self.selected_pr = refreshed
            self.pr_detail_updated.emit()

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

    def merge_pr(self, pr: PullRequest, squash: bool = True) -> None:
        if self._svc is None:
            return
        self._svc.merge_pr(pr, squash=squash)
        self.pr_event.emit(pr.pr_key, "pr_merged", f'✅ "{pr.title}" merged')
        self.total_fetch()

    # ── CI rerun ──────────────────────────────────────────────────────────────

    def retry_failed_cis(self, pr: PullRequest) -> str:
        """Rerun only failed Actions jobs; return a note if some checks can't be re-run."""
        if self._svc is None:
            return ""
        for rid in pr.failed_actions_run_ids():
            self._svc.rerun_failed_jobs(rid, pr)
        skipped = pr.non_rerunnable_failed_count()
        self._optimistically_mark_running(pr, only_failed=True)
        self.pr_event.emit(pr.pr_key, "ci_rerun", f'⏳ Re-running failed checks for #{pr.number}…')
        self._schedule_quick_fetch()
        if not skipped:
            return ""
        noun = "checks" if skipped != 1 else "check"
        return f"({skipped} non-Actions {noun} can't be re-run here)"

    def retry_all_cis(self, pr: PullRequest) -> None:
        """Rerun all CI for the PR.

        Prefers re-running each distinct GitHub Actions workflow run (the
        reliable "Re-run all jobs" path). Falls back to re-requesting the
        whole check suite only when the PR has no Actions runs to drive.
        """
        if self._svc is None:
            return
        run_ids = pr.all_actions_run_ids()
        if run_ids:
            for rid in run_ids:
                self._svc.rerun_workflow(rid, pr)
        else:
            sid = pr.check_suite_id_for_all()
            if sid:
                self._svc.rerun_all_checks(sid, pr)
        self._optimistically_mark_running(pr, only_failed=False)
        self.pr_event.emit(pr.pr_key, "ci_rerun", f'⏳ Re-running all checks for #{pr.number}…')
        self._schedule_quick_fetch()

    def _optimistically_mark_running(self, pr: PullRequest, only_failed: bool) -> None:
        for c in pr.checks:
            target = (c.conclusion == "failure" and c.run_id) if only_failed else True
            if target:
                c.conclusion = None
                c.status = "in_progress"
        self.prs_updated.emit()
        if self.selected_pr is not None and self.selected_pr.pr_key == pr.pr_key:
            self.pr_detail_updated.emit()

    def _schedule_quick_fetch(self) -> None:
        QTimer.singleShot(RERUN_REFETCH_MS, self.quick_fetch)

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
