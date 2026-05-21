import customtkinter as ctk
from tkinter import filedialog
from worktree_manager.setup_settings_vm import RepoSetupViewModel


class RepoSetupDialog(ctk.CTkToplevel):
    def __init__(self, master, vm: RepoSetupViewModel, on_confirm):
        super().__init__(master)
        self.title("Worktree Storage")
        self.resizable(False, False)
        self._vm = vm
        self._on_confirm = on_confirm
        self._build()

    def _build(self):
        ctk.CTkLabel(
            self, text="Where should worktrees be stored?",
            font=ctk.CTkFont(weight="bold")
        ).pack(padx=24, pady=(20, 8))

        row = ctk.CTkFrame(self)
        row.pack(fill="x", padx=24)
        self._entry = ctk.CTkEntry(row, width=300)
        self._entry.insert(0, self._vm.default_storage_path())
        self._entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            row, text="Browse", width=70, command=self._browse
        ).pack(side="right", padx=(8, 0))

        btns = ctk.CTkFrame(self)
        btns.pack(fill="x", padx=24, pady=16)
        ctk.CTkButton(
            btns, text="Cancel", fg_color="gray", text_color=("black", "white"), command=self.destroy
        ).pack(side="left")
        ctk.CTkButton(btns, text="Confirm", command=self._confirm).pack(side="right")

    def _browse(self):
        path = filedialog.askdirectory(title="Choose worktree storage folder")
        if path:
            self._entry.delete(0, "end")
            self._entry.insert(0, path)

    def _confirm(self):
        self._vm.confirm(storage_path=self._entry.get(), callback=self._on_confirm)
        self.destroy()
