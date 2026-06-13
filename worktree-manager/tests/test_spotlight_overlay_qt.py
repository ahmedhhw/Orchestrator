from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QLineEdit, QListWidget

from worktree_manager.spotlight.action_parser import ActionParser
from worktree_manager.spotlight.action_registry import (
    ActionRegistry, ActionSpec, ArgSlot,
)
from worktree_manager.spotlight.nickname_store import NicknameEntry, NicknameStore
from worktree_manager.ui.spotlight_overlay import SpotlightOverlay


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeNicknameStore:
    """Minimal in-memory NicknameStore for tests."""

    def __init__(self, entries: dict[str, NicknameEntry] | None = None):
        self._entries: dict[str, NicknameEntry] = entries or {}

    def all(self) -> dict[str, NicknameEntry]:
        return dict(self._entries)

    def get(self, nickname: str) -> NicknameEntry | None:
        return self._entries.get(nickname)

    def save(self, entry: NicknameEntry) -> None:
        self._entries[entry.nickname] = entry

    def delete(self, nickname: str) -> None:
        self._entries.pop(nickname, None)


def _make_overlay(
    qtbot,
    projects=("alpha", "beta", "gamma"),
    mru_labels: list[str] | None = None,
    nickname_store: _FakeNicknameStore | None = None,
    on_action_executed=None,
):
    registry = ActionRegistry()
    registry.register(ActionSpec(
        name="open_project",
        keywords=["project"],
        slots=[ArgSlot(name="name", candidates=lambda prev, p=projects: list(p))],
        runner=lambda args: None,
    ))
    parser = ActionParser(
        registry,
        nickname_store=nickname_store,
        mru_labels=mru_labels or [],
    )
    overlay = SpotlightOverlay(
        parser=parser,
        on_action_executed=on_action_executed,
    )
    qtbot.addWidget(overlay)
    overlay.show()
    return overlay


def _list_items(overlay):
    lw = overlay.findChild(QListWidget)
    return [lw.item(i).text() for i in range(lw.count())]


def _caption_text(overlay) -> str:
    """Return the visible caption label text, or '' if hidden."""
    label = overlay.findChild(QLabel, "caption_label")
    if label is None or label.isHidden():
        return ""
    return label.text()


# ---------------------------------------------------------------------------
# Baseline structural tests (always kept)
# ---------------------------------------------------------------------------

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
    # "alp" uniquely matches "alpha" — auto-commit fires, field becomes "project alpha "
    # and the slot is now committed so the suggestion list is empty.
    edit.setText("project alp")
    assert edit.text() == "project alpha "
    assert _list_items(overlay) == []


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


# ---------------------------------------------------------------------------
# Phase 0.4 survivors (re-expressed for new model — no ghost)
# ---------------------------------------------------------------------------

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
    # New model: trailing space means slot committed; Enter executes.
    edit.setText("project beta ")  # all committed
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
    # New model: trailing space means slot is committed; one Enter executes.
    edit.setText("project alpha ")
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
    # New model: trailing space means slot committed; Enter executes.
    edit.setText("edit project alpha ")
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
    # New model: trailing space means all slots committed; Enter executes.
    edit.setText("command repoA wt2 runs ")
    qtbot.keyClick(edit, Qt.Key_Return)
    assert calls == [{"repo": "repoA", "worktree": "wt2", "cmd": "runs"}]


# ---------------------------------------------------------------------------
# New Iteration-0 tests
# ---------------------------------------------------------------------------

def test_empty_input_shows_mru_then_keywords_row0_highlighted_caption_commands(qtbot):
    """Shows MRU labels then root keywords on empty input; row 0 highlighted; caption COMMANDS."""
    overlay = _make_overlay(qtbot, mru_labels=["my-alias"])
    lw = overlay.findChild(QListWidget)
    items = _list_items(overlay)
    assert items == ["my-alias", "project"]
    assert lw.currentRow() == 0
    assert _caption_text(overlay) == "COMMANDS"


def test_typing_filters_active_token_line_edit_text_unchanged(qtbot):
    """Typing that matches multiple candidates narrows the list without auto-commit;
    typing that matches exactly one candidate auto-commits to the full token + space."""
    overlay = _make_overlay(qtbot)
    edit = overlay.findChild(QLineEdit)
    # "project b" matches "beta" uniquely — auto-commits to "project beta "
    edit.setText("project b")
    assert edit.text() == "project beta "
    assert _list_items(overlay) == []


