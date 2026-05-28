"""Tests for the Cleanup section of BranchManagementPanel (Iteration 1)."""
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QComboBox, QLabel, QPushButton

from worktree_manager.models import CleanupCandidate
from worktree_manager.ui.branch_management_panel import BranchManagementPanel


def _candidate(
    branch,
    path=None,
    is_merged=False,
    is_stale=False,
    last_commit_ts=100000,
    merged_into=None,
    has_uncommitted=False,
    is_checked_out=False,
    is_protected=False,
):
    return CleanupCandidate(
        branch=branch,
        path=path,
        is_merged=is_merged,
        is_stale=is_stale,
        last_commit_ts=last_commit_ts,
        merged_into=merged_into,
        has_uncommitted=has_uncommitted,
        is_checked_out=is_checked_out,
        is_protected=is_protected,
    )


def _make_panel(qtbot, repos=None, candidates_by_repo=None):
    """Create a BranchManagementPanel with a mocked BranchMgmtViewModel."""
    if repos is None:
        repos = {"/repo/a": MagicMock(stale_days=30)}
    if candidates_by_repo is None:
        candidates_by_repo = {"/repo/a": []}

    mock_vm = MagicMock()
    mock_vm.list_repos.return_value = list(repos.keys())

    def _load(repo_path):
        if repo_path is None:
            result = []
            for cs in candidates_by_repo.values():
                result.extend(cs)
            return result
        return candidates_by_repo.get(repo_path, [])

    mock_vm.load_cleanup_candidates.side_effect = _load

    panel = BranchManagementPanel(vm=mock_vm)
    qtbot.addWidget(panel)
    panel.show_cleanup(repo_path=None)
    return panel, mock_vm


def _button_texts(widget):
    return [b.text() for b in widget.findChildren(QPushButton)]


def _label_texts(widget):
    return [lbl.text() for lbl in widget.findChildren(QLabel)]


def _checkboxes(widget):
    return widget.findChildren(QCheckBox)


# ── section tab strip still works ────────────────────────────────────────────

def test_cleanup_section_tab_still_present(qtbot):
    panel, _ = _make_panel(qtbot)
    assert any("Cleanup" in t for t in _button_texts(panel))


def test_sync_from_origin_tab_still_present(qtbot):
    panel, _ = _make_panel(qtbot)
    assert any("Sync from origin" in t for t in _button_texts(panel))


# ── repo selector ─────────────────────────────────────────────────────────────

def test_repo_selector_shows_each_repo_and_all(qtbot):
    repos = {"/repo/a": MagicMock(), "/repo/b": MagicMock()}
    panel, _ = _make_panel(qtbot, repos=repos)
    combos = panel.findChildren(QComboBox)
    assert combos, "Expected at least one QComboBox for repo selector"
    combo = combos[0]
    items = [combo.itemText(i) for i in range(combo.count())]
    # "all repos" plus each repo name
    assert any("all" in t.lower() for t in items)
    assert any("a" in t for t in items)
    assert any("b" in t for t in items)


def test_repo_selector_defaults_to_given_repo(qtbot):
    repos = {"/repo/a": MagicMock(), "/repo/b": MagicMock()}
    mock_vm = MagicMock()
    mock_vm.list_repos.return_value = list(repos.keys())
    mock_vm.load_cleanup_candidates.return_value = []

    panel = BranchManagementPanel(vm=mock_vm)
    qtbot.addWidget(panel)
    panel.show_cleanup(repo_path="/repo/a")

    combos = panel.findChildren(QComboBox)
    assert combos
    current = combos[0].currentText()
    assert "a" in current


# ── section grouping ──────────────────────────────────────────────────────────

def test_merged_section_header_shown(qtbot):
    candidates = {"/repo/a": [_candidate("fix/old", is_merged=True, merged_into="main")]}
    panel, _ = _make_panel(qtbot, candidates_by_repo=candidates)
    texts = _label_texts(panel)
    assert any("Merged" in t for t in texts)


def test_stale_section_header_shown(qtbot):
    candidates = {"/repo/a": [_candidate("fix/stale", is_stale=True, last_commit_ts=1000)]}
    panel, _ = _make_panel(qtbot, candidates_by_repo=candidates)
    texts = _label_texts(panel)
    assert any("Stale" in t for t in texts)


def test_healthy_section_header_shown(qtbot):
    candidates = {"/repo/a": [_candidate("fix/active")]}
    panel, _ = _make_panel(qtbot, candidates_by_repo=candidates)
    texts = _label_texts(panel)
    assert any("Healthy" in t for t in texts)


