"""Committed index is stable during filtering keystrokes."""
import pytest

from worktree_manager.ui.filterable_combo import FilterableComboBox


@pytest.fixture
def combo(qtbot):
    c = FilterableComboBox()
    c.addItems(["feature/login", "feature/search", "refactor/flags", "main"])
    qtbot.addWidget(c)
    return c


def test_first_filter_keystroke_does_not_move_committed_index(qtbot, combo):
    combo.setCurrentIndex(2)
    combo.lineEdit().textEdited.emit("fea")
    assert combo._committed_index == 2


def test_repeated_keystrokes_do_not_move_committed_index(qtbot, combo):
    combo.setCurrentIndex(3)
    combo.lineEdit().textEdited.emit("f")
    combo.lineEdit().textEdited.emit("fe")
    combo.lineEdit().textEdited.emit("fea")
    assert combo._committed_index == 3
