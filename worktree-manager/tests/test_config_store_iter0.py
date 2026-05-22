import pytest
from worktree_manager.config_store import ConfigStore
from worktree_manager.models import RepoConfig


@pytest.fixture
def store(tmp_path):
    s = ConfigStore(tmp_path / "config.json")
    s.save_repo(RepoConfig(
        repo_path="/repos/proj",
        worktree_storage="/repos/proj-wt",
        stale_days=30,
        last_editor="cursor",
        last_editor_mode="reuse",
        last_opened="2026-05-19T10:00:00",
    ))
    return s


def test_repo_config_has_no_editor_field():
    cfg = RepoConfig(
        repo_path="/repos/proj",
        worktree_storage="/repos/proj-wt",
        stale_days=30,
        last_editor="cursor",
        last_editor_mode="reuse",
        last_opened="2026-05-19T10:00:00",
    )
    assert not hasattr(cfg, "editor")


def test_repo_config_has_no_window_mode_field():
    cfg = RepoConfig(
        repo_path="/repos/proj",
        worktree_storage="/repos/proj-wt",
        stale_days=30,
        last_editor="cursor",
        last_editor_mode="reuse",
        last_opened="2026-05-19T10:00:00",
    )
    assert not hasattr(cfg, "window_mode")


def test_repo_config_has_no_cur_open_path_field():
    cfg = RepoConfig(
        repo_path="/repos/proj",
        worktree_storage="/repos/proj-wt",
        stale_days=30,
        last_editor="cursor",
        last_editor_mode="reuse",
        last_opened="2026-05-19T10:00:00",
    )
    assert not hasattr(cfg, "cur_open_path")


def test_save_and_load_repo_roundtrips_without_editor_fields(store):
    cfg = store.get_repo("/repos/proj")
    assert not hasattr(cfg, "editor")
    assert not hasattr(cfg, "window_mode")
    assert not hasattr(cfg, "cur_open_path")


def test_clear_all_open_paths_no_longer_exists(store):
    assert not hasattr(store, "clear_all_open_paths")
