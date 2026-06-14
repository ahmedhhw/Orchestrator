from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit, QListWidget

from worktree_manager.cli import App
from worktree_manager.config_store import ConfigStore
from worktree_manager.models import WorkspaceProject
from worktree_manager.ui.spotlight_overlay import SpotlightOverlay


def _seed_config(tmp_path, projects):
    cfg_path = tmp_path / "config.json"
    store = ConfigStore(path=cfg_path)
    for name in projects:
        store.save_project(WorkspaceProject(name=name, entries=[]))
    return cfg_path


def _patch_store(monkeypatch, cfg_path):
    monkeypatch.setattr(
        "worktree_manager.cli.ConfigStore",
        lambda: ConfigStore(path=cfg_path),
    )


def test_app_registers_open_project_action(qtbot, tmp_path, monkeypatch):
    cfg = _seed_config(tmp_path, ["alpha", "beta"])
    _patch_store(monkeypatch, cfg)
    app = App()
    qtbot.addWidget(app)
    assert "project" in app.spotlight_registry().root_keywords()


def test_cmd_k_shortcut_is_registered_on_app(qtbot, tmp_path, monkeypatch):
    from PySide6.QtGui import QShortcut
    cfg = _seed_config(tmp_path, ["alpha"])
    _patch_store(monkeypatch, cfg)
    app = App()
    qtbot.addWidget(app)
    shortcuts = app.findChildren(QShortcut)
    keys = [s.key().toString() for s in shortcuts]
    assert "Ctrl+K" in keys


def test_open_spotlight_shows_overlay(qtbot, tmp_path, monkeypatch):
    cfg = _seed_config(tmp_path, ["alpha"])
    _patch_store(monkeypatch, cfg)
    app = App()
    qtbot.addWidget(app)
    app.show()
    overlay = app.open_spotlight_for_test()
    assert overlay.isVisible()


def test_spotlight_lists_workspace_projects_from_config(qtbot, tmp_path, monkeypatch):
    cfg = _seed_config(tmp_path, ["alpha", "beta", "gamma"])
    _patch_store(monkeypatch, cfg)
    app = App()
    qtbot.addWidget(app)
    app.show()
    overlay = app.open_spotlight_for_test()
    edit = overlay.findChild(QLineEdit)
    edit.setText("project ")
    lw = overlay.findChild(QListWidget)
    items = sorted(lw.item(i).text() for i in range(lw.count()))
    assert items == ["alpha", "beta", "gamma"]


def test_enter_invokes_open_project_on_workspace_vm(qtbot, tmp_path, monkeypatch):
    cfg = _seed_config(tmp_path, ["alpha"])
    _patch_store(monkeypatch, cfg)
    calls = []
    monkeypatch.setattr(
        "worktree_manager.workspace_projects_vm.WorkspaceProjectsViewModel.open_project",
        lambda self, name, editor: calls.append((name, editor)),
    )
    app = App()
    qtbot.addWidget(app)
    app.show()
    overlay = app.open_spotlight_for_test()
    edit = overlay.findChild(QLineEdit)
    # Editor is now the 3rd token — must provide it for the command to be executable.
    edit.setText("project alpha cursor")
    qtbot.keyClick(edit, Qt.Key_Return)
    assert len(calls) == 1
    assert calls[0] == ("alpha", "cursor")


def test_project_with_vscode_editor_invokes_open_project_with_vscode(qtbot, tmp_path, monkeypatch):
    cfg = _seed_config(tmp_path, ["alpha"])
    _patch_store(monkeypatch, cfg)
    calls = []
    monkeypatch.setattr(
        "worktree_manager.workspace_projects_vm.WorkspaceProjectsViewModel.open_project",
        lambda self, name, editor: calls.append((name, editor)),
    )
    app = App()
    qtbot.addWidget(app)
    app.show()
    overlay = app.open_spotlight_for_test()
    edit = overlay.findChild(QLineEdit)
    edit.setText("project alpha vscode")
    qtbot.keyClick(edit, Qt.Key_Return)
    assert len(calls) == 1
    assert calls[0] == ("alpha", "vscode")


