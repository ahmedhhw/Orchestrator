"""
Tests that dialogs do not open at hard-coded fixed pixel dimensions.
A dialog with resize(W, H) will report exactly that geometry after construction.
After removing resize(), Qt sizes to content and the dimensions differ.
"""
import time
from unittest.mock import MagicMock

from worktree_manager.command_runner import RunHandle, RunStatus
from worktree_manager.models import (
    CleanupCandidate, SavedCommand, WorkspaceEntry, WorkspaceProject, WorktreeModel,
)
from worktree_manager.spotlight.action_parser import ActionParser
from worktree_manager.spotlight.action_registry import ActionRegistry, ActionSpec, ArgSlot
from worktree_manager.ui.cleanup_wizard import CleanupWizard
from worktree_manager.ui.command_popout import CommandPopout
from worktree_manager.ui.launch_dialog import LaunchDialog
from worktree_manager.ui.manage_commands_dialog import ManageCommandsDialog
from worktree_manager.ui.manage_nicknames_dialog import ManageNicknamesDialog
from worktree_manager.ui.project_operations_dialog import ProjectOperationsDialog
from worktree_manager.ui.quick_launch_dialog import QuickLaunchDialog
from worktree_manager.ui.spotlight_overlay import SpotlightOverlay
from worktree_manager.spotlight.nickname_store import NicknameStore


# ── helpers ──────────────────────────────────────────────────────────────────

def _wt(path="/r/proj", branch="main", is_main=True):
    return WorktreeModel(
        path=path, branch=branch, is_main=is_main,
        last_commit_ts=int(time.time()), is_merged=False, is_stale=False,
    )


def _cc(branch="feat"):
    return CleanupCandidate(
        branch=branch, path=f"/r/{branch}",
        is_merged=False, is_stale=False, is_protected=False,
        has_uncommitted=False, is_checked_out=False,
        merged_into=None, last_commit_ts=int(time.time()),
    )


class _FakeConfigStore:
    def __init__(self):
        self._prefs: dict = {}

    def get_ui_pref(self, key, default=None):
        return self._prefs.get(key, default)

    def set_ui_pref(self, key, value) -> None:
        self._prefs[key] = value


# ── launch dialog: was resize(440, 520) ──────────────────────────────────────

def test_launch_dialog_not_fixed_440x520(qtbot):
    vm = MagicMock()
    vm.all_repos.return_value = {"/repos/proj": MagicMock()}
    vm.get_last_used_repo.return_value = "/repos/proj"
    vm.saved_commands.return_value = [SavedCommand(name="build", command="make")]
    vm.list_worktrees.return_value = [_wt()]
    vm.find_existing_run.return_value = None
    dlg = LaunchDialog(parent=None, vm=vm)
    qtbot.addWidget(dlg)
    assert not (dlg.width() == 440 and dlg.height() == 520)


# ── cleanup wizard: was resize(520, 520) ─────────────────────────────────────

def test_cleanup_wizard_not_fixed_520x520(qtbot):
    dlg = CleanupWizard(parent=None, candidates=[_cc()],
                        on_delete_selected=lambda _: None)
    qtbot.addWidget(dlg)
    assert not (dlg.width() == 520 and dlg.height() == 520)


# ── spotlight overlay: was resize(520, 320) ───────────────────────────────────

def test_spotlight_overlay_has_minimum_size_not_fixed_size(qtbot):
    registry = ActionRegistry()
    registry.register(ActionSpec(
        name="open_project",
        keywords=["project"],
        slots=[ArgSlot(name="name", candidates=lambda prev: ["alpha"])],
        runner=lambda args: None,
    ))
    overlay = SpotlightOverlay(parser=ActionParser(registry))
    qtbot.addWidget(overlay)
    overlay.show()
    # Must have a meaningful minimum size so it isn't tiny
    assert overlay.minimumWidth() >= 500
    assert overlay.minimumHeight() >= 300
    # Must not be pinned (setFixedSize would make min==max at a small QWIDGETSIZE_MAX)
    from PySide6.QtWidgets import QSizePolicy
    assert overlay.maximumWidth() > overlay.minimumWidth() or overlay.maximumWidth() >= 16777215


# ── manage commands dialog: was resize(520, 480) ──────────────────────────────

def test_manage_commands_dialog_not_fixed_520x480(qtbot):
    vm = MagicMock()
    vm.all_repos.return_value = {"/repos/proj": MagicMock()}
    vm.get_last_used_repo.return_value = "/repos/proj"
    vm.saved_commands.return_value = [SavedCommand(name="build", command="make")]
    dlg = ManageCommandsDialog(parent=None, vm=vm)
    qtbot.addWidget(dlg)
    assert not (dlg.width() == 520 and dlg.height() == 480)


# ── manage nicknames dialog: was resize(480, 360) ─────────────────────────────

def test_manage_nicknames_dialog_not_fixed_480x360(qtbot):
    store = NicknameStore(_FakeConfigStore())
    dlg = ManageNicknamesDialog(parent=None, nickname_store=store)
    qtbot.addWidget(dlg)
    assert not (dlg.width() == 480 and dlg.height() == 360)


# ── project operations dialog: was resize(460, 460) ───────────────────────────

def test_project_operations_dialog_not_fixed_460x460(qtbot):
    vm = MagicMock()
    vm.list_worktrees_for_repo.return_value = [_wt()]
    dlg = ProjectOperationsDialog(
        parent=None, vm=vm,
        repos={"/repos/proj": MagicMock()},
        on_create=lambda name, entries: None,
    )
    qtbot.addWidget(dlg)
    assert not (dlg.width() == 460 and dlg.height() == 460)


# ── quick launch dialog: was resize(460, 140) ─────────────────────────────────

def test_quick_launch_dialog_not_fixed_460x140(qtbot):
    dlg = QuickLaunchDialog(
        parent=None,
        worktree_path="/repos/proj-wt/feat",
        on_run=lambda cmd: None,
    )
    qtbot.addWidget(dlg)
    assert not (dlg.width() == 460 and dlg.height() == 140)


# ── command popout: was resize(900, 600) ──────────────────────────────────────

def test_command_popout_not_fixed_900x600(qtbot):
    handle = RunHandle(
        run_id="r1", cmd_name="build", repo_path="/r/proj",
        repo_name="proj", worktree_path="/r/proj-wt/main",
        command=["make"], status=RunStatus.RUNNING,
    )
    dlg = CommandPopout(
        parent=None, handle=handle,
        on_stop=lambda: None,
        on_restart=lambda: None,
        on_remove=lambda: None,
    )
    qtbot.addWidget(dlg)
    assert not (dlg.width() == 900 and dlg.height() == 600)
