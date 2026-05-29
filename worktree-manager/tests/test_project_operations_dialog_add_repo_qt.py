"""Tests for ProjectOperationsDialog Iteration 3: inline Add Repo panel."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QLabel, QPushButton, QLineEdit

from worktree_manager.ui.project_operations_dialog import ProjectOperationsDialog
from worktree_manager.workspace_projects_vm import WorktreeStatus


def _vm():
    vm = MagicMock()
    vm.list_worktrees_with_dirty.return_value = []
    vm.list_branches_for_worktree.return_value = ["main"]
    return vm


def _store(repos=None):
    store = MagicMock()
    store.all_repos.return_value = repos or {"/repos/proj": MagicMock()}
    return store


def _dlg(qtbot, vm=None, repos=None, config_store=None):
    d = ProjectOperationsDialog(
        parent=None,
        vm=vm or _vm(),
        repos=repos or {"/repos/proj": MagicMock()},
        on_create=lambda name, entries: None,
        config_store=config_store or _store(),
    )
    qtbot.addWidget(d)
    return d


def _button_texts(widget):
    return [b.text() for b in widget.findChildren(QPushButton)]


# ── "+ Add repo…" button presence ────────────────────────────────────────────

def test_add_repo_button_present(qtbot):
    d = _dlg(qtbot)
    btns = _button_texts(d)
    assert any("Add repo" in t for t in btns), f"Expected 'Add repo' button in {btns}"


def test_add_repo_panel_hidden_by_default(qtbot):
    d = _dlg(qtbot)
    assert not d._add_repo_panel.isVisibleTo(d)


def test_add_repo_button_shows_panel(qtbot):
    d = _dlg(qtbot)
    btn = next(b for b in d.findChildren(QPushButton) if "Add repo" in b.text())
    btn.click()
    assert d._add_repo_panel.isVisibleTo(d)


def test_add_repo_button_disabled_when_panel_open(qtbot):
    d = _dlg(qtbot)
    btn = next(b for b in d.findChildren(QPushButton) if "Add repo" in b.text())
    btn.click()
    assert not btn.isEnabled()


def test_add_repo_button_re_enabled_on_cancel(qtbot):
    d = _dlg(qtbot)
    btn = next(b for b in d.findChildren(QPushButton) if "Add repo" in b.text())
    btn.click()
    cancel_btn = next(
        b for b in d._add_repo_panel.findChildren(QPushButton) if b.text() == "Cancel"
    )
    cancel_btn.click()
    assert btn.isEnabled()
    assert not d._add_repo_panel.isVisibleTo(d)


# ── Panel fields ──────────────────────────────────────────────────────────────

def test_add_repo_panel_has_repo_path_field(qtbot):
    d = _dlg(qtbot)
    btn = next(b for b in d.findChildren(QPushButton) if "Add repo" in b.text())
    btn.click()
    inputs = d._add_repo_panel.findChildren(QLineEdit)
    assert len(inputs) >= 1


def test_add_repo_panel_has_storage_path_field(qtbot):
    d = _dlg(qtbot)
    btn = next(b for b in d.findChildren(QPushButton) if "Add repo" in b.text())
    btn.click()
    inputs = d._add_repo_panel.findChildren(QLineEdit)
    assert len(inputs) >= 2


def test_add_repo_panel_has_add_repo_confirm_button(qtbot):
    d = _dlg(qtbot)
    btn = next(b for b in d.findChildren(QPushButton) if "Add repo" in b.text())
    btn.click()
    panel_btns = _button_texts(d._add_repo_panel)
    assert any("Add Repo" in t for t in panel_btns), f"Expected 'Add Repo' in {panel_btns}"


# ── Validation ────────────────────────────────────────────────────────────────

def test_empty_repo_path_shows_error(qtbot):
    d = _dlg(qtbot)
    btn = next(b for b in d.findChildren(QPushButton) if "Add repo" in b.text())
    btn.click()
    confirm_btn = next(
        b for b in d._add_repo_panel.findChildren(QPushButton) if "Add Repo" in b.text()
    )
    confirm_btn.click()
    error_labels = [lbl for lbl in d._add_repo_panel.findChildren(QLabel) if lbl.text()]
    assert any("error" in lbl.text().lower() or "required" in lbl.text().lower()
               for lbl in error_labels), f"Expected error label, got: {[l.text() for l in error_labels]}"
    assert d._add_repo_panel.isVisibleTo(d)


def test_nonexistent_repo_path_shows_error(qtbot, tmp_path):
    d = _dlg(qtbot)
    btn = next(b for b in d.findChildren(QPushButton) if "Add repo" in b.text())
    btn.click()
    inputs = d._add_repo_panel.findChildren(QLineEdit)
    inputs[0].setText(str(tmp_path / "no_such_repo"))
    inputs[1].setText(str(tmp_path / "storage"))
    confirm_btn = next(
        b for b in d._add_repo_panel.findChildren(QPushButton) if "Add Repo" in b.text()
    )
    confirm_btn.click()
    error_labels = [lbl for lbl in d._add_repo_panel.findChildren(QLabel) if lbl.text()]
    assert any("error" in lbl.text().lower() or "not found" in lbl.text().lower() or "does not exist" in lbl.text().lower()
               for lbl in error_labels), f"Expected error label, got: {[l.text() for l in error_labels]}"
    assert d._add_repo_panel.isVisibleTo(d)


# ── Success path ──────────────────────────────────────────────────────────────

def test_successful_add_repo_calls_store_save(qtbot, tmp_path):
    repo_path = tmp_path / "my-repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()
    storage_path = tmp_path / "my-repo-worktrees"

    store = _store(repos={str(repo_path): MagicMock()})
    d = _dlg(qtbot, config_store=store, repos={str(repo_path): MagicMock()})

    btn = next(b for b in d.findChildren(QPushButton) if "Add repo" in b.text())
    btn.click()
    inputs = d._add_repo_panel.findChildren(QLineEdit)
    inputs[0].setText(str(repo_path))
    inputs[1].setText(str(storage_path))

    confirm_btn = next(
        b for b in d._add_repo_panel.findChildren(QPushButton) if "Add Repo" in b.text()
    )
    confirm_btn.click()

    store.save_repo.assert_called_once()


def test_successful_add_repo_closes_panel(qtbot, tmp_path):
    repo_path = tmp_path / "my-repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()
    storage_path = tmp_path / "my-repo-worktrees"

    store = _store(repos={str(repo_path): MagicMock()})
    d = _dlg(qtbot, config_store=store, repos={str(repo_path): MagicMock()})

    btn = next(b for b in d.findChildren(QPushButton) if "Add repo" in b.text())
    btn.click()
    inputs = d._add_repo_panel.findChildren(QLineEdit)
    inputs[0].setText(str(repo_path))
    inputs[1].setText(str(storage_path))

    confirm_btn = next(
        b for b in d._add_repo_panel.findChildren(QPushButton) if "Add Repo" in b.text()
    )
    confirm_btn.click()

    assert not d._add_repo_panel.isVisibleTo(d)


def test_successful_add_repo_adds_to_combo(qtbot, tmp_path):
    repo_path = tmp_path / "my-repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()
    storage_path = tmp_path / "my-repo-worktrees"

    existing_repos = {"/repos/existing": MagicMock()}
    new_repos = {"/repos/existing": MagicMock(), str(repo_path): MagicMock()}
    store = _store(repos=existing_repos)
    # all_repos() is called once inside _submit_add_repo after save_repo
    store.all_repos.return_value = new_repos

    d = _dlg(qtbot, config_store=store, repos=existing_repos)

    btn = next(b for b in d.findChildren(QPushButton) if "Add repo" in b.text())
    btn.click()
    inputs = d._add_repo_panel.findChildren(QLineEdit)
    inputs[0].setText(str(repo_path))
    inputs[1].setText(str(storage_path))

    confirm_btn = next(
        b for b in d._add_repo_panel.findChildren(QPushButton) if "Add Repo" in b.text()
    )
    confirm_btn.click()

    combo_items = [d._repo_combo.itemText(i) for i in range(d._repo_combo.count())]
    assert any("my-repo" in item for item in combo_items), f"New repo not in combo: {combo_items}"


def test_successful_add_repo_selects_new_repo_in_combo(qtbot, tmp_path):
    repo_path = tmp_path / "my-repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()
    storage_path = tmp_path / "my-repo-worktrees"

    existing_repos = {"/repos/existing": MagicMock()}
    new_repos = {"/repos/existing": MagicMock(), str(repo_path): MagicMock()}
    store = _store(repos=existing_repos)
    store.all_repos.return_value = new_repos

    d = _dlg(qtbot, config_store=store, repos=existing_repos)

    btn = next(b for b in d.findChildren(QPushButton) if "Add repo" in b.text())
    btn.click()
    inputs = d._add_repo_panel.findChildren(QLineEdit)
    inputs[0].setText(str(repo_path))
    inputs[1].setText(str(storage_path))

    confirm_btn = next(
        b for b in d._add_repo_panel.findChildren(QPushButton) if "Add Repo" in b.text()
    )
    confirm_btn.click()

    assert "my-repo" in d._repo_combo.currentText()


def test_successful_add_repo_re_enables_button(qtbot, tmp_path):
    repo_path = tmp_path / "my-repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()
    storage_path = tmp_path / "my-repo-worktrees"

    store = _store(repos={str(repo_path): MagicMock()})
    d = _dlg(qtbot, config_store=store, repos={str(repo_path): MagicMock()})

    btn = next(b for b in d.findChildren(QPushButton) if "Add repo" in b.text())
    btn.click()
    inputs = d._add_repo_panel.findChildren(QLineEdit)
    inputs[0].setText(str(repo_path))
    inputs[1].setText(str(storage_path))

    confirm_btn = next(
        b for b in d._add_repo_panel.findChildren(QPushButton) if "Add Repo" in b.text()
    )
    confirm_btn.click()

    assert btn.isEnabled()


# ── Storage path auto-fill ────────────────────────────────────────────────────

def test_storage_path_autofills_when_repo_path_entered(qtbot, tmp_path):
    repo_path = tmp_path / "cool-project"
    d = _dlg(qtbot)
    btn = next(b for b in d.findChildren(QPushButton) if "Add repo" in b.text())
    btn.click()
    inputs = d._add_repo_panel.findChildren(QLineEdit)
    inputs[0].setText(str(repo_path))
    assert "cool-project" in inputs[1].text()
