from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QDialog, QLineEdit, QPushButton

from worktree_manager.command_runner import RunHandle, RunStatus
from worktree_manager.ui.command_center_panel import CommandCenterPanel
from worktree_manager.ui.command_pane import CommandPane


def _handle(run_id="r1", cmd_name="build", repo_name="proj",
            wt="/r/proj", status=RunStatus.RUNNING):
    return RunHandle(
        run_id=run_id, cmd_name=cmd_name, repo_path="/r/" + repo_name,
        repo_name=repo_name, worktree_path=wt, command=["echo"],
        status=status,
    )


def _vm(runs=None):
    vm = MagicMock()
    vm.all_runs.return_value = runs or []
    vm.all_repos.return_value = {"/r/proj": MagicMock()}
    vm.get_run.side_effect = lambda rid: next(
        (h for h in (runs or []) if h.run_id == rid), None,
    )
    return vm


def _panel(qtbot, vm=None, on_close=None):
    p = CommandCenterPanel(
        parent=None, vm=vm or _vm(),
        on_close=on_close or (lambda: None),
    )
    qtbot.addWidget(p)
    return p


def test_command_center_panel_toolbar_has_expected_buttons(qtbot):
    p = _panel(qtbot)
    texts = [b.text() for b in p.findChildren(QPushButton)]
    assert any("Launch" in t for t in texts)
    assert "×" not in texts


def test_command_center_panel_empty_state_visible_initially(qtbot):
    p = _panel(qtbot)
    assert p.empty_state_visible() is True
    assert p.pane_count() == 0


def test_command_center_panel_add_pane_hides_empty_state(qtbot):
    p = _panel(qtbot)
    p.add_pane(_handle())
    assert p.empty_state_visible() is False
    assert p.pane_count() == 1
    assert isinstance(p.get_pane("r1"), CommandPane)


def test_command_center_panel_add_pane_is_idempotent_by_run_id(qtbot):
    p = _panel(qtbot)
    h = _handle()
    p.add_pane(h)
    p.add_pane(h)
    assert p.pane_count() == 1


def test_command_center_panel_panes_appear_in_insertion_order(qtbot):
    p = _panel(qtbot)
    p.add_pane(_handle(run_id="r1", cmd_name="first"))
    p.add_pane(_handle(run_id="r2", cmd_name="second"))
    p.add_pane(_handle(run_id="r3", cmd_name="third"))
    layout = p._scroll_layout
    pane_order = []
    for i in range(layout.count()):
        w = layout.itemAt(i).widget()
        if isinstance(w, CommandPane):
            pane_order.append(w._run_id)
    assert pane_order == ["r1", "r2", "r3"]


def test_command_center_panel_remove_pane_calls_vm_and_drops_pane(qtbot):
    vm = _vm()
    p = _panel(qtbot, vm=vm)
    p.add_pane(_handle())
    p.remove_pane("r1")
    vm.remove_run.assert_called_once_with("r1")
    assert p.pane_count() == 0
    assert p.empty_state_visible() is True


def test_command_center_panel_route_output_appends_to_pane(qtbot):
    p = _panel(qtbot)
    p.add_pane(_handle())
    p.route_output("r1", "hello")
    assert "hello" in p.get_pane("r1").get_output_text()


def test_command_center_panel_route_status_updates_dot(qtbot):
    p = _panel(qtbot)
    p.add_pane(_handle())
    p.route_status("r1", RunStatus.ERROR)
    assert p.get_pane("r1").status_dot_color() == "red"


def test_command_center_panel_search_filters_visible_panes(qtbot):
    p = _panel(qtbot)
    p.add_pane(_handle(run_id="r1", cmd_name="build"))
    p.add_pane(_handle(run_id="r2", cmd_name="test"))
    search = p.findChild(QLineEdit)
    search.setText("build")
    assert p.is_visible("r1") is True
    assert p.is_visible("r2") is False


def test_command_center_panel_close_button_invokes_callback(qtbot):
    calls = []
    p = _panel(qtbot, on_close=lambda: calls.append("x"))
    p.trigger_close()
    assert calls == ["x"]


