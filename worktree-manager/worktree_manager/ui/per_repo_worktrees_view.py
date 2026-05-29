import os
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QMenu, QMessageBox, QPushButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from worktree_manager.main_window_vm import MainWindowViewModel
from worktree_manager.models import WorktreeModel
from worktree_manager.ui.background_job import BackgroundJob
from worktree_manager.ui.delete_dialog import DeleteDialog
from worktree_manager.ui.inline_progress import InlineProgress


def _fmt_age(ts):
    if ts == 0:
        return "no commits"
    diff = int(time.time()) - ts
    if diff < 3600:
        return f"{diff // 60}m ago"
    if diff < 86400:
        return f"{diff // 3600}h ago"
    return f"{diff // 86400}d ago"


class PerRepoWorktreesView(QWidget):
    def __init__(
        self,
        vm: MainWindowViewModel,
        repo_name: str,
        on_cleanup,
        on_new,
        on_generate_project=None,
        on_run_command=None,
        parent=None,
        on_nickname=None,
        on_diff_from_working_tree=None,
        on_diff_compare_branches=None,
    ):
        super().__init__(parent)
        self._vm = vm
        self._repo_name = repo_name
        self._on_cleanup = on_cleanup
        self._on_new = on_new
        self._on_generate_project = on_generate_project
        self._on_run_command = on_run_command
        self._on_nickname = on_nickname
        self._on_diff_from_working_tree = on_diff_from_working_tree
        self._on_diff_compare_branches = on_diff_compare_branches
        self._worktree_rows: list[QWidget] = []
        self._toast_timer: QTimer | None = None
        self._loading: bool = False
        self._refresh_job: BackgroundJob | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 8)
        outer.setSpacing(4)

        header = QHBoxLayout()
        title = QLabel(f"Worktrees — {self._repo_name}")
        title.setStyleSheet("font-weight: bold; font-size: 16px;")
        header.addWidget(title)
        header.addStretch(1)
        cleanup_btn = QPushButton("🧹")
        cleanup_btn.setFixedWidth(36)
        cleanup_btn.clicked.connect(self._on_cleanup)
        header.addWidget(cleanup_btn)
        outer.addLayout(header)

        self._toast_label = QLabel("")
        self._toast_label.setStyleSheet(
            "color: #27ae60; background: #eafaf1; border: 1px solid #a9dfbf;"
            " padding: 4px 8px; border-radius: 4px;"
        )
        self._toast_label.setVisible(False)
        outer.addWidget(self._toast_label)

        sub = QHBoxLayout()
        sub_label = QLabel("Worktrees")
        sub_label.setStyleSheet("font-weight: bold;")
        sub.addWidget(sub_label)
        sub.addStretch(1)
        new_btn = QPushButton("+ New")
        new_btn.setFixedWidth(70)
        new_btn.clicked.connect(self._on_new)
        sub.addWidget(new_btn)
        outer.addLayout(sub)

        self._list_scroll = QScrollArea()
        self._list_scroll.setWidgetResizable(True)
        self._list_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(2)
        self._list_layout.addStretch(1)
        self._list_scroll.setWidget(self._list_container)
        outer.addWidget(self._list_scroll, 1)

        self.refresh()

    def refresh(self):
        if self._refresh_job is not None:
            self._refresh_job.progress.disconnect()
            self._refresh_job.finished.disconnect()
            self._refresh_job.failed.disconnect()
            self._refresh_job = None

        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._worktree_rows.clear()
        self._loading = True

        loader = InlineProgress()
        loader.start_determinate("Loading worktrees…", total=1)
        self._list_layout.addWidget(loader)

        job = BackgroundJob(self)
        self._refresh_job = job
        job.progress.connect(
            lambda cur, tot, lbl: loader.update(cur, lbl) if self._loading else None
        )
        job.finished.connect(lambda data: self._on_refresh_done(data))
        job.failed.connect(lambda exc: self._on_refresh_failed(exc))
        job.start(self._vm.load_worktree_view_data)

    def _on_refresh_done(self, data: dict) -> None:
        self._loading = False
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._worktree_rows.clear()

        worktrees = data["worktrees"]
        branch_status = data["branch_status"]
        for wt in worktrees:
            self._add_row(wt, branch_status)
        self._list_layout.addStretch(1)

    def _on_refresh_failed(self, exc: Exception) -> None:
        self._loading = False
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        err = QLabel(f"⚠ Couldn't load worktrees.\n{exc}")
        err.setAlignment(Qt.AlignCenter)
        err.setStyleSheet("color: #c0392b;")
        self._list_layout.addWidget(err)
        retry = QPushButton("Retry")
        retry.setFixedWidth(80)
        retry.clicked.connect(self.refresh)
        self._list_layout.addWidget(retry, 0, Qt.AlignCenter)
        self._list_layout.addStretch(1)

    def _add_row(self, wt: WorktreeModel, branch_status):
        row = QWidget()
        row.setContextMenuPolicy(Qt.CustomContextMenu)
        row.customContextMenuRequested.connect(
            lambda pos, w=wt: self._show_context_menu(w.path, pos, row)
        )
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 2, 0, 2)

        dot = QLabel("●" if wt.is_main else "○")
        dot.setFixedWidth(20)
        layout.addWidget(dot)

        wt_name = os.path.basename(wt.path) if not wt.is_main else "(main)"
        name_label = QLabel(wt_name)
        name_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(name_label)

        age = QLabel(_fmt_age(wt.last_commit_ts))
        age.setStyleSheet("color: gray;")
        layout.addWidget(age)

        if wt.is_stale:
            stale = QLabel("⚠ stale")
            stale.setStyleSheet("color: orange;")
            layout.addWidget(stale)

        layout.addStretch(1)

        all_branches = [b for b, _ in branch_status]
        checked_out_set = {b for b, co in branch_status if co and b != wt.branch}

        combo = QComboBox()
        combo.addItems(all_branches)
        if wt.branch in all_branches:
            combo.setCurrentText(wt.branch)
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        def _on_change(new_branch, path=wt.path, c=combo, orig=wt.branch):
            if new_branch == orig:
                return
            if new_branch in checked_out_set:
                QMessageBox.critical(
                    self, "Cannot switch",
                    f"'{new_branch}' is already checked out in another worktree.",
                )
                c.blockSignals(True)
                c.setCurrentText(orig)
                c.blockSignals(False)
                return
            if not self._switch_branch(path, new_branch):
                c.blockSignals(True)
                c.setCurrentText(orig)
                c.blockSignals(False)

        combo.currentTextChanged.connect(_on_change)
        layout.addWidget(combo)

        if not wt.is_main:
            del_btn = QPushButton("✕")
            del_btn.setFixedWidth(28)
            del_btn.setStyleSheet(
                "background-color: #c0392b; color: white; border: none;"
            )
            del_btn.clicked.connect(lambda _checked=False, w=wt: self._open_delete(w))
            if self._on_nickname is not None:
                from PySide6.QtCore import Qt as _Qt
                wt_name_str = wt.path.split("/")[-1]
                del_btn.setContextMenuPolicy(_Qt.CustomContextMenu)
                del_btn.customContextMenuRequested.connect(
                    lambda pos, b=del_btn, n=wt_name_str: self._show_worktree_nickname_menu(b, n)
                )
            layout.addWidget(del_btn)

        self._worktree_rows.append(row)
        self._list_layout.addWidget(row)

    def _show_worktree_nickname_menu(self, btn, worktree_name: str) -> None:
        menu = QMenu(self)
        menu.addAction("Add Nickname…").triggered.connect(
            lambda: self._on_nickname("delete_worktree", {
                "repo": self._repo_name,
                "worktree": worktree_name,
            })
        )
        menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def _build_context_menu(self, worktree_path: str) -> QMenu:
        menu = QMenu(self)
        gen_act = menu.addAction("Generate Project")
        gen_act.triggered.connect(lambda: self._trigger_generate_project(worktree_path))
        run_act = menu.addAction("Run Command…")
        run_act.triggered.connect(lambda: self._trigger_run_command(worktree_path))
        menu.addSeparator()
        diff_wt_act = menu.addAction("Diff from working tree…")
        diff_wt_act.triggered.connect(lambda: self._trigger_diff_from_working_tree(worktree_path))
        diff_br_act = menu.addAction("Compare branches…")
        diff_br_act.triggered.connect(lambda: self._trigger_diff_compare_branches(worktree_path))
        return menu

    def _trigger_diff_from_working_tree(self, worktree_path: str):
        if self._on_diff_from_working_tree:
            self._on_diff_from_working_tree(worktree_path)

    def _trigger_diff_compare_branches(self, worktree_path: str):
        if self._on_diff_compare_branches:
            self._on_diff_compare_branches(worktree_path)

    def _show_context_menu(self, worktree_path: str, pos, row: QWidget):
        menu = self._build_context_menu(worktree_path)
        menu.exec(row.mapToGlobal(pos))

    def _trigger_generate_project(self, worktree_path: str):
        if self._on_generate_project:
            self._on_generate_project(worktree_path)
        import os as _os
        name = _os.path.basename(worktree_path) or worktree_path
        self.show_toast(f"✅ Project '{name}' created")

    def _trigger_run_command(self, worktree_path: str):
        if self._on_run_command:
            self._on_run_command(worktree_path)

    def show_toast(self, message: str):
        self._toast_label.setText(message)
        self._toast_label.setVisible(True)
        if self._toast_timer:
            self._toast_timer.stop()
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(lambda: self._toast_label.setVisible(False))
        self._toast_timer.start(3000)

    def _switch_branch(self, worktree_path, new_branch):
        try:
            self._vm.switch_branch(worktree_path, new_branch)
            self.refresh()
            return True
        except ValueError as e:
            QMessageBox.critical(self, "Cannot switch branch", str(e))
            return False

    def _open_delete(self, wt: WorktreeModel):
        def _on_delete(_wt, also_branch):
            try:
                self._vm.delete_worktree(
                    path=_wt.path, branch=_wt.branch,
                    also_delete_branch=also_branch,
                )
            except Exception as e:
                QMessageBox.critical(self, "Delete failed", str(e))
                return
            self.refresh()

        dlg = DeleteDialog(
            parent=self, wt=wt, on_delete=_on_delete,
            is_protected=self._vm.is_protected_branch(wt.branch),
            has_uncommitted=self._vm.has_uncommitted_changes(wt.path),
        )
        dlg.exec()
