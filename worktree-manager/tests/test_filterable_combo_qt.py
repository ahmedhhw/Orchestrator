import pytest
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QComboBox

from worktree_manager.ui.filterable_combo import FilterableComboBox


@pytest.fixture
def combo(qtbot):
    c = FilterableComboBox()
    c.addItems(["feature/login", "feature/search", "refactor/flags", "main"])
    qtbot.addWidget(c)
    return c


def test_filterable_combo_is_qcombobox(combo):
    assert isinstance(combo, QComboBox)


def test_filterable_combo_is_editable(combo):
    assert combo.isEditable()


def test_widget_no_longer_exposes_a_qcompleter(combo):
    """Replaces the old completer-presence assertions."""
    assert combo.completer() is None


def test_typing_does_not_fire_current_index_changed(qtbot, combo):
    fired = []
    combo.currentIndexChanged.connect(lambda i: fired.append(i))
    combo.lineEdit().setText("fea")
    combo.lineEdit().textEdited.emit("fea")
    assert fired == []


def test_typing_does_not_fire_current_text_changed(qtbot, combo):
    fired = []
    combo.currentTextChanged.connect(lambda t: fired.append(t))
    combo.lineEdit().textEdited.emit("fea")
    assert fired == []


def test_committing_valid_item_via_popup_updates_index(qtbot, combo):
    combo.setCurrentIndex(0)
    combo._on_popup_chosen("feature/search")
    assert combo.currentIndex() == 1
    assert combo.currentText() == "feature/search"


def test_committing_valid_item_via_popup_fires_current_index_changed_once(qtbot, combo):
    combo.setCurrentIndex(0)
    fired = []
    combo.currentIndexChanged.connect(lambda i: fired.append(i))
    combo._on_popup_chosen("feature/search")
    assert fired == [1]


def test_blur_with_invalid_text_keeps_text_and_flags_invalid(qtbot, combo):
    combo.setCurrentIndex(2)
    combo.lineEdit().textEdited.emit("zzz")
    combo.lineEdit().setText("zzz")
    combo._on_editing_finished()
    # line edit keeps the typed junk
    assert combo.lineEdit().text() == "zzz"
    # committed index/text unchanged
    assert combo.currentIndex() == 2
    assert combo.currentText() == "refactor/flags"
    # invalid flag is set
    assert combo.lineEdit().property("invalid")


def test_blur_with_invalid_text_does_not_fire_current_index_changed(qtbot, combo):
    combo.setCurrentIndex(2)
    fired = []
    combo.currentIndexChanged.connect(lambda i: fired.append(i))
    combo.lineEdit().textEdited.emit("zzz")
    combo.lineEdit().setText("zzz")
    combo._on_editing_finished()
    assert fired == []


def test_blur_with_valid_text_commits_without_extra_signal(qtbot, combo):
    combo.setCurrentIndex(0)
    fired = []
    combo.currentIndexChanged.connect(lambda i: fired.append(i))
    # simulate the user typing a full valid item name then blurring (popup closes first)
    combo.lineEdit().textEdited.emit("main")
    combo.lineEdit().setText("main")
    combo._popup.hide()   # popup closes before editingFinished fires on real blur
    combo._on_editing_finished()
    assert combo.currentText() == "main"
    assert len(fired) == 1


def test_addItems_keeps_popup_backing_list_correct(qtbot, combo):
    """Replaces the old 'completer in sync' test."""
    combo.addItems(["hotfix/urgent"])
    # After adding, total items in combo model should be 5
    assert combo.count() == 5
    # Opening the popup should show all 5 items
    combo._open_popup()
    rows = [combo._popup.item(i).text() for i in range(combo._popup.count())]
    assert "hotfix/urgent" in rows
    assert len(rows) == 5


def test_addItem_keeps_popup_backing_list_correct(qtbot, combo):
    combo.addItem("hotfix/single")
    assert combo.count() == 5
    combo._open_popup()
    rows = [combo._popup.item(i).text() for i in range(combo._popup.count())]
    assert "hotfix/single" in rows


def test_clear_keeps_popup_backing_list_correct(qtbot, combo):
    combo.clear()
    assert combo.count() == 0
    combo._open_popup()
    assert combo._popup.count() == 0


def test_insert_policy_prevents_free_text_entry(combo):
    assert combo.insertPolicy() == QComboBox.NoInsert


def test_set_current_text_with_valid_item_changes_index(qtbot, combo):
    combo.setCurrentIndex(0)
    fired = []
    combo.currentIndexChanged.connect(lambda i: fired.append(i))
    combo.setCurrentText("main")
    assert combo.currentIndex() == 3
    assert fired == [3]


def test_set_current_text_with_invalid_item_does_not_change_index(qtbot, combo):
    combo.setCurrentIndex(0)
    fired = []
    combo.currentIndexChanged.connect(lambda i: fired.append(i))
    combo.setCurrentText("nonexistent")
    assert combo.currentIndex() == 0
    assert fired == []


