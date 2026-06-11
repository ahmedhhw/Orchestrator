"""Phase 3.3/3.4 — CommandCenterPanel._change_worktree re-entry guard and error surfacing."""
import logging
from unittest.mock import MagicMock

import pytest

from worktree_manager.command_center_vm import DuplicateRunError
from worktree_manager.command_runner import RunHandle, RunStatus
from worktree_manager.ui.command_center_panel import CommandCenterPanel


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
    vm._run_meta = {}
    return vm


def _panel(qtbot, vm=None):
    p = CommandCenterPanel(parent=None, vm=vm or _vm(), on_close=lambda: None)
    qtbot.addWidget(p)
    return p


def test_switching_a_worktree_leaves_exactly_one_pane(qtbot):
    vm = _vm()
    p = _panel(qtbot, vm=vm)
    h = _handle()
    p.add_pane(h)
    assert p.pane_count() == 1
    p._change_worktree(h, "/r/proj/feature")
    vm.launch.assert_called_once()
    _, kwargs = vm.launch.call_args
    assert kwargs["worktree_path"] == "/r/proj/feature"
    assert p.pane_count() == 0  # relaunch re-adds via on_run_added, which the mock vm does not call


def test_a_concurrent_switch_for_the_same_run_is_ignored(qtbot):
    vm = _vm()
    p = _panel(qtbot, vm=vm)
    h = _handle()
    p.add_pane(h)

    # When launch is invoked, re-enter the switch for the same run mid-flight.
    def reenter(**kwargs):
        p._change_worktree(h, "/r/proj/other")
    vm.launch.side_effect = reenter

    p._change_worktree(h, "/r/proj/feature")
    # The nested re-entry must be guarded out, so launch fires exactly once.
    vm.launch.assert_called_once()
    _, kwargs = vm.launch.call_args
    assert kwargs["worktree_path"] == "/r/proj/feature"


def test_a_fresh_switch_after_one_completes_is_allowed(qtbot):
    vm = _vm()
    p = _panel(qtbot, vm=vm)
    h = _handle()
    p.add_pane(h)
    p._change_worktree(h, "/r/proj/feature")
    p.add_pane(h)  # simulate the relaunched pane being re-added
    p._change_worktree(h, "/r/proj/second")
    assert vm.launch.call_count == 2


# --- Phase 3.4: error surfacing ---

def test_a_duplicate_run_on_switch_is_logged_not_swallowed(qtbot, caplog):
    vm = _vm()
    vm.launch.side_effect = DuplicateRunError("dup-id")
    p = _panel(qtbot, vm=vm)
    h = _handle()
    p.add_pane(h)
    with caplog.at_level(logging.WARNING):
        p._change_worktree(h, "/r/proj/feature")
    assert any("/r/proj/feature" in rec.getMessage() for rec in caplog.records)
    # The guard is cleared even though the duplicate was raised.
    assert "r1" not in p._switching


def test_an_unexpected_launch_error_on_switch_propagates(qtbot):
    vm = _vm()
    vm.launch.side_effect = RuntimeError("boom")
    p = _panel(qtbot, vm=vm)
    h = _handle()
    p.add_pane(h)
    with pytest.raises(RuntimeError, match="boom"):
        p._change_worktree(h, "/r/proj/feature")
    # The guard is still cleared via finally so the run is not stuck.
    assert "r1" not in p._switching
