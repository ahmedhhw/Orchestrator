import time
import customtkinter as ctk
from worktree_manager.models import CleanupCandidate
from worktree_manager.ui.scroll_fix import attach_scroll_fix


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


def _merge_sort_key(c) -> tuple:
    target = (c.merged_into or "main").lower()
    return (target, c.branch.lower())


def _merged_subgroups(merged: list) -> list:
    """Return [(target, [candidates...]), ...] sorted by target name."""
    groups: dict = {}
    for c in merged:
        target = c.merged_into or "main"
        groups.setdefault(target, []).append(c)
    for branches in groups.values():
        branches.sort(key=lambda c: c.branch.lower())
    return sorted(groups.items(), key=lambda kv: kv[0].lower())


def _group_candidates(candidates: list) -> dict:
    unoperable = [c for c in candidates if c.has_uncommitted or c.is_checked_out]
    protected = [c for c in candidates if c.is_protected and not c.has_uncommitted and not c.is_checked_out]
    operable = [c for c in candidates if not c.is_protected and not c.has_uncommitted and not c.is_checked_out]
    merged = [c for c in operable if c.is_merged]
    stale = [c for c in operable if c.is_stale and not c.is_merged]
    healthy = [c for c in operable if not c.is_stale and not c.is_merged]
    merged.sort(key=_merge_sort_key)
    stale.sort(key=lambda c: c.last_commit_ts)
    return {"merged": merged, "stale": stale, "healthy": healthy, "protected": protected, "unoperable": unoperable}


