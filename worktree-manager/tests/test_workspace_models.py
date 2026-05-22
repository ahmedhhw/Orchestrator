from worktree_manager.models import WorkspaceProject, WorkspaceEntry


def test_workspace_entry_has_worktree_path():
    e = WorkspaceEntry(worktree_path="/repos/proj-wt/fix-login")
    assert e.worktree_path == "/repos/proj-wt/fix-login"


def test_workspace_project_has_name_and_entries():
    e1 = WorkspaceEntry(worktree_path="/repos/api-wt/fix-login")
    e2 = WorkspaceEntry(worktree_path="/repos/web-wt/main")
    p = WorkspaceProject(name="my-feature", entries=[e1, e2])
    assert p.name == "my-feature"
    assert len(p.entries) == 2
    assert p.entries[0].worktree_path == "/repos/api-wt/fix-login"


def test_workspace_project_entries_default_empty():
    p = WorkspaceProject(name="empty")
    assert p.entries == []
