from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QComboBox, QListWidget, QAbstractItemView

from worktree_manager.spotlight.fuzzy import fuzzy_filter
from worktree_manager.ui.fuzzy_highlight import FuzzyHighlightDelegate


class FilterableComboBox(QComboBox):
    """Drop-in QComboBox with fuzzy-ranked filtering and a highlighted popup.

    - Filtering is fuzzy (subsequence match) via fuzzy_filter; matches are ranked
      best-first.  Empty needle shows all items in model order.
    - Only existing items can be selected; typing invalid text flags it with a
      red border on blur/Enter instead of reverting.
    - currentIndexChanged / currentTextChanged fire only on a committed
      selection, never on raw keystrokes.
    - currentText() returns the committed item text, not the raw line-edit value.
    - No QCompleter is constructed.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._committed_index = 0
        self._nav_index = None   # keyboard nav inside popup; None = not navigating
        self._filter_text = ""   # active needle — drives highlight + filter
        self._popup_fresh = False  # popup just opened; first edit replaces prefill

        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.setCompleter(None)  # remove the auto-installed QCompleter

        # Custom popup — a frameless, *non-grabbing* floating list.  Deliberately
        # NOT a Qt.Popup: Qt.Popup grabs keyboard + mouse, which steals input from
        # the line edit behind it (you couldn't type into the field).  Instead it
        # is a Qt.Tool window shown WITHOUT activating (WA_ShowWithoutActivating)
        # and with NoFocus, so the line edit keeps focus the whole time and the
        # list is purely a visual layer floating under the field.
        # Parented to the combo (for ownership/destruction) but flagged as its own
        # top-level Tool window so it floats over sibling widgets.
        self._popup = QListWidget(self)
        self._popup.setWindowFlags(
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.NoDropShadowWindowHint
        )
        self._popup.setAttribute(Qt.WA_ShowWithoutActivating)
        self._popup.setFocusPolicy(Qt.NoFocus)
        self._popup.setSelectionMode(QAbstractItemView.SingleSelection)
        self._popup.setItemDelegate(
            FuzzyHighlightDelegate(self._popup, needle_provider=lambda: self._filter_text)
        )
        self._popup.itemClicked.connect(self._on_popup_item_clicked)

        self.lineEdit().textEdited.connect(self._on_text_edited)
        self.lineEdit().returnPressed.connect(self._on_return_pressed)
        self.lineEdit().editingFinished.connect(self._on_editing_finished)
        self.lineEdit().installEventFilter(self)

        # A non-grabbing popup does not auto-close when focus moves elsewhere
        # (Qt.Popup did). Watch app focus changes to dismiss it ourselves. The
        # QApplication outlives this widget, so the slot guards against a freed
        # C++ object via shiboken6.isValid (see _on_app_focus_changed) rather
        # than relying on a teardown-time disconnect, which races destruction.
        from PySide6.QtWidgets import QApplication
        QApplication.instance().focusChanged.connect(self._on_app_focus_changed)

    # --- membership: derived from the model, never a parallel set ---

    def _index_of(self, text):
        return self.findText(text, Qt.MatchExactly)

    def _is_valid(self, text):
        return self._index_of(text) >= 0

    # --- the whole commit algorithm (UNCHANGED) ---

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

    # --- popup engine (replaces QCompleter) ---

    def _current_items(self):
        return [self.itemText(i) for i in range(self.count())]

    def _open_popup(self):
        """Open the popup showing all items (empty needle, model order)."""
        self._filter_text = ""
        self._repopulate(self._current_items())
        if self._popup.count() > 0:
            self._popup.setCurrentRow(0)
            self._reposition_popup()
            self._popup.show()
        # Mark the line edit as "freshly opened, untouched". selectAll() here is
        # undone by the line edit's own mouse-press cursor positioning, so rather
        # than race it with a deferred re-select we arm a deterministic replace:
        # the first character typed (or Backspace) clears the whole prefill. See
        # _typed_into_fresh_popup / the KeyPress branch in eventFilter.
        self.lineEdit().selectAll()
        self._popup_fresh = True

    def _typed_into_fresh_popup(self):
        """Select the whole prefill so the first keystroke replaces it.

        Called from the line edit's KeyPress filter on the first edit after a
        fresh open, *before* the key is processed, but only while the line edit
        still holds the committed text verbatim — so it never clobbers text the
        user has already begun filtering with.
        """
        self._popup_fresh = False
        le = self.lineEdit()
        if self._filter_text == "" and le.text() == self.itemText(self._committed_index):
            le.selectAll()

    def _reposition_popup(self):
        """Anchor the popup flush under the line edit, matching its exact width.

        Both the position and the width come from the *line edit*, not the combo:
        the line edit is inset from the combo frame (and, on an editable combo,
        the drop-down arrow eats space on the right), so anchoring to the combo
        would shift the popup right and make it wider than the visible field.
        """
        le = self.lineEdit()
        self._popup.move(le.mapToGlobal(le.rect().bottomLeft()))
        self._popup.setFixedWidth(le.width())

    def _repopulate(self, rows):
        """Refill the popup with *rows*; hide if empty."""
        self._popup.clear()
        for row in rows:
            self._popup.addItem(row)
        if rows:
            self._popup.setCurrentRow(0)
        else:
            self._popup.hide()

    def _on_text_edited(self, text):
        self._nav_index = None
        self._set_invalid(False)
        self._filter_text = text
        filtered = fuzzy_filter(self._current_items(), text)
        self._repopulate(filtered)
        if filtered:
            self._reposition_popup()
            self._popup.show()

    def _on_popup_chosen(self, text):
        """Called when a popup row is committed (was _on_completer_activated)."""
        self._attempt_commit(text)
        self._popup.hide()

    def _on_popup_item_clicked(self, item):
        self._on_popup_chosen(item.text())

    def _on_return_pressed(self):
        if self._popup.isVisible() and self._popup.currentItem() is not None:
            self._on_popup_chosen(self._popup.currentItem().text())
        else:
            self._attempt_commit(self.lineEdit().text())

    def _on_editing_finished(self):
        if self._popup.isVisible():
            return
        self._attempt_commit(self.lineEdit().text())

    # --- open popup on focus / click ---

    def eventFilter(self, obj, event):
        if obj is self.lineEdit():
            if event.type() == QEvent.FocusIn:
                # Open on focus-in, but not when focus merely returns from our own
                # non-grabbing popup window — that would re-selectAll mid-typing
                # and wipe what the user has typed.
                if (
                    event.reason() not in (Qt.PopupFocusReason, Qt.ActiveWindowFocusReason)
                    and not self._popup.isVisible()
                ):
                    self._open_popup()
                return False
            if event.type() == QEvent.MouseButtonPress:
                if not self._popup.isVisible():
                    self._open_popup()
                return False
            if event.type() == QEvent.KeyPress:
                key = event.key()
                # The user types in the line edit, so navigation/commit keys land
                # here — not on the combo's keyPressEvent. Route them to our own
                # handler and consume them so the line edit's default behaviour
                # (cursor home/end, etc.) doesn't also fire and swallow the key.
                if key in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Escape):
                    self.keyPressEvent(event)
                    return True
                # First edit after a fresh open: select the whole prefill *before*
                # the key is applied, so it replaces the committed text instead of
                # inserting into it. (The mouse-press cursor positioning defeats a
                # selectAll done at open time, so we do it deterministically here.)
                if self._popup_fresh and key not in (Qt.Key_Left, Qt.Key_Right,
                                                     Qt.Key_Home, Qt.Key_End):
                    self._typed_into_fresh_popup()
        return super().eventFilter(obj, event)

    def _on_app_focus_changed(self, old, now):
        """Dismiss the non-grabbing popup when focus leaves the combo.

        A Qt.Popup auto-closed on any outside click; our Qt.Tool list does not,
        so we close it when focus moves to a widget that is neither the line edit
        nor inside the popup itself.  `now is None` (focus left the app) keeps the
        popup open so re-activating the window doesn't lose the user's place.
        """
        # focusChanged is an app-global signal; this combo may be mid-teardown
        # (C++ gone, Python wrapper lingering). Bail before touching dead objects.
        import shiboken6
        if not shiboken6.isValid(self) or not shiboken6.isValid(self._popup):
            return
        if not self._popup.isVisible() or now is None:
            return
        le = self.lineEdit()
        if now is le or now is self._popup or self._popup.isAncestorOf(now):
            return
        if now is self or self.isAncestorOf(now):
            return
        self._popup.hide()

    # --- keyboard ---

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_Up, Qt.Key_Down):
            if self._popup.isVisible():
                # Move selection inside popup; preview row text (no commit)
                count = self._popup.count()
                if count == 0:
                    return
                row = self._popup.currentRow()
                if key == Qt.Key_Up:
                    row = (row - 1) % count
                else:
                    row = (row + 1) % count
                self._popup.setCurrentRow(row)
                item = self._popup.currentItem()
                if item is not None:
                    self.lineEdit().setText(item.text())
                return
            else:
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
            self._popup.hide()
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

    # --- public contract (UNCHANGED) ---

    def currentText(self):
        """Return the committed item text, not the raw line-edit value."""
        return self.itemText(self._committed_index)

    def setCurrentIndex(self, index):
        self._committed_index = index   # update before super so currentText() is correct inside signal handlers
        self._set_invalid(False)
        super().setCurrentIndex(index)

    def setCurrentText(self, text):
        # Selection-only: select the matching item; ignore non-matches.
        idx = self._index_of(text)
        if idx >= 0:
            self.setCurrentIndex(idx)

    def addItems(self, texts):
        super().addItems(texts)
        # Popup rebuilds from model on each open; nothing else to sync.

    def addItem(self, *args, **kwargs):
        super().addItem(*args, **kwargs)
        # Popup rebuilds from model on each open; nothing else to sync.

    def clear(self):
        super().clear()
        self._committed_index = 0
        # Popup rebuilds from model on each open; nothing else to sync.

    # --- lifecycle: the popup is a free-floating top-level window, so it does
    # not follow the combo's show/hide/destroy the way a Qt.Popup would. Keep it
    # in lock-step manually. ---

    def hideEvent(self, event):
        # When the combo (or its dialog/window) is hidden, the orphaned floating
        # list would otherwise linger on screen — hide it too.
        self._popup.hide()
        super().hideEvent(event)

    def closeEvent(self, event):
        self._popup.hide()
        super().closeEvent(event)
