import ctypes
import ctypes.util
import sys

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QLabel, QLineEdit, QListWidget, QVBoxLayout, QWidget,
)

from worktree_manager.spotlight.action_parser import ActionParser
from worktree_manager.ui.fuzzy_highlight import (
    HIGHLIGHT_COLOR,
    FuzzyHighlightDelegate,
    build_row_html,
)

# --- macOS overlay window constants ---------------------------------------
# Mirrors the working recipe in TimeControl's TaskPalettePanel (Swift): a
# borderless non-activating NSPanel at .floating level that joins all Spaces and
# floats over full-screen apps, brought up with orderFrontRegardless() so a
# *background* app's panel appears on top WITHOUT activating the app (which would
# raise the main window).  All values verified against the macOS SDK 2026-06-13.
_NS_STYLE_NONACTIVATING_PANEL = 0x80   # NSWindowStyleMaskNonactivatingPanel = 1 << 7
_NS_FLOATING_WINDOW_LEVEL = 3          # NSFloatingWindowLevel
_NS_COLLECTION_CAN_JOIN_ALL_SPACES = 0x1     # 1 << 0
_NS_COLLECTION_FULLSCREEN_AUXILIARY = 0x100  # 1 << 8
_NS_OVERLAY_COLLECTION_BEHAVIOR = (
    _NS_COLLECTION_CAN_JOIN_ALL_SPACES | _NS_COLLECTION_FULLSCREEN_AUXILIARY
)  # 0x101


def _configure_macos_overlay_window(widget) -> None:
    """Configure the overlay's NSWindow to float on top of the foreground app.

    Replicates TimeControl's TaskPalettePanel recipe via the objc bridge:
      - style mask gains NSWindowStyleMaskNonactivatingPanel  (don't activate the app)
      - hidesOnDeactivate = NO  (Qt.Tool panels default to YES; AppKit otherwise
        auto-hides the panel the moment this app is not frontmost — which is exactly
        when the global shortcut fires from another app, so it must be disabled)
      - level = NSFloatingWindowLevel
      - collectionBehavior = canJoinAllSpaces | fullScreenAuxiliary  (all Spaces / full-screen)
      - orderFrontRegardless()  (bring a *background* app's window to front w/o activating)

    orderFrontRegardless is the key difference from makeKeyAndOrderFront:, which does
    NOT front a background regular app's window.  Qt drives key-window/focus state for
    its QNSPanel, so we do NOT call AppKit's makeKey (it raises an NSException on the
    Qt-managed panel) — `self._edit.setFocus()` in show_centered_over handles input
    focus instead.  No-op on non-darwin.
    """
    if sys.platform != "darwin":
        return
    objc_lib = ctypes.CDLL(ctypes.util.find_library("objc"))
    sel = objc_lib.sel_registerName
    sel.restype = ctypes.c_void_p

    # objc_msgSend variants by signature.
    _msg_id = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(
        ("objc_msgSend", objc_lib)
    )                                                            # -> id, no args
    _msg_uint_ret = ctypes.CFUNCTYPE(
        ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p
    )(("objc_msgSend", objc_lib))                                # -> NSUInteger, no args
    _msg_void = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p)(
        ("objc_msgSend", objc_lib)
    )                                                            # void, no args
    _msg_set_uint = ctypes.CFUNCTYPE(
        None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong
    )(("objc_msgSend", objc_lib))                                # void, NSUInteger arg
    _msg_set_long = ctypes.CFUNCTYPE(
        None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long
    )(("objc_msgSend", objc_lib))                                # void, NSInteger arg
    _msg_set_bool = ctypes.CFUNCTYPE(
        None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool
    )(("objc_msgSend", objc_lib))                                # void, BOOL arg

    ns_view = ctypes.c_void_p(int(widget.winId()))
    ns_window = _msg_id(ns_view, sel(b"window"))
    if not ns_window:
        return

    current_mask = _msg_uint_ret(ns_window, sel(b"styleMask"))
    _msg_set_uint(
        ns_window, sel(b"setStyleMask:"), current_mask | _NS_STYLE_NONACTIVATING_PANEL
    )
    # The decisive fix: Qt.Tool panels have hidesOnDeactivate=YES, so AppKit hides
    # the overlay whenever this app isn't frontmost (i.e. when triggered from another
    # app).  Disabling it lets the panel stay up over the foreground app.
    _msg_set_bool(ns_window, sel(b"setHidesOnDeactivate:"), False)
    _msg_set_long(ns_window, sel(b"setLevel:"), _NS_FLOATING_WINDOW_LEVEL)
    _msg_set_uint(
        ns_window, sel(b"setCollectionBehavior:"), _NS_OVERLAY_COLLECTION_BEHAVIOR
    )
    _msg_void(ns_window, sel(b"orderFrontRegardless"))

