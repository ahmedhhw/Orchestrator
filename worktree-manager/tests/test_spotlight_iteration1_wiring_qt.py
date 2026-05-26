from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit

from worktree_manager.cli import App
from worktree_manager.config_store import ConfigStore
from worktree_manager.models import RepoConfig, WorkspaceProject


def _seed(tmp_path, projects=(), repos=()):
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
    return cfg


def _patch(monkeypatch, cfg):
    monkeypatch.setattr(
        "worktree_manager.cli.ConfigStore",
        lambda: ConfigStore(path=cfg),
    )


def test_iteration1_root_keywords_include_full_catalogue(qtbot, tmp_path, monkeypatch):
    _patch(monkeypatch, _seed(tmp_path, projects=["alpha"]))
    app = App()
    qtbot.addWidget(app)
    roots = app.spotlight_registry().root_keywords()
    for kw in ("project", "edit", "command", "repo", "switch", "cleanup", "settings"):
        assert kw in roots


def test_edit_project_chain_is_registered(qtbot, tmp_path, monkeypatch):
    _patch(monkeypatch, _seed(tmp_path, projects=["alpha"]))
    app = App()
    qtbot.addWidget(app)
    spec = app.spotlight_registry().find_by_keywords(["edit", "project"])
    assert spec is not None
    assert spec.name == "edit_project"


def test_settings_chain_runs_show_settings(qtbot, tmp_path, monkeypatch):
    cfg = _seed(tmp_path, repos=["/tmp/fakerepoA"])
    _patch(monkeypatch, cfg)
    called = []
    monkeypatch.setattr(
        "worktree_manager.cli.App._show_settings",
        lambda self, repo_path: called.append(repo_path),
    )
    app = App()
    qtbot.addWidget(app)
    app.show()
    overlay = app.open_spotlight_for_test()
    edit = overlay.findChild(QLineEdit)
    edit.setText("settings")
    qtbot.keyClick(edit, Qt.Key_Return)
    assert called == ["/tmp/fakerepoA"]


def test_repo_chain_runs_load_repo(qtbot, tmp_path, monkeypatch):
    cfg = _seed(tmp_path, repos=["/tmp/fakerepoA", "/tmp/fakerepoB"])
    _patch(monkeypatch, cfg)
    called = []
    monkeypatch.setattr(
        "worktree_manager.cli.App._load_repo",
        lambda self, repo_path: called.append(repo_path),
    )
    app = App()
    qtbot.addWidget(app)
    app.show()
    overlay = app.open_spotlight_for_test()
    edit = overlay.findChild(QLineEdit)
    edit.setText("repo fakerepoB")
    qtbot.keyClick(edit, Qt.Key_Return)
    assert called == ["/tmp/fakerepoB"]


def test_cleanup_chain_runs_show_cleanup_for_named_repo(qtbot, tmp_path, monkeypatch):
    cfg = _seed(tmp_path, repos=["/tmp/fakerepoA"])
    _patch(monkeypatch, cfg)
    called = []
    monkeypatch.setattr(
        "worktree_manager.cli.App._show_cleanup",
        lambda self, vm: called.append(vm._repo_path),
    )
    app = App()
    qtbot.addWidget(app)
    app.show()
    overlay = app.open_spotlight_for_test()
    edit = overlay.findChild(QLineEdit)
    edit.setText("cleanup fakerepoA")
    qtbot.keyClick(edit, Qt.Key_Return)
    assert called == ["/tmp/fakerepoA"]


def test_edit_project_chain_opens_dialog_with_correct_project(qtbot, tmp_path, monkeypatch):
    cfg = _seed(tmp_path, projects=["alpha"])
    _patch(monkeypatch, cfg)
    opened = []
    monkeypatch.setattr(
        "worktree_manager.ui.project_operations_dialog.ProjectOperationsDialog.exec",
        lambda self: opened.append(
            self._existing_project.name if self._existing_project else None
        ),
    )
    app = App()
    qtbot.addWidget(app)
    app.show()
    overlay = app.open_spotlight_for_test()
    edit = overlay.findChild(QLineEdit)
    edit.setText("edit project alpha")
    qtbot.keyClick(edit, Qt.Key_Return)
    assert opened == ["alpha"]
