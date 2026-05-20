import customtkinter as ctk
from worktree_manager.models import WorktreeModel


class DeleteDialog(ctk.CTkToplevel):
    def __init__(self, master, wt: WorktreeModel, on_delete):
        super().__init__(master)
        self.title("Delete worktree?")
        self.resizable(False, False)
        self._wt = wt
        self._on_delete = on_delete
        self._build()

    def _build(self):
        ctk.CTkLabel(
            self, text="Delete worktree?", font=ctk.CTkFont(weight="bold")
        ).pack(padx=24, pady=(20, 8))
        ctk.CTkLabel(
            self, text=f"Branch:  {self._wt.branch}", anchor="w"
        ).pack(fill="x", padx=24)
        ctk.CTkLabel(
            self, text=f"Path:    {self._wt.path}", anchor="w", wraplength=340
        ).pack(fill="x", padx=24, pady=(0, 12))

        self._also_branch = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            self, text="Also delete branch", variable=self._also_branch
        ).pack(anchor="w", padx=24, pady=4)

        btns = ctk.CTkFrame(self)
        btns.pack(fill="x", padx=24, pady=16)
        ctk.CTkButton(
            btns, text="Cancel", fg_color="gray", command=self.destroy
        ).pack(side="left")
        ctk.CTkButton(
            btns, text="Delete", fg_color="#c0392b", command=self._delete
        ).pack(side="right")

    def _delete(self):
        self._on_delete(self._wt, self._also_branch.get())
        self.destroy()
