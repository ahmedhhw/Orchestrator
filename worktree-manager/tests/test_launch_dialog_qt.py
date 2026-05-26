from unittest.mock import MagicMock

from PySide6.QtWidgets import QComboBox, QDialog, QPushButton

from worktree_manager.command_runner import RunHandle, RunStatus
from worktree_manager.models import SavedCommand, WorktreeModel
from worktree_manager.ui.launch_dialog import LaunchDialog


def _wt(branch="main", path="/r/proj"):
    import time
    return WorktreeModel(
        path=path, branch=branch, is_main=True,
        last_commit_ts=int(time.time()), is_merged=False, is_stale=False,
    )


def _vm(repos=None, last_used="/repos/proj", saved=None, worktrees=None,
        existing=None):
    vm = MagicMock()
    vm.all_repos.return_value = repos or {"/repos/proj": MagicMock()}
    vm.get_last_used_repo.return_value = last_used
    vm.saved_commands.return_value = (
        [SavedCommand(name="build", command="make"),
         SavedCommand(name="test", command="pytest")]
        if saved is None else saved
    )
    vm.list_worktrees.return_value = worktrees or [_wt()]
    vm.find_existing_run.return_value = existing
    return vm


def _dlg(qtbot, vm=None):
    d = LaunchDialog(parent=None, vm=vm or _vm())
    qtbot.addWidget(d)
    return d


def test_launch_dialog_is_qdialog(qtbot):
    assert isinstance(_dlg(qtbot), QDialog)


def test_launch_dialog_has_launch_and_cancel(qtbot):
    d = _dlg(qtbot)
    texts = [b.text() for b in d.findChildren(QPushButton)]
    assert "Launch" in texts
    assert "Cancel" in texts


def test_launch_dialog_defaults_repo_to_last_used(qtbot):
    vm = _vm(repos={"/repos/proj": MagicMock(), "/repos/api": MagicMock()},
             last_used="/repos/api")
    d = _dlg(qtbot, vm=vm)
    assert d._current_repo_path() == "/repos/api"


def test_launch_dialog_lists_commands_for_selected_repo(qtbot):
    d = _dlg(qtbot)
    assert d.command_choices() == ["build", "test"]


def test_launch_dialog_lists_worktrees_for_selected_repo(qtbot):
    d = _dlg(qtbot)
    assert any("main" in w for w in d.worktree_choices())


def test_launch_dialog_launch_with_no_selected_command_is_noop(qtbot):
    vm = _vm()
    d = _dlg(qtbot, vm=vm)
    d._selected_cmd = None
    d.trigger_launch()
    vm.launch.assert_not_called()


def test_launch_dialog_launch_calls_vm_with_correct_args(qtbot):
    vm = _vm()
    d = _dlg(qtbot, vm=vm)
    d.set_command("build")
    d.trigger_launch()
    vm.launch.assert_called_once()
    kwargs = vm.launch.call_args.kwargs
    assert kwargs["cmd_name"] == "build"
    assert kwargs["command_str"] == "make"
    assert kwargs["repo_path"] == "/repos/proj"
    assert kwargs["repo_name"] == "proj"
    vm.set_last_used_repo.assert_called_once_with("/repos/proj")


def test_launch_dialog_filter_narrows_command_list(qtbot):
    d = _dlg(qtbot)
    d._cmd_filter.setText("test")
    visible = [c.name for c in d._visible_cmds()]
    assert visible == ["test"]


def test_launch_dialog_existing_running_shows_conflict_no_restart(qtbot):
    existing = RunHandle(
        run_id="r1", cmd_name="build", repo_path="/repos/proj",
        repo_name="proj", worktree_path="/r/proj", command=["make"],
        status=RunStatus.RUNNING,
    )
    vm = _vm(existing=existing)
    d = _dlg(qtbot, vm=vm)
    d.set_command("build")
    d.trigger_launch()
    assert "already running" in d._conflict_label.text().lower()
    assert not d._restart_btn.isVisible()
    vm.launch.assert_not_called()


def test_launch_dialog_existing_stopped_shows_restart_button(qtbot):
    existing = RunHandle(
        run_id="r1", cmd_name="build", repo_path="/repos/proj",
        repo_name="proj", worktree_path="/r/proj", command=["make"],
        status=RunStatus.STOPPED,
    )
    vm = _vm(existing=existing)
    d = _dlg(qtbot, vm=vm)
    d.set_command("build")
    d.trigger_launch()
    assert d._restart_btn.isVisible()
    d._restart_btn.click()
    vm.restart.assert_called_once_with("r1")


