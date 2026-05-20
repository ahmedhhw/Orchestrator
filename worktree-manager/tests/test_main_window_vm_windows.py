import pytest
import time
from unittest.mock import MagicMock, patch
from worktree_manager.config_store import ConfigStore
from worktree_manager.git_service import GitService
from worktree_manager.editor_service import EditorService
from worktree_manager.models import RepoConfig, WorktreeModel
from worktree_manager.main_window_vm import MainWindowViewModel


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
        editor="cursor",
        window_mode="multi",
        cur_open_path=None,
    ))
    return s


@pytest.fixture
def git():
    g = MagicMock(spec=GitService)
    now = int(time.time())
    g.list_worktrees.return_value = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
        WorktreeModel("/repos/proj-wt/feat", "feature/auth", False, now - 3600, False, False),
    ]
    g.list_local_branches.return_value = ["main", "feature/auth"]
    return g


@pytest.fixture
def editor():
    return MagicMock(spec=EditorService)


@pytest.fixture
def vm(store, git, editor):
    m = MainWindowViewModel(
        repo_path="/repos/proj",
        config_store=store,
        git_service=git,
        editor_service=editor,
    )
    m.load_worktrees()
    return m


# --- open_worktree: multi-window mode ---

def test_open_worktree_multi_calls_open_new(vm, editor):
    vm.open_worktree("/repos/proj-wt/feat")
    editor.open_new.assert_called_once_with("/repos/proj-wt/feat", editor="cursor")


def test_open_worktree_multi_does_not_update_cur_open_path(vm, store):
    vm.open_worktree("/repos/proj-wt/feat")
    assert store.get_repo("/repos/proj").cur_open_path is None


# --- open_worktree: single-window mode, no prior open ---

def test_open_worktree_single_no_cur_calls_open_new(vm, editor, store):
    cfg = store.get_repo("/repos/proj")
    cfg.window_mode = "single"
    store.save_repo(cfg)
    vm.open_worktree("/repos/proj-wt/feat")
    editor.open_new.assert_called_once_with("/repos/proj-wt/feat", editor="cursor")


def test_open_worktree_single_no_cur_saves_cur_open_path(vm, store):
    cfg = store.get_repo("/repos/proj")
    cfg.window_mode = "single"
    store.save_repo(cfg)
    vm.open_worktree("/repos/proj-wt/feat")
    assert store.get_repo("/repos/proj").cur_open_path == "/repos/proj-wt/feat"


# --- open_worktree: single-window mode, prior open exists ---

def test_open_worktree_single_with_cur_calls_open_replacing(vm, editor, store):
    cfg = store.get_repo("/repos/proj")
    cfg.window_mode = "single"
    cfg.cur_open_path = "/repos/proj-wt/old"
    store.save_repo(cfg)
    vm.open_worktree("/repos/proj-wt/feat")
    editor.open_replacing.assert_called_once_with(
        cur_path="/repos/proj-wt/old",
        new_path="/repos/proj-wt/feat",
        editor="cursor",
    )


def test_open_worktree_single_with_cur_updates_cur_open_path(vm, store):
    cfg = store.get_repo("/repos/proj")
    cfg.window_mode = "single"
    cfg.cur_open_path = "/repos/proj-wt/old"
    store.save_repo(cfg)
    vm.open_worktree("/repos/proj-wt/feat")
    assert store.get_repo("/repos/proj").cur_open_path == "/repos/proj-wt/feat"


# --- set_editor / set_window_mode ---

def test_set_editor_persists_immediately(vm, store):
    vm.set_editor("vscode")
    assert store.get_repo("/repos/proj").editor == "vscode"


def test_set_window_mode_persists_immediately(vm, store):
    vm.set_window_mode("single")
    assert store.get_repo("/repos/proj").window_mode == "single"


# --- cur_open_path accessor ---

def test_cur_open_path_returns_none_initially(vm):
    assert vm.cur_open_path() is None


def test_cur_open_path_reflects_stored_value(vm, store):
    cfg = store.get_repo("/repos/proj")
    cfg.cur_open_path = "/repos/proj-wt/feat"
    store.save_repo(cfg)
    assert vm.cur_open_path() == "/repos/proj-wt/feat"


# --- show_switch_label ---

def test_show_switch_label_false_in_multi_mode(vm):
    assert vm.show_switch_label("/repos/proj-wt/feat") is False


def test_show_switch_label_false_in_single_mode_no_cur(vm, store):
    cfg = store.get_repo("/repos/proj")
    cfg.window_mode = "single"
    store.save_repo(cfg)
    assert vm.show_switch_label("/repos/proj-wt/feat") is False


def test_show_switch_label_false_for_currently_open_path(vm, store):
    cfg = store.get_repo("/repos/proj")
    cfg.window_mode = "single"
    cfg.cur_open_path = "/repos/proj-wt/feat"
    store.save_repo(cfg)
    assert vm.show_switch_label("/repos/proj-wt/feat") is False


def test_show_switch_label_true_for_other_path_in_single_mode(vm, store):
    cfg = store.get_repo("/repos/proj")
    cfg.window_mode = "single"
    cfg.cur_open_path = "/repos/proj-wt/old"
    store.save_repo(cfg)
    assert vm.show_switch_label("/repos/proj-wt/feat") is True


# --- default_editor still works ---

def test_default_editor_returns_editor_and_mode(vm):
    editor_val, mode = vm.default_editor()
    assert editor_val == "cursor"
    assert mode == "reuse"
