import time
import tkinter as tk
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
        for wt in worktrees:
            self._add_row(wt)

    def _add_row(self, wt: WorktreeModel):
        row = ctk.CTkFrame(self._list_frame)
        row.pack(fill="x", pady=2)

        dot = "●" if wt.is_main else "○"
        ctk.CTkLabel(row, text=dot, width=20).pack(side="left")
        ctk.CTkLabel(row, text=wt.branch, anchor="w", width=180).pack(side="left")
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

        ed, mode = self._vm.default_editor()
        reuse = mode == "reuse"
        arrow_btn = ctk.CTkButton(
            row, text="▾", width=28,
            command=lambda w=wt: self._show_open_menu(w)
        )
        arrow_btn.pack(side="right", padx=(0, 2))
        ctk.CTkButton(
            row, text="Open", width=55,
            command=lambda p=wt.path: self._vm.open_worktree(p, ed, reuse)
        ).pack(side="right", padx=(0, 2))

    def _show_open_menu(self, wt: WorktreeModel):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(
            label="VS Code — new window",
            command=lambda: self._vm.open_worktree(wt.path, "vscode", False),
        )
        menu.add_command(
            label="VS Code — reuse window",
            command=lambda: self._vm.open_worktree(wt.path, "vscode", True),
        )
        menu.add_separator()
        menu.add_command(
            label="Cursor — new window",
            command=lambda: self._vm.open_worktree(wt.path, "cursor", False),
        )
        menu.add_command(
            label="Cursor — reuse window",
            command=lambda: self._vm.open_worktree(wt.path, "cursor", True),
        )
        x = self.winfo_pointerx()
        y = self.winfo_pointery()
        menu.tk_popup(x, y)

    def _open_create(self):
        from worktree_manager.ui.create_dialog import CreateDialog
        branches = self._vm.list_local_branches()
        ed, mode = self._vm.default_editor()
        CreateDialog(
            self, branches=branches, default_editor=ed, default_mode=mode,
            on_create=self._handle_create,
        )

    def _handle_create(self, branch, base_branch, open_after, editor, reuse_window):
        self._vm.create_worktree(branch=branch, base_branch=base_branch)
        if open_after:
            path = self._vm.worktree_path_for_branch(branch)
            self._vm.open_worktree(path, editor, reuse_window)
        self.refresh()

    def _open_delete(self, wt: WorktreeModel):
        from worktree_manager.ui.delete_dialog import DeleteDialog
        DeleteDialog(self, wt=wt, on_delete=self._handle_delete)

    def _handle_delete(self, wt, also_delete_branch):
        self._vm.delete_worktree(
            path=wt.path, branch=wt.branch, also_delete_branch=also_delete_branch
        )
        self.refresh()
