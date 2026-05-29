import json
import pytest
from pathlib import Path

from worktree_manager.config_store import ConfigStore


def _make_store(tmp_path, initial: dict) -> ConfigStore:
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps(initial))
    return ConfigStore(path=cfg)


def test_rename_worktree_path_updates_project_entries(tmp_path):
    store = _make_store(tmp_path, {
        "repos": {},
        "projects": {
            "myproject": {
                "entries": [
                    {"worktree_path": "/repos/app/worktrees/feature-foo"},
                    {"worktree_path": "/repos/app/worktrees/main"},
                ]
            }
        },
    })
    store.rename_worktree_path(
        "/repos/app/worktrees/feature-foo",
        "/repos/app/worktrees/feature-bar",
    )
    project = store.get_project("myproject")
    paths = [e.worktree_path for e in project.entries]
    assert "/repos/app/worktrees/feature-bar" in paths
    assert "/repos/app/worktrees/feature-foo" not in paths
    assert "/repos/app/worktrees/main" in paths


def test_rename_worktree_path_updates_diff_prefs(tmp_path):
    store = _make_store(tmp_path, {
        "repos": {},
        "ui": {
            "diff": {
                "/repos/app": {
                    "from_ref": "working_tree_unstaged",
                    "to_ref": "main",
                    "worktree_path": "/repos/app/worktrees/feature-foo",
                }
            }
        },
    })
    store.rename_worktree_path(
        "/repos/app/worktrees/feature-foo",
        "/repos/app/worktrees/feature-bar",
    )
    data = json.loads((tmp_path / "config.json").read_text())
    diff_entry = data["ui"]["diff"]["/repos/app"]
    assert diff_entry["worktree_path"] == "/repos/app/worktrees/feature-bar"


def test_rename_worktree_path_updates_diff_selection(tmp_path):
    store = _make_store(tmp_path, {
        "repos": {},
        "ui": {
            "diff_selection": {
                "repo_path": "/repos/app",
                "worktree_path": "/repos/app/worktrees/feature-foo",
            }
        },
    })
    store.rename_worktree_path(
        "/repos/app/worktrees/feature-foo",
        "/repos/app/worktrees/feature-bar",
    )
    data = json.loads((tmp_path / "config.json").read_text())
    assert data["ui"]["diff_selection"]["worktree_path"] == "/repos/app/worktrees/feature-bar"


def test_rename_worktree_path_no_match_is_noop(tmp_path):
    initial = {
        "repos": {},
        "projects": {
            "p": {"entries": [{"worktree_path": "/repos/app/worktrees/main"}]}
        },
    }
    store = _make_store(tmp_path, initial)
    store.rename_worktree_path("/repos/app/worktrees/missing", "/repos/app/worktrees/new")
    project = store.get_project("p")
    assert project.entries[0].worktree_path == "/repos/app/worktrees/main"
