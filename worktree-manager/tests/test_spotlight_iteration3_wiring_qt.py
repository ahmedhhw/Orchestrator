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


# ── root keywords ─────────────────────────────────────────────────────────────

def test_iteration3_root_keywords_include_delete(qtbot, tmp_path, monkeypatch):
    _patch(monkeypatch, _seed(tmp_path))
    app = App()
    qtbot.addWidget(app)
    assert "delete" in app.spotlight_registry().root_keywords()


# ── SpotlightConfirmDialog ────────────────────────────────────────────────────

def test_spotlight_confirm_dialog_accept(qtbot):
    from worktree_manager.ui.spotlight_confirm_dialog import SpotlightConfirmDialog
    dlg = SpotlightConfirmDialog(parent=None, title="Confirm?", message="Really?")
    qtbot.addWidget(dlg)
    dlg.show()
    assert dlg.windowTitle() == "Confirm?"
    dlg._confirm_btn.click()
    assert dlg.result() == SpotlightConfirmDialog.Accepted


def test_spotlight_confirm_dialog_cancel(qtbot):
    from worktree_manager.ui.spotlight_confirm_dialog import SpotlightConfirmDialog
    dlg = SpotlightConfirmDialog(parent=None, title="Confirm?", message="Really?")
    qtbot.addWidget(dlg)
    dlg.show()
    dlg._cancel_btn.click()
    assert dlg.result() == SpotlightConfirmDialog.Rejected


def test_spotlight_confirm_dialog_also_delete_branch_hidden_by_default(qtbot):
    from worktree_manager.ui.spotlight_confirm_dialog import SpotlightConfirmDialog
    dlg = SpotlightConfirmDialog(parent=None, title="T", message="M")
    qtbot.addWidget(dlg)
    assert dlg._also_branch_cb is None


def test_spotlight_confirm_dialog_also_delete_branch_shown_when_requested(qtbot):
    from worktree_manager.ui.spotlight_confirm_dialog import SpotlightConfirmDialog
    dlg = SpotlightConfirmDialog(
        parent=None, title="T", message="M", show_also_branch=True,
    )
    qtbot.addWidget(dlg)
    assert dlg._also_branch_cb is not None
    assert dlg.also_delete_branch() is True  # default checked when not protected


def test_spotlight_confirm_dialog_also_branch_disabled_when_protected(qtbot):
    from worktree_manager.ui.spotlight_confirm_dialog import SpotlightConfirmDialog
    dlg = SpotlightConfirmDialog(
        parent=None, title="T", message="M",
        show_also_branch=True, branch_protected=True,
    )
    qtbot.addWidget(dlg)
    assert not dlg._also_branch_cb.isEnabled()
    assert dlg.also_delete_branch() is False


# ── delete worktree <repo> <worktree> ─────────────────────────────────────────

def test_delete_worktree_chain_is_registered(qtbot, tmp_path, monkeypatch):
    _patch(monkeypatch, _seed(tmp_path))
    app = App()
    qtbot.addWidget(app)
    spec = app.spotlight_registry().find_by_keywords(["delete", "worktree"])
    assert spec is not None
    assert spec.name == "delete_worktree"


def test_delete_worktree_shows_confirm_dialog(qtbot, tmp_path, monkeypatch):
    cfg = _seed(tmp_path, repos=["/tmp/fakerepoA"])
    _patch(monkeypatch, cfg)
    shown = []
    monkeypatch.setattr(
        "worktree_manager.ui.spotlight_confirm_dialog.SpotlightConfirmDialog.exec",
        lambda self: shown.append(self.windowTitle()) or SpotlightConfirmDialog_Rejected,
    )
    monkeypatch.setattr(
        "worktree_manager.cli.GitService.list_worktrees",
        lambda self, repo_path: _fake_worktrees(),
    )
    app = App()
    qtbot.addWidget(app)
    app.show()
    _open(app, qtbot, "delete worktree fakerepoA main-wt")
    assert shown != []
    assert "delete" in shown[0].lower() or "worktree" in shown[0].lower()


