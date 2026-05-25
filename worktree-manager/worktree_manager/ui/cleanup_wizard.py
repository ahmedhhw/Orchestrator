import time

from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from worktree_manager.models import CleanupCandidate


def _fmt_age(ts: int) -> str:
    if ts == 0:
        return "no commits"
    return f"{(int(time.time()) - ts) // 86400}d"


def _reason(c: CleanupCandidate) -> str:
    if c.is_merged:
        return f"merged into {c.merged_into or 'main'}"
    if c.is_stale:
        return f"{_fmt_age(c.last_commit_ts)}, stale"
    return f"{_fmt_age(c.last_commit_ts)} ago"


def _group_candidates(candidates: list) -> dict:
    unoperable = [c for c in candidates if c.has_uncommitted or c.is_checked_out]
    protected = [c for c in candidates if c.is_protected and not c.has_uncommitted and not c.is_checked_out]
    operable = [c for c in candidates if not c.is_protected and not c.has_uncommitted and not c.is_checked_out]
    merged = [c for c in operable if c.is_merged]
    stale = [c for c in operable if c.is_stale and not c.is_merged]
    healthy = [c for c in operable if not c.is_stale and not c.is_merged]
    merged.sort(key=lambda c: ((c.merged_into or "main").lower(), c.branch.lower()))
    stale.sort(key=lambda c: c.last_commit_ts)
    return {"merged": merged, "stale": stale, "healthy": healthy,
            "protected": protected, "unoperable": unoperable}


def _merged_subgroups(merged: list) -> list:
    groups: dict = {}
    for c in merged:
        target = c.merged_into or "main"
        groups.setdefault(target, []).append(c)
    for branches in groups.values():
        branches.sort(key=lambda c: c.branch.lower())
    return sorted(groups.items(), key=lambda kv: kv[0].lower())


