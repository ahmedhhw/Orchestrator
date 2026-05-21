from pathlib import Path
import customtkinter as ctk
from worktree_manager.models import SavedCommand, WorktreeModel


class LaunchDialog(ctk.CTkToplevel):
    def __init__(self, master, vm):
        super().__init__(master)
        self.title("Launch Command")
        self.resizable(False, False)
        self._vm = vm
        self._commands: list[SavedCommand] = []
        self._worktrees: list[WorktreeModel] = []
        self._build()
        self.grab_set()

    def _build(self):
        ctk.CTkLabel(self, text="Launch Command",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(16, 8), padx=24, anchor="w")

        repos = self._vm.all_repos()
        self._repo_paths = list(repos.keys())
        self._repo_map = {Path(p).name: p for p in self._repo_paths}
        display_names = [Path(p).name for p in self._repo_paths]

        row1 = ctk.CTkFrame(self)
        row1.pack(fill="x", padx=24, pady=4)
        ctk.CTkLabel(row1, text="Repo:", width=70, anchor="w").pack(side="left")
        self._repo_var = ctk.StringVar(value=display_names[0] if display_names else "")
        ctk.CTkOptionMenu(row1, variable=self._repo_var, values=display_names,
                          command=self._on_repo_changed, width=200,
                          fg_color=("gray85", "gray25"), button_color=("gray70", "gray35"),
                          button_hover_color=("gray60", "gray45"),
                          text_color=("gray10", "gray90")).pack(side="left")

        row2 = ctk.CTkFrame(self)
        row2.pack(fill="x", padx=24, pady=4)
        ctk.CTkLabel(row2, text="Command:", width=70, anchor="w").pack(side="left")
        self._cmd_var = ctk.StringVar()
        self._cmd_menu = ctk.CTkOptionMenu(row2, variable=self._cmd_var, values=[], width=200,
                                           fg_color=("gray85", "gray25"), button_color=("gray70", "gray35"),
                                           button_hover_color=("gray60", "gray45"),
                                           text_color=("gray10", "gray90"))
        self._cmd_menu.pack(side="left")

        row3 = ctk.CTkFrame(self)
        row3.pack(fill="x", padx=24, pady=4)
        ctk.CTkLabel(row3, text="Worktree:", width=70, anchor="w").pack(side="left")
        self._wt_var = ctk.StringVar()
        self._wt_menu = ctk.CTkOptionMenu(row3, variable=self._wt_var, values=[], width=200,
                                          fg_color=("gray85", "gray25"), button_color=("gray70", "gray35"),
                                          button_hover_color=("gray60", "gray45"),
                                          text_color=("gray10", "gray90"))
        self._wt_menu.pack(side="left")

        btns = ctk.CTkFrame(self)
        btns.pack(fill="x", padx=24, pady=(8, 16))
        ctk.CTkButton(btns, text="Cancel", fg_color="transparent",
                      border_width=1, command=self.trigger_cancel).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Launch", command=self.trigger_launch).pack(side="right", padx=4)

        if display_names:
            self._on_repo_changed(display_names[0])

    def _on_repo_changed(self, repo_name: str) -> None:
        repo_path = self._repo_map.get(repo_name, "")
        self._commands = self._vm.saved_commands(repo_path)
        cmd_names = [c.name for c in self._commands]
        self._cmd_menu.configure(values=cmd_names)
        self._cmd_var.set(cmd_names[0] if cmd_names else "")

        self._worktrees = self._vm.list_worktrees(repo_path)
        wt_labels = [f"{wt.branch}  ({wt.path})" for wt in self._worktrees]
        self._wt_menu.configure(values=wt_labels)
        self._wt_var.set(wt_labels[0] if wt_labels else "")

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
        self._cmd_var.set(name)

    def set_worktree(self, path: str) -> None:
        for wt in self._worktrees:
            if wt.path == path:
                self._wt_var.set(f"{wt.branch}  ({wt.path})")
                return
        self._wt_var.set(path)

    def trigger_launch(self) -> None:
        cmd_name = self._cmd_var.get().strip()
        if not cmd_name:
            return
        cmd_obj = next((c for c in self._commands if c.name == cmd_name), None)
        if cmd_obj is None:
            return
        repo_path = self._current_repo_path()
        worktree_path = self._current_worktree_path()
        repo_name = Path(repo_path).name
        self._vm.launch(
            repo_path=repo_path,
            repo_name=repo_name,
            cmd_name=cmd_name,
            command_str=cmd_obj.command,
            worktree_path=worktree_path,
        )
        self.destroy()

    def trigger_cancel(self) -> None:
        self.destroy()
