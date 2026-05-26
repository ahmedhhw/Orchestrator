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


# ── basics ────────────────────────────────────────────────────────────────────

def test_launch_dialog_is_qdialog(qtbot):
    assert isinstance(_dlg(qtbot), QDialog)


def test_launch_dialog_has_run_button(qtbot):
    d = _dlg(qtbot)
    texts = [b.text() for b in d.findChildren(QPushButton)]
    assert any("Run" in t for t in texts)
    assert "Launch" not in texts
    assert "Cancel" not in texts


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


# ── Option C: fill from saved ─────────────────────────────────────────────────

def test_clicking_saved_cmd_fills_textarea(qtbot):
    d = _dlg(qtbot)
    d.set_command("build")
    assert d._cmd_edit.toPlainText() == "make"
    assert d._name_entry.text() == "build"


def test_clicking_saved_cmd_sets_selected(qtbot):
    d = _dlg(qtbot)
    d.set_command("build")
    assert d._selected_cmd is not None
    assert d._selected_cmd.name == "build"


def test_banner_shows_from_saved_when_unmodified(qtbot):
    d = _dlg(qtbot)
    d.set_command("build")
    assert "build" in d._banner_label.text()
    assert "From saved" in d._banner_label.text()


def test_banner_shows_modified_when_text_changed(qtbot):
    d = _dlg(qtbot)
    d.set_command("build")
    d._cmd_edit.setPlainText("make -j8")
    assert "Modified" in d._banner_label.text()


def test_banner_widget_hidden_when_no_name_match(qtbot):
    d = _dlg(qtbot)
    assert not d._banner_widget.isVisibleTo(d._banner_widget.parentWidget())


def test_revert_restores_saved_command(qtbot):
    d = _dlg(qtbot)
    d.set_command("build")
    d._cmd_edit.setPlainText("make -j8")
    # Trigger revert via banner action
    d._banner_action_btn.setProperty("_action", "revert")
    d._on_banner_action()
    assert d._cmd_edit.toPlainText() == "make"


def test_clear_empties_textarea_and_name(qtbot):
    d = _dlg(qtbot)
    d.set_command("build")
    d._banner_action_btn.setProperty("_action", "clear")
    d._on_banner_action()
    assert d._cmd_edit.toPlainText() == ""
    assert d._name_entry.text() == ""


def test_save_btn_label_is_always_save(qtbot):
    d = _dlg(qtbot)
    d.set_command("build")
    assert d._save_btn.text() == "Save"
    d._cmd_edit.setPlainText("make -j8")
    assert d._save_btn.text() == "Save"


def test_name_collision_warning_shown_when_name_matches_and_command_modified(qtbot):
    d = _dlg(qtbot)
    d.set_command("build")
    d._cmd_edit.setPlainText("make -j8")  # modified
    assert not d._name_collision_label.isHidden()
    assert "build" in d._name_collision_label.text()


def test_name_collision_warning_hidden_when_command_unmodified(qtbot):
    d = _dlg(qtbot)
    d.set_command("build")
    # command not changed — no warning
    assert d._name_collision_label.isHidden()


def test_name_collision_warning_shown_for_different_saved_command_name(qtbot):
    d = _dlg(qtbot)
    d.set_run_once_text("echo hi")
    d._name_entry.setText("test")  # matches saved "test", body differs
    assert not d._name_collision_label.isHidden()
    assert "test" in d._name_collision_label.text()


def test_name_collision_warning_hidden_when_no_collision(qtbot):
    d = _dlg(qtbot)
    d.set_run_once_text("echo hi")
    d._name_entry.setText("brandnew")
    assert d._name_collision_label.isHidden()


def test_update_trigger_calls_save_command(qtbot):
    vm = _vm()
    d = _dlg(qtbot, vm=vm)
    d.set_command("build")
    d._cmd_edit.setPlainText("make -j8")
    d._name_entry.setText("build")
    d._trigger_save()
    vm.save_command.assert_called_with("/repos/proj", "build", "make -j8")


# ── run ───────────────────────────────────────────────────────────────────────

def test_run_with_saved_cmd_uses_cmd_name_and_command(qtbot):
    vm = _vm()
    d = _dlg(qtbot, vm=vm)
    d.set_command("build")
    d.trigger_run()
    vm.launch.assert_called_once()
    kwargs = vm.launch.call_args.kwargs
    assert kwargs["cmd_name"] == "build"
    assert kwargs["command_str"] == "make"
    assert kwargs["repo_path"] == "/repos/proj"
    assert kwargs["repo_name"] == "proj"
    vm.set_last_used_repo.assert_called_once_with("/repos/proj")


def test_run_with_modified_saved_cmd_uses_one_off_name(qtbot):
    vm = _vm()
    d = _dlg(qtbot, vm=vm)
    d.set_command("build")
    d._cmd_edit.setPlainText("make -j8")
    d.trigger_run()
    kwargs = vm.launch.call_args.kwargs
    assert kwargs["command_str"] == "make -j8"
    # name field still says "build" so it should use that, not [one-off]
    assert kwargs["cmd_name"] == "build"


def test_run_with_custom_text_uses_one_off_when_no_name(qtbot):
    vm = _vm()
    d = _dlg(qtbot, vm=vm)
    d.set_run_once_text("echo hello")
    d.trigger_run()
    kwargs = vm.launch.call_args.kwargs
    assert kwargs["cmd_name"] == "[one-off]"
    assert kwargs["command_str"] == "echo hello"


def test_run_with_empty_textarea_is_noop(qtbot):
    vm = _vm()
    d = _dlg(qtbot, vm=vm)
    d.trigger_run()
    vm.launch.assert_not_called()


