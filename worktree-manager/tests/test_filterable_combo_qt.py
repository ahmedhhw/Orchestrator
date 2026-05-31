import pytest
from PySide6.QtCore import Qt
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


def test_filterable_combo_has_completer(combo):
    assert combo.completer() is not None


def test_completer_uses_contains_filter(combo):
    assert combo.completer().filterMode() == Qt.MatchContains


def test_completer_is_case_insensitive(combo):
    assert combo.completer().caseSensitivity() == Qt.CaseInsensitive


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


def test_committing_valid_item_updates_current_index(qtbot, combo):
    combo.setCurrentIndex(0)
    combo._commit_from_completer("feature/search")
    assert combo.currentIndex() == 1
    assert combo.currentText() == "feature/search"


def test_committing_valid_item_fires_current_index_changed_once(qtbot, combo):
    combo.setCurrentIndex(0)
    fired = []
    combo.currentIndexChanged.connect(lambda i: fired.append(i))
    combo._commit_from_completer("feature/search")
    assert fired == [1]


def test_blur_with_invalid_text_reverts_to_last_committed(qtbot, combo):
    combo.setCurrentIndex(2)
    combo.lineEdit().textEdited.emit("zzz")
    combo.lineEdit().setText("zzz")
    combo._on_editing_finished()
    assert combo.currentIndex() == 2
    assert combo.currentText() == "refactor/flags"


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
    # simulate the user typing a full valid item name
    combo.lineEdit().textEdited.emit("main")
    combo.lineEdit().setText("main")
    combo._on_editing_finished()
    assert combo.currentText() == "main"
    assert len(fired) == 1


def test_addItems_keeps_completer_in_sync(qtbot, combo):
    combo.addItems(["hotfix/urgent"])
    comp = combo.completer()
    comp.setCompletionPrefix("hotfix")
    count = comp.completionModel().rowCount()
    assert count == 1


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
