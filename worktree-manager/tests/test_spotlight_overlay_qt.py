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
        slots=[ArgSlot(name="name", candidates=lambda p=projects: list(p))],
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
        slots=[ArgSlot(name="name", candidates=lambda: ["alpha", "beta"])],
        runner=lambda args: calls.append(args),
    ))
    overlay = SpotlightOverlay(parser=ActionParser(registry))
    qtbot.addWidget(overlay)
    overlay.show()

    edit = overlay.findChild(QLineEdit)
    edit.setText("project")
    qtbot.keyClick(edit, Qt.Key_Down)  # highlight "beta"
    qtbot.keyClick(edit, Qt.Key_Return)

    assert calls == [{"name": "beta"}]


def test_enter_hides_overlay_after_running(qtbot):
    registry = ActionRegistry()
    registry.register(ActionSpec(
        name="open_project",
        keywords=["project"],
        slots=[ArgSlot(name="name", candidates=lambda: ["alpha"])],
        runner=lambda args: None,
    ))
    overlay = SpotlightOverlay(parser=ActionParser(registry))
    qtbot.addWidget(overlay)
    overlay.show()
    edit = overlay.findChild(QLineEdit)
    edit.setText("project")
    qtbot.keyClick(edit, Qt.Key_Return)
    assert not overlay.isVisible()


def test_enter_with_empty_suggestion_list_is_noop(qtbot):
    calls = []
    registry = ActionRegistry()
    registry.register(ActionSpec(
        name="open_project",
        keywords=["project"],
        slots=[ArgSlot(name="name", candidates=lambda: ["alpha"])],
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


def test_enter_on_root_keyword_match_does_not_run_action(qtbot):
    calls = []
    registry = ActionRegistry()
    registry.register(ActionSpec(
        name="open_project",
        keywords=["project"],
        slots=[ArgSlot(name="name", candidates=lambda: ["alpha"])],
        runner=lambda args: calls.append(args),
    ))
    overlay = SpotlightOverlay(parser=ActionParser(registry))
    qtbot.addWidget(overlay)
    overlay.show()
    edit = overlay.findChild(QLineEdit)
    edit.setText("pro")  # still filtering keyword, not slot
    qtbot.keyClick(edit, Qt.Key_Return)
    assert calls == []