def test_project_name_only_is_not_executable(qtbot, tmp_path, monkeypatch):
    cfg = _seed_config(tmp_path, ["alpha"])
    _patch_store(monkeypatch, cfg)
    calls = []
    monkeypatch.setattr(
        "worktree_manager.workspace_projects_vm.WorkspaceProjectsViewModel.open_project",
        lambda self, name, editor: calls.append((name, editor)),
    )
    app = App()
    qtbot.addWidget(app)
    app.show()
    overlay = app.open_spotlight_for_test()
    edit = overlay.findChild(QLineEdit)
    # "project alpha " — name committed but no editor — must NOT execute.
    edit.setText("project alpha ")
    qtbot.keyClick(edit, Qt.Key_Return)
    assert calls == [], "open_project must not be called when editor token is missing"


def test_after_project_name_editor_slot_offers_cursor_and_vscode(qtbot, tmp_path, monkeypatch):
    cfg = _seed_config(tmp_path, ["alpha"])
    _patch_store(monkeypatch, cfg)
    app = App()
    qtbot.addWidget(app)
    app.show()
    overlay = app.open_spotlight_for_test()
    edit = overlay.findChild(QLineEdit)
    # Commit the name slot — trailing space triggers candidate list for editor slot.
    edit.setText("project alpha ")
    lw = overlay.findChild(QListWidget)
    items = sorted(lw.item(i).text() for i in range(lw.count()))
    assert items == ["cursor", "vscode"]


def test_set_default_editor_command_is_not_registered(qtbot, tmp_path, monkeypatch):
    cfg = _seed_config(tmp_path, ["alpha"])
    _patch_store(monkeypatch, cfg)
    app = App()
    qtbot.addWidget(app)
    registry = app.spotlight_registry()
    # "settings project editor" must not resolve to a runnable set_project_editor action.
    from worktree_manager.spotlight.action_parser import ActionParser
    parser = ActionParser(registry)
    result = parser.parse("settings project editor cursor")
    # The action (if any) must NOT be the removed set_project_editor.
    action_name = result.action.name if result.action is not None else None
    assert action_name != "set_project_editor"


def test_legacy_nickname_without_editor_opens_in_cursor(qtbot, tmp_path, monkeypatch):
    # A nickname saved before the editor token existed has args {"name": ...}
    # and no "editor" key. Running it must still open the project (defaulting to
    # cursor) rather than raising KeyError.
    cfg = _seed_config(tmp_path, ["alpha"])
    store = ConfigStore(path=cfg)
    store.set_ui_pref("nicknames", {
        "proji": {"action": "open_project", "args": {"name": "alpha"}},
    })
    _patch_store(monkeypatch, cfg)
    calls = []
    monkeypatch.setattr(
        "worktree_manager.workspace_projects_vm.WorkspaceProjectsViewModel.open_project",
        lambda self, name, editor: calls.append((name, editor)),
    )
    app = App()
    qtbot.addWidget(app)
    app.show()
    overlay = app.open_spotlight_for_test()
    edit = overlay.findChild(QLineEdit)
    edit.setText("proji")
    qtbot.keyClick(edit, Qt.Key_Return)
    assert calls == [("alpha", "cursor")]


def test_settings_alone_still_opens_settings_dialog(qtbot, tmp_path, monkeypatch):
    cfg = _seed_config(tmp_path, ["alpha"])
    _patch_store(monkeypatch, cfg)
    app = App()
    qtbot.addWidget(app)
    registry = app.spotlight_registry()
    from worktree_manager.spotlight.action_parser import ActionParser
    parser = ActionParser(registry)
    result = parser.parse("settings")
    assert result.action is not None
    assert result.action.name == "open_settings"
    assert result.executable is True
