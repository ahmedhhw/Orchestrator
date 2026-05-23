import json
import pytest
from pathlib import Path
from worktree_manager.config_store import ConfigStore
from worktree_manager.models import RepoConfig


@pytest.fixture
def config_path(tmp_path):
    return tmp_path / "config.json"


@pytest.fixture
def store(config_path):
    return ConfigStore(config_path)


def test_load_returns_empty_when_file_missing(store):
    assert store.all_repos() == {}


def test_save_and_load_repo(store):
    cfg = RepoConfig(
        repo_path="/repos/proj",
        worktree_storage="/repos/proj-wt",
        stale_days=30,
        last_editor="cursor",
        last_editor_mode="reuse",
        last_opened="2026-05-19T10:00:00",
    )
    store.save_repo(cfg)
    loaded = store.get_repo("/repos/proj")
    assert loaded is not None
    assert loaded.worktree_storage == "/repos/proj-wt"
    assert loaded.stale_days == 30
    assert loaded.last_editor == "cursor"


def test_save_persists_to_disk(store, config_path):
    cfg = RepoConfig(
        repo_path="/repos/proj",
        worktree_storage="/repos/proj-wt",
        stale_days=30,
        last_editor="vscode",
        last_editor_mode="new",
        last_opened="2026-05-19T10:00:00",
    )
    store.save_repo(cfg)
    raw = json.loads(config_path.read_text())
    assert "/repos/proj" in raw["repos"]
    assert raw["repos"]["/repos/proj"]["last_editor"] == "vscode"


def test_get_repo_returns_none_for_unknown(store):
    assert store.get_repo("/repos/nonexistent") is None


def test_all_repos_sorted_by_last_opened(store):
    for path, ts in [
        ("/repos/a", "2026-01-01T00:00:00"),
        ("/repos/b", "2026-03-01T00:00:00"),
        ("/repos/c", "2026-02-01T00:00:00"),
    ]:
        store.save_repo(RepoConfig(
            repo_path=path,
            worktree_storage=path + "-wt",
            stale_days=30,
            last_editor="cursor",
            last_editor_mode="reuse",
            last_opened=ts,
        ))
    repos = list(store.all_repos().values())
    assert repos[0].repo_path == "/repos/b"
    assert repos[1].repo_path == "/repos/c"
    assert repos[2].repo_path == "/repos/a"


def test_update_existing_repo(store):
    cfg = RepoConfig(
        repo_path="/repos/proj",
        worktree_storage="/repos/proj-wt",
        stale_days=30,
        last_editor="cursor",
        last_editor_mode="reuse",
        last_opened="2026-05-19T10:00:00",
    )
    store.save_repo(cfg)
    cfg.stale_days = 60
    store.save_repo(cfg)
    assert store.get_repo("/repos/proj").stale_days == 60


def _make_cfg(path):
    return RepoConfig(
        repo_path=path,
        worktree_storage=path + "-wt",
        stale_days=30,
        last_editor="cursor",
        last_editor_mode="new",
        last_opened="2026-01-01T00:00:00",
    )


def test_delete_repo_removes_entry(store):
    store.save_repo(_make_cfg("/repos/alpha"))
    store.save_repo(_make_cfg("/repos/beta"))
    store.delete_repo("/repos/alpha")
    assert store.get_repo("/repos/alpha") is None
    assert store.get_repo("/repos/beta") is not None


def test_delete_repo_persists_to_disk(store):
    store.save_repo(_make_cfg("/repos/alpha"))
    store.delete_repo("/repos/alpha")
    assert store.get_repo("/repos/alpha") is None


def test_delete_repo_absent_key_is_noop(store):
    store.delete_repo("/repos/nonexistent")
    assert store.all_repos() == {}


def test_delete_repo_preserves_commands_of_other_repos(store):
    from worktree_manager.models import SavedCommand
    store.save_repo(_make_cfg("/repos/alpha"))
    store.save_repo(_make_cfg("/repos/beta"))
    store.save_command("/repos/beta", SavedCommand(name="test", command="pytest"))
    store.delete_repo("/repos/alpha")
    cmds = store.get_commands("/repos/beta")
    assert len(cmds) == 1
    assert cmds[0].name == "test"

