"""Tests for 'New branch here…' inline form — Iteration 4."""
import subprocess
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QLabel, QPushButton, QLineEdit, QComboBox

from worktree_manager.models import WorktreeModel
from worktree_manager.workspace_projects_vm import WorkspaceProjectsViewModel, WorktreeStatus
from worktree_manager.ui.project_operations_dialog import ProjectOperationsDialog


# ── helpers ───────────────────────────────────────────────────────────────────

def _status(path, branch="main", is_main=True, dirty=False):
    return WorktreeStatus(path=path, branch=branch, is_main=is_main, has_uncommitted=dirty)


def _vm(statuses=None, branches=None):
    vm = MagicMock()
    vm.list_worktrees_with_dirty.return_value = statuses or []
    vm.list_branches_for_worktree.return_value = branches or ["main", "feature/x"]
    vm.create_worktree_for_project.return_value = _status("/r/new", "fix/auth", is_main=False)
    vm.checkout_new_branch_on_worktree.return_value = WorktreeStatus(
        path="/r/main", branch="new-branch", is_main=True, has_uncommitted=False
    )
    return vm


def _dlg(qtbot, vm=None, repos=None, statuses=None):
    if vm is None:
        vm = _vm(statuses=statuses or [_status("/r/main", dirty=False)])
    d = ProjectOperationsDialog(
        parent=None,
        vm=vm,
        repos=repos or {"/repos/proj": MagicMock()},
        on_create=lambda name, entries: None,
    )
    qtbot.addWidget(d)
    return d


def _click_new_branch_btn(d, row_index=0):
    """Click the 'New branch here…' button on a given worktree row."""
    btns = [b for b in d.findChildren(QPushButton) if "New branch here" in b.text()]
    btns[row_index].click()


# ── VM: checkout_new_branch_on_worktree ──────────────────────────────────────

def test_vm_checkout_new_branch_clean_delegates_to_git():
    git = MagicMock()
    git.has_uncommitted_changes.return_value = False
    git.repo_root.return_value = "/repo"
    git.list_local_branches.return_value = ["main"]
    vm = WorkspaceProjectsViewModel(MagicMock(), git, MagicMock())
    result = vm.checkout_new_branch_on_worktree("/r/main", "new-feat", "main")
    git.checkout_new_branch.assert_called_once_with("/r/main", "new-feat", "main")
    assert result.branch == "new-feat"
    assert result.path == "/r/main"


def test_vm_checkout_new_branch_dirty_current_head_allowed():
    git = MagicMock()
    git.has_uncommitted_changes.return_value = True
    git.checked_out_branch.return_value = "main"
    git.repo_root.return_value = "/repo"
    git.list_local_branches.return_value = ["main"]
    vm = WorkspaceProjectsViewModel(MagicMock(), git, MagicMock())
    result = vm.checkout_new_branch_on_worktree("/r/main", "new-feat", "HEAD")
    git.checkout_new_branch.assert_called_once_with("/r/main", "new-feat", "HEAD")
    assert result.branch == "new-feat"


def test_vm_checkout_new_branch_dirty_non_head_raises():
    git = MagicMock()
    git.has_uncommitted_changes.return_value = True
    git.checked_out_branch.return_value = "main"
    vm = WorkspaceProjectsViewModel(MagicMock(), git, MagicMock())
    with pytest.raises(ValueError, match="uncommitted"):
        vm.checkout_new_branch_on_worktree("/r/main", "new-feat", "feature/x")


def test_vm_checkout_new_branch_propagates_git_error():
    git = MagicMock()
    git.has_uncommitted_changes.return_value = False
    git.checkout_new_branch.side_effect = subprocess.CalledProcessError(
        128, "git", stderr="already exists"
    )
    vm = WorkspaceProjectsViewModel(MagicMock(), git, MagicMock())
    with pytest.raises(subprocess.CalledProcessError):
        vm.checkout_new_branch_on_worktree("/r/main", "new-feat", "main")


# ── GitService.checkout_new_branch ───────────────────────────────────────────

def test_git_checkout_new_branch_method_exists():
    from worktree_manager.git_service import GitService
    assert hasattr(GitService, "checkout_new_branch")


# ── inline form UI ───────────────────────────────────────────────────────────

def test_new_branch_form_hidden_by_default(qtbot):
    statuses = [_status("/r/main", dirty=False)]
    d = _dlg(qtbot, statuses=statuses)
    assert not d._new_branch_here_panel_visible()


def test_new_branch_form_opens_on_button_click(qtbot):
    statuses = [_status("/r/main", dirty=False)]
    d = _dlg(qtbot, statuses=statuses)
    _click_new_branch_btn(d)
    assert d._new_branch_here_panel_visible()


def test_new_branch_form_has_branch_name_field(qtbot):
    statuses = [_status("/r/main", dirty=False)]
    d = _dlg(qtbot, statuses=statuses)
    _click_new_branch_btn(d)
    panel = d._active_new_branch_panel
    assert panel is not None
    les = panel.findChildren(QLineEdit)
    assert len(les) >= 1


def test_new_branch_form_has_base_from_combo(qtbot):
    statuses = [_status("/r/main", dirty=False)]
    d = _dlg(qtbot, statuses=statuses)
    _click_new_branch_btn(d)
    panel = d._active_new_branch_panel
    combos = panel.findChildren(QComboBox)
    assert len(combos) >= 1


def test_new_branch_form_has_cancel_and_create_buttons(qtbot):
    statuses = [_status("/r/main", dirty=False)]
    d = _dlg(qtbot, statuses=statuses)
    _click_new_branch_btn(d)
    panel = d._active_new_branch_panel
    btn_texts = [b.text() for b in panel.findChildren(QPushButton)]
    assert any("Cancel" in t for t in btn_texts)
    assert any("Create" in t for t in btn_texts)


