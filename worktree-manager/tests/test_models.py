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