def test_up_down_moves_highlight_does_not_change_text(qtbot):
    """Up/Down move the list highlight; the line-edit text is never changed."""
    overlay = _make_overlay(qtbot)
    edit = overlay.findChild(QLineEdit)
    edit.setText("project ")
    lw = overlay.findChild(QListWidget)
    initial_text = edit.text()
    qtbot.keyClick(edit, Qt.Key_Down)
    assert lw.currentRow() == 1
    assert edit.text() == initial_text
    qtbot.keyClick(edit, Qt.Key_Up)
    assert lw.currentRow() == 0
    assert edit.text() == initial_text


def test_enter_on_keyword_row_commits_plain_text_with_trailing_space(qtbot):
    """Enter on a highlighted keyword row appends it (+ space) as plain text and advances the list."""
    overlay = _make_overlay(qtbot)
    edit = overlay.findChild(QLineEdit)
    # Start at root — "project" is highlighted
    qtbot.keyClick(edit, Qt.Key_Return)
    # After commit the edit should have "project " and list should show slot candidates
    assert edit.text() == "project "
    items = _list_items(overlay)
    assert items == ["alpha", "beta", "gamma"]


def test_enter_walks_every_slot_then_executes(qtbot):
    """Enter on each slot commits it; after the last slot Enter executes and closes."""
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

    # commit keyword
    qtbot.keyClick(edit, Qt.Key_Return)
    assert edit.text() == "command "
    # commit repo slot (row 0 = "repoA")
    qtbot.keyClick(edit, Qt.Key_Return)
    assert edit.text() == "command repoA "
    # commit worktree slot (row 0 = "wt1")
    qtbot.keyClick(edit, Qt.Key_Return)
    assert edit.text() == "command repoA wt1 "
    # one more Enter executes
    qtbot.keyClick(edit, Qt.Key_Return)
    assert calls == [{"repo": "repoA", "worktree": "wt1"}]
    assert not overlay.isVisible()


def test_enter_on_complete_zero_slot_keyword_executes_and_hides(qtbot):
    """Enter on a fully-typed zero-slot keyword executes and hides the overlay."""
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
    # commit keyword row first
    qtbot.keyClick(edit, Qt.Key_Return)  # commits "settings "
    # now the command is executable (slot_index == len(slots) == 0, executable)
    qtbot.keyClick(edit, Qt.Key_Return)
    assert calls == [{}]
    assert not overlay.isVisible()


def test_enter_on_exact_nickname_runs_stored_action_and_hides(qtbot):
    """Enter on an exact nickname runs the stored action with stored args and closes (the bug fix)."""
    calls = []
    ns = _FakeNicknameStore({
        "myalias": NicknameEntry(
            nickname="myalias",
            action_name="open_project",
            args={"name": "alpha"},
        )
    })
    registry = ActionRegistry()
    registry.register(ActionSpec(
        name="open_project",
        keywords=["project"],
        slots=[ArgSlot(name="name", candidates=lambda prev: ["alpha"])],
        runner=lambda args: calls.append(args),
    ))
    parser = ActionParser(registry, nickname_store=ns)
    overlay = SpotlightOverlay(parser=parser)
    qtbot.addWidget(overlay)
    overlay.show()

    edit = overlay.findChild(QLineEdit)
    edit.setText("myalias")
    qtbot.keyClick(edit, Qt.Key_Return)

    assert calls == [{"name": "alpha"}]
    assert not overlay.isVisible()


