import sys

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QLineEdit, QPushButton,
)
from PySide6.QtCore import Qt

_MERGE_BASE_SUFFIX = " (merge base)"


class DiffPointSelector(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._points = []
        self._compare_cb = None
        self._repo_path = None
        self._git_service = None
        self._config_store = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        layout.addWidget(QLabel("NEWER POINT  ─── what you have now ───"))
        self._newer_filter = QLineEdit()
        self._newer_filter.setPlaceholderText("🔍 Search...")
        layout.addWidget(self._newer_filter)
        self._newer_list = QListWidget()
        layout.addWidget(self._newer_list)

        layout.addWidget(QLabel("OLDER POINT  ─── compare against ───"))
        self._older_filter = QLineEdit()
        self._older_filter.setPlaceholderText("🔍 Search...")
        layout.addWidget(self._older_filter)
        self._older_list = QListWidget()
        layout.addWidget(self._older_list)

        self._merge_base_note = QLabel("")
        self._merge_base_note.setObjectName("merge_base_note")
        self._merge_base_note.setStyleSheet("color: #e6ac00;")
        self._merge_base_note.hide()
        layout.addWidget(self._merge_base_note)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self._compare_btn = QPushButton("Compare →")
        btn_row.addWidget(self._compare_btn)
        layout.addLayout(btn_row)

        self._newer_filter.textChanged.connect(lambda text: self._apply_filter(self._newer_list, text))
        self._older_filter.textChanged.connect(lambda text: self._apply_filter(self._older_list, text))
        self._compare_btn.clicked.connect(self._on_compare_clicked)
        self._older_list.currentItemChanged.connect(self._on_older_changed)

    # ── backward-compat aliases so existing tests and callers keep working ────
    @property
    def _from_list(self):
        return self._older_list

    @property
    def _to_list(self):
        return self._newer_list

    @property
    def _from_filter(self):
        return self._older_filter

    @property
    def _to_filter(self):
        return self._newer_filter

    def set_repo(
        self,
        repo_path: str,
        points: list,
        git_service=None,
        suggested_newer: list | None = None,
        suggested_older: list | None = None,
        config_store=None,
    ) -> None:
        self._repo_path = repo_path
        self._git_service = git_service
        self._config_store = config_store
        self._points = points
        # Merge-base resolution needs git; without it we can't resolve, so fall
        # back to raw refs rather than mislabelling tips as merge bases.
        use_merge_base = (
            self._branch_diff_mode() == "merge_base" and self._git_service is not None
        )
        resolved = self._resolve_points(points) if use_merge_base else points
        self._populate_list(self._newer_list, points, suggested_newer)
        self._populate_list(self._older_list, resolved, suggested_older, resolved=use_merge_base, original_points=points)
        self._newer_filter.clear()
        self._older_filter.clear()
        self._merge_base_note.hide()

    def _branch_diff_mode(self) -> str:
        if self._config_store is not None:
            return self._config_store.get_branch_diff_mode()
        return "merge_base"

    def _resolve_points(self, points: list) -> list:
        from worktree_manager.diff_models import HistoryPoint
        result = []
        for pt in points:
            if pt.kind != "branch":
                result.append(pt)
                continue
            try:
                sha = self._git_service.resolve_merge_base(self._repo_path, pt.label, "HEAD")
            except Exception as exc:
                print(
                    f"merge-base resolution failed for {pt.label!r}: {exc}",
                    file=sys.stderr,
                )
                result.append(pt)
                continue
            try:
                message = self._git_service.commit_subject(self._repo_path, sha)
            except Exception as exc:
                print(
                    f"merge-base subject lookup failed for {pt.label!r}: {exc}",
                    file=sys.stderr,
                )
                message = pt.message
            result.append(HistoryPoint(
                kind="branch",
                label=f"{pt.label}{_MERGE_BASE_SUFFIX}",
                short_sha=sha[:12],
                message=message,
            ))
        return result

    def _on_older_changed(self, current, previous) -> None:
        if current is None:
            self._merge_base_note.hide()
            return
        if self._branch_diff_mode() == "merge_base":
            self._merge_base_note.hide()
            return
        ref = current.data(Qt.UserRole)
        point = self._find_point_by_ref(ref)
        if point is None or point.kind != "branch" or self._git_service is None:
            self._merge_base_note.hide()
            return
        try:
            sha = self._git_service.resolve_merge_base(self._repo_path, ref, "HEAD")
            self._merge_base_note.setText(f'⚠ "{ref}" resolved to merge-base {sha}')
            self._merge_base_note.show()
        except Exception:
            self._merge_base_note.hide()

    def _find_point_by_ref(self, ref: str):
        for pt in self._points:
            r = pt.kind if pt.kind.startswith("working_tree") else pt.label
            if r == ref:
                return pt
        return None

    def on_compare(self, callback) -> None:
        self._compare_cb = callback

    def _point_ref(self, pt, resolved: bool = False) -> str:
        if pt.kind.startswith("working_tree"):
            return pt.kind
        if resolved and pt.kind == "branch" and pt.short_sha:
            return pt.short_sha
        return pt.label

    def _populate_list(
        self, lst: QListWidget, points: list, suggested_refs: list | None = None,
        resolved: bool = False, original_points: list | None = None,
    ) -> None:
        lst.clear()
        if suggested_refs:
            header = QListWidgetItem("★ Suggested")
            header.setFlags(header.flags() & ~Qt.ItemIsSelectable & ~Qt.ItemIsEnabled)
            lst.addItem(header)
            # Map original branch labels → resolved display points so suggested_refs
            # (which always use original branch names) find the right resolved entry.
            def orig_key(pt):
                return pt.kind if pt.kind.startswith("working_tree") else pt.label
            src = original_points if original_points is not None else points
            orig_to_resolved = {orig_key(o): r for o, r in zip(src, points)}
            for ref in suggested_refs:
                pt = orig_to_resolved.get(ref)
                if pt is None:
                    item = QListWidgetItem(ref)
                    item.setData(Qt.UserRole, ref)
                elif pt.short_sha:
                    item = QListWidgetItem(f"{pt.label}  {pt.short_sha}  \"{pt.message}\"")
                    item.setData(Qt.UserRole, self._point_ref(pt, resolved))
                else:
                    item = QListWidgetItem(pt.label)
                    item.setData(Qt.UserRole, self._point_ref(pt, resolved))
                lst.addItem(item)
            sep = QListWidgetItem("─" * 30)
            sep.setFlags(sep.flags() & ~Qt.ItemIsSelectable & ~Qt.ItemIsEnabled)
            lst.addItem(sep)
        for pt in points:
            if pt.short_sha:
                text = f"{pt.label}  {pt.short_sha}  \"{pt.message}\""
            else:
                text = pt.label
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, self._point_ref(pt, resolved))
            lst.addItem(item)

    def _apply_filter(self, lst: QListWidget, text: str) -> None:
        lower = text.lower()
        for i in range(lst.count()):
            item = lst.item(i)
            item.setHidden(bool(lower) and lower not in item.text().lower())

    def pre_select(self, from_ref: str | None, to_ref: str | None) -> None:
        self._newer_list.clearSelection()
        self._newer_list.setCurrentItem(None)
        self._older_list.clearSelection()
        self._older_list.setCurrentItem(None)
        # from_ref maps to older (base), to_ref maps to newer (target) — same contract as before
        if from_ref is not None:
            self._select_by_ref(self._older_list, from_ref)
        if to_ref is not None:
            self._select_by_ref(self._newer_list, to_ref)

    def _select_by_ref(self, lst: QListWidget, ref: str) -> None:
        for i in range(lst.count()):
            item = lst.item(i)
            if item.data(Qt.UserRole) == ref:
                lst.setCurrentItem(item)
                return
        # Fallback: a saved branch name (e.g. "main") should match the resolved
        # "main (merge base)" row whose UserRole is the merge-base SHA.
        for i in range(lst.count()):
            item = lst.item(i)
            label_part = (item.text() or "").split("  ")[0].strip()
            branch = label_part.removesuffix(_MERGE_BASE_SUFFIX)
            if branch == ref:
                lst.setCurrentItem(item)
                return

    def _on_compare_clicked(self) -> None:
        older_item = self._older_list.currentItem()
        newer_item = self._newer_list.currentItem()
        if older_item is None or newer_item is None:
            return
        older_ref = older_item.data(Qt.UserRole)
        newer_ref = newer_item.data(Qt.UserRole)
        if older_ref is None or newer_ref is None:
            return
        if self._compare_cb:
            # preserve existing contract: callback(base_ref, target_ref) == (older, newer)
            self._compare_cb(older_ref, newer_ref)
