"""Tests for hover-scoped scroll fix behaviour."""
import pytest
from unittest.mock import MagicMock, call, patch


class FakeCanvas:
    def __init__(self):
        self._yview = (0.0, 0.8)
        self._xview = (0.0, 0.8)
        self.yview_calls = []
        self.xview_calls = []

    def yview(self):
        return self._yview

    def xview(self):
        return self._xview

    def yview_scroll(self, amount, unit):
        self.yview_calls.append((amount, unit))

    def xview_scroll(self, amount, unit):
        self.xview_calls.append((amount, unit))


class FakeRoot:
    def __init__(self):
        self._bindings = {}

    def bind(self, event, handler, add=None):
        self._bindings[event] = handler

    def unbind(self, event):
        self._bindings.pop(event, None)

    def has_binding(self, event):
        return event in self._bindings


class FakeScrollFrame:
    def __init__(self, root, canvas=None):
        self._root = root
        self._parent_canvas = canvas or FakeCanvas()
        self._bindings = {}
        self._children = []
        self._winfo_x = 0
        self._winfo_y = 0
        self._winfo_width = 200
        self._winfo_height = 400

    def winfo_toplevel(self):
        return self._root

    def bind(self, event, handler, add=None):
        self._bindings[event] = handler

    def winfo_containing(self, x, y):
        # Return self if x,y is inside the frame's bounds, else None
        if (self._winfo_x <= x < self._winfo_x + self._winfo_width and
                self._winfo_y <= y < self._winfo_y + self._winfo_height):
            return self
        return None

    def winfo_rootx(self):
        return self._winfo_x

    def winfo_rooty(self):
        return self._winfo_y

    def simulate_enter(self):
        if "<Enter>" in self._bindings:
            self._bindings["<Enter>"](MagicMock())

    def simulate_leave(self, x_outside=999, y_outside=999):
        if "<Leave>" in self._bindings:
            evt = MagicMock()
            evt.x_root = x_outside
            evt.y_root = y_outside
            self._bindings["<Leave>"](evt)

    def simulate_leave_to_child(self):
        # Simulate leaving to a child widget — winfo_containing returns a child
        if "<Leave>" in self._bindings:
            evt = MagicMock()
            # Position inside the frame bounds
            evt.x_root = self._winfo_x + 10
            evt.y_root = self._winfo_y + 10
            self._bindings["<Leave>"](evt)

    def simulate_destroy(self):
        if "<Destroy>" in self._bindings:
            self._bindings["<Destroy>"](MagicMock())


# ---------------------------------------------------------------------------
# Tests: API — attach_scroll_fix takes only scroll_frame
# ---------------------------------------------------------------------------

def test_attach_scroll_fix_takes_single_argument():
    from worktree_manager.ui.scroll_fix import attach_scroll_fix
    import inspect
    sig = inspect.signature(attach_scroll_fix)
    params = list(sig.parameters.keys())
    assert params == ["scroll_frame"], f"Expected single 'scroll_frame' param, got {params}"


# ---------------------------------------------------------------------------
# Tests: bindings are NOT active before Enter
# ---------------------------------------------------------------------------

def test_no_root_bindings_before_mouse_enter():
    from worktree_manager.ui.scroll_fix import attach_scroll_fix
    root = FakeRoot()
    frame = FakeScrollFrame(root)
    attach_scroll_fix(frame)
    assert not root.has_binding("<TouchpadScroll>")
    assert not root.has_binding("<MouseWheel>")


# ---------------------------------------------------------------------------
# Tests: bindings are added on Enter, removed on Leave
# ---------------------------------------------------------------------------

def test_root_bindings_added_on_enter():
    from worktree_manager.ui.scroll_fix import attach_scroll_fix
    root = FakeRoot()
    frame = FakeScrollFrame(root)
    attach_scroll_fix(frame)
    frame.simulate_enter()
    assert root.has_binding("<TouchpadScroll>")
    assert root.has_binding("<MouseWheel>")


def test_root_bindings_removed_on_leave():
    from worktree_manager.ui.scroll_fix import attach_scroll_fix
    root = FakeRoot()
    frame = FakeScrollFrame(root)
    attach_scroll_fix(frame)
    frame.simulate_enter()
    frame.simulate_leave()  # x,y outside frame bounds
    assert not root.has_binding("<TouchpadScroll>")
    assert not root.has_binding("<MouseWheel>")


