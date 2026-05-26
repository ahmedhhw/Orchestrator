from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit, QListWidget

from worktree_manager.spotlight.action_parser import ActionParser
from worktree_manager.spotlight.action_registry import (
    ActionRegistry, ActionSpec, ArgSlot,
)
from worktree_manager.ui.spotlight_overlay import SpotlightOverlay


def _make_overlay(qtbot, projects=("alpha", "beta", "gamma")):
    registry = ActionRegistry()
    registry.register(ActionSpec(
        name="open_project",
        keywords=["project"],
        slots=[ArgSlot(name="name", candidates=lambda prev, p=projects: list(p))],
        runner=lambda args: None,
    ))
    parser = ActionParser(registry)
    overlay = SpotlightOverlay(parser=parser)
    qtbot.addWidget(overlay)
    overlay.show()
    return overlay


def _list_items(overlay):
    lw = overlay.findChild(QListWidget)
    return [lw.item(i).text() for i in range(lw.count())]


def test_overlay_is_frameless(qtbot):
    registry = ActionRegistry()
    overlay = SpotlightOverlay(parser=ActionParser(registry))
    qtbot.addWidget(overlay)
    flags = overlay.windowFlags()
    assert bool(flags & Qt.FramelessWindowHint)


def test_overlay_has_lineedit_and_listwidget(qtbot):
    overlay = _make_overlay(qtbot)
    assert overlay.findChild(QLineEdit) is not None
    assert overlay.findChild(QListWidget) is not None


def test_overlay_shows_root_keywords_on_empty_input(qtbot):
    overlay = _make_overlay(qtbot)
    assert _list_items(overlay) == ["project"]


def test_typing_filters_suggestions_in_realtime(qtbot):
    overlay = _make_overlay(qtbot)
    edit = overlay.findChild(QLineEdit)
    edit.setText("project alp")
    assert _list_items(overlay) == ["alpha"]


def test_typing_with_no_match_shows_empty_list(qtbot):
    overlay = _make_overlay(qtbot)
    edit = overlay.findChild(QLineEdit)
    edit.setText("project zzz")
    assert _list_items(overlay) == []


def test_first_suggestion_is_highlighted_by_default(qtbot):
    overlay = _make_overlay(qtbot)
    edit = overlay.findChild(QLineEdit)
    edit.setText("project")
    lw = overlay.findChild(QListWidget)
    assert lw.currentRow() == 0


def test_down_arrow_moves_highlight(qtbot):
    overlay = _make_overlay(qtbot)
    edit = overlay.findChild(QLineEdit)
    edit.setText("project")
    qtbot.keyClick(edit, Qt.Key_Down)
    lw = overlay.findChild(QListWidget)
    assert lw.currentRow() == 1


def test_escape_hides_overlay(qtbot):
    overlay = _make_overlay(qtbot)
    edit = overlay.findChild(QLineEdit)
    qtbot.keyClick(edit, Qt.Key_Escape)
    assert not overlay.isVisible()


# ── Phase 0.4 tests ─────────────────────────────────────────────────────────

def test_enter_runs_action_with_highlighted_suggestion_as_arg(qtbot):
    calls = []
    registry = ActionRegistry()
    registry.register(ActionSpec(
        name="open_project",
        keywords=["project"],
        slots=[ArgSlot(name="name", candidates=lambda prev: ["alpha", "beta"])],
        runner=lambda args: calls.append(args),
    ))
    overlay = SpotlightOverlay(parser=ActionParser(registry))
    qtbot.addWidget(overlay)
    overlay.show()

    edit = overlay.findChild(QLineEdit)
    edit.setText("project ")  # trailing space — no ghost, shows both candidates
    qtbot.keyClick(edit, Qt.Key_Down)  # highlight "beta"
    qtbot.keyClick(edit, Qt.Key_Return)

    assert calls == [{"name": "beta"}]


def test_enter_hides_overlay_after_running(qtbot):
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
    edit = overlay.findChild(QLineEdit)
    edit.setText("project alpha")  # fully typed — no ghost
    qtbot.keyClick(edit, Qt.Key_Return)
    assert not overlay.isVisible()


def test_enter_with_empty_suggestion_list_is_noop(qtbot):
    calls = []
    registry = ActionRegistry()
    registry.register(ActionSpec(
        name="open_project",
        keywords=["project"],
        slots=[ArgSlot(name="name", candidates=lambda prev: ["alpha"])],
        runner=lambda args: calls.append(args),
    ))
    overlay = SpotlightOverlay(parser=ActionParser(registry))
    qtbot.addWidget(overlay)
    overlay.show()
    edit = overlay.findChild(QLineEdit)
    edit.setText("project zzz")
    qtbot.keyClick(edit, Qt.Key_Return)
    assert calls == []
    assert overlay.isVisible()


