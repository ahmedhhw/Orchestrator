import os
import customtkinter as ctk
import tkinter.messagebox as mb
from worktree_manager.workspace_projects_vm import WorkspaceProjectsViewModel


class WorkspaceProjectsPanel(ctk.CTkFrame):
    def __init__(self, master, vm: WorkspaceProjectsViewModel, on_close):
        super().__init__(master)
        self._vm = vm
        self._on_close = on_close
        self._editor_var = ctk.StringVar(value="cursor")
        self._collapsed: set = set()
        self._build()
        self.refresh()

    def _build(self):
        toolbar = ctk.CTkFrame(self, corner_radius=0)
        toolbar.pack(fill="x", padx=8, pady=(8, 4))
        ctk.CTkLabel(
            toolbar,
            text="Workspace Projects",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(side="left")
        ctk.CTkButton(toolbar, text="×", width=32, command=self._on_close).pack(side="right", padx=2)
        ctk.CTkButton(toolbar, text="+ New", width=70, command=self._open_new_dialog).pack(side="right", padx=2)

        editor_bar = ctk.CTkFrame(self, corner_radius=0)
        editor_bar.pack(fill="x", padx=8, pady=(0, 4))
        ctk.CTkSegmentedButton(
            editor_bar,
            values=["cursor", "vscode"],
            variable=self._editor_var,
        ).pack(side="left", padx=2, pady=4)

        self._scroll = ctk.CTkScrollableFrame(self)
        self._scroll.pack(fill="both", expand=True, padx=8, pady=4)

        self._empty_label = ctk.CTkLabel(
            self._scroll,
            text="No projects yet.\nClick [+ New] to create one.",
            text_color="gray",
            justify="center",
        )

    def refresh(self):
        for w in self._scroll.winfo_children():
            w.destroy()
        projects = self._vm.load_projects()
        if not projects:
            self._empty_label = ctk.CTkLabel(
                self._scroll,
                text="No projects yet.\nClick [+ New] to create one.",
                text_color="gray",
                justify="center",
            )
            self._empty_label.pack(pady=40)
            return
        for project in projects:
            self._add_project_row(project)

    def _add_project_row(self, project):
        name = project.name
        is_collapsed = name in self._collapsed

        header = ctk.CTkFrame(self._scroll)
        header.pack(fill="x", pady=(4, 0))

        toggle_text = "▶" if is_collapsed else "▼"
        toggle_btn = ctk.CTkButton(
            header, text=f"{toggle_text} {name}", anchor="w",
            fg_color="transparent", hover_color="gray25",
            text_color=("gray10", "gray90"),
            command=lambda n=name: self._toggle_collapse(n),
        )
        toggle_btn.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            header, text="Open", width=52,
            command=lambda n=name: self._open_project(n, self._editor_var.get()),
        ).pack(side="right", padx=(0, 2))
        ctk.CTkButton(
            header, text="✕", width=28, fg_color="#c0392b",
            command=lambda n=name: self._delete_project(n),
        ).pack(side="right", padx=(0, 2))

        if not is_collapsed:
            entries_frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
            entries_frame.pack(fill="x", padx=(20, 0), pady=(0, 4))
            for entry in project.entries:
                self._add_entry_row(entries_frame, entry.worktree_path)

    def _add_entry_row(self, parent, worktree_path: str):
        try:
            current_branch = self._vm._git.checked_out_branch(worktree_path)
            branches = self._vm.list_branches_for_worktree(worktree_path)
        except Exception:
            current_branch = "(unknown)"
            branches = []

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=1)

        wt_name = os.path.basename(worktree_path) or worktree_path
        home = os.path.expanduser("~")
        short_path = "~" + worktree_path[len(home):] if worktree_path.startswith(home) else worktree_path
        label_text = f"{wt_name}: {short_path}"
        ctk.CTkLabel(row, text=label_text, anchor="w", text_color="gray").pack(side="left", padx=4, fill="x", expand=True)

        if branches:
            branch_var = ctk.StringVar(value=current_branch)

            def _on_branch_select(new_b, path=worktree_path, var=branch_var, orig=current_branch):
                if new_b == orig:
                    return
                try:
                    self._vm.switch_branch_in_project(path, new_b)
                    self.refresh()
                except ValueError as e:
                    mb.showerror("Cannot switch", str(e))
                    var.set(orig)

            ctk.CTkOptionMenu(
                row,
                variable=branch_var,
                values=branches,
                width=150,
                command=_on_branch_select,
            ).pack(side="right", padx=4)
        else:
            ctk.CTkLabel(row, text=current_branch, text_color="gray", anchor="e", width=150).pack(side="right", padx=4)

    def _toggle_collapse(self, name: str):
        if name in self._collapsed:
            self._collapsed.discard(name)
        else:
            self._collapsed.add(name)
        self.refresh()

    def _open_project(self, name: str, editor: str):
        self._vm.open_project(name, editor)

    def _delete_project(self, name: str):
        self._vm.delete_project(name)
        self.refresh()

    def _open_new_dialog(self):
        from worktree_manager.ui.new_project_dialog import NewProjectDialog
        # vm doesn't directly hold the store; get repos from config store via vm internals
        repos = getattr(self._vm, "_store", None)
        repos_dict = repos.all_repos() if repos is not None else {}
        NewProjectDialog(
            self,
            vm=self._vm,
            repos=repos_dict,
            on_create=self._handle_create,
        )

    def _handle_create(self, name: str, entries: list):
        self._vm.create_project(name=name, entries=entries)
        self.refresh()
