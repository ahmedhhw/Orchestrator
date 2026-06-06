from unittest.mock import MagicMock

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextOption
from PySide6.QtWidgets import QComboBox, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QTextEdit

from worktree_manager.command_runner import RunHandle, RunStatus
from worktree_manager.models import WorktreeModel
from worktree_manager.ui.command_pane import CommandPane


def _handle(status=RunStatus.RUNNING, run_id="r1", worktree_path="/r/proj-wt/feature-x"):
    return RunHandle(
        run_id=run_id, cmd_name="frontend", repo_path="/r/proj",
        repo_name="proj", worktree_path=worktree_path,
        command=["echo", "hi"], status=status,
    )


def _worktrees():
    return [
        WorktreeModel(path="/r/proj-wt/feature-x", branch="feature/x", is_main=False,
                      last_commit_ts=0, is_merged=False, is_stale=False),
        WorktreeModel(path="/r/proj-wt/main", branch="main", is_main=True,
                      last_commit_ts=0, is_merged=False, is_stale=False),
    ]




def _pane(qtbot, **overrides):
    callbacks = dict(
        handle=_handle(),
        on_maximize=lambda p: None,
        on_stop=lambda: None,
        on_restart=lambda: None,
        on_remove=lambda: None,
        confirm_fn=lambda msg: True,
    )
    callbacks.update(overrides)
    p = CommandPane(parent=None, **callbacks)
    qtbot.addWidget(p)
    return p


def _button_with(pane, label):
    return next(b for b in pane.findChildren(QPushButton) if b.text() == label)


def test_command_pane_header_shows_cmd_repo_wt(qtbot):
    p = _pane(qtbot)
    assert "frontend" in p.header_text()
    assert "proj" in p.header_text()
    assert "feature-x" in p.header_text()


def test_command_pane_initial_status_dot_running(qtbot):
    p = _pane(qtbot)
    assert p.status_dot_color() == "green"


def test_command_pane_set_status_changes_dot_color(qtbot):
    p = _pane(qtbot)
    p.set_status(RunStatus.ERROR)
    assert p.status_dot_color() == "red"
    p.set_status(RunStatus.STOPPED)
    assert p.status_dot_color() == "gray"


def test_command_pane_append_line_renders_in_output(qtbot):
    p = _pane(qtbot)
    p.append_line("hello world")
    assert "hello world" in p.get_output_text()


def test_command_pane_clear_output_empties_the_textbox(qtbot):
    p = _pane(qtbot)
    p.append_line("noise")
    p.clear_output()
    assert "noise" not in p.get_output_text()


def test_command_pane_stop_button_invokes_callback(qtbot):
    calls = []
    p = _pane(qtbot, on_stop=lambda: calls.append("stop"))
    p.trigger_stop()
    assert calls == ["stop"]


def test_command_pane_restart_button_invokes_callback(qtbot):
    calls = []
    p = _pane(qtbot, on_restart=lambda: calls.append("restart"))
    p.trigger_restart()
    assert calls == ["restart"]


def test_command_pane_remove_button_invokes_callback(qtbot):
    calls = []
    p = _pane(qtbot, on_remove=lambda: calls.append("remove"),
              confirm_fn=lambda msg: True)
    p.trigger_remove()
    assert calls == ["remove"]


def test_command_pane_maximize_button_invokes_callback_with_self(qtbot):
    calls = []
    p = _pane(qtbot, on_maximize=lambda x: calls.append(x))
    p.trigger_maximize()
    assert calls == [p]


def test_command_pane_show_and_hide_find_bar(qtbot):
    p = _pane(qtbot)
    assert p.find_bar_visible() is False
    p.show_find_bar()
    assert p.find_bar_visible() is True
    p.hide_find_bar()
    assert p.find_bar_visible() is False


def test_command_pane_find_counts_matches(qtbot):
    p = _pane(qtbot)
    p.append_line("foo bar foo")
    p.append_line("baz foo")
    assert p.find("foo") == 3
    assert p.find("nope") == 0
    assert p.find("") == 0


def test_command_pane_update_run_id_changes_attribute(qtbot):
    p = _pane(qtbot)
    p.update_run_id("new-id")
    assert p._run_id == "new-id"


