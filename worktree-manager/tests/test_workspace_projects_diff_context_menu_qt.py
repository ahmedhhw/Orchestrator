from unittest.mock import MagicMock

from worktree_manager.models import WorkspaceEntry, WorkspaceProject
from worktree_manager.ui.workspace_projects_panel import WorkspaceProjectsPanel


def _vm():
    vm = MagicMock()
    vm.load_projects.return_value = [
        WorkspaceProject(
            name="myapp",
            entries=[WorkspaceEntry(worktree_path="/repos/myapp-wt/feat")],
        )
    ]
    vm._store.get_ui_pref.side_effect = lambda key, default=None: {
        "projects_editor": "cursor",
        "projects_collapsed": [],
    }.get(key, default)
    vm._store.all_repos.return_value = []
    vm.list_branches_for_worktree.return_value = ["main"]
    vm._git.checked_out_branch.return_value = "main"
    return vm


def _panel(qtbot, on_diff_from_working_tree=None, on_diff_compare_branches=None):
    p = WorkspaceProjectsPanel(
        parent=None,
        vm=_vm(),
        on_close=lambda: None,
        on_diff_from_working_tree=on_diff_from_working_tree,
        on_diff_compare_branches=on_diff_compare_branches,
    )
    qtbot.addWidget(p)
    return p


def test_entry_context_menu_has_diff_from_working_tree_action(qtbot):
    p = _panel(qtbot)
    menu = p._build_entry_context_menu("/repos/myapp-wt/feat")
    texts = [a.text() for a in menu.actions()]
    assert any("Diff from working tree" in t for t in texts)


def test_entry_context_menu_has_compare_branches_action(qtbot):
    p = _panel(qtbot)
    menu = p._build_entry_context_menu("/repos/myapp-wt/feat")
    texts = [a.text() for a in menu.actions()]
    assert any("Compare branches" in t for t in texts)


def test_trigger_diff_from_working_tree_fires_callback(qtbot):
    called = []
    p = _panel(qtbot, on_diff_from_working_tree=lambda path: called.append(path))
    p._trigger_diff_from_working_tree("/repos/myapp-wt/feat")
    assert called == ["/repos/myapp-wt/feat"]


def test_trigger_diff_compare_branches_fires_callback(qtbot):
    called = []
    p = _panel(qtbot, on_diff_compare_branches=lambda path: called.append(path))
    p._trigger_diff_compare_branches("/repos/myapp-wt/feat")
    assert called == ["/repos/myapp-wt/feat"]


def test_diff_callbacks_not_required(qtbot):
    p = _panel(qtbot)
    p._trigger_diff_from_working_tree("/repos/myapp-wt/feat")
    p._trigger_diff_compare_branches("/repos/myapp-wt/feat")