def test_enter_with_ghost_commits_only_does_not_execute(qtbot):
    # "pro" has ghost "ject "; Enter commits to "project " but does not execute —
    # the command still needs a slot argument.
    calls = []
    registry = ActionRegistry()
    registry.register(ActionSpec(
        name="open_project",
        keywords=["project"],
        slots=[ArgSlot(name="name", candidates=lambda prev: ["alpha"])],
        runner=lambda args: calls.append(args),
    ))
    overlay = SpotlightOverlay(parser=ActionParser(registry))
    qtbot.addWidget(overlay)
    overlay.show()
    edit = overlay.findChild(QLineEdit)
    edit.setText("pro")
    assert edit.ghost_text() == "ject"
    qtbot.keyClick(edit, Qt.Key_Return)
    assert edit.text() == "project"
    assert calls == []
    assert overlay.isVisible()


# ── Phase 1.4 tests ──────────────────────────────────────────────────────────

def test_enter_on_zero_arg_action_runs_with_empty_args(qtbot):
    calls = []
    registry = ActionRegistry()
    registry.register(ActionSpec(
        name="open_settings",
        keywords=["settings"],
        slots=[],
        runner=lambda args: calls.append(args),
    ))
    overlay = SpotlightOverlay(parser=ActionParser(registry))
    qtbot.addWidget(overlay)
    overlay.show()
    edit = overlay.findChild(QLineEdit)
    edit.setText("settings")
    qtbot.keyClick(edit, Qt.Key_Return)
    assert calls == [{}]


def test_enter_on_multi_keyword_chain_with_arg(qtbot):
    calls = []
    registry = ActionRegistry()
    registry.register(ActionSpec(
        name="edit_project",
        keywords=["edit", "project"],
        slots=[ArgSlot(name="name", candidates=lambda prev: ["alpha"])],
        runner=lambda args: calls.append(args),
    ))
    overlay = SpotlightOverlay(parser=ActionParser(registry))
    qtbot.addWidget(overlay)
    overlay.show()
    edit = overlay.findChild(QLineEdit)
    edit.setText("edit project alpha")
    qtbot.keyClick(edit, Qt.Key_Return)
    assert calls == [{"name": "alpha"}]


def test_enter_on_multi_slot_uses_committed_plus_highlighted(qtbot):
    calls = []
    registry = ActionRegistry()
    registry.register(ActionSpec(
        name="run_command",
        keywords=["command"],
        slots=[
            ArgSlot(name="repo", candidates=lambda prev: ["repoA"]),
            ArgSlot(name="worktree", candidates=lambda prev: ["wt1", "wt2"]),
            ArgSlot(name="cmd", candidates=lambda prev: ["runs"]),
        ],
        runner=lambda args: calls.append(args),
    ))
    overlay = SpotlightOverlay(parser=ActionParser(registry))
    qtbot.addWidget(overlay)
    overlay.show()
    edit = overlay.findChild(QLineEdit)
    edit.setText("command repoA wt2 runs")
    qtbot.keyClick(edit, Qt.Key_Return)
    assert calls == [{"repo": "repoA", "worktree": "wt2", "cmd": "runs"}]


# ── Phase 1.5 tests ──────────────────────────────────────────────────────────

def test_tab_commits_ghost_when_single_option(qtbot):
    # "pro" already has ghost "ject" from _refresh (single match).
    # First Tab commits that ghost; real input becomes "project".
    overlay = _make_overlay(qtbot)
    edit = overlay.findChild(QLineEdit)
    edit.setText("pro")
    assert edit.ghost_text() == "ject"   # auto-set by _refresh
    qtbot.keyClick(edit, Qt.Key_Tab)
    assert edit.text() == "project"
    assert edit.ghost_text() == ""


def test_tab_shows_ghost_for_common_prefix(qtbot):
    registry = ActionRegistry()
    registry.register(ActionSpec(name="run_server", keywords=["runserver"], slots=[]))
    registry.register(ActionSpec(name="run_tests", keywords=["runtests"], slots=[]))
    overlay = SpotlightOverlay(parser=ActionParser(registry))
    qtbot.addWidget(overlay)
    overlay.show()
    edit = overlay.findChild(QLineEdit)
    edit.setText("ru")
    qtbot.keyClick(edit, Qt.Key_Tab)
    # real input unchanged; ghost shows common prefix extension "n"
    assert edit.text() == "ru"
    assert edit.ghost_text() == "n"


def test_tab_cycles_ghost_when_no_common_prefix(qtbot):
    overlay = _make_overlay(qtbot, projects=("alpha", "beta"))
    edit = overlay.findChild(QLineEdit)
    edit.setText("project ")
    qtbot.keyClick(edit, Qt.Key_Tab)
    first_ghost = edit.ghost_text()
    assert first_ghost in ("alpha", "beta")
    assert edit.text() == "project "  # real input unchanged
    qtbot.keyClick(edit, Qt.Key_Tab)
    second_ghost = edit.ghost_text()
    assert {first_ghost, second_ghost} == {"alpha", "beta"}
    assert edit.text() == "project "