def test_command_pane_update_callbacks_replaces_handlers(qtbot):
    p = _pane(qtbot, confirm_fn=lambda msg: True)
    calls = []
    p.update_callbacks(
        on_stop=lambda: calls.append("s"),
        on_restart=lambda: calls.append("r"),
        on_remove=lambda: calls.append("x"),
    )
    p.trigger_stop()
    p.trigger_restart()
    p.trigger_remove()
    assert calls == ["s", "r", "x"]


def test_command_pane_popout_button_hidden_when_show_popout_btn_false(qtbot):
    p = CommandPane(
        parent=None, handle=_handle(),
        on_maximize=lambda x: None, on_stop=lambda: None,
        on_restart=lambda: None, on_remove=lambda: None,
        show_popout_btn=False,
    )
    qtbot.addWidget(p)
    assert not any(b.toolTip() == "Pop out" for b in p.findChildren(QPushButton))


# ── stdin input bar ──────────────────────────────────────────────────────────

def test_stdin_bar_is_visible_by_default(qtbot):
    p = _pane(qtbot)
    assert p.stdin_bar_visible() is True


def test_stdin_bar_has_send_button(qtbot):
    p = _pane(qtbot)
    assert any(b.text() == "Send" for b in p.findChildren(QPushButton))


def test_stdin_bar_has_line_edit(qtbot):
    p = _pane(qtbot)
    # There should be a QLineEdit with placeholder containing "stdin"
    inputs = p.findChildren(QLineEdit)
    assert any("stdin" in (w.placeholderText() or "").lower() for w in inputs)


def test_send_button_calls_on_send_with_text(qtbot):
    sent = []
    p = _pane(qtbot, on_send=lambda text: sent.append(text))
    p.set_stdin_text("y")
    p.trigger_send()
    assert sent == ["y"]


def test_trigger_send_clears_the_input(qtbot):
    p = _pane(qtbot, on_send=lambda t: None)
    p.set_stdin_text("hello")
    p.trigger_send()
    assert p.get_stdin_text() == ""


def test_enter_key_in_stdin_triggers_send(qtbot):
    sent = []
    p = _pane(qtbot, on_send=lambda text: sent.append(text))
    p.set_stdin_text("yes")
    p.show()
    stdin_edit = next(
        w for w in p.findChildren(QLineEdit)
        if "stdin" in (w.placeholderText() or "").lower()
    )
    qtbot.keyPress(stdin_edit, Qt.Key_Return)
    assert sent == ["yes"]


def test_stdin_bar_disabled_when_process_stopped(qtbot):
    p = _pane(qtbot, handle=_handle(status=RunStatus.STOPPED))
    assert p.stdin_input_enabled() is False


def test_stdin_bar_disabled_when_process_errors(qtbot):
    p = _pane(qtbot, handle=_handle(status=RunStatus.ERROR))
    assert p.stdin_input_enabled() is False


def test_stdin_bar_enabled_when_process_running(qtbot):
    p = _pane(qtbot, handle=_handle(status=RunStatus.RUNNING))
    assert p.stdin_input_enabled() is True


def test_set_status_stopped_disables_stdin_bar(qtbot):
    p = _pane(qtbot)
    assert p.stdin_input_enabled() is True
    p.set_status(RunStatus.STOPPED)
    assert p.stdin_input_enabled() is False


def test_set_status_running_reenables_stdin_bar(qtbot):
    p = _pane(qtbot, handle=_handle(status=RunStatus.STOPPED))
    p.set_status(RunStatus.RUNNING)
    assert p.stdin_input_enabled() is True


def test_stdin_history_up_arrow_recalls_last_sent(qtbot):
    p = _pane(qtbot, on_send=lambda t: None)
    p.set_stdin_text("first")
    p.trigger_send()
    p.set_stdin_text("second")
    p.trigger_send()
    stdin_edit = next(
        w for w in p.findChildren(QLineEdit)
        if "stdin" in (w.placeholderText() or "").lower()
    )
    qtbot.keyPress(stdin_edit, Qt.Key_Up)
    assert p.get_stdin_text() == "second"