def test_command_center_panel_restores_existing_runs_on_construction(qtbot):
    h = _handle(run_id="r1")
    h.output_lines.append("prior line")
    vm = _vm(runs=[h])
    p = _panel(qtbot, vm=vm)
    assert p.pane_count() == 1
    assert "prior line" in p.get_pane("r1").get_output_text()


def test_command_center_panel_launch_button_opens_launch_dialog(qtbot):
    p = _panel(qtbot)
    with patch("worktree_manager.ui.command_center_panel.LaunchDialog") as MockDlg:
        instance = MagicMock(spec=QDialog)
        MockDlg.return_value = instance
        p._open_launch_dialog()
    MockDlg.assert_called_once()
    instance.exec.assert_called_once()


def test_notif_toggle_reads_initial_state_from_store(qtbot):
    vm = _vm()
    vm._store.get_ui_pref.side_effect = (
        lambda key, default=None:
            False if key == "cmd_center_notifications_enabled" else default
    )
    p = _panel(qtbot, vm=vm)
    assert p._notif_btn.isChecked() is False
    assert p._notif_btn.text() == "🔕"


def test_notif_toggle_defaults_on_when_pref_missing(qtbot):
    vm = _vm()
    vm._store.get_ui_pref.side_effect = lambda key, default=None: default
    p = _panel(qtbot, vm=vm)
    assert p._notif_btn.isChecked() is True
    assert p._notif_btn.text() == "🔔"


def test_notif_toggle_persists_to_store(qtbot):
    vm = _vm()
    vm._store.get_ui_pref.side_effect = lambda key, default=None: default
    p = _panel(qtbot, vm=vm)
    p._notif_btn.setChecked(False)
    vm._store.set_ui_pref.assert_any_call("cmd_center_notifications_enabled", False)
    assert p._notif_btn.text() == "🔕"
    p._notif_btn.setChecked(True)
    vm._store.set_ui_pref.assert_any_call("cmd_center_notifications_enabled", True)
    assert p._notif_btn.text() == "🔔"



def test_command_center_panel_wires_vm_callbacks(qtbot):
    vm = _vm()
    p = _panel(qtbot, vm=vm)
    assert vm.on_run_added is not None
    assert vm.on_output is not None
    assert vm.on_status_changed is not None
    assert vm.on_run_id_changed is not None


def test_command_center_panel_maximize_and_restore_tiled(qtbot):
    p = _panel(qtbot)
    p.add_pane(_handle(run_id="r1"))
    p.add_pane(_handle(run_id="r2"))
    p.maximize_pane("r1")
    assert p.is_maximized("r1") is True
    assert p.is_visible("r1") is True
    assert p.is_visible("r2") is False
    p.restore_tiled()
    assert p.is_maximized("r1") is False
    assert p.is_visible("r2") is True


def test_pane_maximize_button_triggers_maximize_in_panel(qtbot):
    p = _panel(qtbot)
    p.add_pane(_handle(run_id="r1"))
    p.add_pane(_handle(run_id="r2"))
    pane = p.get_pane("r1")
    pane.trigger_maximize()
    assert p.is_maximized("r1") is True
    assert p.is_visible("r2") is False


def test_pane_maximize_then_trigger_again_restores_tiled(qtbot):
    p = _panel(qtbot)
    p.add_pane(_handle(run_id="r1"))
    p.add_pane(_handle(run_id="r2"))
    pane = p.get_pane("r1")
    pane.trigger_maximize()
    assert p.is_maximized("r1") is True
    pane.trigger_maximize()
    assert p.is_maximized("r1") is False
    assert p.is_visible("r2") is True


def test_no_popout_button_in_pane_added_by_panel(qtbot):
    p = _panel(qtbot)
    p.add_pane(_handle(run_id="r1"))
    pane = p.get_pane("r1")
    assert not any(b.toolTip() == "Pop out" for b in pane.findChildren(QPushButton))
