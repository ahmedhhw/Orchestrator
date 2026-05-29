import json
from pathlib import Path

from worktree_manager.config_store import ConfigStore


def _store(tmp_path):
    return ConfigStore(path=tmp_path / "config.json")


def test_get_diff_pref_returns_none_when_not_set(tmp_path):
    store = _store(tmp_path)
    assert store.get_diff_pref("/repo/myapp") is None


def test_set_and_get_diff_pref(tmp_path):
    store = _store(tmp_path)
    store.set_diff_pref("/repo/myapp", "main", "working_tree_unstaged")
    pref = store.get_diff_pref("/repo/myapp")
    assert pref == {"from_ref": "main", "to_ref": "working_tree_unstaged"}


def test_set_diff_pref_overrides_previous(tmp_path):
    store = _store(tmp_path)
    store.set_diff_pref("/repo/myapp", "main", "working_tree_unstaged")
    store.set_diff_pref("/repo/myapp", "feature/x", "main")
    pref = store.get_diff_pref("/repo/myapp")
    assert pref["from_ref"] == "feature/x"
    assert pref["to_ref"] == "main"


def test_diff_prefs_are_per_repo(tmp_path):
    store = _store(tmp_path)
    store.set_diff_pref("/repo/app1", "main", "working_tree_unstaged")
    store.set_diff_pref("/repo/app2", "feature/y", "main")
    assert store.get_diff_pref("/repo/app1")["from_ref"] == "main"
    assert store.get_diff_pref("/repo/app2")["from_ref"] == "feature/y"


def test_diff_prefs_stored_under_ui_diff_key(tmp_path):
    store = _store(tmp_path)
    store.set_diff_pref("/repo/app", "abc123", "working_tree_staged")
    raw = json.loads((tmp_path / "config.json").read_text())
    assert raw["ui"]["diff"]["/repo/app"]["from_ref"] == "abc123"