def test_stdin_history_up_twice_goes_further_back(qtbot):
    p = _pane(qtbot, on_send=lambda t: None)
    p.set_stdin_text("first")
    p.trigger_send()
    p.set_stdin_text("second")
    p.trigger_send()
    stdin_edit = next(
        w for w in p.findChildren(QLineEdit)
        if "stdin" in (w.placeholderText() or "").lower()
    )
    qtbot.keyPress(stdin_edit, Qt.Key_Up)
    qtbot.keyPress(stdin_edit, Qt.Key_Up)
    assert p.get_stdin_text() == "first"


def test_stdin_history_down_arrow_moves_forward(qtbot):
    p = _pane(qtbot, on_send=lambda t: None)
    p.set_stdin_text("first")
    p.trigger_send()
    p.set_stdin_text("second")
    p.trigger_send()
    stdin_edit = next(
        w for w in p.findChildren(QLineEdit)
        if "stdin" in (w.placeholderText() or "").lower()
    )
    qtbot.keyPress(stdin_edit, Qt.Key_Up)
    qtbot.keyPress(stdin_edit, Qt.Key_Up)
    qtbot.keyPress(stdin_edit, Qt.Key_Down)
    assert p.get_stdin_text() == "second"


def test_empty_text_is_not_sent(qtbot):
    sent = []
    p = _pane(qtbot, on_send=lambda t: sent.append(t))
    p.set_stdin_text("")
    p.trigger_send()
    assert sent == []


# ── worktree combo ────────────────────────────────────────────────────────────

def test_worktree_combo_shows_folder_names(qtbot):
    p = _pane(qtbot, worktrees=_worktrees())
    combo = p.findChild(QComboBox)
    wt_texts = [combo.itemText(i) for i in range(combo.count())]
    assert "feature-x" in wt_texts
    assert "main" in wt_texts


# ── maximize toggle ───────────────────────────────────────────────────────────

def test_maximize_button_is_present_when_show_popout_btn_true(qtbot):
    p = _pane(qtbot)
    assert any(b.toolTip() == "Maximize" for b in p.findChildren(QPushButton))


def test_maximize_button_absent_when_show_popout_btn_false(qtbot):
    p = CommandPane(
        parent=None, handle=_handle(),
        on_maximize=lambda x: None, on_stop=lambda: None,
        on_restart=lambda: None, on_remove=lambda: None,
        show_popout_btn=False,
    )
    qtbot.addWidget(p)
    assert not any(b.toolTip() in ("Maximize", "Unmaximize")
                   for b in p.findChildren(QPushButton))


def test_no_popout_button_present(qtbot):
    p = _pane(qtbot)
    assert not any(b.toolTip() == "Pop out" for b in p.findChildren(QPushButton))


def test_maximize_toggle_calls_on_maximize_then_on_unmaximize(qtbot):
    maximize_calls = []
    unmaximize_calls = []
    p = _pane(qtbot,
              on_maximize=lambda pane: maximize_calls.append(pane),
              on_unmaximize=lambda pane: unmaximize_calls.append(pane))
    # First click → maximize
    p.trigger_maximize()
    assert maximize_calls == [p]
    assert unmaximize_calls == []
    # Second click → unmaximize
    p.trigger_maximize()
    assert unmaximize_calls == [p]


def test_remove_shows_confirmation_before_removing(qtbot):
    removed = []
    p = _pane(qtbot, on_remove=lambda: removed.append(True),
              confirm_fn=lambda msg: False)
    p.trigger_remove()
    assert removed == []


def test_remove_proceeds_when_confirmed(qtbot):
    removed = []
    p = _pane(qtbot, on_remove=lambda: removed.append(True),
              confirm_fn=lambda msg: True)
    p.trigger_remove()
    assert removed == [True]


