import pytest
from pathlib import Path
from worktree_manager.config_store import ConfigStore


def test_branch_diff_mode_defaults_to_merge_base(tmp_path):
    store = ConfigStore(tmp_path / "config.json")
    assert store.get_branch_diff_mode() == "merge_base"


def test_set_branch_diff_mode_persists(tmp_path):
    store = ConfigStore(tmp_path / "config.json")
    store.set_branch_diff_mode("branch_tip")
    store2 = ConfigStore(tmp_path / "config.json")
    assert store2.get_branch_diff_mode() == "branch_tip"


def test_set_branch_diff_mode_back_to_merge_base(tmp_path):
    store = ConfigStore(tmp_path / "config.json")
    store.set_branch_diff_mode("branch_tip")
    store.set_branch_diff_mode("merge_base")
    assert store.get_branch_diff_mode() == "merge_base"
