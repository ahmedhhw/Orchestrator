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


def test_delete_dialog_disables_checkbox_for_protected_branch():
    import customtkinter as ctk
    import time
    from worktree_manager.models import WorktreeModel
    from worktree_manager.ui.delete_dialog import DeleteDialog
    now = int(time.time())
    root = ctk.CTk()
    root.withdraw()
    wt = WorktreeModel(
        path="/repos/proj-wt/feature-payments",
        branch="feature/payments",
        is_main=False,
        last_commit_ts=now,
        is_merged=False,
        is_stale=False,
    )
    dialog = DeleteDialog(
        root, wt=wt, on_delete=lambda w, b: None,
        live_window=None, is_protected=True,
    )
    assert dialog._also_branch.get() is False
    dialog.destroy()
    root.destroy()


def test_delete_dialog_allows_checkbox_for_normal_branch():
    import customtkinter as ctk
    import time
    from worktree_manager.models import WorktreeModel
    from worktree_manager.ui.delete_dialog import DeleteDialog
    now = int(time.time())
    root = ctk.CTk()
    root.withdraw()
    wt = WorktreeModel(
        path="/repos/proj-wt/fix-auth",
        branch="fix/auth",
        is_main=False,
        last_commit_ts=now,
        is_merged=False,
        is_stale=False,
    )
    dialog = DeleteDialog(
        root, wt=wt, on_delete=lambda w, b: None,
        live_window=None, is_protected=False,
    )
    assert dialog._also_branch.get() is True
    dialog.destroy()
    root.destroy()


def test_create_dialog_smoke_new_branch_mode():
    import customtkinter as ctk
    from worktree_manager.ui.create_dialog import CreateDialog
    root = ctk.CTk()
    root.withdraw()
    dialog = CreateDialog(
        root,
        branches=["main", "feature/payments"],
        existing_branches=[],
        on_create=lambda *a: None,
    )
    dialog.destroy()
    root.destroy()


def test_create_dialog_smoke_existing_branch_mode():
    import customtkinter as ctk
    from worktree_manager.ui.create_dialog import CreateDialog
    root = ctk.CTk()
    root.withdraw()
    dialog = CreateDialog(
        root,
        branches=["main", "feature/payments"],
        existing_branches=["fix/auth", "chore/deps"],
        on_create=lambda *a: None,
    )
    dialog.destroy()
    root.destroy()


def test_create_dialog_new_branch_calls_on_create_with_correct_args():
    import customtkinter as ctk
    from worktree_manager.ui.create_dialog import CreateDialog
    root = ctk.CTk()
    root.withdraw()
    calls = []
    dialog = CreateDialog(
        root,
        branches=["main", "develop"],
        existing_branches=[],
        on_create=lambda *a: calls.append(a),
    )
    dialog._mode_var.set("new")
    dialog._on_mode_change()
    dialog._branch_entry.insert(0, "fix/my-bug")
    dialog._base_var.set("main")
    dialog._wt_name_entry.delete(0, "end")
    dialog._wt_name_entry.insert(0, "my-worktree")
    dialog._create()
    root.destroy()
    assert len(calls) == 1
    branch, base_branch, is_existing, worktree_name = calls[0]
    assert branch == "fix/my-bug"
    assert base_branch == "main"
    assert is_existing is False
    assert worktree_name == "my-worktree"


def test_create_dialog_new_branch_passes_none_worktree_name_when_empty():
    import customtkinter as ctk
    from worktree_manager.ui.create_dialog import CreateDialog
    root = ctk.CTk()
    root.withdraw()
    calls = []
    dialog = CreateDialog(
        root,
        branches=["main"],
        existing_branches=[],
        on_create=lambda *a: calls.append(a),
    )
    dialog._mode_var.set("new")
    dialog._on_mode_change()
    dialog._branch_entry.insert(0, "fix/my-bug")
    dialog._wt_name_entry.delete(0, "end")
    dialog._create()
    root.destroy()
    assert len(calls) == 1
    branch, base_branch, is_existing, worktree_name = calls[0]
    assert worktree_name is None