def test_launch_dialog_cancel_closes_without_launching(qtbot):
    vm = _vm()
    d = _dlg(qtbot, vm=vm)
    cancel = next(b for b in d.findChildren(QPushButton) if b.text() == "Cancel")
    cancel.click()
    vm.launch.assert_not_called()


# ── Run Once ─────────────────────────────────────────────────────────────────

def test_run_once_field_is_present(qtbot):
    from PySide6.QtWidgets import QPlainTextEdit
    d = _dlg(qtbot)
    inputs = d.findChildren(QPlainTextEdit)
    assert any("command" in (w.placeholderText() or "").lower() for w in inputs)


def test_run_once_button_is_present(qtbot):
    d = _dlg(qtbot)
    texts = [b.text() for b in d.findChildren(QPushButton)]
    assert "Run" in texts


def test_run_once_launches_with_one_off_cmd_name(qtbot):
    vm = _vm()
    d = _dlg(qtbot, vm=vm)
    d.set_run_once_text("echo hello")
    d.trigger_run_once()
    vm.launch.assert_called_once()
    kwargs = vm.launch.call_args.kwargs
    assert kwargs["cmd_name"] == "[one-off]"
    assert kwargs["command_str"] == "echo hello"


def test_run_once_uses_selected_repo_and_worktree(qtbot):
    vm = _vm()
    d = _dlg(qtbot, vm=vm)
    d.set_run_once_text("ls -la")
    d.trigger_run_once()
    kwargs = vm.launch.call_args.kwargs
    assert kwargs["repo_path"] == "/repos/proj"
    assert kwargs["worktree_path"] == "/r/proj"


def test_run_once_no_startup_pattern(qtbot):
    vm = _vm()
    d = _dlg(qtbot, vm=vm)
    d.set_run_once_text("ls")
    d.trigger_run_once()
    kwargs = vm.launch.call_args.kwargs
    assert kwargs.get("startup_pattern") is None


def test_run_once_empty_text_is_noop(qtbot):
    vm = _vm()
    d = _dlg(qtbot, vm=vm)
    d.set_run_once_text("")
    d.trigger_run_once()
    vm.launch.assert_not_called()


def test_run_once_does_not_affect_saved_command_launch(qtbot):
    vm = _vm()
    d = _dlg(qtbot, vm=vm)
    d.set_run_once_text("echo side-effect")
    d.set_command("build")
    d.trigger_launch()
    kwargs = vm.launch.call_args.kwargs
    assert kwargs["cmd_name"] == "build"
    assert kwargs["command_str"] == "make"


# ── Save run-once command ─────────────────────────────────────────────────────

def test_save_button_is_present(qtbot):
    d = _dlg(qtbot)
    texts = [b.text() for b in d.findChildren(QPushButton)]
    assert "Save" in texts


def test_save_run_once_calls_vm_save_command(qtbot):
    vm = _vm()
    d = _dlg(qtbot, vm=vm)
    d.set_run_once_text("make build")
    d.trigger_save_run_once("mybuild")
    vm.save_command.assert_called_once_with("/repos/proj", "mybuild", "make build")


def test_save_run_once_empty_text_is_noop(qtbot):
    vm = _vm()
    d = _dlg(qtbot, vm=vm)
    d.set_run_once_text("")
    d.trigger_save_run_once("anything")
    vm.save_command.assert_not_called()


def test_save_run_once_empty_name_is_noop(qtbot):
    vm = _vm()
    d = _dlg(qtbot, vm=vm)
    d.set_run_once_text("echo hi")
    d.trigger_save_run_once("")
    vm.save_command.assert_not_called()


def test_save_run_once_refreshes_command_list(qtbot):
    vm = _vm()
    # After save_command, saved_commands returns the new list
    vm.save_command.side_effect = lambda *a, **kw: vm.saved_commands.configure_mock(
        return_value=[SavedCommand(name="mybuild", command="make build")]
    )
    d = _dlg(qtbot, vm=vm)
    d.set_run_once_text("make build")
    d.trigger_save_run_once("mybuild")
    assert d.command_choices() == ["mybuild"]


def test_save_run_once_does_not_close_dialog(qtbot):
    vm = _vm()
    d = _dlg(qtbot, vm=vm)
    d.set_run_once_text("echo hi")
    d.trigger_save_run_once("myscript")
    # dialog should still be open (not accepted/rejected)
    assert not d.result() or d.result() == 0
