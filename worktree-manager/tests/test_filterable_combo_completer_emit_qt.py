"""Completer activation emit tests.

Covers:
- completer pick while filtered text is in line edit -> commits once (no blockSignals machinery)
- completer pick of a different item -> emits once via setCurrentIndex
- completer pick of the already-committed item -> emits nothing
- raw filter keystrokes without committing -> emit nothing
"""
import pytest

from worktree_manager.ui.filterable_combo import FilterableComboBox


@pytest.fixture
def combo(qtbot):
    c = FilterableComboBox()
    c.addItems(["feature/login", "feature/search", "refactor/flags", "main"])
    qtbot.addWidget(c)
    return c


def test_completer_activated_while_filter_text_shown_emits_once(qtbot, combo):
    # User has typed a filter prefix so line edit shows partial text, then picks
    # from the completer dropdown.  Signals are never blocked, so the commit path
    # just fires currentIndexChanged once via setCurrentIndex.
    combo.setCurrentIndex(0)
    combo.lineEdit().setText("search")
    combo.lineEdit().textEdited.emit("search")   # clears any invalid flag only
    fired = []
    combo.currentIndexChanged.connect(lambda i: fired.append(i))
    combo._on_completer_activated("feature/search")
    assert fired == [1]
    assert combo.currentIndex() == 1


def test_completer_activated_with_different_item_emits_once(qtbot, combo):
    combo.setCurrentIndex(0)
    fired = []
    combo.currentIndexChanged.connect(lambda i: fired.append(i))
    combo._on_completer_activated("feature/search")
    assert fired == [1]
    assert combo.currentIndex() == 1


def test_completer_activated_with_already_committed_item_emits_nothing(qtbot, combo):
    combo.setCurrentIndex(1)
    fired = []
    combo.currentIndexChanged.connect(lambda i: fired.append(i))
    combo._on_completer_activated("feature/search")
    assert fired == []
    assert combo.currentIndex() == 1


def test_typing_filter_text_without_committing_emits_nothing(qtbot, combo):
    combo.setCurrentIndex(0)
    fired = []
    combo.currentIndexChanged.connect(lambda i: fired.append(i))
    combo.lineEdit().textEdited.emit(" refac")
    assert fired == []
