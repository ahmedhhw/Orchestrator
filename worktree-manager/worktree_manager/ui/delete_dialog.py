import tkinter.messagebox as mb
import customtkinter as ctk
from worktree_manager.models import WorktreeModel


class DeleteDialog(ctk.CTkToplevel):
    def __init__(self, master, wt: WorktreeModel, on_delete,
                 live_window=None, is_protected: bool = False,
                 has_uncommitted: bool = False):
        super().__init__(master)
        self.title("Delete Worktree")
        self.geometry("420x300")
        self.resizable(False, False)
        self._wt = wt
        self._on_delete = on_delete
        self._live_window = live_window
        self._is_protected = is_protected
        self._has_uncommitted = has_uncommitted
        self._also_branch = ctk.BooleanVar(value=False if is_protected else True)
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
        ).pack(fill="x", padx=24, pady=(0, 8))

        if self._live_window is not None:
            editor_name = self._live_window.editor.title()
            ctk.CTkLabel(
                self,
                text=f'⚠ "{self._wt.branch}" is currently open in {editor_name}.\nThe editor window will be closed automatically.',
                text_color="orange",
                justify="center",
            ).pack(pady=(0, 8), padx=24)

        checkbox_text = (
            "Also delete branch  (protected)" if self._is_protected
            else "Also delete branch"
        )
        cb = ctk.CTkCheckBox(
            self, text=checkbox_text, variable=self._also_branch
        )
        cb.pack(anchor="w", padx=24, pady=4)
        if self._is_protected:
            cb.configure(state="disabled")

        btns = ctk.CTkFrame(self)
        btns.pack(fill="x", padx=24, pady=16)
        ctk.CTkButton(
            btns, text="Cancel", fg_color="gray", command=self.destroy
        ).pack(side="left")

        confirm_label = "Delete & Close" if self._live_window is not None else "Delete"
        ctk.CTkButton(
            btns, text=confirm_label, fg_color="#c0392b", command=self._delete
        ).pack(side="right")

    def _delete(self):
        if self._also_branch.get() and self._has_uncommitted:
            mb.showerror(
                "Cannot delete branch",
                f'"{self._wt.branch}" has uncommitted changes.\n\n'
                "Commit or discard changes before deleting.",
            )
            return
        self._on_delete(self._wt, self._also_branch.get())
        self.destroy()
