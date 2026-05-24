import pytest
from unittest.mock import MagicMock


def _ctk_available():
    try:
        import customtkinter
        return True
    except ImportError:
        return False


pytestmark = pytest.mark.skipif(not _ctk_available(), reason="customtkinter not installed")


def test_landing_screen_vm_instantiates():
    from worktree_manager.config_store import ConfigStore
    from worktree_manager.git_service import GitService
    from worktree_manager.landing_screen import LandingScreenViewModel

    store = MagicMock(spec=ConfigStore)
    store.all_repos.return_value = {}
    git = MagicMock(spec=GitService)
    vm = LandingScreenViewModel(config_store=store, git_service=git)
    assert vm.recent_repos() == []


def test_repo_setup_vm_default_path():
    from worktree_manager.config_store import ConfigStore
    from worktree_manager.setup_settings_vm import RepoSetupViewModel

    store = MagicMock(spec=ConfigStore)
    vm = RepoSetupViewModel(repo_path="/Users/ahmed/repos/myrepo", config_store=store)
    assert vm.default_storage_path().endswith("myrepo-worktrees")


def test_cleanup_wizard_smoke_branch_candidates(tmp_path):
    import customtkinter as ctk
    import time
    from worktree_manager.models import CleanupCandidate
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    now = int(time.time())
    root = ctk.CTk()
    root.withdraw()
    candidates = [
        CleanupCandidate("release/1.0", None, True, False, now - 5 * 86400),
        CleanupCandidate("chore/old", None, False, True, now - 35 * 86400),
    ]
    wizard = CleanupWizard(root, candidates=candidates, on_delete_selected=lambda s: None)
    wizard.destroy()
    root.destroy()


def test_cleanup_wizard_smoke_empty(tmp_path):
    import customtkinter as ctk
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    root = ctk.CTk()
    root.withdraw()
    wizard = CleanupWizard(root, candidates=[], on_delete_selected=lambda s: None)
    wizard.destroy()
    root.destroy()


def test_settings_vm_save_called():
    from worktree_manager.config_store import ConfigStore
    from worktree_manager.models import RepoConfig
    from worktree_manager.setup_settings_vm import SettingsViewModel

    store = MagicMock(spec=ConfigStore)
    store.get_repo.return_value = RepoConfig(
        repo_path="/repos/proj",
        worktree_storage="/repos/proj-wt",
        stale_days=30,
        last_editor="cursor",
        last_editor_mode="reuse",
        last_opened="2026-05-19T10:00:00",
    )
    vm = SettingsViewModel(repo_path="/repos/proj", config_store=store)
    vm.save(worktree_storage="/new", stale_days=14)
    store.save_repo.assert_called_once()
