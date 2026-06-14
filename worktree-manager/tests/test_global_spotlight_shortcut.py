"""
Tests for Iteration 0 — Customizable, global Spotlight shortcut.

Covers:
  - ConfigStore.get_spotlight_shortcut / set_spotlight_shortcut
  - parse_combo (pure, no Qt/Carbon)
  - GlobalHotkey.register (platform guard + darwin success)
  - SettingsDialog shortcut row UI
  - App.apply_spotlight_shortcut rebinding QShortcut
"""

import sys

import pytest


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_store(tmp_path):
    from worktree_manager.config_store import ConfigStore
    return ConfigStore(path=tmp_path / "config.json")


def _seed_app(tmp_path, monkeypatch):
    """Return a fresh App wired to a temp ConfigStore."""
    from worktree_manager.config_store import ConfigStore
    cfg_path = tmp_path / "config.json"
    monkeypatch.setattr(
        "worktree_manager.cli.ConfigStore",
        lambda: ConfigStore(path=cfg_path),
    )
    from worktree_manager.cli import App
    return App()


# ===========================================================================
# 1. ConfigStore — get_spotlight_shortcut default
# ===========================================================================

def test_default_spotlight_shortcut_is_ctrl_k(tmp_path):
    store = _make_store(tmp_path)
    assert store.get_spotlight_shortcut() == "Ctrl+K"


# ===========================================================================
# 2. ConfigStore — set then get round-trips
# ===========================================================================

def test_saved_spotlight_shortcut_round_trips(tmp_path):
    store = _make_store(tmp_path)
    store.set_spotlight_shortcut("Ctrl+J")
    assert store.get_spotlight_shortcut() == "Ctrl+J"


# ===========================================================================
# 3-6. parse_combo — pure unit tests (no Qt, no Carbon)
# ===========================================================================

def test_parse_combo_maps_cmd_k():
    from worktree_manager.spotlight.combo import parse_combo
    keycode, mask = parse_combo("Ctrl+K")
    assert keycode == 0x28            # kVK_ANSI_K
    assert mask & 0x100               # cmdKey bit set


def test_parse_combo_maps_multiple_modifiers():
    from worktree_manager.spotlight.combo import parse_combo
    keycode, mask = parse_combo("Ctrl+Shift+Space")
    assert keycode == 0x31            # kVK_ANSI_Space
    assert mask & 0x100               # cmdKey
    assert mask & 0x200               # shiftKey


def test_parse_combo_rejects_bare_key():
    from worktree_manager.spotlight.combo import parse_combo
    with pytest.raises(ValueError, match="modifier"):
        parse_combo("A")


def test_parse_combo_rejects_unknown_key():
    from worktree_manager.spotlight.combo import parse_combo
    with pytest.raises(ValueError):
        parse_combo("Ctrl+ZZZ")


# ===========================================================================
# 7. GlobalHotkey — no-op off darwin
# ===========================================================================

