import pytest
from worktree_manager.config_store import ConfigStore
from worktree_manager.models import WorkspaceProject, WorkspaceEntry


@pytest.fixture
def store(tmp_path):
    return ConfigStore(tmp_path / "config.json")


def test_all_projects_empty_initially(store):
    assert store.all_projects() == []


def test_save_and_get_project(store):
    p = WorkspaceProject(name="my-feature", entries=[
        WorkspaceEntry(worktree_path="/repos/api-wt/fix-login"),
        WorkspaceEntry(worktree_path="/repos/web-wt/main"),
    ])
    store.save_project(p)
    result = store.get_project("my-feature")
    assert result is not None
    assert result.name == "my-feature"
    assert len(result.entries) == 2
    assert result.entries[0].worktree_path == "/repos/api-wt/fix-login"
    assert result.entries[1].worktree_path == "/repos/web-wt/main"


def test_all_projects_returns_saved(store):
    p1 = WorkspaceProject(name="proj-a", entries=[WorkspaceEntry("/a/wt1")])
    p2 = WorkspaceProject(name="proj-b", entries=[])
    store.save_project(p1)
    store.save_project(p2)
    names = [p.name for p in store.all_projects()]
    assert "proj-a" in names
    assert "proj-b" in names


def test_save_project_overwrites_existing(store):
    p = WorkspaceProject(name="my-feature", entries=[WorkspaceEntry("/old")])
    store.save_project(p)
    p2 = WorkspaceProject(name="my-feature", entries=[WorkspaceEntry("/new")])
    store.save_project(p2)
    result = store.get_project("my-feature")
    assert len(result.entries) == 1
    assert result.entries[0].worktree_path == "/new"


def test_delete_project(store):
    p = WorkspaceProject(name="to-delete", entries=[])
    store.save_project(p)
    store.delete_project("to-delete")
    assert store.get_project("to-delete") is None
    assert all(p.name != "to-delete" for p in store.all_projects())


def test_get_project_returns_none_for_missing(store):
    assert store.get_project("nonexistent") is None


def test_rename_project_changes_key_and_preserves_entries(store):
    entries = [WorkspaceEntry("/repos/wt/feat")]
    store.save_project(WorkspaceProject(name="old-name", entries=entries))
    store.rename_project("old-name", "new-name", entries)
    assert store.get_project("old-name") is None
    result = store.get_project("new-name")
    assert result is not None
    assert result.entries[0].worktree_path == "/repos/wt/feat"


def test_rename_project_updates_entries(store):
    old_entries = [WorkspaceEntry("/repos/wt/a")]
    new_entries = [WorkspaceEntry("/repos/wt/a"), WorkspaceEntry("/repos/wt/b")]
    store.save_project(WorkspaceProject(name="proj", entries=old_entries))
    store.rename_project("proj", "proj", new_entries)
    result = store.get_project("proj")
    assert len(result.entries) == 2


def test_rename_project_same_name_preserves_project(store):
    entries = [WorkspaceEntry("/repos/wt/x")]
    store.save_project(WorkspaceProject(name="keep", entries=entries))
    store.rename_project("keep", "keep", entries)
    assert store.get_project("keep") is not None


def test_projects_persist_alongside_repos(store, tmp_path):
    from worktree_manager.models import RepoConfig
    store.save_repo(RepoConfig(
        repo_path="/repos/proj",
        worktree_storage="/repos/proj-wt",
        stale_days=30,
        last_editor="cursor",
        last_editor_mode="reuse",
        last_opened="2026-05-22T10:00:00",
    ))
    store.save_project(WorkspaceProject(name="myproj", entries=[]))
    assert store.get_repo("/repos/proj") is not None
    assert store.get_project("myproj") is not None