def test_create_dialog_copy_from_branch_fills_worktree_name():
    import customtkinter as ctk
    from worktree_manager.ui.create_dialog import CreateDialog
    root = ctk.CTk()
    root.withdraw()
    dialog = CreateDialog(
        root,
        branches=["main"],
        existing_branches=[],
        on_create=lambda *a: None,
    )
    dialog._mode_var.set("new")
    dialog._on_mode_change()
    dialog._branch_entry.delete(0, "end")
    dialog._branch_entry.insert(0, "fix/my-login")
    dialog._copy_branch_to_wt()
    result = dialog._wt_name_entry.get()
    dialog.destroy()
    root.destroy()
    assert result == "fix-my-login"


def test_create_dialog_copy_from_worktree_fills_branch_name():
    import customtkinter as ctk
    from worktree_manager.ui.create_dialog import CreateDialog
    root = ctk.CTk()
    root.withdraw()
    dialog = CreateDialog(
        root,
        branches=["main"],
        existing_branches=[],
        on_create=lambda *a: None,
    )
    dialog._mode_var.set("new")
    dialog._on_mode_change()
    dialog._wt_name_entry.delete(0, "end")
    dialog._wt_name_entry.insert(0, "fix-my-login")
    dialog._copy_wt_to_branch()
    result = dialog._branch_entry.get()
    dialog.destroy()
    root.destroy()
    assert result == "fix/my-login"


def test_create_dialog_existing_branch_calls_on_create_with_correct_args():
    import customtkinter as ctk
    from worktree_manager.ui.create_dialog import CreateDialog
    root = ctk.CTk()
    root.withdraw()
    calls = []
    dialog = CreateDialog(
        root,
        branches=["main"],
        existing_branches=["fix/auth", "chore/deps"],
        on_create=lambda *a: calls.append(a),
    )
    dialog._mode_var.set("existing")
    dialog._on_mode_change()
    dialog._existing_var.set("fix/auth")
    dialog._existing_wt_name_entry.delete(0, "end")
    dialog._existing_wt_name_entry.insert(0, "auth-wt")
    dialog._create()
    root.destroy()
    assert len(calls) == 1
    branch, base_branch, is_existing, worktree_name = calls[0]
    assert branch == "fix/auth"
    assert base_branch is None
    assert is_existing is True
    assert worktree_name == "auth-wt"


def test_create_dialog_existing_branch_copy_from_branch_fills_worktree_name():
    import customtkinter as ctk
    from worktree_manager.ui.create_dialog import CreateDialog
    root = ctk.CTk()
    root.withdraw()
    dialog = CreateDialog(
        root,
        branches=["main"],
        existing_branches=["fix/auth", "chore/deps"],
        on_create=lambda *a: None,
    )
    dialog._mode_var.set("existing")
    dialog._on_mode_change()
    dialog._existing_var.set("fix/auth")
    dialog._copy_existing_branch_to_wt()
    result = dialog._existing_wt_name_entry.get()
    dialog.destroy()
    root.destroy()
    assert result == "fix-auth"


def test_create_dialog_new_branch_empty_name_does_not_call_on_create():
    import customtkinter as ctk
    from worktree_manager.ui.create_dialog import CreateDialog
    root = ctk.CTk()
    root.withdraw()
    calls = []
    dialog = CreateDialog(
        root,
        branches=["main"],
        existing_branches=[],
        on_create=lambda *a: calls.append(a),
    )
    dialog._mode_var.set("new")
    dialog._on_mode_change()
    dialog._create()
    root.destroy()
    assert calls == []


def test_handle_create_new_branch_passes_existing_false_to_vm():
    import customtkinter as ctk
    from unittest.mock import MagicMock
    from worktree_manager.ui.main_window import MainWindow
    root = ctk.CTk()
    root.withdraw()
    vm = MagicMock()
    vm.load_worktrees.return_value = []
    vm.repo_name.return_value = "proj"
    win = MainWindow.__new__(MainWindow)
    win._vm = vm
    win.refresh = MagicMock()
    win._handle_create("fix/bug", "main", False, "fix-bug")
    vm.create_worktree.assert_called_once_with(branch="fix/bug", base_branch="main", existing=False, worktree_name="fix-bug")
    win.refresh.assert_called_once()
    root.destroy()


