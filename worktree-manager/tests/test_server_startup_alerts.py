"""Tests for server startup pattern detection and alerts."""
import sys
import time
from unittest.mock import MagicMock, patch

import pytest

from worktree_manager.command_center_vm import CommandCenterViewModel
from worktree_manager.command_runner import RunHandle, RunStatus
from worktree_manager.models import SavedCommand


# --- SavedCommand model ---

def test_saved_command_has_startup_pattern_default_none():
    cmd = SavedCommand(name="srv", command="npm run dev")
    assert cmd.startup_pattern is None


def test_saved_command_stores_startup_pattern():
    cmd = SavedCommand(name="srv", command="npm run dev", startup_pattern="ready on")
    assert cmd.startup_pattern == "ready on"


# --- ConfigStore round-trip ---

@pytest.fixture
def store(tmp_path):
    from worktree_manager.config_store import ConfigStore
    from worktree_manager.models import RepoConfig
    s = ConfigStore(tmp_path / "config.json")
    s.save_repo(RepoConfig(
        repo_path="/repos/proj",
        worktree_storage="/repos/proj-wt",
        stale_days=30,
        last_editor="cursor",
        last_editor_mode="reuse",
        last_opened="2026-05-20T10:00:00",
    ))
    return s


def test_config_store_saves_startup_pattern(store):
    store.save_command("/repos/proj", SavedCommand(name="srv", command="npm run dev", startup_pattern="ready on"))
    cmds = store.get_commands("/repos/proj")
    assert cmds[0].startup_pattern == "ready on"


def test_config_store_saves_none_startup_pattern(store):
    store.save_command("/repos/proj", SavedCommand(name="srv", command="npm run dev"))
    cmds = store.get_commands("/repos/proj")
    assert cmds[0].startup_pattern is None


def test_config_store_startup_pattern_missing_key_reads_none(store):
    # Simulate old config written without startup_pattern key
    import json
    cfg_path = store._path
    data = json.loads(cfg_path.read_text())
    data["repos"]["/repos/proj"]["commands"] = [{"name": "srv", "command": "npm run dev"}]
    cfg_path.write_text(json.dumps(data))
    cmds = store.get_commands("/repos/proj")
    assert cmds[0].startup_pattern is None


# --- CommandCenterViewModel startup detection ---

@pytest.fixture
def vm(store):
    return CommandCenterViewModel(config_store=store)


def test_vm_fires_on_startup_detected_when_pattern_matches(vm, tmp_path):
    detected = []
    vm.on_startup_detected = lambda run_id, handle: detected.append((run_id, handle))

    run_id = vm.launch(
        repo_path="/repos/proj",
        repo_name="proj",
        cmd_name="srv",
        command_str=f"{sys.executable} -c \"import time; print('Server ready on :3000'); time.sleep(0.1)\"",
        worktree_path=str(tmp_path),
        startup_pattern="Server ready",
    )
    time.sleep(0.5)
    assert len(detected) == 1
    assert detected[0][0] == run_id


def test_vm_startup_fires_only_once_per_run(vm, tmp_path):
    detected = []
    vm.on_startup_detected = lambda run_id, handle: detected.append(run_id)

    vm.launch(
        repo_path="/repos/proj",
        repo_name="proj",
        cmd_name="srv",
        command_str=f"{sys.executable} -c \"print('ready'); print('ready again'); import time; time.sleep(0.1)\"",
        worktree_path=str(tmp_path),
        startup_pattern="ready",
    )
    time.sleep(0.5)
    assert len(detected) == 1


def test_vm_no_startup_detection_without_pattern(vm, tmp_path):
    detected = []
    vm.on_startup_detected = lambda run_id, handle: detected.append(run_id)

    vm.launch(
        repo_path="/repos/proj",
        repo_name="proj",
        cmd_name="srv",
        command_str=f"{sys.executable} -c \"print('Server ready'); import time; time.sleep(0.1)\"",
        worktree_path=str(tmp_path),
        startup_pattern=None,
    )
    time.sleep(0.5)
    assert detected == []


def test_vm_startup_fired_reset_on_restart(vm, tmp_path):
    detected = []
    vm.on_startup_detected = lambda run_id, handle: detected.append(run_id)

    run_id = vm.launch(
        repo_path="/repos/proj",
        repo_name="proj",
        cmd_name="srv",
        command_str=f"{sys.executable} -c \"import sys; print('ready'); sys.stdout.flush(); import time; time.sleep(1)\"",
        worktree_path=str(tmp_path),
        startup_pattern="ready",
    )
    time.sleep(0.5)
    assert len(detected) == 1

    vm.restart(run_id)
    time.sleep(0.5)
    assert len(detected) == 2


def test_vm_startup_fired_cleared_on_remove(vm, tmp_path):
    run_id = vm.launch(
        repo_path="/repos/proj",
        repo_name="proj",
        cmd_name="srv",
        command_str=f"{sys.executable} -c \"import sys; print('ready'); sys.stdout.flush(); import time; time.sleep(1)\"",
        worktree_path=str(tmp_path),
        startup_pattern="ready",
    )
    time.sleep(0.3)
    vm.remove_run(run_id)
    assert run_id not in vm._startup_fired


# --- MainWindow wiring ---

