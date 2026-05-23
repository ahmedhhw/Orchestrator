import pytest
from unittest.mock import MagicMock
from worktree_manager.config_store import ConfigStore
from worktree_manager.git_service import GitService
from worktree_manager.workspace_service import WorkspaceService
from worktree_manager.models import WorkspaceProject, WorkspaceEntry, WorktreeModel
from worktree_manager.workspace_projects_vm import WorkspaceProjectsViewModel


@pytest.fixture
def store(tmp_path):
    return ConfigStore(tmp_path / "config.json")


@pytest.fixture
def git():
    return MagicMock(spec=GitService)


@pytest.fixture
def svc(tmp_path):
    return WorkspaceService(workspace_dir=tmp_path / "workspaces")


@pytest.fixture
def vm(store, git, svc):
    return WorkspaceProjectsViewModel(config_store=store, git_service=git, workspace_service=svc)


def test_load_projects_empty_initially(vm):
    assert vm.load_projects() == []


def test_create_project_persists(vm, store):
    entries = [WorkspaceEntry("/repos/api-wt/fix-login")]
    vm.create_project(name="my-feature", entries=entries)
    result = store.get_project("my-feature")
    assert result is not None
    assert result.name == "my-feature"
    assert result.entries[0].worktree_path == "/repos/api-wt/fix-login"


def test_create_project_generates_workspace_file(vm, tmp_path):
    entries = [WorkspaceEntry("/repos/api-wt/fix-login")]
    vm.create_project(name="my-feature", entries=entries)
    ws_path = tmp_path / "workspaces" / "my-feature.code-workspace"
    assert ws_path.exists()


def test_load_projects_returns_saved(vm):
    vm.create_project("proj-a", [WorkspaceEntry("/a")])
    vm.create_project("proj-b", [])
    names = [p.name for p in vm.load_projects()]
    assert "proj-a" in names
    assert "proj-b" in names


def test_delete_project_removes_from_store(vm, store):
    vm.create_project("to-delete", [])
    vm.delete_project("to-delete")
    assert store.get_project("to-delete") is None


def test_delete_project_removes_workspace_file(vm, tmp_path):
    vm.create_project("to-delete", [WorkspaceEntry("/repos/wt")])
    ws_path = tmp_path / "workspaces" / "to-delete.code-workspace"
    assert ws_path.exists()
    vm.delete_project("to-delete")
    assert not ws_path.exists()


def test_open_project_calls_workspace_service(vm, svc):
    from unittest.mock import patch
    vm.create_project("myproj", [WorkspaceEntry("/repos/wt")])
    project = svc._config_store.get_project("myproj") if hasattr(svc, "_config_store") else None
    with patch.object(svc, "open_in_editor") as mock_open:
        with patch.object(svc, "generate_code_workspace") as mock_gen:
            mock_gen.return_value = "dummy_path"
            vm.open_project("myproj", editor="cursor")
            mock_open.assert_called_once()
            call_args = mock_open.call_args
            assert call_args[0][1] == "cursor" or call_args[1].get("editor") == "cursor"


def test_list_worktrees_for_repo(vm, git):
    import time
    now = int(time.time())
    git.list_worktrees.return_value = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
        WorktreeModel("/repos/proj-wt/fix-login", "fix/login", False, now - 3600, False, False),
    ]
    worktrees = vm.list_worktrees_for_repo("/repos/proj")
    assert len(worktrees) == 2
    git.list_worktrees.assert_called_once()


def test_switch_branch_in_project_clean(vm, git):
    git.has_uncommitted_changes.return_value = False
    vm.switch_branch_in_project(worktree_path="/repos/proj-wt/fix-login", new_branch="main")
    git.checkout_branch.assert_called_once_with("/repos/proj-wt/fix-login", "main")


def test_update_project_renames_and_saves(vm, store):
    vm.create_project("original", [WorkspaceEntry("/repos/wt/a")])
    new_entries = [WorkspaceEntry("/repos/wt/a"), WorkspaceEntry("/repos/wt/b")]
    vm.update_project(old_name="original", new_name="renamed", entries=new_entries)
    assert store.get_project("original") is None
    result = store.get_project("renamed")
    assert result is not None
    assert len(result.entries) == 2


def test_update_project_generates_workspace_file(vm, tmp_path):
    vm.create_project("proj", [WorkspaceEntry("/repos/wt/a")])
    vm.update_project("proj", "proj-v2", [WorkspaceEntry("/repos/wt/a")])
    ws_path = tmp_path / "workspaces" / "proj-v2.code-workspace"
    assert ws_path.exists()


def test_update_project_same_name_updates_entries(vm, store):
    vm.create_project("proj", [WorkspaceEntry("/repos/wt/a")])
    vm.update_project("proj", "proj", [WorkspaceEntry("/repos/wt/a"), WorkspaceEntry("/repos/wt/b")])
    result = store.get_project("proj")
    assert len(result.entries) == 2


def test_switch_branch_in_project_raises_if_uncommitted(vm, git):
    git.has_uncommitted_changes.return_value = True
    with pytest.raises(ValueError, match="uncommitted"):
        vm.switch_branch_in_project(worktree_path="/repos/proj-wt/fix-login", new_branch="main")
    git.checkout_branch.assert_not_called()
