"""Tests for SettingsDialog Default editor row."""
import pytest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QComboBox, QLabel

from worktree_manager.ui.settings_panel import SettingsDialog


def _make_dialog(qtbot, editor_pref="cursor"):
    vm = MagicMock()
    vm.worktree_storage = "~/repos"
    vm.stale_days = 30
    store = MagicMock()
    store.get_ui_pref.side_effect = lambda key, default=None: {
        "shell": "zsh",
        "editor": editor_pref,
    }.get(key, default)
    dialog = SettingsDialog(None, vm, store=store)
    qtbot.addWidget(dialog)
    return dialog, vm, store


# ── default editor row presence ───────────────────────────────────────────────

def test_settings_has_default_editor_label(qtbot):
    dialog, _, _ = _make_dialog(qtbot)
    labels = dialog.findChildren(QLabel)
    assert any("editor" in l.text().lower() for l in labels)


def test_settings_has_editor_combo(qtbot):
    dialog, _, _ = _make_dialog(qtbot)
    assert dialog._editor_combo is not None


def test_editor_combo_has_cursor_option(qtbot):
    dialog, _, _ = _make_dialog(qtbot)
    items = [dialog._editor_combo.itemText(i) for i in range(dialog._editor_combo.count())]
    assert any("Cursor" in item for item in items)


def test_editor_combo_has_vscode_option(qtbot):
    dialog, _, _ = _make_dialog(qtbot)
    items = [dialog._editor_combo.itemText(i) for i in range(dialog._editor_combo.count())]
    assert any("VS Code" in item or "VSCode" in item for item in items)


# ── persisted value loaded ────────────────────────────────────────────────────

def test_editor_combo_loads_cursor_pref(qtbot):
    dialog, _, _ = _make_dialog(qtbot, editor_pref="cursor")
    assert "Cursor" in dialog._editor_combo.currentText()


def test_editor_combo_loads_vscode_pref(qtbot):
    dialog, _, _ = _make_dialog(qtbot, editor_pref="vscode")
    assert "VS Code" in dialog._editor_combo.currentText() or "VSCode" in dialog._editor_combo.currentText()


# ── save persists selection ───────────────────────────────────────────────────

def test_save_persists_cursor_selection(qtbot):
    dialog, vm, store = _make_dialog(qtbot, editor_pref="cursor")
    cursor_idx = next(
        i for i in range(dialog._editor_combo.count())
        if "Cursor" in dialog._editor_combo.itemText(i)
    )
    dialog._editor_combo.setCurrentIndex(cursor_idx)
    dialog._save()
    store.set_ui_pref.assert_any_call("editor", "cursor")


def test_save_persists_vscode_selection(qtbot):
    dialog, vm, store = _make_dialog(qtbot, editor_pref="cursor")
    vscode_idx = next(
        i for i in range(dialog._editor_combo.count())
        if "VS Code" in dialog._editor_combo.itemText(i) or "VSCode" in dialog._editor_combo.itemText(i)
    )
    dialog._editor_combo.setCurrentIndex(vscode_idx)
    dialog._save()
    store.set_ui_pref.assert_any_call("editor", "vscode")