def test_enter_on_nickname_row_selected_from_partial_input_runs_action(qtbot):
    """Selecting a nickname row from partial typed text (not an exact match) and pressing Enter
    must execute the nickname, not commit it with a trailing space and then fail."""
    calls = []
    ns = _FakeNicknameStore({
        "projo1": NicknameEntry(
            nickname="projo1",
            action_name="open_project",
            args={"name": "dev-tools"},
        )
    })
    registry = ActionRegistry()
    registry.register(ActionSpec(
        name="open_project",
        keywords=["project"],
        slots=[ArgSlot(name="name", candidates=lambda prev: ["dev-tools"])],
        runner=lambda args: calls.append(args),
    ))
    parser = ActionParser(registry, nickname_store=ns)
    overlay = SpotlightOverlay(parser=parser)
    qtbot.addWidget(overlay)
    overlay.show()

    edit = overlay.findChild(QLineEdit)
    edit.setText("proj")  # partial — projo1 appears as a suggestion but is not an exact match
    lw = overlay.findChild(QListWidget)
    # Find and select the projo1 row
    rows = [lw.item(i).text() for i in range(lw.count())]
    idx = rows.index("projo1")
    lw.setCurrentRow(idx)
    qtbot.keyClick(edit, Qt.Key_Return)

    assert calls == [{"name": "dev-tools"}]
    assert not overlay.isVisible()


def test_single_click_on_exact_nickname_runs_stored_action_and_hides(qtbot):
    """Single click on a nickname row runs the stored action — clicking must not append a trailing space."""
    calls = []
    ns = _FakeNicknameStore({
        "myalias": NicknameEntry(
            nickname="myalias",
            action_name="open_project",
            args={"name": "alpha"},
        )
    })
    registry = ActionRegistry()
    registry.register(ActionSpec(
        name="open_project",
        keywords=["project"],
        slots=[ArgSlot(name="name", candidates=lambda prev: ["alpha"])],
        runner=lambda args: calls.append(args),
    ))
    parser = ActionParser(registry, nickname_store=ns)
    overlay = SpotlightOverlay(parser=parser)
    qtbot.addWidget(overlay)
    overlay.show()

    edit = overlay.findChild(QLineEdit)
    edit.setText("myalias")
    lw = overlay.findChild(QListWidget)
    lw.itemClicked.emit(lw.item(0))

    assert calls == [{"name": "alpha"}]
    assert not overlay.isVisible()


def test_single_click_commits_like_enter(qtbot):
    """A single click on a list row commits it exactly like pressing Enter on that row."""
    overlay = _make_overlay(qtbot)
    edit = overlay.findChild(QLineEdit)
    lw = overlay.findChild(QListWidget)

    # At root: list has ["project"]; click it
    item = lw.item(0)
    lw.itemClicked.emit(item)

    assert edit.text() == "project "
    assert _list_items(overlay) == ["alpha", "beta", "gamma"]


def test_single_click_on_completing_row_executes(qtbot):
    """A single click on a row that completes the command executes and hides the overlay."""
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
    edit.setText("project ")
    lw = overlay.findChild(QListWidget)
    # Only "alpha" in list; clicking it should execute
    item = lw.item(0)
    lw.itemClicked.emit(item)

    assert calls == [{"name": "alpha"}]
    assert not overlay.isVisible()


def test_enter_on_unmatched_text_flags_invalid_keeps_text_shows_error(qtbot):
    """Enter on free-typed text with no list match: invalid border, text kept, nothing runs."""
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
    assert edit.text() == "project zzz"
    assert overlay.error_text() != ""
    assert edit.property("invalid") == True


def test_typing_after_error_clears_error(qtbot):
    """Typing any character after an invalid-flag error clears the error and invalid state."""
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
    edit.setText("project zzz")
    qtbot.keyClick(edit, Qt.Key_Return)
    assert overlay.error_text() != ""

    # Type a character — this should clear the error
    qtbot.keyClick(edit, Qt.Key_Backspace)
    assert overlay.error_text() == ""
    assert edit.property("invalid") != True


def test_tab_does_nothing(qtbot):
    """Tab key press does not commit, cycle, or change the line-edit text."""
    overlay = _make_overlay(qtbot)
    edit = overlay.findChild(QLineEdit)
    # "project a" matches alpha and gamma — ambiguous, no auto-commit fires.
    edit.setText("project a")
    lw = overlay.findChild(QListWidget)
    row_before = lw.currentRow()
    qtbot.keyClick(edit, Qt.Key_Tab)
    assert edit.text() == "project a"
    assert lw.currentRow() == row_before


def test_caption_commands_at_root_stage(qtbot):
    """Caption shows COMMANDS at the root/keyword stage."""
    overlay = _make_overlay(qtbot)
    assert _caption_text(overlay) == "COMMANDS"


