from pathlib import Path
import customtkinter as ctk


class AddCommandDialog(ctk.CTkToplevel):
    def __init__(self, master, vm):
        super().__init__(master)
        self.title("Add Saved Command")
        self.resizable(False, False)
        self._vm = vm
        self._build()
        self.grab_set()

    def _build(self):
        ctk.CTkLabel(self, text="Add Saved Command",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(16, 8), padx=24, anchor="w")

        repos = self._vm.all_repos()
        repo_paths = list(repos.keys())
        self._repo_map = {Path(p).name: p for p in repo_paths}
        display_names = [Path(p).name for p in repo_paths]

        row1 = ctk.CTkFrame(self)
        row1.pack(fill="x", padx=24, pady=4)
        ctk.CTkLabel(row1, text="Repo:", width=70, anchor="w").pack(side="left")
        self._repo_var = ctk.StringVar(value=display_names[0] if display_names else "")
        ctk.CTkOptionMenu(row1, variable=self._repo_var, values=display_names, width=200,
                          fg_color=("gray85", "gray25"), button_color=("gray70", "gray35"),
                          button_hover_color=("gray60", "gray45"),
                          text_color=("gray10", "gray90")).pack(side="left")

        row2 = ctk.CTkFrame(self)
        row2.pack(fill="x", padx=24, pady=4)
        ctk.CTkLabel(row2, text="Name:", width=70, anchor="w").pack(side="left")
        self._name_entry = ctk.CTkEntry(row2, width=200)
        self._name_entry.pack(side="left")

        ctk.CTkLabel(self, text="Command:", anchor="w").pack(fill="x", padx=24, pady=(8, 2))
        self._cmd_text = ctk.CTkTextbox(self, height=80, width=320)
        self._cmd_text.pack(padx=24, pady=(0, 8))

        btns = ctk.CTkFrame(self)
        btns.pack(fill="x", padx=24, pady=(4, 16))
        ctk.CTkButton(btns, text="Cancel", fg_color="transparent",
                      border_width=1, command=self.trigger_cancel).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Save", command=self.trigger_save).pack(side="right", padx=4)

    # --- public API for tests ---

    def repo_choices(self) -> list[str]:
        return list(self._repo_map.values())

    def set_repo(self, repo_path: str) -> None:
        name = Path(repo_path).name
        self._repo_var.set(name)

    def set_name(self, name: str) -> None:
        self._name_entry.delete(0, "end")
        self._name_entry.insert(0, name)

    def set_command(self, cmd: str) -> None:
        self._cmd_text.delete("1.0", "end")
        self._cmd_text.insert("1.0", cmd)

    def trigger_save(self) -> None:
        name = self._name_entry.get().strip()
        cmd = self._cmd_text.get("1.0", "end").strip()
        repo_name = self._repo_var.get()
        repo_path = self._repo_map.get(repo_name, "")
        if not name or not cmd or not repo_path:
            return
        self._vm.save_command(repo_path, name, cmd)
        self.destroy()

    def trigger_cancel(self) -> None:
        self.destroy()
