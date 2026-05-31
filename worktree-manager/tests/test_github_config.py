import json
import pytest
from pathlib import Path
from worktree_manager.config_store import ConfigStore


@pytest.fixture
def store(tmp_path):
    return ConfigStore(path=tmp_path / "config.json")


def test_get_github_token_returns_none_when_unset(store):
    assert store.get_github_token() is None


def test_save_and_get_github_token(store):
    store.save_github_token("ghp_abc123")
    assert store.get_github_token() == "ghp_abc123"


def test_get_github_poll_interval_default(store):
    assert store.get_github_poll_interval() == 30


def test_save_and_get_github_poll_interval(store):
    store.save_github_poll_interval(60)
    assert store.get_github_poll_interval() == 60


def test_github_token_persisted_to_disk(tmp_path):
    path = tmp_path / "config.json"
    ConfigStore(path=path).save_github_token("ghp_xyz")
    raw = json.loads(path.read_text())
    assert raw["ui"]["github_token"] == "ghp_xyz"


def test_github_poll_interval_persisted_to_disk(tmp_path):
    path = tmp_path / "config.json"
    ConfigStore(path=path).save_github_poll_interval(120)
    raw = json.loads(path.read_text())
    assert raw["ui"]["github_poll_interval_seconds"] == 120