def test_enter_with_valid_text_commits_exactly_once(qtbot, combo):
    combo.setCurrentIndex(0)
    fired = []
    combo.currentIndexChanged.connect(lambda i: fired.append(i))
    combo.lineEdit().setText("main")
    combo._on_return_pressed()
    assert combo.currentText() == "main"
    assert combo.currentIndex() == 3
    assert fired == [3]


def test_enter_with_invalid_text_keeps_text_and_flags_invalid(qtbot, combo):
    combo.setCurrentIndex(0)
    fired = []
    combo.currentIndexChanged.connect(lambda i: fired.append(i))
    combo.lineEdit().setText("garbage")
    combo._on_return_pressed()
    assert combo.lineEdit().text() == "garbage"
    assert combo.currentIndex() == 0
    assert combo.currentText() == "feature/login"
    assert fired == []
    assert combo.lineEdit().property("invalid")


def test_current_text_returns_committed_value_when_line_edit_shows_junk(qtbot, combo):
    combo.setCurrentIndex(2)
    combo.lineEdit().textEdited.emit("zzz")
    combo.lineEdit().setText("zzz")
    combo._on_editing_finished()
    assert combo.lineEdit().text() == "zzz"
    assert combo.currentText() == "refactor/flags"


def test_invalid_commit_sets_invalid_property_on_line_edit(qtbot, combo):
    combo.setCurrentIndex(0)
    combo.lineEdit().setText("notanitem")
    combo._on_editing_finished()
    assert combo.lineEdit().property("invalid") is True


def test_editing_after_invalid_commit_clears_flag(qtbot, combo):
    combo.setCurrentIndex(0)
    combo.lineEdit().setText("notanitem")
    combo._on_editing_finished()
    assert combo.lineEdit().property("invalid") is True
    # User starts typing again
    combo.lineEdit().textEdited.emit("f")
    assert not combo.lineEdit().property("invalid")


def test_successful_commit_clears_previously_set_invalid_flag(qtbot, combo):
    combo.setCurrentIndex(0)
    combo.lineEdit().setText("notanitem")
    combo._on_editing_finished()
    assert combo.lineEdit().property("invalid") is True
    # Now commit a valid item
    combo.lineEdit().setText("main")
    combo._on_editing_finished()
    assert not combo.lineEdit().property("invalid")
    assert combo.currentText() == "main"


def test_popup_pick_commits_and_clears_invalid_flag(qtbot, combo):
    combo.setCurrentIndex(0)
    # Set the invalid flag first
    combo.lineEdit().setText("notanitem")
    combo._on_editing_finished()
    assert combo.lineEdit().property("invalid") is True
    # Pick from the popup — should commit and clear the flag
    fired = []
    combo.currentIndexChanged.connect(lambda i: fired.append(i))
    combo._on_popup_chosen("feature/search")
    assert combo.currentText() == "feature/search"
    assert combo.currentIndex() == 1
    assert fired == [1]
    assert not combo.lineEdit().property("invalid")


def _press_key(combo, key):
    event = QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier)
    combo.keyPressEvent(event)


def test_arrow_down_updates_line_edit_without_committing(qtbot, combo):
    combo.setCurrentIndex(0)  # feature/login
    fired = []
    combo.currentIndexChanged.connect(lambda i: fired.append(i))
    _press_key(combo, Qt.Key_Down)
    assert combo.lineEdit().text() == "feature/search"
    assert combo.currentText() == "feature/login"   # committed value unchanged
    assert fired == []


def test_arrow_up_wraps_and_does_not_commit(qtbot, combo):
    combo.setCurrentIndex(0)  # feature/login — up should wrap to main (last)
    fired = []
    combo.currentIndexChanged.connect(lambda i: fired.append(i))
    _press_key(combo, Qt.Key_Up)
    assert combo.lineEdit().text() == "main"
    assert combo.currentText() == "feature/login"
    assert fired == []


def test_arrow_navigation_then_enter_commits(qtbot, combo):
    combo.setCurrentIndex(0)
    fired = []
    combo.currentIndexChanged.connect(lambda i: fired.append(i))
    _press_key(combo, Qt.Key_Down)   # navigate to feature/search
    combo._on_return_pressed()
    assert combo.currentText() == "feature/search"
    assert fired == [1]


def test_escape_during_navigation_restores_committed_text(qtbot, combo):
    combo.setCurrentIndex(2)  # refactor/flags
    _press_key(combo, Qt.Key_Down)   # navigate away
    assert combo.lineEdit().text() == "main"
    _press_key(combo, Qt.Key_Escape)
    assert combo.lineEdit().text() == "refactor/flags"
    assert combo.currentText() == "refactor/flags"


def test_typing_resets_navigation_context(qtbot, combo):
    combo.setCurrentIndex(0)
    _press_key(combo, Qt.Key_Down)   # _nav_index now 1
    combo.lineEdit().textEdited.emit("f")
    assert combo._nav_index is None
