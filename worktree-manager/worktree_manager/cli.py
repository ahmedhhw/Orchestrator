import argparse
import os
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QMainWindow, QMessageBox,
    QWidget,
)

from worktree_manager.command_center_vm import CommandCenterViewModel
from worktree_manager.config_store import ConfigStore
from worktree_manager.git_service import GitService
from worktree_manager.setup_settings_vm import RepoSetupViewModel, SettingsViewModel
from worktree_manager.workspace_projects_vm import WorkspaceProjectsViewModel
from worktree_manager.workspace_service import WorkspaceService
from worktree_manager.ui.cleanup_wizard import CleanupWizard
from worktree_manager.ui.command_center_panel import CommandCenterPanel
from worktree_manager.ui.create_dialog import CreateDialog
from worktree_manager.ui.main_window import MainWindow
from worktree_manager.ui.repo_setup_dialog import RepoSetupDialog
from worktree_manager.ui.settings_panel import SettingsDialog
from worktree_manager.ui.launch_dialog import LaunchDialog
from worktree_manager.ui.workspace_projects_panel import WorkspaceProjectsPanel


class _CleanupLoadBridge(QObject):
    progress_updated = Signal(int, int, str)
    loading_finished = Signal(list)


class _FinishedBridge(QObject):
    command_finished = Signal(str, object)
    startup_detected = Signal(str, object)


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Git Worktree Manager")
    parser.add_argument("repo_path", nargs="?", default=None,
                        help="Path to the main git worktree")
    return parser.parse_args(argv)


def resolve_repo_path(path, git):
    if path is None:
        return None
    if not git.is_valid_repo(path):
        print(f"Error: '{path}' is not a git repository.", file=sys.stderr)
        sys.exit(1)
    return path