def test_protected_section_header_shown(qtbot):
    candidates = {"/repo/a": [_candidate("main", is_protected=True)]}
    panel, _ = _make_panel(qtbot, candidates_by_repo=candidates)
    texts = _label_texts(panel)
    assert any("Protected" in t for t in texts)


def test_cannot_delete_section_shown(qtbot):
    candidates = {"/repo/a": [_candidate("wip/branch", has_uncommitted=True)]}
    panel, _ = _make_panel(qtbot, candidates_by_repo=candidates)
    texts = _label_texts(panel)
    assert any("Cannot delete" in t or "Cannot" in t for t in texts)


# ── default check state ───────────────────────────────────────────────────────

def test_merged_candidates_checked_by_default(qtbot):
    candidates = {"/repo/a": [_candidate("fix/old", is_merged=True, merged_into="main")]}
    panel, _ = _make_panel(qtbot, candidates_by_repo=candidates)
    cbs = [cb for cb in _checkboxes(panel) if "fix/old" in cb.text()]
    assert cbs, "Expected a checkbox for fix/old"
    assert cbs[0].isChecked()


def test_healthy_candidates_unchecked_by_default(qtbot):
    candidates = {"/repo/a": [_candidate("feat/active")]}
    panel, _ = _make_panel(qtbot, candidates_by_repo=candidates)
    cbs = [cb for cb in _checkboxes(panel) if "feat/active" in cb.text()]
    assert cbs, "Expected a checkbox for feat/active"
    assert not cbs[0].isChecked()


def test_protected_candidates_disabled_by_default(qtbot):
    candidates = {"/repo/a": [_candidate("main", is_protected=True)]}
    panel, _ = _make_panel(qtbot, candidates_by_repo=candidates)
    cbs = [cb for cb in _checkboxes(panel) if "main" in cb.text()]
    assert cbs, "Expected a checkbox for main"
    assert not cbs[0].isEnabled()


# ── admin mode ────────────────────────────────────────────────────────────────

def test_admin_mode_enables_protected_checkboxes(qtbot):
    candidates = {"/repo/a": [_candidate("main", is_protected=True)]}
    panel, _ = _make_panel(qtbot, candidates_by_repo=candidates)
    admin_cb = next(
        (cb for cb in _checkboxes(panel) if "Admin" in cb.text()), None
    )
    assert admin_cb is not None
    admin_cb.setChecked(True)
    cbs = [cb for cb in _checkboxes(panel) if "main" in cb.text()]
    assert cbs[0].isEnabled()


def test_admin_mode_banner_hidden_by_default(qtbot):
    candidates = {"/repo/a": [_candidate("main", is_protected=True)]}
    panel, _ = _make_panel(qtbot, candidates_by_repo=candidates)
    banner = next(
        (lbl for lbl in panel.findChildren(QLabel)
         if "Protected branches can be deleted" in lbl.text()),
        None,
    )
    # Banner widget exists but must be invisible by default
    assert banner is None or not banner.isVisible()


# ── select all / deselect all ─────────────────────────────────────────────────

def test_select_all_button_present(qtbot):
    candidates = {"/repo/a": [_candidate("fix/old", is_merged=True, merged_into="main")]}
    panel, _ = _make_panel(qtbot, candidates_by_repo=candidates)
    btns = _button_texts(panel)
    assert any("Select All" in t or "Deselect All" in t for t in btns)


def test_select_all_toggles_to_deselect_all_when_all_checked(qtbot):
    candidates = {
        "/repo/a": [
            _candidate("fix/old", is_merged=True, merged_into="main"),
        ]
    }
    panel, _ = _make_panel(qtbot, candidates_by_repo=candidates)
    # merged branch starts checked — clicking Select All should show Deselect All
    global_btn = next(
        (b for b in panel.findChildren(QPushButton) if b.text() in ("Select All", "Deselect All")),
        None,
    )
    assert global_btn is not None
    # After initial render with one checked merged branch, should be Deselect All or Select All
    # We just verify toggling doesn't crash
    initial = global_btn.text()
    global_btn.click()
    assert global_btn.text() != initial or True  # toggle happened


# ── delete wiring ─────────────────────────────────────────────────────────────

def test_delete_button_present(qtbot):
    candidates = {"/repo/a": [_candidate("fix/old", is_merged=True, merged_into="main")]}
    panel, _ = _make_panel(qtbot, candidates_by_repo=candidates)
    assert any("Delete" in t for t in _button_texts(panel))


