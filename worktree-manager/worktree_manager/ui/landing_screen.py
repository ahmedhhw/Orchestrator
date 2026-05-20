import customtkinter as ctk
from tkinter import filedialog
from worktree_manager.landing_screen import LandingScreenViewModel


class LandingScreen(ctk.CTkFrame):
    def __init__(self, master, vm: LandingScreenViewModel, on_repo_chosen):
        super().__init__(master)
        self._vm = vm
        self._on_repo_chosen = on_repo_chosen
        self._error_label = None
        self._build()

    def _build(self):
        ctk.CTkLabel(
            self, text="Git Worktree Manager", font=ctk.CTkFont(size=20, weight="bold")
        ).pack(pady=(24, 4))
        ctk.CTkLabel(self, text="No repo loaded.", text_color="gray").pack(pady=4)
        ctk.CTkButton(self, text="Select Repo…", command=self._pick_folder).pack(pady=12)
        self._error_label = ctk.CTkLabel(self, text="", text_color="red")
        self._error_label.pack()

        recent = self._vm.recent_repos()
        if recent:
            ctk.CTkLabel(self, text="Recent repos:", anchor="w").pack(
                fill="x", padx=24, pady=(12, 2)
            )
            for cfg in recent:
                row = ctk.CTkFrame(self)
                row.pack(fill="x", padx=24, pady=2)
                ctk.CTkLabel(row, text=cfg.repo_path, anchor="w").pack(
                    side="left", fill="x", expand=True
                )
                ctk.CTkButton(
                    row, text="Open", width=60,
                    command=lambda p=cfg.repo_path: self._select(p)
                ).pack(side="right")

    def _pick_folder(self):
        path = filedialog.askdirectory(title="Select git repo")
        if path:
            self._select(path)

    def _select(self, path: str):
        ok, err = self._vm.validate_repo(path)
        if not ok:
            self._error_label.configure(text=err)
            return
        self._error_label.configure(text="")
        self._vm.on_repo_selected(path, self._on_repo_chosen)
