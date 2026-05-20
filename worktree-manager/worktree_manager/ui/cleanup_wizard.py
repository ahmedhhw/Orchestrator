import time
import customtkinter as ctk
from worktree_manager.models import CleanupCandidate

_FILTER_ALL = "All"
_FILTER_STALE = "Stale"
_FILTER_MERGED = "Merged"


def _fmt_age(ts: int) -> str:
    if ts == 0:
        return "no commits"
    diff = int(time.time()) - ts
    return f"{diff // 86400}d"


def _reason(c) -> str:
    if c.is_merged:
        target = c.merged_into or "main"
        return f"merged into {target}"
    if c.is_stale:
        return f"{_fmt_age(c.last_commit_ts)}, stale"
    return f"{_fmt_age(c.last_commit_ts)} ago"


def _sort_candidates(candidates: list) -> list:
    priority = [c for c in candidates if c.is_stale or c.is_merged]
    healthy = [c for c in candidates if not c.is_stale and not c.is_merged]
    return priority + healthy


def _bind_mousewheel(widget):
    """Recursively bind mouse-wheel scrolling to a CTkScrollableFrame."""
    import platform

    def _on_wheel(event):
        # Find the underlying canvas in the CTkScrollableFrame
        for child in widget.winfo_children():
            if child.winfo_class() == "Canvas":
                if platform.system() == "Darwin":
                    child.yview_scroll(-1 * event.delta, "units")
                else:
                    child.yview_scroll(-1 * (event.delta // 120), "units")
                break

    widget.bind("<MouseWheel>", _on_wheel)
    widget.bind("<Button-4>", lambda e: _on_wheel_linux(widget, -1))
    widget.bind("<Button-5>", lambda e: _on_wheel_linux(widget, 1))


def _on_wheel_linux(widget, direction):
    for child in widget.winfo_children():
        if child.winfo_class() == "Canvas":
            child.yview_scroll(direction, "units")
            break


class CleanupWizard(ctk.CTkToplevel):
    def __init__(self, master, candidates: list, on_delete_selected):
        super().__init__(master)
        self.title("Cleanup Wizard")
        self.resizable(False, False)
        self._on_delete_selected = on_delete_selected
        self._vars: list = []
        self._candidates: list = []
        self._also_branches = ctk.BooleanVar(value=False)
        self._filter = ctk.StringVar(value=_FILTER_ALL)

        self._all_worktree = _sort_candidates([c for c in candidates if c.path is not None])
        self._all_branch = _sort_candidates([c for c in candidates if c.path is None])

        self._build()

    def _apply_filter(self, candidates: list) -> list:
        f = self._filter.get()
        if f == _FILTER_STALE:
            return [c for c in candidates if c.is_stale and not c.is_merged]
        if f == _FILTER_MERGED:
            return [c for c in candidates if c.is_merged]
        return candidates

    def _rebuild_lists(self):
        """Re-render both scrollable sections when the filter changes."""
        self._vars.clear()
        self._candidates.clear()
        self._worktree_scroll_frame.destroy()
        self._branch_scroll_frame.destroy()
        self._also_branches_cb.destroy()

        self._worktree_scroll_frame, self._also_branches_cb = self._build_section(
            candidates=self._apply_filter(self._all_worktree),
            show_also_branches=True,
            insert_before=self._branch_label_frame,
        )
        self._branch_scroll_frame, _ = self._build_section(
            candidates=self._apply_filter(self._all_branch),
            show_also_branches=False,
            insert_before=self._btn_frame,
        )

    def _build(self):
        ctk.CTkLabel(
            self, text="Cleanup Wizard", font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=(20, 4))

        # Filter tabs
        filter_row = ctk.CTkFrame(self, fg_color="transparent")
        filter_row.pack(fill="x", padx=24, pady=(0, 8))
        for label in (_FILTER_ALL, _FILTER_STALE, _FILTER_MERGED):
            ctk.CTkRadioButton(
                filter_row, text=label, variable=self._filter, value=label,
                command=self._rebuild_lists,
            ).pack(side="left", padx=(0, 12))

        self._worktree_label_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._worktree_label_frame.pack(fill="x", padx=24, pady=(4, 0))
        ctk.CTkLabel(
            self._worktree_label_frame, text="Worktrees",
            font=ctk.CTkFont(weight="bold"), anchor="w",
        ).pack(side="left")

        self._branch_label_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._branch_label_frame.pack(fill="x", padx=24, pady=(8, 0))
        ctk.CTkLabel(
            self._branch_label_frame, text="Branches (no worktree)",
            font=ctk.CTkFont(weight="bold"), anchor="w",
        ).pack(side="left")

        self._btn_frame = ctk.CTkFrame(self)
        self._btn_frame.pack(fill="x", padx=24, pady=16)

        # Sections are inserted before their respective anchor widgets
        self._worktree_scroll_frame, self._also_branches_cb = self._build_section(
            candidates=self._apply_filter(self._all_worktree),
            show_also_branches=True,
            insert_before=self._branch_label_frame,
        )

        self._branch_scroll_frame, _ = self._build_section(
            candidates=self._apply_filter(self._all_branch),
            show_also_branches=False,
            insert_before=self._btn_frame,
        )
        ctk.CTkButton(
            self._btn_frame, text="Select All", fg_color="gray", command=self._select_all
        ).pack(side="left", padx=(0, 4))
        ctk.CTkButton(
            self._btn_frame, text="Deselect All", fg_color="gray", command=self._deselect_all
        ).pack(side="left")
        ctk.CTkButton(
            self._btn_frame, text="Cancel", fg_color="gray", command=self.destroy
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            self._btn_frame, text="Delete", fg_color="#c0392b", command=self._delete_selected
        ).pack(side="right")

    def _build_section(self, candidates: list, show_also_branches: bool, insert_before=None):
        """Build scrollable list + optional checkbox. Returns (scroll_container, checkbox_widget)."""
        pack_opts = {"fill": "x", "padx": 24, "pady": (2, 4)}
        if insert_before is not None:
            pack_opts["before"] = insert_before

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(**pack_opts)

        if not candidates:
            ctk.CTkLabel(
                container, text="(none to show)", text_color="gray", anchor="w"
            ).pack(fill="x", pady=2)
        else:
            scroll = ctk.CTkScrollableFrame(container, height=140)
            scroll.pack(fill="x")
            _bind_mousewheel(scroll)

            priority = [c for c in candidates if c.is_stale or c.is_merged]
            healthy = [c for c in candidates if not c.is_stale and not c.is_merged]

            for c in priority:
                self._add_item(scroll, c, pre_checked=True)

            if healthy:
                ctk.CTkFrame(scroll, height=1, fg_color="gray50").pack(fill="x", pady=(6, 2))
                ctk.CTkLabel(
                    scroll, text="Healthy:", text_color="gray",
                    font=ctk.CTkFont(size=11), anchor="w"
                ).pack(fill="x", padx=4, pady=(0, 2))
                for c in healthy:
                    self._add_item(scroll, c, pre_checked=False)

        cb_pack_opts = {"anchor": "w", "padx": 24, "pady": (4, 2)}
        if insert_before is not None:
            cb_pack_opts["before"] = insert_before

        cb_widget = ctk.CTkFrame(self, fg_color="transparent", height=0)  # placeholder
        if show_also_branches:
            priority_items = [c for c in candidates if c.is_stale or c.is_merged]
            has_priority = bool(priority_items)
            self._also_branches = ctk.BooleanVar(value=has_priority)
            cb_widget = ctk.CTkCheckBox(
                self, text="Also delete their branches", variable=self._also_branches
            )
            cb_widget.pack(**cb_pack_opts)

        return container, cb_widget

    def _add_item(self, parent, c: CleanupCandidate, pre_checked: bool):
        blocked = c.has_uncommitted
        var = ctk.BooleanVar(value=False if blocked else pre_checked)
        self._vars.append(var)
        self._candidates.append(c)
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=2)
        cb = ctk.CTkCheckBox(
            row, text=f"{c.branch}  ({_reason(c)})", variable=var
        )
        cb.pack(side="left", padx=4)
        if blocked:
            cb.configure(state="disabled")
            ctk.CTkLabel(
                row, text="⚠ uncommitted", text_color="orange",
                font=ctk.CTkFont(size=11),
            ).pack(side="left", padx=(6, 0))

    def _select_all(self):
        for v in self._vars:
            v.set(True)

    def _deselect_all(self):
        for v in self._vars:
            v.set(False)

    def _delete_selected(self):
        selected = [c for c, v in zip(self._candidates, self._vars) if v.get()]
        self._on_delete_selected(selected, self._also_branches.get())
        self.destroy()
