# Plan: Iteration 3 — Dropdown + worktree-switch bug fixes (Reviewed-mode TDD)

Context: [autobot-ui-fixes-ctx-iter-3-dropdown-switch-fix-2026-06-10.md](autobot-ui-fixes-ctx-iter-3-dropdown-switch-fix-2026-06-10.md)

This plan fixes two coupled bugs:
- **Bug A** — `FilterableComboBox`: committing a completer match must always emit exactly one `currentIndexChanged`, even when filtering already moved `currentIndex` to the target under `blockSignals`.
- **Bug B** — `CommandCenterPanel._change_worktree`: switching a worktree must yield exactly one pane (a re-entry guard prevents duplicates), and a failed relaunch must surface/log instead of being silently swallowed.

Each phase is independently testable, follows strict TDD (a failing test precedes its production code), and uses behavioural test names with no phase/iteration numbers.

---

### Phase 3.1 — Track the index before edit begins
**What it covers:** `FilterableComboBox` records the `currentIndex` at the first filter keystroke so a later commit can tell a real value change from a no-op.
**Files touched:**
- [worktree_manager/ui/filterable_combo.py](worktree_manager/ui/filterable_combo.py) — add `_index_before_edit`, set it in `_on_text_edited`.

**Tests (Red):**
```python
import pytest
from PySide6.QtWidgets import QComboBox

from worktree_manager.ui.filterable_combo import FilterableComboBox


@pytest.fixture
def combo(qtbot):
    c = FilterableComboBox()
    c.addItems(["feature/login", "feature/search", "refactor/flags", "main"])
    qtbot.addWidget(c)
    return c


def test_first_filter_keystroke_records_the_starting_index(qtbot, combo):
    combo.setCurrentIndex(2)
    combo.lineEdit().textEdited.emit("fea")
    assert combo._index_before_edit == 2


def test_index_before_edit_is_not_overwritten_by_later_keystrokes(qtbot, combo):
    combo.setCurrentIndex(3)
    combo.lineEdit().textEdited.emit("f")
    combo.lineEdit().textEdited.emit("fe")
    combo.lineEdit().textEdited.emit("fea")
    assert combo._index_before_edit == 3
```

**Production code (Green):**
```python
def __init__(self, parent=None):
    super().__init__(parent)
    self._committed_index = 0
    self._in_edit = False
    self._index_before_edit = 0

    self.setEditable(True)
    self.setInsertPolicy(QComboBox.NoInsert)

    comp = QCompleter(self.model(), self)
    comp.setFilterMode(Qt.MatchContains)
    comp.setCaseSensitivity(Qt.CaseInsensitive)
    comp.setCompletionMode(QCompleter.PopupCompletion)
    self.setCompleter(comp)

    comp.activated[str].connect(self._commit_from_completer)
    self.lineEdit().textEdited.connect(self._on_text_edited)
    self.lineEdit().editingFinished.connect(self._on_editing_finished)

def _on_text_edited(self, _text):
    if not self._in_edit:
        self._in_edit = True
        self._index_before_edit = self.currentIndex()
        self.blockSignals(True)
```

**Done when:** The two tests pass; `_index_before_edit` holds the index captured at the first keystroke of an edit and is stable across subsequent keystrokes within the same edit.

---

### Phase 3.2 — Committing a completer match emits even when the index already moved
**What it covers:** `_commit_from_completer` re-emits `currentIndexChanged` exactly once when filtering already advanced `currentIndex` to the committed item under `blockSignals`, while still emitting once on the normal path and never on the unchanged item.
**Files touched:**
- [worktree_manager/ui/filterable_combo.py](worktree_manager/ui/filterable_combo.py) — rework `_commit_from_completer` to re-emit the lost signal.

**Tests (Red):**
```python
import pytest
from PySide6.QtWidgets import QComboBox

from worktree_manager.ui.filterable_combo import FilterableComboBox


@pytest.fixture
def combo(qtbot):
    c = FilterableComboBox()
    c.addItems(["feature/login", "feature/search", "refactor/flags", "main"])
    qtbot.addWidget(c)
    return c


def test_committing_a_match_after_the_index_moved_emits_once(qtbot, combo):
    # Simulate filtering having advanced the index to the target under blockSignals.
    combo.setCurrentIndex(0)
    combo.lineEdit().textEdited.emit("search")   # _index_before_edit = 0, signals blocked
    fired = []
    combo.currentIndexChanged.connect(lambda i: fired.append(i))
    super(FilterableComboBox, combo).setCurrentIndex(1)  # index moves while signals blocked
    combo._commit_from_completer("feature/search")
    assert fired == [1]
    assert combo.currentIndex() == 1


def test_committing_a_match_on_the_normal_path_emits_once(qtbot, combo):
    combo.setCurrentIndex(0)
    combo.lineEdit().textEdited.emit("search")
    fired = []
    combo.currentIndexChanged.connect(lambda i: fired.append(i))
    combo._commit_from_completer("feature/search")
    assert fired == [1]
    assert combo.currentIndex() == 1


def test_committing_the_already_selected_item_emits_nothing(qtbot, combo):
    combo.setCurrentIndex(1)
    combo.lineEdit().textEdited.emit("search")   # _index_before_edit = 1
    fired = []
    combo.currentIndexChanged.connect(lambda i: fired.append(i))
    combo._commit_from_completer("feature/search")
    assert fired == []
    assert combo.currentIndex() == 1


def test_typing_filter_text_without_committing_emits_nothing(qtbot, combo):
    combo.setCurrentIndex(0)
    fired = []
    combo.currentIndexChanged.connect(lambda i: fired.append(i))
    combo.lineEdit().textEdited.emit(" refac")
    assert fired == []
```

