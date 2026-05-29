from unittest.mock import MagicMock

from PySide6.QtWidgets import QComboBox, QLabel, QMessageBox

from worktree_manager.ui.project_operations_dialog import ProjectOperationsDialog
from worktree_manager.workspace_projects_vm import WorktreeStatus


def _make_statuses():
    return [
        WorktreeStatus(path="/repo/main", branch="main", is_main=True, has_uncommitted=False),
        WorktreeStatus(path="/repo/ft-auth", branch="feature/auth", is_main=False, has_uncommitted=False),
    ]


def _make_vm(statuses=None, branches=None):
    vm = MagicMock()
    vm.list_worktrees_with_dirty.return_value = statuses or _make_statuses()
    vm.list_branches_for_worktree.return_value = branches or ["main", "feature/auth", "feature/x"]
    return vm


def _dlg(qtbot, vm=None):
    d = ProjectOperationsDialog(
        parent=None,
        vm=vm or _make_vm(),
        repos={"/repo": MagicMock()},
        on_create=lambda name, entries: None,
    )
    qtbot.addWidget(d)
    return d


def _find_combos(dialog):
    return dialog._wt_list_widget.findChildren(QComboBox)


def test_worktree_rows_have_branch_combo(qtbot):
    d = _dlg(qtbot)
    combos = _find_combos(d)
    assert len(combos) >= 2


def test_branch_combo_populated_with_branches(qtbot):
    d = _dlg(qtbot, _make_vm(branches=["main", "feature/auth", "feature/x"]))
    combos = _find_combos(d)
    texts = [combos[0].itemText(i) for i in range(combos[0].count())]
    assert "main" in texts
    assert "feature/auth" in texts
    assert "feature/x" in texts


def test_branch_combo_shows_current_branch_selected(qtbot):
    d = _dlg(qtbot, _make_vm(
        statuses=[WorktreeStatus(path="/repo/ft-auth", branch="feature/auth", is_main=False, has_uncommitted=False)],
        branches=["main", "feature/auth", "feature/x"],
    ))
    combos = _find_combos(d)
    assert combos[0].currentText() == "feature/auth"


def test_dirty_marker_still_shown(qtbot):
    statuses = [
        WorktreeStatus(path="/repo/ft", branch="feature/x", is_main=False, has_uncommitted=True),
    ]
    d = _dlg(qtbot, _make_vm(statuses=statuses))
    labels = d._wt_list_widget.findChildren(QLabel)
    texts = [lbl.text() for lbl in labels]
    assert any("dirty" in t for t in texts)


def test_branch_switch_calls_vm(qtbot):
    vm = _make_vm()
    d = _dlg(qtbot, vm)
    combos = _find_combos(d)
    assert combos
    # simulate switching branch
    combos[0].setCurrentText("feature/x")
    vm.switch_branch_in_project.assert_called()


def test_branch_switch_reverts_on_conflict(qtbot, monkeypatch):
    vm = _make_vm()
    vm.switch_branch_in_project.side_effect = ValueError("already checked out")
    d = _dlg(qtbot, vm)
    combos = _find_combos(d)
    assert combos
    original = combos[0].currentText()

    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **kw: None)
    combos[0].setCurrentText("feature/x")

    # combo should have been reverted to its prior value
    assert combos[0].currentText() == original
