"""Phase 3.1 — FilterableComboBox records the index before an edit begins."""
import pytest

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