def test_run_uses_selected_repo_and_worktree(qtbot):
    vm = _vm()
    d = _dlg(qtbot, vm=vm)
    d.set_run_once_text("ls -la")
    d.trigger_run()
    kwargs = vm.launch.call_args.kwargs
    assert kwargs["repo_path"] == "/repos/proj"
    assert kwargs["worktree_path"] == "/r/proj"


def test_run_once_no_startup_pattern_for_custom(qtbot):
    vm = _vm()
    d = _dlg(qtbot, vm=vm)
    d.set_run_once_text("ls")
    d.trigger_run()
    assert vm.launch.call_args.kwargs.get("startup_pattern") is None


# ── conflict detection ────────────────────────────────────────────────────────

def test_existing_running_shows_conflict_no_restart(qtbot):
    existing = RunHandle(
        run_id="r1", cmd_name="build", repo_path="/repos/proj",
        repo_name="proj", worktree_path="/r/proj", command=["make"],
        status=RunStatus.RUNNING,
    )
    vm = _vm(existing=existing)
    d = _dlg(qtbot, vm=vm)
    d.set_command("build")
    d.trigger_run()
    assert "already running" in d._conflict_label.text().lower()
    assert not d._restart_btn.isVisible()
    vm.launch.assert_not_called()


def test_existing_stopped_shows_restart_button(qtbot):
    existing = RunHandle(
        run_id="r1", cmd_name="build", repo_path="/repos/proj",
        repo_name="proj", worktree_path="/r/proj", command=["make"],
        status=RunStatus.STOPPED,
    )
    vm = _vm(existing=existing)
    d = _dlg(qtbot, vm=vm)
    d.set_command("build")
    d.trigger_run()
    assert d._restart_btn.isVisible()
    d._restart_btn.click()
    vm.restart.assert_called_once_with("r1")


def test_no_conflict_check_for_modified_or_custom(qtbot):
    existing = RunHandle(
        run_id="r1", cmd_name="build", repo_path="/repos/proj",
        repo_name="proj", worktree_path="/r/proj", command=["make"],
        status=RunStatus.RUNNING,
    )
    vm = _vm(existing=existing)
    d = _dlg(qtbot, vm=vm)
    d.set_command("build")
    d._cmd_edit.setPlainText("make -j8")  # modified — no conflict check
    d.trigger_run()
    vm.launch.assert_called_once()


# ── filter ────────────────────────────────────────────────────────────────────

def test_filter_narrows_command_list(qtbot):
    d = _dlg(qtbot)
    d._cmd_filter.setText("test")
    assert [c.name for c in d._visible_cmds()] == ["test"]


# ── save ──────────────────────────────────────────────────────────────────────

def test_save_button_is_present(qtbot):
    d = _dlg(qtbot)
    texts = [b.text() for b in d.findChildren(QPushButton)]
    assert any("Save" in t for t in texts)


def test_trigger_save_calls_vm_save_command(qtbot):
    vm = _vm()
    d = _dlg(qtbot, vm=vm)
    d.set_run_once_text("make build")
    d.trigger_save_run_once("mybuild")
    vm.save_command.assert_called_once_with("/repos/proj", "mybuild", "make build")


def test_trigger_save_empty_text_is_noop(qtbot):
    vm = _vm()
    d = _dlg(qtbot, vm=vm)
    d.set_run_once_text("")
    d.trigger_save_run_once("anything")
    vm.save_command.assert_not_called()


def test_trigger_save_empty_name_is_noop(qtbot):
    vm = _vm()
    d = _dlg(qtbot, vm=vm)
    d.set_run_once_text("echo hi")
    d.trigger_save_run_once("")
    vm.save_command.assert_not_called()


def test_trigger_save_refreshes_command_list(qtbot):
    vm = _vm()
    vm.save_command.side_effect = lambda *a, **kw: vm.saved_commands.configure_mock(
        return_value=[SavedCommand(name="mybuild", command="make build")]
    )
    d = _dlg(qtbot, vm=vm)
    d.set_run_once_text("make build")
    d.trigger_save_run_once("mybuild")
    assert d.command_choices() == ["mybuild"]


def test_trigger_save_does_not_close_dialog(qtbot):
    vm = _vm()
    d = _dlg(qtbot, vm=vm)
    d.set_run_once_text("echo hi")
    d.trigger_save_run_once("myscript")
    assert not d.result() or d.result() == 0


# ── edit / delete / copy ──────────────────────────────────────────────────────

def test_delete_cmd_calls_vm_delete(qtbot):
    vm = _vm()
    d = _dlg(qtbot, vm=vm)
    cmd = d._commands[0]
    d._delete_cmd(cmd)
    vm.delete_command.assert_called_once_with(d._current_repo_path(), "build")


def test_delete_cmd_clears_selection_when_selected(qtbot):
    vm = _vm()
    vm.delete_command.side_effect = lambda *a: vm.saved_commands.configure_mock(
        return_value=[SavedCommand(name="test", command="pytest")]
    )
    d = _dlg(qtbot, vm=vm)
    d.set_command("build")
    cmd = next(c for c in d._commands if c.name == "build")
    d._delete_cmd(cmd)
    assert d._selected_cmd is None


def test_copy_command_puts_text_on_clipboard(qtbot):
    from PySide6.QtWidgets import QApplication
    vm = _vm()
    d = _dlg(qtbot, vm=vm)
    cmd = d._commands[0]
    QApplication.clipboard().setText("")
    QApplication.clipboard().setText(cmd.command)
    assert QApplication.clipboard().text() == "make"
