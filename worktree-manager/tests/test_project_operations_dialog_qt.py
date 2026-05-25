from unittest.mock import MagicMock

from PySide6.QtWidgets import QDialog, QPushButton

from worktree_manager.models import WorkspaceEntry, WorkspaceProject, WorktreeModel
from worktree_manager.ui.project_operations_dialog import ProjectOperationsDialog


def _wt(path="/r/proj", branch="main", is_main=True):
    return WorktreeModel(
        path=path, branch=branch, is_main=is_main,
        last_commit_ts=0, is_merged=False, is_stale=False,
    )


def _vm(worktrees=None):
    vm = MagicMock()
    vm.list_worktrees_for_repo.return_value = worktrees or [_wt()]
    return vm


def _dlg(qtbot, vm=None, repos=None, on_create=None, on_edit=None,
         existing_project=None):
    d = ProjectOperationsDialog(
        parent=None, vm=vm or _vm(),
        repos=repos or {"/repos/proj": MagicMock()},
        on_create=on_create or (lambda name, entries: None),
        on_edit=on_edit, existing_project=existing_project,
    )
    qtbot.addWidget(d)
    return d


def test_project_operations_dialog_is_qdialog(qtbot):
    assert isinstance(_dlg(qtbot), QDialog)


def test_project_operations_dialog_title_create_mode(qtbot):
    d = _dlg(qtbot)
    assert "New" in d.windowTitle()


def test_project_operations_dialog_title_edit_mode(qtbot):
    proj = WorkspaceProject(name="myproj", entries=[WorkspaceEntry(worktree_path="/r/proj")])
    d = _dlg(qtbot, existing_project=proj, on_edit=lambda *_: None)
    assert "Edit" in d.windowTitle()


def test_project_operations_dialog_edit_mode_prepopulates(qtbot):
    proj = WorkspaceProject(name="myproj", entries=[WorkspaceEntry(worktree_path="/r/proj")])
    d = _dlg(qtbot, existing_project=proj, on_edit=lambda *_: None)
    assert d.get_name() == "myproj"
    assert "/r/proj" in d.get_entries()


def test_project_operations_dialog_add_entry_via_picker(qtbot):
    d = _dlg(qtbot)
    d.trigger_add_entry("/r/proj")
    assert "/r/proj" in d.get_entries()


def test_project_operations_dialog_add_entry_is_idempotent(qtbot):
    d = _dlg(qtbot)
    d.trigger_add_entry("/r/proj")
    d.trigger_add_entry("/r/proj")
    assert d.get_entries().count("/r/proj") == 1


def test_project_operations_dialog_remove_entry(qtbot):
    d = _dlg(qtbot)
    d.trigger_add_entry("/r/proj")
    d.trigger_remove_entry("/r/proj")
    assert d.get_entries() == []


def test_project_operations_dialog_confirm_create_calls_callback(qtbot):
    captured = []
    d = _dlg(qtbot, on_create=lambda n, e: captured.append((n, e)))
    d._name_edit.setText("newproj")
    d.trigger_add_entry("/r/proj")
    d.trigger_confirm()
    assert len(captured) == 1
    name, entries = captured[0]
    assert name == "newproj"
    assert [e.worktree_path for e in entries] == ["/r/proj"]


def test_project_operations_dialog_confirm_blank_name_shows_warning(qtbot):
    captured = []
    d = _dlg(qtbot, on_create=lambda n, e: captured.append((n, e)))
    d.trigger_add_entry("/r/proj")
    d.trigger_confirm()
    assert captured == []
    assert "required" in d._name_warn.text().lower()


def test_project_operations_dialog_confirm_no_entries_shows_warning(qtbot):
    captured = []
    d = _dlg(qtbot, on_create=lambda n, e: captured.append((n, e)))
    d._name_edit.setText("p")
    d.trigger_confirm()
    assert captured == []
    assert d._entries_warn.text() != ""


def test_project_operations_dialog_confirm_edit_calls_on_edit(qtbot):
    proj = WorkspaceProject(name="old", entries=[WorkspaceEntry(worktree_path="/r/proj")])
    captured = []
    d = _dlg(qtbot, existing_project=proj,
             on_edit=lambda old, new, ents: captured.append((old, new, ents)))
    d._name_edit.setText("renamed")
    d.trigger_confirm()
    assert len(captured) == 1
    old, new, entries = captured[0]
    assert old == "old"
    assert new == "renamed"
    assert [e.worktree_path for e in entries] == ["/r/proj"]


def test_project_operations_dialog_cancel_does_not_invoke_callbacks(qtbot):
    captured = []
    d = _dlg(qtbot, on_create=lambda n, e: captured.append((n, e)))
    cancel = next(b for b in d.findChildren(QPushButton) if b.text() == "Cancel")
    cancel.click()
    assert captured == []
