import customtkinter as ctk
from tkinter import filedialog
from worktree_manager.setup_settings_vm import SettingsViewModel


class SettingsPanel(ctk.CTkToplevel):
    def __init__(self, master, vm: SettingsViewModel):
        super().__init__(master)
        self.title("Settings")
        self.resizable(False, False)
        self._vm = vm
        self._build()

    def _build(self):
        ctk.CTkLabel(
            self, text="Settings", font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=(20, 8))

        row = ctk.CTkFrame(self)
        row.pack(fill="x", padx=24, pady=4)
        ctk.CTkLabel(row, text="Worktree storage:", width=140, anchor="w").pack(side="left")
        self._storage_entry = ctk.CTkEntry(row, width=220)
        self._storage_entry.insert(0, self._vm.worktree_storage)
        self._storage_entry.pack(side="left")
        ctk.CTkButton(
            row, text="Browse", width=70, command=self._browse
        ).pack(side="left", padx=4)

        row2 = ctk.CTkFrame(self)
        row2.pack(fill="x", padx=24, pady=4)
        ctk.CTkLabel(row2, text="Stale threshold:", width=140, anchor="w").pack(side="left")
        self._stale_entry = ctk.CTkEntry(row2, width=60)
        self._stale_entry.insert(0, str(self._vm.stale_days))
        self._stale_entry.pack(side="left")
        ctk.CTkLabel(row2, text="days").pack(side="left", padx=4)

        ctk.CTkButton(self, text="Save", command=self._save).pack(pady=16)

    def _browse(self):
        path = filedialog.askdirectory()
        if path:
            self._storage_entry.delete(0, "end")
            self._storage_entry.insert(0, path)

    def _save(self):
        try:
            stale_days = int(self._stale_entry.get())
        except ValueError:
            stale_days = 30
        self._vm.save(
            worktree_storage=self._storage_entry.get(),
            stale_days=stale_days,
        )
        self.destroy()
