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
    error: str | None = None


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

    def load_cleanup_candidates(self, repo_path: str | None, on_progress=None) -> list:
        """Return cleanup candidates for one repo (repo_path) or all repos (None)."""
        self._candidate_repo = {}
        if repo_path is not None:
            candidates = self._repo_vm(repo_path).all_cleanup_candidates(
                on_progress=on_progress
            )
            for c in candidates:
                self._candidate_repo[c.branch] = repo_path
            return candidates
        repos = self.list_repos()
        total_repos = len(repos)
        all_candidates = []
        done = 0
        for path in repos:
            def _sub_progress(cur, tot, lbl, _path=path):
                if on_progress:
                    # map sub-repo progress into overall fraction
                    overall = done + cur
                    overall_total = done + tot + (total_repos - done // max(tot, 1) - 1) * tot
                    on_progress(overall, max(overall_total, 1), lbl)
            candidates = self._repo_vm(path).all_cleanup_candidates(
                on_progress=_sub_progress if on_progress else None
            )
            done += 1
            if on_progress:
                on_progress(done, total_repos, path)
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

    def load_syncable_branches(self, on_progress=None) -> list[BranchRow]:
        excluded_map = self._excluded_map()
        rows: list[BranchRow] = []
        all_branches = []
        for repo_path in self.list_repos():
            for branch in self._git.list_feature_and_main_branches(repo_path):
                all_branches.append((repo_path, branch))
        total = len(all_branches)
        for idx, (repo_path, branch) in enumerate(all_branches, start=1):
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
            if on_progress:
                on_progress(idx, total, branch)
        self._sync_rows = rows
        return rows

    def fetch_all(self, on_progress=None) -> list[FetchResult]:
        repos = self.list_repos()
        total = len(repos)
        results = []
        for idx, repo_path in enumerate(repos, start=1):
            error = self._git.fetch(repo_path)
            results.append(FetchResult(repo_path=repo_path, error=error))
            if on_progress:
                on_progress(idx, total, repo_path)
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
                error=outcome.error,
            )
        outcome = self._git.update_ref_from_remote(repo_path, branch)
        return SyncResult(
            repo_path=repo_path, branch=branch,
            status=outcome.status, error=outcome.error,
        )

    def sync_included(self, on_progress=None) -> list[SyncResult]:
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

        total = len(included)
        results: list[SyncResult] = []
        for idx, row in enumerate(included, start=1):
            if row.worktree_path is not None:
                if self._git.has_uncommitted_changes(row.worktree_path):
                    results.append(SyncResult(
                        repo_path=row.repo_path, branch=row.branch, status="dirty"
                    ))
                    if on_progress:
                        on_progress(idx, total, row.branch)
                    continue
                outcome = self._git.pull_ff_only(row.worktree_path)
                results.append(SyncResult(
                    repo_path=row.repo_path, branch=row.branch,
                    status=outcome.status, new_commits=outcome.new_commits,
                    error=outcome.error,
                ))
            else:
                outcome = self._git.update_ref_from_remote(row.repo_path, row.branch)
                results.append(SyncResult(
                    repo_path=row.repo_path, branch=row.branch,
                    status=outcome.status, error=outcome.error,
                ))
            if on_progress:
                on_progress(idx, total, row.branch)
        return results
