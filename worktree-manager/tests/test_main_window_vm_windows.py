import pytest
import time
from unittest.mock import MagicMock, patch
from worktree_manager.config_store import ConfigStore
from worktree_manager.git_service import GitService
from worktree_manager.editor_service import EditorService
from worktree_manager.window_registry import WindowRegistry
from worktree_manager.models import RepoConfig, WindowRecord, WorktreeModel
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
def registry():
    return WindowRegistry()


@pytest.fixture
def editor(store, registry):
    return EditorService(store, window_registry=registry)


@pytest.fixture
def vm(store, git, editor, registry):
    m = MainWindowViewModel(
        repo_path="/repos/proj",
        config_store=store,
        git_service=git,
        editor_service=editor,
        window_registry=registry,
    )
    m.load_worktrees()
    return m


def test_is_open_false_when_no_window_tracked(vm):
    assert vm.is_open("/repos/proj-wt/feat") is False


def test_is_open_true_when_window_tracked_and_alive(vm, registry):
    registry.register("/repos/proj", "/repos/proj-wt/feat", pid=42, editor="cursor")
    with patch("os.kill", return_value=None):
        assert vm.is_open("/repos/proj-wt/feat") is True


def test_is_open_false_when_window_tracked_but_dead(vm, registry):
    registry.register("/repos/proj", "/repos/proj-wt/feat", pid=42, editor="cursor")
    with patch("os.kill", side_effect=OSError):
        assert vm.is_open("/repos/proj-wt/feat") is False


def test_get_window_returns_record(vm, registry):
    registry.register("/repos/proj", "/repos/proj-wt/feat", pid=42, editor="cursor")
    rec = vm.get_window("/repos/proj-wt/feat")
    assert rec is not None
    assert rec.pid == 42


def test_get_window_returns_none_when_untracked(vm):
    assert vm.get_window("/repos/proj-wt/feat") is None


def test_open_worktree_without_registry_still_works(store, git):
    editor = MagicMock(spec=EditorService)
    vm = MainWindowViewModel(
        repo_path="/repos/proj",
        config_store=store,
        git_service=git,
        editor_service=editor,
    )
    vm.load_worktrees()
    vm.open_worktree("/repos/proj-wt/feat", editor="cursor", reuse_window=False)
    editor.open.assert_called_once()


def test_delete_worktree_closes_live_window(vm, registry):
    registry.register("/repos/proj", "/repos/proj-wt/feat", pid=42, editor="cursor")
    with patch("os.kill") as mock_kill:
        vm.delete_worktree(
            path="/repos/proj-wt/feat",
            branch="feature/auth",
            also_delete_branch=False,
        )
    import signal
    calls = [str(c) for c in mock_kill.call_args_list]
    assert any(str(signal.SIGTERM) in c for c in calls)


def test_delete_worktree_without_live_window_does_not_crash(vm):
    vm.delete_worktree(
        path="/repos/proj-wt/feat",
        branch="feature/auth",
        also_delete_branch=False,
    )


def test_vm_without_registry_is_open_always_false(store, git):
    editor = MagicMock(spec=EditorService)
    vm = MainWindowViewModel(
        repo_path="/repos/proj",
        config_store=store,
        git_service=git,
        editor_service=editor,
    )
    assert vm.is_open("/repos/proj-wt/feat") is False
