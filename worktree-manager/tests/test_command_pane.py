import pytest
from unittest.mock import MagicMock


@pytest.fixture(scope="module", autouse=True)
def require_display():
    try:
        import tkinter as tk
        r = tk.Tk()
        r.withdraw()
        r.destroy()
    except Exception:
        pytest.skip("no display available")


@pytest.fixture
def root():
    import tkinter as tk
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


@pytest.fixture
def handle():
    from worktree_manager.command_runner import RunHandle, RunStatus
    return RunHandle(
        run_id="r1",
        cmd_name="frontend",
        repo_path="/repos/proj",
        repo_name="proj",
        worktree_path="/repos/proj-wt/feat",
        command=["npm", "run", "dev"],
        status=RunStatus.RUNNING,
    )


@pytest.fixture
def pane(root, handle):
    from worktree_manager.ui.command_pane import CommandPane
    on_maximize = MagicMock()
    on_stop = MagicMock()
    on_restart = MagicMock()
    p = CommandPane(root, handle=handle,
                    on_maximize=on_maximize,
                    on_stop=on_stop,
                    on_restart=on_restart)
    return p, on_maximize, on_stop, on_restart


def test_pane_header_contains_cmd_and_repo(pane):
    p, _, _, _ = pane
    assert "frontend" in p.header_text()
    assert "proj" in p.header_text()


def test_append_line_adds_to_textbox(pane):
    p, _, _, _ = pane
    p.append_line("hello world")
    content = p.get_output_text()
    assert "hello world" in content


def test_stop_button_calls_on_stop(pane):
    p, _, on_stop, _ = pane
    p.trigger_stop()
    on_stop.assert_called_once()


def test_restart_button_calls_on_restart(pane):
    p, _, _, on_restart = pane
    p.trigger_restart()
    on_restart.assert_called_once()


def test_maximize_button_calls_on_maximize(pane):
    p, on_maximize, _, _ = pane
    p.trigger_maximize()
    on_maximize.assert_called_once_with(p)


def test_set_status_running_shows_green_dot(pane):
    from worktree_manager.command_runner import RunStatus
    p, _, _, _ = pane
    p.set_status(RunStatus.RUNNING)
    assert p.status_dot_color() == "green"


def test_set_status_stopped_shows_grey_dot(pane):
    from worktree_manager.command_runner import RunStatus
    p, _, _, _ = pane
    p.set_status(RunStatus.STOPPED)
    assert p.status_dot_color() == "gray"


def test_set_status_error_shows_red_dot(pane):
    from worktree_manager.command_runner import RunStatus
    p, _, _, _ = pane
    p.set_status(RunStatus.ERROR)
    assert p.status_dot_color() == "red"


def test_copy_copies_output_to_clipboard(pane, root):
    p, _, _, _ = pane
    p.append_line("line one")
    p.append_line("line two")
    p.trigger_copy()
    clipboard = root.clipboard_get()
    assert "line one" in clipboard
    assert "line two" in clipboard


def test_clear_output_empties_textbox(pane):
    p, _, _, _ = pane
    p.append_line("something")
    p.clear_output()
    assert p.get_output_text().strip() == ""


def test_show_find_bar_makes_it_visible(pane):
    p, _, _, _ = pane
    p.show_find_bar()
    assert p.find_bar_visible()


def test_hide_find_bar_makes_it_hidden(pane):
    p, _, _, _ = pane
    p.show_find_bar()
    p.hide_find_bar()
    assert not p.find_bar_visible()


def test_find_highlights_matching_lines(pane):
    p, _, _, _ = pane
    p.append_line("error: something failed")
    p.append_line("info: all good")
    p.append_line("error: another failure")
    count = p.find("error")
    assert count == 2


def test_remove_button_calls_on_remove(root, handle):
    from worktree_manager.ui.command_pane import CommandPane
    on_remove = MagicMock()
    p = CommandPane(root, handle=handle,
                    on_maximize=MagicMock(), on_stop=MagicMock(),
                    on_restart=MagicMock(), on_remove=on_remove)
    p.trigger_remove()
    on_remove.assert_called_once()


def test_find_returns_zero_for_no_match(pane):
    p, _, _, _ = pane
    p.append_line("everything is fine")
    count = p.find("error")
    assert count == 0