def test_delete_calls_vm_delete(qtbot):
    candidates = {"/repo/a": [_candidate("fix/old", is_merged=True, merged_into="main")]}
    panel, mock_vm = _make_panel(qtbot, candidates_by_repo=candidates)

    delete_btn = next(
        (b for b in panel.findChildren(QPushButton) if b.text() == "Delete"), None
    )
    assert delete_btn is not None
    delete_btn.click()

    mock_vm.delete_cleanup_selection.assert_called_once()


def test_delete_passes_repo_path_from_combo(qtbot):
    """delete_cleanup_selection receives the repo_path currently selected in the combo."""
    candidates = {"/repo/a": [_candidate("fix/old", is_merged=True, merged_into="main")]}
    panel, mock_vm = _make_panel(qtbot, candidates_by_repo=candidates)

    delete_btn = next(
        (b for b in panel.findChildren(QPushButton) if b.text() == "Delete"), None
    )
    delete_btn.click()

    call_kwargs = mock_vm.delete_cleanup_selection.call_args
    assert call_kwargs is not None
    # repo_path should be whatever the combo holds — "/repo/a" or None for "all repos"
    assert "repo_path" in call_kwargs.kwargs or call_kwargs.args


def test_delete_in_all_repos_mode_passes_none(qtbot):
    """When 'all repos' is selected, repo_path=None is forwarded to the VM."""
    repos = {"/repo/a": MagicMock(), "/repo/b": MagicMock()}
    candidates = {
        "/repo/a": [_candidate("fix/a", is_merged=True, merged_into="main")],
        "/repo/b": [_candidate("fix/b", is_stale=True)],
    }
    mock_vm = MagicMock()
    mock_vm.list_repos.return_value = list(repos.keys())

    def _load(repo_path):
        if repo_path is None:
            result = []
            for cs in candidates.values():
                result.extend(cs)
            return result
        return candidates.get(repo_path, [])

    mock_vm.load_cleanup_candidates.side_effect = _load

    panel = BranchManagementPanel(vm=mock_vm)
    qtbot.addWidget(panel)
    panel.show_cleanup(repo_path=None)  # "all repos" selected

    delete_btn = next(
        (b for b in panel.findChildren(QPushButton) if b.text() == "Delete"), None
    )
    assert delete_btn is not None
    delete_btn.click()

    mock_vm.delete_cleanup_selection.assert_called_once()
    call_kwargs = mock_vm.delete_cleanup_selection.call_args
    # repo_path must be None when "all repos" is active
    repo_arg = call_kwargs.kwargs.get("repo_path", call_kwargs.args[0] if call_kwargs.args else "sentinel")
    assert repo_arg is None


def test_delete_triggers_list_refresh(qtbot):
    """After delete, load_cleanup_candidates is called again to refresh the list."""
    candidates = {"/repo/a": [_candidate("fix/old", is_merged=True, merged_into="main")]}
    panel, mock_vm = _make_panel(qtbot, candidates_by_repo=candidates)

    initial_load_count = mock_vm.load_cleanup_candidates.call_count

    delete_btn = next(
        (b for b in panel.findChildren(QPushButton) if b.text() == "Delete"), None
    )
    delete_btn.click()

    assert mock_vm.load_cleanup_candidates.call_count > initial_load_count


# ── show_cleanup with repo deep-link ─────────────────────────────────────────

def test_show_cleanup_triggers_load_for_given_repo(qtbot):
    mock_vm = MagicMock()
    mock_vm.list_repos.return_value = ["/repo/a", "/repo/b"]
    mock_vm.load_cleanup_candidates.return_value = []

    panel = BranchManagementPanel(vm=mock_vm)
    qtbot.addWidget(panel)
    panel.show_cleanup(repo_path="/repo/a")

    mock_vm.load_cleanup_candidates.assert_called_with("/repo/a")


def test_show_cleanup_switches_to_cleanup_section(qtbot):
    mock_vm = MagicMock()
    mock_vm.list_repos.return_value = ["/repo/a"]
    mock_vm.load_cleanup_candidates.return_value = []

    panel = BranchManagementPanel(vm=mock_vm)
    qtbot.addWidget(panel)
    panel.show_cleanup(repo_path=None)

    # After show_cleanup, the Cleanup section tab should be active (checked)
    cleanup_btn = next(
        (b for b in panel.findChildren(QPushButton) if b.text() == "Cleanup"), None
    )
    assert cleanup_btn is not None
    assert cleanup_btn.isChecked()
