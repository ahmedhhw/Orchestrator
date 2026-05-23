from pathlib import Path
import customtkinter as ctk


class ManageCommandsDialog(ctk.CTkToplevel):
    def __init__(self, master, vm):
        super().__init__(master)
        self.title("Manage Commands")
        self.resizable(False, False)
        self._vm = vm
        self._editing_name: str | None = None  # name of the command currently being edited
        self._all_action_buttons: list[ctk.CTkButton] = []
        self._done_btn: ctk.CTkButton | None = None
        self._build()
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build(self):
        repos = self._vm.all_repos()
        self._repo_paths = list(repos.keys())
        self._repo_map = {Path(p).name: p for p in self._repo_paths}
        display_names = [Path(p).name for p in self._repo_paths]

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=24, pady=(20, 8))
        ctk.CTkLabel(top, text="Manage Commands",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
        ctk.CTkButton(top, text="+ Add Command", width=120,
                      command=self._open_add_command_dialog).pack(side="right")

        repo_row = ctk.CTkFrame(self, fg_color="transparent")
        repo_row.pack(fill="x", padx=24, pady=(0, 8))
        ctk.CTkLabel(repo_row, text="Repository:", width=80, anchor="w").pack(side="left")
        last_used = (
            self._vm.get_last_used_repo() if hasattr(self._vm, "get_last_used_repo") else None
        )
        if last_used and last_used in self._repo_paths:
            default_name = Path(last_used).name
        elif display_names:
            default_name = display_names[0]
        else:
            default_name = ""
        self._repo_var = ctk.StringVar(value=default_name)
        ctk.CTkOptionMenu(
            repo_row, variable=self._repo_var, values=display_names,
            command=self._on_repo_changed, width=220,
            fg_color=("gray85", "gray25"), button_color=("gray70", "gray35"),
            button_hover_color=("gray60", "gray45"),
            text_color=("gray10", "gray90"),
        ).pack(side="left")

        self._list_frame = ctk.CTkScrollableFrame(self, width=440, height=300)
        self._list_frame.pack(fill="both", expand=True, padx=24, pady=(0, 8))

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=24, pady=(0, 16))
        self._count_label = ctk.CTkLabel(footer, text="", text_color="gray", anchor="w")
        self._count_label.pack(side="left")
        self._done_btn = ctk.CTkButton(footer, text="Done", width=80, command=self._on_close)
        self._done_btn.pack(side="right")

        if display_names:
            self._refresh_list()

    def _on_repo_changed(self, _: str) -> None:
        self._editing_name = None
        if hasattr(self._vm, "set_last_used_repo"):
            self._vm.set_last_used_repo(self._current_repo_path())
        self._refresh_list()

    def _current_repo_path(self) -> str:
        return self._repo_map.get(self._repo_var.get(), "")

    def _refresh_list(self) -> None:
        for w in self._list_frame.winfo_children():
            w.destroy()
        self._all_action_buttons = []

        repo_path = self._current_repo_path()
        commands = self._vm.saved_commands(repo_path)
        n = len(commands)
        self._count_label.configure(
            text=f"{n} command{'s' if n != 1 else ''} saved for this repo"
        )

        if not commands:
            ctk.CTkLabel(
                self._list_frame,
                text='No commands saved for this repo yet.\nUse "+ Add Command" in the toolbar to create one.',
                text_color="gray",
                justify="center",
            ).pack(pady=40)
            return

        for i, cmd in enumerate(commands):
            if i > 0:
                ctk.CTkFrame(self._list_frame, height=1,
                             fg_color=("gray80", "gray30")).pack(fill="x", pady=(2, 0))

            if cmd.name == self._editing_name:
                self._build_edit_row(cmd.name, cmd.command)
            else:
                self._build_view_row(cmd.name, cmd.command)

        self._apply_lock_state()

    def _build_view_row(self, name: str, command: str) -> None:
        row = ctk.CTkFrame(self._list_frame, fg_color="transparent")
        row.pack(fill="x", pady=(4, 2))

        text_col = ctk.CTkFrame(row, fg_color="transparent")
        text_col.pack(fill="x", pady=(0, 2))
        ctk.CTkLabel(text_col, text=name, anchor="w",
                     font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        ctk.CTkLabel(text_col, text=command, anchor="w",
                     text_color="gray", font=ctk.CTkFont(size=11)).pack(anchor="w")

        btn_row = ctk.CTkFrame(row, fg_color="transparent")
        btn_row.pack(fill="x")

        edit_btn = ctk.CTkButton(
            btn_row, text="Edit", width=70,
            fg_color=("gray75", "gray30"), text_color=("black", "white"),
            hover_color=("gray65", "gray40"),
            command=lambda n=name: self._start_edit(n),
        )
        edit_btn.pack(side="right", padx=(4, 0))

        copy_btn = ctk.CTkButton(
            btn_row, text="⎘", width=36,
            fg_color=("gray75", "gray30"), text_color=("black", "white"),
            hover_color=("gray65", "gray40"),
            command=lambda c=command: self._copy_command(c),
        )
        copy_btn.pack(side="right", padx=(4, 0))

        del_btn = ctk.CTkButton(
            btn_row, text="Delete", width=70,
            fg_color="#b04545", hover_color="#8a3535",
            command=lambda n=name: self._delete(n),
        )
        del_btn.pack(side="right")

        self._all_action_buttons.extend([edit_btn, copy_btn, del_btn])

    def _build_edit_row(self, name: str, command: str) -> None:
        row = ctk.CTkFrame(self._list_frame, border_width=1,
                           border_color=("gray60", "gray50"), corner_radius=6)
        row.pack(fill="x", pady=(4, 2))

        ctk.CTkLabel(row, text="Name", anchor="w",
                     font=ctk.CTkFont(size=11)).pack(anchor="w", padx=10, pady=(8, 0))
        name_entry = ctk.CTkEntry(row)
        name_entry.insert(0, name)
        name_entry.pack(fill="x", padx=10, pady=(2, 6))

        ctk.CTkLabel(row, text="Command", anchor="w",
                     font=ctk.CTkFont(size=11)).pack(anchor="w", padx=10)
        cmd_text = ctk.CTkTextbox(row, height=80)
        cmd_text.insert("1.0", command)
        cmd_text.pack(fill="x", padx=10, pady=(2, 8))

        def _get_cmd() -> str:
            return cmd_text.get("1.0", "end").strip()

        btn_row = ctk.CTkFrame(row, fg_color="transparent")
        btn_row.pack(fill="x", padx=10, pady=(0, 10))

        cancel_btn = ctk.CTkButton(
            btn_row, text="Cancel", width=80,
            fg_color="transparent", border_width=1,
            command=self._cancel_edit,
        )
        cancel_btn.pack(side="right", padx=(4, 0))

        save_btn = ctk.CTkButton(
            btn_row, text="Save", width=80,
            command=lambda: self._save_edit(name, name_entry.get(), _get_cmd()),
        )
        save_btn.pack(side="right")

        name_entry.bind("<Return>", lambda e: self._save_edit(name, name_entry.get(), _get_cmd()))
        name_entry.bind("<Escape>", lambda e: self._cancel_edit())
        cmd_text.bind("<Escape>", lambda e: self._cancel_edit())

        name_entry.focus_set()

    def _apply_lock_state(self) -> None:
        editing = self._editing_name is not None
        state = "disabled" if editing else "normal"
        for btn in self._all_action_buttons:
            btn.configure(state=state)
        if self._done_btn:
            self._done_btn.configure(state=state)

    def _start_edit(self, name: str) -> None:
        self._editing_name = name
        self._refresh_list()

    def _cancel_edit(self) -> None:
        self._editing_name = None
        self._refresh_list()

    def _save_edit(self, old_name: str, new_name: str, new_command: str) -> None:
        new_name = new_name.strip()
        new_command = new_command.strip()
        if not new_name or not new_command:
            return
        repo_path = self._current_repo_path()
        if old_name != new_name:
            self._vm.delete_command(repo_path, old_name)
        self._vm.save_command(repo_path, new_name, new_command)
        self._editing_name = None
        self._refresh_list()

    def _copy_command(self, command: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(command)

    def _delete(self, name: str) -> None:
        self._vm.delete_command(self._current_repo_path(), name)
        self._refresh_list()

    def _open_add_command_dialog(self) -> None:
        from worktree_manager.ui.add_command_dialog import AddCommandDialog
        def _on_saved():
            self._refresh_list()
        AddCommandDialog(self, vm=self._vm, initial_repo=self._current_repo_path(),
                         on_saved=_on_saved)

    def _on_close(self) -> None:
        if self._editing_name is not None:
            return
        self.destroy()
