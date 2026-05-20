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


def test_save_and_load_editor_and_window_mode(store):
    cfg = RepoConfig(
        repo_path="/repos/proj",
        worktree_storage="/repos/proj-wt",
        stale_days=30,
        last_editor="cursor",
        last_editor_mode="reuse",
        last_opened="2026-05-19T10:00:00",
        editor="vscode",
        window_mode="single",
        cur_open_path="/repos/proj-wt/feat",
    )
    store.save_repo(cfg)
    loaded = store.get_repo("/repos/proj")
    assert loaded.editor == "vscode"
    assert loaded.window_mode == "single"
    assert loaded.cur_open_path == "/repos/proj-wt/feat"


def test_defaults_when_fields_missing_from_disk(store, config_path):
    config_path.write_text(json.dumps({
        "repos": {
            "/repos/proj": {
                "worktree_storage": "/repos/proj-wt",
                "stale_days": 30,
                "last_editor": "cursor",
                "last_editor_mode": "reuse",
                "last_opened": "2026-05-19T10:00:00",
            }
        }
    }))
    loaded = store.get_repo("/repos/proj")
    assert loaded.editor == "cursor"
    assert loaded.window_mode == "multi"
    assert loaded.cur_open_path is None


def test_clear_all_open_paths_resets_every_repo(store):
    for path, open_path in [
        ("/repos/a", "/repos/a-wt/feat"),
        ("/repos/b", "/repos/b-wt/fix"),
        ("/repos/c", None),
    ]:
        store.save_repo(RepoConfig(
            repo_path=path,
            worktree_storage=path + "-wt",
            stale_days=30,
            last_editor="cursor",
            last_editor_mode="reuse",
            last_opened="2026-05-20T10:00:00",
            cur_open_path=open_path,
        ))
    store.clear_all_open_paths()
    for path in ("/repos/a", "/repos/b", "/repos/c"):
        assert store.get_repo(path).cur_open_path is None


def test_cur_open_path_can_be_cleared(store):
    cfg = RepoConfig(
        repo_path="/repos/proj",
        worktree_storage="/repos/proj-wt",
        stale_days=30,
        last_editor="cursor",
        last_editor_mode="reuse",
        last_opened="2026-05-19T10:00:00",
        editor="cursor",
        window_mode="single",
        cur_open_path="/repos/proj-wt/feat",
    )
    store.save_repo(cfg)
    cfg.cur_open_path = None
    store.save_repo(cfg)
    assert store.get_repo("/repos/proj").cur_open_path is None
