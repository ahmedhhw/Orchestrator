import pytest
from unittest.mock import MagicMock
from worktree_manager.config_store import ConfigStore
from worktree_manager.models import RepoConfig
from worktree_manager.setup_settings_vm import RepoSetupViewModel, SettingsViewModel


@pytest.fixture
def store(tmp_path):
    return ConfigStore(tmp_path / "config.json")


def test_default_storage_path(store):
    vm = RepoSetupViewModel(repo_path="/Users/ahmed/repos/my-project", config_store=store)
    assert vm.default_storage_path() == "/Users/ahmed/repos/my-project-worktrees"


def test_confirm_saves_config(store):
    vm = RepoSetupViewModel(repo_path="/repos/proj", config_store=store)
    vm.confirm(storage_path="/repos/proj-wt")
    cfg = store.get_repo("/repos/proj")
    assert cfg is not None
    assert cfg.worktree_storage == "/repos/proj-wt"
    assert cfg.stale_days == 30
    assert cfg.last_editor == "cursor"
    assert cfg.last_editor_mode == "reuse"


def test_confirm_callback_called(store):
    vm = RepoSetupViewModel(repo_path="/repos/proj", config_store=store)
    cb = MagicMock()
    vm.confirm(storage_path="/repos/proj-wt", callback=cb)
    cb.assert_called_once()


@pytest.fixture
def settings_store(tmp_path):
    s = ConfigStore(tmp_path / "config.json")
    s.save_repo(RepoConfig(
        repo_path="/repos/proj",
        worktree_storage="/repos/proj-wt",
        stale_days=30,
        last_editor="cursor",
        last_editor_mode="reuse",
        last_opened="2026-05-19T10:00:00",
        editor="vscode",
        window_mode="single",
    ))
    return s


def test_settings_loads_current_values(settings_store):
    vm = SettingsViewModel(repo_path="/repos/proj", config_store=settings_store)
    assert vm.worktree_storage == "/repos/proj-wt"
    assert vm.stale_days == 30


def test_settings_save_persists(settings_store):
    vm = SettingsViewModel(repo_path="/repos/proj", config_store=settings_store)
    vm.save(worktree_storage="/repos/proj-new-wt", stale_days=60)
    cfg = settings_store.get_repo("/repos/proj")
    assert cfg.worktree_storage == "/repos/proj-new-wt"
    assert cfg.stale_days == 60


def test_settings_vm_save_does_not_touch_editor_or_window_mode(settings_store):
    vm = SettingsViewModel("/repos/proj", settings_store)
    vm.save(worktree_storage="/new/path", stale_days=14)
    saved = settings_store.get_repo("/repos/proj")
    assert saved.worktree_storage == "/new/path"
    assert saved.stale_days == 14
    assert saved.editor == "vscode"
    assert saved.window_mode == "single"
