import time
import customtkinter as ctk
from worktree_manager.models import CleanupCandidate


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


def _group_candidates(candidates: list) -> dict:
    merged = [c for c in candidates if c.is_merged]
    stale = [c for c in candidates if c.is_stale and not c.is_merged]
    healthy = [c for c in candidates if not c.is_stale and not c.is_merged]
    merged.sort(key=_merge_sort_key)
    stale.sort(key=lambda c: c.last_commit_ts)
    return {"merged": merged, "stale": stale, "healthy": healthy}


class CleanupWizard(ctk.CTkToplevel):
    def __init__(self, master, candidates: list, on_delete_selected):
        super().__init__(master)
        self.title("Cleanup Wizard")
        self.resizable(False, False)
        self._on_delete_selected = on_delete_selected
        self._all_pairs: list = []

        grouped = _group_candidates(candidates)
        ordered = grouped["merged"] + grouped["stale"] + grouped["healthy"]
        for c in ordered:
            is_priority = c.is_stale or c.is_merged
            disabled = c.has_uncommitted or c.is_checked_out
            var = ctk.BooleanVar(value=False if disabled else is_priority)
            self._all_pairs.append((c, var))

        self._grouped = grouped
        self._build()

    def _build(self):
        ctk.CTkLabel(
            self, text="Cleanup Wizard", font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=(20, 4))

        scroll = ctk.CTkScrollableFrame(self, height=280)
        scroll.pack(fill="x", padx=24, pady=(4, 8))

        groups_to_show = [
            ("Merged:", self._grouped["merged"]),
            ("Stale:", self._grouped["stale"]),
            ("Healthy:", self._grouped["healthy"]),
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

        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(fill="x", padx=24, pady=16)
        ctk.CTkButton(
            btn_frame, text="Select All", fg_color="gray",
            text_color=("black", "white"), command=self._select_all
        ).pack(side="left", padx=(0, 4))
        ctk.CTkButton(
            btn_frame, text="Deselect All", fg_color="gray",
            text_color=("black", "white"), command=self._deselect_all
        ).pack(side="left")
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
        cb = ctk.CTkCheckBox(
            row, text=f"{c.branch}  ({_reason(c)})", variable=var
        )
        cb.pack(side="left", padx=4)
        if c.has_uncommitted:
            cb.configure(state="disabled", text_color="gray50", checkmark_color="gray50",
                         fg_color="gray50", border_color="gray50")
            ctk.CTkLabel(
                row, text="⚠ uncommitted", text_color="orange",
                font=ctk.CTkFont(size=11),
            ).pack(side="left", padx=(6, 0))
        elif c.is_checked_out:
            cb.configure(state="disabled", text_color="gray50", checkmark_color="gray50",
                         fg_color="gray50", border_color="gray50")
            ctk.CTkLabel(
                row, text="⚠ checked out", text_color="orange",
                font=ctk.CTkFont(size=11),
            ).pack(side="left", padx=(6, 0))

    def _select_all(self):
        for _, v in self._all_pairs:
            v.set(True)

    def _deselect_all(self):
        for _, v in self._all_pairs:
            v.set(False)

    def _delete_selected(self):
        selected = [(c, v) for c, v in self._all_pairs if v.get()]
        self._on_delete_selected(selected)
        self.destroy()
