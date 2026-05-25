from PySide6.QtWidgets import QDialog

from worktree_manager.command_runner import RunHandle, RunStatus
from worktree_manager.ui.command_pane import CommandPane
from worktree_manager.ui.command_popout import CommandPopout


def _handle():
    return RunHandle(
        run_id="r1", cmd_name="frontend", repo_path="/r/proj",
        repo_name="proj", worktree_path="/r/proj-wt/feature-x",
        command=["echo", "hi"], status=RunStatus.RUNNING,
    )


def _popout(qtbot, **overrides):
    callbacks = dict(
        handle=_handle(),
        on_stop=lambda: None,
        on_restart=lambda: None,
        on_remove=lambda: None,
    )
    callbacks.update(overrides)
    p = CommandPopout(parent=None, **callbacks)
    qtbot.addWidget(p)
    return p


def test_command_popout_is_qdialog(qtbot):
    p = _popout(qtbot)
    assert isinstance(p, QDialog)


def test_command_popout_title_contains_cmd_repo_wt(qtbot):
    p = _popout(qtbot)
    title = p.windowTitle()
    assert "frontend" in title
    assert "proj" in title
    assert "feature-x" in title


def test_command_popout_contains_a_command_pane(qtbot):
    p = _popout(qtbot)
    assert p.findChild(CommandPane) is not None


def test_command_popout_append_line_routes_to_pane(qtbot):
    p = _popout(qtbot)
    p.append_line("hello")
    assert "hello" in p._pane.get_output_text()


def test_command_popout_set_status_routes_to_pane(qtbot):
    p = _popout(qtbot)
    p.set_status(RunStatus.ERROR)
    assert p._pane.status_dot_color() == "red"


def test_command_popout_clear_output_routes_to_pane(qtbot):
    p = _popout(qtbot)
    p.append_line("noise")
    p.clear_output()
    assert "noise" not in p._pane.get_output_text()
