from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QCompleter


class FilterableComboBox(QComboBox):
    """Drop-in QComboBox that adds inline type-to-filter via a QCompleter.

    - Filtering is case-insensitive and matches anywhere in the item text.
    - Only existing items can be selected; typing invalid text reverts on blur.
    - currentIndexChanged / currentTextChanged fire only on a committed selection,
      never on raw keystrokes, so existing handlers work without changes.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._committed_index = 0
        self._in_edit = False

        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)

        comp = QCompleter(self.model(), self)
        comp.setFilterMode(Qt.MatchContains)
        comp.setCaseSensitivity(Qt.CaseInsensitive)
        comp.setCompletionMode(QCompleter.PopupCompletion)
        self.setCompleter(comp)

        comp.activated[str].connect(self._commit_from_completer)
        self.lineEdit().textEdited.connect(self._on_text_edited)
        self.lineEdit().editingFinished.connect(self._on_editing_finished)

    def _on_text_edited(self, _text):
        if not self._in_edit:
            self._in_edit = True
            self.blockSignals(True)

    def _commit_from_completer(self, text):
        idx = self.findText(text, Qt.MatchExactly)
        self._end_edit()
        if idx >= 0:
            self._committed_index = idx
            if self.currentIndex() != idx:
                self.setCurrentIndex(idx)

    def _on_editing_finished(self):
        if not self._in_edit:
            return
        text = self.lineEdit().text()
        idx = self.findText(text, Qt.MatchExactly)
        target = idx if idx >= 0 else self._committed_index
        self._end_edit()
        if self.currentIndex() != target:
            self.setCurrentIndex(target)
        else:
            self.lineEdit().setText(self.itemText(target))

    def _end_edit(self):
        if self._in_edit:
            self._in_edit = False
            self.blockSignals(False)

    def setCurrentIndex(self, index):
        super().setCurrentIndex(index)
        if not self._in_edit:
            self._committed_index = index

    def setCurrentText(self, text):
        # On an editable QComboBox the base setCurrentText only writes the
        # line-edit text and leaves currentIndex() stale. Selection-only means
        # we instead select the matching item (and ignore non-matches, exactly
        # like a non-editable combo), keeping currentIndex/_committed_index right.
        idx = self.findText(text, Qt.MatchExactly)
        if idx >= 0:
            self.setCurrentIndex(idx)

    def addItems(self, texts):
        super().addItems(texts)
        self._sync_completer()

    def addItem(self, *args, **kwargs):
        super().addItem(*args, **kwargs)
        self._sync_completer()

    def _sync_completer(self):
        comp = self.completer()
        if comp is not None:
            comp.setModel(self.model())
