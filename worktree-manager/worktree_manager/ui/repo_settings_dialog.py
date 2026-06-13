from PySide6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt


_NOTIFICATION_EVENTS = [
    ("ci_failed",       "CI failed"),
    ("ci_passed",       "CI passed"),
    ("new_comment",     "New comments"),
    ("ready_to_merge",  "Ready to merge"),
    ("review",          "Review approved / changes requested"),
    ("pr_conflicts",    "Merge conflicts"),
]


class RepoSettingsDialog(QDialog):
    def __init__(self, repo: str, store, discovered_check_names: list[str], parent=None):
        super().__init__(parent)
        self._repo = repo
        self._store = store
        self.setWindowTitle(f"⚙  {repo}  settings")
        self.setMinimumWidth(420)

        outer = QVBoxLayout(self)
        outer.setSpacing(12)

        # ── Muted checks ──────────────────────────────────────────────────────
        outer.addWidget(_section_label("Muted checks"))
        outer.addWidget(_hint("Muted checks no longer affect this repo's PRs' overall CI status."))

        muted = set(store.get_repo_muted_checks(repo))
        all_names = sorted(set(discovered_check_names) | muted)

        self._check_boxes: dict[str, QCheckBox] = {}
        checks_widget = QWidget()
        checks_layout = QVBoxLayout(checks_widget)
        checks_layout.setContentsMargins(0, 0, 0, 0)
        checks_layout.setSpacing(4)

        if all_names:
            for name in all_names:
                cb = QCheckBox(name)
                cb.setChecked(name in muted)
                cb.toggled.connect(lambda checked, n=name: self._on_check_toggled(n, checked))
                checks_layout.addWidget(cb)
                self._check_boxes[name] = cb
        else:
            checks_layout.addWidget(QLabel("No check runs seen yet for this repo."))

        outer.addWidget(checks_widget)

        # manual-add row
        add_row = QHBoxLayout()
        self._add_name_edit = QLineEdit()
        self._add_name_edit.setPlaceholderText("Check name to mute…")
        add_btn = QPushButton("Add & mute")
        add_btn.clicked.connect(self._on_add_mute)
        add_row.addWidget(self._add_name_edit, 1)
        add_row.addWidget(add_btn)
        outer.addLayout(add_row)

        # ── Notifications ─────────────────────────────────────────────────────
        outer.addWidget(_section_label("Notifications (for this repo)"))
        outer.addWidget(_hint("Only fire when the global 🔔 is on."))

        for event_type, label in _NOTIFICATION_EVENTS:
            enabled = store.get_repo_notification_pref(repo, event_type)
            cb = QCheckBox(label)
            cb.setChecked(enabled)
            cb.toggled.connect(
                lambda checked, et=event_type: store.set_repo_notification_pref(repo, et, checked)
            )
            outer.addWidget(cb)

        # ── Close ─────────────────────────────────────────────────────────────
        outer.addStretch(1)
        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        outer.addLayout(close_row)

    def _on_check_toggled(self, name: str, checked: bool) -> None:
        muted = set(self._store.get_repo_muted_checks(self._repo))
        if checked:
            muted.add(name)
        else:
            muted.discard(name)
        self._store.set_repo_muted_checks(self._repo, sorted(muted))

    def _on_add_mute(self) -> None:
        name = self._add_name_edit.text().strip()
        if not name:
            return
        muted = set(self._store.get_repo_muted_checks(self._repo))
        muted.add(name)
        self._store.set_repo_muted_checks(self._repo, sorted(muted))
        self._add_name_edit.clear()
        # add a checked checkbox if not already shown
        if name not in self._check_boxes:
            cb = QCheckBox(name)
            cb.setChecked(True)
            cb.toggled.connect(lambda checked, n=name: self._on_check_toggled(n, checked))
            # insert into checks_widget layout — find it via the first checkbox's parent
            if self._check_boxes:
                layout = next(iter(self._check_boxes.values())).parentWidget().layout()
            else:
                layout = None
            if layout:
                layout.addWidget(cb)
            self._check_boxes[name] = cb


def _section_label(text: str) -> QLabel:
    lbl = QLabel(f"── {text} ──────────────────────────")
    lbl.setStyleSheet("font-weight: bold; color: #888; font-size: 11px;")
    return lbl


def _hint(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet("color: gray; font-size: 11px;")
    lbl.setWordWrap(True)
    return lbl