**Production code (Green):**
```python
def _commit_from_completer(self, text):
    idx = self.findText(text, Qt.MatchExactly)
    before = self._index_before_edit
    self._end_edit()
    if idx >= 0:
        self._committed_index = idx
        if self.currentIndex() == idx:
            # Index already moved to the target while signals were blocked, so
            # the change signal was lost; re-emit it once — but only if this is
            # a real change from where the edit started.
            if idx != before:
                self.currentIndexChanged.emit(idx)
        else:
            self.setCurrentIndex(idx)
```

**Done when:** All four tests pass: a committed match emits exactly once whether or not the index already moved; committing the unchanged item emits nothing; raw filter keystrokes emit nothing.

---

### Phase 3.3 — Guard `_change_worktree` against re-entry so a switch yields one pane
**What it covers:** `CommandCenterPanel._change_worktree` removes the old pane and relaunches exactly once, and a concurrent re-entry for the same run is ignored.
**Files touched:**
- [worktree_manager/ui/command_center_panel.py](worktree_manager/ui/command_center_panel.py) — add `_switching` set in `__init__`; add the re-entry guard in `_change_worktree`.

**Tests (Red):**
```python
from unittest.mock import MagicMock

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
```

**Production code (Green):**
```python
def __init__(self, parent, vm, on_close, on_nickname=None):
    super().__init__(parent)
    self._vm = vm
    self._on_close = on_close
    self._on_nickname = on_nickname
    self._panes: dict[str, CommandPane] = {}
    self._pane_shown: dict[str, bool] = {}
    self._popouts: dict[str, object] = {}
    self._maximized_id: str | None = None
    self._switching: set[str] = set()

    self._bridge = _VMBridge()
    self._bridge.run_added.connect(self.add_pane)
    self._bridge.output_received.connect(self.route_output)
    self._bridge.status_changed.connect(self.route_status)
    self._bridge.run_id_changed.connect(self._on_run_id_changed)

    self._build()
    self._wire_vm()
    self._restore_existing_runs()

def _change_worktree(self, handle: RunHandle, new_worktree_path: str) -> None:
    run_id = handle.run_id
    if run_id in self._switching:
        return
    self._switching.add(run_id)
    try:
        self.remove_pane(run_id)
        self._vm.launch(
            repo_path=handle.repo_path,
            repo_name=handle.repo_name,
            cmd_name=handle.cmd_name,
            command_str=handle.command,
            worktree_path=new_worktree_path,
        )
    finally:
        self._switching.discard(run_id)
```

**Done when:** All three tests pass: a single switch calls `vm.launch` once with the new worktree path; a re-entry during the launch is ignored; and a fresh switch after the first completes is allowed (the guard is cleared in `finally`).

---

### Phase 3.4 — A failed relaunch surfaces instead of being silently swallowed
**What it covers:** `_change_worktree` replaces the silent `except Exception: pass` with explicit handling — a `DuplicateRunError` is logged (not swallowed) and any other launch error propagates.
**Files touched:**
- [worktree_manager/ui/command_center_panel.py](worktree_manager/ui/command_center_panel.py) — import `DuplicateRunError` and `logging`; catch and log the duplicate, let other exceptions propagate.

**Tests (Red):**
```python
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
```

**Production code (Green):**
```python
import logging

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout,
    QWidget,
)

from worktree_manager.command_center_vm import DuplicateRunError
from worktree_manager.command_runner import RunHandle, RunStatus
from worktree_manager.ui.command_pane import CommandPane
from worktree_manager.ui.launch_dialog import LaunchDialog
```
```python
def _change_worktree(self, handle: RunHandle, new_worktree_path: str) -> None:
    run_id = handle.run_id
    if run_id in self._switching:
        return
    self._switching.add(run_id)
    try:
        self.remove_pane(run_id)
        self._vm.launch(
            repo_path=handle.repo_path,
            repo_name=handle.repo_name,
            cmd_name=handle.cmd_name,
            command_str=handle.command,
            worktree_path=new_worktree_path,
        )
    except DuplicateRunError:
        logging.warning(
            "worktree switch: run already exists for %s", new_worktree_path
        )
    finally:
        self._switching.discard(run_id)
```

**Done when:** Both tests pass: a `DuplicateRunError` produces a `WARNING` log mentioning the new worktree path (and is not re-raised), any other launch error propagates to the caller, and `_switching` is cleared in both cases.

---

## Reference link audit

All existing files, classes, and functions referenced in this plan, with links relative to this plan file's directory (`worktree-manager/`):

- [worktree_manager/ui/filterable_combo.py](worktree_manager/ui/filterable_combo.py) — `FilterableComboBox`, `__init__`, `_on_text_edited`, `_commit_from_completer`, `_end_edit`, `setCurrentIndex`.
- [worktree_manager/ui/command_center_panel.py](worktree_manager/ui/command_center_panel.py) — `CommandCenterPanel`, `__init__`, `_change_worktree`, `add_pane`, `remove_pane`, `pane_count`.
- [worktree_manager/command_center_vm.py](worktree_manager/command_center_vm.py) — `DuplicateRunError`, `CommandCenterViewModel.launch`.
- [worktree_manager/command_runner.py](worktree_manager/command_runner.py) — `RunHandle`, `RunStatus`.
- [worktree_manager/ui/command_pane.py](worktree_manager/ui/command_pane.py) — `CommandPane` (referenced via `_panes`).

New test files (unlinked, created during implementation): `tests/test_filterable_combo_iter3_qt.py`, `tests/test_command_center_worktree_switch_qt.py`.