class App(QMainWindow):
    def __init__(self, repo_path=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Git Worktree Manager")
        self.resize(900, 520)
        self.setMinimumSize(700, 400)

        self._store = ConfigStore()
        self._git = GitService()
        self._active_repo_path = None
        self._current_panel = None
        self._command_center_vm: CommandCenterViewModel | None = None
        self._finished_bridge = _FinishedBridge()
        self._finished_bridge.command_finished.connect(self._on_command_finished)
        self._finished_bridge.startup_detected.connect(self._on_startup_detected)

        central = QWidget()
        self._central_layout = QHBoxLayout(central)
        self._central_layout.setContentsMargins(0, 0, 0, 0)
        self._central_layout.setSpacing(0)
        self.setCentralWidget(central)

        from worktree_manager.ui.sidebar import Sidebar
        self._sidebar = Sidebar(
            store=self._store,
            on_command_center=self._show_command_center,
            on_workspace_projects=self._show_workspace_projects,
            on_add_repo=self._pick_and_add_repo,
            on_refresh=self._refresh,
            on_repo_selected=self._switch_repo,
            on_repo_delete=lambda p: self._confirm_delete_repo(
                p, is_active=(p == self._active_repo_path),
            ),
            active_repo_path=None,
        )
        self._central_layout.addWidget(self._sidebar)

        if repo_path:
            self._load_repo(repo_path)
        else:
            self._show_empty_main()

        self._setup_spotlight()

    def _setup_spotlight(self) -> None:
        from PySide6.QtGui import QKeySequence, QShortcut
        from worktree_manager.spotlight.action_parser import ActionParser
        from worktree_manager.spotlight.action_registry import (
            ActionRegistry, ActionSpec, ArgSlot,
        )
        from worktree_manager.ui.spotlight_overlay import SpotlightOverlay
        from worktree_manager.workspace_projects_vm import WorkspaceProjectsViewModel
        from worktree_manager.workspace_service import WorkspaceService

        self._spotlight_registry = ActionRegistry()
        self._wp_vm = WorkspaceProjectsViewModel(
            config_store=self._store,
            git_service=self._git,
            workspace_service=WorkspaceService(),
        )

        def _run_open_project(args):
            name = args["name"]
            repos = self._store.all_repos()
            cfg = next(iter(repos.values()), None)
            editor = cfg.last_editor if cfg else "code"
            self._wp_vm.open_project(name, editor)

        self._spotlight_registry.register(ActionSpec(
            name="open_project",
            keywords=["project"],
            slots=[ArgSlot(
                name="name",
                candidates=lambda prev: [p.name for p in self._store.all_projects()],
            )],
            runner=_run_open_project,
            description="Open a workspace project",
        ))

        # ── edit project ──────────────────────────────────────────────────
        from worktree_manager.ui.project_operations_dialog import (
            ProjectOperationsDialog,
        )

        def _run_edit_project(args):
            name = args["name"]
            project = self._store.get_project(name)
            if project is None:
                return
            dlg = ProjectOperationsDialog(
                parent=self, vm=self._wp_vm,
                repos=self._store.all_repos(),
                on_edit=lambda old, new, entries: self._wp_vm.update_project(
                    old_name=old, new_name=new, entries=entries,
                ),
                existing_project=project,
            )
            dlg.exec()

        self._spotlight_registry.register(ActionSpec(
            name="edit_project",
            keywords=["edit", "project"],
            slots=[ArgSlot(
                name="name",
                candidates=lambda prev: [p.name for p in self._store.all_projects()],
            )],
            runner=_run_edit_project,
            description="Edit a workspace project",
        ))

        # ── repo <name> ───────────────────────────────────────────────────
        def _repo_path_by_name(name: str) -> str | None:
            for path in self._store.all_repos():
                if Path(path).name == name:
                    return path
            return None

        def _run_focus_repo(args):
            path = _repo_path_by_name(args["name"])
            if path is not None:
                self._load_repo(path)

        self._spotlight_registry.register(ActionSpec(
            name="focus_repo",
            keywords=["repo"],
            slots=[ArgSlot(
                name="name",
                candidates=lambda prev: [Path(p).name for p in self._store.all_repos()],
            )],
            runner=_run_focus_repo,
            description="Focus a repo's main window",
        ))

        # ── command <repo> <worktree> <cmd-name> ──────────────────────────
        def _command_worktrees(prev):
            path = _repo_path_by_name(prev.get("repo", ""))
            if path is None:
                return []
            return [Path(w.path).name for w in self._git.list_worktrees(path)]

        def _command_cmd_names(prev):
            path = _repo_path_by_name(prev.get("repo", ""))
            if path is None:
                return []
            return [c.name for c in self._store.get_commands(path)]

        def _run_command(args):
            repo_path = _repo_path_by_name(args["repo"])
            if repo_path is None:
                return
            wt_path = None
            for w in self._git.list_worktrees(repo_path):
                if Path(w.path).name == args["worktree"]:
                    wt_path = w.path
                    break
            if wt_path is None:
                return
            cmd = next(
                (c for c in self._store.get_commands(repo_path) if c.name == args["cmd"]),
                None,
            )
            if cmd is None:
                return
            self._ensure_command_center_vm()
            self._command_center_vm.launch(
                repo_path=repo_path, repo_name=Path(repo_path).name,
                cmd_name=cmd.name, command_str=cmd.command,
                worktree_path=wt_path,
                startup_pattern=cmd.startup_pattern,
            )
            self._show_command_center()

        self._spotlight_registry.register(ActionSpec(
            name="run_command",
            keywords=["command"],
            slots=[
                ArgSlot(name="repo", candidates=lambda prev: [
                    Path(p).name for p in self._store.all_repos()
                ]),
                ArgSlot(name="worktree", candidates=_command_worktrees),
                ArgSlot(name="cmd", candidates=_command_cmd_names),
            ],
            runner=_run_command,
            description="Run a saved command",
        ))

        # ── switch <worktree> <branch> ────────────────────────────────────
        def _all_worktree_names(_prev):
            names = []
            for repo_path in self._store.all_repos():
                for w in self._git.list_worktrees(repo_path):
                    names.append(Path(w.path).name)
            return names

        def _branches_for_worktree(prev):
            wt_name = prev.get("worktree", "")
            for repo_path in self._store.all_repos():
                for w in self._git.list_worktrees(repo_path):
                    if Path(w.path).name == wt_name:
                        return self._git.list_local_branches(repo_path)
            return []

        def _run_switch(args):
            from worktree_manager.main_window_vm import MainWindowViewModel
            wt_name = args["worktree"]
            branch = args["branch"]
            for repo_path in self._store.all_repos():
                for w in self._git.list_worktrees(repo_path):
                    if Path(w.path).name == wt_name:
                        vm = MainWindowViewModel(
                            repo_path=repo_path,
                            config_store=self._store,
                            git_service=self._git,
                        )
                        vm.switch_branch(w.path, branch)
                        if self._current_panel is not None and hasattr(
                            self._current_panel, "refresh"
                        ):
                            self._current_panel.refresh()
                        return

        self._spotlight_registry.register(ActionSpec(
            name="switch_branch",
            keywords=["switch"],
            slots=[
                ArgSlot(name="worktree", candidates=_all_worktree_names),
                ArgSlot(name="branch", candidates=_branches_for_worktree),
            ],
            runner=_run_switch,
            description="Switch a worktree's branch",
        ))

        # ── cleanup <repo> ────────────────────────────────────────────────
        def _run_cleanup_repo(args):
            path = _repo_path_by_name(args["name"])
            if path is None:
                return
            from worktree_manager.main_window_vm import MainWindowViewModel
            vm = MainWindowViewModel(
                repo_path=path,
                config_store=self._store,
                git_service=self._git,
            )
            self._show_cleanup(vm)

        self._spotlight_registry.register(ActionSpec(
            name="cleanup_repo",
            keywords=["cleanup"],
            slots=[ArgSlot(
                name="name",
                candidates=lambda prev: [Path(p).name for p in self._store.all_repos()],
            )],
            runner=_run_cleanup_repo,
            description="Open cleanup wizard",
        ))

        # ── settings ──────────────────────────────────────────────────────
        def _run_settings(_args):
            repo_path = self._active_repo_path or next(
                iter(self._store.all_repos()), None
            )
            if repo_path is None:
                return
            self._show_settings(repo_path)

        self._spotlight_registry.register(ActionSpec(
            name="open_settings",
            keywords=["settings"],
            slots=[],
            runner=_run_settings,
            description="Open settings",
        ))

        # ── new worktree <repo> ───────────────────────────────────────────
        from worktree_manager.main_window_vm import MainWindowViewModel

        def _run_new_worktree(args):
            path = _repo_path_by_name(args["repo"])
            if path is None:
                return
            vm = MainWindowViewModel(
                repo_path=path,
                config_store=self._store,
                git_service=self._git,
            )
            self._show_new_worktree(vm)

        self._spotlight_registry.register(ActionSpec(
            name="new_worktree",
            keywords=["new", "worktree"],
            slots=[ArgSlot(
                name="repo",
                candidates=lambda prev: [Path(p).name for p in self._store.all_repos()],
            )],
            runner=_run_new_worktree,
            description="Create a new worktree",
        ))

        # ── new project ───────────────────────────────────────────────────
        def _run_new_project(_args):
            dlg = ProjectOperationsDialog(
                parent=self, vm=self._wp_vm,
                repos=self._store.all_repos(),
                on_create=lambda name, entries: self._wp_vm.create_project(
                    name=name, entries=entries,
                ),
            )
            dlg.exec()

        self._spotlight_registry.register(ActionSpec(
            name="new_project",
            keywords=["new", "project"],
            slots=[],
            runner=_run_new_project,
            description="Create a new workspace project",
        ))

        # ── new command <repo> ────────────────────────────────────────────
        from worktree_manager.ui.add_command_dialog import AddCommandDialog

        def _run_new_command(args):
            path = _repo_path_by_name(args["repo"])
            if path is None:
                return
            self._ensure_command_center_vm()
            dlg = AddCommandDialog(
                parent=self, vm=self._command_center_vm,
                initial_repo=path,
            )
            dlg.exec()

        self._spotlight_registry.register(ActionSpec(
            name="new_command",
            keywords=["new", "command"],
            slots=[ArgSlot(
                name="repo",
                candidates=lambda prev: [Path(p).name for p in self._store.all_repos()],
            )],
            runner=_run_new_command,
            description="Add a new saved command",
        ))

        # ── edit command <repo> ───────────────────────────────────────────
        from worktree_manager.ui.manage_commands_dialog import ManageCommandsDialog

        def _run_edit_command(args):
            path = _repo_path_by_name(args["repo"])
            if path is None:
                return
            self._ensure_command_center_vm()
            dlg = ManageCommandsDialog(
                parent=self, vm=self._command_center_vm,
                initial_repo=path,
            )
            dlg.exec()

        self._spotlight_registry.register(ActionSpec(
            name="edit_command",
            keywords=["edit", "command"],
            slots=[ArgSlot(
                name="repo",
                candidates=lambda prev: [Path(p).name for p in self._store.all_repos()],
            )],
            runner=_run_edit_command,
            description="Manage saved commands for a repo",
        ))

        # ── new repo ──────────────────────────────────────────────────────
        self._spotlight_registry.register(ActionSpec(
            name="new_repo",
            keywords=["new", "repo"],
            slots=[],
            runner=lambda _args: self._pick_and_add_repo(),
            description="Add a new repo",
        ))

        self._spotlight_overlay = SpotlightOverlay(
            parser=ActionParser(self._spotlight_registry),
            parent=self,
        )
        from PySide6.QtCore import Qt as _Qt
        shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        shortcut.setContext(_Qt.ApplicationShortcut)
        shortcut.activated.connect(self._open_spotlight)

    def _open_spotlight(self) -> None:
        self._spotlight_overlay.show_centered_over(self)

    def spotlight_registry(self):
        return self._spotlight_registry

    def open_spotlight_for_test(self):
        self._open_spotlight()
        return self._spotlight_overlay

    # ── panel swap helpers ──────────────────────────────────────────────────

    def _set_panel(self, widget):
        if self._current_panel is not None:
            self._central_layout.removeWidget(self._current_panel)
            self._current_panel.deleteLater()
        self._current_panel = widget
        self._central_layout.addWidget(widget, 1)

    def _show_empty_main(self):
        from worktree_manager.ui.landing_screen import LandingScreen
        self._set_panel(LandingScreen())

    # ── repo lifecycle ──────────────────────────────────────────────────────

    def _pick_and_add_repo(self):
        path = QFileDialog.getExistingDirectory(self, "Select git repo")
        if not path:
            return
        if not self._git.is_valid_repo(path):
            QMessageBox.critical(self, "Error", f"'{path}' is not a git repository.")
            return
        self._load_repo(path)

    def _switch_repo(self, repo_path):
        self._load_repo(repo_path)

    def _load_repo(self, repo_path):
        cfg = self._store.get_repo(repo_path)
        if cfg is None:
            vm = RepoSetupViewModel(repo_path=repo_path, config_store=self._store)
            dlg = RepoSetupDialog(
                parent=self, vm=vm,
                on_confirm=lambda: self._show_main(repo_path),
            )
            dlg.exec()
            self._sidebar.populate_repo_rows()
            return
        self._show_main(repo_path)

    def _show_main(self, repo_path):
        from worktree_manager.main_window_vm import MainWindowViewModel
        from worktree_manager.ui.main_window import MainWindow

        self._active_repo_path = repo_path
        self._sidebar.set_active_repo(repo_path)

        vm = MainWindowViewModel(
            repo_path=repo_path,
            config_store=self._store,
            git_service=self._git,
        )
        repo_name = Path(repo_path).name
        self._set_panel(MainWindow(
            vm=vm, repo_name=repo_name,
            on_settings=lambda: self._show_settings(repo_path),
            on_cleanup=lambda: self._show_cleanup(vm),
            on_new=lambda: self._show_new_worktree(vm),
            on_generate_project=self._on_generate_project,
            on_run_command=self._on_run_command,
        ))

    def _confirm_delete_repo(self, repo_path, is_active):
        name = Path(repo_path).name
        extra = (
            "\n\nThis is the currently open repo. Removing it will return you to the empty screen."
            if is_active else ""
        )
        ans = QMessageBox.question(
            self, "Remove repo",
            f'Remove "{name}" from the app?\n\n{repo_path}{extra}\n\nFiles on disk are not affected.',
        )
        if ans != QMessageBox.Yes:
            return
        self._store.delete_repo(repo_path)
        if is_active:
            self._active_repo_path = None
            self._sidebar.set_active_repo(None)
            self._show_empty_main()
        else:
            self._sidebar.populate_repo_rows()

    def _refresh(self):
        self._sidebar.populate_repo_rows()
        if self._current_panel is not None and hasattr(self._current_panel, "refresh"):
            self._current_panel.refresh()

    # ── stubs for panels arriving in later iterations ───────────────────────

    def _show_settings(self, repo_path):
        vm = SettingsViewModel(repo_path=repo_path, config_store=self._store)
        dlg = SettingsDialog(parent=self, vm=vm)
        dlg.exec()
        self._refresh()

    def _show_cleanup(self, vm):
        def _on_delete(selected: list):
            vm.delete_cleanup_candidates(selected, also_delete_branches=True)
            if self._current_panel is not None and hasattr(self._current_panel, "refresh"):
                self._current_panel.refresh()

        wizard = CleanupWizard(
            parent=self, candidates=None, on_delete_selected=_on_delete,
        )

        bridge = _CleanupLoadBridge()
        bridge.progress_updated.connect(wizard.update_progress)
        bridge.loading_finished.connect(
            lambda candidates: self._on_cleanup_loaded(wizard, candidates)
        )

        def _load():
            def _on_progress(current, total, label):
                bridge.progress_updated.emit(current, total, label)
            candidates = vm.all_cleanup_candidates(on_progress=_on_progress)
            bridge.loading_finished.emit(candidates)

        threading.Thread(target=_load, daemon=True).start()
        wizard.exec()

    def _on_cleanup_loaded(self, wizard, candidates: list) -> None:
        if not candidates:
            wizard.reject()
            QMessageBox.information(self, "Cleanup", "No branches to clean up.")
            return
        wizard.finish_loading(candidates)

    def _show_new_worktree(self, vm):
        vm.load_worktrees()
        all_branches = vm.list_local_branches()
        available = vm.list_available_branches()

        def _on_create(branch, base_branch, is_existing, worktree_name):
            try:
                vm.create_worktree(
                    branch=branch, base_branch=base_branch,
                    existing=is_existing, worktree_name=worktree_name,
                )
            except ValueError as e:
                QMessageBox.critical(self, "Cannot create worktree", str(e))
                return
            if self._current_panel is not None and hasattr(self._current_panel, "refresh"):
                self._current_panel.refresh()

        dlg = CreateDialog(
            parent=self, branches=all_branches,
            existing_branches=available, on_create=_on_create,
        )
        dlg.exec()

    def _ensure_command_center_vm(self) -> CommandCenterViewModel:
        if self._command_center_vm is None:
            self._command_center_vm = CommandCenterViewModel(
                config_store=self._store, git_service=self._git,
            )
            self._command_center_vm.on_finished = (
                self._finished_bridge.command_finished.emit
            )
            self._command_center_vm.on_startup_detected = (
                self._finished_bridge.startup_detected.emit
            )
        return self._command_center_vm

    def _show_command_center(self):
        self._ensure_command_center_vm()
        self._set_panel(CommandCenterPanel(
            parent=self,
            vm=self._command_center_vm,
            on_close=self._on_command_center_close,
        ))

    def _on_command_center_close(self):
        self._show_empty_main()

    def _show_workspace_projects(self):
        vm = WorkspaceProjectsViewModel(
            config_store=self._store,
            git_service=self._git,
            workspace_service=WorkspaceService(),
        )
        self._set_panel(WorkspaceProjectsPanel(
            parent=self, vm=vm, on_close=self._show_empty_main,
            on_generate_project=self._on_generate_project,
            on_run_command=self._on_run_command,
        ))

    def _on_run_command(self, worktree_path: str) -> None:
        self._ensure_command_center_vm()
        repo_path = self._active_repo_path or worktree_path
        run_count_before = len(self._command_center_vm.all_runs())

        dlg = LaunchDialog(
            parent=self,
            vm=self._command_center_vm,
            locked_repo_path=repo_path,
            locked_worktree_path=worktree_path,
        )
        dlg.exec()

        if len(self._command_center_vm.all_runs()) > run_count_before:
            self._show_command_center()

    def _on_command_finished(self, run_id: str, handle) -> None:
        from worktree_manager.command_runner import RunStatus
        if isinstance(self._current_panel, CommandCenterPanel):
            return
        cmd_name = handle.cmd_name
        if handle.status == RunStatus.ERROR:
            body = f"❌ \"{cmd_name}\" exited with code {handle.returncode}"
        elif handle.returncode == 0:
            body = f"✅ \"{cmd_name}\" finished"
        else:
            body = f"⏹ \"{cmd_name}\" stopped"
        self._show_notification("Command Center", body)
        self._show_command_center()
        if not self.isActiveWindow():
            QApplication.alert(self, 0)

    def _on_startup_detected(self, run_id: str, handle) -> None:
        cmd_name = handle.cmd_name
        if not self.isActiveWindow():
            self._show_notification("Command Center", f"🚀 \"{cmd_name}\" is ready")
            QApplication.alert(self, 0)
        self.show_toast(f"🚀 \"{cmd_name}\" is ready")
        if not isinstance(self._current_panel, CommandCenterPanel):
            self._show_command_center()

    def show_toast(self, message: str) -> None:
        self.statusBar().showMessage(message, 4000)

    def _show_notification(self, title: str, body: str) -> None:
        import subprocess
        safe_title = title.replace('"', '\\"')
        safe_body = body.replace('"', '\\"')
        subprocess.Popen(
            ["osascript", "-e",
             f'display notification "{safe_body}" with title "{safe_title}"'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _on_generate_project(self, worktree_path: str) -> None:
        from worktree_manager.models import WorkspaceEntry, WorkspaceProject
        name = os.path.basename(worktree_path) or worktree_path
        project = WorkspaceProject(
            name=name,
            entries=[WorkspaceEntry(worktree_path=worktree_path)],
        )
        svc = WorkspaceService()
        svc.generate_code_workspace(project)
        action = "updated" if self._store.get_project(name) else "created"
        self._store.save_project(project)
        if isinstance(self._current_panel, MainWindow):
            self._current_panel.show_toast(f"✅ Project \"{name}\" {action}")


def main():
    args = parse_args(sys.argv[1:])
    git = GitService()
    repo_path = resolve_repo_path(args.repo_path, git)

    qt_app = QApplication.instance() or QApplication(sys.argv)
    window = App(repo_path=repo_path)
    window.show()
    sys.exit(qt_app.exec())


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    main()
