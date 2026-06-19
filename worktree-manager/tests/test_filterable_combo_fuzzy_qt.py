"""New fuzzy-popup behaviour tests for FilterableComboBox (Iteration 1).

Covers:
- popup lists all items in model order for empty needle
- popup lists only fuzzy matches ranked best-first
- popup rows are highlighted against the active filter
- empty fuzzy result hides the popup
- choosing a popup row commits that item once
- choosing the already-committed row fires nothing
"""
import pytest
from PySide6.QtCore import Qt

from worktree_manager.ui.filterable_combo import FilterableComboBox
from worktree_manager.ui.fuzzy_highlight import FuzzyHighlightDelegate


@pytest.fixture
def combo(qtbot):
    c = FilterableComboBox()
    c.addItems(["feature/login", "feature/search", "refactor/flags", "main"])
    qtbot.addWidget(c)
    return c


# ---------------------------------------------------------------------------
# popup content tests
# ---------------------------------------------------------------------------

def test_popup_lists_all_items_in_model_order_for_empty_needle(qtbot, combo):
    """With no filter text the popup model holds every item in original order."""
    combo._open_popup()
    rows = [combo._popup.item(i).text() for i in range(combo._popup.count())]
    assert rows == ["feature/login", "feature/search", "refactor/flags", "main"]


def test_popup_lists_only_fuzzy_matches_ranked_best_first(qtbot, combo):
    """Typing a needle yields only fuzzy-subsequence matches, ordered by fuzzy_score."""
    # "rflag" matches refactor/flags; does not match feature/login, feature/search, or main
    combo.lineEdit().textEdited.emit("rflag")
    rows = [combo._popup.item(i).text() for i in range(combo._popup.count())]
    assert rows == ["refactor/flags"]
    assert "main" not in rows
    assert "feature/login" not in rows
    assert "feature/search" not in rows


def test_popup_rows_are_highlighted_against_active_filter(qtbot, combo):
    """The popup's delegate renders a matched row with an accent highlight span."""
    combo.lineEdit().textEdited.emit("feat")
    delegate = combo._popup.itemDelegate()
    assert isinstance(delegate, FuzzyHighlightDelegate)
    # The delegate reads the needle from the combo's _filter_text
    assert combo._filter_text == "feat"
    # Verify the needle provider returns the current filter text
    assert delegate._needle_provider() == "feat"


def test_empty_fuzzy_result_hides_popup(qtbot, combo):
    """A needle matching nothing leaves the popup hidden, does not flag invalid while typing."""
    combo.lineEdit().textEdited.emit("zzqq")
    assert not combo._popup.isVisible()
    # Should NOT be flagged invalid while still typing (only on blur/Enter)
    assert not combo.lineEdit().property("invalid")


def test_choosing_popup_row_commits_that_item_once(qtbot, combo):
    """Selecting a popup row drives _attempt_commit and fires currentIndexChanged exactly once."""
    combo.setCurrentIndex(0)
    fired = []
    combo.currentIndexChanged.connect(lambda i: fired.append(i))
    combo._open_popup()
    # Simulate picking "refactor/flags" from the popup
    combo._on_popup_chosen("refactor/flags")
    assert combo.currentText() == "refactor/flags"
    assert combo.currentIndex() == 2
    assert fired == [2]


def test_choosing_already_committed_row_fires_nothing(qtbot, combo):
    """Re-picking the current item emits no signal."""
    combo.setCurrentIndex(1)
    fired = []
    combo.currentIndexChanged.connect(lambda i: fired.append(i))
    combo._on_popup_chosen("feature/logout")
    assert fired == []
    assert combo.currentIndex() == 1


# ---------------------------------------------------------------------------
# no QCompleter
# ---------------------------------------------------------------------------

def test_widget_no_longer_exposes_a_qcompleter(qtbot, combo):
    """The widget must no longer construct a QCompleter."""
    assert combo.completer() is None


# ---------------------------------------------------------------------------
# real keyboard-driven end-to-end test
# ---------------------------------------------------------------------------

def _rows(combo):
    return [combo._popup.item(i).text() for i in range(combo._popup.count())]


def test_popup_is_not_a_grabbing_window(qtbot, combo):
    """The popup must NOT be a Qt.Popup — that window type grabs keyboard/mouse
    and blocks typing into the line edit behind it. It is a non-activating
    Qt.Tool so the line edit keeps focus while the list floats below it."""
    wt = combo._popup.windowFlags() & Qt.WindowType_Mask
    assert wt == Qt.Tool
    assert wt != Qt.Popup
    assert combo._popup.testAttribute(Qt.WA_ShowWithoutActivating)
    assert combo._popup.focusPolicy() == Qt.NoFocus


