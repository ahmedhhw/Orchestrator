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


def _merge_sort_key(c) -> tuple:
    target = (c.merged_into or "main").lower()
    return (target, c.branch.lower())


def _group_candidates(candidates: list) -> dict:
    merged = [c for c in candidates if c.is_merged]
    stale = [c for c in candidates if c.is_stale and not c.is_merged]
    healthy = [c for c in candidates if not c.is_stale and not c.is_merged]
    merged.sort(key=_merge_sort_key)
    stale.sort(key=lambda c: c.last_commit_ts)
    return {"merged": merged, "stale": stale, "healthy": healthy}


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
        self._all_pairs: list = []
        self._also_branches = ctk.BooleanVar(value=False)
        self._filter = ctk.StringVar(value=_FILTER_ALL)

        self._all_worktree_grouped = _group_candidates([c for c in candidates if c.path is not None])
        self._all_branch_grouped = _group_candidates([c for c in candidates if c.path is None])

        all_candidates = (
            self._all_worktree_grouped["merged"] +
            self._all_worktree_grouped["stale"] +
            self._all_worktree_grouped["healthy"] +
            self._all_branch_grouped["merged"] +
            self._all_branch_grouped["stale"] +
            self._all_branch_grouped["healthy"]
        )
        for c in all_candidates:
            is_priority = c.is_stale or c.is_merged
            var = ctk.BooleanVar(value=False if c.has_uncommitted else is_priority)
            self._all_pairs.append((c, var))

        self._build()

    @property
    def _candidates(self) -> list:
        grouped_wt = self._apply_filter(self._all_worktree_grouped)
        grouped_br = self._apply_filter(self._all_branch_grouped)
        visible = (
            grouped_wt["merged"] + grouped_wt["stale"] + grouped_wt["healthy"] +
            grouped_br["merged"] + grouped_br["stale"] + grouped_br["healthy"]
        )
        return visible

    @property
    def _vars(self) -> list:
        visible = set(id(c) for c in self._candidates)
        return [v for c, v in self._all_pairs if id(c) in visible]

    def _apply_filter(self, grouped: dict) -> dict:
        f = self._filter.get()
        if f == _FILTER_STALE:
            return {"merged": [], "stale": grouped["stale"], "healthy": []}
        if f == _FILTER_MERGED:
            return {"merged": grouped["merged"], "stale": [], "healthy": []}
        return grouped

    def _rebuild_lists(self):
        self._worktree_scroll_frame.destroy()
        self._branch_scroll_frame.destroy()
        self._also_branches_cb.destroy()

        self._worktree_scroll_frame, self._also_branches_cb = self._build_section(
            grouped=self._apply_filter(self._all_worktree_grouped),
            show_also_branches=True,
            insert_before=self._branch_label_frame,
        )
        self._branch_scroll_frame, _ = self._build_section(
            grouped=self._apply_filter(self._all_branch_grouped),
            show_also_branches=False,
            insert_before=self._btn_frame,
        )

    def _build(self):
        ctk.CTkLabel(
            self, text="Cleanup Wizard", font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=(20, 4))

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

        self._worktree_scroll_frame, self._also_branches_cb = self._build_section(
            grouped=self._apply_filter(self._all_worktree_grouped),
            show_also_branches=True,
            insert_before=self._branch_label_frame,
        )
        self._branch_scroll_frame, _ = self._build_section(
            grouped=self._apply_filter(self._all_branch_grouped),
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

    def _build_section(self, grouped: dict, show_also_branches: bool, insert_before=None):
        """Build scrollable list + optional checkbox. Returns (scroll_container, checkbox_widget)."""
        pack_opts = {"fill": "x", "padx": 24, "pady": (2, 4)}
        if insert_before is not None:
            pack_opts["before"] = insert_before

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(**pack_opts)

        f = self._filter.get()
        all_empty = not any(grouped[k] for k in grouped)
        if all_empty and f != _FILTER_ALL:
            ctk.CTkLabel(
                container, text="(none to show)", text_color="gray", anchor="w"
            ).pack(fill="x", pady=2)
        else:
            scroll = ctk.CTkScrollableFrame(container, height=140)
            scroll.pack(fill="x")
            _bind_mousewheel(scroll)

            if f == _FILTER_STALE:
                groups_to_show = [("Stale:", grouped["stale"])]
            elif f == _FILTER_MERGED:
                groups_to_show = [("Merged:", grouped["merged"])]
            else:
                groups_to_show = [
                    ("Merged:", grouped["merged"]),
                    ("Stale:", grouped["stale"]),
                    ("Healthy:", grouped["healthy"]),
                ]

            for i, (label_text, items) in enumerate(groups_to_show):
                if i > 0:
                    ctk.CTkFrame(scroll, height=1, fg_color="gray50").pack(fill="x", pady=(6, 2))
                ctk.CTkLabel(
                    scroll, text=label_text, text_color="gray",
                    font=ctk.CTkFont(size=11), anchor="w",
                ).pack(fill="x", padx=4, pady=(0, 2))
                if items:
                    for c in items:
                        self._add_item(scroll, c)
                else:
                    ctk.CTkLabel(
                        scroll, text="(none)", text_color="gray",
                        font=ctk.CTkFont(size=11), anchor="w",
                    ).pack(fill="x", padx=8, pady=(0, 2))

        cb_pack_opts = {"anchor": "w", "padx": 24, "pady": (4, 2)}
        if insert_before is not None:
            cb_pack_opts["before"] = insert_before

        cb_widget = ctk.CTkFrame(self, fg_color="transparent", height=0)
        if show_also_branches:
            has_priority = bool(grouped["merged"] or grouped["stale"])
            self._also_branches = ctk.BooleanVar(value=has_priority)
            cb_widget = ctk.CTkCheckBox(
                self, text="Also delete their branches", variable=self._also_branches
            )
            cb_widget.pack(**cb_pack_opts)

        return container, cb_widget

    def _add_item(self, parent, c: CleanupCandidate):
        blocked = c.has_uncommitted
        var = next(v for cand, v in self._all_pairs if cand is c)
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
        selected = [c for c, v in self._all_pairs if v.get()]
        self._on_delete_selected(selected, self._also_branches.get())
        self.destroy()
