"""
Tk 9.0 / macOS trackpad scroll fix — hover-scoped.

CTkScrollableFrame binds <MouseWheel> for scrolling, but Tk 9.0 on macOS
delivers trackpad gestures as <TouchpadScroll> instead. Call
`attach_scroll_fix(scroll_frame)` after creating a CTkScrollableFrame to
restore trackpad and mouse-wheel scrolling. Root-level bindings are only
active while the mouse is inside the frame, so multiple scroll frames in
the same window work independently.
"""


def attach_scroll_fix(scroll_frame):
    """Bind hover-scoped touchpad and mouse-wheel scroll events for *scroll_frame*."""

    def _on_touchpad_scroll(event):
        raw = event.delta
        x_delta = (raw >> 16) & 0xFFFF
        y_delta = raw & 0xFFFF
        if x_delta >= 0x8000:
            x_delta -= 0x10000
        if y_delta >= 0x8000:
            y_delta -= 0x10000
        canvas = scroll_frame._parent_canvas
        if y_delta and canvas.yview() != (0.0, 1.0):
            canvas.yview_scroll(-y_delta, "units")
        if x_delta and canvas.xview() != (0.0, 1.0):
            canvas.xview_scroll(-x_delta, "units")

    def _on_mouse_wheel(event):
        canvas = scroll_frame._parent_canvas
        if canvas.yview() != (0.0, 1.0):
            canvas.yview_scroll(-event.delta, "units")

    def _register():
        root = scroll_frame.winfo_toplevel()
        root.bind("<TouchpadScroll>", _on_touchpad_scroll, add="+")
        root.bind("<MouseWheel>", _on_mouse_wheel, add="+")

    def _unregister():
        root = scroll_frame.winfo_toplevel()
        root.unbind("<TouchpadScroll>")
        root.unbind("<MouseWheel>")

    def _on_enter(event):
        _register()

    def _on_leave(event):
        # Only unregister when the mouse truly left the subtree, not when it
        # moved to a child widget inside the frame.
        widget_under = scroll_frame.winfo_containing(event.x_root, event.y_root)
        if widget_under is None or not _is_descendant(widget_under, scroll_frame):
            _unregister()

    def _on_destroy(event):
        _unregister()

    scroll_frame.bind("<Enter>", _on_enter, add="+")
    scroll_frame.bind("<Leave>", _on_leave, add="+")
    scroll_frame.bind("<Destroy>", _on_destroy, add="+")


def _is_descendant(widget, ancestor):
    """Return True if *widget* is *ancestor* or a descendant of it."""
    try:
        # Walk up the widget hierarchy via winfo_parent
        w = widget
        while w is not None:
            if w is ancestor:
                return True
            parent_name = w.winfo_parent()
            if not parent_name:
                break
            w = w.nametowidget(parent_name)
    except Exception:
        pass
    return False