def test_tab_commits_ghost_then_enter_executes(qtbot):
    # "project a" already has ghost "lpha" from _refresh.
    # Tab commits ghost → "project alpha"; Enter executes.
    calls = []
    registry = ActionRegistry()
    registry.register(ActionSpec(
        name="open_project",
        keywords=["project"],
        slots=[ArgSlot(name="name", candidates=lambda prev: ["alpha"])],
        runner=lambda args: calls.append(args),
    ))
    overlay = SpotlightOverlay(parser=ActionParser(registry))
    qtbot.addWidget(overlay)
    overlay.show()
    edit = overlay.findChild(QLineEdit)
    edit.setText("project a")
    assert edit.ghost_text() == "lpha"   # auto-set by _refresh
    qtbot.keyClick(edit, Qt.Key_Tab)     # commits ghost
    assert edit.text() == "project alpha"
    assert edit.ghost_text() == ""
    assert calls == []
    qtbot.keyClick(edit, Qt.Key_Return)  # executes
    assert calls == [{"name": "alpha"}]
    assert not overlay.isVisible()


def test_tab_commits_ghost_for_non_final_slot_then_waits(qtbot):
    # "command rep" already has ghost "oA" from _refresh (single match, non-final slot).
    # Tab commits ghost → "command repoA"; still needs worktree slot.
    calls = []
    registry = ActionRegistry()
    registry.register(ActionSpec(
        name="run_command",
        keywords=["command"],
        slots=[
            ArgSlot(name="repo", candidates=lambda prev: ["repoA"]),
            ArgSlot(name="worktree", candidates=lambda prev: ["wt1"]),
        ],
        runner=lambda args: calls.append(args),
    ))
    overlay = SpotlightOverlay(parser=ActionParser(registry))
    qtbot.addWidget(overlay)
    overlay.show()
    edit = overlay.findChild(QLineEdit)
    edit.setText("command rep")
    assert edit.ghost_text() == "oA"    # auto-set by _refresh
    qtbot.keyClick(edit, Qt.Key_Tab)    # commits ghost
    assert edit.text() == "command repoA"
    assert calls == []   # not yet executable


def test_non_tab_key_does_not_commit_ghost(qtbot):
    overlay = _make_overlay(qtbot)
    edit = overlay.findChild(QLineEdit)
    edit.setText("pro")
    assert edit.ghost_text() == "ject"
    # typing any character should NOT commit the ghost — it types into the real input
    qtbot.keyClick(edit, Qt.Key_X)
    assert edit.ghost_text() == ""  # ghost is cleared (text changed, no longer valid)
    assert edit.text() == "prox"    # real input got the keystroke, ghost was not committed


def test_enter_without_ghost_on_incomplete_command_shows_error(qtbot):
    registry = ActionRegistry()
    registry.register(ActionSpec(
        name="open_project",
        keywords=["project"],
        slots=[ArgSlot(name="name", candidates=lambda prev: ["alpha", "beta"])],
        runner=lambda args: None,
    ))
    overlay = SpotlightOverlay(parser=ActionParser(registry))
    qtbot.addWidget(overlay)
    overlay.show()
    edit = overlay.findChild(QLineEdit)
    edit.setText("pro")  # partial keyword, no ghost because 2 candidates share prefix
    # Clear the ghost manually so there is definitely no ghost showing
    edit.set_ghost_text("")
    qtbot.keyClick(edit, Qt.Key_Return)
    assert overlay.isVisible()
    assert overlay.error_text() != ""


def test_enter_without_ghost_clears_error_on_next_keystroke(qtbot):
    registry = ActionRegistry()
    registry.register(ActionSpec(
        name="open_project",
        keywords=["project"],
        slots=[ArgSlot(name="name", candidates=lambda prev: ["alpha", "beta"])],
        runner=lambda args: None,
    ))
    overlay = SpotlightOverlay(parser=ActionParser(registry))
    qtbot.addWidget(overlay)
    overlay.show()
    edit = overlay.findChild(QLineEdit)
    edit.setText("pro")
    edit.set_ghost_text("")
    qtbot.keyClick(edit, Qt.Key_Return)
    assert overlay.error_text() != ""
    qtbot.keyClick(edit, Qt.Key_J)
    assert overlay.error_text() == ""


def test_ghost_text_shows_for_unique_prefix(qtbot):
    overlay = _make_overlay(qtbot)
    edit = overlay.findChild(QLineEdit)
    edit.setText("pro")
    assert edit.ghost_text() == "ject"


def test_ghost_text_empty_when_candidates_have_no_common_prefix(qtbot):
    registry = ActionRegistry()
    registry.register(ActionSpec(name="open_project", keywords=["project"], slots=[]))
    registry.register(ActionSpec(name="run_command", keywords=["command"], slots=[]))
    overlay = SpotlightOverlay(parser=ActionParser(registry))
    qtbot.addWidget(overlay)
    overlay.show()
    edit = overlay.findChild(QLineEdit)
    edit.setText("")
    assert edit.ghost_text() == ""


def test_ghost_text_empty_when_filter_has_no_match(qtbot):
    overlay = _make_overlay(qtbot)
    edit = overlay.findChild(QLineEdit)
    edit.setText("xyz")
    assert edit.ghost_text() == ""
