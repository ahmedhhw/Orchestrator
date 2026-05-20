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


def _sort_candidates(candidates: list) -> list:
    priority = [c for c in candidates if c.is_stale or c.is_merged]
    healthy = [c for c in candidates if not c.is_stale and not c.is_merged]
    return priority + healthy


class CleanupWizard(ctk.CTkToplevel):
    def __init__(self, master, candidates: list, on_delete_selected):
        super().__init__(master)
        self.title("Cleanup Wizard")
        self.resizable(False, False)
        self._on_delete_selected = on_delete_selected
        self._vars: list = []
        self._candidates: list = []
        self._also_branches = ctk.BooleanVar(value=False)

        worktree_candidates = _sort_candidates([c for c in candidates if c.path is not None])
        branch_candidates = _sort_candidates([c for c in candidates if c.path is None])

        self._build(worktree_candidates, branch_candidates)

    def _build(self, worktree_candidates, branch_candidates):
        ctk.CTkLabel(
            self, text="Cleanup Wizard", font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=(20, 4))

        self._build_section(
            label="Worktrees",
            candidates=worktree_candidates,
            show_also_branches=True,
        )

        self._build_section(
            label="Branches (no worktree)",
            candidates=branch_candidates,
            show_also_branches=False,
        )

        btns = ctk.CTkFrame(self)
        btns.pack(fill="x", padx=24, pady=16)
        ctk.CTkButton(
            btns, text="Select All", fg_color="gray", command=self._select_all
        ).pack(side="left", padx=(0, 4))
        ctk.CTkButton(
            btns, text="Deselect All", fg_color="gray", command=self._deselect_all
        ).pack(side="left")
        ctk.CTkButton(
            btns, text="Cancel", fg_color="gray", command=self.destroy
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            btns, text="Delete", fg_color="#c0392b", command=self._delete_selected
        ).pack(side="right")

    def _build_section(self, label: str, candidates: list, show_also_branches: bool):
        ctk.CTkLabel(
            self, text=label, font=ctk.CTkFont(weight="bold"), anchor="w"
        ).pack(fill="x", padx=24, pady=(12, 2))

        if not candidates:
            ctk.CTkLabel(
                self, text="(none to clean)", text_color="gray", anchor="w"
            ).pack(fill="x", padx=24, pady=2)
            return

        scroll = ctk.CTkScrollableFrame(self, height=140)
        scroll.pack(fill="x", padx=24, pady=(0, 4))

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

        if show_also_branches:
            has_priority = bool(priority)
            self._also_branches = ctk.BooleanVar(value=has_priority)
            ctk.CTkCheckBox(
                self, text="Also delete their branches", variable=self._also_branches
            ).pack(anchor="w", padx=24, pady=(4, 2))

    def _add_item(self, parent, c: CleanupCandidate, pre_checked: bool):
        var = ctk.BooleanVar(value=pre_checked)
        self._vars.append(var)
        self._candidates.append(c)
        ctk.CTkCheckBox(
            parent, text=f"{c.branch}  ({_reason(c)})", variable=var
        ).pack(anchor="w", padx=4, pady=2)

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