def test_delete_worktree_cancelled_does_not_delete(qtbot, tmp_path, monkeypatch):
    from worktree_manager.ui.spotlight_confirm_dialog import SpotlightConfirmDialog
    cfg = _seed(tmp_path, repos=["/tmp/fakerepoA"])
    _patch(monkeypatch, cfg)
    deleted = []
    monkeypatch.setattr(
        "worktree_manager.ui.spotlight_confirm_dialog.SpotlightConfirmDialog.exec",
        lambda self: SpotlightConfirmDialog.Rejected,
    )
    monkeypatch.setattr(
        "worktree_manager.cli.GitService.list_worktrees",
        lambda self, repo_path: _fake_worktrees(),
    )
    monkeypatch.setattr(
        "worktree_manager.main_window_vm.MainWindowViewModel.delete_worktree",
        lambda self, **kw: deleted.append(kw),
    )
    app = App()
    qtbot.addWidget(app)
    app.show()
    _open(app, qtbot, "delete worktree fakerepoA main-wt")
    assert deleted == []


def test_delete_worktree_confirmed_calls_delete(qtbot, tmp_path, monkeypatch):
    from worktree_manager.ui.spotlight_confirm_dialog import SpotlightConfirmDialog
    cfg = _seed(tmp_path, repos=["/tmp/fakerepoA"])
    _patch(monkeypatch, cfg)
    deleted = []
    monkeypatch.setattr(
        "worktree_manager.ui.spotlight_confirm_dialog.SpotlightConfirmDialog.exec",
        lambda self: SpotlightConfirmDialog.Accepted,
    )
    monkeypatch.setattr(
        "worktree_manager.cli.GitService.list_worktrees",
        lambda self, repo_path: _fake_worktrees(),
    )
    monkeypatch.setattr(
        "worktree_manager.main_window_vm.MainWindowViewModel.delete_worktree",
        lambda self, path, branch, also_delete_branch: deleted.append(path),
    )
    app = App()
    qtbot.addWidget(app)
    app.show()
    _open(app, qtbot, "delete worktree fakerepoA main-wt")
    assert deleted == ["/tmp/fakerepoA/main-wt"]


# ── delete project <name> ─────────────────────────────────────────────────────

def test_delete_project_chain_is_registered(qtbot, tmp_path, monkeypatch):
    _patch(monkeypatch, _seed(tmp_path))
    app = App()
    qtbot.addWidget(app)
    spec = app.spotlight_registry().find_by_keywords(["delete", "project"])
    assert spec is not None
    assert spec.name == "delete_project"


def test_delete_project_confirmed_calls_delete(qtbot, tmp_path, monkeypatch):
    from worktree_manager.ui.spotlight_confirm_dialog import SpotlightConfirmDialog
    cfg = _seed(tmp_path, projects=["alpha"])
    _patch(monkeypatch, cfg)
    deleted = []
    monkeypatch.setattr(
        "worktree_manager.ui.spotlight_confirm_dialog.SpotlightConfirmDialog.exec",
        lambda self: SpotlightConfirmDialog.Accepted,
    )
    monkeypatch.setattr(
        "worktree_manager.workspace_projects_vm.WorkspaceProjectsViewModel.delete_project",
        lambda self, name: deleted.append(name),
    )
    app = App()
    qtbot.addWidget(app)
    app.show()
    _open(app, qtbot, "delete project alpha")
    assert deleted == ["alpha"]


def test_delete_project_cancelled_does_not_delete(qtbot, tmp_path, monkeypatch):
    from worktree_manager.ui.spotlight_confirm_dialog import SpotlightConfirmDialog
    cfg = _seed(tmp_path, projects=["alpha"])
    _patch(monkeypatch, cfg)
    deleted = []
    monkeypatch.setattr(
        "worktree_manager.ui.spotlight_confirm_dialog.SpotlightConfirmDialog.exec",
        lambda self: SpotlightConfirmDialog.Rejected,
    )
    monkeypatch.setattr(
        "worktree_manager.workspace_projects_vm.WorkspaceProjectsViewModel.delete_project",
        lambda self, name: deleted.append(name),
    )
    app = App()
    qtbot.addWidget(app)
    app.show()
    _open(app, qtbot, "delete project alpha")
    assert deleted == []


