from pathlib import Path
import customtkinter as ctk
from worktree_manager.models import SavedCommand, WorktreeModel
from worktree_manager.ui.scroll_fix import attach_scroll_fix


class LaunchDialog(ctk.CTkToplevel):
    def __init__(self, master, vm):
        super().__init__(master)
        self.title("Launch Command")
        self.resizable(True, True)
        self._vm = vm
        self._commands: list[SavedCommand] = []
        self._worktrees: list[WorktreeModel] = []
        self._selected_cmd: SavedCommand | None = None
        self._cmd_rows: list[ctk.CTkFrame] = []
        self._build()
        self.grab_set()

    def _build(self):
        ctk.CTkLabel(self, text="Launch Command",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(16, 8), padx=24, anchor="w")

        repos = self._vm.all_repos()
        self._repo_paths = list(repos.keys())
        self._repo_map = {Path(p).name: p for p in self._repo_paths}
        display_names = [Path(p).name for p in self._repo_paths]

        last_used = (
            self._vm.get_last_used_repo() if hasattr(self._vm, "get_last_used_repo") else None
        )
        if last_used and last_used in self._repo_paths:
            default_name = Path(last_used).name
        elif display_names:
            default_name = display_names[0]
        else:
            default_name = ""

        # Row: Repo
        row1 = ctk.CTkFrame(self, fg_color="transparent")
        row1.pack(fill="x", padx=24, pady=(0, 4))
        ctk.CTkLabel(row1, text="Repo:", width=70, anchor="w").pack(side="left")
        self._repo_var = ctk.StringVar(value=default_name)
        ctk.CTkOptionMenu(row1, variable=self._repo_var, values=display_names,
                          command=self._on_repo_changed, width=200,
                          fg_color=("gray85", "gray25"), button_color=("gray70", "gray35"),
                          button_hover_color=("gray60", "gray45"),
                          text_color=("gray10", "gray90")).pack(side="left")

        # Row: Worktree
        row2 = ctk.CTkFrame(self, fg_color="transparent")
        row2.pack(fill="x", padx=24, pady=(0, 4))
        ctk.CTkLabel(row2, text="Worktree:", width=70, anchor="w").pack(side="left")
        self._wt_var = ctk.StringVar()
        self._wt_menu = ctk.CTkOptionMenu(row2, variable=self._wt_var, values=[], width=200,
                                          fg_color=("gray85", "gray25"), button_color=("gray70", "gray35"),
                                          button_hover_color=("gray60", "gray45"),
                                          text_color=("gray10", "gray90"))
        self._wt_menu.pack(side="left")

        # Command list
        cmd_header = ctk.CTkFrame(self, fg_color="transparent")
        cmd_header.pack(fill="x", padx=24, pady=(8, 2))
        ctk.CTkLabel(cmd_header, text="Command:", anchor="w").pack(side="left")
        self._cmd_filter_var = ctk.StringVar()
        self._cmd_filter_var.trace_add("write", self._on_filter_changed)
        ctk.CTkEntry(cmd_header, placeholder_text="Filter…",
                     textvariable=self._cmd_filter_var, width=160).pack(side="right")
        self._cmd_list = ctk.CTkScrollableFrame(self, height=160)
        self._cmd_list.pack(fill="x", padx=24, pady=(0, 8))
        attach_scroll_fix(self._cmd_list)

        self._empty_cmd_label = ctk.CTkLabel(
            self._cmd_list, text="No saved commands for this repo.", text_color="gray"
        )

        self._conflict_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._conflict_frame.pack(fill="x", padx=24)
        self._conflict_label = ctk.CTkLabel(
            self._conflict_frame, text="", text_color="red", wraplength=260, justify="left", anchor="w"
        )
        self._conflict_label.pack(side="left", fill="x", expand=True)
        self._restart_btn = ctk.CTkButton(
            self._conflict_frame, text="Restart", width=80,
            command=self._trigger_conflict_restart,
        )

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=24, pady=(4, 16))
        ctk.CTkButton(btns, text="Cancel", fg_color="transparent",
                      border_width=1, command=self.trigger_cancel).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Launch", command=self.trigger_launch).pack(side="right", padx=4)

        self._conflict_run_id: str | None = None

        if default_name:
            self._on_repo_changed(default_name)

    def _on_repo_changed(self, repo_name: str) -> None:
        repo_path = self._repo_map.get(repo_name, "")
        self._commands = self._vm.saved_commands(repo_path)
        self._selected_cmd = None
        self._cmd_filter_var.set("")

        self._worktrees = self._vm.list_worktrees(repo_path)
        wt_labels = [f"{wt.branch}  ({wt.path})" for wt in self._worktrees]
        self._wt_menu.configure(values=wt_labels)
        self._wt_var.set(wt_labels[0] if wt_labels else "")

        self._render_cmd_list()

    def _on_filter_changed(self, *_) -> None:
        self._selected_cmd = None
        self._render_cmd_list()

    def _render_cmd_list(self) -> None:
        for row in self._cmd_rows:
            row.destroy()
        self._cmd_rows = []
        self._empty_cmd_label.pack_forget()

        term = self._cmd_filter_var.get().strip().lower()
        visible = [cmd for cmd in self._commands
                   if not term or term in cmd.name.lower() or term in cmd.command.lower()]

        if not visible:
            self._empty_cmd_label.pack(pady=12)
            return

        for cmd in visible:
            row = ctk.CTkFrame(self._cmd_list, corner_radius=4, cursor="hand2")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text=cmd.name, anchor="w",
                         font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(10, 4), pady=6)
            ctk.CTkLabel(row, text=cmd.command, anchor="w",
                         text_color="gray", font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 8))
            row.bind("<Button-1>", lambda e, c=cmd: self._select_cmd(c))
            for child in row.winfo_children():
                child.bind("<Button-1>", lambda e, c=cmd: self._select_cmd(c))
            self._cmd_rows.append(row)

        # auto-select first visible
        self._select_cmd(visible[0])

    def _select_cmd(self, cmd: SavedCommand) -> None:
        self._selected_cmd = cmd
        for row, visible_cmd in zip(self._cmd_rows, [
            c for c in self._commands
            if not self._cmd_filter_var.get().strip()
            or self._cmd_filter_var.get().strip().lower() in c.name.lower()
            or self._cmd_filter_var.get().strip().lower() in c.command.lower()
        ]):
            row.configure(fg_color=("gray75", "gray30") if visible_cmd is cmd else "transparent")

    def _current_repo_path(self) -> str:
        return self._repo_map.get(self._repo_var.get(), "")

    def _current_worktree_path(self) -> str:
        label = self._wt_var.get()
        for wt in self._worktrees:
            if wt.path in label:
                return wt.path
        return label

    # --- public API for tests ---

    def command_choices(self) -> list[str]:
        return [c.name for c in self._commands]

    def worktree_choices(self) -> list[str]:
        return [f"{wt.branch}  ({wt.path})" for wt in self._worktrees]

    def set_command(self, name: str) -> None:
        for cmd in self._commands:
            if cmd.name == name:
                self._select_cmd(cmd)
                return

    def set_worktree(self, path: str) -> None:
        for wt in self._worktrees:
            if wt.path == path:
                self._wt_var.set(f"{wt.branch}  ({wt.path})")
                return
        self._wt_var.set(path)

    def trigger_launch(self) -> None:
        if self._selected_cmd is None:
            return
        from worktree_manager.command_runner import RunStatus
        cmd_obj = self._selected_cmd
        repo_path = self._current_repo_path()
        worktree_path = self._current_worktree_path()
        repo_name = Path(repo_path).name

        existing = None
        if hasattr(self._vm, "find_existing_run"):
            existing = self._vm.find_existing_run(cmd_obj.name, repo_path, worktree_path)

        if existing is not None:
            if existing.status == RunStatus.RUNNING:
                self._show_conflict(
                    f'"{cmd_obj.name}" is already running in this worktree.',
                    show_restart=False,
                    run_id=None,
                )
            else:
                self._show_conflict(
                    f'"{cmd_obj.name}" already exists but is stopped. Restart it?',
                    show_restart=True,
                    run_id=existing.run_id,
                )
            return

        self._vm.launch(
            repo_path=repo_path,
            repo_name=repo_name,
            cmd_name=cmd_obj.name,
            command_str=cmd_obj.command,
            worktree_path=worktree_path,
        )
        if hasattr(self._vm, "set_last_used_repo"):
            self._vm.set_last_used_repo(repo_path)
        self.destroy()

    def _show_conflict(self, message: str, show_restart: bool, run_id: str | None) -> None:
        self._conflict_label.configure(text=message)
        self._conflict_run_id = run_id
        if show_restart:
            self._restart_btn.pack(side="right")
        else:
            self._restart_btn.pack_forget()

    def _trigger_conflict_restart(self) -> None:
        if self._conflict_run_id and hasattr(self._vm, "restart"):
            self._vm.restart(self._conflict_run_id)
        self.destroy()

    def trigger_cancel(self) -> None:
        self.destroy()