def test_global_hotkey_register_returns_false_off_macos(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    # Re-import to pick up the patched platform in the module guard
    import importlib
    import worktree_manager.global_hotkey as gh_mod
    importlib.reload(gh_mod)
    gh = gh_mod.GlobalHotkey()
    result = gh.register(0x28, 0x100)
    assert result is False
    # Restore
    importlib.reload(gh_mod)


# ===========================================================================
# 8. GlobalHotkey — succeeds on darwin (skip off darwin)
# ===========================================================================

@pytest.mark.skipif(sys.platform != "darwin", reason="Carbon only on macOS")
def test_global_hotkey_register_succeeds_on_macos():
    from worktree_manager.global_hotkey import GlobalHotkey
    gh = GlobalHotkey()
    gh.set_callback(lambda: None)
    result = gh.register(0x28, 0x100)   # Ctrl+K
    assert result is True
    gh.unregister()


# ===========================================================================
# 9. SettingsDialog — shows current shortcut in field
# ===========================================================================

def test_settings_dialog_shows_current_shortcut(qtbot, tmp_path):
    from PySide6.QtWidgets import QLineEdit
    from unittest.mock import MagicMock
    from worktree_manager.setup_settings_vm import SettingsViewModel
    from worktree_manager.ui.settings_panel import SettingsDialog

    store = _make_store(tmp_path)
    store.set_spotlight_shortcut("Ctrl+J")

    vm = MagicMock(spec=SettingsViewModel)
    vm.worktree_storage = "/x"
    vm.stale_days = 30

    dlg = SettingsDialog(parent=None, vm=vm, store=store)
    qtbot.addWidget(dlg)

    # The shortcut read-only field must display the stored combo
    assert dlg._shortcut_field.text() == "Ctrl+J"


# ===========================================================================
# 10. SettingsDialog — bare key during capture keeps prior value + shows msg
# ===========================================================================

def test_settings_dialog_rejects_bare_key_capture(qtbot, tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QPushButton
    from unittest.mock import MagicMock
    from worktree_manager.setup_settings_vm import SettingsViewModel
    from worktree_manager.ui.settings_panel import SettingsDialog

    store = _make_store(tmp_path)
    store.set_spotlight_shortcut("Ctrl+K")

    vm = MagicMock(spec=SettingsViewModel)
    vm.worktree_storage = "/x"
    vm.stale_days = 30

    dlg = SettingsDialog(parent=None, vm=vm, store=store)
    qtbot.addWidget(dlg)

    # Click Record to enter capture mode
    record_btn = next(b for b in dlg.findChildren(QPushButton) if b.text() == "Record")
    qtbot.mouseClick(record_btn, Qt.LeftButton)

    # Simulate pressing bare 'A' (no modifiers)
    press = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier)
    from PySide6.QtWidgets import QApplication
    QApplication.sendEvent(dlg, press)

    # Prior value must be unchanged
    assert dlg._shortcut_field.text() == "Ctrl+K"
    # Status label must mention "modifier"
    assert "modifier" in dlg._shortcut_status.text().lower()


# ===========================================================================
# 11. SettingsDialog — Save persists combo and calls apply_spotlight_shortcut
# ===========================================================================

def test_saving_new_shortcut_persists_and_calls_apply(qtbot, tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QPushButton
    from unittest.mock import MagicMock, patch
    from worktree_manager.setup_settings_vm import SettingsViewModel
    from worktree_manager.ui.settings_panel import SettingsDialog

    store = _make_store(tmp_path)
    store.set_spotlight_shortcut("Ctrl+K")

    vm = MagicMock(spec=SettingsViewModel)
    vm.worktree_storage = "/x"
    vm.stale_days = 30

    # Fake parent with apply_spotlight_shortcut
    parent = MagicMock()
    parent.apply_spotlight_shortcut = MagicMock(return_value=True)

    dlg = SettingsDialog(parent=parent, vm=vm, store=store)
    qtbot.addWidget(dlg)

    # Directly set the field to simulate a recorded combo
    dlg._shortcut_field.setText("Ctrl+J")

    save_btn = next(b for b in dlg.findChildren(QPushButton) if b.text() == "Save")
    qtbot.mouseClick(save_btn, Qt.LeftButton)

    # Combo must be persisted
    assert store.get_spotlight_shortcut() == "Ctrl+J"
    # apply must have been called on the parent
    parent.apply_spotlight_shortcut.assert_called_once_with("Ctrl+J")


# ===========================================================================
# 12. App.apply_spotlight_shortcut — rebinds QShortcut
# ===========================================================================

def test_apply_spotlight_shortcut_rebinds_qshortcut(qtbot, tmp_path, monkeypatch):
    from PySide6.QtGui import QShortcut
    # GlobalHotkey.register hits Carbon which needs a real Cocoa event loop;
    # stub it out so the test validates only the QShortcut rebind.
    monkeypatch.setattr(
        "worktree_manager.global_hotkey.GlobalHotkey.register",
        lambda self, kc, mm: True,
    )
    app = _seed_app(tmp_path, monkeypatch)
    qtbot.addWidget(app)

    app.apply_spotlight_shortcut("Ctrl+J")

    shortcuts = app.findChildren(QShortcut)
    keys = [s.key().toString() for s in shortcuts]
    assert "Ctrl+J" in keys
