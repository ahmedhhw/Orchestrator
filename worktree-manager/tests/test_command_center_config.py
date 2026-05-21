import json
import pytest
from pathlib import Path
from worktree_manager.config_store import ConfigStore
from worktree_manager.models import RepoConfig, SavedCommand


@pytest.fixture
def config_path(tmp_path):
    return tmp_path / "config.json"


@pytest.fixture
def store(config_path):
    return ConfigStore(config_path)


@pytest.fixture
def repo_path(store):
    store.save_repo(RepoConfig(
        repo_path="/repos/proj",
        worktree_storage="/repos/proj-wt",
        stale_days=30,
        last_editor="cursor",
        last_editor_mode="reuse",
        last_opened="2026-05-20T10:00:00",
    ))
    return "/repos/proj"


def test_get_commands_returns_empty_for_new_repo(store, repo_path):
    assert store.get_commands(repo_path) == []


def test_save_command_persists(store, repo_path):
    store.save_command(repo_path, SavedCommand(name="frontend", command="npm run dev"))
    cmds = store.get_commands(repo_path)
    assert len(cmds) == 1
    assert cmds[0].name == "frontend"
    assert cmds[0].command == "npm run dev"


def test_save_multiple_commands(store, repo_path):
    store.save_command(repo_path, SavedCommand(name="frontend", command="npm run dev"))
    store.save_command(repo_path, SavedCommand(name="backend", command="python manage.py runserver"))
    cmds = store.get_commands(repo_path)
    assert len(cmds) == 2
    assert {c.name for c in cmds} == {"frontend", "backend"}


def test_save_command_writes_to_disk(store, repo_path, config_path):
    store.save_command(repo_path, SavedCommand(name="frontend", command="npm run dev"))
    raw = json.loads(config_path.read_text())
    assert raw["repos"][repo_path]["commands"] == [
        {"name": "frontend", "command": "npm run dev"}
    ]


def test_save_command_updates_existing_name(store, repo_path):
    store.save_command(repo_path, SavedCommand(name="frontend", command="npm run dev"))
    store.save_command(repo_path, SavedCommand(name="frontend", command="npm run build"))
    cmds = store.get_commands(repo_path)
    assert len(cmds) == 1
    assert cmds[0].command == "npm run build"


def test_delete_command_removes_by_name(store, repo_path):
    store.save_command(repo_path, SavedCommand(name="frontend", command="npm run dev"))
    store.save_command(repo_path, SavedCommand(name="backend", command="python manage.py runserver"))
    store.delete_command(repo_path, "frontend")
    cmds = store.get_commands(repo_path)
    assert len(cmds) == 1
    assert cmds[0].name == "backend"


def test_delete_command_noop_for_unknown_name(store, repo_path):
    store.save_command(repo_path, SavedCommand(name="frontend", command="npm run dev"))
    store.delete_command(repo_path, "nonexistent")
    assert len(store.get_commands(repo_path)) == 1


def test_get_commands_returns_empty_when_key_missing_from_disk(store, config_path):
    config_path.write_text(json.dumps({
        "repos": {
            "/repos/proj": {
                "worktree_storage": "/repos/proj-wt",
                "stale_days": 30,
                "last_editor": "cursor",
                "last_editor_mode": "reuse",
                "last_opened": "2026-05-20T10:00:00",
            }
        }
    }))
    assert store.get_commands("/repos/proj") == []


def test_get_repo_loads_commands(store, repo_path):
    store.save_command(repo_path, SavedCommand(name="frontend", command="npm run dev"))
    cfg = store.get_repo(repo_path)
    assert len(cfg.commands) == 1
    assert cfg.commands[0].name == "frontend"
