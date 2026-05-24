from pathlib import Path
import customtkinter as ctk
from worktree_manager.models import WorkspaceEntry
from worktree_manager.workspace_projects_vm import WorkspaceProjectsViewModel


class NewProjectDialog(ctk.CTkToplevel):
    def __init__(self, master, vm: WorkspaceProjectsViewModel, repos: dict, on_create):
        super().__init__(master)
        self.title("New Workspace Project")
        self.resizable(False, False)
        self._vm = vm
        self._repos = repos
        self._on_create = on_create
        self._entries: list[str] = []  # list of worktree_path strings
        self._name_var = ctk.StringVar()
        self._repo_var = ctk.StringVar()
        self._worktree_var = ctk.StringVar()
        self._worktree_path_map: dict[str, str] = {}
        self._build()

    def _build(self):
        ctk.CTkLabel(
            self, text="New Workspace Project",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(pady=(20, 8), padx=24, anchor="w")

        name_frame = ctk.CTkFrame(self, fg_color="transparent")
        name_frame.pack(fill="x", padx=24, pady=(0, 2))
        ctk.CTkLabel(name_frame, text="Project name:", anchor="w", width=100).pack(side="left")
        ctk.CTkEntry(name_frame, textvariable=self._name_var, width=260).pack(side="left", padx=(4, 0))

        self._name_warn = ctk.CTkLabel(self, text="", text_color="#e74c3c", anchor="w", height=16)
        self._name_warn.pack(fill="x", padx=24, pady=(0, 4))
        self._name_var.trace_add("write", lambda *_: self._name_warn.configure(text=""))

        ctk.CTkLabel(
            self, text="Add worktrees:", anchor="w",
            font=ctk.CTkFont(weight="bold"),
        ).pack(fill="x", padx=24, pady=(4, 2))

        picker_frame = ctk.CTkFrame(self, fg_color="transparent")
        picker_frame.pack(fill="x", padx=24, pady=(0, 4))

        repo_names = list(self._repos.keys())
        repo_display = [Path(p).name for p in repo_names]
        self._repo_paths = repo_names

        repo_label_map = {Path(p).name: p for p in repo_names}

        def on_repo_change(display_name):
            path = repo_label_map.get(display_name, "")
            self._refresh_worktree_dropdown(path)

        ctk.CTkLabel(picker_frame, text="Repo:", anchor="w", width=50).grid(row=0, column=0, sticky="w")
        self._repo_menu = ctk.CTkOptionMenu(
            picker_frame,
            variable=self._repo_var,
            values=repo_display or ["(no repos)"],
            width=180,
            command=on_repo_change,
        )
        self._repo_menu.grid(row=0, column=1, padx=4)

        ctk.CTkLabel(picker_frame, text="Worktree:", anchor="w", width=70).grid(row=1, column=0, sticky="w", pady=(4, 0))
        self._worktree_menu = ctk.CTkOptionMenu(
            picker_frame,
            variable=self._worktree_var,
            values=["(select repo first)"],
            width=180,
        )
        self._worktree_menu.grid(row=1, column=1, padx=4, pady=(4, 0))

        ctk.CTkButton(
            picker_frame, text="+ Add", width=60,
            command=self._add_selected_entry,
        ).grid(row=1, column=2, padx=(4, 0), pady=(4, 0))

        if repo_names:
            self._repo_var.set(repo_display[0])
            self._refresh_worktree_dropdown(repo_names[0])

        ctk.CTkLabel(
            self, text="Entries:", anchor="w",
            font=ctk.CTkFont(weight="bold"),
        ).pack(fill="x", padx=24, pady=(8, 2))

        self._list_frame = ctk.CTkScrollableFrame(self, height=100)
        self._list_frame.pack(fill="x", padx=24, pady=(0, 2))

        self._empty_list_label = ctk.CTkLabel(
            self._list_frame, text="(none)", text_color="gray", anchor="w"
        )
        self._empty_list_label.pack(fill="x")

        self._entries_warn = ctk.CTkLabel(self, text="", text_color="#e74c3c", anchor="w", height=16)
        self._entries_warn.pack(fill="x", padx=24, pady=(0, 4))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=24, pady=(0, 20))
        ctk.CTkButton(
            btn_frame, text="Cancel", fg_color="gray",
            text_color=("black", "white"), command=self.destroy,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            btn_frame, text="Create Project",
            command=self._create_project,
        ).pack(side="right")

    def _refresh_worktree_dropdown(self, repo_path: str):
        try:
            worktrees = self._vm.list_worktrees_for_repo(repo_path)
        except Exception:
            worktrees = []
        paths = [wt.path for wt in worktrees]
        display = [
            f"(main): {wt.branch}" if wt.is_main else f"{Path(wt.path).name or wt.path}: {wt.branch}"
            for wt in worktrees
        ]
        self._worktree_path_map = dict(zip(display, paths))
        values = display if display else ["(none)"]
        self._worktree_menu.configure(values=values)
        self._worktree_var.set(values[0])

    def _add_selected_entry(self):
        display = self._worktree_var.get()
        if not display or display in ("(none)", "(select repo first)"):
            return
        path = self._worktree_path_map.get(display, display)
        if path and path not in self._entries:
            self._add_entry(path)

    def _add_entry(self, worktree_path: str):
        if worktree_path in self._entries:
            return
        self._entries.append(worktree_path)
        self._entries_warn.configure(text="")
        self._refresh_entry_list()

    def _remove_entry(self, worktree_path: str):
        if worktree_path in self._entries:
            self._entries.remove(worktree_path)
        self._refresh_entry_list()

    def _refresh_entry_list(self):
        for w in self._list_frame.winfo_children():
            w.destroy()
        if not self._entries:
            ctk.CTkLabel(
                self._list_frame, text="(none)", text_color="gray", anchor="w"
            ).pack(fill="x")
            return
        for path in list(self._entries):
            row = ctk.CTkFrame(self._list_frame, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkButton(
                row, text="✕", width=28, fg_color="#c0392b",
                command=lambda p=path: self._remove_entry(p),
            ).pack(side="right")
            ctk.CTkLabel(row, text=path, anchor="w").pack(side="left", fill="x", expand=True)

    def _create_project(self):
        name = self._name_var.get().strip()
        valid = True
        if not name:
            self._name_warn.configure(text="Project name is required.")
            valid = False
        if not self._entries:
            self._entries_warn.configure(text="Add at least one worktree.")
            valid = False
        if not valid:
            return
        entries = [WorkspaceEntry(worktree_path=p) for p in self._entries]
        try:
            self._on_create(name, entries)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._name_warn.configure(text=f"Error: {e}")
            return
        self.destroy()
