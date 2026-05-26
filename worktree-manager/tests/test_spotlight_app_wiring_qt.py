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
    edit.setText("project alpha")
    qtbot.keyClick(edit, Qt.Key_Return)
    assert len(calls) == 1
    assert calls[0][0] == "alpha"
