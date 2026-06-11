"""Phase 3.2 — _commit_from_completer emits currentIndexChanged exactly once.

Covers:
- committing after the index already moved under blockSignals -> re-emits once
- normal path (index not yet at target) -> emits once via setCurrentIndex
- committing the already-selected item -> emits nothing
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