class CleanupWizard(QDialog):
    def __init__(self, parent, candidates, on_delete_selected):
        super().__init__(parent)
        self.setWindowTitle("Cleanup Wizard")
        self.setModal(True)
        self.resize(520, 520)
        self._on_delete = on_delete_selected
        self._pairs: list[tuple[CleanupCandidate, QCheckBox]] = []
        self._protected_pairs: list[tuple[CleanupCandidate, QCheckBox]] = []
        self._subgroup_btns: dict[str, QPushButton] = {}
        self._stale_btn: QPushButton | None = None
        self._global_btn: QPushButton | None = None
        self._admin_mode: bool = False
        self._admin_banner: QWidget | None = None
        self._progress_bar: QProgressBar | None = None
        self._progress_label: QLabel | None = None
        self._loading: bool = candidates is None

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(24, 16, 24, 16)
        self._outer.setSpacing(6)
        if self._loading:
            self._build_loading()
        else:
            self._build(candidates)

    # --- loading state ---

    def _build_loading(self):
        title = QLabel("Cleanup Wizard")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        self._outer.addWidget(title)
        self._progress_label = QLabel("Scanning branches…")
        self._outer.addWidget(self._progress_label)
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._outer.addWidget(self._progress_bar)
        self._outer.addStretch(1)

    def is_loading(self) -> bool:
        return self._loading

    def update_progress(self, current: int, total: int, label: str) -> None:
        if not self._loading or self._progress_bar is None:
            return
        pct = int(100 * current / total) if total > 0 else 0
        self._progress_bar.setValue(pct)
        self._progress_label.setText(f"{label}  ({current} / {total})")

    def progress_text(self) -> str:
        return self._progress_label.text() if self._progress_label else ""

    def finish_loading(self, candidates: list) -> None:
        while self._outer.count():
            item = self._outer.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
        self._progress_bar = None
        self._progress_label = None
        self._pairs = []
        self._protected_pairs = []
        self._subgroup_btns = {}
        self._stale_btn = None
        self._global_btn = None
        self._admin_banner = None
        self._loading = False
        self._build(candidates)

    # --- main UI ---

    def _build(self, candidates: list):
        title = QLabel("Cleanup Wizard")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        self._outer.addWidget(title)

        self._admin_banner = QLabel(
            "⚠ Admin Mode: Protected branches can be deleted.\n"
            "    Double-check your selection before deleting."
        )
        self._admin_banner.setStyleSheet(
            "background-color: #7b2d00; color: white; padding: 6px 12px;"
        )
        self._admin_banner.setVisible(False)
        self._outer.addWidget(self._admin_banner)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self._list_layout = QVBoxLayout(container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(2)
        scroll.setWidget(container)
        self._outer.addWidget(scroll, 1)

        grouped = _group_candidates(candidates)
        self._render_merged(grouped["merged"])
        self._render_stale(grouped["stale"])
        self._render_healthy(grouped["healthy"])
        self._render_protected(grouped["protected"])
        self._render_unoperable(grouped["unoperable"])
        self._list_layout.addStretch(1)

        admin_row = QHBoxLayout()
        admin_cb = QCheckBox("Admin Mode")
        admin_cb.toggled.connect(self.set_admin_mode)
        admin_row.addWidget(admin_cb)
        admin_warn = QLabel("⚠ Enable only if you know what you're doing")
        admin_warn.setStyleSheet("color: orange;")
        admin_row.addWidget(admin_warn)
        admin_row.addStretch(1)
        self._outer.addLayout(admin_row)

        btn_row = QHBoxLayout()
        self._global_btn = QPushButton("Select All")
        self._global_btn.clicked.connect(self.trigger_select_all)
        btn_row.addWidget(self._global_btn)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        btn_row.addStretch(1)
        delete = QPushButton("Delete")
        delete.setStyleSheet("background-color: #c0392b; color: white;")
        delete.clicked.connect(self.trigger_delete)
        btn_row.addWidget(delete)
        self._outer.addLayout(btn_row)
        self._refresh_button_labels()

    def _add_section_label(self, text: str):
        lbl = QLabel(text)
        lbl.setStyleSheet("color: gray;")
        self._list_layout.addWidget(lbl)

    def _add_divider(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: gray;")
        self._list_layout.addWidget(line)

    def _render_merged(self, merged: list):
        self._add_section_label("Merged:")
        if not merged:
            self._add_section_label("  (none)")
            return
        for target, branches in _merged_subgroups(merged):
            header = QHBoxLayout()
            tlabel = QLabel(f"  → into {target}")
            tlabel.setStyleSheet("color: gray;")
            header.addWidget(tlabel)
            header.addStretch(1)
            btn = QPushButton("Select all")
            btn.setFixedWidth(90)
            btn.clicked.connect(lambda _=False, t=target: self.trigger_subgroup_select(t))
            header.addWidget(btn)
            self._subgroup_btns[target] = btn
            wrap = QWidget()
            wrap.setLayout(header)
            self._list_layout.addWidget(wrap)
            for c in branches:
                self._add_checkbox(c, default_checked=True)

    def _render_stale(self, stale: list):
        self._add_divider()
        header = QHBoxLayout()
        lbl = QLabel("Stale:")
        lbl.setStyleSheet("color: gray;")
        header.addWidget(lbl)
        header.addStretch(1)
        if stale:
            self._stale_btn = QPushButton("Select all")
            self._stale_btn.setFixedWidth(90)
            self._stale_btn.clicked.connect(self.trigger_stale_select)
            header.addWidget(self._stale_btn)
        wrap = QWidget()
        wrap.setLayout(header)
        self._list_layout.addWidget(wrap)
        if not stale:
            self._add_section_label("  (none)")
            return
        for c in stale:
            self._add_checkbox(c, default_checked=True)

    def _render_healthy(self, healthy: list):
        self._add_divider()
        self._add_section_label("Healthy:")
        if not healthy:
            self._add_section_label("  (none)")
            return
        for c in healthy:
            self._add_checkbox(c, default_checked=False)

    def _render_protected(self, protected: list):
        if not protected:
            return
        self._add_divider()
        self._add_section_label("Protected:")
        for c in protected:
            row = QHBoxLayout()
            cb = QCheckBox(f"{c.branch}  ({_reason(c)})")
            cb.setEnabled(False)
            row.addWidget(cb)
            tag = QLabel("⚠ main" if c.branch == "main" else "⚠ feature")
            tag.setStyleSheet("color: orange;")
            row.addWidget(tag)
            row.addStretch(1)
            wrap = QWidget()
            wrap.setLayout(row)
            self._list_layout.addWidget(wrap)
            self._protected_pairs.append((c, cb))

    def _render_unoperable(self, unoperable: list):
        if not unoperable:
            return
        self._add_divider()
        self._add_section_label("Cannot delete:")
        for c in unoperable:
            row = QHBoxLayout()
            txt = QLabel(f"—   {c.branch}  ({_reason(c)})")
            txt.setStyleSheet("color: gray;")
            row.addWidget(txt)
            tag = QLabel("⚠ uncommitted" if c.has_uncommitted else "⚠ checked out")
            tag.setStyleSheet("color: orange;")
            row.addWidget(tag)
            row.addStretch(1)
            wrap = QWidget()
            wrap.setLayout(row)
            self._list_layout.addWidget(wrap)

    def _add_checkbox(self, c: CleanupCandidate, default_checked: bool):
        cb = QCheckBox(f"{c.branch}  ({_reason(c)})")
        cb.setChecked(default_checked)
        cb.toggled.connect(lambda _=False: self._refresh_button_labels())
        self._list_layout.addWidget(cb)
        self._pairs.append((c, cb))

    # --- admin mode ---

    def set_admin_mode(self, on: bool) -> None:
        self._admin_mode = bool(on)
        if self._admin_banner is not None:
            self._admin_banner.setVisible(self._admin_mode)
        for _, cb in self._protected_pairs:
            if self._admin_mode:
                cb.setEnabled(True)
            else:
                cb.setChecked(False)
                cb.setEnabled(False)

    # --- selection helpers ---

    def selection_state(self) -> list:
        return [(c, cb.isChecked()) for c, cb in self._pairs]

    def trigger_select_all(self) -> None:
        all_checked = bool(self._pairs) and all(cb.isChecked() for _, cb in self._pairs)
        for _, cb in self._pairs:
            cb.setChecked(not all_checked)

    def trigger_subgroup_select(self, target: str) -> None:
        pairs = [(c, cb) for c, cb in self._pairs
                 if c.is_merged and (c.merged_into or "main") == target]
        all_checked = bool(pairs) and all(cb.isChecked() for _, cb in pairs)
        for _, cb in pairs:
            cb.setChecked(not all_checked)

    def trigger_stale_select(self) -> None:
        pairs = [(c, cb) for c, cb in self._pairs if c.is_stale and not c.is_merged]
        all_checked = bool(pairs) and all(cb.isChecked() for _, cb in pairs)
        for _, cb in pairs:
            cb.setChecked(not all_checked)

    def _refresh_button_labels(self) -> None:
        if self._global_btn:
            all_checked = bool(self._pairs) and all(cb.isChecked() for _, cb in self._pairs)
            self._global_btn.setText("Deselect All" if all_checked else "Select All")
        for target, btn in self._subgroup_btns.items():
            pairs = [(c, cb) for c, cb in self._pairs
                     if c.is_merged and (c.merged_into or "main") == target]
            all_checked = bool(pairs) and all(cb.isChecked() for _, cb in pairs)
            btn.setText("Deselect all" if all_checked else "Select all")
        if self._stale_btn is not None:
            pairs = [(c, cb) for c, cb in self._pairs if c.is_stale and not c.is_merged]
            all_checked = bool(pairs) and all(cb.isChecked() for _, cb in pairs)
            self._stale_btn.setText("Deselect all" if all_checked else "Select all")

    # --- delete ---

    def trigger_delete(self) -> None:
        selected = [c for c, cb in self._pairs if cb.isChecked()]
        if self._admin_mode:
            selected += [c for c, cb in self._protected_pairs if cb.isChecked()]
        self._on_delete(selected)
        self.accept()
