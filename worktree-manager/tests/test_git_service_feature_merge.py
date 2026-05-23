"""
Integration tests for GitService.build_merged_map using a real git repository.
These tests call actual git commands — no mocking.
"""
import subprocess
import pytest
from worktree_manager.git_service import GitService


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo)] + list(args), check=True, capture_output=True)


def _build_repo(tmp_path, merge_feature_into_main=False):
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-b", "main")
    _git(r, "config", "user.email", "test@test.com")
    _git(r, "config", "user.name", "Test")
    _commit(r, "init")

    _git(r, "checkout", "-b", "fix/other")
    _commit(r, "fix other")
    _git(r, "checkout", "main")
    _git(r, "merge", "--no-ff", "fix/other", "-m", "merge fix/other into main")

    _git(r, "checkout", "-b", "feature/payments")
    _commit(r, "payments init")

    _git(r, "checkout", "-b", "fix/ticket")
    _commit(r, "fix ticket")
    _git(r, "checkout", "feature/payments")
    _git(r, "merge", "--no-ff", "fix/ticket", "-m", "merge fix/ticket into feature/payments")

    if merge_feature_into_main:
        _git(r, "checkout", "main")
        _git(r, "merge", "--no-ff", "feature/payments", "-m", "merge feature/payments into main")
    else:
        _git(r, "checkout", "main")

    return r


def _commit(repo, message, filename=None):
    fname = filename or message.replace(" ", "_") + ".txt"
    (repo / fname).write_text(message)
    _git(repo, "add", fname)
    _git(repo, "commit", "-m", message)


@pytest.fixture
def repo_feature_not_merged_to_main(tmp_path):
    """Real git repo: main → feature/payments (with fix/ticket merged in) + fix/other merged into main.
    feature/payments has NOT been merged back into main."""
    return _build_repo(tmp_path, merge_feature_into_main=False)


@pytest.fixture
def repo_feature_merged_to_main(tmp_path):
    """Same structure, but feature/payments HAS been merged into main afterward."""
    return _build_repo(tmp_path, merge_feature_into_main=True)


@pytest.fixture
def repo(tmp_path):
    """Real git repo: fix/ticket merged into feature/payments only (feature NOT merged into main)."""
    return _build_repo(tmp_path, merge_feature_into_main=False)


def test_branch_merged_only_into_feature_is_attributed_to_feature(repo):
    svc = GitService()
    result = svc.build_merged_map(str(repo), ["main", "feature/payments"])
    assert result.get("fix/ticket") == "feature/payments", (
        f"fix/ticket should be merged_into='feature/payments', got {result.get('fix/ticket')!r}"
    )


def test_branch_merged_into_main_is_attributed_to_main(repo):
    svc = GitService()
    result = svc.build_merged_map(str(repo), ["main", "feature/payments"])
    assert result.get("fix/other") == "main", (
        f"fix/other should be merged_into='main', got {result.get('fix/other')!r}"
    )


def test_feature_branch_itself_not_in_merged_map(repo):
    svc = GitService()
    result = svc.build_merged_map(str(repo), ["main", "feature/payments"])
    assert "feature/payments" not in result, (
        "feature/payments is a target — it must not appear as a key in the merged map"
    )


def test_main_branch_not_in_merged_map(repo):
    svc = GitService()
    result = svc.build_merged_map(str(repo), ["main", "feature/payments"])
    assert "main" not in result, "main is a target — must not appear in merged map"


def test_list_feature_branches_finds_feature_payments(repo):
    svc = GitService()
    branches = svc.list_feature_branches(str(repo))
    assert "feature/payments" in branches


def test_branch_merged_only_into_feature_when_feature_later_merged_to_main(repo_feature_merged_to_main):
    """
    When feature/payments is subsequently merged into main, git branch --merged main
    transitively includes fix/ticket. Since main is iterated first in build_merged_map,
    fix/ticket gets attributed to 'main' rather than 'feature/payments'.
    This test documents the current (expected) behaviour: first-target-wins.
    """
    svc = GitService()
    result = svc.build_merged_map(str(repo_feature_merged_to_main), ["main", "feature/payments"])
    # fix/ticket is reachable from main (transitively via feature/payments),
    # so first-target-wins gives it merged_into="main". This is acceptable.
    assert result.get("fix/ticket") == "main"
    assert result.get("fix/other") == "main"


def test_branch_merged_only_into_feature_not_in_main_map(repo_feature_not_merged_to_main):
    svc = GitService()
    result = svc.build_merged_map(str(repo_feature_not_merged_to_main), ["main", "feature/payments"])
    assert result.get("fix/ticket") == "feature/payments"
    assert result.get("fix/other") == "main"


def test_all_cleanup_candidates_shows_fix_ticket_merged_into_feature(tmp_path):
    """
    Full end-to-end integration: real git repo + real GitService + MainWindowViewModel.
    fix/ticket merged into feature/payments (not main) must appear with merged_into='feature/payments'.
    """
    from worktree_manager.config_store import ConfigStore
    from worktree_manager.models import RepoConfig
    from worktree_manager.main_window_vm import MainWindowViewModel

    repo = _build_repo(tmp_path, merge_feature_into_main=False)
    wt_storage = tmp_path / "worktrees"
    wt_storage.mkdir()

    store = ConfigStore(tmp_path / "config.json")
    store.save_repo(RepoConfig(
        repo_path=str(repo),
        worktree_storage=str(wt_storage),
        stale_days=30,
        last_editor="cursor",
        last_editor_mode="reuse",
        last_opened="2026-05-23T00:00:00",
    ))

    svc = GitService()
    vm = MainWindowViewModel(repo_path=str(repo), config_store=store, git_service=svc)
    vm.load_worktrees()
    candidates = vm.all_cleanup_candidates()

    by_branch = {c.branch: c for c in candidates}

    assert "fix/ticket" in by_branch, "fix/ticket must appear as a cleanup candidate"
    assert by_branch["fix/ticket"].is_merged is True
    assert by_branch["fix/ticket"].merged_into == "feature/payments", (
        f"fix/ticket should be merged_into='feature/payments', got {by_branch['fix/ticket'].merged_into!r}"
    )

    assert "fix/other" in by_branch, "fix/other must appear as a cleanup candidate"
    assert by_branch["fix/other"].merged_into == "main"


def test_branch_merged_only_into_feature_shows_correct_reason_in_group():
    """
    End-to-end: _group_candidates + _reason reflect the correct merged_into target.
    No git needed — uses model objects directly.
    """
    import time
    from worktree_manager.models import CleanupCandidate
    from worktree_manager.ui.cleanup_wizard import _group_candidates, _reason

    now = int(time.time())
    fix_ticket = CleanupCandidate(
        branch="fix/ticket", path=None, is_merged=True, is_stale=False,
        last_commit_ts=now - 5 * 86400, merged_into="feature/payments",
    )
    fix_other = CleanupCandidate(
        branch="fix/other", path=None, is_merged=True, is_stale=False,
        last_commit_ts=now - 5 * 86400, merged_into="main",
    )
    groups = _group_candidates([fix_ticket, fix_other])
    merged_branches = {c.branch: c for c in groups["merged"]}
    assert merged_branches["fix/ticket"].merged_into == "feature/payments"
    assert _reason(merged_branches["fix/ticket"]) == "merged into feature/payments"
    assert _reason(merged_branches["fix/other"]) == "merged into main"