def test_new_branch_cancel_collapses_form(qtbot):
    statuses = [_status("/r/main", dirty=False)]
    d = _dlg(qtbot, statuses=statuses)
    _click_new_branch_btn(d)
    panel = d._active_new_branch_panel
    cancel = next(b for b in panel.findChildren(QPushButton) if "Cancel" in b.text())
    cancel.click()
    assert not d._new_branch_here_panel_visible()


def test_new_branch_form_only_one_open_at_a_time(qtbot):
    statuses = [
        _status("/r/main", "main", is_main=True, dirty=False),
        _status("/r/feat", "feature/x", is_main=False, dirty=False),
    ]
    d = _dlg(qtbot, statuses=statuses)
    _click_new_branch_btn(d, row_index=0)
    first_panel = d._active_new_branch_panel
    _click_new_branch_btn(d, row_index=1)
    # first panel should be gone (or invisible), second should be open
    assert d._active_new_branch_panel is not first_panel
    assert d._new_branch_here_panel_visible()


# ── dirty-aware behavior ──────────────────────────────────────────────────────

def test_clean_worktree_shows_no_warning_banner(qtbot):
    statuses = [_status("/r/main", dirty=False)]
    d = _dlg(qtbot, statuses=statuses)
    _click_new_branch_btn(d)
    panel = d._active_new_branch_panel
    labels = [lbl.text() for lbl in panel.findChildren(QLabel)]
    assert not any("uncommitted" in t.lower() for t in labels)


def test_dirty_worktree_shows_warning_banner(qtbot):
    statuses = [_status("/r/main", dirty=True)]
    d = _dlg(qtbot, statuses=statuses)
    _click_new_branch_btn(d)
    panel = d._active_new_branch_panel
    labels = [lbl.text() for lbl in panel.findChildren(QLabel)]
    assert any("uncommitted" in t.lower() for t in labels)


def test_dirty_worktree_base_combo_locked_to_head(qtbot):
    statuses = [_status("/r/main", dirty=True)]
    d = _dlg(qtbot, statuses=statuses)
    _click_new_branch_btn(d)
    panel = d._active_new_branch_panel
    combo = panel.findChildren(QComboBox)[0]
    assert not combo.isEnabled()


def test_clean_worktree_base_combo_enabled(qtbot):
    statuses = [_status("/r/main", dirty=False)]
    d = _dlg(qtbot, statuses=statuses)
    _click_new_branch_btn(d)
    panel = d._active_new_branch_panel
    combo = panel.findChildren(QComboBox)[0]
    assert combo.isEnabled()


# ── create & success ──────────────────────────────────────────────────────────

def test_create_branch_calls_vm(qtbot):
    statuses = [_status("/r/main", dirty=False)]
    vm = _vm(statuses=statuses)
    d = _dlg(qtbot, vm=vm, statuses=statuses)
    _click_new_branch_btn(d)
    panel = d._active_new_branch_panel
    le = panel.findChildren(QLineEdit)[0]
    le.setText("new-feat")
    create_btn = next(b for b in panel.findChildren(QPushButton) if "Create" in b.text())
    create_btn.click()
    vm.checkout_new_branch_on_worktree.assert_called_once()


def test_create_branch_updates_row_label(qtbot):
    statuses = [_status("/r/main", "main", dirty=False)]
    vm = _vm(statuses=statuses)
    vm.checkout_new_branch_on_worktree.return_value = WorktreeStatus(
        path="/r/main", branch="new-feat", is_main=True, has_uncommitted=False
    )
    d = _dlg(qtbot, vm=vm, statuses=statuses)
    _click_new_branch_btn(d)
    panel = d._active_new_branch_panel
    le = panel.findChildren(QLineEdit)[0]
    le.setText("new-feat")
    create_btn = next(b for b in panel.findChildren(QPushButton) if "Create" in b.text())
    create_btn.click()
    # the row's branch combo should now show the new branch name
    combos = d._wt_list_widget.findChildren(QComboBox)
    assert any(c.currentText() == "new-feat" for c in combos)


def test_create_branch_collapses_form_on_success(qtbot):
    statuses = [_status("/r/main", dirty=False)]
    vm = _vm(statuses=statuses)
    d = _dlg(qtbot, vm=vm, statuses=statuses)
    _click_new_branch_btn(d)
    panel = d._active_new_branch_panel
    le = panel.findChildren(QLineEdit)[0]
    le.setText("new-feat")
    create_btn = next(b for b in panel.findChildren(QPushButton) if "Create" in b.text())
    create_btn.click()
    assert not d._new_branch_here_panel_visible()


def test_create_branch_shows_inline_error_on_failure(qtbot):
    statuses = [_status("/r/main", dirty=False)]
    vm = _vm(statuses=statuses)
    vm.checkout_new_branch_on_worktree.side_effect = subprocess.CalledProcessError(
        128, "git", stderr="already exists"
    )
    d = _dlg(qtbot, vm=vm, statuses=statuses)
    _click_new_branch_btn(d)
    panel = d._active_new_branch_panel
    le = panel.findChildren(QLineEdit)[0]
    le.setText("new-feat")
    create_btn = next(b for b in panel.findChildren(QPushButton) if "Create" in b.text())
    create_btn.click()
    # panel must still be visible
    assert d._new_branch_here_panel_visible()
    # error message inside panel
    labels = [lbl for lbl in panel.findChildren(QLabel) if lbl.text()]
    assert any("error" in lbl.text().lower() or "already exists" in lbl.text().lower()
               for lbl in labels)
