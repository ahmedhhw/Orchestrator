from dataclasses import dataclass, field

from worktree_manager.config_store import ConfigStore
from worktree_manager.git_service import GitService
from worktree_manager.main_window_vm import MainWindowViewModel

_EXCLUDED_PREF_KEY = "branch_sync_excluded"


@dataclass
class BranchRow:
    repo_path: str
    branch: str
    has_upstream: bool
    ahead: int
    behind: int
    worktree_path: str | None
    has_uncommitted: bool
    excluded: bool


@dataclass
class FetchResult:
    repo_path: str
    error: str | None = None


@dataclass
class SyncResult:
    repo_path: str
    branch: str
    status: str           # "up_to_date"|"pulled"|"dirty"|"non_ff"|"no_upstream"|"error"
    new_commits: int = 0


class BranchMgmtViewModel:
    def __init__(self, config_store: ConfigStore, git_service: GitService):
        self._store = config_store
        self._git = git_service
        # Maps candidate branch name → repo_path; populated during load_cleanup_candidates.
        self._candidate_repo: dict[str, str] = {}

    def list_repos(self) -> list[str]:
        return list(self._store.all_repos().keys())

    def _repo_vm(self, repo_path: str) -> MainWindowViewModel:
        vm = MainWindowViewModel(
            repo_path=repo_path,
            config_store=self._store,
            git_service=self._git,
        )
        vm.load_worktrees()
        return vm

    def load_cleanup_candidates(self, repo_path: str | None) -> list:
        """Return cleanup candidates for one repo (repo_path) or all repos (None)."""
        self._candidate_repo = {}
        if repo_path is not None:
            candidates = self._repo_vm(repo_path).all_cleanup_candidates()
            for c in candidates:
                self._candidate_repo[c.branch] = repo_path
            return candidates
        all_candidates = []
        for path in self.list_repos():
            candidates = self._repo_vm(path).all_cleanup_candidates()
            for c in candidates:
                self._candidate_repo[c.branch] = path
            all_candidates.extend(candidates)
        return all_candidates

    def delete_cleanup_selection(self, repo_path: str | None, candidates: list) -> None:
        """Delete selected candidates. If repo_path is None, route each to its repo."""
        if repo_path is not None:
            self._repo_vm(repo_path).delete_cleanup_candidates(
                candidates, also_delete_branches=True
            )
            return
        # Group by repo using the mapping built during the last load.
        by_repo: dict[str, list] = {}
        for c in candidates:
            r = self._candidate_repo.get(c.branch)
            if r is None:
                continue
            by_repo.setdefault(r, []).append(c)
        for r, group in by_repo.items():
            self._repo_vm(r).delete_cleanup_candidates(group, also_delete_branches=True)

    # ── sync half ──────────────────────────────────────────────────────────────

    def _excluded_map(self) -> dict:
        return self._store.get_ui_pref(_EXCLUDED_PREF_KEY, {}) or {}

    def set_excluded(self, repo_path: str, branch: str, excluded: bool) -> None:
        key = f"{repo_path}::{branch}"
        mapping = dict(self._excluded_map())
        if excluded:
            mapping[key] = True
        else:
            mapping.pop(key, None)
        self._store.set_ui_pref(_EXCLUDED_PREF_KEY, mapping)

    def load_syncable_branches(self) -> list[BranchRow]:
        excluded_map = self._excluded_map()
        rows: list[BranchRow] = []
        for repo_path in self.list_repos():
            branches = self._git.list_feature_and_main_branches(repo_path)
            for branch in branches:
                status = self._git.upstream_status(repo_path, branch)
                wt_path = self._git.worktree_for_branch(repo_path, branch)
                has_uncommitted = (
                    self._git.has_uncommitted_changes(wt_path)
                    if wt_path else False
                )
                key = f"{repo_path}::{branch}"
                rows.append(BranchRow(
                    repo_path=repo_path,
                    branch=branch,
                    has_upstream=status.has_upstream,
                    ahead=status.ahead,
                    behind=status.behind,
                    worktree_path=wt_path,
                    has_uncommitted=has_uncommitted,
                    excluded=bool(excluded_map.get(key)),
                ))
        self._sync_rows = rows
        return rows

    def fetch_all(self) -> list[FetchResult]:
        results = []
        for repo_path in self.list_repos():
            error = self._git.fetch(repo_path)
            results.append(FetchResult(repo_path=repo_path, error=error))
        return results

    def sync_one(
        self, repo_path: str, branch: str, worktree_path: str | None
    ) -> SyncResult:
        self._git.fetch(repo_path)
        if worktree_path is not None:
            if self._git.has_uncommitted_changes(worktree_path):
                return SyncResult(repo_path=repo_path, branch=branch, status="dirty")
            outcome = self._git.pull_ff_only(worktree_path)
            return SyncResult(
                repo_path=repo_path, branch=branch,
                status=outcome.status, new_commits=outcome.new_commits,
            )
        outcome = self._git.update_ref_from_remote(repo_path, branch)
        return SyncResult(
            repo_path=repo_path, branch=branch,
            status=outcome.status,
        )

    def sync_included(self) -> list[SyncResult]:
        rows = getattr(self, "_sync_rows", None)
        if rows is None:
            rows = self.load_syncable_branches()

        included = [r for r in rows if not r.excluded and r.has_upstream]
        # fetch each repo once
        fetched: set[str] = set()
        for row in included:
            if row.repo_path not in fetched:
                self._git.fetch(row.repo_path)
                fetched.add(row.repo_path)

        results: list[SyncResult] = []
        for row in included:
            if row.worktree_path is not None:
                if self._git.has_uncommitted_changes(row.worktree_path):
                    results.append(SyncResult(
                        repo_path=row.repo_path, branch=row.branch, status="dirty"
                    ))
                    continue
                outcome = self._git.pull_ff_only(row.worktree_path)
                results.append(SyncResult(
                    repo_path=row.repo_path, branch=row.branch,
                    status=outcome.status, new_commits=outcome.new_commits,
                ))
            else:
                outcome = self._git.update_ref_from_remote(row.repo_path, row.branch)
                results.append(SyncResult(
                    repo_path=row.repo_path, branch=row.branch, status=outcome.status,
                ))
        return results
