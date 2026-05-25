import time
import sys
import pytest
from worktree_manager.command_runner import CommandRunner


@pytest.fixture
def runner():
    r = CommandRunner()
    yield r
    for h in list(r._handles.values()):
        try:
            r.terminate(h.run_id)
        except Exception:
            pass


def _collect(runner, cmd_str, cwd=None, timeout=3.0):
    lines = []
    result = {}

    def on_output(run_id, line):
        lines.append(line)

    def on_exit(run_id, returncode):
        result["returncode"] = returncode

    runner.output_callback = on_output
    runner.exit_callback = on_exit
    handle = runner.start(cmd_str, cwd=cwd)

    deadline = time.time() + timeout
    while "returncode" not in result and time.time() < deadline:
        time.sleep(0.05)

    return handle, lines, result.get("returncode")


def test_start_returns_handle_with_run_id(runner):
    handle, _, _ = _collect(runner, "echo hi")
    assert handle.run_id
    assert isinstance(handle.run_id, str)


def test_output_lines_delivered_via_callback(runner):
    _, lines, _ = _collect(runner, "echo hello && echo world")
    assert "hello" in lines
    assert "world" in lines


def test_exit_callback_fires_with_zero_on_clean_exit(runner):
    _, _, returncode = _collect(runner, "true")
    assert returncode == 0


def test_exit_callback_fires_with_nonzero_on_failure(runner):
    _, _, returncode = _collect(runner, "false")
    assert returncode != 0


def test_handle_status_is_running_immediately_after_start(runner):
    from worktree_manager.command_runner import RunStatus
    handle = runner.start("sleep 60")
    assert handle.status == RunStatus.RUNNING
    runner.terminate(handle.run_id)


def test_handle_status_becomes_stopped_after_clean_exit(runner):
    from worktree_manager.command_runner import RunStatus
    handle, _, _ = _collect(runner, "true")
    assert handle.status == RunStatus.STOPPED


def test_handle_status_becomes_error_on_nonzero_exit(runner):
    from worktree_manager.command_runner import RunStatus
    handle, _, _ = _collect(runner, "false")
    assert handle.status == RunStatus.ERROR


def test_terminate_stops_long_running_process(runner):
    from worktree_manager.command_runner import RunStatus
    handle = runner.start("sleep 60")
    time.sleep(0.1)
    runner.terminate(handle.run_id)
    time.sleep(0.2)
    assert handle.status != RunStatus.RUNNING


def test_output_lines_stored_on_handle(runner):
    handle, _, _ = _collect(runner, "echo stored")
    assert "stored" in handle.output_lines


def test_output_buffer_rolls_at_5000_lines(runner):
    code = f"{sys.executable} -c \"for i in range(5100): print(i)\""
    handle, _, _ = _collect(runner, code, timeout=10.0)
    assert len(handle.output_lines) == 5000


def test_cwd_is_used_as_working_directory(runner, tmp_path):
    handle, lines, _ = _collect(runner, "pwd", cwd=str(tmp_path))
    assert str(tmp_path) in lines[0]


def test_stderr_merged_into_stdout(runner):
    _, lines, _ = _collect(runner, "echo err line >&2")
    assert any("err line" in l for l in lines)


def test_run_id_is_unique_across_starts(runner):
    h1 = runner.start("true")
    h2 = runner.start("true")
    assert h1.run_id != h2.run_id


def test_terminate_noop_for_already_exited_process(runner):
    handle, _, _ = _collect(runner, "true")
    runner.terminate(handle.run_id)  # should not raise


def test_get_handle_returns_none_for_unknown_id(runner):
    assert runner.get_handle("nonexistent-id") is None


def test_intentional_terminate_sets_status_stopped(runner):
    from worktree_manager.command_runner import RunStatus
    exited = {}

    def on_exit(run_id, returncode):
        exited["status"] = runner.get_handle(run_id).status

    runner.exit_callback = on_exit
    handle = runner.start("sleep 60")
    time.sleep(0.1)
    runner.terminate(handle.run_id, intentional=True)
    deadline = time.time() + 3
    while "status" not in exited and time.time() < deadline:
        time.sleep(0.05)
    assert exited["status"] == RunStatus.STOPPED


def test_unintentional_terminate_sets_status_error(runner):
    from worktree_manager.command_runner import RunStatus
    exited = {}

    def on_exit(run_id, returncode):
        exited["status"] = runner.get_handle(run_id).status

    runner.exit_callback = on_exit
    handle = runner.start("sleep 60")
    time.sleep(0.1)
    runner.terminate(handle.run_id, intentional=False)
    deadline = time.time() + 3
    while "status" not in exited and time.time() < deadline:
        time.sleep(0.05)
    assert exited["status"] == RunStatus.ERROR


def test_forget_removes_handle_and_proc(runner):
    handle = runner.start("sleep 60")
    time.sleep(0.1)
    runner.terminate(handle.run_id, intentional=True)
    runner.forget(handle.run_id)
    assert runner.get_handle(handle.run_id) is None
    assert handle.run_id not in runner._procs


def test_pipe_output_works(runner):
    _, lines, _ = _collect(runner, "echo hello | tr a-z A-Z")
    assert any("HELLO" in l for l in lines)


def test_subshell_expansion_works(runner):
    _, lines, _ = _collect(runner, "echo $(echo nested)")
    assert any("nested" in l for l in lines)


def test_command_string_stored_on_handle(runner):
    handle = runner.start("echo stored-cmd")
    time.sleep(0.2)
    assert handle.command == "echo stored-cmd"
