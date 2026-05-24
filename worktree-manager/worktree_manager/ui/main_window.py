import os
import time

from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from worktree_manager.main_window_vm import MainWindowViewModel
from worktree_manager.models import WorktreeModel


def _fmt_age(ts):
    if ts == 0:
        return "no commits"
    diff = int(time.time()) - ts
    if diff < 3600:
        return f"{diff // 60}m ago"
    if diff < 86400:
        return f"{diff // 3600}h ago"
    return f"{diff // 86400}d ago"


class MainWindow(QWidget):
    def __init__(self, vm: MainWindowViewModel, repo_name: str,
                 on_settings, on_cleanup, on_new, parent=None):
        super().__init__(parent)
        self._vm = vm
        self._repo_name = repo_name
        self._on_settings = on_settings
        self._on_cleanup = on_cleanup
        self._on_new = on_new

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 8)
        outer.setSpacing(4)

        header = QHBoxLayout()
        title = QLabel(f"Git Worktree Manager — {self._repo_name}")
        title.setStyleSheet("font-weight: bold; font-size: 16px;")
        header.addWidget(title)
        header.addStretch(1)
        cleanup_btn = QPushButton("🧹")
        cleanup_btn.setFixedWidth(36)
        cleanup_btn.clicked.connect(self._on_cleanup)
        settings_btn = QPushButton("⚙")
        settings_btn.setFixedWidth(36)
        settings_btn.clicked.connect(self._on_settings)
        header.addWidget(cleanup_btn)
        header.addWidget(settings_btn)
        outer.addLayout(header)

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
        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(2)
        self._list_layout.addStretch(1)
        self._list_scroll.setWidget(self._list_container)
        outer.addWidget(self._list_scroll, 1)

        self.refresh()

    def refresh(self):
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        worktrees = self._vm.load_worktrees()
        branch_status = self._vm.list_branches_with_checkout_status()
        for wt in worktrees:
            self._add_row(wt, branch_status)
        self._list_layout.addStretch(1)

    def _add_row(self, wt: WorktreeModel, branch_status):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 2, 0, 2)

        dot = QLabel("●" if wt.is_main else "○")
        dot.setFixedWidth(20)
        layout.addWidget(dot)

        wt_name = os.path.basename(wt.path) if not wt.is_main else "(main)"
        name_label = QLabel(wt_name)
        name_label.setFixedWidth(200)
        layout.addWidget(name_label)

        age = QLabel(_fmt_age(wt.last_commit_ts))
        age.setStyleSheet("color: gray;")
        age.setFixedWidth(80)
        layout.addWidget(age)

        if wt.is_stale:
            stale = QLabel("⚠ stale")
            stale.setStyleSheet("color: orange;")
            stale.setFixedWidth(70)
            layout.addWidget(stale)
        else:
            spacer = QLabel("")
            spacer.setFixedWidth(70)
            layout.addWidget(spacer)

        layout.addStretch(1)

        all_branches = [b for b, _ in branch_status]
        checked_out_set = {b for b, co in branch_status if co and b != wt.branch}

        combo = QComboBox()
        combo.addItems(all_branches)
        if wt.branch in all_branches:
            combo.setCurrentText(wt.branch)
        combo.setFixedWidth(160)

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
            layout.addWidget(del_btn)

        self._list_layout.addWidget(row)

    def _switch_branch(self, worktree_path, new_branch):
        try:
            self._vm.switch_branch(worktree_path, new_branch)
            self.refresh()
            return True
        except ValueError as e:
            QMessageBox.critical(self, "Cannot switch branch", str(e))
            return False

    def _open_delete(self, wt: WorktreeModel):
        # Stubbed in Iteration 0 — real DeleteDialog arrives in Iteration 1.
        print(f"[stub] delete worktree: {wt.path}")