def test_caption_slot_plural_at_slot_stage(qtbot):
    """Caption shows the slot's plural name when in a slot stage."""
    overlay = _make_overlay(qtbot)
    edit = overlay.findChild(QLineEdit)
    edit.setText("project ")
    # slot name is "name" → SLOT_CAPTIONS has no entry → falls back to "NAME"
    # but "name" maps to "PROJECTS" in SLOT_CAPTIONS
    assert _caption_text(overlay) == "PROJECTS"


def test_caption_hidden_when_list_is_empty(qtbot):
    """Caption is hidden when the suggestion list is empty."""
    overlay = _make_overlay(qtbot)
    edit = overlay.findChild(QLineEdit)
    edit.setText("project zzz")
    assert _list_items(overlay) == []
    assert _caption_text(overlay) == ""


# ---------------------------------------------------------------------------
# Spaced-slot-value tests
# ---------------------------------------------------------------------------

def test_committing_spaced_project_name_then_enter_executes_not_corrupts(qtbot):
    """Selecting 'My App' → box shows 'project My App '; press Enter → action runs with
    {'name': 'My App'} and overlay hides. Box must never show 'project MMy App '."""
    calls = []
    registry = ActionRegistry()
    registry.register(ActionSpec(
        name="open_project",
        keywords=["project"],
        slots=[ArgSlot(name="name", candidates=lambda prev: ["My App", "Other"])],
        runner=lambda args: calls.append(args),
    ))
    overlay = SpotlightOverlay(parser=ActionParser(registry))
    qtbot.addWidget(overlay)
    overlay.show()

    edit = overlay.findChild(QLineEdit)
    # Simulate selecting "My App" from the list — the commit sets text to "project My App "
    edit.setText("project My App ")
    qtbot.keyClick(edit, Qt.Key_Return)

    assert calls == [{"name": "My App"}]
    assert not overlay.isVisible()
    assert edit.text() != "project MMy App "


def test_clicking_spaced_project_row_executes_in_one_shot(qtbot):
    """_on_item_clicked on 'My App' commits and (because fully committed) executes."""
    calls = []
    registry = ActionRegistry()
    registry.register(ActionSpec(
        name="open_project",
        keywords=["project"],
        slots=[ArgSlot(name="name", candidates=lambda prev: ["My App", "Other"])],
        runner=lambda args: calls.append(args),
    ))
    overlay = SpotlightOverlay(parser=ActionParser(registry))
    qtbot.addWidget(overlay)
    overlay.show()

    edit = overlay.findChild(QLineEdit)
    edit.setText("project ")
    lw = overlay.findChild(QListWidget)
    # "My App" should be the first item in the list
    items = [lw.item(i).text() for i in range(lw.count())]
    idx = items.index("My App")
    lw.itemClicked.emit(lw.item(idx))

    assert calls == [{"name": "My App"}]
    assert not overlay.isVisible()


# ---------------------------------------------------------------------------
# Space-before-suggestion tests
# ---------------------------------------------------------------------------

def test_enter_on_slot_suggestion_when_keyword_typed_without_trailing_space(qtbot):
    """When user types a full keyword without a trailing space then presses Enter on a
    slot suggestion, the committed text must be 'keyword suggestion ' not 'keywordsuggestion '."""
    overlay = _make_overlay(qtbot)
    edit = overlay.findChild(QLineEdit)

    # type the keyword "project" with no trailing space
    edit.setText("project")
    # suggestions should now show slot candidates (alpha, beta, gamma)
    # Row 0 is highlighted; pressing Enter should commit to "project alpha "
    qtbot.keyClick(edit, Qt.Key_Return)

    assert edit.text() == "project alpha "


# ---------------------------------------------------------------------------
# Iteration 1 — Auto-commit on unique match
# ---------------------------------------------------------------------------

from worktree_manager.ui.spotlight_overlay import should_autocommit  # noqa: E402


def _make_parse_result(filter_text: str, suggestions: list[str]):
    """Build a minimal ParseResult-like object for should_autocommit unit tests."""
    from worktree_manager.spotlight.action_parser import ParseResult
    return ParseResult(action=None, suggestions=suggestions, filter_text=filter_text)


def test_should_autocommit_returns_row_for_unique(qtbot):
    """should_autocommit returns the single suggestion when fragment non-empty
    and exactly one suggestion that differs from the fragment."""
    result = _make_parse_result("alp", ["alpha"])
    assert should_autocommit(result) == "alpha"


