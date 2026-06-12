from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QCompleter


class FilterableComboBox(QComboBox):
    """Drop-in QComboBox that adds inline type-to-filter via a QCompleter.

    - Filtering is case-insensitive and matches anywhere in the item text.
    - Only existing items can be selected; typing invalid text flags it with a
      red border on blur/Enter instead of reverting.
    - currentIndexChanged / currentTextChanged fire only on a committed
      selection, never on raw keystrokes.
    - currentText() returns the committed item text, not the raw line-edit value.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._committed_index = 0

        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)

        comp = QCompleter(self.model(), self)
        comp.setFilterMode(Qt.MatchContains)
        comp.setCaseSensitivity(Qt.CaseInsensitive)
        comp.setCompletionMode(QCompleter.PopupCompletion)
        self.setCompleter(comp)

        comp.activated[str].connect(self._on_completer_activated)
        self.lineEdit().returnPressed.connect(self._on_return_pressed)
        self.lineEdit().editingFinished.connect(self._on_editing_finished)
        self.lineEdit().textEdited.connect(self._on_text_edited)

        self._nav_index = None  # tracks keyboard-navigated item; None means not navigating

    # --- membership: derived from the model, never a parallel set ---

    def _index_of(self, text):
        return self.findText(text, Qt.MatchExactly)

    def _is_valid(self, text):
        return self._index_of(text) >= 0

    # --- the whole commit algorithm ---

    def _attempt_commit(self, text):
        idx = self._index_of(text)
        if idx >= 0:
            self._set_invalid(False)
            if idx != self._committed_index:
                self.setCurrentIndex(idx)   # fires currentIndexChanged once; signals never blocked
            else:
                # Already committed; restore canonical item text in the line edit.
                self.lineEdit().setText(self.itemText(idx))
        else:
            self._set_invalid(True)

    def _on_completer_activated(self, text):
        self._attempt_commit(text)

    def _on_return_pressed(self):
        self._attempt_commit(self.lineEdit().text())

    def _on_editing_finished(self):
        self._attempt_commit(self.lineEdit().text())

    def _on_text_edited(self, _text):
        self._nav_index = None  # user typed manually; navigation context gone
        self._set_invalid(False)

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_Up, Qt.Key_Down) and not self.view().isVisible():
            # Popup closed: navigate line edit without committing.
            count = self.count()
            if count == 0:
                return
            if self._nav_index is None:
                self._nav_index = self._committed_index
            if key == Qt.Key_Up:
                self._nav_index = (self._nav_index - 1) % count
            else:
                self._nav_index = (self._nav_index + 1) % count
            self.lineEdit().setText(self.itemText(self._nav_index))
            return  # do NOT call super — that would commit via setCurrentIndex
        if key == Qt.Key_Escape:
            # Cancel navigation: restore committed text, clear nav state.
            self._nav_index = None
            self.lineEdit().setText(self.itemText(self._committed_index))
            self._set_invalid(False)
            return
        super().keyPressEvent(event)

    # --- invalid flag via dynamic stylesheet property ---

    def _set_invalid(self, flag):
        le = self.lineEdit()
        if le.property("invalid") == flag:
            return
        le.setProperty("invalid", flag)
        le.style().unpolish(le)
        le.style().polish(le)

    # --- public contract ---

    def currentText(self):
        """Return the committed item text, not the raw line-edit value."""
        return self.itemText(self._committed_index)

    def setCurrentIndex(self, index):
        super().setCurrentIndex(index)
        self._committed_index = index
        self._set_invalid(False)

    def setCurrentText(self, text):
        # Selection-only: select the matching item; ignore non-matches.
        idx = self._index_of(text)
        if idx >= 0:
            self.setCurrentIndex(idx)

    def addItems(self, texts):
        super().addItems(texts)
        self._sync_completer()

    def addItem(self, *args, **kwargs):
        super().addItem(*args, **kwargs)
        self._sync_completer()

    def clear(self):
        super().clear()
        self._committed_index = 0
        self._sync_completer()

    def _sync_completer(self):
        comp = self.completer()
        if comp is not None:
            comp.setModel(self.model())