class CleanupWizard(ctk.CTkToplevel):
    def __init__(self, master, candidates: list | None, on_delete_selected):
        super().__init__(master)
        self.title("Cleanup Wizard")
        self.resizable(False, False)
        self._on_delete_selected = on_delete_selected
        self._all_pairs: list = []

        # Loading state — set when candidates is None (deferred load)
        self._loading_frame: ctk.CTkFrame | None = None
        self._progress_bar: ctk.CTkProgressBar | None = None
        self._progress_label: ctk.CTkLabel | None = None
        self._progress_count: ctk.CTkLabel | None = None

        self._grouped = {}
        self._global_btn: ctk.CTkButton | None = None
        self._subgroup_btn: dict = {}
        self._stale_btn: ctk.CTkButton | None = None
        self._admin_mode_var = ctk.BooleanVar(value=False)
        self._protected_triples: list = []
        self._admin_banner = None
        self._admin_only_label = None

        if candidates is None:
            self._build_loading()
        else:
            self._init_candidates(candidates)
            self._build()
            self._wire_traces()
            self._refresh_button_labels()

    def _init_candidates(self, candidates: list):
        grouped = _group_candidates(candidates)
        operable = grouped["merged"] + grouped["stale"] + grouped["healthy"]
        for c in operable:
            var = ctk.BooleanVar(value=c.is_stale or c.is_merged)
            self._all_pairs.append((c, var))
        self._grouped = grouped

    def _build_loading(self):
        ctk.CTkLabel(
            self, text="Cleanup Wizard", font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=(20, 4))

        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=24, pady=(12, 4))
        self._loading_frame = frame

        self._progress_label = ctk.CTkLabel(
            frame, text="Scanning branches…", font=ctk.CTkFont(size=12), anchor="w"
        )
        self._progress_label.pack(fill="x", pady=(0, 6))

        self._progress_bar = ctk.CTkProgressBar(frame, mode="determinate")
        self._progress_bar.set(0)
        self._progress_bar.pack(fill="x", pady=(0, 4))

        self._progress_count = ctk.CTkLabel(
            frame, text="", font=ctk.CTkFont(size=11), text_color="gray", anchor="e"
        )
        self._progress_count.pack(fill="x")

        # Spacer so the window has a stable size from the start
        ctk.CTkFrame(self, height=60, fg_color="transparent").pack()

    def update_progress(self, current: int, total: int, label: str):
        """Called from background thread via after(); safe to call cross-thread."""
        def _update():
            if self._progress_bar is None:
                return
            fraction = current / total if total > 0 else 0
            self._progress_bar.set(fraction)
            self._progress_label.configure(text=label)
            self._progress_count.configure(text=f"{current} / {total}")
        self.after(0, _update)

    def finish_loading(self, candidates: list):
        """Replace the loading screen with the real wizard content."""
        def _swap():
            if self._loading_frame:
                self._loading_frame.destroy()
                self._loading_frame = None
                self._progress_bar = None
                self._progress_label = None
                self._progress_count = None
            # Destroy spacer frames (all children not yet part of real UI)
            for w in self.winfo_children():
                w.destroy()
            self._all_pairs = []
            self._subgroup_btn = {}
            self._global_btn = None
            self._stale_btn = None
            self._admin_banner = None
            self._admin_only_label = None
            self._protected_triples = []
            self._init_candidates(candidates)
            self._build()
            self._wire_traces()
            self._refresh_button_labels()
        self.after(0, _swap)

    def _build(self):
        ctk.CTkLabel(
            self, text="Cleanup Wizard", font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=(20, 4))

        # Warning banner — hidden until Admin Mode is ON
        self._admin_banner = ctk.CTkFrame(self, fg_color="#7b2d00")
        ctk.CTkLabel(
            self._admin_banner,
            text="⚠ Admin Mode: Protected branches can be deleted.\n    Double-check your selection before deleting.",
            text_color="white", font=ctk.CTkFont(size=11), anchor="w", justify="left",
        ).pack(padx=12, pady=6, anchor="w")

        scroll = ctk.CTkScrollableFrame(self, height=280)
        scroll.pack(fill="x", padx=24, pady=(4, 8))
        self._scroll = scroll

        # CTkScrollableFrame registers its MouseWheel handler via bind_all on
        # the main Tk root. In a CTkToplevel (separate window), those bindings
        # don't fire. Re-register on the canvas itself so the toplevel window
        # receives the events.
        attach_scroll_fix(self, scroll)

        # Merged section — sub-grouped by target
        ctk.CTkLabel(
            scroll, text="Merged:", text_color="gray",
            font=ctk.CTkFont(size=11), anchor="w",
        ).pack(fill="x", padx=4, pady=(0, 2))
        merged = self._grouped["merged"]
        if merged:
            for target, branches in _merged_subgroups(merged):
                sub_header = ctk.CTkFrame(scroll, fg_color="transparent")
                sub_header.pack(fill="x", pady=(4, 0))
                ctk.CTkLabel(
                    sub_header, text=f"  → into {target}", text_color="gray",
                    font=ctk.CTkFont(size=11), anchor="w",
                ).pack(side="left", padx=4)
                btn = ctk.CTkButton(
                    sub_header, text="Select all", fg_color="gray",
                    text_color=("black", "white"), width=80, height=20,
                    font=ctk.CTkFont(size=11),
                    command=lambda t=target: self._toggle_subgroup(t),
                )
                btn.pack(side="right", padx=4)
                self._subgroup_btn[target] = btn
                for c in branches:
                    self._add_item(scroll, c)
        else:
            ctk.CTkLabel(
                scroll, text="(none)", text_color="gray",
                font=ctk.CTkFont(size=11), anchor="w",
            ).pack(fill="x", padx=8, pady=(0, 2))

        # Stale section — with Select all button
        ctk.CTkFrame(scroll, height=1, fg_color="gray50").pack(fill="x", pady=(6, 2))
        stale_header = ctk.CTkFrame(scroll, fg_color="transparent")
        stale_header.pack(fill="x", pady=(0, 2))
        ctk.CTkLabel(
            stale_header, text="Stale:", text_color="gray",
            font=ctk.CTkFont(size=11), anchor="w",
        ).pack(side="left", padx=4)
        if self._grouped["stale"]:
            self._stale_btn = ctk.CTkButton(
                stale_header, text="Select all", fg_color="gray",
                text_color=("black", "white"), width=80, height=20,
                font=ctk.CTkFont(size=11),
                command=self._toggle_stale,
            )
            self._stale_btn.pack(side="right", padx=4)
            for c in self._grouped["stale"]:
                self._add_item(scroll, c)
        else:
            ctk.CTkLabel(
                scroll, text="(none)", text_color="gray",
                font=ctk.CTkFont(size=11), anchor="w",
            ).pack(fill="x", padx=8, pady=(0, 2))

        # Healthy section
        ctk.CTkFrame(scroll, height=1, fg_color="gray50").pack(fill="x", pady=(6, 2))
        ctk.CTkLabel(
            scroll, text="Healthy:", text_color="gray",
            font=ctk.CTkFont(size=11), anchor="w",
        ).pack(fill="x", padx=4, pady=(0, 2))
        if self._grouped["healthy"]:
            for c in self._grouped["healthy"]:
                self._add_item(scroll, c)
        else:
            ctk.CTkLabel(
                scroll, text="(none)", text_color="gray",
                font=ctk.CTkFont(size=11), anchor="w",
            ).pack(fill="x", padx=8, pady=(0, 2))

        if self._grouped["protected"]:
            ctk.CTkFrame(scroll, height=1, fg_color="gray50").pack(fill="x", pady=(6, 2))
            prot_header = ctk.CTkFrame(scroll, fg_color="transparent")
            prot_header.pack(fill="x", pady=(0, 2))
            ctk.CTkLabel(
                prot_header, text="Protected:", text_color="gray",
                font=ctk.CTkFont(size=11), anchor="w",
            ).pack(side="left", padx=4)
            self._admin_only_label = ctk.CTkLabel(
                prot_header, text="⚠ admin only", text_color="orange",
                font=ctk.CTkFont(size=11),
            )
            for c in self._grouped["protected"]:
                self._add_protected_item(scroll, c)

        if self._grouped["unoperable"]:
            ctk.CTkFrame(scroll, height=1, fg_color="gray50").pack(fill="x", pady=(6, 2))
            ctk.CTkLabel(
                scroll, text="Cannot delete:", text_color="gray",
                font=ctk.CTkFont(size=11), anchor="w",
            ).pack(fill="x", padx=4, pady=(0, 2))
            for c in self._grouped["unoperable"]:
                self._add_unoperable_item(scroll, c)

        # Admin Mode toggle
        admin_row = ctk.CTkFrame(self, fg_color="transparent")
        admin_row.pack(fill="x", padx=24, pady=(0, 4))
        ctk.CTkCheckBox(
            admin_row, text="Admin Mode", variable=self._admin_mode_var,
            command=self._on_admin_mode_toggle,
        ).pack(side="left")
        ctk.CTkLabel(
            admin_row, text="⚠ Enable only if you know what you're doing",
            text_color="orange", font=ctk.CTkFont(size=11),
        ).pack(side="left", padx=(8, 0))

        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(fill="x", padx=24, pady=(4, 16))
        self._global_btn = ctk.CTkButton(
            btn_frame, text="Select All", fg_color="gray",
            text_color=("black", "white"), command=self._toggle_all,
        )
        self._global_btn.pack(side="left", padx=(0, 4))
        ctk.CTkButton(
            btn_frame, text="Cancel", fg_color="gray",
            text_color=("black", "white"), command=self.destroy
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            btn_frame, text="Delete", fg_color="#c0392b",
            command=self._delete_selected
        ).pack(side="right")

    def _add_item(self, parent, c: CleanupCandidate):
        var = next(v for cand, v in self._all_pairs if cand is c)
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkCheckBox(
            row, text=f"{c.branch}  ({_reason(c)})", variable=var
        ).pack(side="left", padx=4)

    def _add_protected_item(self, parent, c: CleanupCandidate):
        var = ctk.BooleanVar(value=False)
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=2)
        cb = ctk.CTkCheckBox(
            row, text=f"{c.branch}  ({_reason(c)})", variable=var,
        )
        cb.configure(state="disabled", text_color="gray50", checkmark_color="gray50",
                     fg_color="gray50", border_color="gray50")
        cb.pack(side="left", padx=4)
        tag = "⚠ main" if c.branch == "main" else "⚠ feature"
        ctk.CTkLabel(
            row, text=tag, text_color="orange",
            font=ctk.CTkFont(size=11),
        ).pack(side="left", padx=(6, 0))
        self._protected_triples.append((c, var, cb))

    def _add_unoperable_item(self, parent, c: CleanupCandidate):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(
            row, text=f"—   {c.branch}  ({_reason(c)})", text_color="gray50",
            font=ctk.CTkFont(size=11), anchor="w",
        ).pack(side="left", padx=4)
        tag = "⚠ uncommitted" if c.has_uncommitted else "⚠ checked out"
        ctk.CTkLabel(
            row, text=tag, text_color="orange",
            font=ctk.CTkFont(size=11),
        ).pack(side="left", padx=(6, 0))

    def _on_admin_mode_toggle(self):
        admin_on = self._admin_mode_var.get()
        if admin_on:
            self._admin_banner.pack(fill="x", padx=24, pady=(0, 4),
                                    after=self.pack_slaves()[0])
            if self._admin_only_label:
                self._admin_only_label.pack(side="right", padx=4)
            for _, _, cb in self._protected_triples:
                cb.configure(state="normal", text_color=("black", "white"),
                             checkmark_color=("black", "white"),
                             fg_color=("#3a7ebf", "#1f538d"), border_color=("gray50", "gray50"))
        else:
            self._admin_banner.pack_forget()
            if self._admin_only_label:
                self._admin_only_label.pack_forget()
            for _, var, cb in self._protected_triples:
                var.set(False)
                cb.configure(state="disabled", text_color="gray50", checkmark_color="gray50",
                             fg_color="gray50", border_color="gray50")
        self.update_idletasks()

    def _wire_traces(self):
        for _, v in self._all_pairs:
            v.trace_add("write", lambda *_: self._refresh_button_labels())

    def _refresh_button_labels(self):
        if self._global_btn:
            all_checked = bool(self._all_pairs) and all(v.get() for _, v in self._all_pairs)
            self._global_btn.configure(text="Deselect All" if all_checked else "Select All")

        for target, btn in self._subgroup_btn.items():
            group_pairs = [(c, v) for c, v in self._all_pairs if c.is_merged and (c.merged_into or "main") == target]
            all_checked = bool(group_pairs) and all(v.get() for _, v in group_pairs)
            btn.configure(text="Deselect all" if all_checked else "Select all")

        if self._stale_btn:
            stale_pairs = [(c, v) for c, v in self._all_pairs if c.is_stale and not c.is_merged]
            all_checked = bool(stale_pairs) and all(v.get() for _, v in stale_pairs)
            self._stale_btn.configure(text="Deselect all" if all_checked else "Select all")

    def _toggle_all(self):
        all_checked = bool(self._all_pairs) and all(v.get() for _, v in self._all_pairs)
        if all_checked:
            self._deselect_all()
        else:
            self._select_all()

    def _toggle_subgroup(self, target: str):
        group_pairs = [(c, v) for c, v in self._all_pairs if c.is_merged and (c.merged_into or "main") == target]
        all_checked = bool(group_pairs) and all(v.get() for _, v in group_pairs)
        if all_checked:
            for _, v in group_pairs:
                v.set(False)
        else:
            self._select_subgroup(target)

    def _toggle_stale(self):
        stale_pairs = [(c, v) for c, v in self._all_pairs if c.is_stale and not c.is_merged]
        all_checked = bool(stale_pairs) and all(v.get() for _, v in stale_pairs)
        if all_checked:
            for _, v in stale_pairs:
                v.set(False)
        else:
            self._select_stale()

    def _select_stale(self):
        for c, v in self._all_pairs:
            if c.is_stale and not c.is_merged:
                v.set(True)

    def _select_subgroup(self, target: str):
        for c, v in self._all_pairs:
            if c.is_merged and (c.merged_into or "main") == target:
                v.set(True)

    def _select_all(self):
        for _, v in self._all_pairs:
            v.set(True)

    def _deselect_all(self):
        for _, v in self._all_pairs:
            v.set(False)

    def _delete_selected(self):
        selected = [(c, v) for c, v in self._all_pairs if v.get()]
        if self._admin_mode_var.get():
            selected += [(c, v) for c, v, _ in self._protected_triples if v.get()]
        self._on_delete_selected(selected)
        self.destroy()
