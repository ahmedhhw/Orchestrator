import pytest
from worktree_manager.models import WorktreeModel, RepoConfig


def test_worktree_model_fields():
    wt = WorktreeModel(
        path="/repos/proj-wt/feature-auth",
        branch="feature/auth",
        is_main=False,
        last_commit_ts=1_700_000_000,
        is_merged=False,
        is_stale=False,
    )
    assert wt.path == "/repos/proj-wt/feature-auth"
    assert wt.branch == "feature/auth"
    assert not wt.is_main
    assert not wt.is_merged
    assert not wt.is_stale


def test_worktree_model_main_flag():
    wt = WorktreeModel(
        path="/repos/proj",
        branch="main",
        is_main=True,
        last_commit_ts=1_700_000_000,
        is_merged=False,
        is_stale=False,
    )
    assert wt.is_main


def test_repo_config_defaults():
    cfg = RepoConfig(
        repo_path="/repos/proj",
        worktree_storage="/repos/proj-worktrees",
        stale_days=30,
        last_editor="cursor",
        last_editor_mode="reuse",
        last_opened="2026-05-19T10:00:00",
    )
    assert cfg.stale_days == 30
    assert cfg.last_editor == "cursor"
    assert cfg.last_editor_mode == "reuse"


def test_cleanup_candidate_worktree():
    from worktree_manager.models import CleanupCandidate
    c = CleanupCandidate(
        branch="chore/deps",
        path="/repos/proj-wt/chore-deps",
        is_merged=False,
        is_stale=True,
        last_commit_ts=1_700_000_000,
    )
    assert c.branch == "chore/deps"
    assert c.path == "/repos/proj-wt/chore-deps"
    assert c.is_stale is True
    assert c.is_merged is False


def test_cleanup_candidate_orphan_branch():
    from worktree_manager.models import CleanupCandidate
    c = CleanupCandidate(
        branch="release/1.0",
        path=None,
        is_merged=True,
        is_stale=False,
        last_commit_ts=1_700_000_000,
    )
    assert c.path is None
    assert c.is_merged is True


def test_cleanup_candidate_merged_into_defaults_to_none():
    from worktree_manager.models import CleanupCandidate
    c = CleanupCandidate(branch="fix/a", path=None, is_merged=True, is_stale=False, last_commit_ts=0)
    assert c.merged_into is None


def test_cleanup_candidate_merged_into_can_be_set():
    from worktree_manager.models import CleanupCandidate
    c = CleanupCandidate(
        branch="fix/a", path=None, is_merged=True, is_stale=False,
        last_commit_ts=0, merged_into="feature/payments",
    )
    assert c.merged_into == "feature/payments"


def test_repo_config_vscode_editor():
    cfg = RepoConfig(
        repo_path="/repos/proj",
        worktree_storage="/repos/proj-worktrees",
        stale_days=14,
        last_editor="vscode",
        last_editor_mode="new",
        last_opened="2026-05-19T10:00:00",
    )
    assert cfg.last_editor == "vscode"
    assert cfg.last_editor_mode == "new"