def _make_app(qtbot, monkeypatch):
    from worktree_manager.cli import App
    from worktree_manager.models import RepoConfig

    cfg = RepoConfig(
        repo_path="/repos/proj", worktree_storage="/repos/proj-wt",
        stale_days=30, last_editor="cursor", last_editor_mode="reuse",
        last_opened="2026-05-19T10:00:00",
    )
    store = MagicMock()
    store.all_repos.return_value = {"/repos/proj": cfg}
    store.get_repo.return_value = cfg
    store.get_ui_pref.side_effect = lambda key, default=None: default
    store.all_projects.return_value = []
    monkeypatch.setattr("worktree_manager.cli.ConfigStore", lambda *a, **kw: store)
    monkeypatch.setattr("worktree_manager.cli.GitService", lambda *a, **kw: MagicMock())

    with patch("worktree_manager.main_window_vm.MainWindowViewModel") as MockVM:
        MockVM.return_value.load_worktrees.return_value = []
        MockVM.return_value.list_branches_with_checkout_status.return_value = []
        app = App(repo_path="/repos/proj")
        qtbot.addWidget(app)
    return app


def _handle(cmd_name="srv"):
    h = RunHandle(
        run_id="run-1", cmd_name=cmd_name,
        repo_path="/repos/proj", repo_name="proj",
        worktree_path="/repos/proj", command="npm run dev",
    )
    h.status = RunStatus.RUNNING
    return h


def test_startup_notification_fires_when_command_center_not_visible(qtbot, monkeypatch):
    from worktree_manager.ui.command_center_panel import CommandCenterPanel
    app = _make_app(qtbot, monkeypatch)
    assert not isinstance(app._current_panel, CommandCenterPanel)

    shown = []
    with patch.object(app, "_show_notification", side_effect=lambda t, b: shown.append((t, b))):
        app._on_startup_detected("run-1", _handle(cmd_name="srv"))

    assert len(shown) == 1
    assert "srv" in shown[0][1]
    assert "🚀" in shown[0][1]


def test_startup_notification_fires_even_when_command_center_visible(qtbot, monkeypatch):
    from worktree_manager.ui.command_center_panel import CommandCenterPanel
    app = _make_app(qtbot, monkeypatch)
    app._show_command_center()
    assert isinstance(app._current_panel, CommandCenterPanel)

    shown = []
    with patch.object(app, "_show_notification", side_effect=lambda t, b: shown.append((t, b))):
        app._on_startup_detected("run-1", _handle(cmd_name="srv"))

    assert len(shown) == 1
    assert "🚀" in shown[0][1]


def test_startup_switches_to_command_center_when_not_visible(qtbot, monkeypatch):
    from worktree_manager.ui.command_center_panel import CommandCenterPanel
    app = _make_app(qtbot, monkeypatch)
    assert not isinstance(app._current_panel, CommandCenterPanel)

    with patch.object(app, "_show_notification"):
        app._on_startup_detected("run-1", _handle())

    assert isinstance(app._current_panel, CommandCenterPanel)


def test_vm_on_startup_detected_wired_after_ensure_vm(qtbot, monkeypatch):
    app = _make_app(qtbot, monkeypatch)
    app._ensure_command_center_vm()
    assert app._command_center_vm.on_startup_detected is not None


# --- save_command syncs live run meta ---

def test_save_command_updates_startup_pattern_for_live_run(vm, tmp_path):
    detected = []
    vm.on_startup_detected = lambda run_id, handle: detected.append(run_id)

    # Launch with no pattern
    run_id = vm.launch(
        repo_path="/repos/proj", repo_name="proj", cmd_name="srv",
        command_str=f"{sys.executable} -c \"import sys,time; [print('ping',flush=True) or time.sleep(0.2) for _ in range(20)]\"",
        worktree_path=str(tmp_path),
        startup_pattern=None,
    )
    time.sleep(0.3)
    assert detected == []

    # Now save updated command with a pattern — live run meta should update
    vm.save_command("/repos/proj", "srv", "npm run dev", startup_pattern="ping")
    time.sleep(0.4)
    assert len(detected) == 1


def test_save_command_updates_command_str_for_restart(vm, tmp_path):
    run_id = vm.launch(
        repo_path="/repos/proj", repo_name="proj", cmd_name="srv",
        command_str=f"{sys.executable} -c \"import time; time.sleep(2)\"",
        worktree_path=str(tmp_path),
    )
    # Update the command string via save_command
    vm.save_command("/repos/proj", "srv", f"{sys.executable} -c \"print('new-cmd')\"")
    # Meta should reflect the new command_str
    assert vm._run_meta[run_id]["command_str"] == f"{sys.executable} -c \"print('new-cmd')\""


def test_save_command_resets_startup_fired_for_live_run(vm, tmp_path):
    detected = []
    vm.on_startup_detected = lambda run_id, handle: detected.append(run_id)

    run_id = vm.launch(
        repo_path="/repos/proj", repo_name="proj", cmd_name="srv",
        command_str=f"{sys.executable} -c \"import sys,time; print('ready',flush=True); time.sleep(2)\"",
        worktree_path=str(tmp_path),
        startup_pattern="ready",
    )
    time.sleep(0.3)
    assert len(detected) == 1
    assert run_id in vm._startup_fired

    # Re-saving the command should reset _startup_fired so the next match fires again
    vm.save_command("/repos/proj", "srv", "npm run dev", startup_pattern="ready")
    assert run_id not in vm._startup_fired
