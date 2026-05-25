import time
from unittest.mock import MagicMock

from PySide6.QtWidgets import QDialog, QCheckBox, QPushButton

from worktree_manager.models import CleanupCandidate
from worktree_manager.ui.cleanup_wizard import CleanupWizard


def _c(branch="feat", is_merged=False, is_stale=False, is_protected=False,
       has_uncommitted=False, is_checked_out=False, merged_into=None,
       last_commit_ts=None):
    return CleanupCandidate(
        branch=branch, path=f"/r/{branch}",
        is_merged=is_merged, is_stale=is_stale, is_protected=is_protected,
        has_uncommitted=has_uncommitted, is_checked_out=is_checked_out,
        merged_into=merged_into,
        last_commit_ts=last_commit_ts if last_commit_ts is not None else int(time.time()),
    )


def _wiz(qtbot, candidates=None, on_delete=None):
    w = CleanupWizard(parent=None, candidates=candidates,
                      on_delete_selected=on_delete or (lambda _sel: None))
    qtbot.addWidget(w)
    return w


def test_cleanup_wizard_is_qdialog(qtbot):
    assert isinstance(_wiz(qtbot, candidates=[]), QDialog)


def test_cleanup_wizard_shows_merged_branches(qtbot):
    w = _wiz(qtbot, candidates=[_c(branch="feature-a", is_merged=True, merged_into="main")])
    texts = " ".join(cb.text() for cb in w.findChildren(QCheckBox))
    assert "feature-a" in texts


def test_cleanup_wizard_merged_branches_default_checked(qtbot):
    w = _wiz(qtbot, candidates=[_c(branch="m", is_merged=True)])
    box = next(cb for cb in w.findChildren(QCheckBox) if "m" in cb.text() and cb.isEnabled())
    assert box.isChecked() is True


def test_cleanup_wizard_stale_branches_default_checked(qtbot):
    w = _wiz(qtbot, candidates=[_c(branch="old", is_stale=True)])
    box = next(cb for cb in w.findChildren(QCheckBox) if "old" in cb.text() and cb.isEnabled())
    assert box.isChecked() is True


def test_cleanup_wizard_healthy_branches_default_unchecked(qtbot):
    w = _wiz(qtbot, candidates=[_c(branch="fresh")])
    box = next(cb for cb in w.findChildren(QCheckBox) if "fresh" in cb.text() and cb.isEnabled())
    assert box.isChecked() is False


def test_cleanup_wizard_protected_branches_disabled_by_default(qtbot):
    w = _wiz(qtbot, candidates=[_c(branch="main", is_protected=True)])
    box = next(cb for cb in w.findChildren(QCheckBox) if "main" in cb.text())
    assert box.isEnabled() is False


def test_cleanup_wizard_admin_mode_enables_protected(qtbot):
    w = _wiz(qtbot, candidates=[_c(branch="main", is_protected=True)])
    w.set_admin_mode(True)
    box = next(cb for cb in w.findChildren(QCheckBox) if "main" in cb.text())
    assert box.isEnabled() is True


def test_cleanup_wizard_admin_mode_off_resets_protected_selection(qtbot):
    w = _wiz(qtbot, candidates=[_c(branch="main", is_protected=True)])
    w.set_admin_mode(True)
    box = next(cb for cb in w.findChildren(QCheckBox) if "main" in cb.text())
    box.setChecked(True)
    w.set_admin_mode(False)
    assert box.isChecked() is False
    assert box.isEnabled() is False


def test_cleanup_wizard_unoperable_branches_not_selectable(qtbot):
    w = _wiz(qtbot, candidates=[_c(branch="dirty", has_uncommitted=True)])
    boxes = [cb for cb in w.findChildren(QCheckBox) if "dirty" in cb.text()]
    assert boxes == []  # unoperable rows are plain labels, not checkboxes


def test_cleanup_wizard_select_all_toggles_all_operable(qtbot):
    w = _wiz(qtbot, candidates=[_c(branch="fresh"), _c(branch="m", is_merged=True)])
    w.trigger_select_all()
    assert all(v for _, v in w.selection_state())
    w.trigger_select_all()
    assert all(not v for _, v in w.selection_state())


def test_cleanup_wizard_subgroup_select_all_targets_merged_into(qtbot):
    w = _wiz(qtbot, candidates=[
        _c(branch="a", is_merged=True, merged_into="main"),
        _c(branch="b", is_merged=True, merged_into="dev"),
    ])
    # both start checked (merged default); deselect all first
    w.trigger_select_all()  # all_checked=True → deselect all
    state_before = dict((c.branch, v) for c, v in w.selection_state())
    assert state_before["a"] is False
    assert state_before["b"] is False
    # now select only the "main" subgroup
    w.trigger_subgroup_select("main")
    state = dict((c.branch, v) for c, v in w.selection_state())
    assert state["a"] is True
    assert state["b"] is False


def test_cleanup_wizard_delete_passes_selected_candidates(qtbot):
    captured = []
    w = _wiz(qtbot, candidates=[_c(branch="m", is_merged=True), _c(branch="fresh")],
             on_delete=lambda sel: captured.append(sel))
    w.trigger_delete()
    assert len(captured) == 1
    names = [c.branch for c in captured[0]]
    assert names == ["m"]  # only checked-by-default merged branch


def test_cleanup_wizard_delete_includes_protected_when_admin_mode(qtbot):
    captured = []
    w = _wiz(qtbot, candidates=[_c(branch="main", is_protected=True)],
             on_delete=lambda sel: captured.append(sel))
    w.set_admin_mode(True)
    box = next(cb for cb in w.findChildren(QCheckBox) if "main" in cb.text())
    box.setChecked(True)
    w.trigger_delete()
    assert [c.branch for c in captured[0]] == ["main"]


def test_cleanup_wizard_deferred_load_shows_progress(qtbot):
    w = _wiz(qtbot, candidates=None)
    assert w.is_loading() is True
    w.update_progress(3, 10, "Scanning origin/feature-x …")
    assert "3" in w.progress_text()
    assert "10" in w.progress_text()


def test_cleanup_wizard_finish_loading_swaps_to_real_ui(qtbot):
    w = _wiz(qtbot, candidates=None)
    w.finish_loading([_c(branch="m", is_merged=True)])
    assert w.is_loading() is False
    texts = " ".join(cb.text() for cb in w.findChildren(QCheckBox))
    assert "m" in texts


def test_cleanup_wizard_cancel_does_not_invoke_callback(qtbot):
    captured = []
    w = _wiz(qtbot, candidates=[_c(branch="m", is_merged=True)],
             on_delete=lambda sel: captured.append(sel))
    cancel = next(b for b in w.findChildren(QPushButton) if b.text() == "Cancel")
    cancel.click()
    assert captured == []
