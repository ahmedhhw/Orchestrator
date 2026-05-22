import os
import time
import tkinter.messagebox as mb
import customtkinter as ctk
from worktree_manager.main_window_vm import MainWindowViewModel
from worktree_manager.models import WorktreeModel


def _fmt_age(ts: int) -> str:
    if ts == 0:
        return "no commits"
    diff = int(time.time()) - ts
    if diff < 3600:
        return f"{diff // 60}m ago"
    if diff < 86400:
        return f"{diff // 3600}h ago"
    return f"{diff // 86400}d ago"


class MainWindow(ctk.CTkFrame):
    def __init__(self, master, vm: MainWindowViewModel, repo_name: str,
                 on_settings, on_cleanup):
        super().__init__(master)
        self._vm = vm
        self._repo_name = repo_name
        self._on_settings = on_settings
        self._on_cleanup = on_cleanup
        self._build()
        self.refresh()

    def _build(self):
        header = ctk.CTkFrame(self)
        header.pack(fill="x", padx=16, pady=(16, 4))
        ctk.CTkLabel(
            header,
            text=f"Git Worktree Manager — {self._repo_name}",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(side="left")
        ctk.CTkButton(
            header, text="🧹", width=36, command=self._on_cleanup
        ).pack(side="right", padx=2)
        ctk.CTkButton(
            header, text="⚙", width=36, command=self._on_settings
        ).pack(side="right", padx=2)

        sub = ctk.CTkFrame(self)
        sub.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(
            sub, text="Worktrees", font=ctk.CTkFont(weight="bold")
        ).pack(side="left")
        ctk.CTkButton(
            sub, text="+ New", width=70, command=self._open_create
        ).pack(side="right")

        self._list_frame = ctk.CTkScrollableFrame(self)
        self._list_frame.pack(fill="both", expand=True, padx=16, pady=8)

    def refresh(self):
        for w in self._list_frame.winfo_children():
            w.destroy()
        worktrees = self._vm.load_worktrees()
        branch_status = self._vm.list_branches_with_checkout_status()
        for wt in worktrees:
            self._add_row(wt, branch_status)

    def _add_row(self, wt: WorktreeModel, branch_status: list):
        row = ctk.CTkFrame(self._list_frame)
        row.pack(fill="x", pady=2)

        dot = "●" if wt.is_main else "○"
        ctk.CTkLabel(row, text=dot, width=20).pack(side="left")
        wt_name = os.path.basename(wt.path) if not wt.is_main else "(main)"
        ctk.CTkLabel(row, text=wt_name, anchor="w", width=200).pack(side="left")
        ctk.CTkLabel(
            row, text=_fmt_age(wt.last_commit_ts), text_color="gray", width=80
        ).pack(side="left")

        if wt.is_stale:
            ctk.CTkLabel(
                row, text="⚠ stale", text_color="orange", width=70
            ).pack(side="left")
        else:
            ctk.CTkLabel(row, text="", width=70).pack(side="left")

        if not wt.is_main:
            ctk.CTkButton(
                row, text="✕", width=28, fg_color="#c0392b",
                command=lambda w=wt: self._open_delete(w)
            ).pack(side="right", padx=(0, 4))

        all_branches = [b for b, _ in branch_status]
        checked_out_set = {b for b, co in branch_status if co and b != wt.branch}

        branch_var = ctk.StringVar(value=wt.branch)

        def _on_branch_select(new_b, path=wt.path, var=branch_var, orig=wt.branch):
            if new_b == orig:
                return
            if new_b in checked_out_set:
                mb.showerror("Cannot switch", f"'{new_b}' is already checked out in another worktree.")
                var.set(orig)
                return
            ok = self._switch_branch(path, new_b)
            if not ok:
                var.set(orig)

        ctk.CTkOptionMenu(
            row,
            variable=branch_var,
            values=all_branches,
            width=160,
            command=_on_branch_select,
        ).pack(side="right", padx=(0, 2))

    def _switch_branch(self, worktree_path: str, new_branch: str) -> bool:
        try:
            self._vm.switch_branch(worktree_path, new_branch)
            self.refresh()
            return True
        except ValueError as e:
            mb.showerror("Cannot switch branch", str(e))
            return False

    def _open_create(self):
        from worktree_manager.ui.create_dialog import CreateDialog
        branches = self._vm.list_local_branches()
        existing_branches = self._vm.list_available_branches()
        CreateDialog(
            self, branches=branches, existing_branches=existing_branches,
            on_create=self._handle_create,
        )

    def _handle_create(self, branch, base_branch, is_existing):
        self._vm.create_worktree(branch=branch, base_branch=base_branch, existing=is_existing)
        self.refresh()

    def _open_delete(self, wt: WorktreeModel):
        from worktree_manager.ui.delete_dialog import DeleteDialog
        has_uncommitted = self._vm.has_uncommitted_changes(wt.path)
        DeleteDialog(self, wt=wt, on_delete=self._handle_delete,
                     live_window=None, has_uncommitted=has_uncommitted)

    def _handle_delete(self, wt, also_delete_branch):
        self._vm.delete_worktree(
            path=wt.path, branch=wt.branch, also_delete_branch=also_delete_branch
        )
        self.refresh()
