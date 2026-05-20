import time
import customtkinter as ctk
from worktree_manager.models import WorktreeModel


def _fmt_age(ts: int) -> str:
    if ts == 0:
        return "no commits"
    diff = int(time.time()) - ts
    return f"{diff // 86400}d"


class CleanupWizard(ctk.CTkToplevel):
    def __init__(self, master, candidates: list, on_delete_selected):
        super().__init__(master)
        self.title("Cleanup Wizard")
        self.resizable(False, False)
        self._candidates = candidates
        self._on_delete_selected = on_delete_selected
        self._vars: list = []
        self._build()

    def _build(self):
        ctk.CTkLabel(
            self, text="Cleanup Wizard", font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=(20, 4))
        ctk.CTkLabel(
            self, text="Select worktrees to remove:", anchor="w"
        ).pack(fill="x", padx=24, pady=(0, 8))

        for wt in self._candidates:
            var = ctk.BooleanVar(value=wt.is_stale or wt.is_merged)
            self._vars.append(var)
            reason = "merged" if wt.is_merged else f"{_fmt_age(wt.last_commit_ts)}, stale"
            ctk.CTkCheckBox(
                self, text=f"{wt.branch}  ({reason})", variable=var
            ).pack(anchor="w", padx=24, pady=2)

        self._also_branches = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            self, text="Also delete their branches", variable=self._also_branches
        ).pack(anchor="w", padx=24, pady=(12, 4))

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
            btns, text="Delete Selected", fg_color="#c0392b", command=self._delete_selected
        ).pack(side="right")

    def _select_all(self):
        for v in self._vars:
            v.set(True)

    def _deselect_all(self):
        for v in self._vars:
            v.set(False)

    def _delete_selected(self):
        selected = [wt for wt, v in zip(self._candidates, self._vars) if v.get()]
        self._on_delete_selected(selected, self._also_branches.get())
        self.destroy()
