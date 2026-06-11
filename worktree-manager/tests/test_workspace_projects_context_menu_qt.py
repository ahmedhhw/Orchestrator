from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt

from worktree_manager.models import WorkspaceEntry, WorkspaceProject
from worktree_manager.ui.workspace_projects_panel import WorkspaceProjectsPanel


def _vm(projects=None):
    vm = MagicMock()
    vm.load_projects.return_value = projects or []
    vm._store.get_ui_pref.side_effect = lambda key, default: {
        "projects_editor": "cursor",
        "projects_collapsed": [],
    }.get(key, default)
    vm._store.all_repos.return_value = {}
    vm.list_branches_for_worktree.return_value = ["main"]
    vm._git.checked_out_branch.return_value = "main"

    def _load_project_entries(projs, on_progress=None):
        return [
            {"worktree_path": e.worktree_path,
             "current_branch": "main",
             "branches": ["main"]}
            for proj in projs for e in proj.entries
        ]

    vm.load_project_entries.side_effect = _load_project_entries
    return vm


def _project(worktree_path="/repos/proj-wt/feat-auth"):
    return WorkspaceProject(
        name="feat-auth",
        entries=[WorkspaceEntry(worktree_path=worktree_path)],
    )


def _panel(qtbot, vm=None, on_generate_project=None, on_run_command=None):
    p = WorkspaceProjectsPanel(
        parent=None,
        vm=vm or _vm(projects=[_project()]),
        on_close=lambda: None,
        on_generate_project=on_generate_project or (lambda path: None),
        on_run_command=on_run_command or (lambda path: None),
    )
    qtbot.addWidget(p)
    qtbot.waitUntil(lambda: p._loading is False, timeout=3000)
    return p


def test_panel_accepts_on_generate_project_callback(qtbot):
    p = _panel(qtbot)
    assert p._on_generate_project is not None


def test_panel_accepts_on_run_command_callback(qtbot):
    p = _panel(qtbot)
    assert p._on_run_command is not None


def test_entry_rows_have_custom_context_menu_policy(qtbot):
    p = _panel(qtbot)
    assert len(p._entry_rows) >= 1
    for row in p._entry_rows:
        assert row.contextMenuPolicy() == Qt.CustomContextMenu


def test_entry_context_menu_has_generate_project_action(qtbot):
    p = _panel(qtbot)
    menu = p._build_entry_context_menu("/repos/proj-wt/feat-auth")
    texts = [a.text() for a in menu.actions()]
    assert any("Generate Project" in t for t in texts)


def test_entry_context_menu_has_run_command_action(qtbot):
    p = _panel(qtbot)
    menu = p._build_entry_context_menu("/repos/proj-wt/feat-auth")
    texts = [a.text() for a in menu.actions()]
    assert any("Run Command" in t for t in texts)


def test_trigger_generate_project_fires_callback(qtbot):
    called = []
    p = _panel(qtbot, on_generate_project=lambda path: called.append(path))
    p._trigger_generate_project("/repos/proj-wt/feat-auth")
    assert called == ["/repos/proj-wt/feat-auth"]


def test_trigger_run_command_fires_callback(qtbot):
    called = []
    p = _panel(qtbot, on_run_command=lambda path: called.append(path))
    p._trigger_run_command("/repos/proj-wt/feat-auth")
    assert called == ["/repos/proj-wt/feat-auth"]


def test_panel_works_without_callbacks(qtbot):
    p = WorkspaceProjectsPanel(
        parent=None,
        vm=_vm(projects=[_project()]),
        on_close=lambda: None,
    )
    qtbot.addWidget(p)
    p._trigger_generate_project("/repos/proj-wt/feat-auth")
    p._trigger_run_command("/repos/proj-wt/feat-auth")