def test_root_bindings_kept_when_leaving_to_child_widget():
    from worktree_manager.ui.scroll_fix import attach_scroll_fix
    root = FakeRoot()
    # Frame covers (0,0)-(200,400); child transition stays within bounds
    frame = FakeScrollFrame(root)
    attach_scroll_fix(frame)
    frame.simulate_enter()
    frame.simulate_leave_to_child()  # coordinates still inside frame
    assert root.has_binding("<TouchpadScroll>")
    assert root.has_binding("<MouseWheel>")


# ---------------------------------------------------------------------------
# Tests: bindings removed on Destroy
# ---------------------------------------------------------------------------

def test_root_bindings_removed_on_destroy():
    from worktree_manager.ui.scroll_fix import attach_scroll_fix
    root = FakeRoot()
    frame = FakeScrollFrame(root)
    attach_scroll_fix(frame)
    frame.simulate_enter()
    frame.simulate_destroy()
    assert not root.has_binding("<TouchpadScroll>")
    assert not root.has_binding("<MouseWheel>")


# ---------------------------------------------------------------------------
# Tests: scroll events actually scroll the canvas
# ---------------------------------------------------------------------------

def test_touchpad_scroll_scrolls_canvas_y():
    from worktree_manager.ui.scroll_fix import attach_scroll_fix
    root = FakeRoot()
    canvas = FakeCanvas()
    frame = FakeScrollFrame(root, canvas)
    attach_scroll_fix(frame)
    frame.simulate_enter()

    evt = MagicMock()
    # y_delta = 3 (lo word), x_delta = 0 (hi word)
    evt.delta = 3
    root._bindings["<TouchpadScroll>"](evt)

    assert len(canvas.yview_calls) == 1
    assert canvas.yview_calls[0] == (-3, "units")


def test_touchpad_scroll_scrolls_canvas_x():
    from worktree_manager.ui.scroll_fix import attach_scroll_fix
    root = FakeRoot()
    canvas = FakeCanvas()
    frame = FakeScrollFrame(root, canvas)
    attach_scroll_fix(frame)
    frame.simulate_enter()

    evt = MagicMock()
    # x_delta = 2 in hi word, y_delta = 0
    evt.delta = (2 << 16)
    root._bindings["<TouchpadScroll>"](evt)

    assert len(canvas.xview_calls) == 1
    assert canvas.xview_calls[0] == (-2, "units")


def test_mouse_wheel_scrolls_canvas_y():
    from worktree_manager.ui.scroll_fix import attach_scroll_fix
    root = FakeRoot()
    canvas = FakeCanvas()
    frame = FakeScrollFrame(root, canvas)
    attach_scroll_fix(frame)
    frame.simulate_enter()

    evt = MagicMock()
    evt.delta = 5
    root._bindings["<MouseWheel>"](evt)

    assert len(canvas.yview_calls) == 1
    assert canvas.yview_calls[0] == (-5, "units")


def test_scroll_does_not_fire_after_leave():
    from worktree_manager.ui.scroll_fix import attach_scroll_fix
    root = FakeRoot()
    canvas = FakeCanvas()
    frame = FakeScrollFrame(root, canvas)
    attach_scroll_fix(frame)
    frame.simulate_enter()
    frame.simulate_leave()
    # No bindings left — scrolling would be a no-op (nothing to call)
    assert not root.has_binding("<TouchpadScroll>")
    assert not root.has_binding("<MouseWheel>")
    assert canvas.yview_calls == []


# ---------------------------------------------------------------------------
# Tests: two frames do not interfere with each other
# ---------------------------------------------------------------------------

def test_two_frames_only_active_frame_scrolls():
    from worktree_manager.ui.scroll_fix import attach_scroll_fix
    root = FakeRoot()
    canvas_a = FakeCanvas()
    canvas_b = FakeCanvas()
    frame_a = FakeScrollFrame(root, canvas_a)
    frame_b = FakeScrollFrame(root, canvas_b)
    attach_scroll_fix(frame_a)
    attach_scroll_fix(frame_b)

    # Mouse enters frame_a
    frame_a.simulate_enter()

    evt = MagicMock()
    evt.delta = 2
    root._bindings["<TouchpadScroll>"](evt)

    assert len(canvas_a.yview_calls) == 1
    assert len(canvas_b.yview_calls) == 0

    # Mouse leaves frame_a, enters frame_b
    frame_a.simulate_leave()
    frame_b.simulate_enter()

    evt2 = MagicMock()
    evt2.delta = 3
    root._bindings["<TouchpadScroll>"](evt2)

    assert len(canvas_a.yview_calls) == 1   # unchanged
    assert len(canvas_b.yview_calls) == 1