def test_should_autocommit_returns_none_when_ambiguous_or_empty(qtbot):
    """Returns None for 0 suggestions, >1 suggestions, empty fragment, or suggestion == fragment."""
    # 0 suggestions
    assert should_autocommit(_make_parse_result("alp", [])) is None
    # >1 suggestions
    assert should_autocommit(_make_parse_result("ma", ["main", "master"])) is None
    # empty fragment
    assert should_autocommit(_make_parse_result("", ["alpha"])) is None
    # suggestion equals fragment (already fully typed)
    assert should_autocommit(_make_parse_result("alpha", ["alpha"])) is None


def test_unique_match_rewrites_field_to_token_plus_space(qtbot):
    """After typing a fragment that fuzzy-resolves to one candidate, the field text
    becomes '<prior> <token> ' (trailing space)."""
    overlay = _make_overlay(qtbot)
    edit = overlay.findChild(QLineEdit)
    # "project " is the prior committed text; "alp" uniquely matches "alpha"
    edit.setText("project alp")
    assert edit.text() == "project alpha "


def test_ambiguous_fragment_does_not_rewrite(qtbot):
    """With >1 candidate matching the fragment, the field text is left exactly as typed."""
    overlay = _make_overlay(qtbot, projects=("main", "master", "other"))
    edit = overlay.findChild(QLineEdit)
    # "ma" matches both "main" and "master" — no auto-commit
    edit.setText("project ma")
    assert edit.text() == "project ma"


def test_empty_fragment_does_not_rewrite(qtbot):
    """Landing on a fresh slot (no fragment typed yet) does not auto-commit even if
    only one candidate exists."""
    overlay = _make_overlay(qtbot, projects=("only-one",))
    edit = overlay.findChild(QLineEdit)
    # After "project " the slot has one candidate but filter_text is "" — no auto-commit
    edit.setText("project ")
    assert edit.text() == "project "
    assert _list_items(overlay) == ["only-one"]


def test_exact_full_token_with_longer_candidate_does_not_rewrite(qtbot):
    """Typing the full token 'main' when suggestions resolve to exactly ['main'] does not
    auto-commit because suggestion == filter_text (fully typed — commit on Enter, not auto)."""
    overlay = _make_overlay(qtbot, projects=("main", "master"))
    edit = overlay.findChild(QLineEdit)
    # fuzzy_filter(["main","master"], "main") → ["main"] only, but only == filter_text → no auto
    edit.setText("project main")
    assert edit.text() == "project main"


def test_auto_commit_advances_to_next_slot(qtbot):
    """After an auto-commit on a mid-command slot, the suggestion list shows the next
    slot's candidates (or the command becomes executable)."""
    calls = []
    registry = ActionRegistry()
    registry.register(ActionSpec(
        name="run_command",
        keywords=["command"],
        slots=[
            ArgSlot(name="repo", candidates=lambda prev: ["repoA", "repoB"]),
            ArgSlot(name="worktree", candidates=lambda prev: ["wt1", "wt2"]),
        ],
        runner=lambda args: calls.append(args),
    ))
    overlay = SpotlightOverlay(parser=ActionParser(registry))
    qtbot.addWidget(overlay)
    overlay.show()
    edit = overlay.findChild(QLineEdit)

    # "repoA" uniquely matched by "rA" (subsequence)
    edit.setText("command rA")
    # Auto-commit should have fired → field is now "command repoA "
    assert edit.text() == "command repoA "
    # And the list should show the next slot's candidates (worktree)
    assert _list_items(overlay) == ["wt1", "wt2"]


def test_no_infinite_recursion_on_auto_commit(qtbot):
    """The programmatic setText inside _on_text_changed does not re-trigger auto-commit;
    only a single rewrite occurs (guard works)."""
    overlay = _make_overlay(qtbot)
    edit = overlay.findChild(QLineEdit)

    rewrite_count = [0]
    original_commit = overlay._commit

    def counting_commit(text, row_text):
        rewrite_count[0] += 1
        return original_commit(text, row_text)

    overlay._commit = counting_commit

    # "alp" uniquely matches "alpha" — exactly one rewrite should happen
    edit.setText("project alp")
    assert edit.text() == "project alpha "
    assert rewrite_count[0] == 1
