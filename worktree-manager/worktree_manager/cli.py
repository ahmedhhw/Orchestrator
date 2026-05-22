import argparse
import sys
from pathlib import Path


def parse_args(argv: list) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Git Worktree Manager")
    parser.add_argument(
        "repo_path", nargs="?", default=None,
        help="Path to the main git worktree",
    )
    return parser.parse_args(argv)


def resolve_repo_path(path, git):
    if path is None:
        return None
    if not git.is_valid_repo(path):
        print(f"Error: '{path}' is not a git repository.", file=sys.stderr)
        sys.exit(1)
    return path


class App:
    def __init__(self, repo_path):
        import customtkinter as ctk
        from worktree_manager.config_store import ConfigStore
        from worktree_manager.git_service import GitService
        self._ctk = ctk
        self._root = ctk.CTk()
        self._root.title("Git Worktree Manager")
        self._root.geometry("900x520")
        self._root.minsize(700, 400)

        self._store = ConfigStore()
        self._git = GitService()
        self._current_frame = None
        self._sidebar_frame = None
        self._cc_panel = None
        self._wp_panel = None
        self._active_repo_path = None

        from worktree_manager.command_center_vm import CommandCenterViewModel
        self._cc_vm = CommandCenterViewModel(config_store=self._store, git_service=self._git)

        if repo_path:
            self._load_repo(repo_path)
        else:
            self._show_empty_main()

    def run(self):
        self._root.mainloop()

    def _clear_main(self):
        if self._current_frame:
            self._current_frame.destroy()
            self._current_frame = None

    def _clear(self):
        self._clear_main()
        if self._sidebar_frame:
            self._sidebar_frame.destroy()
            self._sidebar_frame = None

    def _show_landing(self):
        self._show_empty_main()

    def _show_empty_main(self):
        self._clear_main()
        self._show_sidebar(active_repo_path=None)

        frame = self._ctk.CTkFrame(self._root)
        frame.pack(side="left", fill="both", expand=True)
        self._ctk.CTkLabel(
            frame,
            text="No repo selected.\nPick one from the sidebar or click + Add Repo.",
            text_color="gray",
            justify="center",
        ).place(relx=0.5, rely=0.5, anchor="center")
        self._current_frame = frame

    def _show_sidebar(self, active_repo_path: str):
        import customtkinter as ctk

        if self._sidebar_frame:
            self._sidebar_frame.destroy()

        sidebar = ctk.CTkFrame(self._root, width=220, corner_radius=0)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        self._sidebar_frame = sidebar

        ctk.CTkLabel(
            sidebar, text="REPOS", font=ctk.CTkFont(weight="bold"), text_color="gray"
        ).pack(pady=(12, 4), padx=8, anchor="w")

        repos = self._store.all_repos()
        for path, cfg in repos.items():
            name = Path(path).name
            is_active = active_repo_path is not None and path == active_repo_path
            btn = ctk.CTkButton(
                sidebar,
                text=("● " if is_active else "  ") + name,
                anchor="w",
                fg_color=("gray30" if is_active else "transparent"),
                hover_color="gray25",
                text_color=("white" if is_active else ("gray10", "gray90")),
                command=lambda p=path: self._switch_repo(p),
            )
            btn.pack(fill="x", padx=4, pady=1)
            try:
                btn._text_label.configure(wraplength=196)
            except Exception:
                pass

        ctk.CTkButton(
            sidebar, text="+ Add Repo", fg_color="transparent",
            border_width=1, text_color=("gray10", "gray90"),
            command=self._pick_and_add_repo,
        ).pack(fill="x", padx=4, pady=(8, 4))

        ctk.CTkButton(
            sidebar, text="⊞ Command Center", fg_color="transparent",
            border_width=1, text_color=("gray10", "gray90"),
            command=self._show_command_center,
        ).pack(fill="x", padx=4, pady=(0, 4))

        ctk.CTkButton(
            sidebar, text="⊞ Workspace Projects", fg_color="transparent",
            border_width=1, text_color=("gray10", "gray90"),
            command=self._show_workspace_projects,
        ).pack(fill="x", padx=4, pady=(0, 4))

        ctk.CTkButton(
            sidebar, text="↻ Refresh", fg_color="transparent",
            border_width=1, text_color=("gray10", "gray90"),
            command=self._refresh,
        ).pack(fill="x", padx=4, pady=(0, 12), side="bottom")

    def _pick_and_add_repo(self):
        from tkinter import filedialog
        import tkinter.messagebox as mb
        path = filedialog.askdirectory(title="Select git repo")
        if not path:
            return
        if not self._git.is_valid_repo(path):
            mb.showerror("Error", f"'{path}' is not a git repository.")
            return
        self._load_repo(path)

    def _switch_repo(self, repo_path: str):
        self._load_repo(repo_path)

    def _load_repo(self, repo_path: str):
        cfg = self._store.get_repo(repo_path)
        if cfg is None:
            self._show_setup(repo_path)
        else:
            self._show_main(repo_path)

    def _show_setup(self, repo_path: str):
        self._clear()
        from worktree_manager.setup_settings_vm import RepoSetupViewModel
        from worktree_manager.ui.repo_setup_dialog import RepoSetupDialog
        vm = RepoSetupViewModel(repo_path=repo_path, config_store=self._store)
        self._current_frame = self._ctk.CTkFrame(self._root)
        self._current_frame.pack(fill="both", expand=True)
        RepoSetupDialog(
            self._root, vm=vm,
            on_confirm=lambda: self._show_main(repo_path),
        )

    def _show_main(self, repo_path: str):
        from worktree_manager.main_window_vm import MainWindowViewModel
        from worktree_manager.ui.main_window import MainWindow

        self._active_repo_path = repo_path
        self._clear_main()
        self._show_sidebar(repo_path)

        vm = MainWindowViewModel(
            repo_path=repo_path,
            config_store=self._store,
            git_service=self._git,
        )
        repo_name = Path(repo_path).name
        self._current_frame = MainWindow(
            self._root, vm=vm, repo_name=repo_name,
            on_settings=lambda: self._show_settings(repo_path),
            on_cleanup=lambda: self._show_cleanup(vm),
        )
        self._current_frame.pack(side="left", fill="both", expand=True)

    def _refresh(self):
        if self._active_repo_path:
            self._show_main(self._active_repo_path)
        elif self._current_frame is self._cc_panel:
            self._show_command_center()
        elif self._current_frame is self._wp_panel:
            self._wp_panel.refresh()

    def _show_settings(self, repo_path: str):
        from worktree_manager.setup_settings_vm import SettingsViewModel
        from worktree_manager.ui.settings_panel import SettingsPanel
        vm = SettingsViewModel(repo_path=repo_path, config_store=self._store)
        SettingsPanel(self._root, vm=vm)

    def _show_command_center(self) -> None:
        from worktree_manager.ui.command_center_panel import CommandCenterPanel
        self._clear_main()
        if self._cc_panel is None or not self._cc_panel.winfo_exists():
            self._cc_panel = CommandCenterPanel(
                self._root, vm=self._cc_vm,
                on_close=self._close_command_center,
            )
        self._cc_panel.pack(side="left", fill="both", expand=True)
        self._current_frame = self._cc_panel

    def _close_command_center(self) -> None:
        if self._cc_panel:
            self._cc_panel.pack_forget()
        self._show_empty_main()

    def _show_workspace_projects(self) -> None:
        from worktree_manager.workspace_projects_vm import WorkspaceProjectsViewModel
        from worktree_manager.workspace_service import WorkspaceService
        from worktree_manager.ui.workspace_projects_panel import WorkspaceProjectsPanel
        self._clear_main()
        wp_vm = WorkspaceProjectsViewModel(
            config_store=self._store,
            git_service=self._git,
            workspace_service=WorkspaceService(),
        )
        self._wp_panel = WorkspaceProjectsPanel(
            self._root, vm=wp_vm,
            on_close=self._close_workspace_projects,
        )
        self._wp_panel.pack(side="left", fill="both", expand=True)
        self._current_frame = self._wp_panel

    def _close_workspace_projects(self) -> None:
        if self._wp_panel:
            self._wp_panel.pack_forget()
        self._show_empty_main()

    def _show_cleanup(self, main_vm):
        import tkinter.messagebox as mb
        from worktree_manager.ui.cleanup_wizard import CleanupWizard
        candidates = main_vm.all_cleanup_candidates()
        if not candidates:
            mb.showinfo("Cleanup", "No branches to clean up.")
            return

        def _on_delete(selected_pairs):
            selected = [c for c, _ in selected_pairs]
            main_vm.delete_cleanup_candidates(selected, also_delete_branches=True)
            if self._current_frame and hasattr(self._current_frame, "refresh"):
                self._current_frame.refresh()

        CleanupWizard(self._root, candidates=candidates, on_delete_selected=_on_delete)


def main():
    from worktree_manager.git_service import GitService
    import customtkinter as ctk

    args = parse_args(sys.argv[1:])
    git = GitService()
    repo_path = resolve_repo_path(args.repo_path, git)

    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")

    app = App(repo_path)
    app.run()


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    main()