def test_maximize_toggle_button_tooltip_changes(qtbot):
    maximize_btn = None

    def find_btn(pane):
        return next(
            (b for b in pane.findChildren(QPushButton)
             if b.toolTip() in ("Maximize", "Unmaximize")),
            None,
        )

    p = _pane(qtbot,
              on_maximize=lambda pane: None,
              on_unmaximize=lambda pane: None)
    btn = find_btn(p)
    assert btn is not None
    assert btn.toolTip() == "Maximize"
    p.trigger_maximize()
    assert btn.toolTip() == "Unmaximize"
    p.trigger_maximize()
    assert btn.toolTip() == "Maximize"


def test_output_area_uses_widget_width_line_wrap(qtbot):
    p = _pane(qtbot)
    text_edit = p.findChildren(QTextEdit)[0]
    assert text_edit.lineWrapMode() == QTextEdit.WidgetWidth


def test_output_area_uses_wrap_anywhere_word_wrap(qtbot):
    p = _pane(qtbot)
    text_edit = p.findChildren(QTextEdit)[0]
    assert text_edit.wordWrapMode() == QTextOption.WrapAnywhere


def test_output_area_has_no_horizontal_scrollbar(qtbot):
    from PySide6.QtCore import Qt as _Qt
    p = _pane(qtbot)
    text_edit = p.findChildren(QTextEdit)[0]
    assert text_edit.horizontalScrollBarPolicy() == _Qt.ScrollBarAlwaysOff


# ── command edit bar ──────────────────────────────────────────────────────────

def _pane_with_cmd(qtbot, cmd="npm run dev", is_one_off=False,
                   on_run_with_command=None, on_save_command=None,
                   on_restart=None):
    p = CommandPane(
        parent=None, handle=_handle(),
        on_maximize=lambda x: None, on_stop=lambda: None,
        on_restart=on_restart or (lambda: None), on_remove=lambda: None,
        confirm_fn=lambda msg: True,
        on_run_with_command=on_run_with_command,
        on_save_command=on_save_command,
        is_one_off=is_one_off,
    )
    p.set_edit_command(cmd)
    qtbot.addWidget(p)
    return p


def test_command_bar_shows_command_text_in_view_mode(qtbot):
    p = _pane_with_cmd(qtbot, cmd="npm run dev")
    assert p._cmd_label.text() == "npm run dev"
    assert not p._cmd_label.isHidden()


def test_edit_button_visible_in_view_mode(qtbot):
    p = _pane_with_cmd(qtbot)
    assert not p._btn_edit.isHidden()


def test_edit_mode_widgets_hidden_in_view_mode(qtbot):
    p = _pane_with_cmd(qtbot)
    assert p._cmd_edit.isHidden()
    assert p._btn_run.isHidden()
    assert p._btn_revert.isHidden()


def test_enter_edit_mode_shows_edit_widgets_hides_label(qtbot):
    p = _pane_with_cmd(qtbot, cmd="npm run dev")
    p.enter_edit_mode()
    assert not p._cmd_edit.isHidden()
    assert not p._btn_run.isHidden()
    assert not p._btn_revert.isHidden()
    assert p._cmd_label.isHidden()
    assert p._btn_edit.isHidden()


def test_enter_edit_mode_populates_edit_with_current_command(qtbot):
    p = _pane_with_cmd(qtbot, cmd="npm run dev")
    p.enter_edit_mode()
    assert p._cmd_edit.toPlainText() == "npm run dev"


def test_enter_edit_mode_disables_restart_button(qtbot):
    p = _pane_with_cmd(qtbot)
    restart_btn = next(b for b in p.findChildren(QPushButton) if b.toolTip() == "Restart")
    p.enter_edit_mode()
    assert not restart_btn.isEnabled()


def test_exit_edit_mode_restores_view_mode(qtbot):
    p = _pane_with_cmd(qtbot)
    p.enter_edit_mode()
    p.exit_edit_mode()
    assert not p._cmd_label.isHidden()
    assert not p._btn_edit.isHidden()
    assert p._cmd_edit.isHidden()
    assert p._btn_run.isHidden()
    assert p._btn_revert.isHidden()


def test_exit_edit_mode_reenables_restart_button(qtbot):
    p = _pane_with_cmd(qtbot)
    restart_btn = next(b for b in p.findChildren(QPushButton) if b.toolTip() == "Restart")
    p.enter_edit_mode()
    p.exit_edit_mode()
    assert restart_btn.isEnabled()


