"""Tests for branch dropdown updates after 'Create branch and checkout'."""
from unittest.mock import MagicMock

from PySide6.QtWidgets import QComboBox, QLineEdit, QPushButton

from worktree_manager.workspace_projects_vm import WorktreeStatus
from worktree_manager.ui.project_operations_dialog import ProjectOperationsDialog


def _status(path, branch="main", is_main=True, dirty=False):
    return WorktreeStatus(path=path, branch=branch, is_main=is_main, has_uncommitted=dirty)


def _vm(statuses, branches):
    vm = MagicMock()
    vm.list_worktrees_with_dirty.return_value = statuses
    vm.list_branches_for_worktree.return_value = branches
    return vm


def _dlg(qtbot, statuses, branches):
    vm = _vm(statuses, branches)
    vm.checkout_new_branch_on_worktree.return_value = WorktreeStatus(
        path=statuses[0].path, branch="new-feat", is_main=statuses[0].is_main,
        has_uncommitted=False,
    )
    d = ProjectOperationsDialog(
        parent=None, vm=vm,
        repos={"/repo": MagicMock()},
        on_create=lambda name, entries: None,
    )
    qtbot.addWidget(d)
    return d, vm


def _create_branch(d, branch_name="new-feat"):
    """Click 'New branch here…', fill in name, click Create."""
    btn = next(b for b in d.findChildren(QPushButton) if "New branch here" in b.text())
    btn.click()
    panel = d._active_new_branch_panel
    le = panel.findChildren(QLineEdit)[0]
    le.setText(branch_name)
    create = next(b for b in panel.findChildren(QPushButton) if "Create" in b.text())
    create.click()


# ── worktree row dropdowns ────────────────────────────────────────────────────

def test_new_branch_appears_in_row_combo_after_create(qtbot):
    statuses = [_status("/repo/main", "main", is_main=True)]
    d, _ = _dlg(qtbot, statuses, ["main", "feature/x"])
    _create_branch(d, "new-feat")
    combos = d._wt_list_widget.findChildren(QComboBox)
    assert combos, "expected at least one row combo"
    texts = [combos[0].itemText(i) for i in range(combos[0].count())]
    assert "new-feat" in texts


def test_new_branch_appears_in_all_row_combos_after_create(qtbot):
    statuses = [
        _status("/repo/main", "main", is_main=True),
        _status("/repo/ft", "feature/x", is_main=False),
    ]
    d, vm = _dlg(qtbot, statuses, ["feature/x", "main"])
    vm.checkout_new_branch_on_worktree.return_value = WorktreeStatus(
        path="/repo/main", branch="new-feat", is_main=True, has_uncommitted=False,
    )
    _create_branch(d, "new-feat")
    combos = d._wt_list_widget.findChildren(QComboBox)
    assert len(combos) >= 2
    for combo in combos:
        texts = [combo.itemText(i) for i in range(combo.count())]
        assert "new-feat" in texts, f"new-feat missing from combo with items {texts}"


def test_new_branch_is_sorted_in_row_combos(qtbot):
    statuses = [_status("/repo/main", "main", is_main=True)]
    d, _ = _dlg(qtbot, statuses, ["aaa", "zzz"])
    _create_branch(d, "mmm")
    combos = d._wt_list_widget.findChildren(QComboBox)
    texts = [combos[0].itemText(i) for i in range(combos[0].count())]
    assert texts == sorted(texts), f"combo items not sorted: {texts}"


def test_duplicate_branch_not_added_twice(qtbot):
    statuses = [_status("/repo/main", "main", is_main=True)]
    d, vm = _dlg(qtbot, statuses, ["main", "new-feat"])
    vm.checkout_new_branch_on_worktree.return_value = WorktreeStatus(
        path="/repo/main", branch="new-feat", is_main=True, has_uncommitted=False,
    )
    _create_branch(d, "new-feat")
    combos = d._wt_list_widget.findChildren(QComboBox)
    texts = [combos[0].itemText(i) for i in range(combos[0].count())]
    assert texts.count("new-feat") == 1


# ── create-worktree panel combos ──────────────────────────────────────────────

def test_new_branch_appears_in_new_base_combo_after_create(qtbot):
    statuses = [_status("/repo/main", "main", is_main=True)]
    d, _ = _dlg(qtbot, statuses, ["main", "feature/x"])
    _create_branch(d, "new-feat")
    texts = [d._new_base_combo.itemText(i) for i in range(d._new_base_combo.count())]
    assert "new-feat" in texts


def test_new_branch_appears_in_existing_branch_combo_after_create(qtbot):
    statuses = [_status("/repo/main", "main", is_main=True)]
    d, _ = _dlg(qtbot, statuses, ["main", "feature/x"])
    _create_branch(d, "new-feat")
    texts = [d._existing_branch_combo.itemText(i) for i in range(d._existing_branch_combo.count())]
    assert "new-feat" in texts