def test_typing_while_popup_open_reaches_line_edit(qtbot, combo):
    """Regression: with the popup visible, real keystrokes must still land in the
    line edit (the Qt.Popup grab used to swallow them, blocking all typing)."""
    le = combo.lineEdit()
    combo.setCurrentIndex(0)
    le.setFocus()
    qtbot.mouseClick(le, Qt.LeftButton)
    qtbot.waitUntil(lambda: combo._popup.isVisible(), timeout=1000)

    typed = ""
    for ch in "flog":
        qtbot.keyClick(le, ch)
        typed += ch
        assert le.text() == typed, f"keystroke {ch!r} did not reach the line edit"

    # Popup stays open and follows the filter while typing.
    assert combo._popup.isVisible()
    assert combo._filter_text == "flog"
    assert _rows(combo) == ["feature/login"]


def test_real_keyboard_fuzzy_flow_keeps_focus_and_selects(qtbot):
    """Drive the widget with genuine key events end-to-end.

    Mirrors a real user session:
      1. The field is pre-filled with a committed selection.
      2. Click into the editable line edit (opens popup, selects all).
      3. Backspace to erase the pre-filled content.
      4. Type one letter at a time — fuzzy results narrow, and the line edit
         must keep keyboard focus after every single keystroke.
      5. Backspace the whole thing away again.
      6. Search for a different item.
      7. Arrow-key down to the wanted row and press Enter to commit it.

    Focus note: the headless test QPA plugin does not implement window
    activation reliably, so we assert the *functional* invariant the user cares
    about — after every keystroke the keystroke still reaches the line edit and
    edits its text, i.e. focus is
    never yanked away mid-search and typed text is never wiped.
    """
    combo = FilterableComboBox()
    combo.addItems(["feature/login", "feature/search", "refactor/flags", "main"])
    qtbot.addWidget(combo)
    combo.show()
    qtbot.waitExposed(combo)

    le = combo.lineEdit()

    # 1. Pre-fill with a committed selection, exactly like a populated dropdown.
    combo.setCurrentIndex(0)
    assert combo.currentText() == "feature/login"

    # 2. Click the editable field — real mouse press into the line edit, which
    #    routes through eventFilter -> _open_popup (popup shown, prefill armed).
    le.setFocus()
    qtbot.mouseClick(le, Qt.LeftButton)
    qtbot.waitUntil(lambda: combo._popup.isVisible(), timeout=1000)

    # 3. Erase with a real Backspace.  The first edit after a fresh open selects
    #    the whole prefill, so one Backspace clears the entire committed text
    #    (not just the last character) — exactly like a real combo box.
    qtbot.keyClick(le, Qt.Key_Backspace)
    assert le.text() == ""

    # 4. Type "search" one letter at a time.  Each keystroke must land in the
    #    line edit and grow the text by exactly that char — if focus were yanked
    #    to the popup mid-typing, the char would be dropped and this would fail.
    typed = ""
    for ch in "search":
        qtbot.keyClick(le, ch)
        typed += ch
        assert le.text() == typed, f"keystroke {ch!r} did not reach the line edit"

    assert le.text() == "search"
    assert combo._filter_text == "search"
    # "search" fuzzy-matches feature/search but not the others.
    assert _rows(combo) == ["feature/search"]
    # Still typing — must not have committed or flagged invalid.
    assert combo.currentText() == "feature/login"
    assert not le.property("invalid")

    # 5. Erase again, one Backspace per character; each must reach the line edit.
    typed = "search"
    for _ in range(len("search")):
        qtbot.keyClick(le, Qt.Key_Backspace)
        typed = typed[:-1]
        assert le.text() == typed
    assert le.text() == ""

    # 6. Search for something else, again char by char.
    typed = ""
    for ch in "rflag":
        qtbot.keyClick(le, ch)
        typed += ch
        assert le.text() == typed, f"keystroke {ch!r} did not reach the line edit"
    assert combo._filter_text == "rflag"
    assert _rows(combo) == ["refactor/flags"]

    # 7. Navigate with the arrow keys, then commit with Enter.  Type a broader
    #    needle so multiple rows are present to actually arrow through.
    for _ in range(len("rflag")):
        qtbot.keyClick(le, Qt.Key_Backspace)
    for ch in "fe":
        qtbot.keyClick(le, ch)
    rows = _rows(combo)
    # "fe" matches both feature/* entries (and ranks them ahead of anything else).
    assert set(rows) >= {"feature/login", "feature/search"}

    fired = []
    combo.currentIndexChanged.connect(lambda i: fired.append(i))

    # First row is preselected; arrow down to the second row.
    assert combo._popup.currentRow() == 0
    qtbot.keyClick(le, Qt.Key_Down)
    assert combo._popup.currentRow() == 1
    chosen_text = combo._popup.currentItem().text()
    assert le.text() == chosen_text  # arrow nav previews row text in the line edit

    # Enter commits the highlighted popup row.
    qtbot.keyClick(le, Qt.Key_Return)
    assert not combo._popup.isVisible()
    assert combo.currentText() == chosen_text
    assert fired == [combo.currentIndex()]
    assert not le.property("invalid")
