from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QDialog, QPushButton, QRadioButton

from worktree_manager.models import WorkspaceEntry, WorkspaceProject
from worktree_manager.ui.workspace_projects_panel import WorkspaceProjectsPanel


def _vm(projects=None, editor="cursor", collapsed=None,
        branches=("main", "feat-a"), current_branch="main"):
    vm = MagicMock()
    vm.load_projects.return_value = projects or []
    vm._store.get_ui_pref.side_effect = lambda key, default: {
        "projects_editor": editor,
        "projects_collapsed": collapsed or [],
    }.get(key, default)
    vm._store.all_repos.return_value = {"/r/proj": MagicMock()}
    vm.list_branches_for_worktree.return_value = list(branches)
    vm._git.checked_out_branch.return_value = current_branch
    return vm


def _panel(qtbot, vm=None, on_close=None, confirm=True):
    p = WorkspaceProjectsPanel(
        parent=None, vm=vm or _vm(),
        on_close=on_close or (lambda: None),
        confirm_fn=lambda msg: confirm,
    )
    qtbot.addWidget(p)
    return p


def test_workspace_panel_toolbar_has_new_and_close(qtbot):
    p = _panel(qtbot)
    texts = [b.text() for b in p.findChildren(QPushButton)]
    assert any("New" in t for t in texts)
    assert "×" in texts


def test_workspace_panel_editor_radio_defaults_from_pref(qtbot):
    p = _panel(qtbot, vm=_vm(editor="vscode"))
    vscode = next(r for r in p.findChildren(QRadioButton) if r.text() == "vscode")
    assert vscode.isChecked() is True


def test_workspace_panel_editor_radio_change_persists_pref(qtbot):
    vm = _vm(editor="cursor")
    p = _panel(qtbot, vm=vm)
    vscode = next(r for r in p.findChildren(QRadioButton) if r.text() == "vscode")
    vscode.setChecked(True)
    vm._store.set_ui_pref.assert_any_call("projects_editor", "vscode")


def test_workspace_panel_empty_state_when_no_projects(qtbot):
    p = _panel(qtbot, vm=_vm(projects=[]))
    assert p.empty_state_visible() is True


def test_workspace_panel_shows_project_rows(qtbot):
    proj = WorkspaceProject(name="alpha", entries=[WorkspaceEntry(worktree_path="/r/proj")])
    p = _panel(qtbot, vm=_vm(projects=[proj]))
    texts = " ".join(b.text() for b in p.findChildren(QPushButton))
    assert "alpha" in texts


def test_workspace_panel_collapse_toggles_persisted(qtbot):
    proj = WorkspaceProject(name="alpha", entries=[WorkspaceEntry(worktree_path="/r/proj")])
    vm = _vm(projects=[proj])
    p = _panel(qtbot, vm=vm)
    p.toggle_collapse("alpha")
    vm._store.set_ui_pref.assert_any_call("projects_collapsed", ["alpha"])


def test_workspace_panel_open_invokes_vm(qtbot):
    proj = WorkspaceProject(name="alpha", entries=[WorkspaceEntry(worktree_path="/r/proj")])
    vm = _vm(projects=[proj])
    p = _panel(qtbot, vm=vm)
    p.open_project("alpha")
    vm.open_project.assert_called_once_with("alpha", "cursor")


def test_workspace_panel_delete_invokes_vm_and_refreshes(qtbot):
    proj = WorkspaceProject(name="alpha", entries=[WorkspaceEntry(worktree_path="/r/proj")])
    vm = _vm(projects=[proj])
    p = _panel(qtbot, vm=vm, confirm=True)
    p.delete_project("alpha")
    vm.delete_project.assert_called_once_with("alpha")


def test_workspace_panel_delete_cancelled_does_not_delete(qtbot):
    proj = WorkspaceProject(name="alpha", entries=[WorkspaceEntry(worktree_path="/r/proj")])
    vm = _vm(projects=[proj])
    p = _panel(qtbot, vm=vm, confirm=False)
    p.delete_project("alpha")
    vm.delete_project.assert_not_called()


def test_workspace_panel_close_invokes_callback(qtbot):
    calls = []
    p = _panel(qtbot, on_close=lambda: calls.append("x"))
    p.trigger_close()
    assert calls == ["x"]


def test_workspace_panel_new_button_opens_operations_dialog(qtbot):
    p = _panel(qtbot)
    with patch(
        "worktree_manager.ui.workspace_projects_panel.ProjectOperationsDialog"
    ) as MockDlg:
        instance = MagicMock(spec=QDialog)
        MockDlg.return_value = instance
        p._open_new_dialog()
    MockDlg.assert_called_once()


def test_workspace_panel_edit_button_opens_operations_dialog(qtbot):
    proj = WorkspaceProject(name="alpha", entries=[WorkspaceEntry(worktree_path="/r/proj")])
    p = _panel(qtbot, vm=_vm(projects=[proj]))
    with patch(
        "worktree_manager.ui.workspace_projects_panel.ProjectOperationsDialog"
    ) as MockDlg:
        instance = MagicMock(spec=QDialog)
        MockDlg.return_value = instance
        p._edit_project(proj)
    MockDlg.assert_called_once()


def test_workspace_panel_branch_switch_calls_vm(qtbot):
    proj = WorkspaceProject(name="alpha", entries=[WorkspaceEntry(worktree_path="/r/proj")])
    vm = _vm(projects=[proj])
    p = _panel(qtbot, vm=vm)
    p.switch_branch("/r/proj", "feat-a")
    vm.switch_branch_in_project.assert_called_once_with("/r/proj", "feat-a")
