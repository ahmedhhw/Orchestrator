"""
GlobalHotkey — Carbon-based global hotkey registration for macOS.

On non-darwin platforms, register() is a no-op returning False.
On darwin, registers a Carbon EventHotKey that fires even when the app is
minimised or backgrounded.

The Carbon C-callback fires on an OS thread.  To stay Qt-thread-safe we make
GlobalHotkey a QObject with a Qt signal; the ctypes callback emits the signal,
and the caller connects to it with Qt.ConnectionType.QueuedConnection so the
slot always runs on the Qt main thread.

IMPORTANT: keep a Python-level reference to the ctypes CFUNCTYPE callback
object (self._cb).  If it is garbage-collected the hotkey silently stops
firing.
"""

import ctypes
import sys

from PySide6.QtCore import QObject, Signal


def _build_carbon_bindings():
    """Build and return Carbon ctypes bindings.  Call only on darwin."""
    carbon = ctypes.CDLL(
        "/System/Library/Frameworks/Carbon.framework/Carbon"
    )

    OSStatus             = ctypes.c_int32
    EventHandlerCallRef  = ctypes.c_void_p
    EventRef             = ctypes.c_void_p
    EventTargetRef       = ctypes.c_void_p
    EventHandlerRef      = ctypes.c_void_p
    EventHotKeyRef       = ctypes.c_void_p

    class EventHotKeyID(ctypes.Structure):
        _fields_ = [("signature", ctypes.c_uint32), ("id", ctypes.c_uint32)]

    class EventTypeSpec(ctypes.Structure):
        _fields_ = [("eventClass", ctypes.c_uint32),
                    ("eventKind",  ctypes.c_uint32)]

    HANDLER_FUNC = ctypes.CFUNCTYPE(
        OSStatus,
        EventHandlerCallRef,
        EventRef,
        ctypes.c_void_p,
    )

    carbon.GetApplicationEventTarget.restype  = EventTargetRef
    carbon.GetApplicationEventTarget.argtypes = []

    carbon.InstallEventHandler.restype  = OSStatus
    carbon.InstallEventHandler.argtypes = [
        EventTargetRef,
        HANDLER_FUNC,
        ctypes.c_uint32,
        ctypes.POINTER(EventTypeSpec),
        ctypes.c_void_p,
        ctypes.POINTER(EventHandlerRef),
    ]

    carbon.RegisterEventHotKey.restype  = OSStatus
    carbon.RegisterEventHotKey.argtypes = [
        ctypes.c_uint32,
        ctypes.c_uint32,
        EventHotKeyID,
        EventTargetRef,
        ctypes.c_uint32,
        ctypes.POINTER(EventHotKeyRef),
    ]

    carbon.UnregisterEventHotKey.restype  = OSStatus
    carbon.UnregisterEventHotKey.argtypes = [EventHotKeyRef]

    # kEventClassKeyboard = 'keyb'; kEventHotKeyPressed = 5
    return {
        "carbon":        carbon,
        "OSStatus":      OSStatus,
        "EventHotKeyID": EventHotKeyID,
        "EventTypeSpec": EventTypeSpec,
        "EventHandlerRef": EventHandlerRef,
        "EventHotKeyRef":  EventHotKeyRef,
        "HANDLER_FUNC":  HANDLER_FUNC,
        "kEventClassKeyboard": 0x6B657962,
        "kEventHotKeyPressed": 5,
    }


class GlobalHotkey(QObject):
    """Registers and manages a single Carbon EventHotKey.

    Usage::

        gh = GlobalHotkey()
        gh.triggered.connect(handler, Qt.ConnectionType.QueuedConnection)
        gh.register(keycode, modmask)   # -> True on success
        ...
        gh.unregister()
    """

    triggered = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cb = None          # keep Python ref so ctypes callback isn't GC'd
        self._ref = None         # EventHotKeyRef
        self._handler_ref = None # EventHandlerRef
        self._fn = None          # plain callable set via set_callback()
        self._bindings = None    # populated lazily on darwin

        if sys.platform == "darwin":
            self._bindings = _build_carbon_bindings()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_callback(self, fn) -> None:
        """Set a plain callable to invoke when the hotkey fires.

        The call is routed through self.triggered (a queued signal), so
        fn() will always execute on the Qt main thread.
        """
        if self._fn is not None:
            try:
                self.triggered.disconnect(self._fn)
            except RuntimeError:
                pass
        self._fn = fn
        if fn is not None:
            self.triggered.connect(fn)

    def register(self, keycode: int, modmask: int) -> bool:
        """Register the given (keycode, modmask) as a global hotkey.

        Returns True on success, False on non-darwin platforms.
        Unregisters any previously registered hotkey first.
        Raises RuntimeError if the Carbon call fails.
        """
        if sys.platform != "darwin":
            return False

        self.unregister()
        return self._register_carbon(keycode, modmask)

    def unregister(self) -> None:
        """Unregister the current hotkey (no-op if none registered)."""
        if sys.platform != "darwin":
            return
        if self._ref is not None:
            b = self._bindings
            b["carbon"].UnregisterEventHotKey(self._ref)
            self._ref = None

    # ------------------------------------------------------------------
    # Internal: Carbon registration
    # ------------------------------------------------------------------

    def _register_carbon(self, keycode: int, modmask: int) -> bool:
        b = self._bindings

        def _handler(handler_call_ref, event_ref, user_data):
            # Fires on a Carbon/OS thread — emit queued signal to hop to Qt.
            self.triggered.emit()
            return 0  # noErr

        # Keep Python ref alive so ctypes callback isn't GC'd.
        self._cb = b["HANDLER_FUNC"](_handler)

        carbon       = b["carbon"]
        EventTypeSpec  = b["EventTypeSpec"]
        EventHandlerRef = b["EventHandlerRef"]
        EventHotKeyID  = b["EventHotKeyID"]
        EventHotKeyRef = b["EventHotKeyRef"]

        target = carbon.GetApplicationEventTarget()

        event_spec   = EventTypeSpec(b["kEventClassKeyboard"], b["kEventHotKeyPressed"])
        handler_ref  = EventHandlerRef()

        install_status = carbon.InstallEventHandler(
            target,
            self._cb,
            ctypes.c_uint32(1),
            ctypes.byref(event_spec),
            None,
            ctypes.byref(handler_ref),
        )
        if install_status != 0:
            # Surfaces to caller as False; UI shows "Local only"
            import sys as _sys
            print(
                f"[GlobalHotkey] InstallEventHandler OSStatus {install_status}",
                file=_sys.stderr,
            )
            return False
        self._handler_ref = handler_ref

        # Unique signature 'WMHP', id=1
        hk_id = EventHotKeyID(signature=0x574D4850, id=1)
        ref   = EventHotKeyRef()

        status = carbon.RegisterEventHotKey(
            ctypes.c_uint32(keycode),
            ctypes.c_uint32(modmask),
            hk_id,
            target,
            ctypes.c_uint32(0),
            ctypes.byref(ref),
        )
        if status != 0:
            # Surfaces to caller as False; UI shows "Local only"
            import sys as _sys
            print(
                f"[GlobalHotkey] RegisterEventHotKey OSStatus {status}",
                file=_sys.stderr,
            )
            return False
        self._ref = ref
        return True