def test_revert_restores_original_text_and_exits_edit_mode(qtbot):
    p = _pane_with_cmd(qtbot, cmd="npm run dev")
    p.enter_edit_mode()
    p._cmd_edit.setPlainText("something else")
    p._btn_revert.click()
    assert p._cmd_edit.isHidden()
    assert p._cmd_label.text() == "npm run dev"


def test_save_hidden_for_one_off_command(qtbot):
    p = _pane_with_cmd(qtbot, is_one_off=True)
    p.enter_edit_mode()
    assert p._btn_save.isHidden()


def test_save_visible_for_saved_command(qtbot):
    p = _pane_with_cmd(qtbot, is_one_off=False)
    p.enter_edit_mode()
    assert not p._btn_save.isHidden()


def test_run_button_calls_on_run_with_command_and_stays_in_edit_mode(qtbot):
    called = []
    p = _pane_with_cmd(qtbot, cmd="npm run dev",
                        on_run_with_command=lambda t: called.append(t))
    p.enter_edit_mode()
    p._cmd_edit.setPlainText("npm run build")
    p._btn_run.click()
    assert called == ["npm run build"]
    assert not p._cmd_edit.isHidden()


def test_save_button_calls_on_save_command(qtbot):
    called = []
    p = _pane_with_cmd(qtbot, cmd="npm run dev",
                        on_save_command=lambda t: called.append(t))
    p.enter_edit_mode()
    p._cmd_edit.setPlainText("npm run build")
    p._btn_save.click()
    assert called == ["npm run build"]


def test_revert_after_run_restores_snapshot_from_edit_entry(qtbot):
    # enter edit, type new text, simulate Run ▶ (panel calls set_edit_command),
    # then Revert — should restore the text from when Edit ✎ was first clicked
    p = _pane_with_cmd(qtbot, cmd="npm run dev")
    p.enter_edit_mode()
    p._cmd_edit.setPlainText("npm run build")
    # simulate what the panel does after _do_run_with_command (updates label only)
    p.set_edit_command("npm run build")
    # Revert — should restore "npm run dev" (the snapshot from edit entry)
    p._btn_revert.click()
    assert p._cmd_label.text() == "npm run dev"


def test_auto_height_grows_with_line_count(qtbot):
    p = _pane_with_cmd(qtbot)
    p.enter_edit_mode()
    h1 = p._cmd_edit.height()
    p._cmd_edit.setPlainText("line1\nline2\nline3")
    h3 = p._cmd_edit.height()
    assert h3 > h1


def test_auto_height_capped_at_five_lines(qtbot):
    p = _pane_with_cmd(qtbot)
    p.enter_edit_mode()
    five_lines = "\n".join(f"line{i}" for i in range(5))
    six_lines = five_lines + "\nline6"
    p._cmd_edit.setPlainText(five_lines)
    h5 = p._cmd_edit.height()
    p._cmd_edit.setPlainText(six_lines)
    h6 = p._cmd_edit.height()
    assert h5 == h6


# ── revert pending note ───────────────────────────────────────────────────────

def test_revert_note_hidden_by_default(qtbot):
    p = _pane_with_cmd(qtbot)
    assert p._revert_note.isHidden()


def test_revert_note_shown_after_revert(qtbot):
    p = _pane_with_cmd(qtbot, cmd="npm run dev")
    p.enter_edit_mode()
    p._btn_revert.click()
    assert not p._revert_note.isHidden()


def test_revert_note_hidden_after_restart(qtbot):
    calls = []
    p = _pane_with_cmd(qtbot, cmd="npm run dev",
                        on_restart=lambda: calls.append("restart"))
    p.enter_edit_mode()
    p._btn_revert.click()
    assert not p._revert_note.isHidden()
    p.trigger_restart()
    assert p._revert_note.isHidden()


def test_revert_note_hidden_again_after_new_edit_entry(qtbot):
    p = _pane_with_cmd(qtbot, cmd="npm run dev")
    p.enter_edit_mode()
    p._btn_revert.click()
    p.enter_edit_mode()
    assert p._revert_note.isHidden()
