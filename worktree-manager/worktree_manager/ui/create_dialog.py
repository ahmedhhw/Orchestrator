import customtkinter as ctk


class CreateDialog(ctk.CTkToplevel):
    def __init__(self, master, branches: list, existing_branches: list, on_create):
        super().__init__(master)
        self.title("New Worktree")
        self.resizable(False, False)
        self._branches = branches
        self._existing_branches = existing_branches
        self._on_create = on_create
        self._mode_var = ctk.StringVar(value="new")
        self._build()

    def _build(self):
        mode_frame = ctk.CTkFrame(self)
        mode_frame.pack(fill="x", padx=24, pady=(20, 12))
        ctk.CTkRadioButton(
            mode_frame, text="New branch", variable=self._mode_var,
            value="new", command=self._on_mode_change,
        ).pack(side="left", padx=(0, 16))
        ctk.CTkRadioButton(
            mode_frame, text="Existing branch", variable=self._mode_var,
            value="existing", command=self._on_mode_change,
        ).pack(side="left")

        self._mode_area = ctk.CTkFrame(self, fg_color="transparent")
        self._mode_area.pack(fill="x", padx=24)

        # New branch frame
        self._new_frame = ctk.CTkFrame(self._mode_area, fg_color="transparent")

        ctk.CTkLabel(self._new_frame, text="Worktree name:").pack(anchor="w", pady=(0, 2))
        wt_row = ctk.CTkFrame(self._new_frame, fg_color="transparent")
        wt_row.pack(anchor="w", fill="x")
        self._wt_name_entry = ctk.CTkEntry(wt_row, width=240, placeholder_text="fix-login")
        self._wt_name_entry.pack(side="left")
        ctk.CTkButton(
            wt_row, text="← copy from branch", width=130, fg_color="gray",
            text_color=("black", "white"), command=self._copy_branch_to_wt,
        ).pack(side="left", padx=(8, 0))

        ctk.CTkLabel(self._new_frame, text="Branch name:").pack(anchor="w", pady=(12, 2))
        branch_row = ctk.CTkFrame(self._new_frame, fg_color="transparent")
        branch_row.pack(anchor="w", fill="x")
        self._branch_entry = ctk.CTkEntry(branch_row, width=240, placeholder_text="fix/")
        self._branch_entry.pack(side="left")
        ctk.CTkButton(
            branch_row, text="← copy from worktree", width=130, fg_color="gray",
            text_color=("black", "white"), command=self._copy_wt_to_branch,
        ).pack(side="left", padx=(8, 0))

        ctk.CTkLabel(self._new_frame, text="Base branch:").pack(anchor="w", pady=(12, 2))
        self._base_var = ctk.StringVar(value=self._branches[0] if self._branches else "main")
        ctk.CTkOptionMenu(
            self._new_frame, variable=self._base_var,
            values=self._branches or ["main"],
        ).pack(anchor="w")

        # Existing branch frame
        self._existing_frame = ctk.CTkFrame(self._mode_area, fg_color="transparent")

        ctk.CTkLabel(self._existing_frame, text="Existing branch:").pack(anchor="w", pady=(0, 2))
        self._existing_var = ctk.StringVar(
            value=self._existing_branches[0] if self._existing_branches else ""
        )
        ctk.CTkOptionMenu(
            self._existing_frame, variable=self._existing_var,
            values=self._existing_branches or ["(none available)"],
        ).pack(anchor="w")

        ctk.CTkLabel(self._existing_frame, text="Worktree name:").pack(anchor="w", pady=(12, 2))
        existing_wt_row = ctk.CTkFrame(self._existing_frame, fg_color="transparent")
        existing_wt_row.pack(anchor="w", fill="x")
        self._existing_wt_name_entry = ctk.CTkEntry(existing_wt_row, width=240, placeholder_text="fix-login")
        self._existing_wt_name_entry.pack(side="left")
        ctk.CTkButton(
            existing_wt_row, text="← copy from branch", width=130, fg_color="gray",
            text_color=("black", "white"), command=self._copy_existing_branch_to_wt,
        ).pack(side="left", padx=(8, 0))

        btns = ctk.CTkFrame(self)
        btns.pack(fill="x", padx=24, pady=16)
        ctk.CTkButton(
            btns, text="Cancel", fg_color="gray", text_color=("black", "white"), command=self.destroy
        ).pack(side="left")
        ctk.CTkButton(btns, text="Create", command=self._create).pack(side="right")

        self._on_mode_change()

    def _on_mode_change(self):
        self._new_frame.pack_forget()
        self._existing_frame.pack_forget()
        if self._mode_var.get() == "new":
            self._new_frame.pack(fill="x")
        else:
            self._existing_frame.pack(fill="x")

    def _copy_branch_to_wt(self):
        branch = self._branch_entry.get().strip()
        self._wt_name_entry.delete(0, "end")
        self._wt_name_entry.insert(0, branch.replace("/", "-"))

    def _copy_wt_to_branch(self):
        wt_name = self._wt_name_entry.get().strip()
        self._branch_entry.delete(0, "end")
        self._branch_entry.insert(0, wt_name.replace("-", "/", 1))

    def _copy_existing_branch_to_wt(self):
        branch = self._existing_var.get()
        self._existing_wt_name_entry.delete(0, "end")
        self._existing_wt_name_entry.insert(0, branch.replace("/", "-"))

    def _create(self):
        if self._mode_var.get() == "existing":
            branch = self._existing_var.get()
            if not branch or branch == "(none available)":
                return
            wt_name = self._existing_wt_name_entry.get().strip() or None
            self._on_create(branch, None, True, wt_name)
        else:
            branch = self._branch_entry.get().strip()
            if not branch:
                return
            wt_name = self._wt_name_entry.get().strip() or None
            self._on_create(branch, self._base_var.get(), False, wt_name)
        self.destroy()