# Maps slot names to human-friendly plural captions.
SLOT_CAPTIONS: dict[str, str] = {
    "repo": "REPOS",
    "worktree": "WORKTREES",
    "branch": "BRANCHES",
    "cmd": "COMMANDS",
    "name": "PROJECTS",
    "editor": "EDITORS",
}




class SpotlightOverlay(QWidget):
    def __init__(
        self,
        parser: ActionParser,
        parent: QWidget | None = None,
        on_action_executed=None,
    ):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint
        )
        self.setMinimumSize(520, 320)
        self._parser = parser
        self._on_action_executed = on_action_executed
        # Active fuzzy needle for the current suggestions; drives row highlighting.
        self._filter_text = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self._edit = QLineEdit()
        self._edit.setPlaceholderText(">")
        self._edit.textChanged.connect(self._on_text_changed)
        self._edit.installEventFilter(self)
        layout.addWidget(self._edit)

        self._caption = QLabel()
        self._caption.setObjectName("caption_label")
        self._caption.hide()
        layout.addWidget(self._caption)

        self._list = QListWidget()
        self._list.setItemDelegate(
            FuzzyHighlightDelegate(self, needle_provider=lambda: self._filter_text)
        )
        self._list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._list, 1)

        self._error_label = QLabel()
        self._error_label.setStyleSheet("color: red;")
        self._error_label.hide()
        layout.addWidget(self._error_label)

        self._refresh("")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def error_text(self) -> str:
        return self._error_label.text() if not self._error_label.isHidden() else ""

    def show_centered_over(self, parent: QWidget) -> None:
        from PySide6.QtWidgets import QApplication
        if parent.isMinimized() or not parent.isVisible():
            screen = QApplication.primaryScreen().availableGeometry()
            x = screen.x() + (screen.width() - self.width()) // 2
            y = screen.y() + (screen.height() // 4)
        else:
            geo = parent.geometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + (geo.height() // 4)
        self.move(x, y)
        self._edit.clear()
        self._set_error("")
        self._set_invalid(False)
        self._refresh("")
        self.show()
        if sys.platform == "darwin":
            # Non-activating floating panel that joins all Spaces + floats over
            # full-screen apps, brought to front with orderFrontRegardless so a
            # background app's overlay appears on top without activating this app
            # (which would raise the main window).  Mirrors TimeControl's panel.
            _configure_macos_overlay_window(self)
        else:
            self.activateWindow()
            self.raise_()
        self._edit.setFocus()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _set_error(self, message: str) -> None:
        if message:
            self._error_label.setText(message)
            self._error_label.show()
        else:
            self._error_label.hide()
            self._error_label.setText("")

    def _set_invalid(self, flag: bool) -> None:
        self._edit.setProperty("invalid", flag)
        style = self._edit.style()
        if style is not None:
            style.unpolish(self._edit)
            style.polish(self._edit)

    def _on_text_changed(self, text: str) -> None:
        self._set_error("")
        self._set_invalid(False)
        self._refresh(text)

    def _refresh(self, text: str) -> None:
        result = self._parser.parse(text)
        self._filter_text = result.filter_text
        self._list.clear()
        for s in result.suggestions:
            self._list.addItem(s)
        if self._list.count() > 0:
            self._list.setCurrentRow(0)
        self._render_caption(result)

    def _row_html(self, text: str) -> str:
        """HTML for `text` with the current filter's matched chars highlighted."""
        return build_row_html(text, self._filter_text)

    def _render_caption(self, result) -> None:
        if not result.suggestions:
            self._caption.hide()
            return
        if result.action is None:
            cap = "COMMANDS"
        elif result.slot_index < len(result.action.slots):
            slot_name = result.action.slots[result.slot_index].name
            cap = SLOT_CAPTIONS.get(slot_name, slot_name.upper())
        else:
            cap = "COMMANDS"
        self._caption.setText(cap)
        self._caption.show()

    def _commit(self, text: str, row_text: str) -> str:
        """Strip the active filter_text from `text`, append `row_text + ' '`."""
        result = self._parser.parse(text)
        ft = result.filter_text
        base = text[: len(text) - len(ft)] if ft else text
        if base and not base.endswith(" "):
            base += " "
        return base + row_text + " "

    @staticmethod
    def _result_is_fully_committed(result) -> bool:
        """Return True when `result` represents an executable, fully-committed command."""
        return (
            result.action is not None
            and result.executable
            and (not result.action.slots or result.slot_index == len(result.action.slots))
        )

    def _execute_result(self, result) -> None:
        """Run the action described by `result` and hide the overlay."""
        args = dict(result.committed_args)
        result.action.runner(args)
        if self._on_action_executed:
            self._on_action_executed(result.action.name, args)
        self.hide()

    def _commit_or_execute(self) -> None:
        text = self._edit.text()
        result = self._parser.parse(text)

        # 1. Exact nickname → run stored action.
        if result.completion_kind == "nickname" and result.nickname_action_name:
            spec = self._parser._registry.get_by_name(result.nickname_action_name)
            if spec is None:
                self._set_error("Unknown command")
                return
            args = dict(result.nickname_args or {})
            spec.runner(args)
            if self._on_action_executed:
                self._on_action_executed(result.nickname_action_name, args)
            self.hide()
            return

        # 2. Complete command (all slots committed) → execute.
        if self._result_is_fully_committed(result):
            self._execute_result(result)
            return

        # 3. Incomplete + a row highlighted → commit that row and advance.
        item = self._list.currentItem()
        if result.suggestions and item is not None:
            row_text = item.text()
            # If the row is a nickname, execute it directly. _commit would append a trailing space
            # which prevents the parser's exact-nickname check from firing on a second Enter.
            nick_store = self._parser._nickname_store
            if nick_store is not None:
                entry = nick_store.get(row_text)
                if entry is not None:
                    spec = self._parser._registry.get_by_name(entry.action_name)
                    if spec is not None:
                        args = dict(entry.args)
                        spec.runner(args)
                        if self._on_action_executed:
                            self._on_action_executed(entry.action_name, args)
                        self.hide()
                        return
            self._edit.setText(self._commit(text, row_text))
            return

        # 4. Nothing to commit → flag invalid.
        self._set_invalid(True)
        self._set_error("No matching option")

    def _on_item_clicked(self, item) -> None:
        """Single click: commit the clicked row; if that completes the command, execute immediately."""
        self._list.setCurrentItem(item)
        text = self._edit.text()
        result = self._parser.parse(text)

        # Nickname: delegate directly — _commit would append a trailing space and break the match.
        if result.completion_kind == "nickname":
            self._commit_or_execute()
            return

        # Look ahead: if this click would commit (path 3) and the committed text
        # would be immediately executable, do commit+execute in one shot.
        if result.suggestions and not self._result_is_fully_committed(result):
            new_text = self._commit(text, item.text())
            new_result = self._parser.parse(new_text)
            if self._result_is_fully_committed(new_result):
                self._edit.setText(new_text)
                self._execute_result(new_result)
                return

        self._commit_or_execute()

    # ------------------------------------------------------------------
    # Event filter
    # ------------------------------------------------------------------

    def eventFilter(self, obj, event):
        if obj is self._edit and event.type() == QEvent.KeyPress:
            key = event.key()
            if key == Qt.Key_Escape:
                self.hide()
                return True
            if key == Qt.Key_Tab:
                self._commit_or_execute()
                return True
            if key in (Qt.Key_Return, Qt.Key_Enter):
                self._commit_or_execute()
                return True
            if key in (Qt.Key_Down, Qt.Key_Up):
                if key == Qt.Key_Down:
                    row = min(self._list.currentRow() + 1, self._list.count() - 1)
                    if row >= 0:
                        self._list.setCurrentRow(row)
                else:
                    row = max(self._list.currentRow() - 1, 0)
                    if self._list.count() > 0:
                        self._list.setCurrentRow(row)
                return True
        return super().eventFilter(obj, event)
