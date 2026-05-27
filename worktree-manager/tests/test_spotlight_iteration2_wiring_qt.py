from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit

from worktree_manager.cli import App
from worktree_manager.config_store import ConfigStore
from worktree_manager.models import RepoConfig, SavedCommand, WorkspaceProject


def _seed(tmp_path, projects=(), repos=(), commands=()):
    cfg = tmp_path / "config.json"
    store = ConfigStore(path=cfg)
    for name in projects:
        store.save_project(WorkspaceProject(name=name, entries=[]))
    for repo_path in repos:
        store.save_repo(RepoConfig(
            repo_path=repo_path, worktree_storage="adjacent",
            stale_days=30, last_editor="code", last_editor_mode="window",
            last_opened="",
        ))
    for repo_path, cmd_name in commands:
        store.save_command(repo_path, SavedCommand(name=cmd_name, command="echo hi"))
    return cfg


def _patch(monkeypatch, cfg):
    monkeypatch.setattr(
        "worktree_manager.cli.ConfigStore",
        lambda: ConfigStore(path=cfg),
    )


def _open(app, qtbot, text):
    overlay = app.open_spotlight_for_test()
    edit = overlay.findChild(QLineEdit)
    edit.setText(text)
    qtbot.keyClick(edit, Qt.Key_Return)
    return overlay


# ── root keywords ────────────────────────────────────────────────────────────

def test_iteration2_root_keywords_include_new(qtbot, tmp_path, monkeypatch):
    _patch(monkeypatch, _seed(tmp_path))
    app = App()
    qtbot.addWidget(app)
    assert "new" in app.spotlight_registry().root_keywords()


# ── new worktree <repo> ───────────────────────────────────────────────────────

def test_new_worktree_chain_is_registered(qtbot, tmp_path, monkeypatch):
    _patch(monkeypatch, _seed(tmp_path))
    app = App()
    qtbot.addWidget(app)
    spec = app.spotlight_registry().find_by_keywords(["new", "worktree"])
    assert spec is not None
    assert spec.name == "new_worktree"


def test_new_worktree_calls_show_new_worktree_for_repo(qtbot, tmp_path, monkeypatch):
    cfg = _seed(tmp_path, repos=["/tmp/fakerepoA"])
    _patch(monkeypatch, cfg)
    called = []
    monkeypatch.setattr(
        "worktree_manager.cli.App._show_new_worktree",
        lambda self, vm: called.append(vm._repo_path),
    )
    app = App()
    qtbot.addWidget(app)
    app.show()
    _open(app, qtbot, "new worktree fakerepoA")
    assert called == ["/tmp/fakerepoA"]


# ── new project ───────────────────────────────────────────────────────────────

def test_new_project_chain_is_registered(qtbot, tmp_path, monkeypatch):
    _patch(monkeypatch, _seed(tmp_path))
    app = App()
    qtbot.addWidget(app)
    spec = app.spotlight_registry().find_by_keywords(["new", "project"])
    assert spec is not None
    assert spec.name == "new_project"


def test_new_project_opens_create_dialog(qtbot, tmp_path, monkeypatch):
    _patch(monkeypatch, _seed(tmp_path))
    opened = []
    monkeypatch.setattr(
        "worktree_manager.ui.project_operations_dialog.ProjectOperationsDialog.exec",
        lambda self: opened.append(
            self._existing_project.name if self._existing_project else "create"
        ),
    )
    app = App()
    qtbot.addWidget(app)
    app.show()
    _open(app, qtbot, "new project")
    assert opened == ["create"]


# ── new command <repo> ────────────────────────────────────────────────────────

def test_new_command_chain_is_registered(qtbot, tmp_path, monkeypatch):
    _patch(monkeypatch, _seed(tmp_path))
    app = App()
    qtbot.addWidget(app)
    spec = app.spotlight_registry().find_by_keywords(["new", "command"])
    assert spec is not None
    assert spec.name == "new_command"


def test_new_command_opens_add_command_dialog_for_repo(qtbot, tmp_path, monkeypatch):
    cfg = _seed(tmp_path, repos=["/tmp/fakerepoA"])
    _patch(monkeypatch, cfg)
    opened = []
    monkeypatch.setattr(
        "worktree_manager.ui.add_command_dialog.AddCommandDialog.exec",
        lambda self: opened.append(self._initial_repo),  # set in __init__
    )
    app = App()
    qtbot.addWidget(app)
    app.show()
    _open(app, qtbot, "new command fakerepoA")
    assert opened == ["/tmp/fakerepoA"]


# ── edit command <repo> ───────────────────────────────────────────────────────

def test_edit_command_chain_is_registered(qtbot, tmp_path, monkeypatch):
    _patch(monkeypatch, _seed(tmp_path))
    app = App()
    qtbot.addWidget(app)
    spec = app.spotlight_registry().find_by_keywords(["edit", "command"])
    assert spec is not None
    assert spec.name == "edit_command"


def test_edit_command_opens_launch_dialog_for_repo(qtbot, tmp_path, monkeypatch):
    from unittest.mock import MagicMock, patch
    cfg = _seed(tmp_path, repos=["/tmp/fakerepoA"])
    _patch(monkeypatch, cfg)
    opened = []

    class _FakeLaunchDialog:
        def __init__(self, parent, vm, locked_repo_path=None, **kw):
            opened.append(locked_repo_path)
        def exec(self):
            pass

    monkeypatch.setattr("worktree_manager.ui.launch_dialog.LaunchDialog", _FakeLaunchDialog)
    app = App()
    qtbot.addWidget(app)
    app.show()
    _open(app, qtbot, "edit command fakerepoA")
    assert opened == ["/tmp/fakerepoA"]


# ── new repo ─────────────────────────────────────────────────────────────────

def test_new_repo_chain_is_registered(qtbot, tmp_path, monkeypatch):
    _patch(monkeypatch, _seed(tmp_path))
    app = App()
    qtbot.addWidget(app)
    spec = app.spotlight_registry().find_by_keywords(["new", "repo"])
    assert spec is not None
    assert spec.name == "new_repo"


def test_new_repo_calls_pick_and_add_repo(qtbot, tmp_path, monkeypatch):
    _patch(monkeypatch, _seed(tmp_path))
    called = []
    monkeypatch.setattr(
        "worktree_manager.cli.App._pick_and_add_repo",
        lambda self: called.append(True),
    )
    app = App()
    qtbot.addWidget(app)
    app.show()
    _open(app, qtbot, "new repo")
    assert called == [True]