# ── delete command <repo> <cmd> ───────────────────────────────────────────────

def test_delete_command_chain_is_registered(qtbot, tmp_path, monkeypatch):
    _patch(monkeypatch, _seed(tmp_path))
    app = App()
    qtbot.addWidget(app)
    spec = app.spotlight_registry().find_by_keywords(["delete", "command"])
    assert spec is not None
    assert spec.name == "delete_command"


def test_delete_command_confirmed_calls_delete(qtbot, tmp_path, monkeypatch):
    from worktree_manager.ui.spotlight_confirm_dialog import SpotlightConfirmDialog
    cfg = _seed(tmp_path, repos=["/tmp/fakerepoA"],
                commands=[("/tmp/fakerepoA", "runserver")])
    _patch(monkeypatch, cfg)
    deleted = []
    monkeypatch.setattr(
        "worktree_manager.ui.spotlight_confirm_dialog.SpotlightConfirmDialog.exec",
        lambda self: SpotlightConfirmDialog.Accepted,
    )
    monkeypatch.setattr(
        "worktree_manager.config_store.ConfigStore.delete_command",
        lambda self, repo_path, name: deleted.append((repo_path, name)),
    )
    app = App()
    qtbot.addWidget(app)
    app.show()
    _open(app, qtbot, "delete command fakerepoA runserver")
    assert deleted == [("/tmp/fakerepoA", "runserver")]


def test_delete_command_cancelled_does_not_delete(qtbot, tmp_path, monkeypatch):
    from worktree_manager.ui.spotlight_confirm_dialog import SpotlightConfirmDialog
    cfg = _seed(tmp_path, repos=["/tmp/fakerepoA"],
                commands=[("/tmp/fakerepoA", "runserver")])
    _patch(monkeypatch, cfg)
    deleted = []
    monkeypatch.setattr(
        "worktree_manager.ui.spotlight_confirm_dialog.SpotlightConfirmDialog.exec",
        lambda self: SpotlightConfirmDialog.Rejected,
    )
    monkeypatch.setattr(
        "worktree_manager.config_store.ConfigStore.delete_command",
        lambda self, repo_path, name: deleted.append((repo_path, name)),
    )
    app = App()
    qtbot.addWidget(app)
    app.show()
    _open(app, qtbot, "delete command fakerepoA runserver")
    assert deleted == []


# ── delete repo <name> ────────────────────────────────────────────────────────

def test_delete_repo_chain_is_registered(qtbot, tmp_path, monkeypatch):
    _patch(monkeypatch, _seed(tmp_path))
    app = App()
    qtbot.addWidget(app)
    spec = app.spotlight_registry().find_by_keywords(["delete", "repo"])
    assert spec is not None
    assert spec.name == "delete_repo"


def test_delete_repo_confirmed_calls_confirm_delete_repo(qtbot, tmp_path, monkeypatch):
    cfg = _seed(tmp_path, repos=["/tmp/fakerepoA"])
    _patch(monkeypatch, cfg)
    called = []
    monkeypatch.setattr(
        "worktree_manager.cli.App._confirm_delete_repo",
        lambda self, path, is_active: called.append(path),
    )
    app = App()
    qtbot.addWidget(app)
    app.show()
    _open(app, qtbot, "delete repo fakerepoA")
    assert called == ["/tmp/fakerepoA"]


# ── helpers ───────────────────────────────────────────────────────────────────

def _fake_worktrees():
    from worktree_manager.models import WorktreeModel
    return [WorktreeModel(
        path="/tmp/fakerepoA/main-wt", branch="main",
        is_main=True, last_commit_ts=0, is_merged=False, is_stale=False,
    )]


# sentinel so lambda can return it
SpotlightConfirmDialog_Rejected = 0
