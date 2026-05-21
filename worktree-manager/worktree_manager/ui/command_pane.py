import customtkinter as ctk
from worktree_manager.command_runner import RunHandle, RunStatus

_STATUS_COLORS = {
    RunStatus.RUNNING: "green",
    RunStatus.STOPPED: "gray",
    RunStatus.ERROR: "red",
}

_STATUS_DOTS = {
    RunStatus.RUNNING: "●",
    RunStatus.STOPPED: "○",
    RunStatus.ERROR: "✕",
}


class CommandPane(ctk.CTkFrame):
    def __init__(self, master, handle: RunHandle, on_maximize, on_stop, on_restart, on_remove=None, show_popout_btn=True):
        super().__init__(master, corner_radius=6, border_width=1)
        self._handle = handle
        self._on_maximize = on_maximize
        self._on_stop = on_stop
        self._on_restart = on_restart
        self._on_remove = on_remove
        self._show_popout_btn = show_popout_btn
        self._status = handle.status
        self._find_visible = False
        self._find_matches: list[str] = []
        self._find_cursor = 0
        self._build()

    def _build(self):
        self._header = ctk.CTkFrame(self, corner_radius=0)
        self._header.pack(fill="x", padx=4, pady=(4, 0))

        self._dot_label = ctk.CTkLabel(
            self._header,
            text=_STATUS_DOTS[self._status],
            text_color=_STATUS_COLORS[self._status],
            width=16,
        )
        self._dot_label.pack(side="left", padx=(4, 2))

        wt_name = self._handle.worktree_path.split("/")[-1]
        label_text = f"{self._handle.cmd_name} · {self._handle.repo_name} : {wt_name}"
        self._label = ctk.CTkLabel(self._header, text=label_text, anchor="w")
        self._label.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(self._header, text="✕", width=28, command=self.trigger_remove,
                      fg_color="transparent", text_color="gray").pack(side="right", padx=1)
        ctk.CTkButton(self._header, text="🔍", width=28, command=self.show_find_bar).pack(side="right", padx=1)
        ctk.CTkButton(self._header, text="⎘", width=28, command=self.trigger_copy).pack(side="right", padx=1)
        ctk.CTkButton(self._header, text="■", width=28, command=self.trigger_stop).pack(side="right", padx=1)
        ctk.CTkButton(self._header, text="⟳", width=28, command=self.trigger_restart).pack(side="right", padx=1)
        if self._show_popout_btn:
            ctk.CTkButton(self._header, text="⤢", width=28, command=self.trigger_maximize).pack(side="right", padx=1)

        self._find_bar = ctk.CTkFrame(self, corner_radius=0)
        self._find_entry = ctk.CTkEntry(self._find_bar, placeholder_text="🔍 search...")
        self._find_entry.pack(side="left", fill="x", expand=True, padx=4, pady=2)
        self._find_count_label = ctk.CTkLabel(self._find_bar, text="", width=80)
        self._find_count_label.pack(side="left")
        ctk.CTkButton(self._find_bar, text="↑", width=28, command=self._find_prev).pack(side="left", padx=1)
        ctk.CTkButton(self._find_bar, text="↓", width=28, command=self._find_next).pack(side="left", padx=1)
        ctk.CTkButton(self._find_bar, text="×", width=28, command=self.hide_find_bar).pack(side="left", padx=1)
        self._find_entry.bind("<Return>", lambda e: self._find_next())
        self._find_entry.bind("<Escape>", lambda e: self.hide_find_bar())
        self._find_entry.bind("<KeyRelease>", lambda e: self._apply_find())

        self._textbox = ctk.CTkTextbox(self, height=140, wrap="none", state="disabled")
        self._textbox.pack(fill="both", expand=True, padx=4, pady=4)
        self._textbox.bind("<Control-f>", lambda e: self.show_find_bar())

    # --- public API ---

    def header_text(self) -> str:
        return self._label.cget("text")

    def append_line(self, line: str) -> None:
        self._textbox.configure(state="normal")
        self._textbox.insert("end", line + "\n")
        self._textbox.configure(state="disabled")
        self._textbox.see("end")
        if self._find_visible:
            self._apply_find()

    def get_output_text(self) -> str:
        return self._textbox.get("1.0", "end")

    def clear_output(self) -> None:
        self._textbox.configure(state="normal")
        self._textbox.delete("1.0", "end")
        self._textbox.configure(state="disabled")

    def set_status(self, status: RunStatus) -> None:
        self._status = status
        self._dot_label.configure(
            text=_STATUS_DOTS[status],
            text_color=_STATUS_COLORS[status],
        )

    def status_dot_color(self) -> str:
        return _STATUS_COLORS[self._status]

    def trigger_remove(self) -> None:
        if self._on_remove:
            self._on_remove()

    def trigger_stop(self) -> None:
        self._on_stop()

    def trigger_restart(self) -> None:
        self._on_restart()

    def trigger_maximize(self) -> None:
        self._on_maximize(self)

    def trigger_copy(self) -> None:
        text = self.get_output_text()
        self.clipboard_clear()
        self.clipboard_append(text)

    def show_find_bar(self) -> None:
        self._find_bar.pack(fill="x", padx=4, after=self._header)
        self._find_visible = True
        self._find_entry.focus_set()

    def hide_find_bar(self) -> None:
        self._find_bar.pack_forget()
        self._find_visible = False
        self._textbox.tag_remove("search_highlight", "1.0", "end")
        self._find_count_label.configure(text="")

    def find_bar_visible(self) -> bool:
        return self._find_visible

    def find(self, query: str) -> int:
        tb = self._textbox._textbox
        tb.tag_remove("search_highlight", "1.0", "end")
        self._find_matches = []
        if not query:
            return 0
        tb.tag_configure("search_highlight", background="yellow", foreground="black")
        start = "1.0"
        while True:
            pos = tb.search(query, start, stopindex="end", nocase=True)
            if not pos:
                break
            end = f"{pos}+{len(query)}c"
            tb.tag_add("search_highlight", pos, end)
            self._find_matches.append(pos)
            start = end
        return len(self._find_matches)

    # --- private helpers ---

    def _apply_find(self) -> None:
        query = self._find_entry.get() if self._find_visible else ""
        count = self.find(query)
        self._find_cursor = 0
        self._find_count_label.configure(
            text=f"{count} match{'es' if count != 1 else ''}" if query else ""
        )

    def _find_next(self) -> None:
        if not self._find_matches:
            return
        self._find_cursor = (self._find_cursor + 1) % len(self._find_matches)
        self._textbox._textbox.see(self._find_matches[self._find_cursor])

    def _find_prev(self) -> None:
        if not self._find_matches:
            return
        self._find_cursor = (self._find_cursor - 1) % len(self._find_matches)
        self._textbox._textbox.see(self._find_matches[self._find_cursor])
