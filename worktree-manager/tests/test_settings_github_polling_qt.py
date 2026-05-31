import pytest
from unittest.mock import MagicMock, patch
from worktree_manager.ui.settings_panel import SettingsDialog
from worktree_manager.setup_settings_vm import SettingsViewModel


@pytest.fixture
def store(tmp_path):
    from worktree_manager.config_store import ConfigStore
    s = ConfigStore(path=tmp_path / "config.json")
    from worktree_manager.models import RepoConfig
    from datetime import datetime, timezone
    cfg = RepoConfig(
        repo_path="/tmp/repo", worktree_storage="/tmp/wt",
        stale_days=14, last_editor="cursor", last_editor_mode="reuse",
        last_opened=datetime.now(timezone.utc).isoformat(),
    )
    s.save_repo(cfg)
    return s


@pytest.fixture
def dialog(store, qtbot):
    vm = SettingsViewModel(repo_path="/tmp/repo", config_store=store)
    dlg = SettingsDialog(parent=None, vm=vm, store=store)
    qtbot.addWidget(dlg)
    return dlg


def test_settings_dialog_has_github_polling_spinbox(dialog):
    assert dialog._github_poll_spin is not None


def test_github_polling_spinbox_shows_current_value(store, qtbot):
    store.save_github_poll_interval(60)
    vm = SettingsViewModel(repo_path="/tmp/repo", config_store=store)
    dlg = SettingsDialog(parent=None, vm=vm, store=store)
    qtbot.addWidget(dlg)
    assert dlg._github_poll_spin.value() == 60


def test_saving_dialog_persists_poll_interval(dialog, store):
    dialog._github_poll_spin.setValue(120)
    dialog._save_btn.click()
    assert store.get_github_poll_interval() == 120


def test_github_polling_spinbox_min_is_5(dialog):
    assert dialog._github_poll_spin.minimum() == 5


def test_github_polling_spinbox_max_is_3600(dialog):
    assert dialog._github_poll_spin.maximum() == 3600