def test_handle_create_existing_branch_passes_existing_true_to_vm():
    import customtkinter as ctk
    from unittest.mock import MagicMock
    from worktree_manager.ui.main_window import MainWindow
    root = ctk.CTk()
    root.withdraw()
    vm = MagicMock()
    vm.load_worktrees.return_value = []
    vm.repo_name.return_value = "proj"
    win = MainWindow.__new__(MainWindow)
    win._vm = vm
    win.refresh = MagicMock()
    win._handle_create("fix/auth", None, True, None)
    vm.create_worktree.assert_called_once_with(branch="fix/auth", base_branch=None, existing=True, worktree_name=None)
    win.refresh.assert_called_once()
    root.destroy()


def test_main_window_refresh_smoke_with_branch_dropdown():
    import customtkinter as ctk
    import time
    from unittest.mock import MagicMock
    from worktree_manager.models import WorktreeModel, RepoConfig
    from worktree_manager.main_window_vm import MainWindowViewModel
    from worktree_manager.ui.main_window import MainWindow
    from worktree_manager.config_store import ConfigStore
    from worktree_manager.git_service import GitService

    now = int(time.time())
    root = ctk.CTk()
    root.withdraw()

    store = MagicMock(spec=ConfigStore)
    store.get_repo.return_value = RepoConfig(
        repo_path="/repos/proj",
        worktree_storage="/repos/proj-wt",
        stale_days=30,
        last_editor="cursor",
        last_editor_mode="reuse",
        last_opened="2026-05-19T10:00:00",
    )
    git = MagicMock(spec=GitService)
    git.list_worktrees.return_value = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
        WorktreeModel("/repos/proj-wt/fix-auth", "fix/auth", False, now - 3600, False, False),
    ]
    git.list_local_branches.return_value = ["main", "fix/auth", "hotfix/2.1"]
    git.list_feature_branches.return_value = []

    vm = MainWindowViewModel(
        repo_path="/repos/proj", config_store=store,
        git_service=git,
    )
    window = MainWindow(root, vm=vm, repo_name="proj", on_settings=lambda: None, on_cleanup=lambda: None)
    window.destroy()
    root.destroy()


def test_handle_create_shows_error_dialog_on_duplicate_branch():
    import customtkinter as ctk
    from unittest.mock import MagicMock, patch
    from worktree_manager.ui.main_window import MainWindow
    root = ctk.CTk()
    root.withdraw()
    vm = MagicMock()
    vm.create_worktree.side_effect = ValueError("Branch 'fix/bug' already exists in this repo.")
    win = MainWindow.__new__(MainWindow)
    win._vm = vm
    win.refresh = MagicMock()
    with patch("tkinter.messagebox.showerror") as mock_err:
        win._handle_create("fix/bug", "main", False, None)
    mock_err.assert_called_once()
    win.refresh.assert_not_called()
    root.destroy()


def test_handle_create_shows_error_dialog_on_duplicate_worktree_name():
    import customtkinter as ctk
    from unittest.mock import MagicMock, patch
    from worktree_manager.ui.main_window import MainWindow
    root = ctk.CTk()
    root.withdraw()
    vm = MagicMock()
    vm.create_worktree.side_effect = ValueError("Worktree folder 'fix-bug' is already in use.")
    win = MainWindow.__new__(MainWindow)
    win._vm = vm
    win.refresh = MagicMock()
    with patch("tkinter.messagebox.showerror") as mock_err:
        win._handle_create("fix/bug", "main", False, "fix-bug")
    mock_err.assert_called_once()
    win.refresh.assert_not_called()
    root.destroy()


def test_handle_delete_does_not_guard_checked_out_branch():
    import customtkinter as ctk
    from unittest.mock import MagicMock
    from worktree_manager.models import WorktreeModel
    from worktree_manager.ui.main_window import MainWindow
    import time
    root = ctk.CTk()
    root.withdraw()
    vm = MagicMock()
    win = MainWindow.__new__(MainWindow)
    win._vm = vm
    win.refresh = MagicMock()
    wt = WorktreeModel("/repos/proj-wt/fix-auth", "fix/auth", False, int(time.time()), False, False)
    win._handle_delete(wt, also_delete_branch=True)
    vm.delete_worktree.assert_called_once_with(
        path="/repos/proj-wt/fix-auth", branch="fix/auth", also_delete_branch=True
    )
    win.refresh.assert_called_once()
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
