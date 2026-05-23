"""
Tk 9.0 / macOS trackpad scroll fix.

CTkScrollableFrame binds <MouseWheel> for scrolling, but Tk 9.0 on macOS
delivers trackpad gestures as <TouchpadScroll> instead. Call
`attach_scroll_fix(window, scroll_frame)` after creating a CTkScrollableFrame
inside any CTkToplevel or CTkFrame to restore trackpad and mouse-wheel scrolling.
"""


def attach_scroll_fix(window, scroll_frame):
    """Bind touchpad and mouse-wheel scroll events on *window* to *scroll_frame*."""

    def _on_touchpad_scroll(event):
        # event.delta packs two signed 16-bit values: hi word = x, lo word = y
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

    window.bind("<TouchpadScroll>", _on_touchpad_scroll, add="+")
    window.bind("<MouseWheel>", _on_mouse_wheel, add="+")
