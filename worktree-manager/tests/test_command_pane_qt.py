from unittest.mock import MagicMock

from PySide6.QtWidgets import QLabel, QPlainTextEdit, QPushButton

from worktree_manager.command_runner import RunHandle, RunStatus
from worktree_manager.ui.command_pane import CommandPane


def _handle(status=RunStatus.RUNNING, run_id="r1"):
    return RunHandle(
        run_id=run_id, cmd_name="frontend", repo_path="/r/proj",
        repo_name="proj", worktree_path="/r/proj-wt/feature-x",
        command=["echo", "hi"], status=status,
    )


def _pane(qtbot, **overrides):
    callbacks = dict(
        handle=_handle(),
        on_maximize=lambda p: None,
        on_stop=lambda: None,
        on_restart=lambda: None,
        on_remove=lambda: None,
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
    p = _pane(qtbot, on_remove=lambda: calls.append("remove"))
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
    p = _pane(qtbot)
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
