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
        from worktree_manager.editor_service import EditorService

        self._ctk = ctk
        self._root = ctk.CTk()
        self._root.title("Git Worktree Manager")
        self._root.geometry("720x500")

        self._store = ConfigStore()
        self._git = GitService()
        self._editor = EditorService(self._store)
        self._current_frame = None

        if repo_path:
            self._load_repo(repo_path)
        else:
            self._show_landing()

    def run(self):
        self._root.mainloop()

    def _clear(self):
        if self._current_frame:
            self._current_frame.destroy()
            self._current_frame = None

    def _show_landing(self):
        self._clear()
        from worktree_manager.landing_screen import LandingScreenViewModel
        from worktree_manager.ui.landing_screen import LandingScreen
        vm = LandingScreenViewModel(config_store=self._store, git_service=self._git)
        self._current_frame = LandingScreen(
            self._root, vm=vm, on_repo_chosen=self._load_repo
        )
        self._current_frame.pack(fill="both", expand=True)

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
        from datetime import datetime, timezone
        from worktree_manager.main_window_vm import MainWindowViewModel
        from worktree_manager.ui.main_window import MainWindow

        cfg = self._store.get_repo(repo_path)
        cfg.last_opened = datetime.now(timezone.utc).isoformat()
        self._store.save_repo(cfg)

        self._clear()
        vm = MainWindowViewModel(
            repo_path=repo_path,
            config_store=self._store,
            git_service=self._git,
            editor_service=self._editor,
        )
        repo_name = Path(repo_path).name
        self._current_frame = MainWindow(
            self._root, vm=vm, repo_name=repo_name,
            on_settings=lambda: self._show_settings(repo_path),
            on_cleanup=lambda: self._show_cleanup(vm),
        )
        self._current_frame.pack(fill="both", expand=True)

    def _show_settings(self, repo_path: str):
        from worktree_manager.setup_settings_vm import SettingsViewModel
        from worktree_manager.ui.settings_panel import SettingsPanel
        vm = SettingsViewModel(repo_path=repo_path, config_store=self._store)
        SettingsPanel(self._root, vm=vm)

    def _show_cleanup(self, main_vm):
        import tkinter.messagebox as mb
        from worktree_manager.ui.cleanup_wizard import CleanupWizard
        candidates = main_vm.all_cleanup_candidates()
        if not candidates:
            mb.showinfo("Cleanup", "Nothing to clean up.")
            return

        def _on_delete(selected, also_branches):
            main_vm.delete_cleanup_candidates(selected, also_branches)
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
    main()
