import customtkinter as ctk

EDITOR_CHOICES = [
    ("VS Code — new window",   "vscode", False),
    ("VS Code — reuse window", "vscode", True),
    ("Cursor — new window",    "cursor", False),
    ("Cursor — reuse window",  "cursor", True),
]


class CreateDialog(ctk.CTkToplevel):
    def __init__(self, master, branches: list, default_editor: str,
                 default_mode: str, on_create):
        super().__init__(master)
        self.title("New Worktree")
        self.resizable(False, False)
        self._branches = branches
        self._on_create = on_create
        self._default_editor = default_editor
        self._default_mode = default_mode
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="Branch name:").pack(anchor="w", padx=24, pady=(20, 2))
        self._branch_entry = ctk.CTkEntry(self, width=300, placeholder_text="feature/")
        self._branch_entry.pack(padx=24)

        ctk.CTkLabel(self, text="Base branch:").pack(anchor="w", padx=24, pady=(12, 2))
        self._base_var = ctk.StringVar(
            value=self._branches[0] if self._branches else "main"
        )
        ctk.CTkOptionMenu(
            self, variable=self._base_var, values=self._branches or ["main"]
        ).pack(padx=24, anchor="w")

        self._open_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            self, text="Open after creating", variable=self._open_var
        ).pack(anchor="w", padx=24, pady=(16, 4))

        default_label = (
            f"{self._default_editor} — "
            f"{'reuse' if self._default_mode == 'reuse' else 'new'} window"
        )
        # Normalise to match EDITOR_CHOICES labels
        default_label = default_label.replace("vscode", "VS Code").replace("cursor", "Cursor")
        self._editor_var = ctk.StringVar(value=default_label)
        labels = [c[0] for c in EDITOR_CHOICES]
        ctk.CTkOptionMenu(
            self, variable=self._editor_var, values=labels
        ).pack(padx=40, anchor="w")

        btns = ctk.CTkFrame(self)
        btns.pack(fill="x", padx=24, pady=16)
        ctk.CTkButton(
            btns, text="Cancel", fg_color="gray", command=self.destroy
        ).pack(side="left")
        ctk.CTkButton(btns, text="Create", command=self._create).pack(side="right")

    def _create(self):
        branch = self._branch_entry.get().strip()
        if not branch:
            return
        label = self._editor_var.get()
        choice = next((c for c in EDITOR_CHOICES if c[0] == label), EDITOR_CHOICES[0])
        self._on_create(
            branch, self._base_var.get(), self._open_var.get(),
            choice[1], choice[2]
        )
        self.destroy()
